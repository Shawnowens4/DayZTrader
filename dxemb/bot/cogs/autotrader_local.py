from __future__ import annotations

import sys
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.auto_trader_order_service import AutoTraderOrderService


class AutoTraderLocalAdapter:
    """Local-safe read-only/dry-run adapter for Auto-Trader surfaces."""

    def __init__(self, service: AutoTraderOrderService | None = None) -> None:
        self.service = service or AutoTraderOrderService()

    def browse_products(self, *, limit: int = 25) -> dict:
        rows = self.service.list_products(enabled_only=True, limit=limit)
        return {"rows": rows, "count": len(rows), "mode": "read-only"}

    def preview_order(self, *, product_id: int, quantity: int) -> dict:
        out = self.service.preview_order(product_id=product_id, quantity=quantity)
        out["domain"] = "autotrader"
        return out

    def order_status_history(self, *, order_id: int) -> dict:
        order = self.service.get_order(order_id)
        events = self.service.list_order_events(order_id)
        return {
            "order": order,
            "events": events,
            "event_count": len(events),
            "mode": "read-only",
            "domain": "autotrader",
        }


class AutoTraderLocalCog(commands.Cog, name="AutoTraderLocal"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.adapter = AutoTraderLocalAdapter()

    @app_commands.command(name="autotraderproductslocal", description="Read-only local Auto-Trader products")
    @app_commands.default_permissions(administrator=True)
    async def autotrader_products_local(self, interaction: discord.Interaction, limit: int = 25):
        await interaction.response.defer(ephemeral=True)
        out = self.adapter.browse_products(limit=limit)
        await interaction.followup.send(
            f"Auto-Trader products (read-only): count={out['count']}",
            ephemeral=True,
        )

    @app_commands.command(name="autotraderpreviewlocal", description="Dry-run local Auto-Trader order preview")
    @app_commands.default_permissions(administrator=True)
    async def autotrader_preview_local(self, interaction: discord.Interaction, product_id: int, quantity: int):
        await interaction.response.defer(ephemeral=True)
        out = self.adapter.preview_order(product_id=product_id, quantity=quantity)
        await interaction.followup.send(
            f"Auto-Trader preview ({out['mode']}): valid={out['valid']}", 
            ephemeral=True,
        )

    @app_commands.command(name="autotraderhistorylocal", description="Read-only local Auto-Trader order history")
    @app_commands.default_permissions(administrator=True)
    async def autotrader_history_local(self, interaction: discord.Interaction, order_id: int):
        await interaction.response.defer(ephemeral=True)
        out = self.adapter.order_status_history(order_id=order_id)
        await interaction.followup.send(
            f"Auto-Trader order history (read-only): order_id={out['order']['id']} events={out['event_count']}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoTraderLocalCog(bot))
