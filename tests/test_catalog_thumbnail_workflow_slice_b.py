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
    create_disposable_database,
    database_url_for_name,
    disposable_database_name,
    drop_disposable_database,
    ensure_psycopg2_available,
)

ROOT = Path(__file__).resolve().parents[1]
DXEMB_ROOT = ROOT / "dxemb"
if str(DXEMB_ROOT) not in sys.path:
    sys.path.insert(0, str(DXEMB_ROOT))


class CatalogThumbnailWorkflowSliceBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_catalog_b")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

        with psycopg2.connect(cls.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO item (classname, display_name, category, subcategory, is_enabled, thumbnail_url)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (classname) DO NOTHING
                    """,
                    (
                        "CATALOG_LOCAL_ITEM",
                        "Catalog Local Item",
                        "Maps",
                        "Utility",
                        True,
                        "https://example.invalid/assets/tourist_map.webp",
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO item (classname, display_name, category, subcategory, is_enabled, thumbnail_url)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (classname) DO NOTHING
                    """,
                    (
                        "CATALOG_REMOTE_ITEM",
                        "Catalog Remote Item",
                        "Maps",
                        "Utility",
                        True,
                        "https://example.invalid/assets/not_present_anywhere.webp",
                    ),
                )

        os.environ["DATABASE_URL"] = cls.db_url

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

    def test_catalog_list_shows_thumbnail_cards(self) -> None:
        response = self.client.get("/catalog")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("item-thumb", body)
        self.assertIn("js-fallback-img", body)

    def test_catalog_detail_prefers_local_thumbnail_when_available(self) -> None:
        response = self.client.get("/catalog/CATALOG_LOCAL_ITEM")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("/static/catalog_items/tourist_map.webp", body)

    def test_catalog_detail_uses_remote_when_local_missing(self) -> None:
        response = self.client.get("/catalog/CATALOG_REMOTE_ITEM")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("https://example.invalid/assets/not_present_anywhere.webp", body)
        self.assertIn('data-fallback-src="/static/ui/thumbnail-fallback.svg"', body)

    def test_catalog_filters_and_query_contracts_still_work(self) -> None:
        response = self.client.get("/catalog?q=CATALOG_LOCAL_ITEM&state=enabled")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("CATALOG_LOCAL_ITEM", body)
        self.assertNotIn("Internal Server Error", body)


if __name__ == "__main__":
    unittest.main()
