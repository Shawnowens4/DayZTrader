from __future__ import annotations

import importlib
import os
import sys
import unittest
from datetime import datetime
from datetime import timezone
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

from shared.game_economy_service import GameEconomyService
from shared.mission_bounty_service import MissionBountyService
from shared.task_achievement_service import TaskAchievementService
from shared.wallet_ledger_service import WalletLedgerService


class GamesTasksMissionsWebRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_games_web")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("011_wallet_ledger_run5_additive_upgrade.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("008_game_economy_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("009_daily_tasks_achievements_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("010_mission_bounty_foundation.sql"))
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
        self.wallet = WalletLedgerService(database_url=self.db_url)
        self.game = GameEconomyService(database_url=self.db_url)
        self.tasks = TaskAchievementService(database_url=self.db_url)
        self.missions = MissionBountyService(database_url=self.db_url)

        self.user_id = f"games-web-{self._testMethodName}"
        self.wallet.ensure_player(self.user_id, username="GamesWebUser")

        self.game.set_feature_flag(
            game_code="COIN_FLIP",
            is_enabled=True,
            allow_live_payout=False,
            min_wager=10,
            max_wager=500,
        )

        self.tasks.create_task_definition(
            task_code="DAILY_WEB_2",
            display_name="Web Task",
            description="Do 2 actions",
            target_count=2,
            reward_amount=12,
            actor_id="admin",
        )
        self.tasks.create_achievement_definition(
            achievement_code="WEB_ACH_1",
            display_name="Web Achievement",
            description="Complete one task",
            trigger_kind="TASK_COMPLETIONS",
            target_value=1,
            reward_amount=5,
            actor_id="admin",
        )

        self.missions.set_feature_flag(is_enabled=True, allow_reward_settlement=False)
        self.mission_id = self.missions.create_mission(
            mission_code=f"MSN-WEB-{self._testMethodName}",
            title="Web Mission",
            description="Reach objective",
            target_count=2,
            reward_amount=40,
            starts_at=datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc),
            expires_at=None,
            actor_id="admin:owner",
        )
        self.missions.activate_mission(mission_id=self.mission_id, actor_id="admin:owner")

    def test_read_only_route_family(self) -> None:
        now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
        self.game.play_coin_flip(
            discord_user_id=self.user_id,
            wager_amount=10,
            pick_value="HEADS",
            idempotency_key=f"w-{self._testMethodName}",
            actor_discord_id="admin",
            mode="dry-run",
        )
        self.tasks.record_task_progress(
            discord_user_id=self.user_id,
            task_code="DAILY_WEB_2",
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

        resp_games = self.client.get(f"/games/sessions?discord_user_id={self.user_id}&limit=10")
        data_games = resp_games.get_json()
        self.assertEqual(resp_games.status_code, 200)
        self.assertEqual(data_games["mode"], "read-only")
        self.assertEqual(data_games["domain"], "game_economy")
        self.assertGreaterEqual(data_games["count"], 1)

        resp_tasks = self.client.get(f"/tasks/progress/{self.user_id}?limit=10")
        data_tasks = resp_tasks.get_json()
        self.assertEqual(resp_tasks.status_code, 200)
        self.assertEqual(data_tasks["mode"], "read-only")
        self.assertEqual(data_tasks["count"], 1)

        resp_ach = self.client.get(f"/achievements/unlocks/{self.user_id}?limit=10")
        data_ach = resp_ach.get_json()
        self.assertEqual(resp_ach.status_code, 200)
        self.assertEqual(data_ach["mode"], "read-only")
        self.assertEqual(data_ach["count"], 1)

        resp_missions = self.client.get("/missions?limit=10")
        data_missions = resp_missions.get_json()
        self.assertEqual(resp_missions.status_code, 200)
        self.assertEqual(data_missions["mode"], "read-only")
        self.assertGreaterEqual(data_missions["count"], 1)

        resp_progress = self.client.get(f"/missions/progress/{self.user_id}?limit=10")
        data_progress = resp_progress.get_json()
        self.assertEqual(resp_progress.status_code, 200)
        self.assertEqual(data_progress["mode"], "read-only")
        self.assertEqual(data_progress["rows"][0]["status"], "ELIGIBLE")

    def test_coinflip_preview_route_is_dry_run(self) -> None:
        before = self.wallet.get_balance(self.user_id)
        resp = self.client.post(
            "/games/coinflip/preview",
            json={"pick_value": "HEADS", "wager_amount": 25, "server_seed": "abc-seed"},
        )
        data = resp.get_json()
        after = self.wallet.get_balance(self.user_id)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["mode"], "dry-run")
        self.assertFalse(data["applied"])
        self.assertIn(data["outcome_value"], {"HEADS", "TAILS"})
        self.assertEqual(before, after)

    def test_games_task_mission_routes_have_no_mutation_verbs_except_preview(self) -> None:
        rules = list(self.app_module.app.url_map.iter_rules())
        read_only_prefixes = ["/games/sessions", "/tasks/progress", "/achievements/unlocks", "/missions"]

        for rule in rules:
            if any(rule.rule.startswith(prefix) for prefix in read_only_prefixes) and rule.rule != "/games/coinflip/preview":
                methods = {m for m in rule.methods if m not in {"HEAD", "OPTIONS"}}
                self.assertEqual(methods, {"GET"})

    def test_routes_do_not_reference_external_or_spawn_operations(self) -> None:
        source = (DXEMB_ROOT / "web" / "app.py").read_text(encoding="utf-8")
        forbidden = [
            "spawn_item",
            "spawn_vehicle",
            "force_restart",
            "ftp",
            "nitrado_client",
            "xml_generator",
        ]
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
