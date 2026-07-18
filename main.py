"""
DayZ Trader Bot - Main Entry Point
Loads all cogs and starts the bot + Flask web server
"""

import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
from threading import Thread
from web.app import create_app
from bot.services.economy import EconomyService
from bot.services.shop import ShopService
from bot.services.market import MarketService
from bot.services.delivery import DeliveryService
from bot.services.delivery_queue import DeliveryQueue
from db.init_db import init_db

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class DayZTraderBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.economy = None
        self.shop = None
        self.market = None
        self.delivery = None
        self.delivery_queue = None

    async def setup_hook(self):
        await init_db()

        self.economy = EconomyService()
        self.shop = ShopService(self.economy)
        self.market = MarketService(self.economy)
        self.delivery = DeliveryService(
            nitrado_token=os.getenv("NITRADO_TOKEN"),
            server_id=os.getenv("NITRADO_SERVER_ID")
        )
        self.delivery_queue = DeliveryQueue(self.delivery)

        # Load all cogs
        cogs = [
            "bot.cogs.trader",
            "bot.cogs.market",
            "bot.cogs.casino",
            "bot.cogs.raffle",
            "bot.cogs.admin",
        ]
        for cog in cogs:
            await self.load_extension(cog)
            print(f"Loaded cog: {cog}")

        await self.tree.sync()
        print("Slash commands synced.")

        # Start delivery queue processor
        asyncio.create_task(self.delivery_queue.process_loop())

    async def on_ready(self):
        print(f"Bot ready: {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Game(name="DayZ Trader | /shop")
        )

def run_flask(app):
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

async def main():
    bot = DayZTraderBot()
    flask_app = create_app(bot)
    flask_thread = Thread(target=run_flask, args=(flask_app,), daemon=True)
    flask_thread.start()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
