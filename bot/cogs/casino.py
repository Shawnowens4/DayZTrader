"""
Casino Cog - Fixed version
Fix 1: Slots win condition corrected for 3-reel and 5-reel machines
Fix 2: Blackjack uses interactive View (Hit/Stand buttons) for real gameplay
Fix 3: Economy wired via bot.economy (not cog_load)
Fix 4: Poker evaluator handles 7-card hand correctly
"""

import discord
from discord.ext import commands
from discord import app_commands
import random
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple
import asyncio

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
    """Evaluate best 5-card hand from up to 7 cards (poker fix)."""
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
    # Ace-low straight
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

# ─────────────────────────────────────────
# BLACKJACK INTERACTIVE VIEW (Fix 2)
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
            await interaction.client.economy.update_balance(self.user_id, -self.bet, 'Blackjack bust')
            embed = self._make_embed(f'💔 Bust! ({total})', discord.Color.red(), reveal_dealer=True)
            embed.add_field(name='💰 Result', value=f'-{self.bet:,} credits')
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=self._make_embed('🃏 Blackjack — Your turn', discord.Color.blue()), view=self)

    @discord.ui.button(label='Stand', style=discord.ButtonStyle.red)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('Not your game!', ephemeral=True)
            return
        self.done = True
        for item in self.children: item.disabled = True
        # Dealer plays
        while _calc_bj_total(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
        p = _calc_bj_total(self.player_hand)
        d = _calc_bj_total(self.dealer_hand)
        if d > 21 or p > d:
            winnings = self.bet
            msg = f'🎉 You Win! ({p} vs {d})'
            color = discord.Color.green()
        elif p < d:
            winnings = -self.bet
            msg = f'💔 Dealer Wins ({p} vs {d})'
            color = discord.Color.red()
        else:
            winnings = 0
            msg = f'🤝 Push! ({p})'
            color = discord.Color.greyple()
        await interaction.client.economy.update_balance(self.user_id, winnings, 'Blackjack stand')
        embed = self._make_embed(f'🎰 BLACKJACK — {msg}', color, reveal_dealer=True)
        embed.add_field(name='💰 Result', value=f'{winnings:+,} credits')
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
            await interaction.followup.send('❌ Banned.'); return False
        if amount < min_bet:
            await interaction.followup.send(f'❌ Minimum bet is {min_bet:,} credits.'); return False
        bal = await self.bot.economy.get_balance(interaction.user.id)
        if bal < amount:
            await interaction.followup.send(f'❌ Insufficient balance! You have {bal:,}.'); return False
        allowed, msg = await self.bot.security.check_rate_limit(interaction.user.id, 'casino', 10, 60)
        if not allowed:
            await interaction.followup.send(f'⏳ {msg}'); return False
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
            embed = discord.Embed(title='🎰 BLACKJACK! Natural 21!', color=discord.Color.gold())
            embed.add_field(name='Your Hand', value=' '.join(str(c) for c in ph))
            embed.add_field(name='💰 Result', value=f'+{winnings:,} credits')
            await interaction.followup.send(embed=embed)
            return
        view = BlackjackView(ph, dh, deck, amount, interaction.user.id, self.bot.economy)
        embed = discord.Embed(title='🃏 BLACKJACK — Your Turn', description='Hit or Stand?', color=discord.Color.blue())
        embed.add_field(name=f'Your Hand ({total})', value=' '.join(str(c) for c in ph), inline=False)
        embed.add_field(name='Dealer Hand', value=f'{dh[0]} ❓', inline=False)
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
        # BUG FIX: use _evaluate_best_hand on all 7 cards
        p_rank, p_score = _evaluate_best_hand(player_hand + community)
        a_rank, a_score = _evaluate_best_hand(ai_hand + community)
        mult = {'easy': 1.5, 'medium': 2.0, 'hard': 3.0}.get(difficulty, 2.0)
        if p_score > a_score:
            winnings = int(amount * mult); result_msg = f'🎉 You Win! {p_rank.name} vs {a_rank.name}'
            color = discord.Color.green()
        elif p_score < a_score:
            winnings = -amount; result_msg = f'💔 AI Wins! {a_rank.name} vs {p_rank.name}'
            color = discord.Color.red()
        else:
            winnings = 0; result_msg = f'🤝 Split! Both {p_rank.name}'
            color = discord.Color.greyple()
        await self.bot.economy.update_balance(interaction.user.id, winnings, 'Poker')
        embed = discord.Embed(title="🃏 TEXAS HOLD'EM", description=result_msg, color=color)
        embed.add_field(name='Your Hand', value=' '.join(str(c) for c in player_hand), inline=True)
        embed.add_field(name='AI Hand', value=' '.join(str(c) for c in ai_hand), inline=True)
        embed.add_field(name='Community', value=' '.join(str(c) for c in community), inline=False)
        embed.add_field(name='💰 Result', value=f'{winnings:+,} credits')
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
        # BUG FIX: require 3+ match for win, all-match for jackpot (both 3 and 5 reel)
        if max_match == m['reels']:  # All match
            winnings = int(amount * m['mult'] * 5)
            win_type = '\U0001f38a JACKPOT!'
        elif max_match >= 3:         # 3+ match on any reel count
            winnings = int(amount * m['mult'])
            win_type = '\u2728 WINNER!'
        else:
            winnings = -amount
            win_type = '\u274c Try Again'
        await self.bot.economy.update_balance(interaction.user.id, winnings, f'Slots {machine}')
        embed = discord.Embed(title='\U0001f3b0 SLOT MACHINE', description=f'{m["emoji"]} {win_type}\n{" | ".join(result)}', color=discord.Color.yellow())
        embed.add_field(name='Machine', value=f'{machine.upper()}', inline=True)
        embed.add_field(name='Multiplier', value=f'{m["mult"]}x', inline=True)
        embed.add_field(name='\U0001f4b0 Result', value=f'{winnings:+,} credits')
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CasinoCog(bot))
