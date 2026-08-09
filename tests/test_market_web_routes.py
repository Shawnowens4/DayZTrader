from __future__ import annotations

import importlib
import os
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

from shared.market_escrow_service import MarketEscrowService


class MarketWebRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_market_web")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("002_market_escrow_foundation.sql"))
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
        self.service = MarketEscrowService(database_url=self.db_url)
        self.seller = f"seller-web-{self._testMethodName}"
        self.buyer = f"buyer-web-{self._testMethodName}"
        self.item_classname = f"AmmoBoxWeb_{self._testMethodName}"

        self.service.ensure_player(self.seller, username="SellerWeb")
        self.service.ensure_player(self.buyer, username="BuyerWeb")
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

    def test_market_listings_and_detail_routes(self) -> None:
        listing = self.service.create_listing(
            seller_discord_id=self.seller,
            listing_type="ITEM",
            item_classname=self.item_classname,
            vehicle_label=None,
            vehicle_running=True,
            quantity=2,
            price=225,
            created_by="test",
            delivery_mode="P2P_PHYSICAL",
        )

        resp_list = self.client.get("/market/listings?status=ACTIVE")
        data_list = resp_list.get_json()
        self.assertEqual(resp_list.status_code, 200)
        self.assertGreaterEqual(data_list["count"], 1)
        self.assertEqual(data_list["mode"], "read-only")

        resp_detail = self.client.get(f"/market/listings/{listing['listing_id']}")
        data_detail = resp_detail.get_json()
        self.assertEqual(resp_detail.status_code, 200)
        self.assertEqual(data_detail["delivery_mode"], "P2P_PHYSICAL")

    def test_market_preview_route(self) -> None:
        resp = self.client.post(
            "/market/listings/preview",
            json={
                "listing_type": "VEHICLE",
                "vehicle_label": "Ada 4x4",
                "vehicle_running": False,
                "quantity": 1,
                "price": 900,
            },
        )
        data = resp.get_json()

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(data["valid"])
        self.assertEqual(data["delivery_mode"], "P2P_PHYSICAL")
        self.assertEqual(data["spawn_behavior"], "not-supported")
        self.assertFalse(data["applied"])

    def test_market_escrow_status_and_timeline(self) -> None:
        self.service.wallet.credit(
            discord_user_id=self.buyer,
            amount=1000,
            reference_type="SEED",
            reference_id=f"seed-{self._testMethodName}",
            reason_code="SEED",
        )

        listing = self.service.create_listing(
            seller_discord_id=self.seller,
            listing_type="ITEM",
            item_classname=self.item_classname,
            vehicle_label=None,
            vehicle_running=True,
            quantity=1,
            price=300,
            created_by="test",
            delivery_mode="P2P_PHYSICAL",
        )
        hold = self.service.hold_escrow(
            listing_id=listing["listing_id"],
            buyer_discord_id=self.buyer,
            actor_discord_id="test",
        )

        resp_status = self.client.get(f"/market/escrow/{hold['escrow_id']}")
        data_status = resp_status.get_json()
        self.assertEqual(resp_status.status_code, 200)
        self.assertEqual(data_status["status"], "HELD")

        resp_timeline = self.client.get(f"/market/escrow/{hold['escrow_id']}/timeline")
        data_timeline = resp_timeline.get_json()
        self.assertEqual(resp_timeline.status_code, 200)
        self.assertGreaterEqual(data_timeline["count"], 1)
        self.assertEqual(data_timeline["rows"][0]["event_type"], "HELD")

    def test_market_routes_do_not_reference_spawn_code(self) -> None:
        source = (DXEMB_ROOT / "web" / "app.py").read_text(encoding="utf-8")
        forbidden = [
            "spawn_item",
            "spawn_vehicle",
            "spawn_queue",
            "nitrado",
            "force_restart",
            "claim_code",
        ]
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
