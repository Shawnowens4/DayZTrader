from __future__ import annotations

import sys
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.game_economy_service import DeterministicCoinFlipEngine
from shared.game_economy_service import GameEconomyService
from shared.mission_bounty_service import MissionBountyService
from shared.task_achievement_service import TaskAchievementService


class GamesLocalAdapter:
    """Local-safe read-only and dry-run adapter for games/tasks/missions."""

    def __init__(
        self,
        game_service: GameEconomyService | None = None,
        task_service: TaskAchievementService | None = None,
        mission_service: MissionBountyService | None = None,
    ) -> None:
        self.game_service = game_service or GameEconomyService()
        self.task_service = task_service or TaskAchievementService()
        self.mission_service = mission_service or MissionBountyService()

    def game_history(self, *, discord_user_id: str, limit: int = 25) -> dict:
        rows = self.game_service.list_sessions(discord_user_id=discord_user_id, limit=limit)
        return {
            "discord_user_id": discord_user_id,
            "rows": rows,
            "count": len(rows),
            "mode": "read-only",
            "domain": "game_economy",
        }

    def coinflip_preview(self, *, pick_value: str, wager_amount: int, server_seed: str) -> dict:
        normalized_pick = pick_value.strip().upper()
        out = DeterministicCoinFlipEngine.compute_outcome(
            server_seed=server_seed,
            pick_value=normalized_pick,
        )
        payout_amount = wager_amount * 2 if out["is_win"] else 0
        return {
            "mode": "dry-run",
            "domain": "game_economy",
            "game_code": "COIN_FLIP",
            "pick_value": normalized_pick,
            "outcome_value": out["outcome_value"],
            "is_win": bool(out["is_win"]),
            "wager_amount": wager_amount,
            "payout_amount": payout_amount,
            "server_seed_hash": out["server_seed_hash"],
            "applied": False,
        }

    def task_progress(self, *, discord_user_id: str, limit: int = 25) -> dict:
        rows = self.task_service.list_task_progress(discord_user_id=discord_user_id, limit=limit)
        return {
            "discord_user_id": discord_user_id,
            "rows": rows,
            "count": len(rows),
            "mode": "read-only",
            "domain": "tasks",
        }

    def achievement_unlocks(self, *, discord_user_id: str, limit: int = 25) -> dict:
        rows = self.task_service.list_achievement_unlocks(discord_user_id=discord_user_id, limit=limit)
        return {
            "discord_user_id": discord_user_id,
            "rows": rows,
            "count": len(rows),
            "mode": "read-only",
            "domain": "achievements",
        }

    def mission_status(self, *, discord_user_id: str, limit: int = 25) -> dict:
        rows = self.mission_service.list_progress(discord_user_id=discord_user_id, limit=limit)
        return {
            "discord_user_id": discord_user_id,
            "rows": rows,
            "count": len(rows),
            "mode": "read-only",
            "domain": "missions",
        }


class GamesLocalCog(commands.Cog, name="GamesLocal"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.adapter = GamesLocalAdapter()

    @app_commands.command(name="gamelocalhistory", description="Read-only local game session history")
    @app_commands.default_permissions(administrator=True)
    async def game_local_history(self, interaction: discord.Interaction, discord_user_id: str, limit: int = 25):
        await interaction.response.defer(ephemeral=True)
        out = self.adapter.game_history(discord_user_id=discord_user_id, limit=limit)
        await interaction.followup.send(
            f"Game history (read-only): user={discord_user_id} sessions={out['count']}",
            ephemeral=True,
        )

    @app_commands.command(name="gamelocalpreview", description="Dry-run coin flip preview (no persistence)")
    @app_commands.default_permissions(administrator=True)
    async def game_local_preview(
        self,
        interaction: discord.Interaction,
        pick_value: str,
        wager_amount: int,
        server_seed: str,
    ):
        await interaction.response.defer(ephemeral=True)
        if wager_amount <= 0:
            await interaction.followup.send("wager_amount must be > 0", ephemeral=True)
            return

        out = self.adapter.coinflip_preview(
            pick_value=pick_value,
            wager_amount=wager_amount,
            server_seed=server_seed,
        )
        await interaction.followup.send(
            (
                f"Game preview ({out['mode']}): pick={out['pick_value']} "
                f"outcome={out['outcome_value']} payout={out['payout_amount']}"
            ),
            ephemeral=True,
        )

    @app_commands.command(name="taskprogresslocal", description="Read-only local task progress")
    @app_commands.default_permissions(administrator=True)
    async def task_progress_local(self, interaction: discord.Interaction, discord_user_id: str, limit: int = 25):
        await interaction.response.defer(ephemeral=True)
        out = self.adapter.task_progress(discord_user_id=discord_user_id, limit=limit)
        await interaction.followup.send(
            f"Task progress (read-only): user={discord_user_id} rows={out['count']}",
            ephemeral=True,
        )

    @app_commands.command(name="achievementslocal", description="Read-only local achievement unlocks")
    @app_commands.default_permissions(administrator=True)
    async def achievements_local(self, interaction: discord.Interaction, discord_user_id: str, limit: int = 25):
        await interaction.response.defer(ephemeral=True)
        out = self.adapter.achievement_unlocks(discord_user_id=discord_user_id, limit=limit)
        await interaction.followup.send(
            f"Achievement unlocks (read-only): user={discord_user_id} rows={out['count']}",
            ephemeral=True,
        )

    @app_commands.command(name="missionstatuslocal", description="Read-only local mission progress status")
    @app_commands.default_permissions(administrator=True)
    async def mission_status_local(self, interaction: discord.Interaction, discord_user_id: str, limit: int = 25):
        await interaction.response.defer(ephemeral=True)
        out = self.adapter.mission_status(discord_user_id=discord_user_id, limit=limit)
        await interaction.followup.send(
            f"Mission status (read-only): user={discord_user_id} rows={out['count']}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesLocalCog(bot))
