from __future__ import annotations

import importlib
import os
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
)

ROOT = Path(__file__).resolve().parents[1]
DXEMB_ROOT = ROOT / "dxemb"
if str(DXEMB_ROOT) not in sys.path:
    sys.path.insert(0, str(DXEMB_ROOT))

from shared.wallet_ledger_service import WalletLedgerService


class WalletWebRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_wallet_web")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, DXEMB_ROOT / "db" / "migrations" / "001_wallet_ledger_foundation.sql")
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
        self.service = WalletLedgerService(database_url=self.db_url)
        self.user_id = f"wallet-web-{self._testMethodName}"
        self.service.ensure_player(self.user_id, username="WalletWebUser")

    def test_wallet_balance_route(self) -> None:
        self.service.credit(
            discord_user_id=self.user_id,
            amount=55,
            reference_type="TEST",
            reference_id=f"credit-{self._testMethodName}",
            reason_code="TEST",
        )
        resp = self.client.get(f"/wallet/{self.user_id}")
        data = resp.get_json()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["balance"], 55)
        self.assertEqual(data["mode"], "read-only")

    def test_wallet_ledger_route(self) -> None:
        self.service.credit(
            discord_user_id=self.user_id,
            amount=20,
            reference_type="TEST",
            reference_id=f"credit-{self._testMethodName}",
            reason_code="TEST",
        )
        resp = self.client.get(f"/wallet/{self.user_id}/ledger?limit=10")
        data = resp.get_json()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["rows"][0]["entry_type"], "CREDIT")

    def test_wallet_preview_route_non_mutating(self) -> None:
        self.service.credit(
            discord_user_id=self.user_id,
            amount=40,
            reference_type="TEST",
            reference_id=f"credit-{self._testMethodName}",
            reason_code="TEST",
        )
        before = self.service.get_balance(self.user_id)

        resp = self.client.post(
            f"/wallet/{self.user_id}/preview",
            json={"operation": "debit", "amount": 50},
        )
        data = resp.get_json()
        after = self.service.get_balance(self.user_id)

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(data["allowed"])
        self.assertFalse(data["applied"])
        self.assertEqual(before, after)

    def test_wallet_adjust_route_disabled(self) -> None:
        resp = self.client.post(f"/wallet/{self.user_id}/adjust", json={"amount": 10})
        data = resp.get_json()

        self.assertEqual(resp.status_code, 403)
        self.assertEqual(data["mode"], "disabled")


if __name__ == "__main__":
    unittest.main()
