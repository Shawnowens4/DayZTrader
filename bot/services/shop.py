"""
Shop Service - Individual items and bundles, Nitrado delivery integration
"""
import aiosqlite
import json
import uuid
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from db.init_db import DB_PATH

@dataclass
class ShopItem:
    item_id: str
    class_name: str
    display_name: str
    price: int
    category: str = "misc"
    is_bundle: bool = False
    bundle_items: List[dict] = field(default_factory=list)  # [{"class": "AKM", "qty": 1}]
    stock: int = -1
    enabled: bool = True
    admin_only: bool = False
    fully_kitted: bool = False
    description: str = ""

class ShopService:
    def __init__(self, economy):
        self.economy = economy

    async def create_item(self, item: ShopItem, admin_id: int) -> ShopItem:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO shop_items
                (item_id, class_name, display_name, price, category, is_bundle,
                 bundle_data, stock, enabled, admin_only, fully_kitted, description, created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    item.item_id, item.class_name, item.display_name, item.price,
                    item.category, int(item.is_bundle),
                    json.dumps(item.bundle_items) if item.is_bundle else None,
                    item.stock, int(item.enabled), int(item.admin_only),
                    int(item.fully_kitted), item.description, admin_id
                )
            )
            await db.commit()
        return item

    async def create_bundle(self, display_name: str, items: List[dict],
                             price: int, category: str = "bundle",
                             admin_id: int = 0, description: str = "") -> ShopItem:
        """items = [{\"class\": \"AKM\", \"qty\": 1, \"attachments\": []}]"""
        bundle = ShopItem(
            item_id=str(uuid.uuid4())[:8],
            class_name="BUNDLE",
            display_name=display_name,
            price=price,
            category=category,
            is_bundle=True,
            bundle_items=items,
            description=description
        )
        return await self.create_item(bundle, admin_id)

    async def get_item(self, item_id: str) -> Optional[ShopItem]:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM shop_items WHERE item_id=?", (item_id,)) as cur:
                row = await cur.fetchone()
        if not row:
            return None
        return self._row_to_item(dict(row))

    async def get_catalog(self, category: str = None, include_disabled: bool = False) -> List[ShopItem]:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            if category:
                query = "SELECT * FROM shop_items WHERE category=?"
                params = (category,)
            else:
                query = "SELECT * FROM shop_items"
                params = ()
            if not include_disabled:
                query += (" AND" if "WHERE" in query else " WHERE") + " enabled=1"
            async with db.execute(query, params) as cur:
                rows = await cur.fetchall()
        return [self._row_to_item(dict(r)) for r in rows]

    async def toggle_item(self, item_id: str, enabled: bool):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE shop_items SET enabled=? WHERE item_id=?", (int(enabled), item_id))
            await db.commit()

    async def update_price(self, item_id: str, price: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE shop_items SET price=? WHERE item_id=?", (price, item_id))
            await db.commit()

    async def set_stock(self, item_id: str, stock: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE shop_items SET stock=? WHERE item_id=?", (stock, item_id))
            await db.commit()

    async def purchase(self, discord_id: int, username: str, item_id: str,
                       delivery_zone: str, quantity: int = 1) -> dict:
        item = await self.get_item(item_id)
        if not item:
            return {"success": False, "message": "\u274c Item not found."}
        if not item.enabled:
            return {"success": False, "message": "\u274c This item is currently unavailable."}
        if item.stock != -1 and item.stock < quantity:
            return {"success": False, "message": f"\u274c Only {item.stock} in stock."}

        total_cost = item.price * quantity
        balance = await self.economy.get_balance(discord_id)
        if balance < total_cost:
            return {"success": False, "message": f"\u274c Insufficient credits. Need {total_cost:,}, have {balance:,}."}

        await self.economy.update_balance(discord_id, -total_cost)

        if item.stock != -1:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE shop_items SET stock=stock-? WHERE item_id=?", (quantity, item_id))
                await db.commit()

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO purchases (discord_id, item_id, quantity, total_cost, delivery_zone) VALUES (?,?,?,?,?)",
                (discord_id, item_id, quantity, total_cost, delivery_zone)
            )
            await db.commit()

        new_bal = await self.economy.get_balance(discord_id)
        return {
            "success": True,
            "item": item,
            "total_cost": total_cost,
            "new_balance": new_bal,
            "delivery_zone": delivery_zone,
            "message": f"\u2705 Purchased **{item.display_name}** for {total_cost:,} credits! Delivering to {delivery_zone}..."
        }

    def _row_to_item(self, row: dict) -> ShopItem:
        return ShopItem(
            item_id=row["item_id"],
            class_name=row["class_name"],
            display_name=row["display_name"],
            price=row["price"],
            category=row["category"],
            is_bundle=bool(row["is_bundle"]),
            bundle_items=json.loads(row["bundle_data"]) if row["bundle_data"] else [],
            stock=row["stock"],
            enabled=bool(row["enabled"]),
            admin_only=bool(row["admin_only"]),
            fully_kitted=bool(row["fully_kitted"]),
            description=row.get("description", "")
        )
