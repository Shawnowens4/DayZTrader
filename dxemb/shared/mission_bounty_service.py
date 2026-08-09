"""Mission/Bounty local foundation service (feature-flagged)."""

from __future__ import annotations

import os
from datetime import datetime
from datetime import timezone
from typing import Any

from psycopg2.extras import Json

from shared.wallet_ledger_service import WalletLedgerService


DEFAULT_DATABASE_URL = "postgresql://dxemb:dxemb@db:5432/dxemb"


class MissionBountyError(Exception):
    """Base mission/bounty service error."""


class PermissionError(MissionBountyError):
    """Raised when caller lacks admin authority."""


class MissionStateError(MissionBountyError):
    """Raised on invalid mission state transitions or claim state."""


class FeatureDisabledError(MissionBountyError):
    """Raised when mission feature flags disallow an operation."""


class MissionBountyService:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.wallet = WalletLedgerService(database_url=self.database_url)

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.database_url, connect_timeout=5)

    @staticmethod
    def _require_admin(actor_id: str) -> None:
        if not actor_id.startswith("admin:"):
            raise PermissionError("admin actor required")

    def set_feature_flag(self, *, is_enabled: bool, allow_reward_settlement: bool) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE mission_feature_flag
                    SET is_enabled = %s,
                        allow_reward_settlement = %s,
                        updated_at = NOW()
                    WHERE feature_code = 'MISSION_BOUNTY'
                    """,
                    (bool(is_enabled), bool(allow_reward_settlement)),
                )

    def _get_flag(self, cur) -> dict[str, Any]:
        cur.execute(
            """
            SELECT is_enabled, allow_reward_settlement
            FROM mission_feature_flag
            WHERE feature_code = 'MISSION_BOUNTY'
            """,
        )
        row = cur.fetchone()
        if not row:
            raise FeatureDisabledError("MISSION_BOUNTY feature flag row not found")
        return {
            "is_enabled": bool(row[0]),
            "allow_reward_settlement": bool(row[1]),
        }

    def create_mission(
        self,
        *,
        mission_code: str,
        title: str,
        description: str,
        target_count: int,
        reward_amount: int,
        starts_at: datetime | None,
        expires_at: datetime | None,
        actor_id: str,
    ) -> int:
        self._require_admin(actor_id)
        if target_count <= 0:
            raise MissionStateError("target_count must be > 0")
        if reward_amount < 0:
            raise MissionStateError("reward_amount must be >= 0")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mission_bounty (
                        mission_code,
                        title,
                        description,
                        target_count,
                        reward_amount,
                        starts_at,
                        expires_at,
                        state,
                        moderation_state,
                        created_by,
                        updated_by,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'DRAFT', 'APPROVED', %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        mission_code,
                        title,
                        description,
                        target_count,
                        reward_amount,
                        starts_at,
                        expires_at,
                        actor_id,
                        actor_id,
                        Json({"scope": "local-only"}),
                    ),
                )
                return int(cur.fetchone()[0])

    def activate_mission(self, *, mission_id: int, actor_id: str) -> None:
        self._require_admin(actor_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE mission_bounty
                    SET state = 'ACTIVE',
                        updated_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                      AND state = 'DRAFT'
                    """,
                    (actor_id, mission_id),
                )
                if cur.rowcount == 0:
                    raise MissionStateError("mission must be DRAFT to activate")

    def cancel_mission(self, *, mission_id: int, actor_id: str, reason: str) -> None:
        self._require_admin(actor_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE mission_bounty
                    SET state = 'CANCELLED',
                        cancel_reason = %s,
                        updated_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                      AND state IN ('DRAFT', 'ACTIVE')
                    """,
                    (reason, actor_id, mission_id),
                )
                if cur.rowcount == 0:
                    raise MissionStateError("mission cannot be cancelled from current state")

    def record_progress(
        self,
        *,
        mission_id: int,
        discord_user_id: str,
        increment: int,
        now: datetime,
        actor_id: str,
    ) -> dict[str, Any]:
        if increment <= 0:
            raise MissionStateError("increment must be > 0")
        self.wallet.ensure_player(discord_user_id)

        with self._connect() as conn:
            with conn.cursor() as cur:
                flag = self._get_flag(cur)
                if not flag["is_enabled"]:
                    raise FeatureDisabledError("mission feature is disabled")

                cur.execute(
                    """
                    SELECT target_count, state, expires_at
                    FROM mission_bounty
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (mission_id,),
                )
                mission = cur.fetchone()
                if not mission:
                    raise MissionStateError("mission not found")

                target_count = int(mission[0])
                state = mission[1]
                expires_at = mission[2]
                if state != "ACTIVE":
                    raise MissionStateError("mission must be ACTIVE for progress")
                if expires_at is not None and now.astimezone(timezone.utc) > expires_at.astimezone(timezone.utc):
                    raise MissionStateError("mission expired")

                cur.execute(
                    """
                    SELECT id, progress_count, status
                    FROM mission_bounty_progress
                    WHERE mission_id = %s
                      AND discord_user_id = %s
                    FOR UPDATE
                    """,
                    (mission_id, discord_user_id),
                )
                row = cur.fetchone()

                if row:
                    progress_id = int(row[0])
                    progress_count = int(row[1]) + increment
                    old_status = row[2]
                else:
                    progress_id = None
                    progress_count = increment
                    old_status = "ENROLLED"

                new_status = "ELIGIBLE" if progress_count >= target_count else "ENROLLED"
                eligible_at = now if new_status == "ELIGIBLE" else None

                if progress_id is None:
                    cur.execute(
                        """
                        INSERT INTO mission_bounty_progress (
                            mission_id,
                            discord_user_id,
                            progress_count,
                            status,
                            eligible_at,
                            metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            mission_id,
                            discord_user_id,
                            progress_count,
                            new_status,
                            eligible_at,
                            Json({"actor_id": actor_id}),
                        ),
                    )
                    progress_id = int(cur.fetchone()[0])
                else:
                    cur.execute(
                        """
                        UPDATE mission_bounty_progress
                        SET progress_count = %s,
                            status = %s,
                            eligible_at = COALESCE(eligible_at, %s),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (progress_count, new_status, eligible_at, progress_id),
                    )

                return {
                    "progress_id": progress_id,
                    "mission_id": mission_id,
                    "discord_user_id": discord_user_id,
                    "progress_count": progress_count,
                    "status": new_status,
                    "previous_status": old_status,
                }

    def claim_reward(
        self,
        *,
        mission_id: int,
        discord_user_id: str,
        now: datetime,
        actor_id: str,
        apply_reward: bool = False,
    ) -> dict[str, Any]:
        self.wallet.ensure_player(discord_user_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                flag = self._get_flag(cur)
                if not flag["is_enabled"]:
                    raise FeatureDisabledError("mission feature is disabled")

                cur.execute(
                    """
                    SELECT reward_amount, state, expires_at
                    FROM mission_bounty
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (mission_id,),
                )
                mission = cur.fetchone()
                if not mission:
                    raise MissionStateError("mission not found")

                reward_amount = int(mission[0])
                state = mission[1]
                expires_at = mission[2]
                if state != "ACTIVE":
                    raise MissionStateError("mission must be ACTIVE for claims")
                if expires_at is not None and now.astimezone(timezone.utc) > expires_at.astimezone(timezone.utc):
                    raise MissionStateError("mission expired")

                cur.execute(
                    """
                    SELECT id, status, claim_reference_id, reward_granted
                    FROM mission_bounty_progress
                    WHERE mission_id = %s
                      AND discord_user_id = %s
                    FOR UPDATE
                    """,
                    (mission_id, discord_user_id),
                )
                progress = cur.fetchone()
                if not progress:
                    raise MissionStateError("progress not found")

                progress_id = int(progress[0])
                status = progress[1]
                if status == "CLAIMED":
                    return {
                        "mission_id": mission_id,
                        "discord_user_id": discord_user_id,
                        "status": "CLAIMED",
                        "idempotent": True,
                    }
                if status != "ELIGIBLE":
                    raise MissionStateError("progress is not eligible for claim")

                claim_reference_id = f"MISSION_REWARD:{mission_id}:{discord_user_id}"
                reward_ledger_id = None
                reward_granted = False
                if apply_reward and reward_amount > 0:
                    if not flag["allow_reward_settlement"]:
                        raise FeatureDisabledError("reward settlement is disabled")
                    reward = self.wallet.credit(
                        discord_user_id=discord_user_id,
                        amount=reward_amount,
                        reference_type="MISSION_REWARD",
                        reference_id=claim_reference_id,
                        reason_code="MISSION_CLAIM_REWARD",
                        actor_discord_id=actor_id,
                        metadata={"mission_id": mission_id},
                    )
                    reward_ledger_id = reward.ledger_id
                    reward_granted = True

                cur.execute(
                    """
                    UPDATE mission_bounty_progress
                    SET status = 'CLAIMED',
                        claimed_at = %s,
                        claim_reference_id = %s,
                        reward_granted = %s,
                        reward_ledger_id = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (now, claim_reference_id, reward_granted, reward_ledger_id, progress_id),
                )

                return {
                    "mission_id": mission_id,
                    "discord_user_id": discord_user_id,
                    "status": "CLAIMED",
                    "reward_granted": reward_granted,
                    "reward_ledger_id": reward_ledger_id,
                    "idempotent": False,
                }

    def list_missions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 200))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, mission_code, title, target_count, reward_amount,
                           state, moderation_state, starts_at, expires_at, created_at
                    FROM mission_bounty
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (safe_limit,),
                )
                rows = cur.fetchall()

        out = []
        for row in rows:
            out.append(
                {
                    "id": int(row[0]),
                    "mission_code": row[1],
                    "title": row[2],
                    "target_count": int(row[3]),
                    "reward_amount": int(row[4]),
                    "state": row[5],
                    "moderation_state": row[6],
                    "starts_at": row[7],
                    "expires_at": row[8],
                    "created_at": row[9],
                }
            )
        return out

    def list_progress(self, *, discord_user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT mb.id, mb.mission_code, mb.title,
                           p.progress_count, mb.target_count, p.status,
                           p.reward_granted, p.claimed_at, p.updated_at
                    FROM mission_bounty_progress p
                    JOIN mission_bounty mb ON mb.id = p.mission_id
                    WHERE p.discord_user_id = %s
                    ORDER BY p.updated_at DESC, p.id DESC
                    LIMIT %s
                    """,
                    (discord_user_id, safe_limit),
                )
                rows = cur.fetchall()

        out = []
        for row in rows:
            out.append(
                {
                    "mission_id": int(row[0]),
                    "mission_code": row[1],
                    "title": row[2],
                    "progress_count": int(row[3]),
                    "target_count": int(row[4]),
                    "status": row[5],
                    "reward_granted": bool(row[6]),
                    "claimed_at": row[7],
                    "updated_at": row[8],
                }
            )
        return out
