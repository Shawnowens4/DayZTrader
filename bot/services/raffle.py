"""
Raffle Service - FIXED VERSION
Fixed bugs: get_odds iterator, economy wiring
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum

class RaffleStatus(Enum):
    INACTIVE = "inactive"
    OPEN     = "open"
    DRAWING  = "drawing"
    COMPLETE = "complete"

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
    def __init__(self, db=None):
        self.db = db
        self.current_raffle: Optional[RaffleRound] = None
        self.raffle_history: List[RaffleRound] = []

    async def start_raffle(
        self,
        vehicle: str,
        vehicle_display: str,
        entry_cost: int = 500,
        duration_hours: int = 168,
        max_entries: int = 10
    ) -> RaffleRound:
        now = datetime.now()
        end_time = now + timedelta(hours=duration_hours)
        week_number = now.isocalendar()[1]

        raffle = RaffleRound(
            week_number=week_number,
            vehicle=vehicle,
            vehicle_display=vehicle_display,
            entry_cost=entry_cost,
            max_entries_per_player=max_entries,
            start_time=now,
            end_time=end_time,
            status=RaffleStatus.OPEN
        )
        self.current_raffle = raffle
        return raffle

    async def enter_raffle(
        self,
        user_id: int,
        username: str,
        num_entries: int = 1,
        economy_service=None
    ) -> Dict:
        if not self.current_raffle:
            return {'success': False, 'message': 'No active raffle at the moment!'}
        if self.current_raffle.status != RaffleStatus.OPEN:
            return {'success': False, 'message': f'Raffle is {self.current_raffle.status.value}'}
        if datetime.now() > self.current_raffle.end_time:
            return {'success': False, 'message': 'Raffle has ended!'}

        existing_entries = sum(
            e.entries for e in self.current_raffle.entries if e.user_id == user_id
        )
        if existing_entries + num_entries > self.current_raffle.max_entries_per_player:
            remaining = self.current_raffle.max_entries_per_player - existing_entries
            return {'success': False, 'message': f'Max entries is {self.current_raffle.max_entries_per_player}. You have {remaining} remaining.'}

        total_cost = self.current_raffle.entry_cost * num_entries

        if economy_service:
            balance = await economy_service.get_balance(user_id)
            if balance < total_cost:
                return {'success': False, 'message': f'Need {total_cost} credits, you have {balance}'}
            await economy_service.update_balance(user_id, -total_cost, f'Raffle entry x{num_entries}')

        existing = next((e for e in self.current_raffle.entries if e.user_id == user_id), None)
        if existing:
            existing.entries += num_entries
        else:
            self.current_raffle.entries.append(RaffleEntry(user_id, username, num_entries))

        total_entries = sum(e.entries for e in self.current_raffle.entries if e.user_id == user_id)
        return {
            'success': True,
            'message': f'You entered the raffle! Tickets: {num_entries} | Cost: {total_cost} credits | Total tickets: {total_entries}',
            'remaining_tickets': self.current_raffle.max_entries_per_player - total_entries
        }

    async def draw_winner(self) -> Optional[RaffleRound]:
        if not self.current_raffle:
            return None
        if self.current_raffle.status == RaffleStatus.COMPLETE:
            return self.current_raffle

        self.current_raffle.status = RaffleStatus.DRAWING

        raffle_pool = []
        for entry in self.current_raffle.entries:
            raffle_pool.extend([entry.user_id] * entry.entries)

        if not raffle_pool:
            self.current_raffle.status = RaffleStatus.COMPLETE
            return self.current_raffle

        winner_id = random.choice(raffle_pool)
        winner_entry = next((e for e in self.current_raffle.entries if e.user_id == winner_id), None)
        if winner_entry:
            self.current_raffle.winner = winner_entry.user_id
            self.current_raffle.winner_name = winner_entry.username

        self.current_raffle.status = RaffleStatus.COMPLETE
        self.raffle_history.append(self.current_raffle)
        return self.current_raffle

    def get_raffle_info(self) -> Optional[Dict]:
        if not self.current_raffle:
            return None
        time_remaining = self.current_raffle.end_time - datetime.now()
        hours_remaining = time_remaining.total_seconds() / 3600
        total_entries = sum(e.entries for e in self.current_raffle.entries)
        unique_players = len(self.current_raffle.entries)
        return {
            'vehicle': self.current_raffle.vehicle_display,
            'status': self.current_raffle.status.value,
            'entry_cost': self.current_raffle.entry_cost,
            'total_entries': total_entries,
            'unique_players': unique_players,
            'hours_remaining': max(0, hours_remaining),
            'max_entries_per_player': self.current_raffle.max_entries_per_player,
            'end_time': self.current_raffle.end_time
        }

    def get_player_entries(self, user_id: int) -> int:
        if not self.current_raffle:
            return 0
        entry = next((e for e in self.current_raffle.entries if e.user_id == user_id), None)
        return entry.entries if entry else 0

    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        if not self.current_raffle:
            return []
        sorted_entries = sorted(self.current_raffle.entries, key=lambda e: e.entries, reverse=True)[:limit]
        total = sum(e.entries for e in self.current_raffle.entries)
        return [
            {
                'rank': idx + 1,
                'username': entry.username,
                'tickets': entry.entries,
                'odds': f"{entry.entries} in {total}"
            }
            for idx, entry in enumerate(sorted_entries)
        ]

    # BUG FIX: was "for e.entries in ..." — now correctly "for e in ..."
    def get_odds(self, user_id: int) -> Dict:
        if not self.current_raffle:
            return {'error': 'No active raffle'}
        player_tickets = self.get_player_entries(user_id)
        total_tickets = sum(e.entries for e in self.current_raffle.entries)  # FIXED
        if total_tickets == 0:
            return {'player_tickets': 0, 'total_tickets': 0, 'odds_percent': 0, 'odds_formatted': '0.00%'}
        odds_percent = (player_tickets / total_tickets) * 100
        return {
            'player_tickets': player_tickets,
            'total_tickets': total_tickets,
            'odds_percent': odds_percent,
            'odds_formatted': f"{odds_percent:.2f}%"
        }

    async def get_raffle_history(self, limit: int = 10) -> List[Dict]:
        return [
            {
                'week': raffle.week_number,
                'vehicle': raffle.vehicle_display,
                'winner': raffle.winner_name,
                'total_entries': sum(e.entries for e in raffle.entries),
                'completed_at': raffle.created_at
            }
            for raffle in self.raffle_history[-limit:]
        ]
