"""
Market Service - Player-to-player trading with escrow
"""

import sqlite3
import uuid
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime, timedelta

class TradeStatus(Enum):
    PENDING   = 'pending'
    ESCROWED  = 'escrowed'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'
    DISPUTED  = 'disputed'

class MarketService:
    def __init__(self, db_path: str, economy_service):
        self.db_path = db_path
        self.economy = economy_service

    def _conn(self):
        return sqlite3.connect(self.db_path)

    async def create_listing(
        self,
        seller_id: int,
        item_class: str,
        item_display: str,
        quantity: int,
        asking_price: int,
        expiry_days: int = 7
    ) -> dict:
        # Check active listing count
        with self._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM market_listings WHERE seller_id = ? AND status IN ('pending','escrowed')",
                (seller_id,)
            ).fetchone()[0]
        if count >= 5:
            return {'success': False, 'message': 'Max 5 active listings allowed.'}
        if asking_price < 100:
            return {'success': False, 'message': 'Minimum listing price is 100 credits.'}

        listing_id = str(uuid.uuid4())[:12]
        expires = datetime.now() + timedelta(days=expiry_days)

        with self._conn() as conn:
            conn.execute(
                '''INSERT INTO market_listings
                (listing_id, seller_id, item_class, item_display, quantity, asking_price, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (listing_id, seller_id, item_class, item_display, quantity, asking_price, expires.isoformat())
            )
        return {'success': True, 'listing_id': listing_id, 'expires_at': expires}

    async def buy_listing(self, buyer_id: int, listing_id: str) -> dict:
        """Buyer pays into escrow. Credits locked until delivery confirmed."""
        with self._conn() as conn:
            row = conn.execute(
                'SELECT * FROM market_listings WHERE listing_id = ?', (listing_id,)
            ).fetchone()
        if not row:
            return {'success': False, 'message': 'Listing not found.'}

        cols = ['listing_id','seller_id','item_class','item_display','quantity',
                'asking_price','status','buyer_id','escrow_held','dispute_reason','expires_at','created_at','updated_at']
        listing = dict(zip(cols, row))

        if listing['status'] != 'pending':
            return {'success': False, 'message': 'Listing is no longer available.'}
        if listing['seller_id'] == buyer_id:
            return {'success': False, 'message': "You can't buy your own listing."}
        if datetime.fromisoformat(listing['expires_at']) < datetime.now():
            return {'success': False, 'message': 'Listing has expired.'}

        balance = await self.economy.get_balance(buyer_id)
        if balance < listing['asking_price']:
            return {'success': False, 'message': f'Insufficient credits. Need {listing["asking_price"]:,}.'}

        # Lock credits in escrow
        await self.economy.update_balance(buyer_id, -listing['asking_price'], f'Escrow: {listing_id}')

        with self._conn() as conn:
            conn.execute(
                '''UPDATE market_listings SET status = 'escrowed', buyer_id = ?, escrow_held = ?,
                updated_at = ? WHERE listing_id = ?''',
                (buyer_id, listing['asking_price'], datetime.now().isoformat(), listing_id)
            )
            conn.execute(
                'INSERT INTO trade_audit_log (trade_type, actor_id, target_id, item_ref, amount, notes) VALUES (?, ?, ?, ?, ?, ?)',
                ('escrow_locked', buyer_id, listing['seller_id'], listing_id, listing['asking_price'], 'buyer paid into escrow')
            )
        return {'success': True, 'listing': listing, 'message': 'Credits locked in escrow. Seller notified to deliver the item.'}

    async def confirm_delivery(self, admin_id: int, listing_id: str) -> dict:
        """Admin confirms delivery. Releases escrow to seller."""
        with self._conn() as conn:
            row = conn.execute(
                'SELECT * FROM market_listings WHERE listing_id = ?', (listing_id,)
            ).fetchone()
        if not row:
            return {'success': False, 'message': 'Listing not found.'}
        cols = ['listing_id','seller_id','item_class','item_display','quantity',
                'asking_price','status','buyer_id','escrow_held','dispute_reason','expires_at','created_at','updated_at']
        listing = dict(zip(cols, row))

        if listing['status'] != 'escrowed':
            return {'success': False, 'message': 'Trade not in escrowed state.'}

        # Release escrow to seller
        await self.economy.update_balance(listing['seller_id'], listing['escrow_held'], f'Sale: {listing_id}')

        with self._conn() as conn:
            conn.execute(
                "UPDATE market_listings SET status = 'delivered', updated_at = ? WHERE listing_id = ?",
                (datetime.now().isoformat(), listing_id)
            )
            conn.execute(
                'INSERT INTO trade_audit_log (trade_type, actor_id, target_id, item_ref, amount, admin_id, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                ('escrow_released', listing['buyer_id'], listing['seller_id'], listing_id, listing['escrow_held'], admin_id, 'delivery confirmed by admin')
            )
        return {'success': True, 'message': f'Escrow released. {listing["escrow_held"]:,} credits sent to seller.'}

    async def dispute_trade(self, user_id: int, listing_id: str, reason: str) -> dict:
        with self._conn() as conn:
            conn.execute(
                "UPDATE market_listings SET status = 'disputed', dispute_reason = ? WHERE listing_id = ? AND (seller_id = ? OR buyer_id = ?)",
                (reason, listing_id, user_id, user_id)
            )
        return {'success': True, 'message': 'Trade disputed. An admin will review shortly.'}

    async def refund_escrow(self, admin_id: int, listing_id: str) -> dict:
        with self._conn() as conn:
            row = conn.execute(
                'SELECT buyer_id, escrow_held FROM market_listings WHERE listing_id = ?', (listing_id,)
            ).fetchone()
        if not row or not row[0]:
            return {'success': False, 'message': 'No escrow to refund.'}
        await self.economy.update_balance(row[0], row[1], f'Escrow refund: {listing_id}')
        with self._conn() as conn:
            conn.execute(
                "UPDATE market_listings SET status = 'cancelled', escrow_held = 0 WHERE listing_id = ?",
                (listing_id,)
            )
            conn.execute(
                'INSERT INTO trade_audit_log (trade_type, actor_id, item_ref, amount, admin_id, notes) VALUES (?, ?, ?, ?, ?, ?)',
                ('escrow_refunded', row[0], listing_id, row[1], admin_id, 'admin refunded escrow')
            )
        return {'success': True, 'message': f'Refunded {row[1]:,} credits to buyer.'}

    async def get_listings(self, status: str = 'pending', category: str = None) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM market_listings WHERE status = ? ORDER BY created_at DESC",
                (status,)
            ).fetchall()
        cols = ['listing_id','seller_id','item_class','item_display','quantity',
                'asking_price','status','buyer_id','escrow_held','dispute_reason','expires_at','created_at','updated_at']
        return [dict(zip(cols, r)) for r in rows]

    async def expire_old_listings(self):
        """Background task: auto-expire and refund listings past expiry."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT listing_id, buyer_id, escrow_held FROM market_listings WHERE status IN ('pending','escrowed') AND expires_at < ?",
                (datetime.now().isoformat(),)
            ).fetchall()
        for row in rows:
            if row[1] and row[2] > 0:
                await self.refund_escrow(0, row[0])
            else:
                with self._conn() as conn:
                    conn.execute(
                        "UPDATE market_listings SET status = 'cancelled' WHERE listing_id = ?", (row[0],)
                    )
