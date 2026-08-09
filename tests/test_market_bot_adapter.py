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

from bot.cogs.market_local import MarketLocalAdapter
from shared.market_escrow_service import MarketEscrowService


class MarketBotAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_market_bot")
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
        self.service = MarketEscrowService(database_url=self.db_url)
        self.adapter = MarketLocalAdapter(service=self.service)
        self.seller = f"seller-{self._testMethodName}"
        self.buyer = f"buyer-{self._testMethodName}"
        self.item_classname = f"AmmoBox_{self._testMethodName}"
        self.service.ensure_player(self.seller, username="Seller")
        self.service.ensure_player(self.buyer, username="Buyer")
        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO item (classname, display_name, category, subcategory, buy_price, sell_price)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (classname) DO NOTHING
                    """,
                    (self.item_classname, "Ammo Box", "Test", "Fixtures", 1, 1),
                )
        self.service.wallet.credit(
            discord_user_id=self.buyer,
            amount=1000,
            reference_type="SEED",
            reference_id=f"seed-{self._testMethodName}",
            reason_code="SEED",
        )

    def test_preview_has_no_spawn_and_no_mutation(self) -> None:
        preview = self.adapter.preview_listing(
            listing_type="ITEM",
            item_classname=self.item_classname,
            vehicle_label=None,
            vehicle_running=True,
            quantity=1,
            price=150,
        )

        self.assertEqual(preview["delivery_mode"], "P2P_PHYSICAL")
        self.assertEqual(preview["spawn_behavior"], "not-supported")
        self.assertFalse(preview["applied"])

    def test_create_hold_and_status(self) -> None:
        listing = self.adapter.create_listing_local(
            seller_discord_id=self.seller,
            listing_type="ITEM",
            item_classname=self.item_classname,
            vehicle_label=None,
            vehicle_running=True,
            quantity=2,
            price=200,
            created_by="test",
            delivery_mode="P2P_PHYSICAL",
        )
        self.assertEqual(listing["status"], "ACTIVE")

        hold = self.adapter.hold_escrow_local(
            listing_id=listing["listing_id"],
            buyer_discord_id=self.buyer,
            actor_discord_id="test",
        )
        self.assertEqual(hold["status"], "HELD")

        listing_status = self.adapter.get_listing_status(listing["listing_id"])
        escrow_status = self.adapter.get_escrow_status(hold["escrow_id"])
        self.assertEqual(listing_status, "RESERVED")
        self.assertEqual(escrow_status, "HELD")

    def test_no_discord_mutation_api_usage_in_market_local_source(self) -> None:
        source = (DXEMB_ROOT / "bot" / "cogs" / "market_local.py").read_text(encoding="utf-8")
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
