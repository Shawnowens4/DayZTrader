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

from bot.cogs.wallet_local import WalletLocalAdapter
from shared.wallet_ledger_service import WalletLedgerService


class WalletBotAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_wallet_bot")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.service = WalletLedgerService(database_url=self.db_url)
        self.user_id = f"wallet-bot-{self._testMethodName}"
        self.service.ensure_player(self.user_id, username="WalletBotUser")
        self.adapter = WalletLocalAdapter(service=self.service)

    def test_balance_and_history_read_only(self) -> None:
        self.service.credit(
            discord_user_id=self.user_id,
            amount=120,
            reference_type="TEST",
            reference_id=f"credit-{self._testMethodName}",
            reason_code="TEST",
        )

        bal = self.adapter.balance(discord_user_id=self.user_id)
        hist = self.adapter.transaction_history(discord_user_id=self.user_id, limit=5)

        self.assertTrue(bal["read_only"])
        self.assertEqual(bal["balance"], 120)
        self.assertTrue(hist["read_only"])
        self.assertEqual(hist["count"], 1)

    def test_preview_does_not_mutate(self) -> None:
        self.service.credit(
            discord_user_id=self.user_id,
            amount=80,
            reference_type="TEST",
            reference_id=f"credit-{self._testMethodName}",
            reason_code="TEST",
        )

        before = self.service.get_balance(self.user_id)
        credit_preview = self.adapter.preview_credit(discord_user_id=self.user_id, amount=20)
        debit_preview = self.adapter.preview_debit(discord_user_id=self.user_id, amount=200)
        after = self.service.get_balance(self.user_id)

        self.assertEqual(before, after)
        self.assertFalse(credit_preview["applied"])
        self.assertFalse(debit_preview["applied"])
        self.assertFalse(debit_preview["allowed"])

    def test_no_discord_mutation_api_usage_in_wallet_local_source(self) -> None:
        source = (DXEMB_ROOT / "bot" / "cogs" / "wallet_local.py").read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
