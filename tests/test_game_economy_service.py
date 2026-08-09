from __future__ import annotations

import hashlib
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

from shared.game_economy_service import DeterministicCoinFlipEngine
from shared.game_economy_service import GameDisabledError
from shared.game_economy_service import GameEconomyService
from shared.game_economy_service import InvalidWagerError
from shared.game_economy_service import LivePayoutDisabledError
from shared.wallet_ledger_service import WalletLedgerService


class GameEconomyServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_game")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("008_game_economy_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.service = GameEconomyService(database_url=self.db_url)
        self.wallet = WalletLedgerService(database_url=self.db_url)
        self.user_id = f"game-{self._testMethodName}"
        self.wallet.ensure_player(self.user_id, username="GameUser")
        self.service.set_feature_flag(
            game_code="COIN_FLIP",
            is_enabled=True,
            allow_live_payout=False,
            min_wager=1,
            max_wager=5000,
        )

    def test_engine_determinism(self) -> None:
        seed = "abc123seed"
        first = DeterministicCoinFlipEngine.compute_outcome(server_seed=seed, pick_value="HEADS")
        second = DeterministicCoinFlipEngine.compute_outcome(server_seed=seed, pick_value="HEADS")
        expected_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()

        self.assertEqual(first["outcome_value"], second["outcome_value"])
        self.assertEqual(first["rng_value"], second["rng_value"])
        self.assertEqual(first["server_seed_hash"], expected_hash)

    def test_invalid_wager_rejected(self) -> None:
        with self.assertRaises(InvalidWagerError):
            self.service.play_coin_flip(
                discord_user_id=self.user_id,
                wager_amount=0,
                pick_value="HEADS",
                idempotency_key="invalid-wager",
                actor_discord_id="admin",
                mode="dry-run",
            )

    def test_disabled_game_rejected(self) -> None:
        self.service.set_feature_flag(
            game_code="COIN_FLIP",
            is_enabled=False,
            allow_live_payout=False,
            min_wager=1,
            max_wager=100,
        )

        with self.assertRaises(GameDisabledError):
            self.service.play_coin_flip(
                discord_user_id=self.user_id,
                wager_amount=10,
                pick_value="TAILS",
                idempotency_key="disabled-game",
                actor_discord_id="admin",
                mode="dry-run",
            )

    def test_live_payout_flag_guard_and_ledger_link(self) -> None:
        self.wallet.credit(
            discord_user_id=self.user_id,
            amount=500,
            reference_type="SEED",
            reference_id=f"seed-{self._testMethodName}",
            reason_code="SEED",
        )

        with self.assertRaises(LivePayoutDisabledError):
            self.service.play_coin_flip(
                discord_user_id=self.user_id,
                wager_amount=25,
                pick_value="HEADS",
                idempotency_key="live-disabled",
                actor_discord_id="admin",
                mode="wallet-settle",
            )

        self.service.set_feature_flag(
            game_code="COIN_FLIP",
            is_enabled=True,
            allow_live_payout=True,
            min_wager=1,
            max_wager=1000,
        )

        result = self.service.play_coin_flip(
            discord_user_id=self.user_id,
            wager_amount=25,
            pick_value="HEADS",
            idempotency_key="live-enabled",
            actor_discord_id="admin",
            mode="wallet-settle",
        )
        self.assertFalse(result.idempotent)

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT debit_ledger_id, payout_ledger_id, debit_reference_id, payout_reference_id
                    FROM game_session
                    WHERE id = %s
                    """,
                    (result.session_id,),
                )
                row = cur.fetchone()

        self.assertIsNotNone(row[0])
        if result.payout_amount > 0:
            self.assertIsNotNone(row[1])
        self.assertIsNotNone(row[2])

    def test_duplicate_idempotency_returns_existing_session(self) -> None:
        first = self.service.play_coin_flip(
            discord_user_id=self.user_id,
            wager_amount=10,
            pick_value="HEADS",
            idempotency_key="dup-001",
            actor_discord_id="admin",
            mode="dry-run",
        )
        second = self.service.play_coin_flip(
            discord_user_id=self.user_id,
            wager_amount=10,
            pick_value="HEADS",
            idempotency_key="dup-001",
            actor_discord_id="admin",
            mode="dry-run",
        )

        self.assertFalse(first.idempotent)
        self.assertTrue(second.idempotent)
        self.assertEqual(first.session_id, second.session_id)

    def test_dry_run_makes_no_direct_balance_writes(self) -> None:
        before = self.wallet.get_balance(self.user_id)

        out = self.service.play_coin_flip(
            discord_user_id=self.user_id,
            wager_amount=15,
            pick_value="TAILS",
            idempotency_key="dry-run-balance",
            actor_discord_id="admin",
            mode="dry-run",
        )

        after = self.wallet.get_balance(self.user_id)
        self.assertEqual(out.mode, "dry-run")
        self.assertEqual(before, after)

        source = (DXEMB_ROOT / "shared" / "game_economy_service.py").read_text(encoding="utf-8")
        self.assertNotIn("UPDATE wallet_account", source)
        self.assertIn("self.wallet.debit", source)


if __name__ == "__main__":
    unittest.main()
