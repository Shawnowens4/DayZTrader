from __future__ import annotations

import sys
import unittest
from pathlib import Path

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

from shared.moderation_audit_service import ModerationAuditService


class ModerationAuditServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_mod_audit")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("003_moderation_audit_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.service = ModerationAuditService(database_url=self.db_url)

    def test_warn_records_action(self) -> None:
        result = self.service.record_warn(
            actor_discord_id="admin-1",
            target_discord_id="player-1",
            reason="spam links",
            reference_id="warn-ref-1",
        )

        self.assertTrue(result["applied"])
        self.assertFalse(result["idempotent"])
        self.assertEqual(result["action_type"], "WARN")

    def test_warn_is_idempotent_by_reference(self) -> None:
        first = self.service.record_warn(
            actor_discord_id="admin-1",
            target_discord_id="player-2",
            reason="caps abuse",
            reference_id="warn-ref-2",
        )
        second = self.service.record_warn(
            actor_discord_id="admin-1",
            target_discord_id="player-2",
            reason="caps abuse",
            reference_id="warn-ref-2",
        )

        self.assertTrue(first["applied"])
        self.assertFalse(second["applied"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(first["id"], second["id"])

    def test_target_status_counts_and_latest(self) -> None:
        self.service.record_warn(
            actor_discord_id="admin-1",
            target_discord_id="player-3",
            reason="rule 1",
            reference_id="warn-ref-3-a",
        )
        self.service.record_warn(
            actor_discord_id="admin-2",
            target_discord_id="player-3",
            reason="rule 2",
            reference_id="warn-ref-3-b",
        )
        self.service.record_status_query(
            actor_discord_id="admin-2",
            target_discord_id="player-3",
            reference_id="status-ref-3",
        )

        status = self.service.get_target_status("player-3")
        self.assertEqual(status["counts"].get("WARN"), 2)
        self.assertEqual(status["counts"].get("STATUS_QUERY"), 1)
        self.assertEqual(status["latest"]["action_type"], "STATUS_QUERY")

    def test_dry_run_preview_is_non_mutating(self) -> None:
        preview = self.service.build_dry_run_preview(
            actor_discord_id="admin-3",
            target_discord_id="player-4",
            action_type="WARN",
            reason="preview only",
        )

        self.assertFalse(preview["applied"])
        self.assertTrue(preview["dry_run"])
        status = self.service.get_target_status("player-4")
        self.assertEqual(status["counts"], {})
        self.assertIsNone(status["latest"])

    def test_moderation_table_is_immutable(self) -> None:
        import psycopg2

        created = self.service.record_warn(
            actor_discord_id="admin-4",
            target_discord_id="player-5",
            reason="immutability",
            reference_id="warn-ref-5",
        )

        with self.assertRaises(psycopg2.Error):
            with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE moderation_action SET reason = %s WHERE id = %s",
                        ("changed", created["id"]),
                    )


if __name__ == "__main__":
    unittest.main()
