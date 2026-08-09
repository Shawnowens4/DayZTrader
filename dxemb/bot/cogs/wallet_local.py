from __future__ import annotations

import sys
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.wallet_ledger_service import InsufficientFundsError
from shared.wallet_ledger_service import WalletLedgerService


class WalletLocalAdapter:
    """Read-only wallet adapter for local-safe bot usage."""

    def __init__(self, service: WalletLedgerService | None = None) -> None:
        self.service = service or WalletLedgerService()

    def balance(self, *, discord_user_id: str) -> dict:
        return {
            "discord_user_id": discord_user_id,
            "balance": self.service.get_balance(discord_user_id),
            "read_only": True,
        }

    def transaction_history(self, *, discord_user_id: str, limit: int = 10) -> dict:
        rows = self.service.list_ledger_entries(discord_user_id=discord_user_id, limit=limit)
        return {
            "discord_user_id": discord_user_id,
            "rows": rows,
            "count": len(rows),
            "read_only": True,
        }

    def preview_credit(self, *, discord_user_id: str, amount: int) -> dict:
        current = self.service.get_balance(discord_user_id)
        return {
            "discord_user_id": discord_user_id,
            "mode": "dry-run",
            "operation": "credit",
            "amount": amount,
            "current_balance": current,
            "projected_balance": current + amount,
            "applied": False,
        }

    def preview_debit(self, *, discord_user_id: str, amount: int) -> dict:
        current = self.service.get_balance(discord_user_id)
        projected = current - amount
        allowed = projected >= 0
        return {
            "discord_user_id": discord_user_id,
            "mode": "dry-run",
            "operation": "debit",
            "amount": amount,
            "current_balance": current,
            "projected_balance": projected,
            "allowed": allowed,
            "error": None if allowed else str(InsufficientFundsError("insufficient funds")),
            "applied": False,
        }


class WalletLocalCog(commands.Cog, name="WalletLocal"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.adapter = WalletLocalAdapter()

    @app_commands.command(name="walletbalancelocal", description="Read-only local wallet balance")
    @app_commands.default_permissions(administrator=True)
    async def wallet_balance_local(self, interaction: discord.Interaction, discord_user_id: str):
        await interaction.response.defer(ephemeral=True)
        out = self.adapter.balance(discord_user_id=discord_user_id)
        await interaction.followup.send(
            f"Wallet balance (read-only): user={out['discord_user_id']} balance={out['balance']}",
            ephemeral=True,
        )

    @app_commands.command(name="wallethistorylocal", description="Read-only local wallet ledger history")
    @app_commands.default_permissions(administrator=True)
    async def wallet_history_local(self, interaction: discord.Interaction, discord_user_id: str, limit: int = 10):
        await interaction.response.defer(ephemeral=True)
        out = self.adapter.transaction_history(discord_user_id=discord_user_id, limit=limit)
        await interaction.followup.send(
            f"Wallet history (read-only): user={out['discord_user_id']} rows={out['count']}",
            ephemeral=True,
        )

    @app_commands.command(name="walletpreviewlocal", description="Dry-run wallet credit/debit preview only")
    @app_commands.default_permissions(administrator=True)
    async def wallet_preview_local(
        self,
        interaction: discord.Interaction,
        discord_user_id: str,
        operation: str,
        amount: int,
    ):
        await interaction.response.defer(ephemeral=True)
        op = operation.strip().lower()
        if op == "credit":
            out = self.adapter.preview_credit(discord_user_id=discord_user_id, amount=amount)
        elif op == "debit":
            out = self.adapter.preview_debit(discord_user_id=discord_user_id, amount=amount)
        else:
            await interaction.followup.send("Operation must be credit or debit", ephemeral=True)
            return

        await interaction.followup.send(
            (
                f"Wallet preview ({out['mode']}): op={out['operation']} amount={out['amount']} "
                f"current={out['current_balance']} projected={out['projected_balance']}"
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(WalletLocalCog(bot))
