from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

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

FIXTURES = ROOT / "tests" / "fixtures" / "catalog"


class TypesXmlImportFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        import psycopg2

        cls._psycopg2 = psycopg2
        cls.db_name = disposable_database_name(prefix="dxemb_types_import")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)

        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

        os.environ["DATABASE_URL"] = cls.db_url

        import shared.db as shared_db
        import shared.catalog.service as catalog_service

        shared_db.DATABASE_URL = cls.db_url
        catalog_service.DATABASE_URL = cls.db_url

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def _connect(self):
        return self._psycopg2.connect(self.db_url, connect_timeout=5)

    def test_parse_rejects_malformed_xml(self) -> None:
        from shared.catalog.types_xml import TypesXmlParseError
        from shared.catalog.types_xml import parse_types_xml_for_import

        malformed = FIXTURES / "types_malformed.xml"
        with self.assertRaises(TypesXmlParseError):
            parse_types_xml_for_import(malformed)

    def test_dry_run_then_apply_is_idempotent_and_preserves_curated_fields(self) -> None:
        from shared.catalog.service import import_types_xml_foundation_sync

        fixture_path = FIXTURES / "types_valid_small.xml"

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO item (
                        classname,
                        display_name,
                        category,
                        subcategory,
                        buy_price,
                        sell_price,
                        is_enabled,
                        thumbnail_url,
                        notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (classname) DO NOTHING
                    """,
                    (
                        "AKM",
                        "AKM Curated Name",
                        "legacy",
                        "legacy_sub",
                        4200,
                        1800,
                        True,
                        "/static/catalog_items/custom_akm.webp",
                        json.dumps({"manual_note": "keep me"}),
                    ),
                )

        dry = import_types_xml_foundation_sync(path=str(fixture_path), dry_run=True)
        self.assertEqual(dry["mode"], "dry-run")
        self.assertEqual(dry["parsed"], 3)
        self.assertEqual(dry["created"], 2)
        self.assertEqual(dry["updated"], 1)
        self.assertEqual(dry["unchanged"], 0)
        self.assertEqual(dry["review_required"], 2)
        self.assertEqual(dry["malformed"], 1)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM item")
                self.assertEqual(cur.fetchone()[0], 1)

        applied = import_types_xml_foundation_sync(path=str(fixture_path), dry_run=False)
        self.assertEqual(applied["mode"], "apply")
        self.assertEqual(applied["created"], 2)
        self.assertEqual(applied["updated"], 1)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT buy_price, sell_price, is_enabled, thumbnail_url, category, notes
                    FROM item
                    WHERE classname = %s
                    """,
                    ("AKM",),
                )
                row = cur.fetchone()

        self.assertEqual(row[0], 4200)
        self.assertEqual(row[1], 1800)
        self.assertTrue(row[2])
        self.assertEqual(row[3], "/static/catalog_items/custom_akm.webp")
        self.assertEqual(row[4], "weapons")

        notes = json.loads(row[5] or "{}") if isinstance(row[5], str) else (row[5] or {})
        self.assertEqual(notes.get("manual_note"), "keep me")
        self.assertIn("import", notes)
        self.assertEqual(notes["import"].get("source_basename"), "types_valid_small.xml")
        self.assertEqual(notes["import"].get("evidence_locator"), "/types/type[1][@name='AKM']")

        again = import_types_xml_foundation_sync(path=str(fixture_path), dry_run=False)
        self.assertEqual(again["created"], 0)
        self.assertEqual(again["updated"], 0)
        self.assertEqual(again["unchanged"], 3)


if __name__ == "__main__":
    unittest.main()
