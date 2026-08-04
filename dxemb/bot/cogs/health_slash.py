from __future__ import annotations
# =============================================================
# DXEMB  bot/cogs/health_slash.py  (B0)
# First slash command — /health
# Proves bot.tree.sync infrastructure works.
# Mirrors !health output as a slash command.
# Admin-only: ephemeral reply visible only to the user.
# =============================================================

import sys
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.db import get_sync_health

TABLES = ["player", "item", "escrow_transaction"]


class HealthSlashCog(commands.Cog, name="HealthSlash"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="health",
        description="Show DXEMB system health — DB status, latency, table counts",
    )
    @app_commands.default_permissions(administrator=True)
    async def health(self, interaction: discord.Interaction):
        """Admin-only slash command — ephemeral health check."""
        await interaction.response.defer(ephemeral=True)

        try:
            db = get_sync_health(TABLES)
        except Exception as exc:
            await interaction.followup.send(
                f"❌ DB health check failed: `{exc}`", ephemeral=True
            )
            return

        status_emoji = "✅" if db["connected"] else "❌"
        color = discord.Color.green() if db["connected"] else discord.Color.red()

        embed = discord.Embed(
            title=f"{status_emoji} DXEMB System Health",
            color=color,
        )

        embed.add_field(
            name="Database",
            value="Connected" if db["connected"] else f"Error: {db['error']}",
            inline=True,
        )

        if db["connected"]:
            embed.add_field(
                name="Latency",
                value=f"{db['latency_ms']} ms",
                inline=True,
            )

        if db.get("tables"):
            table_lines = "\n".join(
                f"`{t}` — {c} rows" for t, c in db["tables"].items()
            )
            embed.add_field(name="Tables", value=table_lines, inline=False)

        embed.set_footer(text="DXEMB Admin — visible only to you")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HealthSlashCog(bot))
