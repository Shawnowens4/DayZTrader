"""Local-only ticket lifecycle service for controlled recovery slices."""

from __future__ import annotations

import os
from typing import Any


DEFAULT_DATABASE_URL = "postgresql://dxemb:dxemb@db:5432/dxemb"


class TicketStateError(Exception):
    """Raised when an invalid ticket transition is requested."""


class TicketService:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.database_url, connect_timeout=5)

    def open_ticket(
        self,
        *,
        external_ref: str,
        requester_discord_id: str,
        subject: str,
        details: str | None,
        actor_discord_id: str,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO support_ticket (
                        external_ref,
                        requester_discord_id,
                        subject,
                        details,
                        status
                    )
                    VALUES (%s, %s, %s, %s, 'OPEN')
                    ON CONFLICT (external_ref)
                    DO UPDATE SET
                        subject = COALESCE(EXCLUDED.subject, support_ticket.subject),
                        details = COALESCE(EXCLUDED.details, support_ticket.details)
                    RETURNING id, status
                    """,
                    (external_ref, requester_discord_id, subject, details),
                )
                row = cur.fetchone()
                ticket_id = int(row[0])

                cur.execute(
                    """
                    INSERT INTO support_ticket_event (ticket_id, event_type, actor_discord_id, note)
                    VALUES (%s, 'OPENED', %s, %s)
                    """,
                    (ticket_id, actor_discord_id, details),
                )

        return {"ticket_id": ticket_id, "status": row[1]}

    def assign_ticket(self, *, ticket_id: int, assignee_discord_id: str, actor_discord_id: str, note: str | None = None) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status
                    FROM support_ticket
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (ticket_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise TicketStateError("ticket not found")
                if row[0] == "CLOSED":
                    raise TicketStateError("cannot assign closed ticket")

                cur.execute(
                    """
                    UPDATE support_ticket
                    SET assignee_discord_id = %s,
                        status = 'ASSIGNED',
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (assignee_discord_id, ticket_id),
                )
                cur.execute(
                    """
                    INSERT INTO support_ticket_event (ticket_id, event_type, actor_discord_id, note)
                    VALUES (%s, 'ASSIGNED', %s, %s)
                    """,
                    (ticket_id, actor_discord_id, note),
                )

    def close_ticket(self, *, ticket_id: int, actor_discord_id: str, note: str | None = None) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status
                    FROM support_ticket
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (ticket_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise TicketStateError("ticket not found")
                if row[0] == "CLOSED":
                    raise TicketStateError("ticket already closed")

                cur.execute(
                    """
                    UPDATE support_ticket
                    SET status = 'CLOSED',
                        closed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (ticket_id,),
                )
                cur.execute(
                    """
                    INSERT INTO support_ticket_event (ticket_id, event_type, actor_discord_id, note)
                    VALUES (%s, 'CLOSED', %s, %s)
                    """,
                    (ticket_id, actor_discord_id, note),
                )

    def reopen_ticket(self, *, ticket_id: int, actor_discord_id: str, note: str | None = None) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status
                    FROM support_ticket
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (ticket_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise TicketStateError("ticket not found")
                if row[0] != "CLOSED":
                    raise TicketStateError("only closed tickets can be reopened")

                cur.execute(
                    """
                    UPDATE support_ticket
                    SET status = 'OPEN',
                        closed_at = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (ticket_id,),
                )
                cur.execute(
                    """
                    INSERT INTO support_ticket_event (ticket_id, event_type, actor_discord_id, note)
                    VALUES (%s, 'REOPENED', %s, %s)
                    """,
                    (ticket_id, actor_discord_id, note),
                )

    def get_ticket(self, ticket_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        external_ref,
                        requester_discord_id,
                        assignee_discord_id,
                        subject,
                        details,
                        status,
                        opened_at,
                        closed_at
                    FROM support_ticket
                    WHERE id = %s
                    """,
                    (ticket_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise TicketStateError("ticket not found")

                cur.execute(
                    """
                    SELECT event_type, actor_discord_id, note
                    FROM support_ticket_event
                    WHERE ticket_id = %s
                    ORDER BY id ASC
                    """,
                    (ticket_id,),
                )
                events = [
                    {"event_type": r[0], "actor_discord_id": r[1], "note": r[2]}
                    for r in cur.fetchall()
                ]

        return {
            "id": int(row[0]),
            "external_ref": row[1],
            "requester_discord_id": row[2],
            "assignee_discord_id": row[3],
            "subject": row[4],
            "details": row[5],
            "status": row[6],
            "opened_at": row[7],
            "closed_at": row[8],
            "events": events,
        }
