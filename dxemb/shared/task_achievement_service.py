"""Daily task and achievement local foundation service."""

from __future__ import annotations

import os
from datetime import datetime
from datetime import timezone
from typing import Any

from psycopg2.extras import Json

from shared.wallet_ledger_service import WalletLedgerService


DEFAULT_DATABASE_URL = "postgresql://dxemb:dxemb@db:5432/dxemb"


class TaskAchievementError(Exception):
    """Base error for task/achievement operations."""


class DefinitionNotFoundError(TaskAchievementError):
    """Raised when required definition rows are missing or disabled."""


class ProgressValidationError(TaskAchievementError):
    """Raised for invalid progress/unlock input."""


class TaskAchievementService:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.wallet = WalletLedgerService(database_url=self.database_url)

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.database_url, connect_timeout=5)

    @staticmethod
    def utc_cycle_date(now: datetime) -> str:
        return now.astimezone(timezone.utc).date().isoformat()

    def create_task_definition(
        self,
        *,
        task_code: str,
        display_name: str,
        description: str,
        target_count: int,
        reward_amount: int,
        actor_id: str,
        is_enabled: bool = True,
    ) -> int:
        if target_count <= 0:
            raise ProgressValidationError("target_count must be > 0")
        if reward_amount < 0:
            raise ProgressValidationError("reward_amount must be >= 0")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO task_definition (
                        task_code,
                        display_name,
                        description,
                        target_count,
                        reward_amount,
                        is_enabled,
                        created_by,
                        updated_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (task_code)
                    DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        description = EXCLUDED.description,
                        target_count = EXCLUDED.target_count,
                        reward_amount = EXCLUDED.reward_amount,
                        is_enabled = EXCLUDED.is_enabled,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (
                        task_code,
                        display_name,
                        description,
                        target_count,
                        reward_amount,
                        bool(is_enabled),
                        actor_id,
                        actor_id,
                    ),
                )
                return int(cur.fetchone()[0])

    def create_achievement_definition(
        self,
        *,
        achievement_code: str,
        display_name: str,
        description: str,
        trigger_kind: str,
        target_value: int,
        reward_amount: int,
        actor_id: str,
        is_enabled: bool = True,
        one_time: bool = True,
    ) -> int:
        if target_value <= 0:
            raise ProgressValidationError("target_value must be > 0")
        if reward_amount < 0:
            raise ProgressValidationError("reward_amount must be >= 0")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO achievement_definition (
                        achievement_code,
                        display_name,
                        description,
                        trigger_kind,
                        target_value,
                        reward_amount,
                        one_time,
                        is_enabled,
                        created_by,
                        updated_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (achievement_code)
                    DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        description = EXCLUDED.description,
                        trigger_kind = EXCLUDED.trigger_kind,
                        target_value = EXCLUDED.target_value,
                        reward_amount = EXCLUDED.reward_amount,
                        one_time = EXCLUDED.one_time,
                        is_enabled = EXCLUDED.is_enabled,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (
                        achievement_code,
                        display_name,
                        description,
                        trigger_kind,
                        target_value,
                        reward_amount,
                        bool(one_time),
                        bool(is_enabled),
                        actor_id,
                        actor_id,
                    ),
                )
                return int(cur.fetchone()[0])

    def record_task_progress(
        self,
        *,
        discord_user_id: str,
        task_code: str,
        increment: int,
        now: datetime,
        actor_id: str,
        apply_reward: bool = False,
    ) -> dict[str, Any]:
        if increment <= 0:
            raise ProgressValidationError("increment must be > 0")

        self.wallet.ensure_player(discord_user_id)
        cycle_date = self.utc_cycle_date(now)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, target_count, reward_amount, is_enabled
                    FROM task_definition
                    WHERE task_code = %s
                    """,
                    (task_code,),
                )
                task = cur.fetchone()
                if not task or not bool(task[3]):
                    raise DefinitionNotFoundError(f"task not found or disabled: {task_code}")

                task_id = int(task[0])
                target_count = int(task[1])
                reward_amount = int(task[2])

                cur.execute(
                    """
                    SELECT id, progress_count, completed_at, reward_granted, reward_reference_id
                    FROM task_progress
                    WHERE discord_user_id = %s
                      AND task_id = %s
                      AND cycle_date_utc = %s
                    FOR UPDATE
                    """,
                    (discord_user_id, task_id, cycle_date),
                )
                row = cur.fetchone()

                if row:
                    progress_id = int(row[0])
                    progress_count = int(row[1]) + increment
                    completed_at = row[2]
                    reward_granted = bool(row[3])
                else:
                    progress_id = None
                    progress_count = increment
                    completed_at = None
                    reward_granted = False

                newly_completed = completed_at is None and progress_count >= target_count
                completed_at_value = now if newly_completed else completed_at

                reward_reference_id = None
                reward_ledger_id = None
                if newly_completed and apply_reward and reward_amount > 0 and not reward_granted:
                    reward_reference_id = f"TASK_REWARD:{task_code}:{discord_user_id}:{cycle_date}"
                    reward_entry = self.wallet.credit(
                        discord_user_id=discord_user_id,
                        amount=reward_amount,
                        reference_type="TASK_REWARD",
                        reference_id=reward_reference_id,
                        reason_code="TASK_COMPLETION_REWARD",
                        actor_discord_id=actor_id,
                        metadata={"task_code": task_code, "cycle_date_utc": cycle_date},
                    )
                    reward_ledger_id = reward_entry.ledger_id
                    reward_granted = True

                if progress_id is None:
                    cur.execute(
                        """
                        INSERT INTO task_progress (
                            discord_user_id,
                            task_id,
                            cycle_date_utc,
                            progress_count,
                            completed_at,
                            reward_granted,
                            reward_reference_id,
                            reward_ledger_id,
                            metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            discord_user_id,
                            task_id,
                            cycle_date,
                            progress_count,
                            completed_at_value,
                            reward_granted,
                            reward_reference_id,
                            reward_ledger_id,
                            Json({"actor_id": actor_id}),
                        ),
                    )
                    progress_id = int(cur.fetchone()[0])
                else:
                    cur.execute(
                        """
                        UPDATE task_progress
                        SET progress_count = %s,
                            completed_at = COALESCE(completed_at, %s),
                            reward_granted = %s,
                            reward_reference_id = COALESCE(reward_reference_id, %s),
                            reward_ledger_id = COALESCE(reward_ledger_id, %s),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            progress_count,
                            completed_at_value,
                            reward_granted,
                            reward_reference_id,
                            reward_ledger_id,
                            progress_id,
                        ),
                    )

                return {
                    "progress_id": progress_id,
                    "task_code": task_code,
                    "cycle_date_utc": cycle_date,
                    "progress_count": progress_count,
                    "target_count": target_count,
                    "completed": progress_count >= target_count,
                    "reward_granted": reward_granted,
                    "reward_reference_id": reward_reference_id,
                    "reward_ledger_id": reward_ledger_id,
                    "mode": "wallet-settle" if apply_reward else "dry-run",
                }

    def unlock_achievement(
        self,
        *,
        discord_user_id: str,
        achievement_code: str,
        now: datetime,
        actor_id: str,
        apply_reward: bool = False,
    ) -> dict[str, Any]:
        self.wallet.ensure_player(discord_user_id)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, reward_amount, is_enabled
                    FROM achievement_definition
                    WHERE achievement_code = %s
                    """,
                    (achievement_code,),
                )
                ach = cur.fetchone()
                if not ach or not bool(ach[2]):
                    raise DefinitionNotFoundError(f"achievement not found or disabled: {achievement_code}")

                achievement_id = int(ach[0])
                reward_amount = int(ach[1])

                cur.execute(
                    """
                    SELECT id, reward_granted, reward_reference_id, reward_ledger_id
                    FROM achievement_unlock
                    WHERE discord_user_id = %s
                      AND achievement_id = %s
                    FOR UPDATE
                    """,
                    (discord_user_id, achievement_id),
                )
                existing = cur.fetchone()
                if existing:
                    return {
                        "unlock_id": int(existing[0]),
                        "achievement_code": achievement_code,
                        "reward_granted": bool(existing[1]),
                        "reward_reference_id": existing[2],
                        "reward_ledger_id": existing[3],
                        "idempotent": True,
                    }

                reward_reference_id = None
                reward_ledger_id = None
                reward_granted = False
                if apply_reward and reward_amount > 0:
                    reward_reference_id = f"ACH_REWARD:{achievement_code}:{discord_user_id}"
                    reward_entry = self.wallet.credit(
                        discord_user_id=discord_user_id,
                        amount=reward_amount,
                        reference_type="ACH_REWARD",
                        reference_id=reward_reference_id,
                        reason_code="ACHIEVEMENT_REWARD",
                        actor_discord_id=actor_id,
                        metadata={"achievement_code": achievement_code},
                    )
                    reward_ledger_id = reward_entry.ledger_id
                    reward_granted = True

                cur.execute(
                    """
                    INSERT INTO achievement_unlock (
                        discord_user_id,
                        achievement_id,
                        unlocked_at,
                        reward_granted,
                        reward_reference_id,
                        reward_ledger_id,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        discord_user_id,
                        achievement_id,
                        now,
                        reward_granted,
                        reward_reference_id,
                        reward_ledger_id,
                        Json({"actor_id": actor_id}),
                    ),
                )
                unlock_id = int(cur.fetchone()[0])

                return {
                    "unlock_id": unlock_id,
                    "achievement_code": achievement_code,
                    "reward_granted": reward_granted,
                    "reward_reference_id": reward_reference_id,
                    "reward_ledger_id": reward_ledger_id,
                    "idempotent": False,
                }

    def evaluate_task_completion_achievements(
        self,
        *,
        discord_user_id: str,
        now: datetime,
        actor_id: str,
        apply_reward: bool = False,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT achievement_code, target_value
                    FROM achievement_definition
                    WHERE trigger_kind = 'TASK_COMPLETIONS'
                      AND is_enabled = TRUE
                    ORDER BY id ASC
                    """,
                )
                ach_rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM task_progress
                    WHERE discord_user_id = %s
                      AND completed_at IS NOT NULL
                    """,
                    (discord_user_id,),
                )
                completed_count = int(cur.fetchone()[0])

        unlocked: list[dict[str, Any]] = []
        for row in ach_rows:
            code = row[0]
            threshold = int(row[1])
            if completed_count >= threshold:
                unlocked.append(
                    self.unlock_achievement(
                        discord_user_id=discord_user_id,
                        achievement_code=code,
                        now=now,
                        actor_id=actor_id,
                        apply_reward=apply_reward,
                    )
                )
        return unlocked

    def list_task_progress(self, *, discord_user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT td.task_code, tp.cycle_date_utc, tp.progress_count, td.target_count,
                           tp.completed_at, tp.reward_granted, tp.created_at
                    FROM task_progress tp
                    JOIN task_definition td ON td.id = tp.task_id
                    WHERE tp.discord_user_id = %s
                    ORDER BY tp.cycle_date_utc DESC, tp.created_at DESC
                    LIMIT %s
                    """,
                    (discord_user_id, safe_limit),
                )
                rows = cur.fetchall()

        out = []
        for row in rows:
            out.append(
                {
                    "task_code": row[0],
                    "cycle_date_utc": row[1].isoformat(),
                    "progress_count": int(row[2]),
                    "target_count": int(row[3]),
                    "completed_at": row[4],
                    "reward_granted": bool(row[5]),
                    "created_at": row[6],
                }
            )
        return out

    def list_achievement_unlocks(self, *, discord_user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ad.achievement_code, au.unlocked_at, au.reward_granted,
                           au.reward_reference_id, au.reward_ledger_id
                    FROM achievement_unlock au
                    JOIN achievement_definition ad ON ad.id = au.achievement_id
                    WHERE au.discord_user_id = %s
                    ORDER BY au.unlocked_at DESC, au.id DESC
                    LIMIT %s
                    """,
                    (discord_user_id, safe_limit),
                )
                rows = cur.fetchall()

        out = []
        for row in rows:
            out.append(
                {
                    "achievement_code": row[0],
                    "unlocked_at": row[1],
                    "reward_granted": bool(row[2]),
                    "reward_reference_id": row[3],
                    "reward_ledger_id": row[4],
                }
            )
        return out
