from __future__ import annotations

import sys
import unittest
from pathlib import Path

import psycopg2

from tests.harness.postgres_isolated import (
    admin_database_url,
    apply_schema,
    apply_sql_file,
    create_disposable_database,
    database_url_for_name,
    disposable_database_name,
    drop_disposable_database,
    ensure_psycopg2_available,
    migration_sql_path,
)

ROOT = Path(__file__).resolve().parents[1]
DXEMB_ROOT = ROOT / "dxemb"
if str(DXEMB_ROOT) not in sys.path:
    sys.path.insert(0, str(DXEMB_ROOT))

from shared.auto_trader_order_service import AutoTraderOrderService
from shared.wallet_ledger_service import WalletLedgerService


class NitradoDeliverySchedulerSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_nit_schema")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("002_market_escrow_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("006_auto_trader_order_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("007_nitrado_delivery_scheduler_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.order_service = AutoTraderOrderService(database_url=self.db_url)
        self.wallet = WalletLedgerService(database_url=self.db_url)
        self.buyer = f"scheduler-buyer-{self._testMethodName}"
        self.order_service.ensure_player(self.buyer, username="SchedulerBuyer")

        self.item_classname = f"SCHED_ITEM_{self._testMethodName}"
        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO item (classname, display_name, category, subcategory, is_enabled)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (classname) DO NOTHING
                    """,
                    (self.item_classname, self.item_classname, "Weapons", "Rifles", True),
                )

        self.product_id = self.order_service.create_product(
            product_code=f"SCHED-PRD-{self._testMethodName}",
            product_type="ITEM",
            item_classname=self.item_classname,
            display_name="Scheduler Item",
            price=200,
            created_by="admin",
            is_enabled=True,
            is_sellable=True,
            console_safe=True,
        )
        self.order = self.order_service.create_order(
            order_reference=f"SCHED-ORDER-{self._testMethodName}",
            buyer_discord_id=self.buyer,
            product_id=self.product_id,
            quantity=1,
            created_by="admin",
            initial_state="paid",
        )

    def test_required_scheduler_tables_exist(self) -> None:
        required_tables = [
            "delivery_poll_run",
            "restart_window_cache",
            "trader_delivery_request",
            "trader_scheduler_event",
            "trader_spawn_artifact",
            "trader_delivery_attempt",
            "trader_delivery_alert",
            "trader_delivery_refund_link",
        ]

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tablename
                    FROM pg_catalog.pg_tables
                    WHERE schemaname = 'public'
                    """
                )
                existing = {row[0] for row in cur.fetchall()}

        for table in required_tables:
            self.assertIn(table, existing)

    def test_delivery_request_requires_existing_trader_order(self) -> None:
        with self.assertRaises(psycopg2.Error):
            with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO trader_delivery_request (order_id, delivery_request_key, state)
                        VALUES (%s, %s, %s)
                        """,
                        (999999999, f"ORDER:999999999:DELIVERY:{self._testMethodName}", "queued_for_delivery"),
                    )

    def test_delivery_request_idempotency_unique_constraints(self) -> None:
        key = f"ORDER:{self.order.order_id}:DELIVERY"
        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trader_delivery_request (order_id, delivery_request_key, state)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (self.order.order_id, key, "queued_for_delivery"),
                )
                first_id = int(cur.fetchone()[0])

        self.assertGreater(first_id, 0)

        with self.assertRaises(psycopg2.Error):
            with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO trader_delivery_request (order_id, delivery_request_key, state)
                        VALUES (%s, %s, %s)
                        """,
                        (self.order.order_id, key, "queued_for_delivery"),
                    )

    def test_scheduler_event_is_immutable(self) -> None:
        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trader_delivery_request (order_id, delivery_request_key, state)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (self.order.order_id, f"ORDER:{self.order.order_id}:IMMUTABLE", "queued_for_delivery"),
                )
                request_id = int(cur.fetchone()[0])

                cur.execute(
                    """
                    INSERT INTO trader_scheduler_event (
                        trader_delivery_request_id,
                        order_id,
                        event_type,
                        from_state,
                        to_state,
                        decision,
                        reason_code,
                        reference_id,
                        details
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        request_id,
                        self.order.order_id,
                        "DECISION_MADE",
                        "queued_for_delivery",
                        "awaiting_restart_window",
                        "hold",
                        "WINDOW_UNKNOWN",
                        f"IMMUTABLE-EVENT-{self._testMethodName}",
                        "{}",
                    ),
                )
                event_id = int(cur.fetchone()[0])

        with self.assertRaises(psycopg2.Error):
            with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE trader_scheduler_event
                        SET reason_code = 'SHOULD_FAIL'
                        WHERE id = %s
                        """,
                        (event_id,),
                    )

    def test_refund_link_uniqueness(self) -> None:
        self.wallet.credit(
            discord_user_id=self.buyer,
            amount=400,
            reference_type="TEST_FUNDS",
            reference_id=f"funds-{self._testMethodName}",
            reason_code="TEST",
        )
        debit = self.wallet.debit(
            discord_user_id=self.buyer,
            amount=100,
            reference_type="AUTO_TRADER_ORDER_DEBIT",
            reference_id=f"debit-{self._testMethodName}",
            reason_code="ORDER_DEBIT",
        )

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trader_delivery_refund_link (
                        order_id,
                        refund_reference_id,
                        wallet_ledger_id,
                        details
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        self.order.order_id,
                        f"AUTO_TRADER_REFUND:{self.order.order_id}",
                        debit.ledger_id,
                        "{}",
                    ),
                )

        with self.assertRaises(psycopg2.Error):
            with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO trader_delivery_refund_link (
                            order_id,
                            refund_reference_id,
                            wallet_ledger_id,
                            details
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            self.order.order_id,
                            f"AUTO_TRADER_REFUND_DUP:{self.order.order_id}",
                            debit.ledger_id,
                            "{}",
                        ),
                    )

    def test_no_scheduler_fk_to_p2p_tables(self) -> None:
        scheduler_tables = (
            "trader_delivery_request",
            "trader_scheduler_event",
            "trader_spawn_artifact",
            "trader_delivery_attempt",
            "trader_delivery_alert",
            "trader_delivery_refund_link",
        )

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT c.confrelid::regclass::text AS referenced_table
                    FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    WHERE c.contype = 'f'
                      AND t.relname = ANY(%s)
                    """,
                    (list(scheduler_tables),),
                )
                refs = {row[0] for row in cur.fetchall()}

        self.assertNotIn("player_listing", refs)
        self.assertNotIn("market_escrow", refs)
        self.assertIn("trader_order", refs)


if __name__ == "__main__":
    unittest.main()
