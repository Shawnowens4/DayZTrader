"""
DayZ Console Trader Bot - Main Entry Point
Supports: Xbox/PS5 Nitrado servers via XML CE delivery
"""

import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
log = logging.getLogger('DayZTrader')

INITIAL_COGS = [
    'bot.cogs.admin',
    'bot.cogs.trader',
    'bot.cogs.market',
    'bot.cogs.casino',
    'bot.cogs.raffle',
]

class DayZTraderBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix='!',
            intents=intents,
            application_id=os.getenv('DISCORD_APP_ID')
        )

    async def setup_hook(self):
        for cog in INITIAL_COGS:
            try:
                await self.load_extension(cog)
                log.info(f'Loaded cog: {cog}')
            except Exception as e:
                log.error(f'Failed to load cog {cog}: {e}')
        await self.tree.sync()
        log.info('Slash commands synced.')

    async def on_ready(self):
        log.info(f'Bot online as {self.user} (ID: {self.user.id})')
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name='the DayZ Trader | /shop'
            )
        )

async def main():
    bot = DayZTraderBot()
    async with bot:
        await bot.start(os.getenv('DISCORD_TOKEN'))

if __name__ == '__main__':
    asyncio.run(main())
