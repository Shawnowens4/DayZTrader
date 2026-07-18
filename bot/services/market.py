"""
Player Marketplace Service - P2P trading with escrow security
"""
import aiosqlite
import uuid
from enum import Enum
from datetime import datetime, timedelta
from typing import List, Optional
from db.init_db import DB_PATH

class TradeStatus(Enum):
    PENDING   = "pending"
    ESCROWED  = "escrowed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    DISPUTED  = "disputed"

class MarketService:
    def __init__(self, economy):
        self.economy = economy

    async def create_listing(self, seller_id: int, seller_name: str,
                              item_class: str, item_display: str,
                              quantity: int, asking_price: int,
                              duration_days: int = 7) -> dict:
        # Check active listing count
        count = await self._active_listing_count(seller_id)
        if count >= 5:
            return {"success": False, "message": "\u274c Max 5 active listings per player."}
        if asking_price < 100:
            return {"success": False, "message": "\u274c Minimum listing price is 100 credits."}

        listing_id = str(uuid.uuid4())[:12]
        expires = datetime.now() + timedelta(days=duration_days)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO market_listings
                (listing_id, seller_id, item_class, item_display, quantity,
                 asking_price, status, expires_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (listing_id, seller_id, item_class, item_display, quantity,
                 asking_price, TradeStatus.PENDING.value, expires.isoformat())
            )
            await db.commit()
        return {"success": True, "listing_id": listing_id, "expires": expires}

    async def buy_listing(self, buyer_id: int, buyer_name: str, listing_id: str) -> dict:
        listing = await self._get_listing(listing_id)
        if not listing:
            return {"success": False, "message": "\u274c Listing not found."}
        if listing["status"] != TradeStatus.PENDING.value:
            return {"success": False, "message": "\u274c Listing not available."}
        if listing["seller_id"] == buyer_id:
            return {"success": False, "message": "\u274c You cannot buy your own listing."}
        if datetime.fromisoformat(listing["expires_at"]) < datetime.now():
            return {"success": False, "message": "\u274c Listing has expired."}

        price = listing["asking_price"]
        balance = await self.economy.get_balance(buyer_id)
        if balance < price:
            return {"success": False, "message": f"\u274c Need {price:,} credits, you have {balance:,}."}

        # Lock credits into escrow
        await self.economy.update_balance(buyer_id, -price)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE market_listings SET status=?, buyer_id=?, escrow_held=? WHERE listing_id=?",
                (TradeStatus.ESCROWED.value, buyer_id, price, listing_id)
            )
            await db.commit()
        return {
            "success": True,
            "message": f"\u2705 Purchase locked! {price:,} credits held in escrow. Admin will deliver your item.",
            "listing": listing
        }

    async def confirm_delivery(self, admin_id: int, listing_id: str) -> dict:
        """Admin confirms item delivered in-game. Releases escrow to seller."""
        listing = await self._get_listing(listing_id)
        if not listing or listing["status"] != TradeStatus.ESCROWED.value:
            return {"success": False, "message": "\u274c Listing not in escrow state."}

        seller_id = listing["seller_id"]
        escrow = listing["escrow_held"]
        fee = int(escrow * 0.02)  # 2% market fee
        payout = escrow - fee

        await self.economy.update_balance(seller_id, payout)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE market_listings SET status=?, completed_at=? WHERE listing_id=?",
                (TradeStatus.DELIVERED.value, datetime.now().isoformat(), listing_id)
            )
            await db.execute(
                "INSERT INTO audit_log (action, actor_id, target_id, amount, notes, admin_id) VALUES (?,?,?,?,?,?)",
                ("market_delivery", listing["buyer_id"], seller_id, payout, f"Listing {listing_id}", admin_id)
            )
            await db.commit()
        return {"success": True, "payout": payout, "fee": fee}

    async def dispute_trade(self, user_id: int, listing_id: str, reason: str) -> dict:
        listing = await self._get_listing(listing_id)
        if not listing:
            return {"success": False, "message": "\u274c Listing not found."}
        if user_id not in [listing["seller_id"], listing["buyer_id"]]:
            return {"success": False, "message": "\u274c You are not party to this trade."}
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE market_listings SET status=?, dispute_reason=? WHERE listing_id=?",
                (TradeStatus.DISPUTED.value, reason, listing_id)
            )
            await db.commit()
        return {"success": True, "message": "\u26a0\ufe0f Dispute filed. Admin will review and release or refund escrow."}

    async def refund_escrow(self, admin_id: int, listing_id: str) -> dict:
        """Admin refunds escrow to buyer (dispute resolution or cancellation)."""
        listing = await self._get_listing(listing_id)
        if not listing or listing["escrow_held"] <= 0:
            return {"success": False, "message": "\u274c No escrow to refund."}
        buyer_id = listing["buyer_id"]
        await self.economy.update_balance(buyer_id, listing["escrow_held"])
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE market_listings SET status=?, escrow_held=0 WHERE listing_id=?",
                (TradeStatus.CANCELLED.value, listing_id)
            )
            await db.commit()
        return {"success": True, "refunded": listing["escrow_held"]}

    async def get_listings(self, status: str = "pending", seller_id: int = None) -> List[dict]:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            if seller_id:
                async with db.execute(
                    "SELECT * FROM market_listings WHERE seller_id=? ORDER BY created_at DESC",
                    (seller_id,)
                ) as cur:
                    rows = await cur.fetchall()
            else:
                async with db.execute(
                    "SELECT * FROM market_listings WHERE status=? ORDER BY created_at DESC",
                    (status,)
                ) as cur:
                    rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def _get_listing(self, listing_id: str) -> Optional[dict]:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM market_listings WHERE listing_id=?", (listing_id,)) as cur:
                row = await cur.fetchone()
        return dict(row) if row else None

    async def _active_listing_count(self, seller_id: int) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM market_listings WHERE seller_id=? AND status IN ('pending','escrowed')",
                (seller_id,)
            ) as cur:
                row = await cur.fetchone()
        return row[0] if row else 0
