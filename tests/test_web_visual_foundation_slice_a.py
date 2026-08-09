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


class WebVisualFoundationSliceATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_visual_a")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("002_market_escrow_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("006_auto_trader_order_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

        with psycopg2.connect(cls.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO item (classname, display_name, category, subcategory, is_enabled)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (classname) DO NOTHING
                    """,
                    (
                        "SLICE_A_ITEM",
                        "Slice A Item",
                        "Weapons",
                        "Rifles",
                        True,
                    ),
                )

        os.environ["DATABASE_URL"] = cls.db_url

        # These modules cache DATABASE_URL at import time, so rebind per test DB.
        import shared.db as shared_db
        import shared.catalog.service as catalog_service

        shared_db.DATABASE_URL = cls.db_url
        catalog_service.DATABASE_URL = cls.db_url

        app_module = importlib.import_module("web.app")
        cls.app_module = importlib.reload(app_module)
        cls.client = cls.app_module.app.test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def _table_counts(self) -> dict[str, int]:
        tracked_tables = [
            "player",
            "item",
            "escrow_transaction",
            "wallet_ledger",
            "wallet_balance_snapshot",
            "player_listing",
            "market_escrow",
            "trader_product",
            "trader_order",
        ]
        out: dict[str, int] = {}
        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                for table in tracked_tables:
                    cur.execute("SELECT to_regclass(%s)", (table,))
                    exists = cur.fetchone()[0]
                    if exists:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
                        out[table] = int(cur.fetchone()[0])
        return out

    def test_core_routes_preserved_non_500(self) -> None:
        paths = [
            "/",
            "/health",
            "/catalog",
            "/vehicles",
            "/api/vehicles/catalog",
            "/autotrader/products",
        ]
        for path in paths:
            response = self.client.get(path)
            self.assertLess(response.status_code, 500, msg=f"route {path} returned {response.status_code}")

        catalog = self.client.get("/api/vehicles/catalog").get_json()
        if catalog["count"] > 0:
            classname = catalog["families"][0]["classname"]
            detail = self.client.get(f"/vehicles/{classname}")
            self.assertLess(detail.status_code, 500)

    def test_get_pages_do_not_mutate_state(self) -> None:
        before = self._table_counts()

        pages = [
            "/",
            "/health",
            "/catalog",
            "/vehicles",
            "/api/vehicles/catalog",
            "/autotrader/products",
        ]
        for path in pages:
            response = self.client.get(path)
            self.assertLess(response.status_code, 500)

        after = self._table_counts()
        self.assertEqual(before, after)

    def test_image_fallback_behavior_is_controlled(self) -> None:
        vehicles_page = self.client.get("/vehicles")
        body = vehicles_page.get_data(as_text=True)
        self.assertEqual(vehicles_page.status_code, 200)
        self.assertIn("data-fallback-src=\"/static/ui/thumbnail-fallback.svg\"", body)
        self.assertIn("js-fallback-img", body)

        catalog_detail = self.client.get("/catalog/SLICE_A_ITEM")
        detail_body = catalog_detail.get_data(as_text=True)
        self.assertEqual(catalog_detail.status_code, 200)
        self.assertIn("data-fallback-src=\"/static/ui/thumbnail-fallback.svg\"", detail_body)

        fallback_asset = self.client.get("/static/ui/thumbnail-fallback.svg")
        self.assertEqual(fallback_asset.status_code, 200)
        self.assertIn("thumbnail missing", fallback_asset.get_data(as_text=True))

    def test_json_contracts_are_unchanged(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        health_payload = health.get_json()
        self.assertIn("status", health_payload)
        self.assertIn("db", health_payload)
        self.assertIn("connected", health_payload["db"])
        self.assertIn("latency_ms", health_payload["db"])
        self.assertIn("tables", health_payload["db"])

        products = self.client.get("/autotrader/products")
        self.assertEqual(products.status_code, 200)
        products_payload = products.get_json()
        self.assertEqual(products_payload["mode"], "read-only")
        self.assertEqual(products_payload["domain"], "autotrader")


if __name__ == "__main__":
    unittest.main()
