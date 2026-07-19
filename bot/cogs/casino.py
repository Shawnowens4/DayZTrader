"""
Casino Cog - Fixed version
Fix 1: Slots win condition corrected for 3-reel and 5-reel machines
Fix 2: Blackjack uses interactive View (Hit/Stand buttons) for real gameplay
Fix 3: Economy wired via bot.economy
Fix 4: Poker evaluator handles 7-card hand correctly
Fix 5: All game results now write to casino_games + upsert casino_stats tables
"""

import discord
from discord.ext import commands
from discord import app_commands
import random
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple
import asyncio
import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'trader.db')

# ─────────────────────────────────────────
class HandRank(Enum):
    HIGH_CARD = 1; ONE_PAIR = 2; TWO_PAIR = 3; THREE_OF_A_KIND = 4
    STRAIGHT = 5; FLUSH = 6; FULL_HOUSE = 7; FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9; ROYAL_FLUSH = 10

@dataclass
class Card:
    suit: str
    rank: str
    def __str__(self): return f'{self.rank}{self.suit}'
    @property
    def value(self):
        if self.rank in ['J','Q','K']: return 10
        elif self.rank == 'A': return 11
        else: return int(self.rank)
    @property
    def rank_index(self):
        return ['2','3','4','5','6','7','8','9','10','J','Q','K','A'].index(self.rank)

def _create_deck():
    return [Card(s, r) for s in ['\u2660','\u2665','\u2666','\u2663'] for r in ['2','3','4','5','6','7','8','9','10','J','Q','K','A']]

def _calc_bj_total(hand):
    total = sum(c.value for c in hand)
    aces = sum(1 for c in hand if c.rank == 'A')
    while total > 21 and aces:
        total -= 10; aces -= 1
    return total

def _evaluate_best_hand(cards: List[Card]) -> Tuple[HandRank, int]:
    from itertools import combinations
    best = (HandRank.HIGH_CARD, 0)
    for combo in combinations(cards, min(5, len(cards))):
        result = _eval_5(list(combo))
        if result[0].value > best[0].value or (result[0].value == best[0].value and result[1] > best[1]):
            best = result
    return best

def _eval_5(cards: List[Card]) -> Tuple[HandRank, int]:
    ranks = sorted([c.rank_index for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    counts = sorted(rank_counts.values(), reverse=True)
    is_flush = len(set(suits)) == 1
    is_straight = (len(rank_counts) == 5 and (ranks[0] - ranks[-1] == 4))
    if set([c.rank_index for c in cards]) == {12, 0, 1, 2, 3}:
        is_straight = True
    score = sum(r * (13 ** i) for i, r in enumerate(sorted(ranks)))
    if is_flush and is_straight:
        if ranks[0] == 12: return (HandRank.ROYAL_FLUSH, 1000)
        return (HandRank.STRAIGHT_FLUSH, 900 + ranks[0])
    if counts[0] == 4: return (HandRank.FOUR_OF_A_KIND, 800 + score)
    if counts[0] == 3 and counts[1] == 2: return (HandRank.FULL_HOUSE, 700 + score)
    if is_flush: return (HandRank.FLUSH, 600 + score)
    if is_straight: return (HandRank.STRAIGHT, 500 + ranks[0])
    if counts[0] == 3: return (HandRank.THREE_OF_A_KIND, 400 + score)
    if counts[0] == 2 and counts[1] == 2: return (HandRank.TWO_PAIR, 300 + score)
    if counts[0] == 2: return (HandRank.ONE_PAIR, 200 + score)
    return (HandRank.HIGH_CARD, 100 + score)


async def _record_game(discord_id: int, game_type: str, bet: int, winnings: int, result: str):
    """Write to casino_games and upsert casino_stats so /api/casino/stats is populated."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO casino_games (discord_id, game_type, bet_amount, winnings, result) VALUES (?,?,?,?,?)',
            (discord_id, game_type, bet, winnings, result)
        )
        # Upsert casino_stats
        await db.execute(
            '''
            INSERT INTO casino_stats (discord_id, total_bets, total_wagered, total_winnings,
                games_played, favorite_game, biggest_win, last_played)
            VALUES (?, 1, ?, MAX(0,?), 1, ?, MAX(0,?), CURRENT_TIMESTAMP)
            ON CONFLICT(discord_id) DO UPDATE SET
                total_bets     = total_bets + 1,
                total_wagered  = total_wagered + excluded.total_wagered,
                total_winnings = total_winnings + excluded.total_winnings,
                games_played   = games_played + 1,
                favorite_game  = excluded.favorite_game,
                biggest_win    = MAX(biggest_win, excluded.biggest_win),
                last_played    = CURRENT_TIMESTAMP
            ''',
            (discord_id, bet, winnings, game_type, winnings)
        )
        await db.commit()


# ─────────────────────────────────────────
# BLACKJACK INTERACTIVE VIEW
# ─────────────────────────────────────────

class BlackjackView(discord.ui.View):
    def __init__(self, player_hand, dealer_hand, deck, bet, user_id, economy):
        super().__init__(timeout=60)
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.deck = deck
        self.bet = bet
        self.user_id = user_id
        self.economy = economy
        self.done = False

    def _make_embed(self, title, color, reveal_dealer=False):
        embed = discord.Embed(title=title, color=color)
        embed.add_field(name=f'Your Hand ({_calc_bj_total(self.player_hand)})', value=' '.join(str(c) for c in self.player_hand), inline=False)
        if reveal_dealer:
            embed.add_field(name=f'Dealer Hand ({_calc_bj_total(self.dealer_hand)})', value=' '.join(str(c) for c in self.dealer_hand), inline=False)
        else:
            embed.add_field(name='Dealer Hand', value=f'{self.dealer_hand[0]} \u2753', inline=False)
        return embed

    @discord.ui.button(label='Hit', style=discord.ButtonStyle.green)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('Not your game!', ephemeral=True)
            return
        self.player_hand.append(self.deck.pop())
        total = _calc_bj_total(self.player_hand)
        if total > 21:
            self.done = True
            for item in self.children: item.disabled = True
            await self.economy.update_balance(self.user_id, -self.bet, 'Blackjack bust')
            await _record_game(self.user_id, 'blackjack', self.bet, 0, 'lose')
            embed = self._make_embed(f'\U0001f494 Bust! ({total})', discord.Color.red(), reveal_dealer=True)
            embed.add_field(name='\U0001f4b0 Result', value=f'-{self.bet:,} credits')
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=self._make_embed('\U0001f0cf Blackjack \u2014 Your turn', discord.Color.blue()), view=self)

    @discord.ui.button(label='Stand', style=discord.ButtonStyle.red)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('Not your game!', ephemeral=True)
            return
        self.done = True
        for item in self.children: item.disabled = True
        while _calc_bj_total(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
        p = _calc_bj_total(self.player_hand)
        d = _calc_bj_total(self.dealer_hand)
        if d > 21 or p > d:
            winnings = self.bet; msg = f'\U0001f389 You Win! ({p} vs {d})'; color = discord.Color.green(); res = 'win'
        elif p < d:
            winnings = -self.bet; msg = f'\U0001f494 Dealer Wins ({p} vs {d})'; color = discord.Color.red(); res = 'lose'
        else:
            winnings = 0; msg = f'\U0001f91d Push! ({p})'; color = discord.Color.greyple(); res = 'tie'
        await self.economy.update_balance(self.user_id, winnings, 'Blackjack stand')
        await _record_game(self.user_id, 'blackjack', self.bet, max(0, winnings), res)
        embed = self._make_embed(f'\U0001f3b0 BLACKJACK \u2014 {msg}', color, reveal_dealer=True)
        embed.add_field(name='\U0001f4b0 Result', value=f'{winnings:+,} credits')
        await interaction.response.edit_message(embed=embed, view=self)


# ─────────────────────────────────────────
# CASINO COG
# ─────────────────────────────────────────

class CasinoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _check_bet(self, interaction, amount, min_bet=100):
        await self.bot.economy.ensure_user(interaction.user.id, interaction.user.name)
        if await self.bot.security.is_banned(interaction.user.id):
            await interaction.followup.send('\u274c Banned.'); return False
        if amount < min_bet:
            await interaction.followup.send(f'\u274c Minimum bet is {min_bet:,} credits.'); return False
        bal = await self.bot.economy.get_balance(interaction.user.id)
        if bal < amount:
            await interaction.followup.send(f'\u274c Insufficient balance! You have {bal:,}.'); return False
        allowed, msg = await self.bot.security.check_rate_limit(interaction.user.id, 'casino', 10, 60)
        if not allowed:
            await interaction.followup.send(f'\u23f3 {msg}'); return False
        return True

    @app_commands.command(name='blackjack', description='Play interactive Blackjack vs Dealer')
    @app_commands.describe(amount='Bet amount (min 100)')
    async def blackjack(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        if not await self._check_bet(interaction, amount): return
        deck = _create_deck(); random.shuffle(deck)
        ph = [deck.pop(), deck.pop()]
        dh = [deck.pop(), deck.pop()]
        total = _calc_bj_total(ph)
        if total == 21:
            winnings = int(amount * 1.5)
            await self.bot.economy.update_balance(interaction.user.id, winnings, 'Blackjack natural')
            await _record_game(interaction.user.id, 'blackjack', amount, winnings, 'blackjack')
            embed = discord.Embed(title='\U0001f3b0 BLACKJACK! Natural 21!', color=discord.Color.gold())
            embed.add_field(name='Your Hand', value=' '.join(str(c) for c in ph))
            embed.add_field(name='\U0001f4b0 Result', value=f'+{winnings:,} credits')
            await interaction.followup.send(embed=embed)
            return
        view = BlackjackView(ph, dh, deck, amount, interaction.user.id, self.bot.economy)
        embed = discord.Embed(title='\U0001f0cf BLACKJACK \u2014 Your Turn', description='Hit or Stand?', color=discord.Color.blue())
        embed.add_field(name=f'Your Hand ({total})', value=' '.join(str(c) for c in ph), inline=False)
        embed.add_field(name='Dealer Hand', value=f'{dh[0]} \u2753', inline=False)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name='poker', description="Play Texas Hold'em vs AI")
    @app_commands.describe(amount='Bet amount', difficulty='easy/medium/hard')
    async def poker(self, interaction: discord.Interaction, amount: int, difficulty: str = 'medium'):
        await interaction.response.defer()
        if not await self._check_bet(interaction, amount): return
        deck = _create_deck(); random.shuffle(deck)
        player_hand = [deck.pop(), deck.pop()]
        ai_hand = [deck.pop(), deck.pop()]
        community = [deck.pop() for _ in range(5)]
        p_rank, p_score = _evaluate_best_hand(player_hand + community)
        a_rank, a_score = _evaluate_best_hand(ai_hand + community)
        mult = {'easy': 1.5, 'medium': 2.0, 'hard': 3.0}.get(difficulty, 2.0)
        if p_score > a_score:
            winnings = int(amount * mult); result_msg = f'\U0001f389 You Win! {p_rank.name} vs {a_rank.name}'
            color = discord.Color.green(); res = 'win'
        elif p_score < a_score:
            winnings = -amount; result_msg = f'\U0001f494 AI Wins! {a_rank.name} vs {p_rank.name}'
            color = discord.Color.red(); res = 'lose'
        else:
            winnings = 0; result_msg = f'\U0001f91d Split! Both {p_rank.name}'
            color = discord.Color.greyple(); res = 'tie'
        await self.bot.economy.update_balance(interaction.user.id, winnings, 'Poker')
        await _record_game(interaction.user.id, 'poker', amount, max(0, winnings), res)
        embed = discord.Embed(title="\U0001f0cf TEXAS HOLD'EM", description=result_msg, color=color)
        embed.add_field(name='Your Hand', value=' '.join(str(c) for c in player_hand), inline=True)
        embed.add_field(name='AI Hand', value=' '.join(str(c) for c in ai_hand), inline=True)
        embed.add_field(name='Community', value=' '.join(str(c) for c in community), inline=False)
        embed.add_field(name='\U0001f4b0 Result', value=f'{winnings:+,} credits')
        await interaction.followup.send(embed=embed)

    @app_commands.command(name='slots', description='Play Slot Machines')
    @app_commands.describe(amount='Bet amount', machine='classic/diamond/lucky/deluxe/mega')
    async def slots(self, interaction: discord.Interaction, amount: int, machine: str = 'classic'):
        await interaction.response.defer()
        if not await self._check_bet(interaction, amount): return
        machines = {
            'classic': {'symbols': ['\U0001f352','\U0001f34b','\U0001f34a','\U0001f514','\U0001f48e'], 'reels': 3, 'mult': 2.0, 'emoji': '\U0001f3b0'},
            'diamond': {'symbols': ['\U0001f48e','\U0001f451','\u2b50','\U0001f3c6','\U0001f4b0'], 'reels': 3, 'mult': 2.5, 'emoji': '\U0001f48e'},
            'lucky':   {'symbols': ['\U0001f340','\U0001f3b4','\U0001f3b2','\U0001f3af','\U0001f31f'], 'reels': 3, 'mult': 2.2, 'emoji': '\U0001f340'},
            'deluxe':  {'symbols': ['\U0001f3ad','\U0001f3aa','\U0001f3a8','\U0001f3ac','\U0001f3a4'], 'reels': 5, 'mult': 3.0, 'emoji': '\U0001f3ad'},
            'mega':    {'symbols': ['\U0001f534','\U0001f7e0','\U0001f7e1','\U0001f7e2','\U0001f535'], 'reels': 5, 'mult': 3.5, 'emoji': '\U0001f3af'}
        }
        m = machines.get(machine, machines['classic'])
        result = [random.choice(m['symbols']) for _ in range(m['reels'])]
        counts = {s: result.count(s) for s in set(result)}
        max_match = max(counts.values())
        if max_match == m['reels']:
            winnings = int(amount * m['mult'] * 5); win_type = '\U0001f38a JACKPOT!'; res = 'jackpot'
        elif max_match >= 3:
            winnings = int(amount * m['mult']); win_type = '\u2728 WINNER!'; res = 'win'
        else:
            winnings = -amount; win_type = '\u274c Try Again'; res = 'lose'
        await self.bot.economy.update_balance(interaction.user.id, winnings, f'Slots {machine}')
        await _record_game(interaction.user.id, 'slots', amount, max(0, winnings), res)
        embed = discord.Embed(title='\U0001f3b0 SLOT MACHINE', description=f'{m["emoji"]} {win_type}\n{" | ".join(result)}', color=discord.Color.yellow())
        embed.add_field(name='Machine', value=machine.upper(), inline=True)
        embed.add_field(name='Multiplier', value=f'{m["mult"]}x', inline=True)
        embed.add_field(name='\U0001f4b0 Result', value=f'{winnings:+,} credits')
        await interaction.followup.send(embed=embed)

    @app_commands.command(name='roulette', description='Play Roulette')
    @app_commands.describe(amount='Bet amount', bet_type='number/color/odd_even/high_low', bet_value='e.g. 17, red, odd, high')
    async def roulette(self, interaction: discord.Interaction, amount: int, bet_type: str = 'color', bet_value: str = 'red'):
        await interaction.response.defer()
        if not await self._check_bet(interaction, amount): return
        winning_number = random.randint(0, 36)
        red_numbers = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        is_red = winning_number in red_numbers
        is_odd = winning_number % 2 == 1
        win = False; multiplier = 1
        if bet_type == 'number':   win = str(winning_number) == bet_value; multiplier = 36
        elif bet_type == 'color':  win = (bet_value == 'red' and is_red) or (bet_value == 'black' and not is_red and winning_number != 0); multiplier = 2
        elif bet_type == 'odd_even': win = (bet_value == 'odd' and is_odd) or (bet_value == 'even' and not is_odd and winning_number != 0); multiplier = 2
        elif bet_type == 'high_low': win = (bet_value == 'high' and 19 <= winning_number <= 36) or (bet_value == 'low' and 1 <= winning_number <= 18); multiplier = 2
        winnings = amount * multiplier if win else -amount
        color_emoji = '\U0001f534' if is_red else ('\u26ab' if winning_number != 0 else '\U0001f7e2')
        res = 'win' if win else 'lose'
        await self.bot.economy.update_balance(interaction.user.id, winnings, 'Roulette')
        await _record_game(interaction.user.id, 'roulette', amount, max(0, winnings), res)
        embed = discord.Embed(
            title='\U0001f3b2 ROULETTE',
            description=f'The ball landed on {color_emoji} **{winning_number}**',
            color=discord.Color.green() if win else discord.Color.red()
        )
        embed.add_field(name='Your Bet', value=f'{bet_type}: {bet_value}', inline=True)
        embed.add_field(name='Multiplier', value=f'{multiplier}x', inline=True)
        embed.add_field(name='\U0001f4b0 Result', value=f'{winnings:+,} credits')
        await interaction.followup.send(embed=embed)

    @app_commands.command(name='horse_race', description='Bet on a horse race')
    @app_commands.describe(amount='Bet amount', horse='Horse number 1-8')
    async def horse_race(self, interaction: discord.Interaction, amount: int, horse: int = 1):
        await interaction.response.defer()
        if not await self._check_bet(interaction, amount): return
        horses = {
            1: '\U0001f40e Thunder', 2: '\U0001f434 Lightning', 3: '\U0001f40e Midnight',
            4: '\U0001f434 Blaze',   5: '\U0001f40e Spirit',   6: '\U0001f434 Comet',
            7: '\U0001f40e Storm',   8: '\U0001f434 Victory'
        }
        if horse not in horses:
            await interaction.followup.send('\u274c Choose horse 1-8.'); return
        winner = random.randint(1, 8)
        win = winner == horse
        winnings = amount * 5 if win else -amount
        res = 'win' if win else 'lose'
        await self.bot.economy.update_balance(interaction.user.id, winnings, 'Horse race')
        await _record_game(interaction.user.id, 'horse_race', amount, max(0, winnings), res)
        embed = discord.Embed(
            title='\U0001f3c7 HORSE RACE',
            description=f'{horses[winner]} wins! You bet on {horses[horse]}.',
            color=discord.Color.green() if win else discord.Color.red()
        )
        embed.add_field(name='Result', value='\U0001f3c6 WINNER! 5x payout' if win else '\U0001f494 Better luck next time')
        embed.add_field(name='\U0001f4b0 Credits', value=f'{winnings:+,}')
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CasinoCog(bot))
