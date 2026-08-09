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

from bot.cogs.autotrader_local import AutoTraderLocalAdapter
from shared.auto_trader_order_service import AutoTraderOrderService


class AutoTraderBotAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_auto_bot")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("006_auto_trader_order_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.service = AutoTraderOrderService(database_url=self.db_url)
        self.adapter = AutoTraderLocalAdapter(service=self.service)

        self.item_classname = f"AUTO_ITEM_{self._testMethodName}"
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

        self.product_id = self.service.create_product(
            product_code=f"AUTO-BOT-{self._testMethodName}",
            product_type="ITEM",
            item_classname=self.item_classname,
            display_name="Auto Item",
            price=250,
            created_by="admin",
            console_safe=True,
        )

    def test_browse_and_preview_read_only(self) -> None:
        products = self.adapter.browse_products(limit=10)
        preview = self.adapter.preview_order(product_id=self.product_id, quantity=2)

        self.assertEqual(products["mode"], "read-only")
        self.assertGreaterEqual(products["count"], 1)
        self.assertEqual(preview["mode"], "dry-run")
        self.assertTrue(preview["valid"])
        self.assertFalse(preview["applied"])

    def test_order_status_history_read_only(self) -> None:
        self.service.ensure_player("buyer-auto-history")
        created = self.service.create_order(
            order_reference=f"AUTO-HIST-{self._testMethodName}",
            buyer_discord_id="buyer-auto-history",
            product_id=self.product_id,
            quantity=1,
            created_by="admin",
        )
        self.service.transition_order(
            order_id=created.order_id,
            to_state="pending_payment",
            actor_discord_id="admin",
            reason_code="PENDING",
            reference_id=f"PENDING-{self._testMethodName}",
        )

        history = self.adapter.order_status_history(order_id=created.order_id)
        self.assertEqual(history["mode"], "read-only")
        self.assertEqual(history["domain"], "autotrader")
        self.assertGreaterEqual(history["event_count"], 2)

    def test_no_discord_mutation_api_usage_in_autotrader_local_source(self) -> None:
        source = (DXEMB_ROOT / "bot" / "cogs" / "autotrader_local.py").read_text(encoding="utf-8")
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

    def test_autotrader_adapter_not_using_p2p_tables_by_name(self) -> None:
        source = (DXEMB_ROOT / "bot" / "cogs" / "autotrader_local.py").read_text(encoding="utf-8")
        self.assertNotIn("market_escrow", source)
        self.assertNotIn("player_listing", source)


if __name__ == "__main__":
    unittest.main()
