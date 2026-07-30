# =============================================================
# DXEMB — cogs/health.py  (Epic A3)
# HealthCog: end-to-end smoke test.
#   !ping   — bot latency + DB connectivity check
#   !dbinfo — table row counts for quick schema sanity check
# =============================================================
import time
import discord
from discord.ext import commands

from db import get_pool


class HealthCog(commands.Cog, name="Health"):
    """Bot and database health checks."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ----------------------------------------------------------
    # !ping
    # Reports Discord gateway latency and a DB round-trip time.
    # ----------------------------------------------------------
    @commands.command(name="ping", help="Bot + DB latency check")
    async def ping(self, ctx: commands.Context):
        discord_ms = round(self.bot.latency * 1000)

        # DB round-trip
        db_status = "\u274c unreachable"
        db_ms = None
        try:
            pool = await get_pool()
            t0 = time.monotonic()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_ms = round((time.monotonic() - t0) * 1000)
            db_status = f"\u2705 {db_ms} ms"
        except Exception as exc:
            db_status = f"\u274c {exc}"

        embed = discord.Embed(
            title="\U0001f4e1 DXEMB Health Check",
            colour=discord.Colour.green() if db_ms is not None else discord.Colour.red(),
        )
        embed.add_field(name="Discord latency", value=f"{discord_ms} ms", inline=True)
        embed.add_field(name="Database",        value=db_status,           inline=True)
        embed.set_footer(text="DayZ Xbox Trader — DXEMB")
        await ctx.send(embed=embed)

    # ----------------------------------------------------------
    # !dbinfo
    # Quick row-count sanity check on core tables.
    # ----------------------------------------------------------
    @commands.command(name="dbinfo", help="Row counts for core DB tables")
    @commands.has_permissions(administrator=True)
    async def dbinfo(self, ctx: commands.Context):
        tables = ["player", "item", "escrow_transaction"]
        lines = []
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                for table in tables:
                    count = await conn.fetchval(
                        f"SELECT COUNT(*) FROM {table}"  # noqa: S608
                    )
                    lines.append(f"`{table}`: **{count}** rows")
            colour = discord.Colour.blurple()
            body   = "\n".join(lines)
        except Exception as exc:
            colour = discord.Colour.red()
            body   = f"\u274c DB error: {exc}"

        embed = discord.Embed(
            title="\U0001f5c4\ufe0f DXEMB DB Info",
            description=body,
            colour=colour,
        )
        embed.set_footer(text="Admin only — DayZ Xbox Trader")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(HealthCog(bot))
