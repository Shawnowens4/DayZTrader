"""
Economy Service - SQLite-backed credit system
"""
import aiosqlite
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'trader.db')

class EconomyService:
    def __init__(self):
        self.db_path = DB_PATH

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            with open(os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'schema.sql')) as f:
                await db.executescript(f.read())
            await db.commit()

    async def get_or_create_user(self, discord_id: int, username: str) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
            )
            user = await cursor.fetchone()
            if not user:
                await db.execute(
                    "INSERT INTO users (discord_id, username) VALUES (?, ?)",
                    (discord_id, username)
                )
                await db.commit()
                cursor = await db.execute(
                    "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
                )
                user = await cursor.fetchone()
            return dict(user)

    async def get_balance(self, discord_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT balance FROM users WHERE discord_id = ?", (discord_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def update_balance(self, discord_id: int, amount: int, reason: str = None) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            if amount > 0:
                await db.execute(
                    "UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE discord_id = ?",
                    (amount, amount, discord_id)
                )
            else:
                await db.execute(
                    "UPDATE users SET balance = balance + ?, total_spent = total_spent + ? WHERE discord_id = ?",
                    (amount, abs(amount), discord_id)
                )
            # Audit log
            await db.execute(
                "INSERT INTO trade_audit_log (trade_type, actor_id, amount, notes) VALUES (?, ?, ?, ?)",
                ('balance_adjust', discord_id, amount, reason)
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT balance FROM users WHERE discord_id = ?", (discord_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def claim_daily(self, discord_id: int, username: str, amount: int = 500) -> dict:
        user = await self.get_or_create_user(discord_id, username)
        now = datetime.now()
        if user.get('last_daily'):
            last = datetime.fromisoformat(user['last_daily'])
            diff = now - last
            if diff < timedelta(hours=24):
                remaining = timedelta(hours=24) - diff
                hours = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                return {'success': False, 'message': f'\u23f0 Come back in **{hours}h {mins}m**'}
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET last_daily = ? WHERE discord_id = ?",
                (now.isoformat(), discord_id)
            )
            await db.commit()
        new_balance = await self.update_balance(discord_id, amount, 'daily_reward')
        return {'success': True, 'amount': amount, 'new_balance': new_balance}

    async def get_leaderboard(self, limit: int = 10) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def transfer(self, from_id: int, to_id: int, amount: int) -> dict:
        balance = await self.get_balance(from_id)
        if balance < amount:
            return {'success': False, 'message': 'Insufficient balance'}
        if amount <= 0:
            return {'success': False, 'message': 'Amount must be positive'}
        await self.update_balance(from_id, -amount, f'transfer_to_{to_id}')
        await self.update_balance(to_id, amount, f'transfer_from_{from_id}')
        return {'success': True, 'amount': amount}
