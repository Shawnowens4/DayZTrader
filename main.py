"""
DayZ Console Trader Bot - Main Entry Point
"""

import discord
from discord.ext import commands
import asyncio
import os
import yaml
import sqlite3
from bot.services.economy import EconomyService
from bot.services.shop import ShopService
from bot.services.market import MarketService
from bot.services.delivery import DeliveryService
from bot.services.delivery_queue import DeliveryQueue
from bot.services.security import SecurityService

with open('config/settings.yaml', 'r') as f:
    config = yaml.safe_load(f)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class DayZTraderBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=intents,
            application_id=config['bot']['application_id']
        )
        self.config = config
        self.db_path = config['database']['path']
        self._init_db()
        self.economy = EconomyService(self.db_path)
        self.shop = ShopService(self.db_path)
        self.market_service = MarketService(self.db_path, self.economy)
        self.delivery_queue = DeliveryQueue()
        self.delivery = DeliveryService(
            nitrado_token=config['nitrado']['token'],
            server_id=config['nitrado']['server_id'],
            queue=self.delivery_queue
        )
        self.security = SecurityService(self.db_path)

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        with open('db/schema.sql', 'r') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()

    async def setup_hook(self):
        cogs = [
            'bot.cogs.trader',
            'bot.cogs.market',
            'bot.cogs.casino',
            'bot.cogs.raffle',
            'bot.cogs.admin',
        ]
        for cog in cogs:
            await self.load_extension(cog)
        await self.tree.sync()
        asyncio.create_task(self.delivery_queue.process_loop())
        print(f'[BOT] Synced slash commands.')

    async def on_ready(self):
        print(f'[BOT] Logged in as {self.user} (ID: {self.user.id})')
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name='the DayZ Trader'
            )
        )

bot = DayZTraderBot()

if __name__ == '__main__':
    bot.run(config['bot']['token'])
