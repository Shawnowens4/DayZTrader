"""
Shop Service - Admin-managed items and bundles
"""

import sqlite3
import json
import uuid
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class BundleItem:
    class_name: str
    quantity: int = 1
    attachments: List[str] = field(default_factory=list)

@dataclass
class ShopItem:
    item_id: str
    class_name: str
    display_name: str
    price: int
    category: str = 'general'
    is_bundle: bool = False
    bundle_items: List[BundleItem] = field(default_factory=list)
    stock: int = -1
    enabled: bool = True
    admin_only: bool = False
    description: str = ''
    image_url: str = ''

class ShopService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _conn(self):
        return sqlite3.connect(self.db_path)

    async def create_item(
        self,
        class_name: str,
        display_name: str,
        price: int,
        category: str = 'general',
        stock: int = -1,
        description: str = '',
        admin_id: int = None
    ) -> ShopItem:
        item = ShopItem(
            item_id=str(uuid.uuid4())[:8],
            class_name=class_name,
            display_name=display_name,
            price=price,
            category=category,
            stock=stock,
            description=description
        )
        with self._conn() as conn:
            conn.execute(
                '''INSERT INTO shop_items
                (item_id, class_name, display_name, price, category, is_bundle, stock, description, created_by)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)''',
                (item.item_id, class_name, display_name, price, category, stock, description, admin_id)
            )
        return item

    async def create_bundle(
        self,
        display_name: str,
        price: int,
        items: List[BundleItem],
        category: str = 'bundles',
        discount_pct: int = 0,
        description: str = '',
        admin_id: int = None
    ) -> ShopItem:
        bundle_id = str(uuid.uuid4())[:8]
        bundle_data = json.dumps([{
            'class': i.class_name,
            'qty': i.quantity,
            'attachments': i.attachments
        } for i in items])
        # Apply discount
        final_price = int(price * (1 - discount_pct / 100))
        with self._conn() as conn:
            conn.execute(
                '''INSERT INTO shop_items
                (item_id, class_name, display_name, price, category, is_bundle, bundle_data, description, created_by)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)''',
                (bundle_id, 'BUNDLE', display_name, final_price, category, bundle_data, description, admin_id)
            )
        return ShopItem(
            item_id=bundle_id,
            class_name='BUNDLE',
            display_name=display_name,
            price=final_price,
            category=category,
            is_bundle=True,
            bundle_items=items,
            description=description
        )

    async def get_catalog(self, category: str = None, include_disabled: bool = False) -> List[dict]:
        query = 'SELECT * FROM shop_items WHERE 1=1'
        params = []
        if category:
            query += ' AND category = ?'
            params.append(category)
        if not include_disabled:
            query += ' AND enabled = 1'
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        cols = ['item_id','class_name','display_name','price','category',
                'is_bundle','bundle_data','stock','enabled','admin_only','description','image_url','created_by','created_at','updated_at']
        return [dict(zip(cols, r)) for r in rows]

    async def get_item(self, item_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute('SELECT * FROM shop_items WHERE item_id = ?', (item_id,)).fetchone()
        if not row:
            return None
        cols = ['item_id','class_name','display_name','price','category',
                'is_bundle','bundle_data','stock','enabled','admin_only','description','image_url','created_by','created_at','updated_at']
        return dict(zip(cols, row))

    async def toggle_item(self, item_id: str, enabled: bool) -> bool:
        with self._conn() as conn:
            conn.execute('UPDATE shop_items SET enabled = ? WHERE item_id = ?', (int(enabled), item_id))
        return True

    async def update_price(self, item_id: str, new_price: int) -> bool:
        with self._conn() as conn:
            conn.execute('UPDATE shop_items SET price = ?, updated_at = ? WHERE item_id = ?',
                         (new_price, datetime.now().isoformat(), item_id))
        return True

    async def set_stock(self, item_id: str, stock: int) -> bool:
        with self._conn() as conn:
            conn.execute('UPDATE shop_items SET stock = ? WHERE item_id = ?', (stock, item_id))
        return True

    async def delete_item(self, item_id: str) -> bool:
        with self._conn() as conn:
            conn.execute('DELETE FROM shop_items WHERE item_id = ?', (item_id,))
        return True

    async def purchase(
        self,
        discord_id: int,
        item_id: str,
        economy_service,
        delivery_zone: str = 'NWAF'
    ) -> dict:
        item = await self.get_item(item_id)
        if not item:
            return {'success': False, 'message': 'Item not found.'}
        if not item['enabled']:
            return {'success': False, 'message': 'Item is currently unavailable.'}
        if item['stock'] == 0:
            return {'success': False, 'message': 'Out of stock!'}

        balance = await economy_service.get_balance(discord_id)
        if balance < item['price']:
            return {'success': False, 'message': f'Insufficient credits. Need {item["price"]}, you have {balance}.'}

        # Deduct credits
        await economy_service.update_balance(discord_id, -item['price'], f'Purchase: {item["display_name"]}')

        # Decrement stock
        if item['stock'] > 0:
            with self._conn() as conn:
                conn.execute('UPDATE shop_items SET stock = stock - 1 WHERE item_id = ?', (item_id,))

        # Log purchase
        with self._conn() as conn:
            conn.execute(
                'INSERT INTO purchases (discord_id, item_id, quantity, total_price, delivery_zone) VALUES (?, ?, 1, ?, ?)',
                (discord_id, item_id, item['price'], delivery_zone)
            )

        return {
            'success': True,
            'item': item,
            'delivery_zone': delivery_zone,
            'message': f'Purchase successful! Your {item["display_name"]} will spawn at {delivery_zone} on the next CE cycle (1-5 min).'
        }
