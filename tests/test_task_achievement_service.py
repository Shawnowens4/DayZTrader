from __future__ import annotations

import sys
import unittest
from datetime import datetime
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

from shared.task_achievement_service import TaskAchievementService
from shared.wallet_ledger_service import WalletLedgerService


class TaskAchievementServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_tasks")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("009_daily_tasks_achievements_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.service = TaskAchievementService(database_url=self.db_url)
        self.wallet = WalletLedgerService(database_url=self.db_url)
        self.user_id = f"task-user-{self._testMethodName}"
        self.wallet.ensure_player(self.user_id, username="TaskUser")

        self.service.create_task_definition(
            task_code="DAILY_KILL_3",
            display_name="Daily Kills",
            description="Get 3 kills",
            target_count=3,
            reward_amount=50,
            actor_id="admin",
        )
        self.service.create_achievement_definition(
            achievement_code="TASK_STREAK_1",
            display_name="Task Starter",
            description="Complete one task",
            trigger_kind="TASK_COMPLETIONS",
            target_value=1,
            reward_amount=25,
            actor_id="admin",
        )

    def test_progress_and_completion(self) -> None:
        now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
        step1 = self.service.record_task_progress(
            discord_user_id=self.user_id,
            task_code="DAILY_KILL_3",
            increment=2,
            now=now,
            actor_id="admin",
            apply_reward=False,
        )
        step2 = self.service.record_task_progress(
            discord_user_id=self.user_id,
            task_code="DAILY_KILL_3",
            increment=1,
            now=now,
            actor_id="admin",
            apply_reward=True,
        )

        self.assertFalse(step1["completed"])
        self.assertTrue(step2["completed"])
        self.assertTrue(step2["reward_granted"])
        self.assertEqual(self.wallet.get_balance(self.user_id), 50)

    def test_duplicate_reward_prevention(self) -> None:
        now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
        first = self.service.record_task_progress(
            discord_user_id=self.user_id,
            task_code="DAILY_KILL_3",
            increment=3,
            now=now,
            actor_id="admin",
            apply_reward=True,
        )
        second = self.service.record_task_progress(
            discord_user_id=self.user_id,
            task_code="DAILY_KILL_3",
            increment=1,
            now=now,
            actor_id="admin",
            apply_reward=True,
        )

        self.assertTrue(first["reward_granted"])
        self.assertTrue(second["reward_granted"])
        self.assertEqual(self.wallet.get_balance(self.user_id), 50)

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM wallet_ledger
                    WHERE discord_user_id = %s
                      AND reference_type = 'TASK_REWARD'
                    """,
                    (self.user_id,),
                )
                reward_rows = int(cur.fetchone()[0])
        self.assertEqual(reward_rows, 1)

    def test_midnight_utc_reset_cycle(self) -> None:
        before_midnight = datetime(2026, 8, 8, 23, 59, tzinfo=timezone.utc)
        after_midnight = datetime(2026, 8, 9, 0, 1, tzinfo=timezone.utc)

        self.service.record_task_progress(
            discord_user_id=self.user_id,
            task_code="DAILY_KILL_3",
            increment=2,
            now=before_midnight,
            actor_id="admin",
            apply_reward=False,
        )
        self.service.record_task_progress(
            discord_user_id=self.user_id,
            task_code="DAILY_KILL_3",
            increment=1,
            now=after_midnight,
            actor_id="admin",
            apply_reward=False,
        )

        rows = self.service.list_task_progress(discord_user_id=self.user_id, limit=10)
        cycle_dates = {r["cycle_date_utc"] for r in rows}
        self.assertIn("2026-08-08", cycle_dates)
        self.assertIn("2026-08-09", cycle_dates)

    def test_achievement_unlock_idempotency_and_reward(self) -> None:
        now = datetime(2026, 8, 8, 12, 30, tzinfo=timezone.utc)
        self.service.record_task_progress(
            discord_user_id=self.user_id,
            task_code="DAILY_KILL_3",
            increment=3,
            now=now,
            actor_id="admin",
            apply_reward=True,
        )

        unlocked = self.service.evaluate_task_completion_achievements(
            discord_user_id=self.user_id,
            now=now,
            actor_id="admin",
            apply_reward=True,
        )
        unlocked_again = self.service.evaluate_task_completion_achievements(
            discord_user_id=self.user_id,
            now=now,
            actor_id="admin",
            apply_reward=True,
        )

        self.assertEqual(len(unlocked), 1)
        self.assertFalse(unlocked[0]["idempotent"])
        self.assertEqual(len(unlocked_again), 1)
        self.assertTrue(unlocked_again[0]["idempotent"])
        self.assertEqual(self.wallet.get_balance(self.user_id), 75)

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM wallet_ledger
                    WHERE discord_user_id = %s
                      AND reference_type = 'ACH_REWARD'
                    """,
                    (self.user_id,),
                )
                ach_rows = int(cur.fetchone()[0])
        self.assertEqual(ach_rows, 1)

    def test_no_direct_balance_write_in_service_source(self) -> None:
        source = (DXEMB_ROOT / "shared" / "task_achievement_service.py").read_text(encoding="utf-8")
        self.assertNotIn("UPDATE wallet_account", source)
        self.assertIn("self.wallet.credit", source)


if __name__ == "__main__":
    unittest.main()
