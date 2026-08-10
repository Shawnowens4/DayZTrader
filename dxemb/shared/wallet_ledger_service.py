"""Wallet and immutable virtual-credit ledger service.

This service keeps the existing wallet_account / wallet_ledger table names for
compatibility, but treats the legacy discord_user_id columns as generic immutable
owner identifiers during the local-admin foundation stage.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from datetime import timezone
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


class InvalidOwnerError(WalletServiceError):
    """Raised when a wallet owner identifier is invalid."""


class MetadataValidationError(WalletServiceError):
    """Raised when metadata contains unsupported or unsafe content."""


OWNER_KINDS = {"LOCAL_PLAYER", "LOCAL_ADMIN", "SYSTEM"}
ENTRY_TYPES = {"CREDIT", "DEBIT", "ADMIN_ADJUSTMENT", "REVERSAL", "REFUND"}
_OWNER_ID_RE = re.compile(r"^[A-Za-z0-9:_\-.]{1,80}$")
_SECRET_KEY_RE = re.compile(r"token|password|secret|authorization|cookie|session", re.IGNORECASE)
_MAX_METADATA_DEPTH = 4
_MAX_METADATA_LIST_ITEMS = 50
_MAX_METADATA_STRING = 500


@dataclass(frozen=True)
class LedgerResult:
    ledger_id: int
    owner_id: str
    entry_type: str
    amount: int
    signed_amount: int
    balance_before: int
    balance_after: int
    reference_type: str
    reference_id: str
    idempotency_key: str
    actor_id: str
    actor_source: str
    reason_code: str | None
    reason_text: str
    applied: bool
    idempotent: bool

    @property
    def discord_user_id(self) -> str:
        return self.owner_id

    @property
    def transaction_type(self) -> str:
        return self.entry_type

    @property
    def amount_minor(self) -> int:
        return self.signed_amount

    @property
    def balance_after_minor(self) -> int:
        return self.balance_after


class WalletLedgerService:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.database_url, connect_timeout=5)

    def ensure_player(self, discord_user_id: str, username: str | None = None) -> None:
        self.ensure_wallet_owner(
            owner_id=discord_user_id,
            display_name=username,
            owner_kind="LOCAL_PLAYER",
        )

    def ensure_wallet_owner(
        self,
        owner_id: str,
        display_name: str | None = None,
        owner_kind: str = "LOCAL_PLAYER",
    ) -> None:
        normalized_owner_id = self._normalize_owner_id(owner_id)
        normalized_kind = self._normalize_owner_kind(owner_kind)
        normalized_label = self._normalize_optional_text(display_name)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO player (discord_id, username)
                    VALUES (%s, %s)
                    ON CONFLICT (discord_id)
                    DO UPDATE SET username = COALESCE(EXCLUDED.username, player.username)
                    """,
                    (normalized_owner_id, normalized_label),
                )
                cur.execute(
                    """
                    INSERT INTO wallet_account (discord_user_id, owner_kind, owner_label, balance)
                    VALUES (%s, %s, %s, 0)
                    ON CONFLICT (discord_user_id)
                    DO UPDATE SET owner_kind = EXCLUDED.owner_kind,
                                  owner_label = COALESCE(EXCLUDED.owner_label, wallet_account.owner_label)
                    """,
                    (normalized_owner_id, normalized_kind, normalized_label),
                )

    def get_balance(self, discord_user_id: str) -> int:
        normalized_owner_id = self._normalize_owner_id(discord_user_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT balance
                    FROM wallet_account
                    WHERE discord_user_id = %s
                    """,
                    (normalized_owner_id,),
                )
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def get_wallet_owner(self, owner_id: str) -> dict[str, Any] | None:
        normalized_owner_id = self._normalize_owner_id(owner_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        a.id,
                        a.discord_user_id,
                        a.owner_kind,
                        a.owner_label,
                        a.balance,
                        a.created_at,
                        a.updated_at,
                        COALESCE(stats.tx_count, 0),
                        stats.latest_activity
                    FROM wallet_account a
                    LEFT JOIN (
                        SELECT discord_user_id, COUNT(*)::BIGINT AS tx_count, MAX(created_at) AS latest_activity
                        FROM wallet_ledger
                        GROUP BY discord_user_id
                    ) stats ON stats.discord_user_id = a.discord_user_id
                    WHERE a.discord_user_id = %s
                    LIMIT 1
                    """,
                    (normalized_owner_id,),
                )
                row = cur.fetchone()

        if not row:
            return None

        return {
            "account_id": int(row[0]),
            "owner_id": row[1],
            "owner_kind": row[2],
            "owner_label": row[3],
            "balance_minor": int(row[4]),
            "created_at": row[5],
            "updated_at": row[6],
            "transaction_count": int(row[7]),
            "latest_activity": row[8],
        }

    def get_wallet_summary(self, owner_id: str) -> dict[str, Any] | None:
        owner = self.get_wallet_owner(owner_id)
        if owner is None:
            return None

        normalized_owner_id = self._normalize_owner_id(owner_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN signed_amount > 0 THEN signed_amount ELSE 0 END), 0),
                        COALESCE(ABS(SUM(CASE WHEN signed_amount < 0 THEN signed_amount ELSE 0 END)), 0),
                        COALESCE(SUM(signed_amount), 0),
                        COALESCE(MAX(created_at), NULL)
                    FROM wallet_ledger
                    WHERE discord_user_id = %s
                    """,
                    (normalized_owner_id,),
                )
                totals = cur.fetchone()

                cur.execute(
                    """
                    SELECT reference_type, reference_id, entry_type, created_at
                    FROM wallet_ledger
                    WHERE discord_user_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (normalized_owner_id,),
                )
                latest = cur.fetchone()

        owner["total_credits_minor"] = int(totals[0])
        owner["total_debits_minor"] = int(totals[1])
        owner["ledger_net_minor"] = int(totals[2])
        owner["last_ledger_at"] = totals[3]
        owner["recent_reference"] = (
            {
                "reference_type": latest[0],
                "reference_id": latest[1],
                "entry_type": latest[2],
                "created_at": latest[3],
            }
            if latest
            else None
        )
        return owner

    def list_wallet_owners(self, query: str = "", limit: int = 25, offset: int = 0) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 50))
        safe_offset = max(0, offset)
        pattern = f"%{query.strip()}%" if query.strip() else None

        statement = """
            SELECT
                a.id,
                a.discord_user_id,
                a.owner_kind,
                a.owner_label,
                a.balance,
                a.created_at,
                a.updated_at,
                COALESCE(stats.tx_count, 0),
                stats.latest_activity
            FROM wallet_account a
            LEFT JOIN (
                SELECT discord_user_id, COUNT(*)::BIGINT AS tx_count, MAX(created_at) AS latest_activity
                FROM wallet_ledger
                GROUP BY discord_user_id
            ) stats ON stats.discord_user_id = a.discord_user_id
            WHERE (%s IS NULL OR a.discord_user_id ILIKE %s OR COALESCE(a.owner_label, '') ILIKE %s)
            ORDER BY COALESCE(stats.latest_activity, a.updated_at, a.created_at) DESC, a.discord_user_id ASC
            LIMIT %s OFFSET %s
        """

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(statement, (pattern, pattern, pattern, safe_limit, safe_offset))
                rows = cur.fetchall()

        return [
            {
                "account_id": int(row[0]),
                "owner_id": row[1],
                "owner_kind": row[2],
                "owner_label": row[3],
                "balance_minor": int(row[4]),
                "created_at": row[5],
                "updated_at": row[6],
                "transaction_count": int(row[7]),
                "latest_activity": row[8],
            }
            for row in rows
        ]

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
        actor_source: str = "service",
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerResult:
        return self._apply_entry(
            owner_id=discord_user_id,
            entry_type="CREDIT",
            signed_amount=amount,
            reference_type=reference_type,
            reference_id=reference_id,
            reason_code=reason_code,
            reason_text=reason_text,
            actor_id=actor_discord_id,
            actor_source=actor_source,
            idempotency_key=idempotency_key,
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
        actor_source: str = "service",
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerResult:
        return self._apply_entry(
            owner_id=discord_user_id,
            entry_type="DEBIT",
            signed_amount=-amount,
            reference_type=reference_type,
            reference_id=reference_id,
            reason_code=reason_code,
            reason_text=reason_text,
            actor_id=actor_discord_id,
            actor_source=actor_source,
            idempotency_key=idempotency_key,
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
        actor_source: str = "local_admin",
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerResult:
        if self._normalize_optional_text(actor_discord_id) is None:
            raise InvalidAmountError("actor_discord_id is required for admin adjustments")
        if self._normalize_optional_text(reason_text) is None:
            raise InvalidAmountError("reason_text is required for admin adjustments")

        return self._apply_entry(
            owner_id=discord_user_id,
            entry_type="ADMIN_ADJUSTMENT",
            signed_amount=signed_amount,
            reference_type="ADMIN_ADJUST",
            reference_id=reference_id,
            reason_code=reason_code,
            reason_text=reason_text,
            actor_id=actor_discord_id,
            actor_source=actor_source,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )

    def reverse_entry(
        self,
        *,
        owner_id: str,
        original_ledger_id: int,
        transaction_type: str,
        idempotency_key: str,
        actor_id: str,
        actor_source: str,
        reason_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerResult:
        normalized_owner_id = self._normalize_owner_id(owner_id)
        normalized_transaction_type = transaction_type.strip().upper()
        if normalized_transaction_type not in {"REVERSAL", "REFUND"}:
            raise InvalidAmountError("transaction_type must be REVERSAL or REFUND")
        normalized_idempotency_key = self._normalize_required_text(idempotency_key, "idempotency_key")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, signed_amount, reference_type, reference_id, entry_type
                    FROM wallet_ledger
                    WHERE id = %s AND discord_user_id = %s
                    LIMIT 1
                    """,
                    (original_ledger_id, normalized_owner_id),
                )
                row = cur.fetchone()
                if not row:
                    raise InvalidOwnerError("original ledger entry not found for owner")

                original_entry_type = (row[4] or "").strip().upper()
                if original_entry_type in {"REVERSAL", "REFUND"}:
                    raise InvalidAmountError("cannot reverse a correction entry")

                cur.execute(
                    """
                    SELECT
                        id,
                        entry_type,
                        amount,
                        signed_amount,
                        balance_before,
                        balance_after,
                        idempotency_key,
                        actor_discord_id,
                        actor_source,
                        reason_code,
                        reason_text,
                        reference_type,
                        reference_id
                    FROM wallet_ledger
                    WHERE discord_user_id = %s
                      AND reference_type IN ('REVERSAL', 'REFUND')
                      AND reference_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (normalized_owner_id, str(original_ledger_id)),
                )
                existing_correction = cur.fetchone()

                if existing_correction:
                    existing_type = (existing_correction[1] or "").strip().upper()
                    existing_idempotency = existing_correction[6]
                    if existing_idempotency == normalized_idempotency_key:
                        return LedgerResult(
                            ledger_id=int(existing_correction[0]),
                            owner_id=normalized_owner_id,
                            entry_type=existing_type,
                            amount=int(existing_correction[2]),
                            signed_amount=int(existing_correction[3]),
                            balance_before=int(existing_correction[4]),
                            balance_after=int(existing_correction[5]),
                            reference_type=existing_correction[11],
                            reference_id=existing_correction[12],
                            idempotency_key=existing_idempotency,
                            actor_id=existing_correction[7] or "system:local",
                            actor_source=existing_correction[8],
                            reason_code=existing_correction[9],
                            reason_text=existing_correction[10],
                            applied=False,
                            idempotent=True,
                        )

                    if existing_type == normalized_transaction_type:
                        raise InvalidAmountError(
                            f"a {existing_type} already exists for ledger entry {original_ledger_id}"
                        )

                    raise InvalidAmountError(
                        f"ledger entry {original_ledger_id} already has correction type {existing_type}"
                    )

        signed_amount = -int(row[1])
        return self._apply_entry(
            owner_id=normalized_owner_id,
            entry_type=normalized_transaction_type,
            signed_amount=signed_amount,
            reference_type=normalized_transaction_type,
            reference_id=str(original_ledger_id),
            reason_code=normalized_transaction_type,
            reason_text=reason_text,
            actor_id=actor_id,
            actor_source=actor_source,
            idempotency_key=normalized_idempotency_key,
            metadata={
                **(metadata or {}),
                "original_ledger_id": original_ledger_id,
                "original_reference_type": row[2],
                "original_reference_id": row[3],
                "original_entry_type": row[4],
            },
        )

    def list_ledger_history(
        self,
        owner_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        entry_type: str | None = None,
        direction: str = "all",
        status: str = "all",
        reference_query: str = "",
        created_after: str = "",
        created_before: str = "",
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)
        normalized_owner_id = self._normalize_owner_id(owner_id)

        conditions = ["wl.discord_user_id = %s"]
        params: list[Any] = [normalized_owner_id]

        normalized_direction = (direction or "all").strip().lower()
        if normalized_direction not in {"all", "credit", "debit"}:
            raise InvalidAmountError("direction must be one of all, credit, debit")
        if normalized_direction == "credit":
            conditions.append("wl.signed_amount > 0")
        elif normalized_direction == "debit":
            conditions.append("wl.signed_amount < 0")

        normalized_status = (status or "all").strip().lower()
        if normalized_status not in {"all", "posted", "corrected", "correction"}:
            raise InvalidAmountError("status must be one of all, posted, corrected, correction")
        if normalized_status == "correction":
            conditions.append("wl.entry_type IN ('REVERSAL', 'REFUND')")
        elif normalized_status == "corrected":
            conditions.append("wl.entry_type NOT IN ('REVERSAL', 'REFUND')")
            conditions.append(
                "EXISTS (SELECT 1 FROM wallet_ledger corr WHERE corr.discord_user_id = wl.discord_user_id "
                "AND corr.reference_type IN ('REVERSAL', 'REFUND') AND corr.reference_id = wl.id::text)"
            )
        elif normalized_status == "posted":
            conditions.append("wl.entry_type NOT IN ('REVERSAL', 'REFUND')")
            conditions.append(
                "NOT EXISTS (SELECT 1 FROM wallet_ledger corr WHERE corr.discord_user_id = wl.discord_user_id "
                "AND corr.reference_type IN ('REVERSAL', 'REFUND') AND corr.reference_id = wl.id::text)"
            )

        normalized_entry_type = (entry_type or "").strip().upper()
        if normalized_entry_type:
            if normalized_entry_type not in ENTRY_TYPES | {"HOLD", "RELEASE"}:
                raise InvalidAmountError("unsupported transaction type filter")
            conditions.append("wl.entry_type = %s")
            params.append(normalized_entry_type)

        normalized_created_after = self._parse_optional_datetime(created_after, "created_after")
        if normalized_created_after:
            conditions.append("wl.created_at >= %s")
            params.append(normalized_created_after)

        normalized_created_before = self._parse_optional_datetime(created_before, "created_before")
        if normalized_created_before:
            conditions.append("wl.created_at <= %s")
            params.append(normalized_created_before)

        reference_filter = (reference_query or "").strip()
        if reference_filter:
            like = f"%{reference_filter}%"
            conditions.append(
                "(wl.reference_type ILIKE %s OR wl.reference_id ILIKE %s OR wl.idempotency_key ILIKE %s OR COALESCE(wl.reason_text, '') ILIKE %s)"
            )
            params.extend([like, like, like, like])

        where_clause = " AND ".join(conditions)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        wl.id,
                        wl.discord_user_id,
                        wl.entry_type,
                        wl.amount,
                        wl.signed_amount,
                        wl.balance_before,
                        wl.balance_after,
                        wl.reference_type,
                        wl.reference_id,
                        wl.idempotency_key,
                        wl.reason_code,
                        wl.reason_text,
                        wl.actor_discord_id,
                        wl.actor_source,
                        wl.metadata,
                        wl.created_at
                    FROM wallet_ledger wl
                    WHERE {where_clause}
                    ORDER BY wl.created_at DESC, wl.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (*params, safe_limit, safe_offset),
                )
                rows = cur.fetchall()

                row_ids = [int(row[0]) for row in rows]
                corrected_by: dict[int, list[dict[str, Any]]] = {}
                if row_ids:
                    cur.execute(
                        """
                        SELECT
                            id,
                            entry_type,
                            reference_id,
                            idempotency_key,
                            created_at
                        FROM wallet_ledger
                        WHERE discord_user_id = %s
                          AND reference_type IN ('REVERSAL', 'REFUND')
                          AND reference_id = ANY(%s)
                        ORDER BY created_at DESC, id DESC
                        """,
                        (normalized_owner_id, [str(v) for v in row_ids]),
                    )
                    for corr in cur.fetchall():
                        original_id = int(corr[2])
                        corrected_by.setdefault(original_id, []).append(
                            {
                                "ledger_id": int(corr[0]),
                                "entry_type": corr[1],
                                "idempotency_key": corr[3],
                                "created_at": corr[4],
                            }
                        )

        out: list[dict[str, Any]] = []
        for row in rows:
            entry_id = int(row[0])
            entry_type_value = row[2]
            signed_minor = int(row[4])
            is_correction = entry_type_value in {"REVERSAL", "REFUND"}
            original_ledger_id = self._extract_original_ledger_id(
                reference_type=row[7],
                reference_id=row[8],
                metadata=row[14],
            )
            row_corrected_by = corrected_by.get(entry_id, [])
            if is_correction:
                normalized_status_value = "correction"
            elif row_corrected_by:
                normalized_status_value = "corrected"
            else:
                normalized_status_value = "posted"

            out.append(
                {
                    "id": entry_id,
                    "discord_user_id": row[1],
                    "entry_type": entry_type_value,
                    "amount": int(row[3]),
                    "amount_minor": signed_minor,
                    "signed_amount": signed_minor,
                    "balance_before": int(row[5]),
                    "balance_after": int(row[6]),
                    "balance_after_minor": int(row[6]),
                    "reference_type": row[7],
                    "reference_id": row[8],
                    "idempotency_key": row[9],
                    "reason_code": row[10],
                    "reason_text": row[11],
                    "actor_discord_id": row[12],
                    "actor_source": row[13],
                    "metadata": row[14],
                    "created_at": row[15],
                    "direction": "credit" if signed_minor > 0 else "debit",
                    "status": normalized_status_value,
                    "display_type": self._display_entry_type(entry_type_value),
                    "display_direction": "Credit" if signed_minor > 0 else "Debit",
                    "display_reference": f"{row[7]}:{row[8]}",
                    "original_ledger_id": original_ledger_id,
                    "is_correction": is_correction,
                    "corrected_by": row_corrected_by,
                    "related_order_id": self._extract_related_order_id(row[14]),
                    "trace_context": self._build_trace_context(
                        entry_type=entry_type_value,
                        reference_type=row[7],
                        metadata=row[14],
                        original_ledger_id=original_ledger_id,
                        corrected_by=row_corrected_by,
                    ),
                }
            )

        return out

    def list_ledger_entries(self, discord_user_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self.list_ledger_history(
            discord_user_id,
            limit=limit,
            offset=offset,
            entry_type=None,
            direction="all",
            reference_query="",
            status="all",
            created_after="",
            created_before="",
        )

    def create_authorized_entry(
        self,
        *,
        owner_id: str,
        operation: str,
        amount_minor: int,
        reason_text: str,
        actor_id: str,
        actor_source: str = "local_admin",
        idempotency_key: str | None = None,
        reference_id: str | None = None,
        reason_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerResult:
        normalized_operation = (operation or "").strip().lower()
        normalized_reason_text = self._normalize_required_text(reason_text, "reason_text")
        normalized_actor_id = self._normalize_required_text(actor_id, "actor_id")

        if normalized_operation not in {"credit", "debit", "adjustment"}:
            raise InvalidAmountError("operation must be one of credit, debit, adjustment")
        if amount_minor == 0:
            raise InvalidAmountError("amount_minor must not be zero")

        amount = abs(int(amount_minor))
        operation_ref = (
            self._normalize_optional_text(reference_id)
            or self._normalize_optional_text(idempotency_key)
            or f"wallet-op-{uuid.uuid4().hex[:16]}"
        )
        operation_idempotency = self._normalize_optional_text(idempotency_key) or operation_ref

        if normalized_operation == "credit":
            return self.credit(
                discord_user_id=owner_id,
                amount=amount,
                reference_type="ADMIN_CREDIT",
                reference_id=operation_ref,
                reason_code=reason_code or "ADMIN_CREDIT",
                reason_text=normalized_reason_text,
                actor_discord_id=normalized_actor_id,
                actor_source=actor_source,
                idempotency_key=operation_idempotency,
                metadata=metadata,
            )

        if normalized_operation == "debit":
            return self.debit(
                discord_user_id=owner_id,
                amount=amount,
                reference_type="ADMIN_DEBIT",
                reference_id=operation_ref,
                reason_code=reason_code or "ADMIN_DEBIT",
                reason_text=normalized_reason_text,
                actor_discord_id=normalized_actor_id,
                actor_source=actor_source,
                idempotency_key=operation_idempotency,
                metadata=metadata,
            )

        return self.admin_adjust(
            discord_user_id=owner_id,
            signed_amount=int(amount_minor),
            reference_id=operation_ref,
            reason_code=reason_code or "ADMIN_ADJUSTMENT",
            reason_text=normalized_reason_text,
            actor_discord_id=normalized_actor_id,
            actor_source=actor_source,
            idempotency_key=operation_idempotency,
            metadata=metadata,
        )

    def get_ledger_entry(self, owner_id: str, ledger_id: int) -> dict[str, Any] | None:
        normalized_owner_id = self._normalize_owner_id(owner_id)
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
                        idempotency_key,
                        reason_code,
                        reason_text,
                        actor_discord_id,
                        actor_source,
                        metadata,
                        created_at
                    FROM wallet_ledger
                    WHERE discord_user_id = %s
                      AND id = %s
                    LIMIT 1
                    """,
                    (normalized_owner_id, ledger_id),
                )
                row = cur.fetchone()

        if not row:
            return None

        return {
            "id": int(row[0]),
            "discord_user_id": row[1],
            "owner_id": row[1],
            "entry_type": row[2],
            "amount": int(row[3]),
            "amount_minor": int(row[4]),
            "signed_amount": int(row[4]),
            "balance_before": int(row[5]),
            "balance_after": int(row[6]),
            "balance_after_minor": int(row[6]),
            "reference_type": row[7],
            "reference_id": row[8],
            "idempotency_key": row[9],
            "reason_code": row[10],
            "reason_text": row[11],
            "actor_discord_id": row[12],
            "actor_source": row[13],
            "metadata": row[14],
            "created_at": row[15],
        }

    def reconcile_balance(self, owner_id: str) -> dict[str, Any]:
        normalized_owner_id = self._normalize_owner_id(owner_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT balance
                    FROM wallet_account
                    WHERE discord_user_id = %s
                    LIMIT 1
                    """,
                    (normalized_owner_id,),
                )
                account_row = cur.fetchone()
                account_balance = int(account_row[0]) if account_row else 0

                cur.execute(
                    """
                    SELECT COALESCE(SUM(signed_amount), 0), COUNT(*)
                    FROM wallet_ledger
                    WHERE discord_user_id = %s
                    """,
                    (normalized_owner_id,),
                )
                ledger_total, entry_count = cur.fetchone()

        ledger_total_int = int(ledger_total)
        return {
            "owner_id": normalized_owner_id,
            "account_balance_minor": account_balance,
            "ledger_total_minor": ledger_total_int,
            "entry_count": int(entry_count),
            "matches": account_balance == ledger_total_int,
        }

    def _apply_entry(
        self,
        *,
        owner_id: str,
        entry_type: str,
        signed_amount: int,
        reference_type: str,
        reference_id: str,
        reason_code: str,
        reason_text: str | None,
        actor_id: str | None,
        actor_source: str,
        idempotency_key: str | None,
        metadata: dict[str, Any] | None,
    ) -> LedgerResult:
        normalized_owner_id = self._normalize_owner_id(owner_id)
        normalized_entry_type = self._normalize_entry_type(entry_type)
        if signed_amount == 0:
            raise InvalidAmountError("signed amount must not be zero")

        amount = abs(signed_amount)
        normalized_reference_type = self._normalize_required_text(reference_type, "reference_type")
        normalized_reference_id = self._normalize_required_text(reference_id, "reference_id")
        normalized_reason_code = self._normalize_optional_text(reason_code)
        normalized_reason_text = (
            self._normalize_optional_text(reason_text)
            or normalized_reason_code
            or normalized_reference_type
        )
        normalized_actor_id = self._normalize_optional_text(actor_id) or "system:local"
        normalized_actor_source = self._normalize_required_text(actor_source, "actor_source")
        normalized_idempotency_key = self._normalize_required_text(
            idempotency_key or f"{normalized_reference_type}:{normalized_reference_id}",
            "idempotency_key",
        )
        safe_metadata = self._sanitize_metadata(metadata or {})

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO player (discord_id)
                    VALUES (%s)
                    ON CONFLICT (discord_id) DO NOTHING
                    """,
                    (normalized_owner_id,),
                )
                cur.execute(
                    """
                    INSERT INTO wallet_account (discord_user_id, owner_kind, owner_label, balance)
                    VALUES (%s, 'LOCAL_PLAYER', %s, 0)
                    ON CONFLICT (discord_user_id) DO NOTHING
                    """,
                    (normalized_owner_id, normalized_owner_id),
                )

                cur.execute(
                    """
                    SELECT
                        id,
                        amount,
                        signed_amount,
                        balance_before,
                        balance_after,
                        entry_type,
                        idempotency_key,
                        actor_discord_id,
                        actor_source,
                        reason_code,
                        reason_text
                    FROM wallet_ledger
                    WHERE discord_user_id = %s
                      AND idempotency_key = %s
                    """,
                    (normalized_owner_id, normalized_idempotency_key),
                )
                existing = cur.fetchone()
                if existing:
                    return LedgerResult(
                        ledger_id=int(existing[0]),
                        owner_id=normalized_owner_id,
                        entry_type=existing[5],
                        amount=int(existing[1]),
                        signed_amount=int(existing[2]),
                        balance_before=int(existing[3]),
                        balance_after=int(existing[4]),
                        reference_type=normalized_reference_type,
                        reference_id=normalized_reference_id,
                        idempotency_key=existing[6],
                        actor_id=existing[7] or "system:local",
                        actor_source=existing[8],
                        reason_code=existing[9],
                        reason_text=existing[10],
                        applied=False,
                        idempotent=True,
                    )

                cur.execute(
                    """
                    SELECT id, balance
                    FROM wallet_account
                    WHERE discord_user_id = %s
                    FOR UPDATE
                    """,
                    (normalized_owner_id,),
                )
                account_id, balance_before = cur.fetchone()
                account_id = int(account_id)
                balance_before = int(balance_before)
                balance_after = balance_before + signed_amount
                if balance_after < 0:
                    raise InsufficientFundsError(
                        f"insufficient funds for {normalized_owner_id}: {balance_before} < {amount}"
                    )

                cur.execute(
                    """
                    UPDATE wallet_account
                    SET balance = %s,
                        updated_at = NOW()
                    WHERE discord_user_id = %s
                    """,
                    (balance_after, normalized_owner_id),
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
                        idempotency_key,
                        reason_code,
                        reason_text,
                        actor_discord_id,
                        actor_source,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        normalized_owner_id,
                        normalized_entry_type,
                        amount,
                        signed_amount,
                        balance_before,
                        balance_after,
                        normalized_reference_type,
                        normalized_reference_id,
                        normalized_idempotency_key,
                        normalized_reason_code,
                        normalized_reason_text,
                        normalized_actor_id,
                        normalized_actor_source,
                        Json(safe_metadata),
                    ),
                )
                ledger_id = int(cur.fetchone()[0])

        return LedgerResult(
            ledger_id=ledger_id,
            owner_id=normalized_owner_id,
            entry_type=normalized_entry_type,
            amount=amount,
            signed_amount=signed_amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reference_type=normalized_reference_type,
            reference_id=normalized_reference_id,
            idempotency_key=normalized_idempotency_key,
            actor_id=normalized_actor_id,
            actor_source=normalized_actor_source,
            reason_code=normalized_reason_code,
            reason_text=normalized_reason_text,
            applied=True,
            idempotent=False,
        )

    def _normalize_owner_id(self, owner_id: str) -> str:
        normalized = (owner_id or "").strip()
        if not normalized or not _OWNER_ID_RE.fullmatch(normalized):
            raise InvalidOwnerError("owner_id must be 1-80 chars using letters, digits, :, _, -, or .")
        return normalized

    def _normalize_owner_kind(self, owner_kind: str) -> str:
        normalized = (owner_kind or "").strip().upper()
        if normalized not in OWNER_KINDS:
            raise InvalidOwnerError("owner_kind must be one of LOCAL_PLAYER, LOCAL_ADMIN, SYSTEM")
        return normalized

    def _normalize_entry_type(self, entry_type: str) -> str:
        normalized = (entry_type or "").strip().upper()
        if normalized not in ENTRY_TYPES:
            raise InvalidAmountError("unsupported transaction type")
        return normalized

    def _normalize_required_text(self, value: str | None, field_name: str) -> str:
        normalized = self._normalize_optional_text(value)
        if normalized is None:
            raise InvalidAmountError(f"{field_name} is required")
        return normalized

    def _normalize_optional_text(self, value: str | None) -> str | None:
        normalized = (value or "").strip()
        return normalized or None

    def _sanitize_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            raise MetadataValidationError("metadata must be a JSON object")
        return self._sanitize_metadata_node(metadata, depth=0)

    def _sanitize_metadata_node(self, value: Any, *, depth: int) -> Any:
        if depth > _MAX_METADATA_DEPTH:
            raise MetadataValidationError("metadata nesting is too deep")

        if value is None or isinstance(value, bool) or isinstance(value, int):
            return value

        if isinstance(value, float):
            raise MetadataValidationError("metadata may not contain floats")

        if isinstance(value, str):
            return value.strip()[:_MAX_METADATA_STRING]

        if isinstance(value, list):
            if len(value) > _MAX_METADATA_LIST_ITEMS:
                raise MetadataValidationError("metadata list is too large")
            return [self._sanitize_metadata_node(item, depth=depth + 1) for item in value]

        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for raw_key, raw_value in value.items():
                key = str(raw_key).strip()
                if not key:
                    raise MetadataValidationError("metadata keys must be non-empty strings")
                if _SECRET_KEY_RE.search(key):
                    raise MetadataValidationError("metadata contains a disallowed sensitive key")
                out[key] = self._sanitize_metadata_node(raw_value, depth=depth + 1)
            return out

        raise MetadataValidationError("metadata contains an unsupported value type")

    def _parse_optional_datetime(self, value: str | None, field_name: str) -> datetime | None:
        raw = (value or "").strip()
        if not raw:
            return None
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise InvalidAmountError(f"{field_name} must be an ISO datetime") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _extract_original_ledger_id(self, *, reference_type: str, reference_id: str, metadata: Any) -> int | None:
        if isinstance(metadata, dict):
            value = metadata.get("original_ledger_id")
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                return None
        if reference_type in {"REVERSAL", "REFUND"}:
            try:
                return int(reference_id)
            except (TypeError, ValueError):
                return None
        return None

    def _extract_related_order_id(self, metadata: Any) -> int | None:
        if not isinstance(metadata, dict):
            return None
        value = metadata.get("order_id")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _display_entry_type(self, entry_type: str) -> str:
        names = {
            "CREDIT": "Credit",
            "DEBIT": "Debit",
            "ADMIN_ADJUSTMENT": "Admin Adjustment",
            "REVERSAL": "Reversal",
            "REFUND": "Refund",
            "HOLD": "Hold",
            "RELEASE": "Release",
        }
        return names.get(entry_type, entry_type)

    def _build_trace_context(
        self,
        *,
        entry_type: str,
        reference_type: str,
        metadata: Any,
        original_ledger_id: int | None,
        corrected_by: list[dict[str, Any]],
    ) -> str:
        parts: list[str] = []
        if reference_type.startswith("AUTO_TRADER_ORDER"):
            parts.append("Auto-Trader")
        elif reference_type.startswith("ADMIN_"):
            parts.append("Admin operation")

        order_id = self._extract_related_order_id(metadata)
        if order_id is not None:
            parts.append(f"order #{order_id}")

        if original_ledger_id is not None:
            parts.append(f"original ledger #{original_ledger_id}")

        if corrected_by:
            correction_labels = ", ".join(f"{c['entry_type']} #{c['ledger_id']}" for c in corrected_by)
            parts.append(f"corrected by {correction_labels}")

        if not parts and entry_type in {"REVERSAL", "REFUND"}:
            parts.append("Ledger correction")

        return " | ".join(parts)
