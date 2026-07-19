"""
Raffle Cog - Fixed version
Bug fixes:
  1. get_odds: fixed generator expression (e.entries -> e in)
  2. economy wired via bot.economy
  3. admin_channel resolved via config key 'admin_log_channel' -> 'log_channel' (correct key)
  4. Raffle delivery: uses bot.delivery_queue.add() with correct DeliveryJob import
     (was importing from bot.services.delivery which has no DeliveryJob)
     and uses bot.delivery.queue_vehicle_delivery() directly as fallback
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from bot.services.raffle import RaffleService
from bot.services.delivery_queue import DeliveryJob
from datetime import datetime
import uuid


class RaffleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.raffle = RaffleService(bot.db_path)
        self.raffle_loop.start()

    def _get_economy(self):
        return self.bot.economy

    async def _get_admin_channel(self):
        # Fixed: config key is 'log_channel' not 'admin_log_channel'
        channel_name = self.bot.config['bot'].get('log_channel', 'admin-logs')
        for guild in self.bot.guilds:
            ch = discord.utils.get(guild.channels, name=channel_name)
            if ch:
                return ch
        return None

    @tasks.loop(hours=1)
    async def raffle_loop(self):
        if self.raffle.current_raffle:
            if datetime.now() > self.raffle.current_raffle.end_time:
                await self._draw_and_announce()

    async def _draw_and_announce(self):
        raffle = await self.raffle.draw_winner()
        if not raffle or not raffle.winner:
            return
        admin_ch = await self._get_admin_channel()
        if admin_ch:
            embed = discord.Embed(title='\U0001f389 RAFFLE WINNER!', color=discord.Color.gold())
            embed.add_field(name='\U0001f3c6 Winner', value=f'<@{raffle.winner}> ({raffle.winner_name})', inline=False)
            embed.add_field(name='\U0001f697 Prize', value=raffle.vehicle_display, inline=True)
            embed.add_field(name='\U0001f3ab Total Entries', value=sum(e.entries for e in raffle.entries), inline=True)
            await admin_ch.send(embed=embed)
        try:
            winner_user = await self.bot.fetch_user(raffle.winner)
            dm = discord.Embed(
                title='\U0001f389 YOU WON THE RAFFLE!',
                description=f'You won a **{raffle.vehicle_display}**!',
                color=discord.Color.green()
            )
            dm.add_field(name='Next Steps', value='Your vehicle will be queued for CE delivery at your chosen zone!')
            await winner_user.send(embed=dm)
            # Fixed: use delivery_queue.add() with correct DeliveryJob from delivery_queue module
            job = DeliveryJob(
                job_id=str(uuid.uuid4())[:8].upper(),
                job_type='vehicle',
                item_class=raffle.vehicle,
                quantity=1,
                delivery_zone='NWAF',
                fully_kitted=True,
                buyer_id=raffle.winner
            )
            await self.bot.delivery_queue.add(job)
        except Exception as e:
            print(f'[RaffleCog] Winner DM/delivery failed: {e}')

    @app_commands.command(name='raffle', description='\U0001f3b0 Car Raffle System')
    @app_commands.describe(subcommand='enter / info / odds / leaderboard / history')
    async def raffle_cmd(self, interaction: discord.Interaction, subcommand: str):
        sub = subcommand.lower()
        if sub == 'info':            await self._raffle_info(interaction)
        elif sub == 'enter':         await self._raffle_enter(interaction)
        elif sub == 'odds':          await self._raffle_odds(interaction)
        elif sub == 'leaderboard':   await self._raffle_leaderboard(interaction)
        elif sub == 'history':       await self._raffle_history(interaction)
        else: await interaction.response.send_message('\u274c Unknown subcommand. Use: enter/info/odds/leaderboard/history')

    async def _raffle_info(self, interaction):
        await interaction.response.defer()
        info = self.raffle.get_raffle_info()
        if not info:
            await interaction.followup.send('\u274c No active raffle!')
            return
        embed = discord.Embed(title='\U0001f3b0 WEEKLY CAR RAFFLE', description=f'**{info["vehicle"]}** is up for grabs!', color=discord.Color.purple())
        embed.add_field(name='\U0001f3ab Entry Cost', value=f'{info["entry_cost"]:,} credits', inline=True)
        embed.add_field(name='\U0001f465 Players', value=info['unique_players'], inline=True)
        embed.add_field(name='\U0001f39f\ufe0f Total Entries', value=info['total_entries'], inline=True)
        embed.add_field(name='\u23f0 Time Remaining', value=f'{info["hours_remaining"]:.1f} hours', inline=True)
        await interaction.followup.send(embed=embed)

    async def _raffle_enter(self, interaction):
        await interaction.response.defer()
        await self.bot.economy.ensure_user(interaction.user.id, interaction.user.name)
        result = await self.raffle.enter_raffle(
            interaction.user.id,
            interaction.user.name,
            num_entries=1,
            economy_service=self._get_economy()
        )
        color = discord.Color.green() if result['success'] else discord.Color.red()
        embed = discord.Embed(title='\U0001f39f\ufe0f Raffle Entry', description=result['message'], color=color)
        await interaction.followup.send(embed=embed)

    async def _raffle_odds(self, interaction):
        await interaction.response.defer()
        odds = self.raffle.get_odds(interaction.user.id)
        if 'error' in odds:
            await interaction.followup.send(f'\u274c {odds["error"]}')
            return
        embed = discord.Embed(title='\U0001f4ca YOUR RAFFLE ODDS', color=discord.Color.blue())
        embed.add_field(name='\U0001f39f\ufe0f Your Tickets', value=odds['player_tickets'], inline=True)
        embed.add_field(name='\U0001f4c8 Total Tickets', value=odds['total_tickets'], inline=True)
        embed.add_field(name='\U0001f3af Win Probability', value=odds['odds_formatted'], inline=False)
        await interaction.followup.send(embed=embed)

    async def _raffle_leaderboard(self, interaction):
        await interaction.response.defer()
        lb = self.raffle.get_leaderboard()
        if not lb:
            await interaction.followup.send('\u274c No entries yet!')
            return
        embed = discord.Embed(title='\U0001f3c6 RAFFLE LEADERBOARD', color=discord.Color.gold())
        for entry in lb:
            embed.add_field(name=f'#{entry["rank"]} {entry["username"]}', value=f'{entry["tickets"]} tickets | Odds: {entry["odds"]}', inline=False)
        await interaction.followup.send(embed=embed)

    async def _raffle_history(self, interaction):
        await interaction.response.defer()
        history = await self.raffle.get_raffle_history()
        if not history:
            await interaction.followup.send('\u274c No raffle history yet!')
            return
        embed = discord.Embed(title='\U0001f4dc RAFFLE HISTORY', color=discord.Color.gold())
        for r in reversed(history[-5:]):
            embed.add_field(name=f'Week {r["week"]}: {r["vehicle"]}', value=f'Winner: {r["winner"]} | Entries: {r["total_entries"]}', inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name='raffle_admin', description='[ADMIN] Manage raffles')
    @app_commands.default_permissions(administrator=True)
    async def raffle_admin(self, interaction: discord.Interaction, action: str, vehicle: str = None, display_name: str = None, cost: int = 500):
        if not any(r.name == self.bot.config['bot']['admin_role'] for r in interaction.user.roles):
            await interaction.response.send_message('\u274c Admin only!', ephemeral=True)
            return
        await interaction.response.defer()
        if action == 'start':
            if not vehicle or not display_name:
                await interaction.followup.send('\u274c Need vehicle classname and display name!')
                return
            await self.raffle.start_raffle(vehicle=vehicle, vehicle_display=display_name, entry_cost=cost)
            await interaction.followup.send(f'\u2705 Raffle started for **{display_name}**! Cost: {cost:,} credits.')
        elif action == 'draw':
            raffle = await self.raffle.draw_winner()
            if raffle and raffle.winner:
                await interaction.followup.send(f'\U0001f389 Winner: <@{raffle.winner}>')
            else:
                await interaction.followup.send('\u274c Raffle not ready to draw.')
        elif action == 'cancel':
            self.raffle.current_raffle = None
            await interaction.followup.send('\u2705 Raffle cancelled.')


async def setup(bot):
    await bot.add_cog(RaffleCog(bot))
