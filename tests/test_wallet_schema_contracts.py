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


class WalletSchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        import psycopg2

        cls._psycopg2 = psycopg2
        cls.db_name = disposable_database_name(prefix="dxemb_wallet_contract")
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

    def _connect(self):
        return self._psycopg2.connect(self.db_url, connect_timeout=5)

    def test_wallet_tables_and_required_columns_exist(self) -> None:
        expected_account = {"discord_user_id", "owner_kind", "owner_label", "balance", "created_at", "updated_at"}
        expected_ledger = {
            "discord_user_id",
            "entry_type",
            "amount",
            "signed_amount",
            "balance_before",
            "balance_after",
            "reference_type",
            "reference_id",
            "idempotency_key",
            "reason_code",
            "reason_text",
            "actor_discord_id",
            "actor_source",
            "metadata",
            "created_at",
        }
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'wallet_account'")
                account_cols = {row[0] for row in cur.fetchall()}
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'wallet_ledger'")
                ledger_cols = {row[0] for row in cur.fetchall()}

        self.assertTrue(expected_account.issubset(account_cols))
        self.assertTrue(expected_ledger.issubset(ledger_cols))

    def test_wallet_constraints_exist(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT conname, pg_get_constraintdef(c.oid)
                    FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    JOIN pg_namespace n ON t.relnamespace = n.oid
                    WHERE n.nspname = 'public'
                      AND t.relname IN ('wallet_account', 'wallet_ledger')
                    """
                )
                constraints = {row[0]: row[1] for row in cur.fetchall()}

        self.assertIn("uq_wallet_ledger_idempotency", constraints)
        self.assertTrue(any("signed_amount <> 0" in value for value in constraints.values()))
        self.assertTrue(any("balance >= 0" in value for value in constraints.values()))


if __name__ == "__main__":
    unittest.main()