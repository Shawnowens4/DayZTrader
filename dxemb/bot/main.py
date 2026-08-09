# =============================================================
# DXEMB Bot — main.py  (A3 / B0)
# commands.Bot with cog loader.
# Prefix commands (!health, !shop) — unchanged.
# Slash commands — synced on ready via bot.tree.sync().
#
# Sync behaviour (SLASH_SYNC env var):
#   global  — sync to all guilds (up to 1h propagation) [default]
#   guild   — instant sync to GUILD_IDS only (dev/test)
#   off     — skip sync entirely (fastest cold start)
#
# GUILD_IDS: comma-separated guild IDs for guild sync mode.
# =============================================================
import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

TOKEN      = os.getenv("DISCORD_BOT_TOKEN", "")
PREFIX     = os.getenv("BOT_PREFIX", "!")
SLASH_SYNC = os.getenv("SLASH_SYNC", "global").strip().lower()
_GUILD_IDS_RAW = os.getenv("GUILD_IDS", "").strip()

GUILD_OBJECTS: list[discord.Object] = []
if _GUILD_IDS_RAW:
    for _gid in _GUILD_IDS_RAW.split(","):
        _gid = _gid.strip()
        if _gid.isdigit():
            GUILD_OBJECTS.append(discord.Object(id=int(_gid)))

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
    "cogs.health_slash",
    "cogs.moderation_local",
    "cogs.wallet_local",
    "cogs.market_local",
    "cogs.autotrader_local",
]


@bot.event
async def on_ready():
    gateway_ms = round(bot.latency * 1000)
    print(
        f"[DXEMB] READY | user={bot.user} id={bot.user.id} "
        f"guilds={len(bot.guilds)} gateway_ms={gateway_ms}"
    )
    print(f"[DXEMB] Command prefix: '{PREFIX}'")
    await _sync_slash_commands()


async def _sync_slash_commands() -> None:
    """Sync the app command tree based on SLASH_SYNC env var."""
    if SLASH_SYNC == "off":
        print("[DXEMB] Slash sync: OFF (SLASH_SYNC=off)")
        return

    if SLASH_SYNC == "guild":
        if not GUILD_OBJECTS:
            print("[DXEMB] Slash sync: guild mode but GUILD_IDS is empty — skipping")
            return
        for guild in GUILD_OBJECTS:
            try:
                synced = await bot.tree.sync(guild=guild)
                print(f"[DXEMB] Slash sync: guild {guild.id} → {len(synced)} command(s)")
            except Exception as exc:
                print(f"[DXEMB] Slash sync: guild {guild.id} FAILED — {exc}")
        return

    # default: global
    try:
        synced = await bot.tree.sync()
        print(f"[DXEMB] Slash sync: global → {len(synced)} command(s)")
    except Exception as exc:
        print(f"[DXEMB] Slash sync: global FAILED — {exc}")


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
