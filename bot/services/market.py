"""
Player Marketplace Service - P2P trading with escrow security
"""

import aiosqlite
import uuid
import os
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", "db/dayz_trader.db")

class TradeStatus(Enum):
    PENDING   = "pending"    # Listed, waiting for buyer
    ESCROWED  = "escrowed"   # Buyer paid, awaiting admin confirm of delivery
    DELIVERED = "delivered"  # Admin confirmed item delivered in-game
    CANCELLED = "cancelled"  # Listing cancelled by seller
    EXPIRED   = "expired"    # Listing expired without a buyer
    DISPUTED  = "disputed"   # Buyer/seller raised a dispute

@dataclass
class MarketListing:
    listing_id: str
    seller_id: int
    item_class: str
    item_display: str
    quantity: int
    asking_price: int
    status: TradeStatus
    buyer_id: Optional[int] = None
    escrow_held: int = 0
    dispute_reason: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

class MarketService:
    def __init__(self, db_path: str = DB_PATH, config: dict = None):
        self.db_path = db_path
        self.config = config or {}
        self.listing_fee_pct = self.config.get('listing_fee_pct', 5)
        self.max_listings = self.config.get('max_listings_per_player', 5)
        self.expiry_days = self.config.get('listing_expiry_days', 7)
        self.min_price = self.config.get('min_price', 100)
        self.max_price = self.config.get('max_price', 1000000)

    async def create_listing(
        self,
        seller_id: int,
        item_class: str,
        item_display: str,
        quantity: int,
        asking_price: int,
        economy_service
    ) -> Dict:
        # Validate price
        if asking_price < self.min_price:
            return {'success': False, 'message': f'Minimum price is {self.min_price} credits'}
        if asking_price > self.max_price:
            return {'success': False, 'message': f'Maximum price is {self.max_price:,} credits'}

        # Check active listings count
        count = await self._count_active_listings(seller_id)
        if count >= self.max_listings:
            return {'success': False, 'message': f'Max {self.max_listings} active listings allowed'}

        # Deduct listing fee
        listing_fee = int(asking_price * self.listing_fee_pct / 100)
        balance = await economy_service.get_balance(seller_id)
        if balance < listing_fee:
            return {'success': False, 'message': f'Need {listing_fee} credits for listing fee ({self.listing_fee_pct}%)'}

        await economy_service.update_balance(seller_id, -listing_fee, 'Market listing fee')

        listing_id = str(uuid.uuid4())[:10]
        expires_at = datetime.now() + timedelta(days=self.expiry_days)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO market_listings
                   (listing_id, seller_id, item_class, item_display, quantity, asking_price, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (listing_id, seller_id, item_class, item_display, quantity, asking_price, expires_at.isoformat())
            )
            await db.execute(
                "INSERT INTO trade_audit_log (trade_type, actor_id, item_ref, amount, notes) VALUES (?, ?, ?, ?, ?)",
                ('listing_created', seller_id, item_class, asking_price, f'Listing {listing_id} created')
            )
            await db.commit()

        return {
            'success': True,
            'listing_id': listing_id,
            'listing_fee': listing_fee,
            'message': f'Listed {item_display} x{quantity} for {asking_price:,} credits! (Fee: {listing_fee})'
        }

    async def buy_listing(self, buyer_id: int, listing_id: str, economy_service) -> Dict:
        listing = await self.get_listing(listing_id)
        if not listing:
            return {'success': False, 'message': 'Listing not found'}
        if listing.status != TradeStatus.PENDING:
            return {'success': False, 'message': f'Listing is {listing.status.value}'}
        if listing.seller_id == buyer_id:
            return {'success': False, 'message': 'You cannot buy your own listing!'}
        if listing.expires_at and datetime.now() > listing.expires_at:
            await self._expire_listing(listing_id)
            return {'success': False, 'message': 'This listing has expired'}

        # Check buyer balance
        balance = await economy_service.get_balance(buyer_id)
        if balance < listing.asking_price:
            return {'success': False, 'message': f'Need {listing.asking_price:,} credits, you have {balance:,}'}

        # Deduct from buyer and hold in escrow
        await economy_service.update_balance(buyer_id, -listing.asking_price, f'Escrow: {listing.item_display}')

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE market_listings
                   SET status='escrowed', buyer_id=?, escrow_held=?, updated_at=CURRENT_TIMESTAMP
                   WHERE listing_id=?""",
                (buyer_id, listing.asking_price, listing_id)
            )
            await db.execute(
                "INSERT INTO trade_audit_log (trade_type, actor_id, target_id, item_ref, amount, notes) VALUES (?, ?, ?, ?, ?, ?)",
                ('escrow_held', buyer_id, listing.seller_id, listing.item_class, listing.asking_price, f'Listing {listing_id}')
            )
            await db.commit()

        return {
            'success': True,
            'listing': listing,
            'message': f'Purchase pending! {listing.asking_price:,} credits held in escrow. An admin will confirm delivery in-game.'
        }

    async def confirm_delivery(
        self,
        admin_id: int,
        listing_id: str,
        economy_service
    ) -> Dict:
        listing = await self.get_listing(listing_id)
        if not listing:
            return {'success': False, 'message': 'Listing not found'}
        if listing.status != TradeStatus.ESCROWED:
            return {'success': False, 'message': f'Listing is {listing.status.value}, not escrowed'}

        # Release escrow to seller
        await economy_service.update_balance(
            listing.seller_id, listing.escrow_held,
            f'Market sale: {listing.item_display} (confirmed by admin {admin_id})'
        )

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE market_listings SET status='delivered', updated_at=CURRENT_TIMESTAMP WHERE listing_id=?",
                (listing_id,)
            )
            await db.execute(
                "INSERT INTO trade_audit_log (trade_type, actor_id, target_id, item_ref, amount, notes, admin_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ('delivery_confirmed', listing.seller_id, listing.buyer_id, listing.item_class,
                 listing.escrow_held, f'Listing {listing_id} delivered', admin_id)
            )
            await db.commit()

        return {
            'success': True,
            'message': f'Delivery confirmed! {listing.escrow_held:,} credits released to seller.'
        }

    async def dispute_trade(self, user_id: int, listing_id: str, reason: str) -> Dict:
        listing = await self.get_listing(listing_id)
        if not listing:
            return {'success': False, 'message': 'Listing not found'}
        if listing.status != TradeStatus.ESCROWED:
            return {'success': False, 'message': 'Can only dispute escrowed trades'}
        if user_id not in (listing.buyer_id, listing.seller_id):
            return {'success': False, 'message': 'Only buyer or seller can dispute'}

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE market_listings SET status='disputed', dispute_reason=?, updated_at=CURRENT_TIMESTAMP WHERE listing_id=?",
                (reason, listing_id)
            )
            await db.execute(
                "INSERT INTO trade_audit_log (trade_type, actor_id, item_ref, notes) VALUES (?, ?, ?, ?)",
                ('dispute_raised', user_id, listing.item_class, f'Listing {listing_id}: {reason}')
            )
            await db.commit()

        return {'success': True, 'message': 'Dispute filed. An admin will review and resolve this trade.'}

    async def refund_escrow(self, admin_id: int, listing_id: str, economy_service) -> Dict:
        listing = await self.get_listing(listing_id)
        if not listing or listing.status not in (TradeStatus.ESCROWED, TradeStatus.DISPUTED):
            return {'success': False, 'message': 'Cannot refund this listing'}

        await economy_service.update_balance(
            listing.buyer_id, listing.escrow_held,
            f'Escrow refund: {listing.item_display}'
        )

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE market_listings SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE listing_id=?",
                (listing_id,)
            )
            await db.execute(
                "INSERT INTO trade_audit_log (trade_type, actor_id, target_id, item_ref, amount, notes, admin_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ('escrow_refunded', listing.buyer_id, listing.seller_id, listing.item_class,
                 listing.escrow_held, f'Listing {listing_id} refunded', admin_id)
            )
            await db.commit()

        return {'success': True, 'message': f'{listing.escrow_held:,} credits refunded to buyer.'}

    async def get_listings(
        self,
        status: str = 'pending',
        category: str = None,
        seller_id: int = None
    ) -> List[MarketListing]:
        async with aiosqlite.connect(self.db_path) as db:
            query = "SELECT * FROM market_listings WHERE status=?"
            params = [status]
            if seller_id:
                query += " AND seller_id=?"
                params.append(seller_id)
            query += " ORDER BY created_at DESC"
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_listing(r) for r in rows]

    async def get_listing(self, listing_id: str) -> Optional[MarketListing]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM market_listings WHERE listing_id=?", (listing_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return self._row_to_listing(row) if row else None

    async def _count_active_listings(self, seller_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM market_listings WHERE seller_id=? AND status IN ('pending','escrowed')",
                (seller_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def _expire_listing(self, listing_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE market_listings SET status='expired' WHERE listing_id=?", (listing_id,)
            )
            await db.commit()

    def _row_to_listing(self, row) -> MarketListing:
        return MarketListing(
            listing_id=row[0], seller_id=row[1], item_class=row[2],
            item_display=row[3], quantity=row[4], asking_price=row[5],
            status=TradeStatus(row[6]), buyer_id=row[7], escrow_held=row[8],
            dispute_reason=row[9],
            expires_at=datetime.fromisoformat(row[10]) if row[10] else None,
            created_at=datetime.fromisoformat(row[11]) if row[11] else None
        )
