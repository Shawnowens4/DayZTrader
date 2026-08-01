from __future__ import annotations

import sys
from pathlib import Path

import discord
from discord.ext import commands

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.catalog.service import get_catalog_item_async
from shared.catalog.service import list_catalog_categories_async
from shared.catalog.service import search_catalog_async

from ui.trader_embeds import build_catalog_page_embed
from ui.trader_embeds import build_category_embed
from ui.trader_embeds import build_item_detail_embed
from ui.trader_views import CatalogPagerView
from ui.trader_views import CategorySelectView

PAGE_SIZE = 5


class TraderCog(commands.Cog, name="Trader"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_listener(self.on_dxemb_catalog_page, "on_dxemb_catalog_page")

    def cog_unload(self):
        self.bot.remove_listener(self.on_dxemb_catalog_page, "on_dxemb_catalog_page")

    @commands.command(name="shop", aliases=["trader"], help="Guided trader browse flow")
    async def shop(self, ctx: commands.Context):
        categories = await list_catalog_categories_async(enabled_only=True)
        if not categories:
            await ctx.send(
                "Trader catalog is empty. Import types.xml into the item table first."
            )
            return

        async def on_category_select(interaction: discord.Interaction, category: str):
            await self._render_category_page(
                interaction=interaction,
                owner_id=ctx.author.id,
                category=category,
                page_index=0,
            )

        embed = build_category_embed(categories, prefix=str(ctx.prefix))
        view = CategorySelectView(
            owner_id=ctx.author.id,
            categories=categories,
            on_select=on_category_select,
        )
        await ctx.send(embed=embed, view=view)

    async def on_dxemb_catalog_page(self, interaction: discord.Interaction, payload: dict):
        await self._render_category_page(
            interaction=interaction,
            owner_id=interaction.user.id,
            category=payload["category"],
            page_index=payload["page_index"],
        )

    async def _render_category_page(
        self,
        interaction: discord.Interaction,
        owner_id: int,
        category: str,
        page_index: int,
    ):
        items, has_next = await self._fetch_page(category=category, page_index=page_index)
        embed = build_catalog_page_embed(
            category=category,
            items=items,
            page_index=page_index,
            has_next=has_next,
        )

        async def load_page(next_category: str, next_page_index: int) -> tuple[list[dict], bool]:
            return await self._fetch_page(next_category, next_page_index)

        async def load_item(classname: str) -> dict | None:
            return await get_catalog_item_async(classname)

        async def send_detail(next_interaction: discord.Interaction, item: dict):
            detail = build_item_detail_embed(item)
            await next_interaction.response.send_message(embed=detail, ephemeral=True)

        view = CatalogPagerView(
            owner_id=owner_id,
            category=category,
            page_index=page_index,
            items=items,
            has_next=has_next,
            load_page=load_page,
            load_item=load_item,
            send_detail=send_detail,
        )

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)

    async def _fetch_page(self, category: str, page_index: int) -> tuple[list[dict], bool]:
        rows = await search_catalog_async(
            category=category,
            enabled_only=True,
            limit=PAGE_SIZE + 1,
            offset=page_index * PAGE_SIZE,
        )
        has_next = len(rows) > PAGE_SIZE
        page_items = rows[:PAGE_SIZE]
        return page_items, has_next


async def setup(bot: commands.Bot):
    await bot.add_cog(TraderCog(bot))
