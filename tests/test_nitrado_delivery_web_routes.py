from __future__ import annotations

import importlib
import os
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
from shared.nitrado_delivery_fakes import InMemoryRestartWindowProvider
from shared.nitrado_delivery_interfaces import ProviderWindowRecord
from shared.nitrado_delivery_scheduler_service import NitradoDeliverySchedulerService


class NitradoDeliveryWebRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_nit_web")
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

        os.environ["DATABASE_URL"] = cls.db_url
        app_module = importlib.import_module("web.app")
        cls.app_module = importlib.reload(app_module)
        cls.client = cls.app_module.app.test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.order_service = AutoTraderOrderService(database_url=self.db_url)
        self.scheduler = NitradoDeliverySchedulerService(database_url=self.db_url)

        self.buyer = f"nit-web-buyer-{self._testMethodName}"
        self.order_service.ensure_player(self.buyer, username="NitWebBuyer")

        self.item_classname = f"NIT_WEB_ITEM_{self._testMethodName}"
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

        product_id = self.order_service.create_product(
            product_code=f"NIT-WEB-PRD-{self._testMethodName}",
            product_type="ITEM",
            item_classname=self.item_classname,
            display_name="Nit Web Item",
            price=500,
            created_by="admin",
            console_safe=True,
        )

        created = self.order_service.create_order(
            order_reference=f"NIT-WEB-ORDER-{self._testMethodName}",
            buyer_discord_id=self.buyer,
            product_id=product_id,
            quantity=1,
            created_by="admin",
            initial_state="paid",
        )
        self.order_id = created.order_id

        self.scheduler.enqueue_delivery_request(order_id=self.order_id, actor_id="scheduler")

        now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
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
        self.scheduler.poll_and_cache_windows(provider=provider, now=now, actor_id="scheduler")
        self.scheduler.evaluate_request(order_id=self.order_id, now=now)

    def test_scheduler_request_and_status_routes_are_read_only(self) -> None:
        resp_requests = self.client.get("/autotrader/scheduler/requests?limit=25")
        requests_data = resp_requests.get_json()

        self.assertEqual(resp_requests.status_code, 200)
        self.assertEqual(requests_data["mode"], "read-only")
        self.assertEqual(requests_data["domain"], "autotrader_scheduler")
        self.assertGreaterEqual(requests_data["count"], 1)

        resp_status = self.client.get(f"/autotrader/scheduler/orders/{self.order_id}/status")
        status_data = resp_status.get_json()

        self.assertEqual(resp_status.status_code, 200)
        self.assertEqual(status_data["mode"], "read-only")
        self.assertEqual(status_data["domain"], "autotrader_scheduler")
        self.assertEqual(status_data["order_id"], self.order_id)
        self.assertGreaterEqual(status_data["event_count"], 1)

    def test_scheduler_status_not_found_for_unknown_order(self) -> None:
        resp = self.client.get("/autotrader/scheduler/orders/999999/status")
        self.assertEqual(resp.status_code, 404)

    def test_scheduler_routes_have_no_mutation_verbs(self) -> None:
        rules = self.app_module.app.url_map.iter_rules()
        scheduler_rules = [r for r in rules if r.rule.startswith("/autotrader/scheduler")]
        self.assertGreaterEqual(len(scheduler_rules), 2)

        for rule in scheduler_rules:
            methods = {m for m in rule.methods if m not in {"HEAD", "OPTIONS"}}
            self.assertEqual(methods, {"GET"})


if __name__ == "__main__":
    unittest.main()
