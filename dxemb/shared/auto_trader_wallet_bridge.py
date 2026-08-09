"""Atomic wallet-to-order bridge for Auto-Trader.

Creates paid trader orders with a single atomic wallet debit operation.
This module does not call Player Market + Escrow services.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from psycopg2.extras import Json

from shared.auto_trader_order_service import OrderStateError
from shared.auto_trader_order_service import ProductNotAllowedError


DEFAULT_DATABASE_URL = "postgresql://dxemb:dxemb@db:5432/dxemb"


class AutoTraderBridgeError(Exception):
    """Base exception for bridge operations."""


class AutoTraderBridgeInsufficientFunds(AutoTraderBridgeError):
    """Raised when buyer balance is insufficient."""


@dataclass(frozen=True)
class WalletOrderBridgeResult:
    order_id: int
    order_reference: str
    state: str
    total_price: int
    debited: bool
    idempotent: bool


class AutoTraderWalletBridge:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.database_url, connect_timeout=5)

    def create_paid_order_with_wallet_debit(
        self,
        *,
        order_reference: str,
        debit_reference_id: str,
        buyer_discord_id: str,
        product_id: int,
        quantity: int,
        actor_discord_id: str,
        reason_text: str | None = None,
    ) -> WalletOrderBridgeResult:
        if quantity <= 0:
            raise ProductNotAllowedError("quantity must be > 0")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, state, total_price
                    FROM trader_order
                    WHERE order_reference = %s
                    FOR UPDATE
                    """,
                    (order_reference,),
                )
                existing = cur.fetchone()
                if existing:
                    return WalletOrderBridgeResult(
                        order_id=int(existing[0]),
                        order_reference=order_reference,
                        state=existing[1],
                        total_price=int(existing[2]),
                        debited=False,
                        idempotent=True,
                    )

                product = self._fetch_allowed_product(cur, product_id=product_id)
                unit_price = int(product["price"])
                total_price = unit_price * quantity

                cur.execute(
                    """
                    INSERT INTO player (discord_id)
                    VALUES (%s)
                    ON CONFLICT (discord_id) DO NOTHING
                    """,
                    (buyer_discord_id,),
                )

                cur.execute(
                    """
                    INSERT INTO wallet_account (discord_user_id, balance)
                    VALUES (%s, 0)
                    ON CONFLICT (discord_user_id) DO NOTHING
                    """,
                    (buyer_discord_id,),
                )

                cur.execute(
                    """
                    SELECT balance
                    FROM wallet_account
                    WHERE discord_user_id = %s
                    FOR UPDATE
                    """,
                    (buyer_discord_id,),
                )
                balance_before = int(cur.fetchone()[0])
                balance_after = balance_before - total_price
                if balance_after < 0:
                    raise AutoTraderBridgeInsufficientFunds(
                        f"insufficient funds for {buyer_discord_id}: {balance_before} < {total_price}"
                    )

                cur.execute(
                    """
                    UPDATE wallet_account
                    SET balance = %s,
                        updated_at = NOW()
                    WHERE discord_user_id = %s
                    """,
                    (balance_after, buyer_discord_id),
                )

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
                        payment_reference_id,
                        created_by,
                        updated_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'paid', %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        order_reference,
                        buyer_discord_id,
                        product_id,
                        quantity,
                        unit_price,
                        total_price,
                        debit_reference_id,
                        actor_discord_id,
                        actor_discord_id,
                    ),
                )
                order_id = int(cur.fetchone()[0])

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
                    VALUES (%s, 'DEBIT', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        buyer_discord_id,
                        total_price,
                        -total_price,
                        balance_before,
                        balance_after,
                        "AUTO_TRADER_ORDER_DEBIT",
                        debit_reference_id,
                        "AUTO_TRADER_ORDER_DEBIT",
                        reason_text or f"Auto-Trader purchase debit for order {order_reference}",
                        actor_discord_id,
                        Json({"order_id": order_id, "product_id": product_id}),
                    ),
                )

                self._insert_order_event(
                    cur,
                    order_id=order_id,
                    event_type="ORDER_CREATED",
                    from_state=None,
                    to_state="paid",
                    actor_discord_id=actor_discord_id,
                    reason_code="ORDER_CREATE",
                    reason_text="Auto-Trader paid order created via wallet bridge",
                    reference_id=f"CREATE:{order_reference}",
                    details={"product_id": product_id, "quantity": quantity},
                )
                self._insert_order_event(
                    cur,
                    order_id=order_id,
                    event_type="WALLET_DEBIT_APPLIED",
                    from_state="paid",
                    to_state="paid",
                    actor_discord_id=actor_discord_id,
                    reason_code="ORDER_DEBIT",
                    reason_text=reason_text,
                    reference_id=debit_reference_id,
                    details={"total_price": total_price},
                )

                return WalletOrderBridgeResult(
                    order_id=order_id,
                    order_reference=order_reference,
                    state="paid",
                    total_price=total_price,
                    debited=True,
                    idempotent=False,
                )

    def refund_order(
        self,
        *,
        order_id: int,
        refund_reference_id: str,
        actor_discord_id: str,
        reason_text: str,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT buyer_discord_id, total_price, state, refund_reference_id
                    FROM trader_order
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (order_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise OrderStateError("order not found")

                buyer_discord_id, total_price, state, existing_refund_ref = row
                total_price = int(total_price)
                if state not in {"failed", "cancelled", "refunded"}:
                    raise OrderStateError("refund requires order state failed or cancelled")

                if state == "refunded" or existing_refund_ref == refund_reference_id:
                    return {
                        "order_id": order_id,
                        "state": "refunded",
                        "refunded": False,
                        "idempotent": True,
                    }

                cur.execute(
                    """
                    INSERT INTO wallet_account (discord_user_id, balance)
                    VALUES (%s, 0)
                    ON CONFLICT (discord_user_id) DO NOTHING
                    """,
                    (buyer_discord_id,),
                )
                cur.execute(
                    """
                    SELECT balance
                    FROM wallet_account
                    WHERE discord_user_id = %s
                    FOR UPDATE
                    """,
                    (buyer_discord_id,),
                )
                balance_before = int(cur.fetchone()[0])
                balance_after = balance_before + total_price

                cur.execute(
                    """
                    UPDATE wallet_account
                    SET balance = %s,
                        updated_at = NOW()
                    WHERE discord_user_id = %s
                    """,
                    (balance_after, buyer_discord_id),
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
                    VALUES (%s, 'REFUND', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (discord_user_id, reference_type, reference_id) DO NOTHING
                    """,
                    (
                        buyer_discord_id,
                        total_price,
                        total_price,
                        balance_before,
                        balance_after,
                        "AUTO_TRADER_ORDER_REFUND",
                        refund_reference_id,
                        "AUTO_TRADER_ORDER_REFUND",
                        reason_text,
                        actor_discord_id,
                        Json({"order_id": order_id}),
                    ),
                )

                cur.execute(
                    """
                    UPDATE trader_order
                    SET state = 'refunded',
                        refund_reference_id = %s,
                        updated_by = %s,
                        updated_at = NOW(),
                        closed_at = NOW()
                    WHERE id = %s
                    """,
                    (refund_reference_id, actor_discord_id, order_id),
                )

                self._insert_order_event(
                    cur,
                    order_id=order_id,
                    event_type="ORDER_REFUNDED",
                    from_state=state,
                    to_state="refunded",
                    actor_discord_id=actor_discord_id,
                    reason_code="ORDER_REFUND",
                    reason_text=reason_text,
                    reference_id=refund_reference_id,
                    details={"refund_amount": total_price},
                )

                return {
                    "order_id": order_id,
                    "state": "refunded",
                    "refunded": True,
                    "idempotent": False,
                }

    def _fetch_allowed_product(self, cur, *, product_id: int) -> dict[str, Any]:
        cur.execute(
            """
            SELECT id, price, is_enabled, is_sellable, console_safe
            FROM auto_trader_product
            WHERE id = %s
            """,
            (product_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ProductNotAllowedError("product not found")
        if not row[2] or not row[3]:
            raise ProductNotAllowedError("product is disabled or not sellable")
        if not row[4]:
            raise ProductNotAllowedError("product is not marked console-safe")

        return {"id": int(row[0]), "price": int(row[1])}

    def _insert_order_event(
        self,
        cur,
        *,
        order_id: int,
        event_type: str,
        from_state: str | None,
        to_state: str | None,
        actor_discord_id: str,
        reason_code: str,
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
                order_id,
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
