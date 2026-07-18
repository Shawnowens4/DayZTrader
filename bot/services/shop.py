"""
Shop Service - Admin-managed items, bundles, and purchases
"""
import aiosqlite
import json
import uuid
import os
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'trader.db')


@dataclass
class BundleItem:
    class_name: str
    quantity: int = 1


@dataclass
class ShopItem:
    item_id: str
    class_name: str
    display_name: str
    price: int
    category: str
    is_bundle: bool = False
    bundle_items: Optional[List[dict]] = None
    bundle_discount_pct: int = 0
    stock: int = -1
    enabled: bool = True
    admin_only: bool = False


class ShopService:
    def __init__(self):
        self.db_path = DB_PATH

    async def create_item(
        self, class_name: str, display_name: str, price: int,
        category: str, admin_id: int, stock: int = -1,
        admin_only: bool = False, description: str = None
    ) -> ShopItem:
        item_id = str(uuid.uuid4())[:8].upper()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT INTO shop_items '
                '(item_id, class_name, display_name, price, category, stock, admin_only, description, created_by) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (item_id, class_name, display_name, price, category, stock, admin_only, description, admin_id)
            )
            await db.commit()
        return ShopItem(item_id, class_name, display_name, price, category, stock=stock)

    async def create_bundle(
        self, display_name: str, items: List[BundleItem],
        price: int, category: str, admin_id: int,
        discount_pct: int = 0
    ) -> ShopItem:
        item_id = str(uuid.uuid4())[:8].upper()
        # Serialize BundleItem list to JSON [{"class": ..., "qty": ...}]
        bundle_data = json.dumps(
            [{'class': i.class_name, 'qty': i.quantity} for i in items]
        )
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT INTO shop_items '
                '(item_id, class_name, display_name, price, category, is_bundle, bundle_data, bundle_discount, created_by) '
                'VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)',
                (item_id, f'bundle_{item_id}', display_name, price, category, bundle_data, discount_pct, admin_id)
            )
            await db.commit()
        return ShopItem(
            item_id, f'bundle_{item_id}', display_name, price,
            category, is_bundle=True,
            bundle_items=[{'class': i.class_name, 'qty': i.quantity} for i in items]
        )

    async def get_catalog(self, category: str = None, include_disabled: bool = False) -> List[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = 'SELECT * FROM shop_items WHERE 1=1'
            params = []
            if not include_disabled:
                query += ' AND enabled = 1'
            if category:
                query += ' AND category = ?'
                params.append(category)
            query += ' ORDER BY category, price'
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            items = []
            for row in rows:
                item = dict(row)
                if item['bundle_data']:
                    item['bundle_items'] = json.loads(item['bundle_data'])
                items.append(item)
            return items

    async def get_item(self, item_id: str) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM shop_items WHERE item_id = ?', (item_id,)
            )
            row = await cursor.fetchone()
            if row:
                item = dict(row)
                if item['bundle_data']:
                    item['bundle_items'] = json.loads(item['bundle_data'])
                return item
            return None

    async def toggle_item(self, item_id: str, enabled: bool) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE shop_items SET enabled = ?, updated_at = ? WHERE item_id = ?',
                (int(enabled), datetime.now().isoformat(), item_id)
            )
            await db.commit()
        return True

    async def delete_item(self, item_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE shop_items SET enabled = 0, updated_at = ? WHERE item_id = ?',
                (datetime.now().isoformat(), item_id)
            )
            await db.commit()
        return True

    async def update_price(self, item_id: str, new_price: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE shop_items SET price = ?, updated_at = ? WHERE item_id = ?',
                (new_price, datetime.now().isoformat(), item_id)
            )
            await db.commit()
        return True

    async def set_stock(self, item_id: str, qty: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE shop_items SET stock = ?, updated_at = ? WHERE item_id = ?',
                (qty, datetime.now().isoformat(), item_id)
            )
            await db.commit()
        return True

    async def purchase(
        self, discord_id: int, item_id: str,
        economy_service, delivery_zone: str = 'NWAF'
    ) -> dict:
        """
        Fixed signature: purchase(discord_id, item_id, economy_service, delivery_zone)
        Caller in trader.py: bot.shop.purchase(uid, item_id, self.bot.economy, delivery_zone=zone)
        """
        item = await self.get_item(item_id)
        if not item:
            return {'success': False, 'message': 'Item not found'}
        if not item['enabled']:
            return {'success': False, 'message': 'Item is currently unavailable'}
        if item['stock'] == 0:
            return {'success': False, 'message': 'Out of stock'}

        balance = await economy_service.get_balance(discord_id)
        if balance < item['price']:
            return {'success': False, 'message': f'Insufficient credits. Need {item["price"]}, have {balance}'}

        await economy_service.update_balance(discord_id, -item['price'], f'shop_purchase_{item_id}')

        if item['stock'] > 0:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'UPDATE shop_items SET stock = stock - 1 WHERE item_id = ?', (item_id,)
                )
                await db.commit()

        # Log purchase — use schema column 'status' not 'delivery_status'
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT INTO purchases (discord_id, item_id, total_cost, delivery_zone, status) '
                "VALUES (?, ?, ?, ?, 'queued')",
                (discord_id, item_id, item['price'], delivery_zone)
            )
            await db.commit()

        return {
            'success': True,
            'item': item,
            'cost': item['price'],
            'delivery_zone': delivery_zone
        }
