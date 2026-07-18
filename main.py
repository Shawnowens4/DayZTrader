"""
DayZ Trader Bot - Main Entry Point
"""
import discord
from discord.ext import commands
import asyncio
import os
import yaml
from dotenv import load_dotenv

from bot.services.economy import EconomyService
from bot.services.shop import ShopService
from bot.services.market import MarketService
from bot.services.security import SecurityService
from bot.services.delivery import DeliveryService
from bot.services.delivery_queue import DeliveryQueue

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class DayZTraderBot(commands.Bot):
    def __init__(self):
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml')
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        super().__init__(
            command_prefix=self.config['bot']['prefix'],
            intents=intents,
            application_id=os.getenv('APPLICATION_ID')
        )

        # DB path shared across all services
        self.db_path = os.path.join(os.path.dirname(__file__), 'db', 'trader.db')

        # Instantiate all services
        self.economy = EconomyService()
        self.shop = ShopService()
        self.market_service = MarketService()
        self.security = SecurityService()
        self.delivery = DeliveryService()
        self.delivery_queue = DeliveryQueue(self.delivery)

    async def setup_hook(self):
        # Initialize DB schema
        await self.economy.init_db()

        # Start the delivery queue processor
        asyncio.create_task(self.delivery_queue.process_loop())

        # Load all cogs — no economy cog (economy is a service, not a cog)
        cogs = [
            'bot.cogs.trader',
            'bot.cogs.market',
            'bot.cogs.casino',
            'bot.cogs.raffle',
            'bot.cogs.admin',
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f'\u2705 Loaded: {cog}')
            except Exception as e:
                print(f'\u274c Failed to load {cog}: {e}')

        # Sync slash commands
        guild_id = os.getenv('GUILD_ID') or str(self.config['bot'].get('guild_id', ''))
        if guild_id and guild_id != '0':
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f'\u2705 Commands synced to guild {guild_id}')
        else:
            await self.tree.sync()
            print('\u2705 Commands synced globally')

    async def on_ready(self):
        print(f'\u2705 Bot online: {self.user} (ID: {self.user.id})')
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name='the DayZ Trader'
            )
        )


async def main():
    bot = DayZTraderBot()
    async with bot:
        await bot.start(os.getenv('DISCORD_TOKEN'))


if __name__ == '__main__':
    asyncio.run(main())
