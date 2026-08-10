from __future__ import annotations

import sys
import threading
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

from shared.wallet_ledger_service import InsufficientFundsError
from shared.wallet_ledger_service import InvalidAmountError
from shared.wallet_ledger_service import InvalidOwnerError
from shared.wallet_ledger_service import MetadataValidationError
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
            apply_sql_file(cls.db_url, migration_sql_path("011_wallet_ledger_run5_additive_upgrade.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.service = WalletLedgerService(database_url=self.db_url)
        self.owner_id = f"local:wallet-{self._testMethodName}"
        self.service.ensure_wallet_owner(self.owner_id, display_name="WalletUser", owner_kind="LOCAL_PLAYER")

    def _connect(self):
        return psycopg2.connect(self.db_url, connect_timeout=5)

    def test_create_get_wallet_owner_behavior(self) -> None:
        owner = self.service.get_wallet_owner(self.owner_id)
        self.assertIsNotNone(owner)
        self.assertEqual(owner["owner_id"], self.owner_id)
        self.assertEqual(owner["owner_kind"], "LOCAL_PLAYER")
        self.assertEqual(owner["balance_minor"], 0)

    def test_credit_behavior_and_integer_balance_result(self) -> None:
        result = self.service.credit(
            discord_user_id=self.owner_id,
            amount=100,
            reference_type="TEST_CREDIT",
            reference_id="credit-001",
            reason_code="TEST",
            idempotency_key="wallet-credit-001",
        )

        self.assertTrue(result.applied)
        self.assertEqual(result.amount_minor, 100)
        self.assertEqual(result.balance_after_minor, 100)
        self.assertEqual(self.service.get_balance(self.owner_id), 100)

    def test_debit_behavior_and_insufficient_funds_rejection(self) -> None:
        self.service.credit(
            discord_user_id=self.owner_id,
            amount=90,
            reference_type="TEST_CREDIT",
            reference_id="credit-002",
            reason_code="TEST",
            idempotency_key="wallet-credit-002",
        )
        debit = self.service.debit(
            discord_user_id=self.owner_id,
            amount=40,
            reference_type="TEST_DEBIT",
            reference_id="debit-001",
            reason_code="TEST",
            idempotency_key="wallet-debit-001",
        )

        self.assertEqual(debit.balance_before, 90)
        self.assertEqual(debit.balance_after, 50)

        with self.assertRaises(InsufficientFundsError):
            self.service.debit(
                discord_user_id=self.owner_id,
                amount=80,
                reference_type="TEST_DEBIT",
                reference_id="debit-002",
                reason_code="TEST",
                idempotency_key="wallet-debit-002",
            )

    def test_duplicate_idempotency_does_not_double_apply(self) -> None:
        first = self.service.credit(
            discord_user_id=self.owner_id,
            amount=75,
            reference_type="TEST_CREDIT",
            reference_id="credit-003",
            reason_code="TEST",
            idempotency_key="wallet-credit-003",
        )
        second = self.service.credit(
            discord_user_id=self.owner_id,
            amount=75,
            reference_type="TEST_CREDIT",
            reference_id="credit-003-different",
            reason_code="TEST",
            idempotency_key="wallet-credit-003",
        )

        self.assertTrue(first.applied)
        self.assertFalse(second.applied)
        self.assertTrue(second.idempotent)
        self.assertEqual(self.service.get_balance(self.owner_id), 75)

    def test_concurrent_debit_safety(self) -> None:
        self.service.credit(
            discord_user_id=self.owner_id,
            amount=100,
            reference_type="TEST_CREDIT",
            reference_id="credit-004",
            reason_code="TEST",
            idempotency_key="wallet-credit-004",
        )

        barrier = threading.Barrier(3)
        outcomes: list[str] = []

        def worker(name: str) -> None:
            local_service = WalletLedgerService(database_url=self.db_url)
            barrier.wait()
            try:
                local_service.debit(
                    discord_user_id=self.owner_id,
                    amount=80,
                    reference_type="TEST_CONCURRENT_DEBIT",
                    reference_id=name,
                    reason_code="TEST",
                    idempotency_key=f"{name}-idempotency",
                )
                outcomes.append("applied")
            except InsufficientFundsError:
                outcomes.append("insufficient")

        t1 = threading.Thread(target=worker, args=("thread-1",))
        t2 = threading.Thread(target=worker, args=("thread-2",))
        t1.start()
        t2.start()
        barrier.wait()
        t1.join()
        t2.join()

        self.assertEqual(sorted(outcomes), ["applied", "insufficient"])
        self.assertEqual(self.service.get_balance(self.owner_id), 20)

    def test_append_only_immutability(self) -> None:
        entry = self.service.credit(
            discord_user_id=self.owner_id,
            amount=20,
            reference_type="TEST_CREDIT",
            reference_id="credit-immut",
            reason_code="TEST",
            idempotency_key="wallet-credit-immut",
        )

        with self._connect() as conn:
            with conn.cursor() as cur:
                with self.assertRaises(psycopg2.Error):
                    cur.execute("UPDATE wallet_ledger SET reason_text = 'bad' WHERE id = %s", (entry.ledger_id,))
                conn.rollback()
                with self.assertRaises(psycopg2.Error):
                    cur.execute("DELETE FROM wallet_ledger WHERE id = %s", (entry.ledger_id,))

    def test_compensating_reversal_and_refund_behavior(self) -> None:
        credit = self.service.credit(
            discord_user_id=self.owner_id,
            amount=60,
            reference_type="TEST_CREDIT",
            reference_id="credit-reverse",
            reason_code="TEST",
            idempotency_key="wallet-credit-reverse",
        )
        reversal = self.service.reverse_entry(
            owner_id=self.owner_id,
            original_ledger_id=credit.ledger_id,
            transaction_type="REVERSAL",
            idempotency_key="wallet-reversal-001",
            actor_id="local_admin",
            actor_source="local_admin",
            reason_text="reverse mistaken credit",
        )
        self.assertEqual(reversal.signed_amount, -60)
        self.assertEqual(self.service.get_balance(self.owner_id), 0)

        self.service.credit(
            discord_user_id=self.owner_id,
            amount=25,
            reference_type="TEST_CREDIT",
            reference_id="credit-refund-base",
            reason_code="TEST",
            idempotency_key="wallet-credit-refund-base",
        )
        debit = self.service.debit(
            discord_user_id=self.owner_id,
            amount=20,
            reference_type="TEST_DEBIT",
            reference_id="debit-refund",
            reason_code="TEST",
            idempotency_key="wallet-debit-refund",
        )
        refund = self.service.reverse_entry(
            owner_id=self.owner_id,
            original_ledger_id=debit.ledger_id,
            transaction_type="REFUND",
            idempotency_key="wallet-refund-001",
            actor_id="local_admin",
            actor_source="local_admin",
            reason_text="refund mistaken debit",
        )
        self.assertEqual(refund.signed_amount, 20)
        self.assertEqual(self.service.get_balance(self.owner_id), 25)

    def test_admin_adjustment_requires_reason_and_exact_idempotency(self) -> None:
        with self.assertRaises(InvalidAmountError):
            self.service.admin_adjust(
                discord_user_id=self.owner_id,
                signed_amount=50,
                reference_id="admin-adjust-001",
                reason_code="ADMIN_CREDIT",
                reason_text="",
                actor_discord_id="local_admin",
                idempotency_key="admin-adjust-001",
            )

        result = self.service.admin_adjust(
            discord_user_id=self.owner_id,
            signed_amount=50,
            reference_id="admin-adjust-001",
            reason_code="ADMIN_CREDIT",
            reason_text="manual credit",
            actor_discord_id="local_admin",
            idempotency_key="admin-adjust-001",
        )
        duplicate = self.service.admin_adjust(
            discord_user_id=self.owner_id,
            signed_amount=50,
            reference_id="admin-adjust-001-different",
            reason_code="ADMIN_CREDIT",
            reason_text="manual credit",
            actor_discord_id="local_admin",
            idempotency_key="admin-adjust-001",
        )

        self.assertTrue(result.applied)
        self.assertTrue(duplicate.idempotent)
        self.assertEqual(self.service.get_balance(self.owner_id), 50)

    def test_invalid_amount_metadata_and_owner_rejection(self) -> None:
        with self.assertRaises(InvalidOwnerError):
            self.service.ensure_wallet_owner("bad owner id")

        with self.assertRaises(InvalidAmountError):
            self.service.credit(
                discord_user_id=self.owner_id,
                amount=0,
                reference_type="TEST",
                reference_id="zero",
                reason_code="TEST",
                idempotency_key="zero-key",
            )

        with self.assertRaises(MetadataValidationError):
            self.service.credit(
                discord_user_id=self.owner_id,
                amount=10,
                reference_type="TEST",
                reference_id="bad-meta",
                reason_code="TEST",
                idempotency_key="bad-meta-key",
                metadata={"token": "secret"},
            )

    def test_reconciliation_balance_parity(self) -> None:
        self.service.credit(
            discord_user_id=self.owner_id,
            amount=30,
            reference_type="TEST_CREDIT",
            reference_id="credit-reconcile",
            reason_code="TEST",
            idempotency_key="wallet-credit-reconcile",
        )
        self.service.debit(
            discord_user_id=self.owner_id,
            amount=10,
            reference_type="TEST_DEBIT",
            reference_id="debit-reconcile",
            reason_code="TEST",
            idempotency_key="wallet-debit-reconcile",
        )
        reconciliation = self.service.reconcile_balance(self.owner_id)

        self.assertTrue(reconciliation["matches"])
        self.assertEqual(reconciliation["account_balance_minor"], 20)
        self.assertEqual(reconciliation["ledger_total_minor"], 20)

    def test_wallet_summary_contains_totals_and_recent_reference(self) -> None:
        self.service.credit(
            discord_user_id=self.owner_id,
            amount=100,
            reference_type="AUTO_TRADER_ORDER_DEBIT",
            reference_id="order-01",
            reason_code="TEST",
            idempotency_key="summary-credit",
        )
        self.service.debit(
            discord_user_id=self.owner_id,
            amount=40,
            reference_type="TEST_DEBIT",
            reference_id="debit-01",
            reason_code="TEST",
            idempotency_key="summary-debit",
        )

        summary = self.service.get_wallet_summary(self.owner_id)

        self.assertIsNotNone(summary)
        self.assertEqual(summary["balance_minor"], 60)
        self.assertEqual(summary["total_credits_minor"], 100)
        self.assertEqual(summary["total_debits_minor"], 40)
        self.assertEqual(summary["ledger_net_minor"], 60)
        self.assertIsNotNone(summary["recent_reference"])

    def test_list_ledger_history_filters_and_ordering(self) -> None:
        self.service.credit(
            discord_user_id=self.owner_id,
            amount=20,
            reference_type="FILTER",
            reference_id="credit-a",
            reason_code="TEST",
            idempotency_key="filter-credit-a",
        )
        self.service.debit(
            discord_user_id=self.owner_id,
            amount=5,
            reference_type="FILTER",
            reference_id="debit-a",
            reason_code="TEST",
            idempotency_key="filter-debit-a",
        )
        self.service.credit(
            discord_user_id=self.owner_id,
            amount=30,
            reference_type="AUTO_TRADER_ORDER_DEBIT",
            reference_id="credit-b",
            reason_code="TEST",
            idempotency_key="filter-credit-b",
            metadata={"order_id": 77},
        )

        all_rows = self.service.list_ledger_history(self.owner_id, limit=10, offset=0)
        credit_rows = self.service.list_ledger_history(self.owner_id, direction="credit", limit=10, offset=0)
        searched_rows = self.service.list_ledger_history(self.owner_id, reference_query="credit-b", limit=10, offset=0)
        paged_rows = self.service.list_ledger_history(self.owner_id, limit=1, offset=1)

        self.assertGreaterEqual(len(all_rows), 3)
        self.assertTrue(all_rows[0]["id"] > all_rows[1]["id"])
        self.assertTrue(all(row["signed_amount"] > 0 for row in credit_rows))
        self.assertEqual(len(searched_rows), 1)
        self.assertEqual(searched_rows[0]["reference_id"], "credit-b")
        self.assertEqual(len(paged_rows), 1)

    def test_create_authorized_entry_idempotency_and_funds_guards(self) -> None:
        first = self.service.create_authorized_entry(
            owner_id=self.owner_id,
            operation="credit",
            amount_minor=55,
            reason_text="grant",
            actor_id="local_admin",
            idempotency_key="authorized-credit-001",
            reference_id="authorized-credit-001",
        )
        duplicate = self.service.create_authorized_entry(
            owner_id=self.owner_id,
            operation="credit",
            amount_minor=55,
            reason_text="grant",
            actor_id="local_admin",
            idempotency_key="authorized-credit-001",
            reference_id="authorized-credit-001",
        )

        self.assertTrue(first.applied)
        self.assertTrue(duplicate.idempotent)
        self.assertEqual(self.service.get_balance(self.owner_id), 55)

        with self.assertRaises(InsufficientFundsError):
            self.service.create_authorized_entry(
                owner_id=self.owner_id,
                operation="debit",
                amount_minor=500,
                reason_text="too much",
                actor_id="local_admin",
                idempotency_key="authorized-debit-001",
            )

    def test_reverse_entry_duplicate_guardrails_and_idempotency(self) -> None:
        credit = self.service.credit(
            discord_user_id=self.owner_id,
            amount=80,
            reference_type="TEST_CREDIT",
            reference_id="rev-src-1",
            reason_code="TEST",
            idempotency_key="rev-src-1",
        )

        first = self.service.reverse_entry(
            owner_id=self.owner_id,
            original_ledger_id=credit.ledger_id,
            transaction_type="REVERSAL",
            idempotency_key="rev-entry-001",
            actor_id="local_admin",
            actor_source="local_admin",
            reason_text="reverse once",
        )
        repeat_same_key = self.service.reverse_entry(
            owner_id=self.owner_id,
            original_ledger_id=credit.ledger_id,
            transaction_type="REVERSAL",
            idempotency_key="rev-entry-001",
            actor_id="local_admin",
            actor_source="local_admin",
            reason_text="reverse once",
        )

        self.assertTrue(first.applied)
        self.assertTrue(repeat_same_key.idempotent)

        with self.assertRaises(InvalidAmountError):
            self.service.reverse_entry(
                owner_id=self.owner_id,
                original_ledger_id=credit.ledger_id,
                transaction_type="REVERSAL",
                idempotency_key="rev-entry-002",
                actor_id="local_admin",
                actor_source="local_admin",
                reason_text="duplicate reversal attempt",
            )

    def test_reverse_entry_metadata_contains_original_lineage(self) -> None:
        self.service.credit(
            discord_user_id=self.owner_id,
            amount=15,
            reference_type="TEST_CREDIT",
            reference_id="lineage-funding",
            reason_code="TEST",
            idempotency_key="lineage-funding",
        )
        debit = self.service.debit(
            discord_user_id=self.owner_id,
            amount=15,
            reference_type="AUTO_TRADER_ORDER_DEBIT",
            reference_id="order-989",
            reason_code="TEST",
            idempotency_key="lineage-src-debit",
        )
        refund = self.service.reverse_entry(
            owner_id=self.owner_id,
            original_ledger_id=debit.ledger_id,
            transaction_type="REFUND",
            idempotency_key="lineage-refund-001",
            actor_id="local_admin",
            actor_source="local_admin",
            reason_text="refund with lineage",
        )

        entry = self.service.get_ledger_entry(self.owner_id, refund.ledger_id)
        self.assertIsNotNone(entry)
        metadata = entry["metadata"]
        self.assertEqual(metadata["original_ledger_id"], debit.ledger_id)
        self.assertEqual(metadata["original_reference_type"], "AUTO_TRADER_ORDER_DEBIT")
        self.assertEqual(metadata["original_reference_id"], "order-989")

    def test_list_ledger_history_status_and_date_filters(self) -> None:
        first = self.service.credit(
            discord_user_id=self.owner_id,
            amount=40,
            reference_type="TEST_CREDIT",
            reference_id="status-a",
            reason_code="TEST",
            idempotency_key="status-a",
        )
        second = self.service.credit(
            discord_user_id=self.owner_id,
            amount=30,
            reference_type="TEST_CREDIT",
            reference_id="status-b",
            reason_code="TEST",
            idempotency_key="status-b",
        )
        self.service.reverse_entry(
            owner_id=self.owner_id,
            original_ledger_id=first.ledger_id,
            transaction_type="REVERSAL",
            idempotency_key="status-reversal",
            actor_id="local_admin",
            actor_source="local_admin",
            reason_text="correct status a",
        )

        corrected = self.service.list_ledger_history(self.owner_id, status="corrected", limit=50)
        corrections = self.service.list_ledger_history(self.owner_id, status="correction", limit=50)
        posted = self.service.list_ledger_history(self.owner_id, status="posted", limit=50)
        date_filtered = self.service.list_ledger_history(
            self.owner_id,
            created_after="2000-01-01T00:00:00Z",
            created_before="2100-01-01T00:00:00Z",
            limit=50,
        )

        self.assertTrue(any(row["id"] == first.ledger_id for row in corrected))
        self.assertTrue(all(row["entry_type"] in {"REVERSAL", "REFUND"} for row in corrections))
        self.assertTrue(any(row["id"] == second.ledger_id for row in posted))
        self.assertGreaterEqual(len(date_filtered), 3)

        with self.assertRaises(InvalidAmountError):
            self.service.list_ledger_history(self.owner_id, created_after="not-a-datetime", limit=10)


if __name__ == "__main__":
    unittest.main()
