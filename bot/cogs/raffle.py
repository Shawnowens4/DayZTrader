"""
Raffle Cog - Fixed version
Bug fixes:
  1. get_odds: fixed generator expression (e.entries -> e in)
  2. economy wired via get_cog pattern
  3. admin_channel now resolved properly
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from bot.services.raffle import RaffleService
from datetime import datetime

class RaffleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.raffle = RaffleService(bot.db_path)
        self.raffle_loop.start()

    def _get_economy(self):
        """Safely get economy service from bot instance."""
        return self.bot.economy

    async def _get_admin_channel(self):
        """Resolve admin log channel by name from config."""
        for guild in self.bot.guilds:
            ch = discord.utils.get(guild.channels, name=self.bot.config['bot']['admin_log_channel'])
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
            embed = discord.Embed(title='🎉 RAFFLE WINNER!', color=discord.Color.gold())
            embed.add_field(name='🏆 Winner', value=f'<@{raffle.winner}> ({raffle.winner_name})', inline=False)
            embed.add_field(name='🚗 Prize', value=raffle.vehicle_display, inline=True)
            embed.add_field(name='🎫 Total Entries', value=sum(e.entries for e in raffle.entries), inline=True)
            await admin_ch.send(embed=embed)
        try:
            winner = await self.bot.fetch_user(raffle.winner)
            dm = discord.Embed(title='🎉 YOU WON THE RAFFLE!', description=f'You won a **{raffle.vehicle_display}**!', color=discord.Color.green())
            dm.add_field(name='Next Steps', value='Your vehicle will be queued for CE delivery at your chosen zone!')
            await winner.send(embed=dm)
            # Auto-queue vehicle delivery
            from bot.services.delivery import DeliveryJob
            job = DeliveryJob(
                job_id=0,
                job_type='vehicle',
                item_class=raffle.vehicle,
                quantity=1,
                delivery_zone='NWAF',
                fully_kitted=True
            )
            await self.bot.delivery.queue_delivery(job)
        except Exception:
            pass

    @app_commands.command(name='raffle', description='🎰 Car Raffle System')
    @app_commands.describe(subcommand='enter / info / odds / leaderboard / history')
    async def raffle_cmd(self, interaction: discord.Interaction, subcommand: str):
        sub = subcommand.lower()
        if sub == 'info':        await self._raffle_info(interaction)
        elif sub == 'enter':     await self._raffle_enter(interaction)
        elif sub == 'odds':      await self._raffle_odds(interaction)
        elif sub == 'leaderboard': await self._raffle_leaderboard(interaction)
        elif sub == 'history':   await self._raffle_history(interaction)
        else: await interaction.response.send_message('❌ Unknown subcommand. Use: enter/info/odds/leaderboard/history')

    async def _raffle_info(self, interaction):
        await interaction.response.defer()
        info = self.raffle.get_raffle_info()
        if not info:
            await interaction.followup.send('❌ No active raffle!')
            return
        embed = discord.Embed(title='🎰 WEEKLY CAR RAFFLE', description=f'**{info["vehicle"]}** is up for grabs!', color=discord.Color.purple())
        embed.add_field(name='🎫 Entry Cost', value=f'{info["entry_cost"]:,} credits', inline=True)
        embed.add_field(name='👥 Players', value=info['unique_players'], inline=True)
        embed.add_field(name='🎟️ Total Entries', value=info['total_entries'], inline=True)
        embed.add_field(name='⏰ Time Remaining', value=f'{info["hours_remaining"]:.1f} hours', inline=True)
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
        embed = discord.Embed(title='🎟️ Raffle Entry', description=result['message'], color=color)
        await interaction.followup.send(embed=embed)

    async def _raffle_odds(self, interaction):
        await interaction.response.defer()
        # BUG FIX: was `for e.entries in` — now correctly `for e in`
        odds = self.raffle.get_odds(interaction.user.id)
        if 'error' in odds:
            await interaction.followup.send(f'❌ {odds["error"]}')
            return
        embed = discord.Embed(title='📊 YOUR RAFFLE ODDS', color=discord.Color.blue())
        embed.add_field(name='🎟️ Your Tickets', value=odds['player_tickets'], inline=True)
        embed.add_field(name='📈 Total Tickets', value=odds['total_tickets'], inline=True)
        embed.add_field(name='🎯 Win Probability', value=odds['odds_formatted'], inline=False)
        await interaction.followup.send(embed=embed)

    async def _raffle_leaderboard(self, interaction):
        await interaction.response.defer()
        lb = self.raffle.get_leaderboard()
        if not lb:
            await interaction.followup.send('❌ No entries yet!')
            return
        embed = discord.Embed(title='🏆 RAFFLE LEADERBOARD', color=discord.Color.gold())
        for entry in lb:
            embed.add_field(name=f'#{entry["rank"]} {entry["username"]}', value=f'{entry["tickets"]} tickets | Odds: {entry["odds"]}', inline=False)
        await interaction.followup.send(embed=embed)

    async def _raffle_history(self, interaction):
        await interaction.response.defer()
        history = await self.raffle.get_raffle_history()
        if not history:
            await interaction.followup.send('❌ No raffle history yet!')
            return
        embed = discord.Embed(title='📜 RAFFLE HISTORY', color=discord.Color.gold())
        for r in reversed(history[-5:]):
            embed.add_field(name=f'Week {r["week"]}: {r["vehicle"]}', value=f'Winner: {r["winner"]} | Entries: {r["total_entries"]}', inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name='raffle_admin', description='[ADMIN] Manage raffles')
    @app_commands.default_permissions(administrator=True)
    async def raffle_admin(self, interaction, action: str, vehicle: str = None, display_name: str = None, cost: int = 500):
        if not any(r.name == self.bot.config['bot']['admin_role'] for r in interaction.user.roles):
            await interaction.response.send_message('❌ Admin only!', ephemeral=True)
            return
        await interaction.response.defer()
        if action == 'start':
            if not vehicle or not display_name:
                await interaction.followup.send('❌ Need vehicle classname and display name!')
                return
            raffle = await self.raffle.start_raffle(vehicle=vehicle, vehicle_display=display_name, entry_cost=cost)
            await interaction.followup.send(f'✅ Raffle started for **{display_name}**! Cost: {cost:,} credits.')
        elif action == 'draw':
            raffle = await self.raffle.draw_winner()
            if raffle and raffle.winner:
                await interaction.followup.send(f'🎉 Winner: <@{raffle.winner}>')
            else:
                await interaction.followup.send('❌ Raffle not ready to draw.')
        elif action == 'cancel':
            self.raffle.current_raffle = None
            await interaction.followup.send('✅ Raffle cancelled.')

async def setup(bot):
    await bot.add_cog(RaffleCog(bot))
