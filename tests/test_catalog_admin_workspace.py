from __future__ import annotations

import importlib
import json
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

FIXTURE_TYPES = ROOT / "tests" / "fixtures" / "catalog" / "types_valid_small.xml"


class CatalogAdminWorkspaceTests(unittest.TestCase):
    ADMIN_HEADERS = {"X-DXEMB-ROLE": "admin"}

    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_catalog_admin")
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

        cls.catalog_service = catalog_service
        catalog_service.import_types_xml_foundation_sync(path=str(FIXTURE_TYPES), dry_run=False)
        cls._seed_extra_rows()

        app_module = importlib.import_module("web.app")
        cls.app_module = importlib.reload(app_module)
        cls.client = cls.app_module.app.test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    @classmethod
    def _seed_extra_rows(cls) -> None:
        with psycopg2.connect(cls.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO item (classname, display_name, category, subcategory, is_enabled, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (classname) DO NOTHING
                    """,
                    (
                        "LEGACY_TOOL",
                        "Legacy Tool",
                        "legacy",
                        "unknown",
                        False,
                        json.dumps({"manual": {"admin_notes": [{"created_at_utc": "2026-08-10T00:00:00Z", "note": "legacy preserved"}]}}),
                    ),
                )

                for idx in range(1, 31):
                    cur.execute(
                        """
                        INSERT INTO item (classname, display_name, category, subcategory, is_enabled, notes)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (classname) DO NOTHING
                        """,
                        (
                            f"FILLER_{idx:02d}",
                            f"Filler Item {idx:02d}",
                            "tools",
                            "utility",
                            False,
                            json.dumps(_import_notes_payload(f"FILLER_{idx:02d}", usage="Industrial", category="tools")),
                        ),
                    )

                for idx in range(1, 4):
                    cur.execute(
                        """
                        INSERT INTO item (classname, display_name, category, subcategory, is_enabled, notes)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (classname) DO NOTHING
                        """,
                        (
                            f"BULK_{idx}",
                            f"Bulk Item {idx}",
                            "weapons",
                            "bulk",
                            False,
                            json.dumps(_import_notes_payload(f"BULK_{idx}", usage="BulkUsage", category="weapons")),
                        ),
                    )

    def _connect(self):
        return psycopg2.connect(self.db_url, connect_timeout=5)

    def _get_admin(self, path: str):
        return self.client.get(path, headers=self.ADMIN_HEADERS)

    def _post_admin(self, path: str, *, data: dict[str, str], follow_redirects: bool = False):
        return self.client.post(path, data=data, follow_redirects=follow_redirects, headers=self.ADMIN_HEADERS)

    def test_admin_routes_require_admin_role(self) -> None:
        page = self.client.get("/catalog/admin")
        save = self.client.post(
            "/catalog/admin/AKM",
            data={
                "display_name": "AKM",
                "curated_category": "Weapons",
                "curated_subcategory": "Rifles",
                "buy_price": "",
                "sell_price": "",
                "thumbnail_override": "",
                "catalog_enabled": "1",
                "review_required": "1",
                "auto_trader_candidate": "0",
                "direct_purchase_candidate": "0",
                "rental_candidate": "0",
                "bundle_candidate": "0",
                "horde_event_candidate": "0",
                "admin_note_append": "auth check",
            },
        )

        self.assertEqual(page.status_code, 403)
        self.assertEqual(save.status_code, 403)
        self.assertIn("admin role is required", page.get_data(as_text=True))

    def test_legacy_catalog_enabled_mutation_requires_admin_role(self) -> None:
        blocked = self.client.post("/catalog/AKM/enabled", data={"enabled": "0"})
        allowed = self._post_admin("/catalog/AKM/enabled", data={"enabled": "0"})

        self.assertEqual(blocked.status_code, 403)
        self.assertIn("admin role is required", blocked.get_data(as_text=True))
        self.assertEqual(allowed.status_code, 302)
        self.assertFalse(self.catalog_service.get_catalog_admin_item_sync("AKM")["is_enabled"])

    def test_admin_route_renders(self) -> None:
        response = self._get_admin("/catalog/admin")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Catalog Admin Curation Workspace", body)
        self.assertIn("Local admin tooling only", body)
        self.assertNotIn("dayzidb.com", body)

    def test_search_by_classname_and_display_name(self) -> None:
        save = self.client.post(
            "/catalog/admin/AKM",
            data={
                "display_name": "Curated AKM",
                "curated_category": "Weapons",
                "curated_subcategory": "Rifles",
                "buy_price": "1500",
                "sell_price": "900",
                "thumbnail_override": "/static/catalog_items/tourist_map.webp",
                "catalog_enabled": "1",
                "review_required": "1",
                "auto_trader_candidate": "0",
                "direct_purchase_candidate": "0",
                "rental_candidate": "0",
                "bundle_candidate": "0",
                "horde_event_candidate": "0",
                "admin_note_append": "rename for search",
            },
            follow_redirects=True,
            headers=self.ADMIN_HEADERS,
        )
        self.assertEqual(save.status_code, 200)

        by_classname = self._get_admin("/catalog/admin?q=AKM")
        self.assertIn("Curated AKM", by_classname.get_data(as_text=True))

        by_display = self._get_admin("/catalog/admin?q=Curated+AKM")
        self.assertIn("Curated AKM", by_display.get_data(as_text=True))

    def test_filter_behavior(self) -> None:
        response = self._get_admin(
            "/catalog/admin?review_state=yes&warning_state=yes&imported_usage=Industrial"
        )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("BROKEN_NUMBER_ITEM", body)
        self.assertNotIn("AKM", body)

    def test_bounded_result_behavior(self) -> None:
        response = self._get_admin("/catalog/admin?limit=25")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Next", body)
        self.assertLessEqual(body.count('class="action-link"'), 25)

    def test_detail_route_and_lookup(self) -> None:
        ok = self._get_admin("/catalog/admin/AKM")
        missing = self._get_admin("/catalog/admin/DOES_NOT_EXIST")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(missing.status_code, 404)

    def test_read_only_imported_evidence_provenance_rendering(self) -> None:
        response = self._get_admin("/catalog/admin/BROKEN_NUMBER_ITEM")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Imported Evidence and Provenance", body)
        self.assertIn("types_valid_small.xml", body)
        self.assertIn("Malformed field warnings", body)
        self.assertIn("nominal", body)

    def test_manual_curation_persists(self) -> None:
        response = self._post_admin(
            "/catalog/admin/AK74_Black",
            data={
                "display_name": "Curated AK74 Black",
                "curated_category": "Weapons",
                "curated_subcategory": "Assault",
                "buy_price": "2200",
                "sell_price": "1000",
                "thumbnail_override": "/static/catalog_items/tourist_map.webp",
                "catalog_enabled": "1",
                "review_required": "0",
                "auto_trader_candidate": "1",
                "direct_purchase_candidate": "0",
                "rental_candidate": "0",
                "bundle_candidate": "0",
                "horde_event_candidate": "0",
                "admin_note_append": "first curated pass",
            },
            follow_redirects=True,
        )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Saved local admin curation fields", body)
        self.assertIn("Curated AK74 Black", body)

        item = self.catalog_service.get_catalog_admin_item_sync("AK74_Black")
        self.assertEqual(item["display_name"], "Curated AK74 Black")
        self.assertEqual(item["buy_price"], 2200)
        self.assertEqual(item["sell_price"], 1000)
        self.assertTrue(item["future_flags"]["auto_trader_candidate"])
        self.assertEqual(item["manual_thumbnail_override"], "/static/catalog_items/tourist_map.webp")
        self.assertEqual(len(item["admin_notes"]), 1)

    def test_imported_provenance_preserved_after_manual_save(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT notes FROM item WHERE classname = %s", ("AKM",))
                before = json.loads(cur.fetchone()[0])

        self._post_admin(
            "/catalog/admin/AKM",
            data={
                "display_name": "AKM Provenance Safe",
                "curated_category": "Weapons",
                "curated_subcategory": "Rifles",
                "buy_price": "500",
                "sell_price": "250",
                "thumbnail_override": "",
                "catalog_enabled": "0",
                "review_required": "1",
                "auto_trader_candidate": "0",
                "direct_purchase_candidate": "0",
                "rental_candidate": "0",
                "bundle_candidate": "0",
                "horde_event_candidate": "0",
                "admin_note_append": "provenance preservation test",
            },
        )

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT notes FROM item WHERE classname = %s", ("AKM",))
                after = json.loads(cur.fetchone()[0])

        self.assertEqual(before["import"]["source_sha256"], after["import"]["source_sha256"])
        self.assertEqual(before["import"]["evidence_locator"], after["import"]["evidence_locator"])
        self.assertEqual(before["import"]["types_xml"], after["import"]["types_xml"])

    def test_future_eligibility_defaults_false(self) -> None:
        imported_item = self.catalog_service.get_catalog_admin_item_sync("AKM")
        legacy_item = self.catalog_service.get_catalog_admin_item_sync("LEGACY_TOOL")
        self.assertTrue(all(value is False for value in imported_item["future_flags"].values()))
        self.assertTrue(all(value is False for value in legacy_item["future_flags"].values()))

    def test_valid_single_item_enable_disable(self) -> None:
        disable = self._post_admin(
            "/catalog/admin/AKM",
            data={
                "display_name": "AKM",
                "curated_category": "Weapons",
                "curated_subcategory": "Rifles",
                "buy_price": "",
                "sell_price": "",
                "thumbnail_override": "",
                "catalog_enabled": "0",
                "review_required": "1",
                "auto_trader_candidate": "0",
                "direct_purchase_candidate": "0",
                "rental_candidate": "0",
                "bundle_candidate": "0",
                "horde_event_candidate": "0",
                "admin_note_append": "disable catalog",
            },
        )
        enable = self._post_admin(
            "/catalog/admin/AKM",
            data={
                "display_name": "AKM",
                "curated_category": "Weapons",
                "curated_subcategory": "Rifles",
                "buy_price": "",
                "sell_price": "",
                "thumbnail_override": "",
                "catalog_enabled": "1",
                "review_required": "1",
                "auto_trader_candidate": "0",
                "direct_purchase_candidate": "0",
                "rental_candidate": "0",
                "bundle_candidate": "0",
                "horde_event_candidate": "0",
                "admin_note_append": "enable catalog",
            },
        )
        self.assertEqual(disable.status_code, 302)
        self.assertEqual(enable.status_code, 302)
        item = self.catalog_service.get_catalog_admin_item_sync("AKM")
        self.assertTrue(item["is_enabled"])

    def test_invalid_price_thumbnail_flag_input_rejection(self) -> None:
        response = self._post_admin(
            "/catalog/admin/AKM",
            data={
                "display_name": "Bad Input",
                "curated_category": "Weapons",
                "curated_subcategory": "Rifles",
                "buy_price": "-5",
                "sell_price": "3",
                "thumbnail_override": "https://remote.invalid/image.webp",
                "catalog_enabled": "notabool",
                "review_required": "1",
                "auto_trader_candidate": "banana",
                "direct_purchase_candidate": "0",
                "rental_candidate": "0",
                "bundle_candidate": "0",
                "horde_event_candidate": "0",
                "admin_note_append": "bad request",
            },
        )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 400)
        self.assertIn("buy price must be zero or greater", body)
        self.assertIn("thumbnail override must be a local-only asset reference", body)
        self.assertIn("catalog enabled must be a boolean form value", body)
        self.assertIn("Auto Trader candidate must be a boolean form value", body)

    def test_bulk_confirmation_count_mismatch_rejection(self) -> None:
        response = self._post_admin(
            "/catalog/admin/bulk-review",
            data={
                "query": "BULK_",
                "imported_state": "imported",
                "review_state": "yes",
                "enabled_state": "all",
                "image_state": "all",
                "warning_state": "all",
                "imported_category": "",
                "imported_usage": "BulkUsage",
                "auto_trader_candidate": "all",
                "direct_purchase_candidate": "all",
                "rental_candidate": "all",
                "bundle_candidate": "all",
                "horde_event_candidate": "all",
                "limit": "25",
                "bulk_action": "disable",
                "apply_to_filtered": "1",
                "confirmation": "DISABLE 99",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("confirmation token must exactly match DISABLE 3", response.get_data(as_text=True))

    def test_valid_bounded_bulk_enable_disable_behavior(self) -> None:
        response = self._post_admin(
            "/catalog/admin/bulk-review",
            data={
                "query": "BULK_",
                "imported_state": "imported",
                "review_state": "yes",
                "enabled_state": "all",
                "image_state": "all",
                "warning_state": "all",
                "imported_category": "",
                "imported_usage": "BulkUsage",
                "auto_trader_candidate": "all",
                "direct_purchase_candidate": "all",
                "rental_candidate": "all",
                "bundle_candidate": "all",
                "horde_event_candidate": "all",
                "limit": "25",
                "bulk_action": "disable",
                "apply_to_filtered": "1",
                "confirmation": "DISABLE 3",
            },
            follow_redirects=True,
        )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Review-required state disabled for 3 item(s).", body)
        for idx in range(1, 4):
            item = self.catalog_service.get_catalog_admin_item_sync(f"BULK_{idx}")
            self.assertFalse(item["review_required"])

    def test_malformed_warning_display_for_fixture_equivalent(self) -> None:
        response = self._get_admin("/catalog/admin/BROKEN_NUMBER_ITEM")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("source warning", body)
        self.assertIn("nominal", body)

    def test_existing_catalog_and_vehicle_routes_remain_intact(self) -> None:
        catalog = self.client.get("/catalog")
        vehicles = self._get_admin("/vehicles")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(vehicles.status_code, 200)



def _import_notes_payload(classname: str, *, usage: str, category: str) -> dict[str, object]:
    return {
        "import": {
            "source_label": "types.xml:local",
            "source_basename": "seeded.xml",
            "source_sha256": "seeded-sha",
            "imported_at_utc": "2026-08-10T00:00:00Z",
            "evidence_locator": f"/types/type[@name='{classname}']",
            "display_name": classname.replace("_", " "),
            "category": category,
            "subcategory": usage,
            "review_required": False,
            "malformed_fields": [],
            "types_xml": {
                "nominal": 1,
                "lifetime": 100,
                "restock": 0,
                "min": 0,
                "quantmin": -1,
                "quantmax": -1,
                "cost": 100,
                "categories": [category],
                "usages": [usage],
                "values": [],
                "flags": {"count_in_map": "1"},
            },
        }
    }


if __name__ == "__main__":
    unittest.main()
