"""
Casino Service - FIXED VERSION
Fixed: slots win conditions for 5-reel, poker hand eval bug, blackjack flow
"""

import random
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

class HandRank(Enum):
    HIGH_CARD      = 1
    ONE_PAIR       = 2
    TWO_PAIR       = 3
    THREE_OF_A_KIND= 4
    STRAIGHT       = 5
    FLUSH          = 6
    FULL_HOUSE     = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH    = 10

@dataclass
class Card:
    suit: str
    rank: str

    def __str__(self):
        return f"{self.rank}{self.suit}"

    @property
    def value(self) -> int:
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 11
        else:
            return int(self.rank)

class CasinoService:
    def __init__(self):
        self.active_games = {}

    def _create_deck(self) -> List[Card]:
        suits = ['\u2660', '\u2665', '\u2666', '\u2663']
        ranks = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
        return [Card(suit, rank) for suit in suits for rank in ranks]

    def _fresh_shuffled_deck(self) -> List[Card]:
        deck = self._create_deck()
        random.shuffle(deck)
        return deck

    # ==================== POKER ====================

    def play_poker(self, player_bet: int, difficulty: str = 'medium') -> dict:
        deck = self._fresh_shuffled_deck()
        player_hand = [deck.pop(), deck.pop()]
        ai_hand     = [deck.pop(), deck.pop()]
        community   = [deck.pop() for _ in range(5)]

        # Evaluate best 5 from 7 cards
        player_rank, player_score = self._best_hand(player_hand + community)
        ai_rank, ai_score         = self._best_hand(ai_hand + community)

        if player_score > ai_score:
            mult = self._poker_multiplier(difficulty)
            winnings = int(player_bet * mult)
            result, message = 'win', f'You Win! Your {player_rank.name} beats AI {ai_rank.name}! (x{mult})'
        elif player_score < ai_score:
            winnings = -player_bet
            result, message = 'lose', f'AI Wins! Their {ai_rank.name} beats your {player_rank.name}'
        else:
            winnings = 0
            result, message = 'tie', f'Split Pot! Both have {player_rank.name}'

        return {
            'game': 'poker', 'result': result, 'winnings': winnings, 'message': message,
            'player_hand': [str(c) for c in player_hand],
            'ai_hand': [str(c) for c in ai_hand],
            'community': [str(c) for c in community],
            'player_rank': player_rank.name, 'ai_rank': ai_rank.name
        }

    def _best_hand(self, seven_cards: List[Card]) -> Tuple[HandRank, int]:
        """Evaluate best 5-card hand from up to 7 cards"""
        from itertools import combinations
        best_rank = HandRank.HIGH_CARD
        best_score = 0
        for five in combinations(seven_cards, 5):
            rank, score = self._evaluate_five(list(five))
            if score > best_score:
                best_score = score
                best_rank = rank
        return best_rank, best_score

    def _evaluate_five(self, cards: List[Card]) -> Tuple[HandRank, int]:
        rank_order = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
        ranks  = [c.rank for c in cards]
        suits  = [c.suit for c in cards]
        values = sorted([rank_order.index(r) for r in ranks], reverse=True)
        rank_counts = {r: ranks.count(r) for r in set(ranks)}
        counts = sorted(rank_counts.values(), reverse=True)
        is_flush    = len(set(suits)) == 1
        is_straight = (max(values) - min(values) == 4) and len(set(values)) == 5

        if is_flush and is_straight:
            if min(values) == 8:  # 10-A
                return HandRank.ROYAL_FLUSH, 10000
            return HandRank.STRAIGHT_FLUSH, 9000 + max(values)
        if counts[0] == 4: return HandRank.FOUR_OF_A_KIND,  8000 + max(values)
        if counts[0] == 3 and counts[1] == 2: return HandRank.FULL_HOUSE, 7000 + max(values)
        if is_flush:   return HandRank.FLUSH,    6000 + max(values)
        if is_straight:return HandRank.STRAIGHT, 5000 + max(values)
        if counts[0] == 3: return HandRank.THREE_OF_A_KIND, 4000 + max(values)
        if counts[0] == 2 and counts[1] == 2: return HandRank.TWO_PAIR, 3000 + max(values)
        if counts[0] == 2: return HandRank.ONE_PAIR, 2000 + max(values)
        return HandRank.HIGH_CARD, 1000 + max(values)

    def _poker_multiplier(self, difficulty: str) -> float:
        return {'easy': 1.5, 'medium': 2.0, 'hard': 3.0}.get(difficulty, 2.0)

    # ==================== BLACKJACK ====================

    def deal_blackjack(self, player_bet: int) -> dict:
        """Deal initial blackjack hands - returns state for interactive play"""
        deck = self._fresh_shuffled_deck()
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
        player_total = self._bj_total(player_hand)
        dealer_total = self._bj_total(dealer_hand)

        state = {
            'deck': [str(c) for c in deck],
            'player_hand': [str(c) for c in player_hand],
            'dealer_hand': [str(c) for c in dealer_hand],
            'player_total': player_total,
            'dealer_show': dealer_hand[0].rank + dealer_hand[0].suit,
            'bet': player_bet,
            'done': False
        }
        # Natural blackjack check
        if player_total == 21:
            state['done'] = True
            state['result'] = 'blackjack'
            state['winnings'] = int(player_bet * 2.5)
            state['message'] = 'BLACKJACK! Natural 21!'
        return state

    def blackjack_stand(self, state: dict) -> dict:
        """Resolve dealer play after player stands"""
        deck = self._fresh_shuffled_deck()  # New deck for dealer draw
        dealer_cards = [Card(c[-1], c[:-1]) for c in state['dealer_hand']]
        player_total = state['player_total']
        dealer_total = self._bj_total(dealer_cards)

        while dealer_total < 17:
            card = deck.pop()
            dealer_cards.append(card)
            dealer_total = self._bj_total(dealer_cards)

        bet = state['bet']
        if dealer_total > 21:
            result, winnings, msg = 'win', bet * 2, f'Dealer Bust! You win! ({player_total} vs {dealer_total})'
        elif player_total > dealer_total:
            result, winnings, msg = 'win', bet * 2, f'You Win! ({player_total} vs {dealer_total})'
        elif player_total < dealer_total:
            result, winnings, msg = 'lose', -bet, f'Dealer Wins. ({player_total} vs {dealer_total})'
        else:
            result, winnings, msg = 'tie', 0, f'Push! Both have {player_total}'

        state.update({'done': True, 'result': result, 'winnings': winnings, 'message': msg,
                      'dealer_hand': [str(c) for c in dealer_cards], 'dealer_total': dealer_total})
        return state

    def _bj_total(self, hand) -> int:
        total = sum(c.value for c in hand)
        aces  = sum(1 for c in hand if c.rank == 'A')
        while total > 21 and aces:
            total -= 10
            aces  -= 1
        return total

    # ==================== SLOTS (FIXED) ====================

    def play_slots(self, player_bet: int, machine_type: str = 'classic') -> dict:
        machines = {
            'classic': {'symbols': ['\U0001f352','\U0001f34b','\U0001f34a','\U0001f514','\U0001f48e'], 'reels': 3, 'multiplier': 2.0, 'emoji': '\U0001f3b0'},
            'diamond': {'symbols': ['\U0001f48e','\U0001f451','\u2b50','\U0001f3c6','\U0001f4b0'], 'reels': 3, 'multiplier': 2.5, 'emoji': '\U0001f48e'},
            'lucky':   {'symbols': ['\U0001f340','\U0001f3b4','\U0001f3b2','\U0001f3af','\U0001f31f'], 'reels': 3, 'multiplier': 2.2, 'emoji': '\U0001f340'},
            'deluxe':  {'symbols': ['\U0001f3ad','\U0001f3aa','\U0001f3a8','\U0001f3ac','\U0001f3a4'], 'reels': 5, 'multiplier': 3.0, 'emoji': '\U0001f3ad'},
            'mega':    {'symbols': ['\U0001f534','\U0001f7e0','\U0001f7e1','\U0001f7e2','\U0001f535'], 'reels': 5, 'multiplier': 3.5, 'emoji': '\U0001f3af'},
        }
        machine = machines.get(machine_type, machines['classic'])
        result = [random.choice(machine['symbols']) for _ in range(machine['reels'])]
        reels  = machine['reels']

        # FIXED win conditions - account for reel count properly
        from collections import Counter
        counts = Counter(result)
        max_match = counts.most_common(1)[0][1]

        if max_match == reels:  # All match - JACKPOT
            winnings   = int(player_bet * machine['multiplier'] * 5)
            win_type   = 'JACKPOT!'
            result_type = 'jackpot'
        elif (reels == 3 and max_match >= 2) or (reels == 5 and max_match >= 3):  # Partial match
            winnings   = int(player_bet * machine['multiplier'])
            win_type   = 'WINNER!'
            result_type = 'win'
        else:
            winnings   = -player_bet
            win_type   = 'Try Again'
            result_type = 'lose'

        return {
            'game': 'slots', 'type': machine_type, 'result': result_type,
            'winnings': winnings, 'reels': result,
            'message': f"{machine['emoji']} {win_type}\n{' | '.join(result)}",
            'machine': machine['emoji'], 'multiplier': machine['multiplier']
        }

    # ==================== ROULETTE ====================

    def play_roulette(self, player_bet: int, bet_type: str, bet_value: str) -> dict:
        winning_number = random.randint(0, 36)
        red_numbers = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        is_red = winning_number in red_numbers
        is_odd = winning_number % 2 == 1

        win = False
        multiplier = 1

        if bet_type == 'number':
            win = str(winning_number) == bet_value
            multiplier = 36
        elif bet_type == 'color':
            win = (bet_value == 'red' and is_red) or (bet_value == 'black' and not is_red and winning_number != 0)
            multiplier = 2
        elif bet_type == 'odd_even':
            win = (bet_value == 'odd' and is_odd) or (bet_value == 'even' and not is_odd and winning_number != 0)
            multiplier = 2
        elif bet_type == 'high_low':
            win = (bet_value == 'high' and 19 <= winning_number <= 36) or (bet_value == 'low' and 1 <= winning_number <= 18)
            multiplier = 2

        winnings = player_bet * multiplier if win else -player_bet
        color_emoji = '\U0001f534' if is_red else ('\u26ab' if winning_number != 0 else '\U0001f7e2')

        return {
            'game': 'roulette', 'result': 'win' if win else 'lose', 'winnings': winnings,
            'winning_number': winning_number,
            'message': f'The ball landed on {color_emoji} {winning_number}! {"YOU WIN!" if win else "Better luck next time"}',
            'bet_type': bet_type, 'bet_value': bet_value,
            'color': '\U0001f534 Red' if is_red else ('\u26ab Black' if winning_number != 0 else '\U0001f7e2 Green'),
            'multiplier': multiplier
        }

    # ==================== HORSE RACING ====================

    def play_horse_race(self, player_bet: int, horse_number: int) -> dict:
        horses = {
            1: '\U0001f40e Thunder', 2: '\U0001f434 Lightning', 3: '\U0001f40e Midnight',
            4: '\U0001f434 Blaze',   5: '\U0001f40e Spirit',   6: '\U0001f434 Comet',
            7: '\U0001f40e Storm',   8: '\U0001f434 Victory'
        }
        if horse_number not in horses:
            return {'game': 'horse_race', 'result': 'error', 'message': 'Invalid horse number (1-8)'}

        winning_horse = random.randint(1, 8)
        if winning_horse == horse_number:
            winnings = player_bet * 5
            result   = 'win'
            message  = f'WINNER! {horses[horse_number]} crosses first!'
        else:
            winnings = -player_bet
            result   = 'lose'
            message  = f'{horses[winning_horse]} wins! Better luck next time.'

        return {
            'game': 'horse_race', 'result': result, 'winnings': winnings,
            'horse_bet': horses[horse_number], 'winning_horse': horses[winning_horse],
            'message': message
        }
