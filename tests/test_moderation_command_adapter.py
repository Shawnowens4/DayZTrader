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

from bot.cogs.moderation_local import LocalModerationAdapter
from shared.moderation_audit_service import ModerationAuditService


class ModerationCommandAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_mod_cmd")
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
        service = ModerationAuditService(database_url=self.db_url)
        self.adapter = LocalModerationAdapter(service=service)

    def test_warn_records_local_action(self) -> None:
        result = self.adapter.warn(
            actor_discord_id="100",
            target_discord_id="200",
            reason="test warn",
            reference_id="cmd-warn-1",
        )
        self.assertTrue(result["applied"])
        self.assertEqual(result["action_type"], "WARN")

    def test_query_status_records_status_query(self) -> None:
        self.adapter.warn(
            actor_discord_id="100",
            target_discord_id="201",
            reason="warn",
            reference_id="cmd-warn-2",
        )
        status = self.adapter.query_status(actor_discord_id="101", target_discord_id="201")
        self.assertEqual(status["counts"]["WARN"], 1)
        self.assertEqual(status["counts"]["STATUS_QUERY"], 1)

    def test_preview_action_does_not_persist(self) -> None:
        preview = self.adapter.preview_action(
            actor_discord_id="102",
            target_discord_id="202",
            reason="preview",
        )
        self.assertTrue(preview["dry_run"])
        status = self.adapter.query_status(actor_discord_id="102", target_discord_id="202")
        # query_status writes one STATUS_QUERY row; preview should not add WARN rows
        self.assertEqual(status["counts"].get("WARN", 0), 0)


if __name__ == "__main__":
    unittest.main()
