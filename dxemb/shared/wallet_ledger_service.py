"""Wallet and immutable ledger foundation service.

This module is intentionally standalone for Slice 3 so it can be validated
with isolated tests before any bot/web integration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from psycopg2.extras import Json


DEFAULT_DATABASE_URL = "postgresql://dxemb:dxemb@db:5432/dxemb"


class WalletServiceError(Exception):
    """Base error for wallet service operations."""


class InsufficientFundsError(WalletServiceError):
    """Raised when a debit/adjustment would make balance negative."""


class InvalidAmountError(WalletServiceError):
    """Raised when provided amount is invalid for an operation."""


@dataclass(frozen=True)
class LedgerResult:
    ledger_id: int
    discord_user_id: str
    entry_type: str
    amount: int
    signed_amount: int
    balance_before: int
    balance_after: int
    reference_type: str
    reference_id: str
    applied: bool
    idempotent: bool


class WalletLedgerService:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.database_url, connect_timeout=5)

    def ensure_player(self, discord_user_id: str, username: str | None = None) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO player (discord_id, username)
                    VALUES (%s, %s)
                    ON CONFLICT (discord_id)
                    DO UPDATE SET username = COALESCE(EXCLUDED.username, player.username)
                    """,
                    (discord_user_id, username),
                )

    def get_balance(self, discord_user_id: str) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT balance
                    FROM wallet_account
                    WHERE discord_user_id = %s
                    """,
                    (discord_user_id,),
                )
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def credit(
        self,
        discord_user_id: str,
        amount: int,
        reference_type: str,
        reference_id: str,
        reason_code: str,
        *,
        reason_text: str | None = None,
        actor_discord_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerResult:
        return self._apply_entry(
            discord_user_id=discord_user_id,
            entry_type="CREDIT",
            signed_amount=amount,
            reference_type=reference_type,
            reference_id=reference_id,
            reason_code=reason_code,
            reason_text=reason_text,
            actor_discord_id=actor_discord_id,
            metadata=metadata,
        )

    def debit(
        self,
        discord_user_id: str,
        amount: int,
        reference_type: str,
        reference_id: str,
        reason_code: str,
        *,
        reason_text: str | None = None,
        actor_discord_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerResult:
        return self._apply_entry(
            discord_user_id=discord_user_id,
            entry_type="DEBIT",
            signed_amount=-amount,
            reference_type=reference_type,
            reference_id=reference_id,
            reason_code=reason_code,
            reason_text=reason_text,
            actor_discord_id=actor_discord_id,
            metadata=metadata,
        )

    def admin_adjust(
        self,
        discord_user_id: str,
        signed_amount: int,
        reference_id: str,
        reason_code: str,
        *,
        reason_text: str | None = None,
        actor_discord_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerResult:
        if actor_discord_id.strip() == "":
            raise InvalidAmountError("actor_discord_id is required for admin adjustments")

        return self._apply_entry(
            discord_user_id=discord_user_id,
            entry_type="ADJUSTMENT",
            signed_amount=signed_amount,
            reference_type="ADMIN_ADJUST",
            reference_id=reference_id,
            reason_code=reason_code,
            reason_text=reason_text,
            actor_discord_id=actor_discord_id,
            metadata=metadata,
        )

    def list_ledger_entries(self, discord_user_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        discord_user_id,
                        entry_type,
                        amount,
                        signed_amount,
                        balance_before,
                        balance_after,
                        reference_type,
                        reference_id,
                        reason_code,
                        reason_text,
                        actor_discord_id,
                        metadata,
                        created_at
                    FROM wallet_ledger
                    WHERE discord_user_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (discord_user_id, safe_limit, safe_offset),
                )
                rows = cur.fetchall()

        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": row[0],
                    "discord_user_id": row[1],
                    "entry_type": row[2],
                    "amount": int(row[3]),
                    "signed_amount": int(row[4]),
                    "balance_before": int(row[5]),
                    "balance_after": int(row[6]),
                    "reference_type": row[7],
                    "reference_id": row[8],
                    "reason_code": row[9],
                    "reason_text": row[10],
                    "actor_discord_id": row[11],
                    "metadata": row[12],
                    "created_at": row[13],
                }
            )

        return out

    def _apply_entry(
        self,
        *,
        discord_user_id: str,
        entry_type: str,
        signed_amount: int,
        reference_type: str,
        reference_id: str,
        reason_code: str,
        reason_text: str | None,
        actor_discord_id: str | None,
        metadata: dict[str, Any] | None,
    ) -> LedgerResult:
        if signed_amount == 0:
            raise InvalidAmountError("signed amount must not be zero")

        amount = abs(signed_amount)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        amount,
                        signed_amount,
                        balance_before,
                        balance_after,
                        entry_type
                    FROM wallet_ledger
                    WHERE discord_user_id = %s
                      AND reference_type = %s
                      AND reference_id = %s
                    """,
                    (discord_user_id, reference_type, reference_id),
                )
                existing = cur.fetchone()
                if existing:
                    return LedgerResult(
                        ledger_id=int(existing[0]),
                        discord_user_id=discord_user_id,
                        entry_type=existing[5],
                        amount=int(existing[1]),
                        signed_amount=int(existing[2]),
                        balance_before=int(existing[3]),
                        balance_after=int(existing[4]),
                        reference_type=reference_type,
                        reference_id=reference_id,
                        applied=False,
                        idempotent=True,
                    )

                cur.execute(
                    """
                    INSERT INTO wallet_account (discord_user_id, balance)
                    VALUES (%s, 0)
                    ON CONFLICT (discord_user_id) DO NOTHING
                    """,
                    (discord_user_id,),
                )

                cur.execute(
                    """
                    SELECT balance
                    FROM wallet_account
                    WHERE discord_user_id = %s
                    FOR UPDATE
                    """,
                    (discord_user_id,),
                )
                balance_before = int(cur.fetchone()[0])
                balance_after = balance_before + signed_amount
                if balance_after < 0:
                    raise InsufficientFundsError(
                        f"insufficient funds for {discord_user_id}: {balance_before} < {amount}"
                    )

                cur.execute(
                    """
                    UPDATE wallet_account
                    SET balance = %s,
                        updated_at = NOW()
                    WHERE discord_user_id = %s
                    """,
                    (balance_after, discord_user_id),
                )

                cur.execute(
                    """
                    INSERT INTO wallet_ledger (
                        discord_user_id,
                        entry_type,
                        amount,
                        signed_amount,
                        balance_before,
                        balance_after,
                        reference_type,
                        reference_id,
                        reason_code,
                        reason_text,
                        actor_discord_id,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        discord_user_id,
                        entry_type,
                        amount,
                        signed_amount,
                        balance_before,
                        balance_after,
                        reference_type,
                        reference_id,
                        reason_code,
                        reason_text,
                        actor_discord_id,
                        Json(metadata or {}),
                    ),
                )
                ledger_id = int(cur.fetchone()[0])

        return LedgerResult(
            ledger_id=ledger_id,
            discord_user_id=discord_user_id,
            entry_type=entry_type,
            amount=amount,
            signed_amount=signed_amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reference_type=reference_type,
            reference_id=reference_id,
            applied=True,
            idempotent=False,
        )
