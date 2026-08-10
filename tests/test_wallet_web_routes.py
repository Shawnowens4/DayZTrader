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
    migration_sql_path,
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
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("011_wallet_ledger_run5_additive_upgrade.sql"))
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
        self.owner_id = f"local:web-{self._testMethodName}"
        self.service.ensure_wallet_owner(self.owner_id, display_name="WalletWebUser", owner_kind="LOCAL_PLAYER")
        self.admin_headers = {"X-DXEMB-ROLE": "admin", "X-DXEMB-ACTOR-ID": "local_admin"}

    def test_player_wallet_page_requires_identity_and_renders_history(self) -> None:
        self.service.credit(
            discord_user_id=self.owner_id,
            amount=120,
            reference_type="AUTO_TRADER_ORDER_DEBIT",
            reference_id="order-1",
            reason_code="TEST",
            idempotency_key="wallet-player-credit-1",
            metadata={"order_id": 42},
        )
        missing = self.client.get("/wallet/me")
        mismatch = self.client.get(
            f"/wallet/me?discord_user_id={self.owner_id}",
            headers={"X-DXEMB-PLAYER-ID": "local:other"},
        )
        ok = self.client.get(
            f"/wallet/me?discord_user_id={self.owner_id}&direction=all&limit=25",
            headers={"X-DXEMB-PLAYER-ID": self.owner_id},
        )

        self.assertEqual(missing.status_code, 401)
        self.assertIn("player identity is required", missing.get_data(as_text=True))
        self.assertEqual(mismatch.status_code, 403)
        body = ok.get_data(as_text=True)
        self.assertEqual(ok.status_code, 200)
        self.assertIn("My Wallet", body)
        self.assertIn(self.owner_id, body)
        self.assertIn("Available balance", body)
        self.assertIn("AUTO_TRADER_ORDER_DEBIT", body)
        self.assertIn("wallet-player-credit-1", body)
        self.assertIn("Auto-Trader", body)
        self.assertIn("order #42", body)

    def test_player_wallet_filter_errors_and_status_filters(self) -> None:
        self.service.credit(
            discord_user_id=self.owner_id,
            amount=35,
            reference_type="TEST_CREDIT",
            reference_id="status-1",
            reason_code="TEST",
            idempotency_key="status-1",
        )
        bad = self.client.get(
            f"/wallet/me?discord_user_id={self.owner_id}&created_after=bad-date",
            headers={"X-DXEMB-PLAYER-ID": self.owner_id},
        )
        filtered = self.client.get(
            f"/wallet/me?discord_user_id={self.owner_id}&status=posted&direction=credit",
            headers={"X-DXEMB-PLAYER-ID": self.owner_id},
        )

        self.assertEqual(bad.status_code, 400)
        self.assertIn("created_after must be an ISO datetime", bad.get_data(as_text=True))
        self.assertEqual(filtered.status_code, 200)
        self.assertIn("posted", filtered.get_data(as_text=True))

    def test_player_wallet_limit_and_page_invalid_values_fallback(self) -> None:
        self.service.credit(
            discord_user_id=self.owner_id,
            amount=10,
            reference_type="TEST_CREDIT",
            reference_id="bad-pagination-fallback",
            reason_code="TEST",
            idempotency_key="bad-pagination-fallback",
        )
        response = self.client.get(
            f"/wallet/me?discord_user_id={self.owner_id}&limit=abc&page=xyz",
            headers={"X-DXEMB-PLAYER-ID": self.owner_id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Transaction History", response.get_data(as_text=True))

    def test_admin_adjust_requires_admin_role(self) -> None:
        blocked = self.client.post(
            f"/wallet/admin/{self.owner_id}/adjust",
            data={
                "entry_mode": "credit",
                "amount_minor": "50",
                "reason_text": "manual credit",
                "confirmation": "APPLY +50",
            },
        )

        self.assertEqual(blocked.status_code, 403)
        self.assertIn("admin role is required", blocked.get_data(as_text=True))

    def test_admin_list_requires_admin_role(self) -> None:
        blocked = self.client.get("/wallet/admin")
        self.assertEqual(blocked.status_code, 403)
        self.assertIn("admin role is required", blocked.get_data(as_text=True))

    def test_admin_detail_requires_admin_role(self) -> None:
        blocked = self.client.get(f"/wallet/admin/{self.owner_id}")
        self.assertEqual(blocked.status_code, 403)
        self.assertIn("admin role is required", blocked.get_data(as_text=True))

    def test_admin_route_rendering_and_bounded_history(self) -> None:
        for idx in range(30):
            self.service.credit(
                discord_user_id=self.owner_id,
                amount=idx + 1,
                reference_type="TEST_CREDIT",
                reference_id=f"credit-{idx}",
                reason_code="TEST",
                idempotency_key=f"web-credit-{idx}",
            )

        list_resp = self.client.get("/wallet/admin?as_role=admin")
        detail_resp = self.client.get(f"/wallet/admin/{self.owner_id}?as_role=admin&limit=25")
        detail_body = detail_resp.get_data(as_text=True)

        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(detail_resp.status_code, 200)
        self.assertIn("Wallet Admin Workspace", list_resp.get_data(as_text=True))
        self.assertIn("Virtual credits only", detail_body)
        self.assertIn("Next", detail_body)
        self.assertLessEqual(detail_body.count("<tr>"), 26)

    def test_admin_adjustment_workflow_and_invalid_confirmation(self) -> None:
        bad = self.client.post(
            f"/wallet/admin/{self.owner_id}/adjust",
            data={
                "entry_mode": "credit",
                "amount_minor": "50",
                "idempotency_key": "wallet-route-001",
                "actor_id": "local_admin",
                "reason_text": "manual credit",
                "metadata_json": '{"ticket":"route-1"}',
                "confirmation": "APPLY +49",
                "owner_kind": "LOCAL_PLAYER",
                "owner_label": "Wallet Web User",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(bad.status_code, 400)
        self.assertIn("confirmation phrase must exactly match APPLY +50", bad.get_data(as_text=True))

        ok = self.client.post(
            f"/wallet/admin/{self.owner_id}/adjust",
            data={
                "entry_mode": "credit",
                "amount_minor": "50",
                "idempotency_key": "wallet-route-001",
                "actor_id": "local_admin",
                "reason_text": "manual credit",
                "metadata_json": '{"ticket":"route-1"}',
                "confirmation": "APPLY +50",
                "owner_kind": "LOCAL_PLAYER",
                "owner_label": "Wallet Web User",
            },
            follow_redirects=True,
            headers=self.admin_headers,
        )
        body = ok.get_data(as_text=True)
        self.assertEqual(ok.status_code, 200)
        self.assertIn("Posted wallet entry CREDIT +50", body)
        self.assertEqual(self.service.get_balance(self.owner_id), 50)

        dup = self.client.post(
            f"/wallet/admin/{self.owner_id}/adjust",
            data={
                "entry_mode": "credit",
                "amount_minor": "50",
                "idempotency_key": "wallet-route-001",
                "actor_id": "local_admin",
                "reason_text": "manual credit",
                "metadata_json": '{"ticket":"route-1"}',
                "confirmation": "APPLY +50",
                "owner_kind": "LOCAL_PLAYER",
                "owner_label": "Wallet Web User",
            },
            follow_redirects=True,
            headers=self.admin_headers,
        )
        self.assertEqual(dup.status_code, 200)
        self.assertIn("reused existing idempotency key", dup.get_data(as_text=True))
        self.assertEqual(self.service.get_balance(self.owner_id), 50)

    def test_admin_adjust_redirect_preserves_filters(self) -> None:
        response = self.client.post(
            f"/wallet/admin/{self.owner_id}/adjust",
            data={
                "entry_mode": "credit",
                "amount_minor": "25",
                "idempotency_key": "wallet-route-filters-001",
                "actor_id": "local_admin",
                "reason_text": "credit with filter state",
                "metadata_json": '{"note":"contains ampersand & symbol"}',
                "confirmation": "APPLY +25",
                "owner_kind": "LOCAL_PLAYER",
                "owner_label": "Wallet Web User",
                "page": "2",
                "limit": "50",
                "direction": "credit",
                "status": "posted",
                "entry_type": "CREDIT",
                "reference_query": "order & refund",
                "created_after": "2000-01-01T00:00:00Z",
                "created_before": "2100-01-01T00:00:00Z",
                "as_role": "admin",
            },
            headers=self.admin_headers,
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        location = response.headers.get("Location", "")
        self.assertIn("page=2", location)
        self.assertIn("limit=50", location)
        self.assertIn("direction=credit", location)
        self.assertIn("status=posted", location)
        self.assertIn("entry_type=CREDIT", location)
        self.assertIn("reference_query=order+%26+refund", location)
        self.assertIn("created_after=2000-01-01T00%3A00%3A00Z", location)
        self.assertIn("created_before=2100-01-01T00%3A00%3A00Z", location)

    def test_admin_debit_insufficient_funds_rejected(self) -> None:
        response = self.client.post(
            f"/wallet/admin/{self.owner_id}/adjust",
            data={
                "entry_mode": "debit",
                "amount_minor": "20",
                "idempotency_key": "wallet-route-insufficient",
                "actor_id": "local_admin",
                "reason_text": "manual debit",
                "metadata_json": '{}',
                "confirmation": "APPLY -20",
                "owner_kind": "LOCAL_PLAYER",
                "owner_label": "Wallet Web User",
            },
            headers=self.admin_headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("insufficient funds", response.get_data(as_text=True))

    def test_reversal_and_refund_routes(self) -> None:
        credit = self.service.credit(
            discord_user_id=self.owner_id,
            amount=60,
            reference_type="TEST_CREDIT",
            reference_id="credit-route-reversal",
            reason_code="TEST",
            idempotency_key="credit-route-reversal",
        )
        self.service.credit(
            discord_user_id=self.owner_id,
            amount=25,
            reference_type="TEST_CREDIT",
            reference_id="credit-route-refund-base",
            reason_code="TEST",
            idempotency_key="credit-route-refund-base",
        )
        debit = self.service.debit(
            discord_user_id=self.owner_id,
            amount=20,
            reference_type="TEST_DEBIT",
            reference_id="debit-route-refund",
            reason_code="TEST",
            idempotency_key="debit-route-refund",
        )

        reversal = self.client.post(
            f"/wallet/admin/{self.owner_id}/adjust",
            data={
                "entry_mode": "reversal",
                "original_ledger_id": str(credit.ledger_id),
                "idempotency_key": "reversal-route-001",
                "actor_id": "local_admin",
                "reason_text": "reverse credit",
                "metadata_json": '{}',
                "confirmation": "APPLY -60",
                "owner_kind": "LOCAL_PLAYER",
                "owner_label": "Wallet Web User",
            },
            follow_redirects=True,
            headers=self.admin_headers,
        )
        refund = self.client.post(
            f"/wallet/admin/{self.owner_id}/adjust",
            data={
                "entry_mode": "refund",
                "original_ledger_id": str(debit.ledger_id),
                "idempotency_key": "refund-route-001",
                "actor_id": "local_admin",
                "reason_text": "refund debit",
                "metadata_json": '{}',
                "confirmation": "APPLY +20",
                "owner_kind": "LOCAL_PLAYER",
                "owner_label": "Wallet Web User",
            },
            follow_redirects=True,
            headers=self.admin_headers,
        )

        self.assertEqual(reversal.status_code, 200)
        self.assertEqual(refund.status_code, 200)
        self.assertIn("REVERSAL -60", reversal.get_data(as_text=True))
        self.assertIn("REFUND +20", refund.get_data(as_text=True))
        self.assertIn("original ledger", reversal.get_data(as_text=True))

    def test_duplicate_reversal_guardrail_feedback(self) -> None:
        credit = self.service.credit(
            discord_user_id=self.owner_id,
            amount=45,
            reference_type="TEST_CREDIT",
            reference_id="dup-rev-credit",
            reason_code="TEST",
            idempotency_key="dup-rev-credit",
        )

        first = self.client.post(
            f"/wallet/admin/{self.owner_id}/adjust",
            data={
                "entry_mode": "reversal",
                "original_ledger_id": str(credit.ledger_id),
                "idempotency_key": "dup-rev-001",
                "actor_id": "local_admin",
                "reason_text": "reverse once",
                "metadata_json": '{}',
                "confirmation": "APPLY -45",
                "owner_kind": "LOCAL_PLAYER",
                "owner_label": "Wallet Web User",
            },
            follow_redirects=True,
            headers=self.admin_headers,
        )
        duplicate = self.client.post(
            f"/wallet/admin/{self.owner_id}/adjust",
            data={
                "entry_mode": "reversal",
                "original_ledger_id": str(credit.ledger_id),
                "idempotency_key": "dup-rev-002",
                "actor_id": "local_admin",
                "reason_text": "reverse twice",
                "metadata_json": '{}',
                "confirmation": "APPLY -45",
                "owner_kind": "LOCAL_PLAYER",
                "owner_label": "Wallet Web User",
            },
            headers=self.admin_headers,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("already exists", duplicate.get_data(as_text=True))

    def test_admin_adjust_actor_header_mismatch_rejected(self) -> None:
        response = self.client.post(
            f"/wallet/admin/{self.owner_id}/adjust",
            data={
                "entry_mode": "credit",
                "amount_minor": "10",
                "idempotency_key": "wallet-route-actor-mismatch",
                "actor_id": "other_actor",
                "reason_text": "actor mismatch",
                "metadata_json": '{}',
                "confirmation": "APPLY +10",
                "owner_kind": "LOCAL_PLAYER",
                "owner_label": "Wallet Web User",
            },
            headers={"X-DXEMB-ROLE": "admin", "X-DXEMB-ACTOR-ID": "local_admin"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("must match X-DXEMB-ACTOR-ID", response.get_data(as_text=True))

    def test_wallet_preview_rejects_non_integer_amount(self) -> None:
        response = self.client.post(
            f"/wallet/{self.owner_id}/preview",
            json={"operation": "credit", "amount": "not-an-int"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("amount must be an integer", response.get_data(as_text=True))

    def test_existing_and_neighboring_routes_remain_intact(self) -> None:
        self.service.credit(
            discord_user_id=self.owner_id,
            amount=55,
            reference_type="TEST",
            reference_id=f"credit-{self._testMethodName}",
            reason_code="TEST",
            idempotency_key=f"wallet-{self._testMethodName}",
        )
        paths = [
            f"/wallet/{self.owner_id}",
            f"/wallet/{self.owner_id}/ledger?limit=10",
            f"/wallet/me?discord_user_id={self.owner_id}",
            "/catalog",
            "/catalog/admin",
            "/vehicles",
        ]
        for path in paths:
            response = self.client.get(path)
            self.assertLess(response.status_code, 500, msg=f"route {path} returned {response.status_code}")


if __name__ == "__main__":
    unittest.main()
