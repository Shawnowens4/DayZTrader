"""Local-only moderation audit service for controlled recovery slices."""

from __future__ import annotations

import os
from typing import Any

from psycopg2.extras import Json


DEFAULT_DATABASE_URL = "postgresql://dxemb:dxemb@db:5432/dxemb"


class ModerationAuditService:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.database_url, connect_timeout=5)

    def record_warn(
        self,
        *,
        actor_discord_id: str,
        target_discord_id: str,
        reason: str,
        reference_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._record_action(
            action_type="WARN",
            actor_discord_id=actor_discord_id,
            target_discord_id=target_discord_id,
            reason=reason,
            reference_id=reference_id,
            metadata=metadata,
        )

    def record_status_query(
        self,
        *,
        actor_discord_id: str,
        target_discord_id: str,
        reference_id: str,
    ) -> dict[str, Any]:
        return self._record_action(
            action_type="STATUS_QUERY",
            actor_discord_id=actor_discord_id,
            target_discord_id=target_discord_id,
            reason=None,
            reference_id=reference_id,
            metadata=None,
        )

    def build_dry_run_preview(
        self,
        *,
        actor_discord_id: str,
        target_discord_id: str,
        action_type: str,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "applied": False,
            "dry_run": True,
            "action_type": action_type,
            "actor_discord_id": actor_discord_id,
            "target_discord_id": target_discord_id,
            "reason": reason,
            "note": "preview only; no Discord or guild mutation executed",
        }

    def get_target_status(self, target_discord_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT action_type, COUNT(*)
                    FROM moderation_action
                    WHERE target_discord_id = %s
                    GROUP BY action_type
                    """,
                    (target_discord_id,),
                )
                grouped = {row[0]: int(row[1]) for row in cur.fetchall()}

                cur.execute(
                    """
                    SELECT id, action_type, actor_discord_id, reason, created_at, reference_id
                    FROM moderation_action
                    WHERE target_discord_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (target_discord_id,),
                )
                latest = cur.fetchone()

        return {
            "target_discord_id": target_discord_id,
            "counts": grouped,
            "latest": (
                {
                    "id": int(latest[0]),
                    "action_type": latest[1],
                    "actor_discord_id": latest[2],
                    "reason": latest[3],
                    "created_at": latest[4],
                    "reference_id": latest[5],
                }
                if latest
                else None
            ),
        }

    def _record_action(
        self,
        *,
        action_type: str,
        actor_discord_id: str,
        target_discord_id: str,
        reason: str | None,
        reference_id: str,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, action_type, actor_discord_id, target_discord_id, reason
                    FROM moderation_action
                    WHERE action_type = %s AND reference_id = %s
                    """,
                    (action_type, reference_id),
                )
                existing = cur.fetchone()
                if existing:
                    return {
                        "id": int(existing[0]),
                        "action_type": existing[1],
                        "actor_discord_id": existing[2],
                        "target_discord_id": existing[3],
                        "reason": existing[4],
                        "applied": False,
                        "idempotent": True,
                    }

                cur.execute(
                    """
                    INSERT INTO moderation_action (
                        action_type,
                        actor_discord_id,
                        target_discord_id,
                        reason,
                        metadata,
                        reference_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        action_type,
                        actor_discord_id,
                        target_discord_id,
                        reason,
                        Json(metadata or {}),
                        reference_id,
                    ),
                )
                action_id = int(cur.fetchone()[0])

        return {
            "id": action_id,
            "action_type": action_type,
            "actor_discord_id": actor_discord_id,
            "target_discord_id": target_discord_id,
            "reason": reason,
            "applied": True,
            "idempotent": False,
        }
