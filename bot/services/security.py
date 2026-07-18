"""
Security Service - Rate limiting, cooldowns, audit helpers
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Tuple

class SecurityService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _conn(self):
        return sqlite3.connect(self.db_path)

    async def check_rate_limit(
        self,
        discord_id: int,
        action: str,
        max_count: int,
        window_seconds: int
    ) -> Tuple[bool, str]:
        """Returns (allowed, message)."""
        now = datetime.now()
        window_start = now - timedelta(seconds=window_seconds)
        with self._conn() as conn:
            row = conn.execute(
                'SELECT count, window_start FROM rate_limits WHERE discord_id = ? AND action = ?',
                (discord_id, action)
            ).fetchone()
            if not row:
                conn.execute(
                    'INSERT INTO rate_limits (discord_id, action, count, window_start) VALUES (?, ?, 1, ?)',
                    (discord_id, action, now.isoformat())
                )
                return True, ''
            count, ws = row
            ws_dt = datetime.fromisoformat(ws)
            if ws_dt < window_start:
                # Reset window
                conn.execute(
                    'UPDATE rate_limits SET count = 1, window_start = ? WHERE discord_id = ? AND action = ?',
                    (now.isoformat(), discord_id, action)
                )
                return True, ''
            if count >= max_count:
                wait = (ws_dt + timedelta(seconds=window_seconds) - now)
                mins = int(wait.total_seconds() // 60)
                secs = int(wait.total_seconds() % 60)
                return False, f'Rate limited. Try again in {mins}m {secs}s.'
            conn.execute(
                'UPDATE rate_limits SET count = count + 1 WHERE discord_id = ? AND action = ?',
                (discord_id, action)
            )
        return True, ''

    async def is_banned(self, discord_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute('SELECT is_banned FROM users WHERE discord_id = ?', (discord_id,)).fetchone()
        return bool(row and row[0])

    async def ban_user(self, discord_id: int, admin_id: int, reason: str = ''):
        with self._conn() as conn:
            conn.execute('UPDATE users SET is_banned = 1 WHERE discord_id = ?', (discord_id,))
            conn.execute(
                'INSERT INTO trade_audit_log (trade_type, actor_id, target_id, notes, admin_id) VALUES (?, ?, ?, ?, ?)',
                ('ban', admin_id, discord_id, reason, admin_id)
            )

    async def unban_user(self, discord_id: int, admin_id: int):
        with self._conn() as conn:
            conn.execute('UPDATE users SET is_banned = 0 WHERE discord_id = ?', (discord_id,))
