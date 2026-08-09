from __future__ import annotations

import sys
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.market_escrow_service import EscrowStateError
from shared.market_escrow_service import MarketEscrowService


class MarketLocalAdapter:
    """Local-safe adapter for P2P listing/escrow read + preview workflows."""

    def __init__(self, service: MarketEscrowService | None = None) -> None:
        self.service = service or MarketEscrowService()

    def preview_listing(
        self,
        *,
        listing_type: str,
        item_classname: str | None,
        vehicle_label: str | None,
        vehicle_running: bool,
        quantity: int,
        price: int,
    ) -> dict:
        errors: list[str] = []
        if listing_type not in {"ITEM", "VEHICLE"}:
            errors.append("listing_type must be ITEM or VEHICLE")
        if quantity <= 0:
            errors.append("quantity must be > 0")
        if price <= 0:
            errors.append("price must be > 0")
        if listing_type == "VEHICLE" and not vehicle_running:
            errors.append("non-running vehicles cannot be listed")

        return {
            "mode": "dry-run",
            "delivery_mode": "P2P_PHYSICAL",
            "listing_type": listing_type,
            "item_classname": item_classname,
            "vehicle_label": vehicle_label,
            "vehicle_running": vehicle_running,
            "quantity": quantity,
            "price": price,
            "valid": len(errors) == 0,
            "errors": errors,
            "applied": False,
            "spawn_behavior": "not-supported",
        }

    def create_listing_local(self, **kwargs) -> dict:
        return self.service.create_listing(**kwargs)

    def hold_escrow_local(self, *, listing_id: int, buyer_discord_id: str, actor_discord_id: str) -> dict:
        return self.service.hold_escrow(
            listing_id=listing_id,
            buyer_discord_id=buyer_discord_id,
            actor_discord_id=actor_discord_id,
        )

    def get_listing_status(self, listing_id: int) -> str:
        return self.service.get_listing_status(listing_id)

    def get_escrow_status(self, escrow_id: int) -> str:
        return self.service.get_escrow_status(escrow_id)


class MarketLocalCog(commands.Cog, name="MarketLocal"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.adapter = MarketLocalAdapter()

    @app_commands.command(name="marketpreviewlocal", description="Dry-run local P2P listing preview")
    @app_commands.default_permissions(administrator=True)
    async def market_preview_local(
        self,
        interaction: discord.Interaction,
        listing_type: str,
        quantity: int,
        price: int,
        item_classname: str | None = None,
        vehicle_label: str | None = None,
        vehicle_running: bool = True,
    ):
        await interaction.response.defer(ephemeral=True)
        out = self.adapter.preview_listing(
            listing_type=listing_type.strip().upper(),
            item_classname=item_classname,
            vehicle_label=vehicle_label,
            vehicle_running=vehicle_running,
            quantity=quantity,
            price=price,
        )
        await interaction.followup.send(
            (
                f"Market preview ({out['mode']}): valid={out['valid']} "
                f"delivery={out['delivery_mode']} spawn={out['spawn_behavior']}"
            ),
            ephemeral=True,
        )

    @app_commands.command(name="marketcreatelocal", description="Create local-safe P2P listing")
    @app_commands.default_permissions(administrator=True)
    async def market_create_local(
        self,
        interaction: discord.Interaction,
        seller_discord_id: str,
        listing_type: str,
        quantity: int,
        price: int,
        item_classname: str | None = None,
        vehicle_label: str | None = None,
        vehicle_running: bool = True,
    ):
        await interaction.response.defer(ephemeral=True)
        out = self.adapter.create_listing_local(
            seller_discord_id=seller_discord_id,
            listing_type=listing_type.strip().upper(),
            item_classname=item_classname,
            vehicle_label=vehicle_label,
            vehicle_running=vehicle_running,
            quantity=quantity,
            price=price,
            created_by=f"discord:{interaction.user.id}",
            delivery_mode="P2P_PHYSICAL",
        )
        await interaction.followup.send(
            (
                f"Listing created: id={out['listing_id']} status={out['status']} "
                f"delivery={out['delivery_mode']}"
            ),
            ephemeral=True,
        )

    @app_commands.command(name="marketholdlocal", description="Create local-safe escrow hold")
    @app_commands.default_permissions(administrator=True)
    async def market_hold_local(
        self,
        interaction: discord.Interaction,
        listing_id: int,
        buyer_discord_id: str,
    ):
        await interaction.response.defer(ephemeral=True)
        actor = f"discord:{interaction.user.id}"
        out = self.adapter.hold_escrow_local(
            listing_id=listing_id,
            buyer_discord_id=buyer_discord_id,
            actor_discord_id=actor,
        )
        await interaction.followup.send(
            f"Escrow held: id={out['escrow_id']} status={out['status']}",
            ephemeral=True,
        )

    @app_commands.command(name="marketstatuslocal", description="Read local listing/escrow status")
    @app_commands.default_permissions(administrator=True)
    async def market_status_local(
        self,
        interaction: discord.Interaction,
        listing_id: int | None = None,
        escrow_id: int | None = None,
    ):
        await interaction.response.defer(ephemeral=True)
        if listing_id is None and escrow_id is None:
            await interaction.followup.send("Provide listing_id or escrow_id", ephemeral=True)
            return

        try:
            listing_status = self.adapter.get_listing_status(listing_id) if listing_id is not None else None
            escrow_status = self.adapter.get_escrow_status(escrow_id) if escrow_id is not None else None
        except EscrowStateError as exc:
            await interaction.followup.send(f"Status error: {exc}", ephemeral=True)
            return

        await interaction.followup.send(
            f"Market status: listing={listing_status} escrow={escrow_status}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(MarketLocalCog(bot))
