"""
Shop Service - Admin-managed item and bundle catalog
"""

import aiosqlite
import uuid
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "db/dayz_trader.db")

@dataclass
class ShopItem:
    item_id: str
    class_name: str
    display_name: str
    price: int
    category: str = 'misc'
    is_bundle: bool = False
    bundle_items: List[Dict] = field(default_factory=list)  # [{"class": "AKM", "qty": 1}]
    bundle_discount_pct: int = 0
    stock: int = -1
    enabled: bool = True
    admin_only: bool = False

class ShopService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def create_item(
        self,
        class_name: str,
        display_name: str,
        price: int,
        category: str = 'misc',
        stock: int = -1,
        admin_only: bool = False,
        created_by: int = None
    ) -> ShopItem:
        item_id = str(uuid.uuid4())[:8]
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO shop_items
                   (item_id, class_name, display_name, price, category, stock, admin_only, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_id, class_name, display_name, price, category, stock, admin_only, created_by)
            )
            await db.commit()
        return ShopItem(item_id, class_name, display_name, price, category, stock=stock)

    async def create_bundle(
        self,
        display_name: str,
        items: List[Dict],  # [{"class": "AKM", "display": "AKM Rifle", "qty": 1}]
        price: int,
        discount_pct: int = 0,
        category: str = 'misc',
        created_by: int = None
    ) -> ShopItem:
        item_id = str(uuid.uuid4())[:8]
        bundle_json = json.dumps(items)
        class_name = f"BUNDLE_{item_id}"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO shop_items
                   (item_id, class_name, display_name, price, category, is_bundle, bundle_data, bundle_discount_pct, created_by)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)""",
                (item_id, class_name, display_name, price, category, bundle_json, discount_pct, created_by)
            )
            await db.commit()
        return ShopItem(item_id, class_name, display_name, price, category, is_bundle=True,
                        bundle_items=items, bundle_discount_pct=discount_pct)

    async def get_catalog(self, category: str = None, admin: bool = False) -> List[ShopItem]:
        async with aiosqlite.connect(self.db_path) as db:
            if category:
                query = "SELECT * FROM shop_items WHERE enabled=1 AND category=?"
                if not admin:
                    query += " AND admin_only=0"
                async with db.execute(query, (category,)) as cursor:
                    rows = await cursor.fetchall()
            else:
                query = "SELECT * FROM shop_items WHERE enabled=1"
                if not admin:
                    query += " AND admin_only=0"
                async with db.execute(query) as cursor:
                    rows = await cursor.fetchall()
        return [self._row_to_item(r) for r in rows]

    async def get_item(self, item_id: str) -> Optional[ShopItem]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM shop_items WHERE item_id=?", (item_id,)) as cursor:
                row = await cursor.fetchone()
                return self._row_to_item(row) if row else None

    async def toggle_item(self, item_id: str, enabled: bool) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE shop_items SET enabled=?, updated_at=CURRENT_TIMESTAMP WHERE item_id=?",
                (enabled, item_id)
            )
            await db.commit()
        return True

    async def set_price(self, item_id: str, price: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE shop_items SET price=?, updated_at=CURRENT_TIMESTAMP WHERE item_id=?",
                (price, item_id)
            )
            await db.commit()
        return True

    async def set_stock(self, item_id: str, stock: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE shop_items SET stock=?, updated_at=CURRENT_TIMESTAMP WHERE item_id=?",
                (stock, item_id)
            )
            await db.commit()
        return True

    async def purchase(
        self,
        discord_id: int,
        item_id: str,
        quantity: int,
        economy_service
    ) -> Dict:
        item = await self.get_item(item_id)
        if not item:
            return {'success': False, 'message': 'Item not found'}
        if not item.enabled:
            return {'success': False, 'message': 'Item is not available'}
        if item.stock != -1 and item.stock < quantity:
            return {'success': False, 'message': f'Only {item.stock} in stock!'}

        total_cost = item.price * quantity
        balance = await economy_service.get_balance(discord_id)
        if balance < total_cost:
            return {'success': False, 'message': f'Need {total_cost} credits, you have {balance}'}

        # Deduct balance
        await economy_service.update_balance(discord_id, -total_cost, f'Purchase: {item.display_name} x{quantity}')

        # Deduct stock if limited
        if item.stock != -1:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE shop_items SET stock=stock-? WHERE item_id=?", (quantity, item_id)
                )
                await db.execute(
                    "INSERT INTO shop_purchases (discord_id, item_id, quantity, total_cost) VALUES (?, ?, ?, ?)",
                    (discord_id, item_id, quantity, total_cost)
                )
                await db.commit()
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO shop_purchases (discord_id, item_id, quantity, total_cost) VALUES (?, ?, ?, ?)",
                    (discord_id, item_id, quantity, total_cost)
                )
                await db.commit()

        return {
            'success': True,
            'message': f'Purchased {item.display_name} x{quantity} for {total_cost} credits!',
            'item': item,
            'total_cost': total_cost
        }

    def _row_to_item(self, row) -> ShopItem:
        bundle_items = json.loads(row[6]) if row[6] else []
        return ShopItem(
            item_id=row[0], class_name=row[1], display_name=row[2],
            price=row[3], category=row[4], is_bundle=bool(row[5]),
            bundle_items=bundle_items, bundle_discount_pct=row[7],
            stock=row[8], enabled=bool(row[9]), admin_only=bool(row[10])
        )
