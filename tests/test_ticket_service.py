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

from shared.ticket_service import TicketService
from shared.ticket_service import TicketStateError


class TicketServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_ticket")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("004_ticket_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.service = TicketService(database_url=self.db_url)

    def test_open_assign_close_reopen_lifecycle(self) -> None:
        opened = self.service.open_ticket(
            external_ref=f"ticket-{self._testMethodName}",
            requester_discord_id="requester-1",
            subject="Need help",
            details="details",
            actor_discord_id="requester-1",
        )
        ticket_id = opened["ticket_id"]

        self.service.assign_ticket(
            ticket_id=ticket_id,
            assignee_discord_id="staff-1",
            actor_discord_id="staff-1",
            note="claimed",
        )
        self.service.close_ticket(ticket_id=ticket_id, actor_discord_id="staff-1", note="resolved")
        self.service.reopen_ticket(ticket_id=ticket_id, actor_discord_id="staff-2", note="follow-up")

        ticket = self.service.get_ticket(ticket_id)
        self.assertEqual(ticket["status"], "OPEN")
        self.assertEqual([e["event_type"] for e in ticket["events"]], ["OPENED", "ASSIGNED", "CLOSED", "REOPENED"])

    def test_cannot_assign_closed_ticket(self) -> None:
        opened = self.service.open_ticket(
            external_ref=f"ticket-{self._testMethodName}",
            requester_discord_id="requester-2",
            subject="Issue",
            details=None,
            actor_discord_id="requester-2",
        )
        self.service.close_ticket(ticket_id=opened["ticket_id"], actor_discord_id="staff-1")

        with self.assertRaises(TicketStateError):
            self.service.assign_ticket(
                ticket_id=opened["ticket_id"],
                assignee_discord_id="staff-2",
                actor_discord_id="staff-2",
            )

    def test_event_table_is_immutable(self) -> None:
        import psycopg2

        opened = self.service.open_ticket(
            external_ref=f"ticket-{self._testMethodName}",
            requester_discord_id="requester-3",
            subject="Immutable",
            details=None,
            actor_discord_id="requester-3",
        )
        ticket = self.service.get_ticket(opened["ticket_id"])

        with self.assertRaises(psycopg2.Error):
            with psycopg2.connect(self.db_url, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE support_ticket_event SET note = %s WHERE ticket_id = %s",
                        ("changed", ticket["id"]),
                    )


if __name__ == "__main__":
    unittest.main()
