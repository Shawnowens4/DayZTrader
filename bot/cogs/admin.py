"""
Admin Cog - Persistent Discord admin panel with buttons and modals
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from bot.services.shop import BundleItem
import json

def is_trader_admin(interaction: discord.Interaction) -> bool:
    return any(r.name == interaction.client.config['bot']['admin_role'] for r in interaction.user.roles)

# ───────────────────────────────────────────────────────────────────────
# MODALS
# ───────────────────────────────────────────────────────────────────────

class AddItemModal(discord.ui.Modal, title='Add Shop Item'):
    class_name = discord.ui.TextInput(label='DayZ Classname', placeholder='AKM_Chaos')
    display_name = discord.ui.TextInput(label='Display Name', placeholder='AKM Rifle')
    price = discord.ui.TextInput(label='Price (credits)', placeholder='2500')
    category = discord.ui.TextInput(label='Category', placeholder='weapons / vehicles / food / general')
    description = discord.ui.TextInput(label='Description (optional)', required=False, placeholder='Fully built AKM')

    async def on_submit(self, interaction: discord.Interaction):
        try:
            item = await interaction.client.shop.create_item(
                class_name=str(self.class_name),
                display_name=str(self.display_name),
                price=int(str(self.price)),
                category=str(self.category),
                description=str(self.description),
                admin_id=interaction.user.id
            )
            await interaction.response.send_message(
                f'✅ Added **{item.display_name}** (ID: `{item.item_id}`) for {item.price:,} credits.', ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f'❌ Error: {e}', ephemeral=True)


class AddBundleModal(discord.ui.Modal, title='Create Bundle'):
    display_name = discord.ui.TextInput(label='Bundle Name', placeholder='Starter Kit')
    price = discord.ui.TextInput(label='Price (credits)', placeholder='5000')
    items_json = discord.ui.TextInput(
        label='Items (JSON)',
        style=discord.TextStyle.paragraph,
        placeholder='[{"class":"AKM","qty":1},{"class":"AKM_Mag30","qty":3}]'
    )
    category = discord.ui.TextInput(label='Category', placeholder='bundles')
    discount = discord.ui.TextInput(label='Discount % (0-50)', placeholder='10', required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            raw = json.loads(str(self.items_json))
            bundle_items = [BundleItem(class_name=i['class'], quantity=i.get('qty', 1)) for i in raw]
            discount_pct = int(str(self.discount)) if str(self.discount) else 0
            bundle = await interaction.client.shop.create_bundle(
                display_name=str(self.display_name),
                price=int(str(self.price)),
                items=bundle_items,
                category=str(self.category),
                discount_pct=discount_pct,
                admin_id=interaction.user.id
            )
            await interaction.response.send_message(
                f'✅ Bundle **{bundle.display_name}** created (ID: `{bundle.item_id}`) for {bundle.price:,} credits.', ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f'❌ Error: {e}', ephemeral=True)


class ToggleItemModal(discord.ui.Modal, title='Enable / Disable Item'):
    item_id = discord.ui.TextInput(label='Item ID')
    enabled = discord.ui.TextInput(label='Enable? (yes/no)', placeholder='yes')

    async def on_submit(self, interaction: discord.Interaction):
        state = str(self.enabled).lower() in ('yes', 'true', '1')
        await interaction.client.shop.toggle_item(str(self.item_id), state)
        status = 'enabled' if state else 'disabled'
        await interaction.response.send_message(f'✅ Item `{self.item_id}` is now **{status}**.', ephemeral=True)


class AdjustBalanceModal(discord.ui.Modal, title='Adjust Player Balance'):
    discord_id = discord.ui.TextInput(label='Discord User ID')
    amount = discord.ui.TextInput(label='Amount (+/-)', placeholder='+1000 or -500')
    reason = discord.ui.TextInput(label='Reason', placeholder='Admin adjustment')

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amt = int(str(self.amount).replace('+', ''))
            uid = int(str(self.discord_id))
            new_bal = await interaction.client.economy.update_balance(uid, amt, str(self.reason))
            await interaction.response.send_message(
                f'✅ Adjusted <@{uid}> balance by **{amt:+,}**. New balance: **{new_bal:,}**', ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f'❌ Error: {e}', ephemeral=True)


class ConfirmDeliveryModal(discord.ui.Modal, title='Confirm Market Delivery'):
    listing_id = discord.ui.TextInput(label='Listing ID')

    async def on_submit(self, interaction: discord.Interaction):
        result = await interaction.client.market_service.confirm_delivery(interaction.user.id, str(self.listing_id))
        await interaction.response.send_message(
            f'✅ {result["message"]}' if result['success'] else f'❌ {result["message"]}', ephemeral=True
        )


class RefundEscrowModal(discord.ui.Modal, title='Refund Escrow to Buyer'):
    listing_id = discord.ui.TextInput(label='Listing ID')

    async def on_submit(self, interaction: discord.Interaction):
        result = await interaction.client.market_service.refund_escrow(interaction.user.id, str(self.listing_id))
        await interaction.response.send_message(
            f'✅ {result["message"]}' if result['success'] else f'❌ {result["message"]}', ephemeral=True
        )


# ───────────────────────────────────────────────────────────────────────
# PERSISTENT ADMIN PANEL VIEW
# ───────────────────────────────────────────────────────────────────────

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent across restarts

    async def _admin_check(self, interaction: discord.Interaction) -> bool:
        if not is_trader_admin(interaction):
            await interaction.response.send_message('❌ Admin only!', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='➕ Add Item', style=discord.ButtonStyle.green, custom_id='admin:add_item', row=0)
    async def add_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._admin_check(interaction): return
        await interaction.response.send_modal(AddItemModal())

    @discord.ui.button(label='📦 Create Bundle', style=discord.ButtonStyle.blurple, custom_id='admin:create_bundle', row=0)
    async def create_bundle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._admin_check(interaction): return
        await interaction.response.send_modal(AddBundleModal())

    @discord.ui.button(label='🔄 Toggle Item', style=discord.ButtonStyle.grey, custom_id='admin:toggle_item', row=0)
    async def toggle_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._admin_check(interaction): return
        await interaction.response.send_modal(ToggleItemModal())

    @discord.ui.button(label='💰 Adjust Balance', style=discord.ButtonStyle.red, custom_id='admin:adjust_balance', row=1)
    async def adjust_balance(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._admin_check(interaction): return
        await interaction.response.send_modal(AdjustBalanceModal())

    @discord.ui.button(label='✅ Confirm Delivery', style=discord.ButtonStyle.green, custom_id='admin:confirm_delivery', row=1)
    async def confirm_delivery(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._admin_check(interaction): return
        await interaction.response.send_modal(ConfirmDeliveryModal())

    @discord.ui.button(label='💸 Refund Escrow', style=discord.ButtonStyle.red, custom_id='admin:refund_escrow', row=1)
    async def refund_escrow(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._admin_check(interaction): return
        await interaction.response.send_modal(RefundEscrowModal())

    @discord.ui.button(label='📋 View Disputes', style=discord.ButtonStyle.grey, custom_id='admin:view_disputes', row=2)
    async def view_disputes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._admin_check(interaction): return
        listings = await interaction.client.market_service.get_listings(status='disputed')
        if not listings:
            await interaction.response.send_message('✅ No active disputes!', ephemeral=True)
            return
        embed = discord.Embed(title='🚨 Active Disputes', color=discord.Color.red())
        for l in listings:
            embed.add_field(
                name=f'{l["item_display"]} | ID: {l["listing_id"]}',
                value=f'Buyer: <@{l["buyer_id"]}> | Seller: <@{l["seller_id"]}>\nReason: {l["dispute_reason"]}',
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='📊 Delivery Queue', style=discord.ButtonStyle.grey, custom_id='admin:delivery_queue', row=2)
    async def delivery_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._admin_check(interaction): return
        size = interaction.client.delivery_queue.queue_size
        await interaction.response.send_message(
            f'📦 **Delivery Queue:** {size} jobs pending\n⚠️ The server is **never** restarted by the bot — CE cycle handles all spawns automatically.',
            ephemeral=True
        )

    @discord.ui.button(label='🗑️ Delete Item', style=discord.ButtonStyle.red, custom_id='admin:delete_item', row=2)
    async def delete_item_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._admin_check(interaction): return
        class DeleteModal(discord.ui.Modal, title='Delete Shop Item'):
            item_id = discord.ui.TextInput(label='Item ID to delete')
            async def on_submit(s, i: discord.Interaction):
                await i.client.shop.delete_item(str(s.item_id))
                await i.response.send_message(f'🗑️ Item `{s.item_id}` deleted.', ephemeral=True)
        await interaction.response.send_modal(DeleteModal())


# ───────────────────────────────────────────────────────────────────────
# ADMIN COG
# ───────────────────────────────────────────────────────────────────────

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(AdminPanelView())  # Re-register persistent view on restart
        self.expire_loop.start()

    @tasks.loop(hours=1)
    async def expire_loop(self):
        """Hourly cleanup of expired market listings"""
        await self.bot.market_service.expire_old_listings()

    @app_commands.command(name='admin_panel', description='[ADMIN] Open the DayZ Trader admin panel')
    @app_commands.default_permissions(administrator=True)
    async def admin_panel(self, interaction: discord.Interaction):
        if not is_trader_admin(interaction):
            await interaction.response.send_message('❌ Admin only!', ephemeral=True)
            return
        embed = discord.Embed(
            title='⚙️ DayZ Trader — Admin Panel',
            description='Use the buttons below to manage the shop, marketplace, economy, and deliveries.',
            color=0x2b2d31
        )
        embed.add_field(name='🛒 Shop', value='Add items, create bundles, toggle/delete listings', inline=False)
        embed.add_field(name='🏪 Market', value='Confirm deliveries, refund escrow, view disputes', inline=False)
        embed.add_field(name='💰 Economy', value='Adjust player balances with audit logging', inline=False)
        embed.add_field(
            name='📦 Deliveries',
            value='⚠️ The server is **never** restarted by the bot. CE cycle (~1-5 min) handles all spawns.',
            inline=False
        )
        await interaction.channel.send(embed=embed, view=AdminPanelView())
        await interaction.response.send_message('✅ Panel posted!', ephemeral=True)

    @app_commands.command(name='ban_player', description='[ADMIN] Ban a player from trading')
    @app_commands.default_permissions(administrator=True)
    async def ban_player(self, interaction: discord.Interaction, user: discord.Member, reason: str = ''):
        if not is_trader_admin(interaction):
            await interaction.response.send_message('❌ Admin only!', ephemeral=True)
            return
        await self.bot.security.ban_user(user.id, interaction.user.id, reason)
        await interaction.response.send_message(f'🔨 <@{user.id}> banned from trading. Reason: {reason}', ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
