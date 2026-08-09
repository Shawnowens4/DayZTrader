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

from shared.wallet_ledger_service import InsufficientFundsError
from shared.wallet_ledger_service import WalletLedgerService


class WalletLedgerServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_wallet")
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
        self.user_id = f"wallet-{self._testMethodName}"
        self.service.ensure_player(self.user_id, username="WalletUser")

    def test_credit_increases_balance_and_writes_ledger(self) -> None:
        result = self.service.credit(
            discord_user_id=self.user_id,
            amount=100,
            reference_type="TEST_CREDIT",
            reference_id="credit-001",
            reason_code="TEST",
        )

        self.assertTrue(result.applied)
        self.assertFalse(result.idempotent)
        self.assertEqual(result.balance_after, 100)
        self.assertEqual(self.service.get_balance(self.user_id), 100)

    def test_debit_decreases_balance(self) -> None:
        self.service.credit(
            discord_user_id=self.user_id,
            amount=90,
            reference_type="TEST_CREDIT",
            reference_id="credit-002",
            reason_code="TEST",
        )
        result = self.service.debit(
            discord_user_id=self.user_id,
            amount=40,
            reference_type="TEST_DEBIT",
            reference_id="debit-001",
            reason_code="TEST",
        )

        self.assertTrue(result.applied)
        self.assertEqual(result.balance_before, 90)
        self.assertEqual(result.balance_after, 50)
        self.assertEqual(self.service.get_balance(self.user_id), 50)

    def test_insufficient_funds_raises(self) -> None:
        with self.assertRaises(InsufficientFundsError):
            self.service.debit(
                discord_user_id=self.user_id,
                amount=25,
                reference_type="TEST_DEBIT",
                reference_id="debit-002",
                reason_code="TEST",
            )

    def test_duplicate_reference_is_idempotent(self) -> None:
        first = self.service.credit(
            discord_user_id=self.user_id,
            amount=75,
            reference_type="TEST_CREDIT",
            reference_id="credit-003",
            reason_code="TEST",
        )
        second = self.service.credit(
            discord_user_id=self.user_id,
            amount=75,
            reference_type="TEST_CREDIT",
            reference_id="credit-003",
            reason_code="TEST",
        )

        self.assertTrue(first.applied)
        self.assertFalse(first.idempotent)
        self.assertFalse(second.applied)
        self.assertTrue(second.idempotent)
        self.assertEqual(first.ledger_id, second.ledger_id)
        self.assertEqual(self.service.get_balance(self.user_id), 75)

    def test_ledger_history_order_and_content(self) -> None:
        self.service.credit(
            discord_user_id=self.user_id,
            amount=50,
            reference_type="TEST_CREDIT",
            reference_id="credit-004",
            reason_code="TEST",
        )
        self.service.debit(
            discord_user_id=self.user_id,
            amount=20,
            reference_type="TEST_DEBIT",
            reference_id="debit-004",
            reason_code="TEST",
        )

        history = self.service.list_ledger_entries(self.user_id, limit=10)
        self.assertGreaterEqual(len(history), 2)
        self.assertEqual(history[0]["reference_id"], "debit-004")
        self.assertEqual(history[1]["reference_id"], "credit-004")
        self.assertEqual(history[0]["balance_after"], 30)


if __name__ == "__main__":
    unittest.main()
