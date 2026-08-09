from __future__ import annotations

import sys
import uuid
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.moderation_audit_service import ModerationAuditService


class LocalModerationAdapter:
    """Local moderation adapter with no guild mutation behavior."""

    def __init__(self, service: ModerationAuditService | None = None) -> None:
        self.service = service or ModerationAuditService()

    def warn(self, *, actor_discord_id: str, target_discord_id: str, reason: str, reference_id: str | None = None) -> dict:
        ref = reference_id or f"warn-{target_discord_id}-{uuid.uuid4().hex[:10]}"
        return self.service.record_warn(
            actor_discord_id=actor_discord_id,
            target_discord_id=target_discord_id,
            reason=reason,
            reference_id=ref,
            metadata={"mode": "local-only"},
        )

    def query_status(self, *, actor_discord_id: str, target_discord_id: str) -> dict:
        self.service.record_status_query(
            actor_discord_id=actor_discord_id,
            target_discord_id=target_discord_id,
            reference_id=f"status-{target_discord_id}-{uuid.uuid4().hex[:10]}",
        )
        return self.service.get_target_status(target_discord_id)

    def preview_action(self, *, actor_discord_id: str, target_discord_id: str, reason: str) -> dict:
        return self.service.build_dry_run_preview(
            actor_discord_id=actor_discord_id,
            target_discord_id=target_discord_id,
            action_type="WARN",
            reason=reason,
        )


class ModerationLocalCog(commands.Cog, name="ModerationLocal"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.adapter = LocalModerationAdapter()

    @app_commands.command(
        name="modwarnlocal",
        description="Record a local moderation warning without any guild mutation",
    )
    @app_commands.default_permissions(administrator=True)
    async def mod_warn_local(
        self,
        interaction: discord.Interaction,
        target_discord_id: str,
        reason: str,
    ):
        await interaction.response.defer(ephemeral=True)
        result = self.adapter.warn(
            actor_discord_id=str(interaction.user.id),
            target_discord_id=target_discord_id,
            reason=reason,
        )
        await interaction.followup.send(
            (
                f"Local warn recorded. id={result['id']} "
                f"target={result['target_discord_id']} idempotent={result['idempotent']}"
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="modstatuslocal",
        description="Query local moderation action status for a target",
    )
    @app_commands.default_permissions(administrator=True)
    async def mod_status_local(
        self,
        interaction: discord.Interaction,
        target_discord_id: str,
    ):
        await interaction.response.defer(ephemeral=True)
        status = self.adapter.query_status(
            actor_discord_id=str(interaction.user.id),
            target_discord_id=target_discord_id,
        )
        latest = status["latest"]
        latest_text = (
            f"{latest['action_type']} by {latest['actor_discord_id']}"
            if latest
            else "none"
        )
        await interaction.followup.send(
            (
                f"Local status for {target_discord_id}: "
                f"counts={status['counts']} latest={latest_text}"
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="modpreviewlocal",
        description="Preview local moderation warn action (dry-run only)",
    )
    @app_commands.default_permissions(administrator=True)
    async def mod_preview_local(
        self,
        interaction: discord.Interaction,
        target_discord_id: str,
        reason: str,
    ):
        await interaction.response.defer(ephemeral=True)
        preview = self.adapter.preview_action(
            actor_discord_id=str(interaction.user.id),
            target_discord_id=target_discord_id,
            reason=reason,
        )
        await interaction.followup.send(
            (
                f"Preview only: action={preview['action_type']} "
                f"target={preview['target_discord_id']} note={preview['note']}"
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationLocalCog(bot))
