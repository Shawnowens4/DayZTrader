"""Auto-Trader product and order service.

This module is intentionally isolated from Player Market + Escrow services.
No P2P table or workflow is used by this service.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from psycopg2.extras import Json

from shared.wallet_ledger_service import WalletLedgerService


DEFAULT_DATABASE_URL = "postgresql://dxemb:dxemb@db:5432/dxemb"


class AutoTraderOrderError(Exception):
    """Base exception for auto-trader order service errors."""


class ProductNotAllowedError(AutoTraderOrderError):
    """Raised when requested product or reference is not allow-listed."""


class OrderStateError(AutoTraderOrderError):
    """Raised for invalid state transitions."""


@dataclass(frozen=True)
class OrderCreateResult:
    order_id: int
    order_reference: str
    state: str
    applied: bool
    idempotent: bool


class AutoTraderOrderService:
    ALLOWED_TRANSITIONS = {
        "draft": {"pending_payment", "cancelled"},
        "pending_payment": {"paid", "failed", "cancelled"},
        "paid": {"queued_for_delivery", "refunded", "failed", "cancelled"},
        "queued_for_delivery": {"awaiting_restart_window", "failed", "cancelled"},
        "awaiting_restart_window": {"delivery_written", "failed", "cancelled"},
        "delivery_written": {"delivered", "failed", "refunded"},
        "failed": {"refunded"},
        "cancelled": {"refunded"},
        "delivered": set(),
        "refunded": set(),
    }

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.wallet = WalletLedgerService(database_url=self.database_url)

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.database_url, connect_timeout=5)

    def ensure_player(self, discord_user_id: str, username: str | None = None) -> None:
        self.wallet.ensure_player(discord_user_id, username=username)

    def create_product(
        self,
        *,
        product_code: str,
        product_type: str,
        display_name: str,
        price: int,
        created_by: str,
        item_classname: str | None = None,
        kit_code: str | None = None,
        vehicle_code: str | None = None,
        is_enabled: bool = True,
        is_sellable: bool = True,
        stock_limit: int | None = None,
        stock_remaining: int | None = None,
        console_safe: bool = True,
        console_metadata: dict[str, Any] | None = None,
    ) -> int:
        ptype = product_type.strip().upper()
        if ptype not in {"ITEM", "KIT", "VEHICLE"}:
            raise ProductNotAllowedError("product_type must be ITEM, KIT, or VEHICLE")

        if ptype == "ITEM" and not item_classname:
            raise ProductNotAllowedError("ITEM product requires item_classname")
        if ptype == "KIT" and not kit_code:
            raise ProductNotAllowedError("KIT product requires kit_code")
        if ptype == "VEHICLE" and not vehicle_code:
            raise ProductNotAllowedError("VEHICLE product requires vehicle_code")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auto_trader_product (
                        product_code,
                        product_type,
                        item_classname,
                        kit_code,
                        vehicle_code,
                        display_name,
                        price,
                        is_enabled,
                        is_sellable,
                        stock_limit,
                        stock_remaining,
                        console_safe,
                        console_metadata,
                        created_by,
                        updated_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        product_code,
                        ptype,
                        item_classname,
                        kit_code,
                        vehicle_code,
                        display_name,
                        int(price),
                        bool(is_enabled),
                        bool(is_sellable),
                        stock_limit,
                        stock_remaining,
                        bool(console_safe),
                        Json(console_metadata or {}),
                        created_by,
                        created_by,
                    ),
                )
                return int(cur.fetchone()[0])

    def create_order(
        self,
        *,
        order_reference: str,
        buyer_discord_id: str,
        product_id: int,
        quantity: int,
        created_by: str,
        initial_state: str = "draft",
    ) -> OrderCreateResult:
        if quantity <= 0:
            raise ProductNotAllowedError("quantity must be > 0")

        self.ensure_player(buyer_discord_id)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, state
                    FROM trader_order
                    WHERE order_reference = %s
                    """,
                    (order_reference,),
                )
                existing = cur.fetchone()
                if existing:
                    return OrderCreateResult(
                        order_id=int(existing[0]),
                        order_reference=order_reference,
                        state=existing[1],
                        applied=False,
                        idempotent=True,
                    )

                product = self._fetch_allowed_product(cur, product_id=product_id)
                unit_price = int(product["price"])
                total_price = unit_price * quantity

                cur.execute(
                    """
                    INSERT INTO trader_order (
                        order_reference,
                        buyer_discord_id,
                        product_id,
                        quantity,
                        unit_price,
                        total_price,
                        state,
                        created_by,
                        updated_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        order_reference,
                        buyer_discord_id,
                        product_id,
                        quantity,
                        unit_price,
                        total_price,
                        initial_state,
                        created_by,
                        created_by,
                    ),
                )
                order_id = int(cur.fetchone()[0])

                self._insert_event(
                    cur,
                    trader_order_id=order_id,
                    event_type="ORDER_CREATED",
                    from_state=None,
                    to_state=initial_state,
                    actor_discord_id=created_by,
                    reason_code="ORDER_CREATE",
                    reason_text="Auto-Trader order created",
                    reference_id=f"CREATE:{order_reference}",
                    details={"product_id": product_id, "quantity": quantity},
                )

                return OrderCreateResult(
                    order_id=order_id,
                    order_reference=order_reference,
                    state=initial_state,
                    applied=True,
                    idempotent=False,
                )

    def transition_order(
        self,
        *,
        order_id: int,
        to_state: str,
        actor_discord_id: str,
        reason_code: str,
        reason_text: str | None = None,
        reference_id: str,
        details: dict[str, Any] | None = None,
    ) -> str:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT state
                    FROM trader_order
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (order_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise OrderStateError("order not found")

                from_state = row[0]
                if from_state == to_state:
                    return from_state

                allowed = self.ALLOWED_TRANSITIONS.get(from_state, set())
                if to_state not in allowed:
                    raise OrderStateError(f"invalid transition: {from_state} -> {to_state}")

                closed_at_sql = "NOW()" if to_state in {"delivered", "failed", "refunded", "cancelled"} else "NULL"
                cur.execute(
                    f"""
                    UPDATE trader_order
                    SET state = %s,
                        updated_by = %s,
                        updated_at = NOW(),
                        closed_at = {closed_at_sql}
                    WHERE id = %s
                    """,
                    (to_state, actor_discord_id, order_id),
                )

                self._insert_event(
                    cur,
                    trader_order_id=order_id,
                    event_type="ORDER_STATE_CHANGED",
                    from_state=from_state,
                    to_state=to_state,
                    actor_discord_id=actor_discord_id,
                    reason_code=reason_code,
                    reason_text=reason_text,
                    reference_id=reference_id,
                    details=details or {},
                )

                return to_state

    def get_order(self, order_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, order_reference, buyer_discord_id, product_id, quantity,
                           unit_price, total_price, state, payment_reference_id,
                           refund_reference_id, failure_reason, cancellation_reason,
                           delivery_metadata, created_by, updated_by, created_at,
                           updated_at, closed_at
                    FROM trader_order
                    WHERE id = %s
                    """,
                    (order_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise OrderStateError("order not found")

        return {
            "id": int(row[0]),
            "order_reference": row[1],
            "buyer_discord_id": row[2],
            "product_id": int(row[3]),
            "quantity": int(row[4]),
            "unit_price": int(row[5]),
            "total_price": int(row[6]),
            "state": row[7],
            "payment_reference_id": row[8],
            "refund_reference_id": row[9],
            "failure_reason": row[10],
            "cancellation_reason": row[11],
            "delivery_metadata": row[12],
            "created_by": row[13],
            "updated_by": row[14],
            "created_at": row[15],
            "updated_at": row[16],
            "closed_at": row[17],
        }

    def list_order_events(self, order_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_type, from_state, to_state, actor_discord_id,
                           reason_code, reason_text, reference_id, details, created_at
                    FROM trader_order_event
                    WHERE trader_order_id = %s
                    ORDER BY created_at ASC, id ASC
                    """,
                    (order_id,),
                )
                rows = cur.fetchall()

        out = []
        for row in rows:
            out.append(
                {
                    "id": int(row[0]),
                    "event_type": row[1],
                    "from_state": row[2],
                    "to_state": row[3],
                    "actor_discord_id": row[4],
                    "reason_code": row[5],
                    "reason_text": row[6],
                    "reference_id": row[7],
                    "details": row[8],
                    "created_at": row[9],
                }
            )
        return out

    def list_products(self, *, enabled_only: bool = True, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as conn:
            with conn.cursor() as cur:
                if enabled_only:
                    cur.execute(
                        """
                        SELECT id, product_code, product_type, item_classname, kit_code,
                               vehicle_code, display_name, price, is_enabled,
                               is_sellable, stock_limit, stock_remaining,
                               console_safe, console_metadata, created_at, updated_at
                        FROM auto_trader_product
                        WHERE is_enabled = TRUE AND is_sellable = TRUE
                        ORDER BY id ASC
                        LIMIT %s
                        """,
                        (safe_limit,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, product_code, product_type, item_classname, kit_code,
                               vehicle_code, display_name, price, is_enabled,
                               is_sellable, stock_limit, stock_remaining,
                               console_safe, console_metadata, created_at, updated_at
                        FROM auto_trader_product
                        ORDER BY id ASC
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
                    "product_code": row[1],
                    "product_type": row[2],
                    "item_classname": row[3],
                    "kit_code": row[4],
                    "vehicle_code": row[5],
                    "display_name": row[6],
                    "price": int(row[7]),
                    "is_enabled": bool(row[8]),
                    "is_sellable": bool(row[9]),
                    "stock_limit": row[10],
                    "stock_remaining": row[11],
                    "console_safe": bool(row[12]),
                    "console_metadata": row[13],
                    "created_at": row[14],
                    "updated_at": row[15],
                }
            )
        return out

    def _fetch_allowed_product(self, cur, *, product_id: int) -> dict[str, Any]:
        cur.execute(
            """
            SELECT id, product_type, price, is_enabled, is_sellable, console_safe
            FROM auto_trader_product
            WHERE id = %s
            """,
            (product_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ProductNotAllowedError("product not found")

        if not row[3] or not row[4]:
            raise ProductNotAllowedError("product is disabled or not sellable")
        if not row[5]:
            raise ProductNotAllowedError("product is not marked console-safe")

        return {
            "id": int(row[0]),
            "product_type": row[1],
            "price": int(row[2]),
        }

    def _insert_event(
        self,
        cur,
        *,
        trader_order_id: int,
        event_type: str,
        from_state: str | None,
        to_state: str | None,
        actor_discord_id: str | None,
        reason_code: str | None,
        reason_text: str | None,
        reference_id: str,
        details: dict[str, Any],
    ) -> None:
        cur.execute(
            """
            INSERT INTO trader_order_event (
                trader_order_id,
                event_type,
                from_state,
                to_state,
                actor_discord_id,
                reason_code,
                reason_text,
                reference_id,
                details
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (trader_order_id, reference_id) DO NOTHING
            """,
            (
                trader_order_id,
                event_type,
                from_state,
                to_state,
                actor_discord_id,
                reason_code,
                reason_text,
                reference_id,
                Json(details),
            ),
        )
