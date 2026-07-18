"""
Economy Service - Balance management, transactions, daily rewards
"""

import aiosqlite
import os
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "db/dayz_trader.db")

class EconomyService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def ensure_user(self, discord_id: int, username: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (discord_id, username) VALUES (?, ?)",
                (discord_id, username)
            )
            await db.execute(
                "UPDATE users SET username=?, last_active=CURRENT_TIMESTAMP WHERE discord_id=?",
                (username, discord_id)
            )
            await db.commit()

    async def get_balance(self, discord_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT balance FROM users WHERE discord_id=?", (discord_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def update_balance(self, discord_id: int, amount: int, description: str = "") -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE discord_id = ?",
                (amount, discord_id)
            )
            await db.execute(
                "INSERT INTO transactions (discord_id, amount, type, description) VALUES (?, ?, ?, ?)",
                (discord_id, amount, 'credit' if amount > 0 else 'debit', description)
            )
            if amount > 0:
                await db.execute(
                    "UPDATE users SET total_earned = total_earned + ? WHERE discord_id = ?",
                    (amount, discord_id)
                )
            else:
                await db.execute(
                    "UPDATE users SET total_spent = total_spent + ? WHERE discord_id = ?",
                    (abs(amount), discord_id)
                )
            await db.commit()
            async with db.execute(
                "SELECT balance FROM users WHERE discord_id=?", (discord_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def transfer(self, sender_id: int, receiver_id: int, amount: int) -> dict:
        sender_balance = await self.get_balance(sender_id)
        if sender_balance < amount:
            return {'success': False, 'message': 'Insufficient balance'}
        await self.update_balance(sender_id, -amount, f'Transfer to {receiver_id}')
        await self.update_balance(receiver_id, amount, f'Transfer from {sender_id}')
        return {'success': True, 'message': f'Transferred {amount} credits'}

    async def get_leaderboard(self, limit: int = 10) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT discord_id, username, balance FROM users ORDER BY balance DESC LIMIT ?",
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [{'discord_id': r[0], 'username': r[1], 'balance': r[2]} for r in rows]

    async def get_transaction_history(self, discord_id: int, limit: int = 20) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT amount, type, description, timestamp FROM transactions WHERE discord_id=? ORDER BY timestamp DESC LIMIT ?",
                (discord_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [{'amount': r[0], 'type': r[1], 'description': r[2], 'timestamp': r[3]} for r in rows]
