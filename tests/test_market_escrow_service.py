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

from shared.market_escrow_service import EscrowStateError
from shared.market_escrow_service import MarketEscrowService
from shared.wallet_ledger_service import WalletLedgerService


class MarketEscrowServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_market")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("002_market_escrow_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.market = MarketEscrowService(database_url=self.db_url)
        self.wallet = WalletLedgerService(database_url=self.db_url)

        suffix = self._testMethodName
        self.seller_id = f"seller-{suffix}"
        self.buyer_id = f"buyer-{suffix}"

        self.market.ensure_player(self.seller_id, username="Seller")
        self.market.ensure_player(self.buyer_id, username="Buyer")

        self.wallet.credit(
            discord_user_id=self.buyer_id,
            amount=1000,
            reference_type="TEST_FUNDS",
            reference_id=f"funds-{suffix}",
            reason_code="TEST",
        )

        self._insert_item("M4A1")

    def _insert_item(self, classname: str) -> None:
        import psycopg2

        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO item (classname, display_name, category, subcategory, is_enabled)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (classname) DO NOTHING
                    """,
                    (classname, classname, "Weapons", "Rifles", True),
                )

    def test_listing_rejects_non_running_vehicle(self) -> None:
        with self.assertRaises(ValueError):
            self.market.create_listing(
                seller_discord_id=self.seller_id,
                listing_type="VEHICLE",
                item_classname=None,
                vehicle_label="Sarka 120",
                vehicle_running=False,
                quantity=1,
                price=400,
                created_by=self.seller_id,
            )

    def test_hold_then_release_after_pickup_confirmation(self) -> None:
        listing = self.market.create_listing(
            seller_discord_id=self.seller_id,
            listing_type="ITEM",
            item_classname="M4A1",
            vehicle_label=None,
            vehicle_running=True,
            quantity=1,
            price=250,
            created_by=self.seller_id,
        )

        escrow = self.market.hold_escrow(
            listing_id=listing["listing_id"],
            buyer_discord_id=self.buyer_id,
            actor_discord_id="staff-1",
        )

        self.market.confirm_pickup(
            escrow_id=escrow["escrow_id"],
            buyer_discord_id=self.buyer_id,
        )
        self.market.release_escrow(
            escrow_id=escrow["escrow_id"],
            actor_discord_id="staff-1",
        )

        self.assertEqual(self.market.get_escrow_status(escrow["escrow_id"]), "RELEASED")
        self.assertEqual(self.market.get_listing_status(listing["listing_id"]), "COMPLETED")
        self.assertEqual(self.wallet.get_balance(self.buyer_id), 750)
        self.assertEqual(self.wallet.get_balance(self.seller_id), 250)

    def test_release_requires_pickup_confirmation(self) -> None:
        listing = self.market.create_listing(
            seller_discord_id=self.seller_id,
            listing_type="ITEM",
            item_classname="M4A1",
            vehicle_label=None,
            vehicle_running=True,
            quantity=1,
            price=100,
            created_by=self.seller_id,
        )
        escrow = self.market.hold_escrow(
            listing_id=listing["listing_id"],
            buyer_discord_id=self.buyer_id,
            actor_discord_id="staff-1",
        )

        with self.assertRaises(EscrowStateError):
            self.market.release_escrow(
                escrow_id=escrow["escrow_id"],
                actor_discord_id="staff-1",
            )

    def test_dispute_then_refund_flow(self) -> None:
        listing = self.market.create_listing(
            seller_discord_id=self.seller_id,
            listing_type="ITEM",
            item_classname="M4A1",
            vehicle_label=None,
            vehicle_running=True,
            quantity=1,
            price=300,
            created_by=self.seller_id,
        )
        escrow = self.market.hold_escrow(
            listing_id=listing["listing_id"],
            buyer_discord_id=self.buyer_id,
            actor_discord_id="staff-1",
        )

        self.market.raise_dispute(
            escrow_id=escrow["escrow_id"],
            actor_discord_id="staff-1",
            reason="pickup mismatch",
        )
        self.market.refund_disputed(
            escrow_id=escrow["escrow_id"],
            actor_discord_id="staff-2",
            reason="approved refund",
        )

        self.assertEqual(self.market.get_escrow_status(escrow["escrow_id"]), "REFUNDED")
        self.assertEqual(self.market.get_listing_status(listing["listing_id"]), "CANCELLED")
        self.assertEqual(self.wallet.get_balance(self.buyer_id), 1000)
        self.assertEqual(self.wallet.get_balance(self.seller_id), 0)

    def test_listing_enforces_p2p_physical_delivery_mode(self) -> None:
        with self.assertRaises(ValueError):
            self.market.create_listing(
                seller_discord_id=self.seller_id,
                listing_type="ITEM",
                item_classname="M4A1",
                vehicle_label=None,
                vehicle_running=True,
                quantity=1,
                price=100,
                created_by=self.seller_id,
                delivery_mode="SERVER_SPAWN",
            )


if __name__ == "__main__":
    unittest.main()
