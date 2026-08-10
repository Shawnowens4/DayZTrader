"""Wallet and immutable virtual-credit ledger service.

This service keeps the existing wallet_account / wallet_ledger table names for
compatibility, but treats the legacy discord_user_id columns as generic immutable
owner identifiers during the local-admin foundation stage.
"""

from __future__ import annotations

import json
import os
import re
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

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT signed_amount, reference_type, reference_id
                    FROM wallet_ledger
                    WHERE id = %s AND discord_user_id = %s
                    LIMIT 1
                    """,
                    (original_ledger_id, normalized_owner_id),
                )
                row = cur.fetchone()
                if not row:
                    raise InvalidOwnerError("original ledger entry not found for owner")

        signed_amount = -int(row[0])
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
            idempotency_key=idempotency_key,
            metadata={
                **(metadata or {}),
                "original_ledger_id": original_ledger_id,
                "original_reference_type": row[1],
                "original_reference_id": row[2],
            },
        )

    def list_ledger_entries(self, discord_user_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)
        normalized_owner_id = self._normalize_owner_id(discord_user_id)

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
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (normalized_owner_id, safe_limit, safe_offset),
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
            )

        return out

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
