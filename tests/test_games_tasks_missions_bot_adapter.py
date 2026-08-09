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

from bot.cogs.games_local import GamesLocalAdapter
from shared.game_economy_service import GameEconomyService
from shared.mission_bounty_service import MissionBountyService
from shared.task_achievement_service import TaskAchievementService
from shared.wallet_ledger_service import WalletLedgerService


class GamesTasksMissionsBotAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_games_bot")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("008_game_economy_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("009_daily_tasks_achievements_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("010_mission_bounty_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.wallet = WalletLedgerService(database_url=self.db_url)
        self.game = GameEconomyService(database_url=self.db_url)
        self.tasks = TaskAchievementService(database_url=self.db_url)
        self.missions = MissionBountyService(database_url=self.db_url)
        self.adapter = GamesLocalAdapter(
            game_service=self.game,
            task_service=self.tasks,
            mission_service=self.missions,
        )

        self.user_id = f"games-bot-{self._testMethodName}"
        self.wallet.ensure_player(self.user_id, username="GamesBotUser")

        self.game.set_feature_flag(
            game_code="COIN_FLIP",
            is_enabled=True,
            allow_live_payout=False,
            min_wager=10,
            max_wager=500,
        )

        self.tasks.create_task_definition(
            task_code="DAILY_OPEN_2",
            display_name="Open 2 Crates",
            description="Open two crates",
            target_count=2,
            reward_amount=15,
            actor_id="admin",
        )
        self.tasks.create_achievement_definition(
            achievement_code="TASK_COMPLETE_1",
            display_name="First Task",
            description="Complete one daily task",
            trigger_kind="TASK_COMPLETIONS",
            target_value=1,
            reward_amount=20,
            actor_id="admin",
        )

        self.missions.set_feature_flag(is_enabled=True, allow_reward_settlement=False)
        self.mission_id = self.missions.create_mission(
            mission_code=f"MSN-BOT-{self._testMethodName}",
            title="Bot Mission",
            description="Reach target",
            target_count=2,
            reward_amount=30,
            starts_at=datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc),
            expires_at=None,
            actor_id="admin:owner",
        )
        self.missions.activate_mission(mission_id=self.mission_id, actor_id="admin:owner")

    def test_read_only_and_preview_surfaces(self) -> None:
        now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
        self.game.play_coin_flip(
            discord_user_id=self.user_id,
            wager_amount=10,
            pick_value="HEADS",
            idempotency_key=f"g-{self._testMethodName}",
            actor_discord_id="admin",
            mode="dry-run",
        )
        self.tasks.record_task_progress(
            discord_user_id=self.user_id,
            task_code="DAILY_OPEN_2",
            increment=2,
            now=now,
            actor_id="admin",
            apply_reward=False,
        )
        self.tasks.evaluate_task_completion_achievements(
            discord_user_id=self.user_id,
            now=now,
            actor_id="admin",
            apply_reward=False,
        )
        self.missions.record_progress(
            mission_id=self.mission_id,
            discord_user_id=self.user_id,
            increment=2,
            now=now,
            actor_id="admin:owner",
        )

        history = self.adapter.game_history(discord_user_id=self.user_id, limit=10)
        preview = self.adapter.coinflip_preview(
            pick_value="heads",
            wager_amount=25,
            server_seed="seed-preview-123",
        )
        task_rows = self.adapter.task_progress(discord_user_id=self.user_id, limit=10)
        ach_rows = self.adapter.achievement_unlocks(discord_user_id=self.user_id, limit=10)
        mission_rows = self.adapter.mission_status(discord_user_id=self.user_id, limit=10)

        self.assertEqual(history["mode"], "read-only")
        self.assertGreaterEqual(history["count"], 1)

        self.assertEqual(preview["mode"], "dry-run")
        self.assertFalse(preview["applied"])
        self.assertIn(preview["outcome_value"], {"HEADS", "TAILS"})

        self.assertEqual(task_rows["mode"], "read-only")
        self.assertEqual(task_rows["count"], 1)

        self.assertEqual(ach_rows["mode"], "read-only")
        self.assertEqual(ach_rows["count"], 1)

        self.assertEqual(mission_rows["mode"], "read-only")
        self.assertEqual(mission_rows["rows"][0]["status"], "ELIGIBLE")

    def test_adapter_source_avoids_discord_mutation_apis(self) -> None:
        source = (DXEMB_ROOT / "bot" / "cogs" / "games_local.py").read_text(encoding="utf-8")
        forbidden = [
            "add_roles",
            "remove_roles",
            "create_text_channel",
            "create_thread",
            "ban(",
            "kick(",
            "timeout(",
            "edit_permissions",
            "webhook",
            "delete_message",
        ]
        for token in forbidden:
            self.assertNotIn(token, source)

    def test_adapter_source_uses_no_direct_wallet_sql(self) -> None:
        source = (DXEMB_ROOT / "bot" / "cogs" / "games_local.py").read_text(encoding="utf-8")
        self.assertNotIn("UPDATE wallet_account", source)
        self.assertNotIn("INSERT INTO wallet_ledger", source)
        self.assertIn("GameEconomyService", source)


if __name__ == "__main__":
    unittest.main()
