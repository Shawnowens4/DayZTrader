from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable

import discord


PageLoader = Callable[[str, int], Awaitable[tuple[list[dict], bool]]]
ItemLoader = Callable[[str], Awaitable[dict | None]]
DetailSender = Callable[[discord.Interaction, dict], Awaitable[None]]


class UserScopedView(discord.ui.View):
    def __init__(self, owner_id: int, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Only the command starter can interact with this trader panel.",
            ephemeral=True,
        )
        return False


class CategorySelect(discord.ui.Select):
    def __init__(self, categories: list[str], on_select: Callable[[discord.Interaction, str], Awaitable[None]]):
        options = [
            discord.SelectOption(label=cat[:100], value=cat[:100], description=f"Browse {cat}")
            for cat in categories[:25]
        ]
        super().__init__(
            placeholder="Choose an item category",
            min_values=1,
            max_values=1,
            options=options,
        )
        self._on_select = on_select

    async def callback(self, interaction: discord.Interaction):
        await self._on_select(interaction, self.values[0])


class CategorySelectView(UserScopedView):
    def __init__(self, owner_id: int, categories: list[str], on_select: Callable[[discord.Interaction, str], Awaitable[None]]):
        super().__init__(owner_id=owner_id, timeout=180)
        self.add_item(CategorySelect(categories, on_select))


class ItemSelect(discord.ui.Select):
    def __init__(
        self,
        items: list[dict],
        load_item: ItemLoader,
        send_detail: DetailSender,
    ):
        options = []
        for item in items[:25]:
            label = (item.get("display_name") or item["classname"])[:100]
            options.append(
                discord.SelectOption(
                    label=label,
                    value=item["classname"],
                    description=(item.get("subcategory") or "no subcategory")[:100],
                )
            )
        super().__init__(
            placeholder="Pick an item for details",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )
        self._load_item = load_item
        self._send_detail = send_detail

    async def callback(self, interaction: discord.Interaction):
        classname = self.values[0]
        item = await self._load_item(classname)
        if not item:
            await interaction.response.send_message(
                "Item details are unavailable right now.",
                ephemeral=True,
            )
            return
        await self._send_detail(interaction, item)


class CatalogPagerView(UserScopedView):
    def __init__(
        self,
        owner_id: int,
        category: str,
        page_index: int,
        items: list[dict],
        has_next: bool,
        load_page: PageLoader,
        load_item: ItemLoader,
        send_detail: DetailSender,
    ):
        super().__init__(owner_id=owner_id, timeout=300)
        self.category = category
        self.page_index = page_index
        self.items = items
        self.has_next = has_next
        self._load_page = load_page

        if items:
            self.add_item(ItemSelect(items, load_item=load_item, send_detail=send_detail))

    async def _refresh(self, interaction: discord.Interaction, next_page: int):
        items, has_next = await self._load_page(self.category, next_page)
        payload = {
            "category": self.category,
            "page_index": next_page,
            "items": items,
            "has_next": has_next,
        }
        await interaction.response.defer()
        self.stop()
        interaction.client.dispatch("dxemb_catalog_page", interaction, payload)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, row=2)
    async def prev_page(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if self.page_index <= 0:
            await interaction.response.send_message("Already on the first page.", ephemeral=True)
            return
        await self._refresh(interaction, self.page_index - 1)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, row=2)
    async def next_page(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not self.has_next:
            await interaction.response.send_message("No more items in this category.", ephemeral=True)
            return
        await self._refresh(interaction, self.page_index + 1)
