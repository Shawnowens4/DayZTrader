# =============================================================
# DXEMB Bot — main.py  (Epic A3)
# commands.Bot with cog loader. Replaces bare discord.Client.
# =============================================================
import os
import asyncio
import discord
from discord.ext import commands

TOKEN   = os.getenv("DISCORD_BOT_TOKEN", "")
PREFIX  = os.getenv("BOT_PREFIX", "!")

# Privileged intents — message_content required for prefix commands
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ----------------------------------------------------------------
# Cogs to load on startup — add new cog module paths here
# ----------------------------------------------------------------
INITIAL_COGS = [
    "cogs.health",
    "cogs.trader",
]


@bot.event
async def on_ready():
    gateway_ms = round(bot.latency * 1000)
    print(
        f"[DXEMB] READY | user={bot.user} id={bot.user.id} "
        f"guilds={len(bot.guilds)} gateway_ms={gateway_ms}"
    )
    print(f"[DXEMB] Command prefix: '{PREFIX}'")


async def load_cogs():
    for cog in INITIAL_COGS:
        try:
            await bot.load_extension(cog)
            print(f"[DXEMB] Loaded cog: {cog}")
        except Exception as exc:
            print(f"[DXEMB] FAILED to load cog {cog}: {exc}")


async def main():
    if not TOKEN:
        print("[DXEMB] Startup check: DISCORD_BOT_TOKEN is missing or blank.")
        print("[DXEMB] Running in no-op mode; Discord connection disabled.")
        while True:
            await asyncio.sleep(60)

    print(
        "[DXEMB] Startup check: DISCORD_BOT_TOKEN is present "
        f"(len={len(TOKEN)})."
    )
    print("[DXEMB] Attempting Discord Gateway connection...")

    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
