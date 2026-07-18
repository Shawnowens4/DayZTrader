"""
Economy Service - Manages player balances via SQLite
"""
import aiosqlite
import os
from datetime import datetime, timedelta
from db.init_db import DB_PATH

class EconomyService:

    async def get_or_create_user(self, discord_id: int, username: str) -> dict:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE discord_id=?", (discord_id,)) as cur:
                row = await cur.fetchone()
            if not row:
                await db.execute(
                    "INSERT INTO users (discord_id, username) VALUES (?, ?)",
                    (discord_id, username)
                )
                await db.commit()
                async with db.execute("SELECT * FROM users WHERE discord_id=?", (discord_id,)) as cur:
                    row = await cur.fetchone()
            return dict(row)

    async def get_balance(self, discord_id: int) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT balance FROM users WHERE discord_id=?", (discord_id,)) as cur:
                row = await cur.fetchone()
            return row[0] if row else 0

    async def update_balance(self, discord_id: int, amount: int) -> int:
        """Add or subtract from balance. Returns new balance."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE discord_id=?",
                (amount, discord_id)
            )
            if amount > 0:
                await db.execute(
                    "UPDATE users SET total_earned = total_earned + ? WHERE discord_id=?",
                    (amount, discord_id)
                )
            else:
                await db.execute(
                    "UPDATE users SET total_spent = total_spent + ? WHERE discord_id=?",
                    (abs(amount), discord_id)
                )
            await db.commit()
            async with db.execute("SELECT balance FROM users WHERE discord_id=?", (discord_id,)) as cur:
                row = await cur.fetchone()
            return row[0] if row else 0

    async def claim_daily(self, discord_id: int, username: str, amount: int = 500) -> dict:
        user = await self.get_or_create_user(discord_id, username)
        last = user.get("last_daily")
        if last:
            last_dt = datetime.fromisoformat(last)
            if datetime.now() - last_dt < timedelta(hours=24):
                remaining = timedelta(hours=24) - (datetime.now() - last_dt)
                hours = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                return {"success": False, "message": f"\u23f0 Daily available in {hours}h {mins}m"}
        await self.update_balance(discord_id, amount)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET last_daily=? WHERE discord_id=?",
                (datetime.now().isoformat(), discord_id)
            )
            await db.commit()
        new_bal = await self.get_balance(discord_id)
        return {"success": True, "amount": amount, "new_balance": new_bal}

    async def get_leaderboard(self, limit: int = 10) -> list:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,)
            ) as cur:
                rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def admin_adjust(self, discord_id: int, amount: int, admin_id: int, reason: str = ""):
        new_bal = await self.update_balance(discord_id, amount)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO audit_log (action, actor_id, target_id, amount, notes, admin_id) VALUES (?,?,?,?,?,?)",
                ("balance_adjust", admin_id, discord_id, amount, reason, admin_id)
            )
            await db.commit()
        return new_bal
