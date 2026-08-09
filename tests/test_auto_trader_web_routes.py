from __future__ import annotations

import importlib
import os
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


class AutoTraderWebRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_auto_web")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("006_auto_trader_order_foundation.sql"))
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
        self.service = AutoTraderOrderService(database_url=self.db_url)
        self.buyer = f"auto-web-buyer-{self._testMethodName}"
        self.service.ensure_player(self.buyer, username="AutoWebBuyer")

        self.item_classname = f"AUTO_WEB_ITEM_{self._testMethodName}"
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

        self.product_id = self.service.create_product(
            product_code=f"AUTO-WEB-{self._testMethodName}",
            product_type="ITEM",
            item_classname=self.item_classname,
            display_name="Auto Web Item",
            price=450,
            created_by="admin",
            console_safe=True,
        )

    def test_products_preview_and_orders_routes(self) -> None:
        created = self.service.create_order(
            order_reference=f"AUTO-WEB-ORDER-{self._testMethodName}",
            buyer_discord_id=self.buyer,
            product_id=self.product_id,
            quantity=1,
            created_by="admin",
        )
        self.service.transition_order(
            order_id=created.order_id,
            to_state="pending_payment",
            actor_discord_id="admin",
            reason_code="PENDING",
            reference_id=f"PENDING-{self._testMethodName}",
        )

        resp_products = self.client.get("/autotrader/products?limit=10")
        data_products = resp_products.get_json()
        self.assertEqual(resp_products.status_code, 200)
        self.assertEqual(data_products["mode"], "read-only")
        self.assertEqual(data_products["domain"], "autotrader")

        resp_preview = self.client.post(
            "/autotrader/orders/preview",
            json={"product_id": self.product_id, "quantity": 2},
        )
        data_preview = resp_preview.get_json()
        self.assertEqual(resp_preview.status_code, 200)
        self.assertEqual(data_preview["mode"], "dry-run")
        self.assertFalse(data_preview["applied"])

        resp_orders = self.client.get(f"/autotrader/orders?buyer_discord_id={self.buyer}")
        data_orders = resp_orders.get_json()
        self.assertEqual(resp_orders.status_code, 200)
        self.assertGreaterEqual(data_orders["count"], 1)

        resp_detail = self.client.get(f"/autotrader/orders/{created.order_id}")
        data_detail = resp_detail.get_json()
        self.assertEqual(resp_detail.status_code, 200)
        self.assertEqual(data_detail["order"]["state"], "pending_payment")

        resp_history = self.client.get(f"/autotrader/orders/{created.order_id}/history")
        data_history = resp_history.get_json()
        self.assertEqual(resp_history.status_code, 200)
        self.assertGreaterEqual(data_history["count"], 2)

    def test_autotrader_routes_are_namespace_separate_from_p2p(self) -> None:
        rules = self.app_module.app.url_map.iter_rules()
        autotrader_rules = [r.rule for r in rules if r.endpoint.startswith("autotrader_")]
        self.assertGreaterEqual(len(autotrader_rules), 4)
        for rule in autotrader_rules:
            self.assertTrue(rule.startswith("/autotrader"))
            self.assertFalse(rule.startswith("/market"))

    def test_routes_have_no_external_delivery_side_effect_tokens(self) -> None:
        source = (DXEMB_ROOT / "web" / "app.py").read_text(encoding="utf-8")
        forbidden = [
            "nitrado",
            "ftp",
            "xml_generator",
            "force_restart",
            "spawn_item",
            "spawn_vehicle",
            "restart_window_write",
        ]
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
