"""
Trader Cog - Shop with individual items and bundles
Fixed:
  - import DeliveryJob from bot.services.delivery_queue (correct module)
  - shop.purchase() call order corrected: (uid, item_id, economy, delivery_zone=zone)
  - daily command passes username correctly
  - delivery uses bot.delivery_queue.add() instead of bot.delivery.queue_delivery()
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.services.delivery_queue import DeliveryJob
import json
import uuid


class TraderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='shop', description='Browse the DayZ item shop')
    @app_commands.describe(category='Filter by category (weapons/vehicles/food/bundles/all)')
    async def shop(self, interaction: discord.Interaction, category: str = 'all'):
        await interaction.response.defer()
        await self.bot.economy.ensure_user(interaction.user.id, interaction.user.name)

        cat = None if category == 'all' else category
        items = await self.bot.shop.get_catalog(category=cat)

        if not items:
            await interaction.followup.send('\u274c No items available in this category.')
            return

        embed = discord.Embed(
            title=f'\U0001f6d2 DayZ Trader Shop{" \u2014 " + category.upper() if category != "all" else ""}',
            color=discord.Color.green()
        )
        for item in items[:15]:
            bundle_tag = ' \U0001f4e6' if item['is_bundle'] else ''
            stock_tag = f' | Stock: {item["stock"]}' if item['stock'] >= 0 else ''
            embed.add_field(
                name=f'{item["display_name"]}{bundle_tag}',
                value=f'\U0001f4b0 {item["price"]:,} credits | ID: `{item["item_id"]}`{stock_tag}\n{item["description"] or ""}',
                inline=False
            )
        embed.set_footer(text='Use /buy <item_id> <zone> to purchase')
        await interaction.followup.send(embed=embed)

    @app_commands.command(name='buy', description='Purchase an item or bundle from the shop')
    @app_commands.describe(
        item_id='Item ID from /shop',
        zone='Delivery zone: NWAF / Berezino / NEAF / Vybor / Elektro / Cherno / Balota / Tisy'
    )
    async def buy(self, interaction: discord.Interaction, item_id: str, zone: str = 'NWAF'):
        await interaction.response.defer(ephemeral=True)
        uid = interaction.user.id
        await self.bot.economy.ensure_user(uid, interaction.user.name)

        if await self.bot.security.is_banned(uid):
            await interaction.followup.send('\u274c You are banned from trading.')
            return
        allowed, msg = await self.bot.security.check_rate_limit(uid, 'purchase', 5, 300)
        if not allowed:
            await interaction.followup.send(f'\u23f3 {msg}')
            return

        # Fixed call: (uid, item_id, economy_service, delivery_zone=zone)
        result = await self.bot.shop.purchase(uid, item_id, self.bot.economy, delivery_zone=zone)

        if not result['success']:
            await interaction.followup.send(f'\u274c {result["message"]}')
            return

        item = result['item']
        is_vehicle = item['category'] == 'vehicles'

        if item['is_bundle'] and item.get('bundle_data'):
            bundle_items = json.loads(item['bundle_data'])
            for bi in bundle_items:
                job = DeliveryJob(
                    job_id=str(uuid.uuid4())[:8].upper(),
                    job_type='vehicle' if any(k in bi['class'] for k in ('Car', 'Truck', 'Heli', 'UAZ', 'Sedan', 'Bus')) else 'item',
                    item_class=bi['class'],
                    quantity=bi.get('qty', 1),
                    delivery_zone=zone,
                    buyer_id=uid
                )
                await self.bot.delivery_queue.add(job)
        else:
            job = DeliveryJob(
                job_id=str(uuid.uuid4())[:8].upper(),
                job_type='vehicle' if is_vehicle else 'item',
                item_class=item['class_name'],
                quantity=1,
                delivery_zone=zone,
                fully_kitted=is_vehicle,
                buyer_id=uid
            )
            await self.bot.delivery_queue.add(job)

        embed = discord.Embed(
            title='\u2705 Purchase Confirmed!',
            description=f'**{item["display_name"]}** is being queued for delivery.',
            color=discord.Color.green()
        )
        embed.add_field(name='\U0001f4b0 Cost', value=f'{item["price"]:,} credits', inline=True)
        embed.add_field(name='\U0001f4cd Delivery Zone', value=zone, inline=True)
        embed.add_field(
            name='\u23f1\ufe0f When will it spawn?',
            value='Your item will appear at the delivery zone on the next CE cycle (1\u20135 minutes). **Do not restart the server.**',
            inline=False
        )
        await interaction.followup.send(embed=embed)

        log_ch = discord.utils.get(interaction.guild.channels, name=self.bot.config['bot']['delivery_log_channel'])
        if log_ch:
            log = discord.Embed(title='\U0001f4e6 New Delivery Queued', color=discord.Color.blue())
            log.add_field(name='Player', value=f'<@{uid}>')
            log.add_field(name='Item', value=item['display_name'])
            log.add_field(name='Zone', value=zone)
            await log_ch.send(embed=log)

    @app_commands.command(name='balance', description='Check your credit balance')
    async def balance(self, interaction: discord.Interaction):
        await self.bot.economy.ensure_user(interaction.user.id, interaction.user.name)
        bal = await self.bot.economy.get_balance(interaction.user.id)
        embed = discord.Embed(title='\U0001f4b0 Your Balance', color=discord.Color.gold())
        embed.add_field(name='Credits', value=f'{bal:,}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='daily', description='Claim your daily credits')
    async def daily(self, interaction: discord.Interaction):
        # Fixed: pass username as second arg, then amount
        result = await self.bot.economy.claim_daily(
            interaction.user.id,
            interaction.user.name,
            self.bot.config['economy']['daily_reward']
        )
        if result['success']:
            await interaction.response.send_message(
                f'\u2705 You claimed **{result["amount"]:,} credits**!', ephemeral=True
            )
        else:
            await interaction.response.send_message(f'\u23f3 {result["message"]}', ephemeral=True)

    @app_commands.command(name='leaderboard', description='Top credit holders')
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        lb = await self.bot.economy.get_leaderboard(10)
        embed = discord.Embed(title='\U0001f3c6 Credit Leaderboard', color=discord.Color.gold())
        medals = ['\U0001f947', '\U0001f948', '\U0001f949']
        for i, row in enumerate(lb):
            medal = medals[i] if i < 3 else f'#{i+1}'
            embed.add_field(
                name=f'{medal} {row["username"]}',
                value=f'{row["balance"]:,} credits',
                inline=False
            )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TraderCog(bot))
