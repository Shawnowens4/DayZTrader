from __future__ import annotations

import sys
import unittest
from datetime import datetime
from datetime import timedelta
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

from shared.mission_bounty_service import FeatureDisabledError
from shared.mission_bounty_service import MissionBountyService
from shared.mission_bounty_service import MissionStateError
from shared.mission_bounty_service import PermissionError
from shared.wallet_ledger_service import WalletLedgerService


class MissionBountyServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_mission")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("010_mission_bounty_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.service = MissionBountyService(database_url=self.db_url)
        self.wallet = WalletLedgerService(database_url=self.db_url)
        self.user_id = f"mission-user-{self._testMethodName}"
        self.wallet.ensure_player(self.user_id, username="MissionUser")
        self.service.set_feature_flag(is_enabled=True, allow_reward_settlement=False)

    def _create_active_mission(self, *, expires_at: datetime | None = None) -> int:
        mission_id = self.service.create_mission(
            mission_code=f"MSN-{self._testMethodName}",
            title="Bandit Hunt",
            description="Eliminate bandits",
            target_count=3,
            reward_amount=40,
            starts_at=datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc),
            expires_at=expires_at,
            actor_id="admin:owner",
        )
        self.service.activate_mission(mission_id=mission_id, actor_id="admin:owner")
        return mission_id

    def test_creator_admin_rule(self) -> None:
        with self.assertRaises(PermissionError):
            self.service.create_mission(
                mission_code="MSN-NONADMIN",
                title="Nope",
                description="Nope",
                target_count=1,
                reward_amount=0,
                starts_at=None,
                expires_at=None,
                actor_id="user:123",
            )

    def test_claim_idempotency_and_no_duplicate_reward(self) -> None:
        self.service.set_feature_flag(is_enabled=True, allow_reward_settlement=True)
        mission_id = self._create_active_mission()
        now = datetime(2026, 8, 8, 13, 0, tzinfo=timezone.utc)

        self.service.record_progress(
            mission_id=mission_id,
            discord_user_id=self.user_id,
            increment=3,
            now=now,
            actor_id="admin:owner",
        )

        first = self.service.claim_reward(
            mission_id=mission_id,
            discord_user_id=self.user_id,
            now=now,
            actor_id="admin:owner",
            apply_reward=True,
        )
        second = self.service.claim_reward(
            mission_id=mission_id,
            discord_user_id=self.user_id,
            now=now,
            actor_id="admin:owner",
            apply_reward=True,
        )

        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(self.wallet.get_balance(self.user_id), 40)

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM wallet_ledger
                    WHERE discord_user_id = %s
                      AND reference_type = 'MISSION_REWARD'
                    """,
                    (self.user_id,),
                )
                reward_rows = int(cur.fetchone()[0])
        self.assertEqual(reward_rows, 1)

    def test_cancellation_blocks_progress(self) -> None:
        mission_id = self._create_active_mission()
        self.service.cancel_mission(mission_id=mission_id, actor_id="admin:owner", reason="maintenance")

        with self.assertRaises(MissionStateError):
            self.service.record_progress(
                mission_id=mission_id,
                discord_user_id=self.user_id,
                increment=1,
                now=datetime(2026, 8, 8, 13, 0, tzinfo=timezone.utc),
                actor_id="admin:owner",
            )

    def test_expiry_blocks_progress(self) -> None:
        mission_id = self._create_active_mission(
            expires_at=datetime(2026, 8, 8, 12, 30, tzinfo=timezone.utc)
        )
        with self.assertRaises(MissionStateError):
            self.service.record_progress(
                mission_id=mission_id,
                discord_user_id=self.user_id,
                increment=1,
                now=datetime(2026, 8, 8, 13, 0, tzinfo=timezone.utc),
                actor_id="admin:owner",
            )

    def test_feature_flag_blocks_claim_when_disabled(self) -> None:
        mission_id = self._create_active_mission()
        now = datetime(2026, 8, 8, 13, 0, tzinfo=timezone.utc)
        self.service.record_progress(
            mission_id=mission_id,
            discord_user_id=self.user_id,
            increment=3,
            now=now,
            actor_id="admin:owner",
        )
        self.service.set_feature_flag(is_enabled=False, allow_reward_settlement=False)

        with self.assertRaises(FeatureDisabledError):
            self.service.claim_reward(
                mission_id=mission_id,
                discord_user_id=self.user_id,
                now=now,
                actor_id="admin:owner",
                apply_reward=False,
            )

    def test_no_direct_balance_write_in_service_source(self) -> None:
        source = (DXEMB_ROOT / "shared" / "mission_bounty_service.py").read_text(encoding="utf-8")
        self.assertNotIn("UPDATE wallet_account", source)
        self.assertIn("self.wallet.credit", source)


if __name__ == "__main__":
    unittest.main()
