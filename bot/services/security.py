"""
Security Service - Rate limiting, fraud detection, audit log
"""
import aiosqlite
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'trader.db')

class SecurityService:
    def __init__(self):
        self.db_path = DB_PATH
        self._rate_limits: Dict[int, list] = defaultdict(list)
        self._purchase_limits: Dict[int, list] = defaultdict(list)

    def check_rate_limit(self, user_id: int, action: str,
                          max_calls: int = 5, window_seconds: int = 60) -> bool:
        """Returns True if allowed, False if rate limited"""
        now = datetime.now()
        key = f'{user_id}_{action}'
        timestamps = self._rate_limits[key]
        # Remove old entries outside the window
        cutoff = now - timedelta(seconds=window_seconds)
        self._rate_limits[key] = [t for t in timestamps if t > cutoff]
        if len(self._rate_limits[key]) >= max_calls:
            return False
        self._rate_limits[key].append(now)
        return True

    def check_purchase_limit(self, user_id: int,
                              max_purchases: int = 10,
                              window_hours: int = 24) -> bool:
        """Prevent purchase flooding within 24h window"""
        now = datetime.now()
        cutoff = now - timedelta(hours=window_hours)
        purchases = self._purchase_limits[user_id]
        self._purchase_limits[user_id] = [t for t in purchases if t > cutoff]
        if len(self._purchase_limits[user_id]) >= max_purchases:
            return False
        self._purchase_limits[user_id].append(now)
        return True

    async def log_audit(self, trade_type: str, actor_id: int,
                         target_id: int = None, item_ref: str = None,
                         amount: int = None, notes: str = None,
                         admin_id: int = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO trade_audit_log
                   (trade_type, actor_id, target_id, item_ref, amount, notes, admin_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (trade_type, actor_id, target_id, item_ref, amount, notes, admin_id)
            )
            await db.commit()

    async def get_audit_log(self, limit: int = 50, actor_id: int = None) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if actor_id:
                cursor = await db.execute(
                    "SELECT * FROM trade_audit_log WHERE actor_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (actor_id, limit)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM trade_audit_log ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def is_banned(self, discord_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT is_banned FROM users WHERE discord_id = ?", (discord_id,)
            )
            row = await cursor.fetchone()
            return bool(row[0]) if row else False

    async def ban_user(self, discord_id: int, admin_id: int, reason: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET is_banned = 1 WHERE discord_id = ?", (discord_id,)
            )
            await db.commit()
        await self.log_audit('ban', admin_id, discord_id, notes=reason, admin_id=admin_id)

    async def unban_user(self, discord_id: int, admin_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET is_banned = 0 WHERE discord_id = ?", (discord_id,)
            )
            await db.commit()
        await self.log_audit('unban', admin_id, discord_id, admin_id=admin_id)
