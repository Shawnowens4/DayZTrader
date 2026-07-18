"""
Economy Service - Manages player balances and transactions
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional

class EconomyService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _conn(self):
        return sqlite3.connect(self.db_path)

    async def get_balance(self, discord_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                'SELECT balance FROM users WHERE discord_id = ?', (discord_id,)
            ).fetchone()
            return row[0] if row else 0

    async def ensure_user(self, discord_id: int, username: str, starting_balance: int = 1000):
        with self._conn() as conn:
            conn.execute(
                'INSERT OR IGNORE INTO users (discord_id, username, balance) VALUES (?, ?, ?)',
                (discord_id, username, starting_balance)
            )

    async def update_balance(self, discord_id: int, amount: int, reason: str = '') -> int:
        """Add or subtract from balance. Returns new balance."""
        with self._conn() as conn:
            conn.execute(
                'UPDATE users SET balance = balance + ? WHERE discord_id = ?',
                (amount, discord_id)
            )
            row = conn.execute(
                'SELECT balance FROM users WHERE discord_id = ?', (discord_id,)
            ).fetchone()
            new_balance = row[0] if row else 0
            # Audit
            conn.execute(
                'INSERT INTO trade_audit_log (trade_type, actor_id, amount, notes) VALUES (?, ?, ?, ?)',
                ('balance_change', discord_id, amount, reason)
            )
            return new_balance

    async def transfer(self, from_id: int, to_id: int, amount: int) -> bool:
        """Transfer credits between players."""
        if amount <= 0:
            return False
        balance = await self.get_balance(from_id)
        if balance < amount:
            return False
        with self._conn() as conn:
            conn.execute('UPDATE users SET balance = balance - ? WHERE discord_id = ?', (amount, from_id))
            conn.execute('UPDATE users SET balance = balance + ? WHERE discord_id = ?', (amount, to_id))
            conn.execute(
                'INSERT INTO trade_audit_log (trade_type, actor_id, target_id, amount, notes) VALUES (?, ?, ?, ?, ?)',
                ('transfer', from_id, to_id, amount, 'player transfer')
            )
        return True

    async def claim_daily(self, discord_id: int, amount: int = 500) -> dict:
        """Claim daily reward."""
        with self._conn() as conn:
            row = conn.execute(
                'SELECT last_daily FROM users WHERE discord_id = ?', (discord_id,)
            ).fetchone()
            if not row:
                return {'success': False, 'message': 'User not registered.'}
            last = row[0]
            if last:
                last_dt = datetime.fromisoformat(last)
                if datetime.now() - last_dt < timedelta(hours=24):
                    remaining = timedelta(hours=24) - (datetime.now() - last_dt)
                    hours = int(remaining.total_seconds() // 3600)
                    mins = int((remaining.total_seconds() % 3600) // 60)
                    return {'success': False, 'message': f'Come back in {hours}h {mins}m!'}
            conn.execute(
                'UPDATE users SET balance = balance + ?, last_daily = ? WHERE discord_id = ?',
                (amount, datetime.now().isoformat(), discord_id)
            )
        return {'success': True, 'amount': amount}

    async def get_leaderboard(self, limit: int = 10) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                'SELECT discord_id, username, balance FROM users ORDER BY balance DESC LIMIT ?',
                (limit,)
            ).fetchall()
        return [{'discord_id': r[0], 'username': r[1], 'balance': r[2]} for r in rows]
