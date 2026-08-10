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
from shared.auto_trader_order_service import OrderStateError
from shared.auto_trader_order_service import ProductNotAllowedError


class AutoTraderOrderServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_auto_order")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("011_wallet_ledger_run5_additive_upgrade.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("002_market_escrow_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("006_auto_trader_order_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.service = AutoTraderOrderService(database_url=self.db_url)
        self.user_id = f"auto-buyer-{self._testMethodName}"
        self.service.ensure_player(self.user_id, username="AutoBuyer")

        self.item_classname = f"M4A1_{self._testMethodName}"
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

    def _create_item_product(self) -> int:
        return self.service.create_product(
            product_code=f"PRD-{self._testMethodName}",
            product_type="ITEM",
            display_name="M4A1",
            price=350,
            item_classname=self.item_classname,
            created_by="admin",
            stock_limit=100,
            stock_remaining=100,
            console_safe=True,
        )

    def test_state_transitions(self) -> None:
        product_id = self._create_item_product()
        created = self.service.create_order(
            order_reference=f"ORDER-{self._testMethodName}",
            buyer_discord_id=self.user_id,
            product_id=product_id,
            quantity=2,
            created_by="admin",
            initial_state="draft",
        )

        self.service.transition_order(
            order_id=created.order_id,
            to_state="pending_payment",
            actor_discord_id="admin",
            reason_code="PENDING",
            reference_id=f"PENDING-{self._testMethodName}",
        )
        self.service.transition_order(
            order_id=created.order_id,
            to_state="paid",
            actor_discord_id="admin",
            reason_code="PAID",
            reference_id=f"PAID-{self._testMethodName}",
        )
        self.service.transition_order(
            order_id=created.order_id,
            to_state="queued_for_delivery",
            actor_discord_id="admin",
            reason_code="QUEUE",
            reference_id=f"QUEUE-{self._testMethodName}",
        )

        order = self.service.get_order(created.order_id)
        self.assertEqual(order["state"], "queued_for_delivery")

    def test_create_order_idempotency(self) -> None:
        product_id = self._create_item_product()
        reference = f"ORDER-IDEMP-{self._testMethodName}"

        first = self.service.create_order(
            order_reference=reference,
            buyer_discord_id=self.user_id,
            product_id=product_id,
            quantity=1,
            created_by="admin",
            initial_state="draft",
        )
        second = self.service.create_order(
            order_reference=reference,
            buyer_discord_id=self.user_id,
            product_id=product_id,
            quantity=1,
            created_by="admin",
            initial_state="draft",
        )

        self.assertTrue(first.applied)
        self.assertFalse(second.applied)
        self.assertTrue(second.idempotent)
        self.assertEqual(first.order_id, second.order_id)

    def test_allow_list_enforcement(self) -> None:
        product_id = self.service.create_product(
            product_code=f"PRD-DISABLED-{self._testMethodName}",
            product_type="KIT",
            kit_code=f"KIT-{self._testMethodName}",
            display_name="Starter Kit",
            price=120,
            created_by="admin",
            is_enabled=False,
            is_sellable=True,
            console_safe=True,
        )

        with self.assertRaises(ProductNotAllowedError):
            self.service.create_order(
                order_reference=f"ORDER-DISABLED-{self._testMethodName}",
                buyer_discord_id=self.user_id,
                product_id=product_id,
                quantity=1,
                created_by="admin",
            )

    def test_invalid_transition_guard(self) -> None:
        product_id = self._create_item_product()
        created = self.service.create_order(
            order_reference=f"ORDER-STATE-{self._testMethodName}",
            buyer_discord_id=self.user_id,
            product_id=product_id,
            quantity=1,
            created_by="admin",
            initial_state="draft",
        )

        with self.assertRaises(OrderStateError):
            self.service.transition_order(
                order_id=created.order_id,
                to_state="delivered",
                actor_discord_id="admin",
                reason_code="INVALID",
                reference_id=f"INVALID-{self._testMethodName}",
            )

    def test_p2p_tables_untouched(self) -> None:
        product_id = self._create_item_product()
        self.service.create_order(
            order_reference=f"ORDER-SEP-{self._testMethodName}",
            buyer_discord_id=self.user_id,
            product_id=product_id,
            quantity=1,
            created_by="admin",
        )

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM player_listing")
                listing_count = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM market_escrow")
                escrow_count = int(cur.fetchone()[0])

        self.assertEqual(listing_count, 0)
        self.assertEqual(escrow_count, 0)


if __name__ == "__main__":
    unittest.main()
