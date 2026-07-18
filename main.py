"""
DayZ Console Trader Bot - Main Entry Point
"""

import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
import yaml

load_dotenv()

with open("config/settings.yaml", "r") as f:
    config = yaml.safe_load(f)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class DayZTraderBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            application_id=os.getenv("DISCORD_APP_ID")
        )
        self.config = config

    async def setup_hook(self):
        cogs = [
            "bot.cogs.admin",
            "bot.cogs.trader",
            "bot.cogs.market",
            "bot.cogs.casino",
            "bot.cogs.raffle",
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"[OK] Loaded {cog}")
            except Exception as e:
                print(f"[ERR] Failed to load {cog}: {e}")

        await self.tree.sync()
        print("[OK] Slash commands synced")

    async def on_ready(self):
        print(f"[OK] Logged in as {self.user} (ID: {self.user.id})")
        print(f"[OK] Connected to {len(self.guilds)} guild(s)")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the DayZ Trader Market"
            )
        )

bot = DayZTraderBot()

async def main():
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
