from __future__ import annotations

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

from shared.auto_trader_order_service import AutoTraderOrderService
from shared.auto_trader_wallet_bridge import AutoTraderWalletBridge
from shared.wallet_ledger_service import WalletLedgerService


class AutoTraderWalletBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_auto_bridge")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("011_wallet_ledger_run5_additive_upgrade.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("002_market_escrow_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("006_auto_trader_order_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.order_service = AutoTraderOrderService(database_url=self.db_url)
        self.bridge = AutoTraderWalletBridge(database_url=self.db_url)
        self.wallet = WalletLedgerService(database_url=self.db_url)

        self.buyer_id = f"bridge-buyer-{self._testMethodName}"
        self.order_service.ensure_player(self.buyer_id, username="BridgeBuyer")

        self.item_classname = f"AKM_{self._testMethodName}"
        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO item (classname, display_name, category, subcategory, is_enabled)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (classname) DO NOTHING
                    """,
                    (self.item_classname, self.item_classname, "Weapons", "Rifles", True),
                )

        self.product_id = self.order_service.create_product(
            product_code=f"BRIDGE-PRD-{self._testMethodName}",
            product_type="ITEM",
            item_classname=self.item_classname,
            display_name="AKM",
            price=250,
            created_by="admin",
            is_enabled=True,
            is_sellable=True,
            console_safe=True,
        )

        self.wallet.credit(
            discord_user_id=self.buyer_id,
            amount=1000,
            reference_type="TEST_FUNDS",
            reference_id=f"funds-{self._testMethodName}",
            reason_code="TEST",
        )

    def test_atomic_create_paid_order_and_debit_idempotent(self) -> None:
        order_reference = f"BRIDGE-ORDER-{self._testMethodName}"
        debit_reference = f"BRIDGE-DEBIT-{self._testMethodName}"

        first = self.bridge.create_paid_order_with_wallet_debit(
            order_reference=order_reference,
            debit_reference_id=debit_reference,
            buyer_discord_id=self.buyer_id,
            product_id=self.product_id,
            quantity=2,
            actor_discord_id="admin",
        )
        second = self.bridge.create_paid_order_with_wallet_debit(
            order_reference=order_reference,
            debit_reference_id=debit_reference,
            buyer_discord_id=self.buyer_id,
            product_id=self.product_id,
            quantity=2,
            actor_discord_id="admin",
        )

        self.assertTrue(first.debited)
        self.assertFalse(second.debited)
        self.assertTrue(second.idempotent)
        self.assertEqual(first.order_id, second.order_id)
        self.assertEqual(self.wallet.get_balance(self.buyer_id), 500)

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM wallet_ledger
                    WHERE discord_user_id = %s
                      AND reference_type = 'AUTO_TRADER_ORDER_DEBIT'
                      AND reference_id = %s
                    """,
                    (self.buyer_id, debit_reference),
                )
                debit_rows = int(cur.fetchone()[0])
        self.assertEqual(debit_rows, 1)

    def test_refund_after_failed_or_cancelled_order(self) -> None:
        order_reference = f"BRIDGE-ORDER-RF-{self._testMethodName}"
        debit_reference = f"BRIDGE-DEBIT-RF-{self._testMethodName}"
        created = self.bridge.create_paid_order_with_wallet_debit(
            order_reference=order_reference,
            debit_reference_id=debit_reference,
            buyer_discord_id=self.buyer_id,
            product_id=self.product_id,
            quantity=1,
            actor_discord_id="admin",
        )
        self.order_service.transition_order(
            order_id=created.order_id,
            to_state="failed",
            actor_discord_id="admin",
            reason_code="DELIVERY_FAIL",
            reference_id=f"FAIL-{self._testMethodName}",
        )

        first_refund = self.bridge.refund_order(
            order_id=created.order_id,
            refund_reference_id=f"REFUND-{self._testMethodName}",
            actor_discord_id="admin",
            reason_text="delivery failed",
        )
        second_refund = self.bridge.refund_order(
            order_id=created.order_id,
            refund_reference_id=f"REFUND-{self._testMethodName}",
            actor_discord_id="admin",
            reason_text="delivery failed",
        )

        self.assertTrue(first_refund["refunded"])
        self.assertFalse(second_refund["refunded"])
        self.assertTrue(second_refund["idempotent"])
        self.assertEqual(self.wallet.get_balance(self.buyer_id), 1000)

    def test_bridge_keeps_p2p_tables_untouched(self) -> None:
        self.bridge.create_paid_order_with_wallet_debit(
            order_reference=f"BRIDGE-SEP-{self._testMethodName}",
            debit_reference_id=f"BRIDGE-SEP-DEBIT-{self._testMethodName}",
            buyer_discord_id=self.buyer_id,
            product_id=self.product_id,
            quantity=1,
            actor_discord_id="admin",
        )

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM market_escrow")
                escrow_count = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM player_listing")
                listing_count = int(cur.fetchone()[0])

        self.assertEqual(escrow_count, 0)
        self.assertEqual(listing_count, 0)


if __name__ == "__main__":
    unittest.main()
