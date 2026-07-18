"""
Player Market Service - Escrow-protected P2P trading
Fixed:
  - buy_listing: removed delivery_zone from market_listings insert (not in schema)
  - confirm_delivery / refund_escrow: economy_service param now optional (bot passes it)
  - All audit inserts use 'audit_log' (not 'trade_audit_log')
  - dispute_trade: uses 'audit_log'
"""
import aiosqlite
import uuid
import os
from datetime import datetime, timedelta
from typing import Optional, List

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'trader.db')


class MarketService:
    def __init__(self):
        self.db_path = DB_PATH

    async def create_listing(
        self, seller_id: int, item_class: str,
        item_display: str, quantity: int,
        asking_price: int, expiry_hours: int = 72
    ) -> dict:
        listing_id = str(uuid.uuid4())[:10].upper()
        expires_at = datetime.now() + timedelta(hours=expiry_hours)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM market_listings WHERE seller_id = ? AND status = 'pending'",
                (seller_id,)
            )
            row = await cursor.fetchone()
            if row[0] >= 5:
                return {'success': False, 'message': 'Max 5 active listings reached'}
            await db.execute(
                'INSERT INTO market_listings '
                '(listing_id, seller_id, item_class, item_display, quantity, asking_price, expires_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (listing_id, seller_id, item_class, item_display, quantity,
                 asking_price, expires_at.isoformat())
            )
            await db.commit()
        return {'success': True, 'listing_id': listing_id, 'expires_at': expires_at}

    async def buy_listing(
        self, buyer_id: int, listing_id: str,
        economy_service
    ) -> dict:
        """
        Fixed: removed delivery_zone — not in market_listings schema.
        Cog call: await bot.market_service.buy_listing(buyer_id, listing_id, bot.economy)
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM market_listings WHERE listing_id = ? AND status = 'pending'",
                (listing_id,)
            )
            listing = await cursor.fetchone()
            if not listing:
                return {'success': False, 'message': 'Listing not found or already sold'}
            listing = dict(listing)

            if listing['seller_id'] == buyer_id:
                return {'success': False, 'message': 'Cannot buy your own listing'}

            if datetime.fromisoformat(listing['expires_at']) < datetime.now():
                await db.execute(
                    "UPDATE market_listings SET status = 'cancelled' WHERE listing_id = ?",
                    (listing_id,)
                )
                await db.commit()
                return {'success': False, 'message': 'Listing has expired'}

            balance = await economy_service.get_balance(buyer_id)
            if balance < listing['asking_price']:
                return {'success': False, 'message': f'Need {listing["asking_price"]} credits, have {balance}'}

            await economy_service.update_balance(buyer_id, -listing['asking_price'], f'escrow_{listing_id}')

            await db.execute(
                "UPDATE market_listings SET status = 'escrowed', buyer_id = ?, escrow_held = ? WHERE listing_id = ?",
                (buyer_id, listing['asking_price'], listing_id)
            )
            await db.execute(
                'INSERT INTO audit_log (trade_type, actor_id, target_id, item_ref, amount, notes) VALUES (?, ?, ?, ?, ?, ?)',
                ('escrow', buyer_id, listing['seller_id'], listing_id, listing['asking_price'], 'buyer_paid_escrow')
            )
            await db.commit()

        return {'success': True, 'listing': listing, 'message': 'Credits locked in escrow. Trade in progress.'}

    async def confirm_delivery(
        self, admin_id: int, listing_id: str,
        economy_service=None
    ) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM market_listings WHERE listing_id = ? AND status = 'escrowed'",
                (listing_id,)
            )
            listing = await cursor.fetchone()
            if not listing:
                return {'success': False, 'message': 'Listing not in escrow state'}
            listing = dict(listing)

            if economy_service:
                await economy_service.update_balance(
                    listing['seller_id'], listing['escrow_held'],
                    f'escrow_release_{listing_id}'
                )
            else:
                # Fallback: direct SQL update
                await db.execute(
                    'UPDATE users SET balance = balance + ? WHERE discord_id = ?',
                    (listing['escrow_held'], listing['seller_id'])
                )

            await db.execute(
                "UPDATE market_listings SET status = 'delivered' WHERE listing_id = ?",
                (listing_id,)
            )
            await db.execute(
                'INSERT INTO audit_log (trade_type, actor_id, target_id, item_ref, amount, notes) VALUES (?, ?, ?, ?, ?, ?)',
                ('delivery', listing['buyer_id'], listing['seller_id'], listing_id,
                 listing['escrow_held'], 'escrow_released_to_seller')
            )
            await db.commit()

        return {'success': True, 'message': f'Delivery confirmed. {listing["escrow_held"]} credits released to seller.'}

    async def dispute_trade(
        self, user_id: int, listing_id: str, reason: str
    ) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE market_listings SET status = 'disputed' WHERE listing_id = ? AND (seller_id = ? OR buyer_id = ?)",
                (listing_id, user_id, user_id)
            )
            await db.execute(
                'INSERT INTO audit_log (trade_type, actor_id, item_ref, notes) VALUES (?, ?, ?, ?)',
                ('dispute', user_id, listing_id, reason)
            )
            await db.commit()
        return {'success': True, 'message': 'Dispute filed. An admin will review it.'}

    async def refund_escrow(
        self, admin_id: int, listing_id: str,
        economy_service=None
    ) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM market_listings WHERE listing_id = ? AND status IN ('escrowed','disputed')",
                (listing_id,)
            )
            listing = await cursor.fetchone()
            if not listing:
                return {'success': False, 'message': 'Listing not found or not in refundable state'}
            listing = dict(listing)

            if economy_service:
                await economy_service.update_balance(
                    listing['buyer_id'], listing['escrow_held'],
                    f'escrow_refund_{listing_id}'
                )
            else:
                await db.execute(
                    'UPDATE users SET balance = balance + ? WHERE discord_id = ?',
                    (listing['escrow_held'], listing['buyer_id'])
                )

            await db.execute(
                "UPDATE market_listings SET status = 'cancelled' WHERE listing_id = ?",
                (listing_id,)
            )
            await db.execute(
                'INSERT INTO audit_log (trade_type, actor_id, target_id, item_ref, amount, notes) VALUES (?, ?, ?, ?, ?, ?)',
                ('refund', listing['buyer_id'], listing['seller_id'], listing_id,
                 listing['escrow_held'], 'admin_refunded_escrow')
            )
            await db.commit()
        return {'success': True, 'message': f'{listing["escrow_held"]} credits refunded to buyer.'}

    async def get_listings(
        self, category: str = None, seller_id: int = None,
        status: str = 'pending'
    ) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = 'SELECT * FROM market_listings WHERE status = ?'
            params = [status]
            if seller_id:
                query += ' AND seller_id = ?'
                params.append(seller_id)
            query += ' ORDER BY created_at DESC LIMIT 50'
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def expire_old_listings(self, economy_service=None) -> int:
        count = 0
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM market_listings WHERE status IN ('pending','escrowed') AND expires_at < ?",
                (datetime.now().isoformat(),)
            )
            rows = await cursor.fetchall()
            for row in rows:
                listing = dict(row)
                if listing['status'] == 'escrowed' and listing['buyer_id']:
                    if economy_service:
                        await economy_service.update_balance(
                            listing['buyer_id'], listing['escrow_held'],
                            f'auto_refund_expired_{listing["listing_id"]}'
                        )
                    else:
                        await db.execute(
                            'UPDATE users SET balance = balance + ? WHERE discord_id = ?',
                            (listing['escrow_held'], listing['buyer_id'])
                        )
                await db.execute(
                    "UPDATE market_listings SET status = 'cancelled' WHERE listing_id = ?",
                    (listing['listing_id'],)
                )
                count += 1
            await db.commit()
        return count
