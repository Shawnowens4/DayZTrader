from __future__ import annotations

import discord


def build_category_embed(categories: list[str], prefix: str) -> discord.Embed:
    embed = discord.Embed(
        title="DXEMB Trader Browser",
        description="Pick a catalog category to browse trader items.",
        colour=discord.Colour.blurple(),
    )
    if categories:
        embed.add_field(
            name="Available categories",
            value=", ".join(f"`{name}`" for name in categories[:20]),
            inline=False,
        )
    embed.set_footer(text=f"Use {prefix}shop anytime to restart guided browse")
    return embed


def build_catalog_page_embed(
    category: str,
    items: list[dict],
    page_index: int,
    has_next: bool,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Trader Catalog - {category}",
        description="Browse items with buttons, then pick one for details.",
        colour=discord.Colour.green(),
    )

    if not items:
        embed.description = "No items available in this category yet."
        return embed

    lines = []
    for idx, item in enumerate(items, start=1):
        name = item.get("display_name") or item["classname"]
        buy = item.get("buy_price")
        price_txt = f"{buy} TZC" if buy is not None else "price pending"
        lines.append(f"**{idx}.** {name} (`{item['classname']}`) - {price_txt}")

    embed.add_field(name="Items", value="\n".join(lines), inline=False)
    embed.set_footer(
        text=f"Page {page_index + 1} | {'More pages available' if has_next else 'End of results'}"
    )
    return embed


def build_item_detail_embed(item: dict) -> discord.Embed:
    title = item.get("display_name") or item["classname"]
    embed = discord.Embed(
        title=title,
        description=f"Classname: `{item['classname']}`",
        colour=discord.Colour.gold(),
    )
    embed.add_field(name="Category", value=item.get("category") or "unknown", inline=True)
    embed.add_field(
        name="Subcategory",
        value=item.get("subcategory") or "unknown",
        inline=True,
    )

    buy = item.get("buy_price")
    sell = item.get("sell_price")
    embed.add_field(
        name="Pricing",
        value=(
            f"Buy: {buy} TZC\nSell: {sell} TZC"
            if buy is not None or sell is not None
            else "Not priced yet"
        ),
        inline=False,
    )
    embed.add_field(
        name="Thumbnail",
        value=f"{item.get('thumbnail_status', 'unknown')} ({item.get('thumbnail_source', 'n/a')})",
        inline=False,
    )

    thumb = item.get("resolved_thumbnail_url")
    if thumb:
        embed.set_thumbnail(url=thumb)
    embed.set_footer(text="DXEMB Console Trader Preview")
    return embed
