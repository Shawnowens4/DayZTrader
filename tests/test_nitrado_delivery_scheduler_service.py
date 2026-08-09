from __future__ import annotations

import sys
import unittest
from datetime import datetime
from datetime import timedelta
from datetime import timezone
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
from shared.nitrado_delivery_decision_engine import DecisionPolicy
from shared.nitrado_delivery_fakes import InMemoryDeliveryFileTransport
from shared.nitrado_delivery_fakes import InMemoryRestartWindowProvider
from shared.nitrado_delivery_interfaces import ProviderWindowRecord
from shared.nitrado_delivery_scheduler_service import NitradoDeliverySchedulerService
from shared.nitrado_delivery_scheduler_service import SchedulerBoundaryError
from shared.wallet_ledger_service import WalletLedgerService


class NitradoDeliverySchedulerServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_nit_service")
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
        self.scheduler = NitradoDeliverySchedulerService(database_url=self.db_url)
        self.wallet = WalletLedgerService(database_url=self.db_url)

        self.buyer = f"sched-service-{self._testMethodName}"
        self.order_service.ensure_player(self.buyer, username="SchedService")

        self.item_classname = f"SCHED_SERVICE_ITEM_{self._testMethodName}"
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
            product_code=f"SVC-PRD-{self._testMethodName}",
            product_type="ITEM",
            item_classname=self.item_classname,
            display_name="Service Item",
            price=300,
            created_by="admin",
            console_safe=True,
        )

        created = self.order_service.create_order(
            order_reference=f"SVC-ORDER-{self._testMethodName}",
            buyer_discord_id=self.buyer,
            product_id=self.product_id,
            quantity=1,
            created_by="admin",
            initial_state="paid",
        )
        self.order_id = created.order_id

    def test_enqueue_request_enforces_autotrader_boundary(self) -> None:
        with self.assertRaises(SchedulerBoundaryError):
            self.scheduler.enqueue_delivery_request(
                order_id=self.order_id,
                actor_id="scheduler",
                source_domain="P2P",
            )

    def test_poll_cache_and_decision_flow_uses_fakes(self) -> None:
        now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
        request = self.scheduler.enqueue_delivery_request(
            order_id=self.order_id,
            actor_id="scheduler",
        )
        self.assertTrue(request.applied)

        provider = InMemoryRestartWindowProvider(
            windows=[
                ProviderWindowRecord(
                    source_ref="fake-provider",
                    window_start_at=now + timedelta(minutes=10),
                    window_end_at=now + timedelta(minutes=20),
                    confidence="high",
                    observed_at=now - timedelta(minutes=1),
                    expires_at=now + timedelta(minutes=30),
                    is_conflicting=False,
                )
            ]
        )

        poll = self.scheduler.poll_and_cache_windows(
            provider=provider,
            now=now,
            actor_id="scheduler",
        )
        decision = self.scheduler.evaluate_request(order_id=self.order_id, now=now)

        self.assertEqual(poll["mode"], "dry-run")
        self.assertEqual(poll["cached_windows"], 1)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(decision["action"], "eligible_to_write")
        self.assertEqual(decision["mode"], "dry-run")

        events = self.scheduler.list_events(order_id=self.order_id)
        self.assertGreaterEqual(len(events), 2)

    def test_prepare_artifact_metadata_is_dry_run_only(self) -> None:
        self.scheduler.enqueue_delivery_request(order_id=self.order_id, actor_id="scheduler")
        transport = InMemoryDeliveryFileTransport()

        out = self.scheduler.prepare_artifact_metadata_dry_run(
            order_id=self.order_id,
            artifact_type="xml_staging_metadata",
            payload={"vehicle": "Humvee", "quantity": 1},
            transport=transport,
        )

        self.assertEqual(out["mode"], "dry-run")
        self.assertEqual(len(transport.calls), 1)
        self.assertIsNotNone(out["artifact_hash"])

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM trader_spawn_artifact
                    WHERE order_id = %s
                    """,
                    (self.order_id,),
                )
                artifact_count = int(cur.fetchone()[0])
        self.assertEqual(artifact_count, 1)

    def test_retry_and_alert_are_logged_for_missed_guard(self) -> None:
        now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
        self.scheduler.enqueue_delivery_request(order_id=self.order_id, actor_id="scheduler")

        provider = InMemoryRestartWindowProvider(
            windows=[
                ProviderWindowRecord(
                    source_ref="fake-provider",
                    window_start_at=now + timedelta(minutes=4),
                    window_end_at=now + timedelta(minutes=12),
                    confidence="high",
                    observed_at=now - timedelta(minutes=1),
                    expires_at=now + timedelta(minutes=30),
                    is_conflicting=False,
                )
            ]
        )

        self.scheduler.poll_and_cache_windows(provider=provider, now=now, actor_id="scheduler")
        decision = self.scheduler.evaluate_request(
            order_id=self.order_id,
            now=now,
            policy=DecisionPolicy(poll_interval_minutes=5),
        )

        self.assertEqual(decision["action"], "retry_later")
        self.assertTrue(decision["should_alert"])

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM trader_delivery_attempt
                    WHERE order_id = %s
                    """,
                    (self.order_id,),
                )
                attempts = int(cur.fetchone()[0])

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM trader_delivery_alert
                    WHERE order_id = %s
                    """,
                    (self.order_id,),
                )
                alerts = int(cur.fetchone()[0])

        self.assertEqual(attempts, 1)
        self.assertGreaterEqual(alerts, 1)

    def test_refund_eligibility_link_is_idempotent(self) -> None:
        self.wallet.credit(
            discord_user_id=self.buyer,
            amount=500,
            reference_type="TEST_FUNDS",
            reference_id=f"funds-{self._testMethodName}",
            reason_code="TEST",
        )
        debit = self.wallet.debit(
            discord_user_id=self.buyer,
            amount=50,
            reference_type="AUTO_TRADER_ORDER_DEBIT",
            reference_id=f"debit-{self._testMethodName}",
            reason_code="ORDER_DEBIT",
        )

        first = self.scheduler.link_refund_eligibility(
            order_id=self.order_id,
            refund_reference_id=f"AUTO_TRADER_REFUND:{self.order_id}",
            wallet_ledger_id=debit.ledger_id,
        )
        second = self.scheduler.link_refund_eligibility(
            order_id=self.order_id,
            refund_reference_id=f"AUTO_TRADER_REFUND:{self.order_id}",
            wallet_ledger_id=debit.ledger_id,
        )

        self.assertTrue(first["linked"])
        self.assertFalse(second["linked"])
        self.assertTrue(second["idempotent"])

    def test_scheduler_service_does_not_touch_p2p_tables(self) -> None:
        self.scheduler.enqueue_delivery_request(order_id=self.order_id, actor_id="scheduler")
        requests = self.scheduler.list_requests()
        self.assertGreaterEqual(len(requests), 1)

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
