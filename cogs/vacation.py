import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import time
import traceback
import asyncio
from datetime import datetime
from config import VACATION_ROLE_ID, VACATION_LOG_CHANNEL_ID, VACATION_PANEL_CHANNEL_ID
import database as db

# Модальное окно для ухода в отпуск
class VacationModal(Modal, title="Уход в отпуск"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.add_item(TextInput(
            label="Длительность",
            placeholder="например: 2 недели, 10 дней, 1 месяц",
            required=True,
            max_length=50
        ))
        self.add_item(TextInput(
            label="Причина",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500,
            placeholder="Укажите причину отпуска"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        duration = self.children[0].value
        reason = self.children[1].value
        user_id = interaction.user.id
        now = time.time()

        # Проверяем, не в отпуске ли уже
        if db.is_on_vacation(user_id):
            return await interaction.response.send_message("❌ Вы уже в отпуске. Сначала вернитесь из отпуска.", ephemeral=True)

        # Проверяем, есть ли роль отпуска (на случай рассинхронизации)
        role = interaction.guild.get_role(VACATION_ROLE_ID)
        if role and role in interaction.user.roles:
            return await interaction.response.send_message("❌ У вас уже есть роль отпуска. Если это ошибка, обратитесь к администратору.", ephemeral=True)

        # Сохраняем в БД
        db.add_vacation(user_id, now, duration, reason, interaction.channel_id)

        # Выдаём роль
        if role:
            await interaction.user.add_roles(role, reason="Уход в отпуск")

        # Подтверждение пользователю
        await interaction.response.send_message(
            f"✅ Вы ушли в отпуск. Длительность: {duration}. Причина: {reason}\n"
            f"Чтобы вернуться, нажмите кнопку «Отменить отпуск».",
            ephemeral=True
        )

        # Логируем
        log_channel = self.bot.get_channel(VACATION_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="🏖 Уход в отпуск",
                description=f"{interaction.user.mention} ушёл в отпуск.",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Длительность", value=duration, inline=True)
            embed.add_field(name="Причина", value=reason, inline=False)
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            await log_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        traceback.print_exc()
        await interaction.response.send_message("❌ Произошла внутренняя ошибка.", ephemeral=True)


# Persistent view для панели отпусков
class VacationPanelView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🏖 Взять отпуск", style=discord.ButtonStyle.primary, custom_id="vacation_take")
    async def take_vacation(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(VacationModal(self.bot))

    @discord.ui.button(label="↩️ Отменить отпуск", style=discord.ButtonStyle.danger, custom_id="vacation_cancel")
    async def cancel_vacation(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        if not db.is_on_vacation(user_id):
            return await interaction.response.send_message("❌ Вы не в отпуске.", ephemeral=True)

        # Удаляем из БД
        db.remove_vacation(user_id)

        # Снимаем роль
        role = interaction.guild.get_role(VACATION_ROLE_ID)
        if role and role in interaction.user.roles:
            await interaction.user.remove_roles(role, reason="Возвращение из отпуска")

        await interaction.response.send_message("✅ Вы вернулись из отпуска.", ephemeral=True)

        # Логируем
        log_channel = self.bot.get_channel(VACATION_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="↩️ Возвращение из отпуска",
                description=f"{interaction.user.mention} вернулся из отпуска.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            await log_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())


# Основной cog отпусков
class Vacation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(VacationPanelView(self.bot))
        print("✅ Persistent view для отпусков зарегистрирован")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_vacation_panel(self, ctx):
        """Создаёт панель отпусков в указанном канале."""
        channel = self.bot.get_channel(VACATION_PANEL_CHANNEL_ID)
        if not channel:
            return await ctx.send("❌ Канал для панели отпусков не найден. Проверьте VACATION_PANEL_CHANNEL_ID в config.")

        embed = discord.Embed(
            title="🏖 Система отпусков",
            description=(
                "Для того, чтобы уйти в отпуск, вам необходимо нажать на кнопку **«Взять отпуск»** и указать необходимую информацию.\n\n"
                "Чтобы вернуться из отпуска, нажмите на кнопку **«Отменить отпуск»**.\n\n"
                "При уходе в отпуск сохраняются текущие роли, дополнительно выдается роль отпуска."
            ),
            color=0x2F3136,
            timestamp=datetime.now()
        )
        embed.set_footer(text="Система отпусков")

        view = VacationPanelView(self.bot)
        await channel.send(embed=embed, view=view)
        await ctx.send("✅ Панель отпусков установлена.")

    # Опционально: реакция на упоминания (как в AFK)
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.mentions:
            for user in message.mentions:
                if db.is_on_vacation(user.id):
                    vacation_data = db.get_vacation(user.id)
                    if vacation_data:
                        start, duration, reason = vacation_data
                        try:
                            embed = discord.Embed(
                                title="🏖 Пользователь в отпуске",
                                description=f"{user.mention} сейчас в отпуске.",
                                color=discord.Color.blue()
                            )
                            embed.add_field(name="Длительность", value=duration, inline=True)
                            embed.add_field(name="Причина", value=reason, inline=False)
                            await message.author.send(embed=embed)
                        except:
                            pass

async def setup(bot):
    await bot.add_cog(Vacation(bot))
    print("🎉 Cog Vacation успешно загружен")