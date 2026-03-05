import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import traceback
import asyncio
from config import (
    BLACKLIST_LOG_CHANNEL_ID, BLACKLIST_PANEL_CHANNEL_ID,
    ROLE_MODER, LEADER_ROLE_ID, DEPUTY_LEADER_ROLE_ID
)
import database as db

class PanelBlacklistModal(Modal, title="Добавление в ЧС"):
    def __init__(self):
        super().__init__()
        self.add_item(TextInput(label="ID пользователя", required=True, placeholder="Числовой ID"))
        self.add_item(TextInput(label="Причина", style=discord.TextStyle.paragraph, required=True, max_length=500))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.children[0].value)
        except ValueError:
            return await interaction.response.send_message("❌ Некорректный ID.", ephemeral=True)
        reason = self.children[1].value

        member = interaction.guild.get_member(user_id)

        # Мгновенный ответ
        await interaction.response.send_message(f"✅ Пользователь {user_id} добавляется в ЧС...", ephemeral=True)

        async def background():
            if not member:
                # Если пользователь не на сервере, просто добавляем в БД без уведомления
                pass
            else:
                try:
                    embed = discord.Embed(
                        title="⛔ Вы в чёрном списке",
                        description=f"Причина: {reason}",
                        color=discord.Color.dark_gray()
                    )
                    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
                    await member.send(embed=embed)
                except:
                    pass

            db.add_to_blacklist(user_id, reason, interaction.user.id)

            log_channel = interaction.guild.get_channel(BLACKLIST_LOG_CHANNEL_ID)
            if log_channel:
                embed = discord.Embed(
                    title="⛔ Добавление в ЧС",
                    description=f"Пользователь {member.mention if member else f'ID:{user_id}'} добавлен в ЧС.",
                    color=discord.Color.dark_gray()
                )
                embed.add_field(name="Модератор", value=interaction.user.mention)
                embed.add_field(name="Причина", value=reason)
                await log_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

        asyncio.create_task(background())

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        traceback.print_exc()
        await interaction.response.send_message("❌ Внутренняя ошибка.", ephemeral=True)


class PanelRemoveBlacklistModal(Modal, title="Удаление из ЧС"):
    def __init__(self):
        super().__init__()
        self.add_item(TextInput(label="ID пользователя", required=True, placeholder="Числовой ID"))
        self.add_item(TextInput(label="Причина удаления", style=discord.TextStyle.paragraph, required=False, max_length=500))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.children[0].value)
        except ValueError:
            return await interaction.response.send_message("❌ Некорректный ID.", ephemeral=True)
        reason = self.children[1].value or "Не указана"

        if not db.is_blacklisted(user_id):
            return await interaction.response.send_message(f"❌ Пользователь {user_id} не в ЧС.", ephemeral=True)

        member = interaction.guild.get_member(user_id)

        # Мгновенный ответ
        await interaction.response.send_message(f"✅ Пользователь {user_id} удаляется из ЧС...", ephemeral=True)

        async def background():
            db.remove_from_blacklist(user_id)

            log_channel = interaction.guild.get_channel(BLACKLIST_LOG_CHANNEL_ID)
            if log_channel:
                embed = discord.Embed(
                    title="✅ Удаление из ЧС",
                    description=f"Пользователь {member.mention if member else f'ID:{user_id}'} удалён из ЧС.",
                    color=discord.Color.green()
                )
                embed.add_field(name="Модератор", value=interaction.user.mention)
                embed.add_field(name="Причина", value=reason, inline=False)
                await log_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

        asyncio.create_task(background())

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        traceback.print_exc()
        await interaction.response.send_message("❌ Внутренняя ошибка.", ephemeral=True)


class BlacklistPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    def _has_access(self, user):
        allowed = [ROLE_MODER, LEADER_ROLE_ID, DEPUTY_LEADER_ROLE_ID]
        return any(role in [r.id for r in user.roles] for role in allowed)

    @discord.ui.button(label="📋 Добавить в ЧС", style=discord.ButtonStyle.danger, custom_id="blacklist_add")
    async def add_blacklist(self, interaction: discord.Interaction, button: Button):
        try:
            if not self._has_access(interaction.user):
                return await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
            await interaction.response.send_modal(PanelBlacklistModal())
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message("❌ Внутренняя ошибка.", ephemeral=True)

    @discord.ui.button(label="✅ Убрать из ЧС", style=discord.ButtonStyle.success, custom_id="blacklist_remove")
    async def remove_blacklist(self, interaction: discord.Interaction, button: Button):
        try:
            if not self._has_access(interaction.user):
                return await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
            await interaction.response.send_modal(PanelRemoveBlacklistModal())
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message("❌ Внутренняя ошибка.", ephemeral=True)


class Blacklist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(BlacklistPanelView())
        print("✅ Persistent view для чёрного списка зарегистрирован")

    async def cog_load(self):
        channel = self.bot.get_channel(BLACKLIST_PANEL_CHANNEL_ID)
        if not channel:
            print("❌ Канал для панели управления чёрным списком не найден.")
            return

        embed = discord.Embed(
            title="🛠 Управление чёрным списком",
            description="Используйте кнопки ниже для добавления или удаления пользователей из ЧС.",
            color=discord.Color.dark_blue()
        )
        view = BlacklistPanelView()

        async for message in channel.history(limit=10):
            if message.author == self.bot.user:
                await message.delete()

        await channel.send(embed=embed, view=view)
        print("✅ Панель управления чёрным списком восстановлена")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_blacklist_panel(self, ctx):
        channel = self.bot.get_channel(BLACKLIST_PANEL_CHANNEL_ID)
        if not channel:
            return await ctx.send("❌ Канал для панели управления не найден. Проверьте BLACKLIST_PANEL_CHANNEL_ID.")

        embed = discord.Embed(
            title="🛠 Управление чёрным списком",
            description="Используйте кнопки ниже для добавления или удаления пользователей из ЧС.",
            color=discord.Color.dark_blue()
        )
        view = BlacklistPanelView()
        await channel.send(embed=embed, view=view)
        await ctx.send("✅ Панель управления чёрным списком установлена.")

async def setup(bot):
    await bot.add_cog(Blacklist(bot))
    print("🎉 Cog Blacklist успешно загружен")