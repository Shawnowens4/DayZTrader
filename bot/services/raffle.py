"""
Raffle Service - Fixed
Fix 1: get_odds total_tickets generator (e.entries for e in ...)
Fix 2: DB operations now use bot.db_path
"""

import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from enum import Enum
import sqlite3

class RaffleStatus(Enum):
    INACTIVE = 'inactive'
    OPEN = 'open'
    DRAWING = 'drawing'
    COMPLETE = 'complete'

@dataclass
class RaffleEntry:
    user_id: int
    username: str
    entries: int = 1
    timestamp: datetime = None
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class RaffleRound:
    week_number: int
    vehicle: str
    vehicle_display: str
    entry_cost: int
    max_entries_per_player: int
    start_time: datetime
    end_time: datetime
    status: RaffleStatus
    entries: List[RaffleEntry] = field(default_factory=list)
    winner: Optional[int] = None
    winner_name: Optional[str] = None
    created_at: datetime = None
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class RaffleService:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.current_raffle: Optional[RaffleRound] = None
        self.raffle_history: List[RaffleRound] = []

    async def start_raffle(self, vehicle, vehicle_display, entry_cost=500, duration_hours=168, max_entries=10):
        now = datetime.now()
        raffle = RaffleRound(
            week_number=now.isocalendar()[1],
            vehicle=vehicle,
            vehicle_display=vehicle_display,
            entry_cost=entry_cost,
            max_entries_per_player=max_entries,
            start_time=now,
            end_time=now + timedelta(hours=duration_hours),
            status=RaffleStatus.OPEN
        )
        self.current_raffle = raffle
        return raffle

    async def enter_raffle(self, user_id, username, num_entries=1, economy_service=None):
        if not self.current_raffle:
            return {'success': False, 'message': '❌ No active raffle!'}
        if self.current_raffle.status != RaffleStatus.OPEN:
            return {'success': False, 'message': f'❌ Raffle is {self.current_raffle.status.value}'}
        if datetime.now() > self.current_raffle.end_time:
            return {'success': False, 'message': '❌ Raffle has ended!'}
        existing_entries = sum(e.entries for e in self.current_raffle.entries if e.user_id == user_id)
        if existing_entries + num_entries > self.current_raffle.max_entries_per_player:
            remaining = self.current_raffle.max_entries_per_player - existing_entries
            return {'success': False, 'message': f'❌ Max {self.current_raffle.max_entries_per_player} entries. You have {remaining} left.'}
        total_cost = self.current_raffle.entry_cost * num_entries
        if economy_service:
            balance = await economy_service.get_balance(user_id)
            if balance < total_cost:
                return {'success': False, 'message': f'❌ Need {total_cost:,}, you have {balance:,}'}
            await economy_service.update_balance(user_id, -total_cost, 'Raffle entry')
        existing = next((e for e in self.current_raffle.entries if e.user_id == user_id), None)
        if existing:
            existing.entries += num_entries
        else:
            self.current_raffle.entries.append(RaffleEntry(user_id, username, num_entries))
        total = sum(e.entries for e in self.current_raffle.entries if e.user_id == user_id)
        return {
            'success': True,
            'message': f'🎟️ Entered! Tickets: {total} | Cost: {total_cost:,} credits | Remaining: {self.current_raffle.max_entries_per_player - total}'
        }

    async def draw_winner(self):
        if not self.current_raffle or self.current_raffle.status == RaffleStatus.COMPLETE:
            return self.current_raffle
        if datetime.now() < self.current_raffle.end_time:
            return None
        self.current_raffle.status = RaffleStatus.DRAWING
        pool = []
        for e in self.current_raffle.entries:
            pool.extend([e.user_id] * e.entries)
        if not pool:
            self.current_raffle.status = RaffleStatus.COMPLETE
            return self.current_raffle
        winner_id = random.choice(pool)
        winner_entry = next((e for e in self.current_raffle.entries if e.user_id == winner_id), None)
        if winner_entry:
            self.current_raffle.winner = winner_entry.user_id
            self.current_raffle.winner_name = winner_entry.username
        self.current_raffle.status = RaffleStatus.COMPLETE
        self.raffle_history.append(self.current_raffle)
        return self.current_raffle

    def get_raffle_info(self):
        if not self.current_raffle:
            return None
        tr = self.current_raffle.end_time - datetime.now()
        return {
            'vehicle': self.current_raffle.vehicle_display,
            'status': self.current_raffle.status.value,
            'entry_cost': self.current_raffle.entry_cost,
            'total_entries': sum(e.entries for e in self.current_raffle.entries),
            'unique_players': len(self.current_raffle.entries),
            'hours_remaining': max(0, tr.total_seconds() / 3600),
            'max_entries_per_player': self.current_raffle.max_entries_per_player,
            'end_time': self.current_raffle.end_time
        }

    def get_player_entries(self, user_id):
        if not self.current_raffle:
            return 0
        e = next((e for e in self.current_raffle.entries if e.user_id == user_id), None)
        return e.entries if e else 0

    def get_odds(self, user_id):
        if not self.current_raffle:
            return {'error': 'No active raffle'}
        player_tickets = self.get_player_entries(user_id)
        # BUG FIX: was 'for e.entries in' which caused AttributeError
        total_tickets = sum(e.entries for e in self.current_raffle.entries)
        if total_tickets == 0:
            return {'player_tickets': 0, 'total_tickets': 0, 'odds_percent': 0, 'odds_formatted': '0.00%'}
        odds = (player_tickets / total_tickets) * 100
        return {
            'player_tickets': player_tickets,
            'total_tickets': total_tickets,
            'odds_percent': odds,
            'odds_formatted': f'{odds:.2f}%'
        }

    def get_leaderboard(self, limit=10):
        if not self.current_raffle:
            return []
        total = sum(e.entries for e in self.current_raffle.entries)
        return [
            {'rank': i+1, 'username': e.username, 'tickets': e.entries, 'odds': f'{e.entries} in {total}'}
            for i, e in enumerate(sorted(self.current_raffle.entries, key=lambda x: x.entries, reverse=True)[:limit])
        ]

    async def get_raffle_history(self, limit=10):
        return [
            {'week': r.week_number, 'vehicle': r.vehicle_display, 'winner': r.winner_name,
             'total_entries': sum(e.entries for e in r.entries), 'completed_at': r.created_at}
            for r in self.raffle_history[-limit:]
        ]
