"""
Market Cog - Player-to-player trading with escrow security
Fixed:
  - buy_listing: passes economy_service (bot.economy), removed delivery_zone param
  - confirm_delivery / refund_escrow: passes economy_service
"""

import discord
from discord.ext import commands
from discord import app_commands


class MarketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='market', description='Browse the player marketplace')
    async def market(self, interaction: discord.Interaction):
        await interaction.response.defer()
        listings = await self.bot.market_service.get_listings(status='pending')
        if not listings:
            await interaction.followup.send('\U0001f4ed No active listings right now. Use /list to sell something!')
            return
        embed = discord.Embed(title='\U0001f3ea Player Marketplace', color=discord.Color.blurple())
        for l in listings[:10]:
            embed.add_field(
                name=f'{l["item_display"]} x{l["quantity"]}',
                value=f'\U0001f4b0 {l["asking_price"]:,} credits | ID: `{l["listing_id"]}` | Seller: <@{l["seller_id"]}>',
                inline=False
            )
        embed.set_footer(text='Use /buy_listing <id> to purchase with escrow protection')
        await interaction.followup.send(embed=embed)

    @app_commands.command(name='list', description='List an item for sale on the marketplace')
    @app_commands.describe(
        item_class='DayZ classname of item (e.g. AKM)',
        display_name='Friendly name (e.g. AKM Rifle)',
        quantity='How many',
        price='Asking price in credits'
    )
    async def list_item(
        self, interaction: discord.Interaction,
        item_class: str, display_name: str, quantity: int, price: int
    ):
        await self.bot.economy.ensure_user(interaction.user.id, interaction.user.name)
        if await self.bot.security.is_banned(interaction.user.id):
            await interaction.response.send_message('\u274c Banned.', ephemeral=True)
            return
        result = await self.bot.market_service.create_listing(
            interaction.user.id, item_class, display_name, quantity, price
        )
        if result['success']:
            embed = discord.Embed(title='\u2705 Listing Created', color=discord.Color.green())
            embed.add_field(name='Item', value=display_name)
            embed.add_field(name='Price', value=f'{price:,} credits')
            embed.add_field(name='Listing ID', value=f'`{result["listing_id"]}`')
            embed.add_field(name='\U0001f512 Escrow Protection', value='Buyer credits are locked until delivery is confirmed.', inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(f'\u274c {result["message"]}', ephemeral=True)

    @app_commands.command(name='buy_listing', description='Buy from the player marketplace (escrow protected)')
    @app_commands.describe(listing_id='Listing ID from /market')
    async def buy_listing(self, interaction: discord.Interaction, listing_id: str):
        await interaction.response.defer(ephemeral=True)
        await self.bot.economy.ensure_user(interaction.user.id, interaction.user.name)
        # Fixed: pass economy_service, no delivery_zone
        result = await self.bot.market_service.buy_listing(
            interaction.user.id, listing_id, self.bot.economy
        )
        if result['success']:
            embed = discord.Embed(
                title='\U0001f512 Escrow Locked \u2014 Trade In Progress',
                description=result['message'],
                color=discord.Color.orange()
            )
            embed.add_field(
                name='What happens next?',
                value='The seller delivers your item in-game. An admin confirms delivery and releases credits to the seller. Use /dispute if anything goes wrong.',
                inline=False
            )
            await interaction.followup.send(embed=embed)
            try:
                seller = await self.bot.fetch_user(result['listing']['seller_id'])
                await seller.send(
                    f'\U0001f6d2 Someone bought your **{result["listing"]["item_display"]}** listing! '
                    'Deliver it in-game and notify an admin to confirm.'
                )
            except Exception:
                pass
        else:
            await interaction.followup.send(f'\u274c {result["message"]}')

    @app_commands.command(name='dispute', description='Dispute a trade')
    @app_commands.describe(listing_id='Listing ID', reason='Reason for dispute')
    async def dispute(self, interaction: discord.Interaction, listing_id: str, reason: str):
        result = await self.bot.market_service.dispute_trade(interaction.user.id, listing_id, reason)
        await interaction.response.send_message(
            f'\U0001f6a8 {result["message"]}' if result['success'] else f'\u274c {result["message"]}',
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(MarketCog(bot))
