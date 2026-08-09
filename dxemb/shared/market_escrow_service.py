"""P2P marketplace listing and escrow foundation service.

This service intentionally excludes any server-spawn workflow.
Delivery mode is constrained to physical player-to-player transfer.
"""

from __future__ import annotations

import os
from typing import Any

from psycopg2.extras import Json

from shared.wallet_ledger_service import WalletLedgerService


DEFAULT_DATABASE_URL = "postgresql://dxemb:dxemb@db:5432/dxemb"


class EscrowStateError(Exception):
    """Raised for invalid escrow/listing state transitions."""


class MarketEscrowService:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.wallet = WalletLedgerService(database_url=self.database_url)

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.database_url, connect_timeout=5)

    def ensure_player(self, discord_user_id: str, username: str | None = None) -> None:
        self.wallet.ensure_player(discord_user_id, username=username)

    def create_listing(
        self,
        *,
        seller_discord_id: str,
        listing_type: str,
        item_classname: str | None,
        vehicle_label: str | None,
        vehicle_running: bool,
        quantity: int,
        price: int,
        created_by: str,
        delivery_mode: str = "P2P_PHYSICAL",
        notes: str | None = None,
    ) -> dict[str, Any]:
        if delivery_mode != "P2P_PHYSICAL":
            raise ValueError("P2P listings must use delivery mode P2P_PHYSICAL")

        if listing_type == "VEHICLE" and not vehicle_running:
            raise ValueError("non-running vehicles cannot be listed")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO player_listing (
                        seller_discord_id,
                        listing_type,
                        item_classname,
                        vehicle_label,
                        vehicle_running,
                        quantity,
                        price,
                        delivery_mode,
                        status,
                        created_by,
                        updated_by,
                        notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE', %s, %s, %s)
                    RETURNING id, status, delivery_mode
                    """,
                    (
                        seller_discord_id,
                        listing_type,
                        item_classname,
                        vehicle_label,
                        vehicle_running,
                        quantity,
                        price,
                        delivery_mode,
                        created_by,
                        created_by,
                        notes,
                    ),
                )
                row = cur.fetchone()

        return {
            "listing_id": int(row[0]),
            "status": row[1],
            "delivery_mode": row[2],
        }

    def hold_escrow(self, *, listing_id: int, buyer_discord_id: str, actor_discord_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT seller_discord_id, price, status
                    FROM player_listing
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (listing_id,),
                )
                listing = cur.fetchone()
                if not listing:
                    raise EscrowStateError("listing not found")

                seller_discord_id, price, status = listing
                if status != "ACTIVE":
                    raise EscrowStateError("listing is not active")
                if seller_discord_id == buyer_discord_id:
                    raise EscrowStateError("buyer cannot be seller")

                hold_reference = f"P2P_HOLD:{listing_id}:{buyer_discord_id}"
                self.wallet.debit(
                    discord_user_id=buyer_discord_id,
                    amount=int(price),
                    reference_type="P2P_ESCROW_HOLD",
                    reference_id=hold_reference,
                    reason_code="P2P_ESCROW_HOLD",
                    reason_text=f"Escrow hold for listing {listing_id}",
                    actor_discord_id=actor_discord_id,
                    metadata={"listing_id": listing_id},
                )

                cur.execute(
                    """
                    UPDATE player_listing
                    SET status = 'RESERVED',
                        buyer_discord_id = %s,
                        updated_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (buyer_discord_id, actor_discord_id, listing_id),
                )

                cur.execute(
                    """
                    INSERT INTO market_escrow (
                        listing_id,
                        seller_discord_id,
                        buyer_discord_id,
                        amount,
                        hold_reference_id,
                        status,
                        created_by,
                        updated_by
                    )
                    VALUES (%s, %s, %s, %s, %s, 'HELD', %s, %s)
                    RETURNING id
                    """,
                    (
                        listing_id,
                        seller_discord_id,
                        buyer_discord_id,
                        int(price),
                        hold_reference,
                        actor_discord_id,
                        actor_discord_id,
                    ),
                )
                escrow_id = int(cur.fetchone()[0])

                self._insert_event(
                    cur,
                    escrow_id=escrow_id,
                    event_type="HELD",
                    actor_discord_id=actor_discord_id,
                    details={"listing_id": listing_id, "amount": int(price)},
                )

        return {"escrow_id": escrow_id, "status": "HELD"}

    def confirm_pickup(self, *, escrow_id: int, buyer_discord_id: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE market_escrow
                    SET pickup_confirmed_by_buyer = TRUE,
                        pickup_confirmed_at = NOW(),
                        updated_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                      AND buyer_discord_id = %s
                    """,
                    (buyer_discord_id, escrow_id, buyer_discord_id),
                )
                if cur.rowcount == 0:
                    raise EscrowStateError("pickup confirmation failed")

                self._insert_event(
                    cur,
                    escrow_id=escrow_id,
                    event_type="PICKUP_CONFIRMED",
                    actor_discord_id=buyer_discord_id,
                    details={},
                )

    def release_escrow(self, *, escrow_id: int, actor_discord_id: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT listing_id, seller_discord_id, amount, status, pickup_confirmed_by_buyer
                    FROM market_escrow
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (escrow_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise EscrowStateError("escrow not found")

                listing_id, seller_discord_id, amount, status, pickup_confirmed = row
                if status != "HELD":
                    raise EscrowStateError("escrow is not held")
                if not pickup_confirmed:
                    raise EscrowStateError("pickup confirmation is required before release")

                release_reference = f"P2P_RELEASE:{escrow_id}"
                self.wallet.credit(
                    discord_user_id=seller_discord_id,
                    amount=int(amount),
                    reference_type="P2P_ESCROW_RELEASE",
                    reference_id=release_reference,
                    reason_code="P2P_ESCROW_RELEASE",
                    reason_text=f"Escrow release for listing {listing_id}",
                    actor_discord_id=actor_discord_id,
                    metadata={"escrow_id": escrow_id, "listing_id": listing_id},
                )

                cur.execute(
                    """
                    UPDATE market_escrow
                    SET status = 'RELEASED',
                        release_reference_id = %s,
                        updated_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (release_reference, actor_discord_id, escrow_id),
                )
                cur.execute(
                    """
                    UPDATE player_listing
                    SET status = 'COMPLETED',
                        updated_by = %s,
                        updated_at = NOW(),
                        closed_at = NOW()
                    WHERE id = %s
                    """,
                    (actor_discord_id, listing_id),
                )

                self._insert_event(
                    cur,
                    escrow_id=escrow_id,
                    event_type="RELEASED",
                    actor_discord_id=actor_discord_id,
                    details={"listing_id": listing_id},
                )

    def raise_dispute(self, *, escrow_id: int, actor_discord_id: str, reason: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE market_escrow
                    SET status = 'DISPUTED',
                        dispute_reason = %s,
                        updated_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                      AND status = 'HELD'
                    """,
                    (reason, actor_discord_id, escrow_id),
                )
                if cur.rowcount == 0:
                    raise EscrowStateError("only HELD escrow can be disputed")

                cur.execute(
                    """
                    UPDATE player_listing
                    SET status = 'DISPUTED',
                        updated_by = %s,
                        updated_at = NOW()
                    WHERE id = (SELECT listing_id FROM market_escrow WHERE id = %s)
                    """,
                    (actor_discord_id, escrow_id),
                )

                self._insert_event(
                    cur,
                    escrow_id=escrow_id,
                    event_type="DISPUTED",
                    actor_discord_id=actor_discord_id,
                    details={"reason": reason},
                )

    def refund_disputed(self, *, escrow_id: int, actor_discord_id: str, reason: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT listing_id, buyer_discord_id, amount, status
                    FROM market_escrow
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (escrow_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise EscrowStateError("escrow not found")

                listing_id, buyer_discord_id, amount, status = row
                if status not in {"DISPUTED", "HELD"}:
                    raise EscrowStateError("only disputed/held escrow can be refunded")

                refund_reference = f"P2P_REFUND:{escrow_id}"
                self.wallet.credit(
                    discord_user_id=buyer_discord_id,
                    amount=int(amount),
                    reference_type="P2P_ESCROW_REFUND",
                    reference_id=refund_reference,
                    reason_code="P2P_ESCROW_REFUND",
                    reason_text=reason,
                    actor_discord_id=actor_discord_id,
                    metadata={"escrow_id": escrow_id, "listing_id": listing_id},
                )

                cur.execute(
                    """
                    UPDATE market_escrow
                    SET status = 'REFUNDED',
                        refund_reference_id = %s,
                        updated_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (refund_reference, actor_discord_id, escrow_id),
                )
                cur.execute(
                    """
                    UPDATE player_listing
                    SET status = 'CANCELLED',
                        updated_by = %s,
                        updated_at = NOW(),
                        closed_at = NOW()
                    WHERE id = %s
                    """,
                    (actor_discord_id, listing_id),
                )

                self._insert_event(
                    cur,
                    escrow_id=escrow_id,
                    event_type="REFUNDED",
                    actor_discord_id=actor_discord_id,
                    details={"reason": reason},
                )

    def get_escrow_status(self, escrow_id: int) -> str:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM market_escrow WHERE id = %s", (escrow_id,))
                row = cur.fetchone()
                if not row:
                    raise EscrowStateError("escrow not found")
                return row[0]

    def get_listing_status(self, listing_id: int) -> str:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM player_listing WHERE id = %s", (listing_id,))
                row = cur.fetchone()
                if not row:
                    raise EscrowStateError("listing not found")
                return row[0]

    def _insert_event(
        self,
        cur,
        *,
        escrow_id: int,
        event_type: str,
        actor_discord_id: str | None,
        details: dict[str, Any],
    ) -> None:
        cur.execute(
            """
            INSERT INTO market_escrow_event (escrow_id, event_type, actor_discord_id, details)
            VALUES (%s, %s, %s, %s)
            """,
            (escrow_id, event_type, actor_discord_id, Json(details)),
        )
