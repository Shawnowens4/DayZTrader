"""Profile/onboarding persistence and dry-run evaluator service."""

from __future__ import annotations

import os
from typing import Any

from psycopg2.extras import Json


DEFAULT_DATABASE_URL = "postgresql://dxemb:dxemb@db:5432/dxemb"

ALLOWED_TRANSITIONS = {
    "PENDING": {"STARTED"},
    "STARTED": {"PROFILE_CAPTURED"},
    "PROFILE_CAPTURED": {"READY_FOR_REVIEW"},
    "READY_FOR_REVIEW": {"COMPLETED"},
    "COMPLETED": set(),
}


class OnboardingStateError(Exception):
    """Raised for invalid onboarding state transition requests."""


class ProfileOnboardingService:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.database_url, connect_timeout=5)

    def upsert_profile(
        self,
        *,
        discord_user_id: str,
        display_name: str | None,
        timezone: str | None,
        preferred_platform: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO player_profile (
                        discord_user_id,
                        display_name,
                        timezone,
                        preferred_platform,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (discord_user_id)
                    DO UPDATE SET
                        display_name = COALESCE(EXCLUDED.display_name, player_profile.display_name),
                        timezone = COALESCE(EXCLUDED.timezone, player_profile.timezone),
                        preferred_platform = COALESCE(EXCLUDED.preferred_platform, player_profile.preferred_platform),
                        metadata = player_profile.metadata || EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id, display_name, timezone, preferred_platform, metadata
                    """,
                    (
                        discord_user_id,
                        display_name,
                        timezone,
                        preferred_platform,
                        Json(metadata or {}),
                    ),
                )
                row = cur.fetchone()

        return {
            "id": int(row[0]),
            "discord_user_id": discord_user_id,
            "display_name": row[1],
            "timezone": row[2],
            "preferred_platform": row[3],
            "metadata": row[4],
        }

    def transition_onboarding_state(
        self,
        *,
        discord_user_id: str,
        to_state: str,
        actor_discord_id: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO onboarding_session (discord_user_id)
                    VALUES (%s)
                    ON CONFLICT (discord_user_id) DO NOTHING
                    """,
                    (discord_user_id,),
                )

                cur.execute(
                    """
                    SELECT id, state
                    FROM onboarding_session
                    WHERE discord_user_id = %s
                    FOR UPDATE
                    """,
                    (discord_user_id,),
                )
                row = cur.fetchone()
                onboarding_id = int(row[0])
                from_state = row[1]

                if to_state == from_state:
                    return {
                        "onboarding_id": onboarding_id,
                        "from_state": from_state,
                        "to_state": to_state,
                        "applied": False,
                        "idempotent": True,
                    }

                allowed = ALLOWED_TRANSITIONS.get(from_state, set())
                if to_state not in allowed:
                    raise OnboardingStateError(f"invalid transition: {from_state} -> {to_state}")

                cur.execute(
                    """
                    UPDATE onboarding_session
                    SET state = %s,
                        note = %s,
                        updated_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (to_state, note, actor_discord_id, onboarding_id),
                )
                cur.execute(
                    """
                    INSERT INTO onboarding_event (onboarding_id, from_state, to_state, actor_discord_id, note)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (onboarding_id, from_state, to_state, actor_discord_id, note),
                )

        return {
            "onboarding_id": onboarding_id,
            "from_state": from_state,
            "to_state": to_state,
            "applied": True,
            "idempotent": False,
        }

    def evaluate_onboarding_dry_run(self, *, discord_user_id: str, state: str) -> dict[str, Any]:
        actions: list[str] = []
        if state == "PENDING":
            actions = ["show_intro_prompt", "request_profile_fields"]
        elif state == "STARTED":
            actions = ["validate_profile_payload", "request_missing_fields"]
        elif state == "PROFILE_CAPTURED":
            actions = ["build_review_summary", "queue_manual_review"]
        elif state == "READY_FOR_REVIEW":
            actions = ["await_staff_review", "hold_role_channel_actions"]
        elif state == "COMPLETED":
            actions = ["noop_completed"]
        else:
            actions = ["unknown_state_noop"]

        return {
            "discord_user_id": discord_user_id,
            "state": state,
            "dry_run": True,
            "actions": actions,
            "note": "evaluator output only; no Discord actions executed",
        }

    def get_onboarding_state(self, discord_user_id: str) -> str | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT state FROM onboarding_session WHERE discord_user_id = %s",
                    (discord_user_id,),
                )
                row = cur.fetchone()
                return row[0] if row else None
