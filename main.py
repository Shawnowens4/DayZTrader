"""
DayZ Trader Bot - Main Entry Point
"""
import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class DayZTraderBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            application_id=os.getenv("APPLICATION_ID")
        )

    async def setup_hook(self):
        # Load all cogs
        cogs = [
            "bot.cogs.economy",
            "bot.cogs.trader",
            "bot.cogs.market",
            "bot.cogs.casino",
            "bot.cogs.raffle",
            "bot.cogs.admin",
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"✅ Loaded: {cog}")
            except Exception as e:
                print(f"❌ Failed to load {cog}: {e}")

        # Sync slash commands
        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"✅ Commands synced to guild {guild_id}")
        else:
            await self.tree.sync()
            print("✅ Commands synced globally")

    async def on_ready(self):
        print(f"✅ Bot online: {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the DayZ Trader"
            )
        )

async def main():
    bot = DayZTraderBot()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
