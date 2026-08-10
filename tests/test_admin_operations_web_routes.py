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

from shared.auto_trader_order_service import AutoTraderOrderService
from shared.moderation_audit_service import ModerationAuditService
from shared.nitrado_delivery_scheduler_service import NitradoDeliverySchedulerService
from shared.ticket_service import TicketService


class AdminOperationsWebRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_ops_web")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("001_wallet_ledger_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("011_wallet_ledger_run5_additive_upgrade.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("003_moderation_audit_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("004_ticket_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("006_auto_trader_order_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("007_nitrado_delivery_scheduler_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("008_game_economy_foundation.sql"))
            apply_sql_file(cls.db_url, migration_sql_path("010_mission_bounty_foundation.sql"))
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
        self.mod_service = ModerationAuditService(database_url=self.db_url)
        self.ticket_service = TicketService(database_url=self.db_url)
        self.order_service = AutoTraderOrderService(database_url=self.db_url)
        self.scheduler_service = NitradoDeliverySchedulerService(database_url=self.db_url)

        target_id = f"ops-target-{self._testMethodName}"
        self.mod_service.record_warn(
            actor_discord_id="ops-admin",
            target_discord_id=target_id,
            reason="ops warning",
            reference_id=f"ops-warn-{self._testMethodName}",
        )
        self.mod_service.record_status_query(
            actor_discord_id="ops-admin",
            target_discord_id=target_id,
            reference_id=f"ops-status-{self._testMethodName}",
        )

        opened = self.ticket_service.open_ticket(
            external_ref=f"OPS-TKT-{self._testMethodName}",
            requester_discord_id=target_id,
            subject="Ops ticket",
            details="ticket from test",
            actor_discord_id="ops-admin",
        )
        self.ticket_service.assign_ticket(
            ticket_id=opened["ticket_id"],
            assignee_discord_id="ops-assignee",
            actor_discord_id="ops-admin",
            note="assigned",
        )

        self.order_service.ensure_player("ops-buyer", username="OpsBuyer")
        item_classname = f"OPS_ITEM_{self._testMethodName}"
        with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO item (classname, display_name, category, subcategory, is_enabled)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (classname) DO NOTHING
                    """,
                    (item_classname, item_classname, "Weapons", "Rifles", True),
                )

        product_id = self.order_service.create_product(
            product_code=f"OPS-PRD-{self._testMethodName}",
            product_type="ITEM",
            item_classname=item_classname,
            display_name="Ops Product",
            price=250,
            created_by="ops-admin",
            console_safe=True,
        )
        order = self.order_service.create_order(
            order_reference=f"OPS-ORDER-{self._testMethodName}",
            buyer_discord_id="ops-buyer",
            product_id=product_id,
            quantity=1,
            created_by="ops-admin",
            initial_state="paid",
        )
        self.scheduler_service.enqueue_delivery_request(order_id=order.order_id, actor_id="ops-admin")

    def test_workspace_requires_admin_role(self) -> None:
        response = self.client.get("/admin/operations")
        self.assertEqual(response.status_code, 403)
        self.assertIn("admin role is required", response.get_data(as_text=True))

    def test_workspace_renders_cross_system_evidence(self) -> None:
        response = self.client.get("/admin/operations?as_role=admin&limit=10")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Admin Operations Workspace", body)
        self.assertIn("Server Configuration Snapshot", body)
        self.assertIn("Moderation Evidence", body)
        self.assertIn("Ticket Evidence", body)
        self.assertIn("Scheduler Evidence", body)
        self.assertIn("queued_for_delivery", body)
        self.assertIn("STATUS_QUERY", body)
        self.assertIn("ASSIGNED", body)
        self.assertIn("COIN_FLIP", body)

    def test_workspace_filters_are_applied(self) -> None:
        target_id = f"ops-target-{self._testMethodName}"
        response = self.client.get(
            "/admin/operations"
            f"?as_role=admin&limit=10&target_discord_id={target_id}"
            "&moderation_action=WARN&ticket_status=ASSIGNED&delivery_state=queued_for_delivery"
        )
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(target_id, body)
        self.assertIn("WARN", body)
        self.assertIn("ASSIGNED", body)
        self.assertIn("queued_for_delivery", body)


if __name__ == "__main__":
    unittest.main()
