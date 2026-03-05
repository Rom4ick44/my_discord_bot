import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import json
import traceback
import asyncio
from datetime import datetime
from enum import Enum
from config import (
    REQUEST_CHANNEL_ID, ACCEPTED_CHANNEL_ID, REJECTED_CHANNEL_ID,
    APPLICATION_BUTTON_CHANNEL_ID, APPLICATION_BANNER_URL, VOICE_CHANNEL_ID,
    ROLE_OZON, ROLE_GUEST, ROLE_FAMQ, ROLE_ACADEMY,
    INVITER_ROLE_ID, LEADER_ROLE_ID, DEPUTY_LEADER_ROLE_ID
)
import database as db

QUESTIONS = [
    "Имя и возраст | Статик",
    "Средний онлайн | Прайм-тайм",
    "В каких были семьях и почему ушли?",
    "Почему выбрали именно нашу семью?",
    "Оцените вашу адекватность от 0/10"
]

class AppStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

def has_any_role(user, role_ids):
    user_roles = {r.id for r in user.roles}
    return any(rid in user_roles for rid in role_ids)

async def safe_delete(message):
    try:
        await message.delete()
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass

async def send_to_channel(channel, embed=None, embeds=None):
    if channel:
        await channel.send(embed=embed, embeds=embeds, allowed_mentions=discord.AllowedMentions.none())

def create_past_apps_text(guild, user_id):
    past_apps = db.get_user_applications(user_id)
    lines = []
    for app_id, status, date, msg_id in past_apps:
        if msg_id:
            jump_url = f"https://discord.com/channels/{guild.id}/{REQUEST_CHANNEL_ID}/{msg_id}"
            lines.append(f"[#{app_id} - {status}]({jump_url}) ({date[:10]})")
        else:
            lines.append(f"#{app_id} - {status} ({date[:10]})")
    return "\n".join(lines) if lines else "Нет"

# ---------- Модальное окно заявки ----------
class ApplicationModal(Modal, title="Заявка на вступление"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        for q in QUESTIONS:
            label = q.split('|')[0].strip()[:45]
            self.add_item(TextInput(
                label=label,
                style=discord.TextStyle.paragraph if len(q) > 50 else discord.TextStyle.short,
                required=True,
                max_length=500,
                placeholder="Введите ответ..."
            ))

    async def on_submit(self, interaction: discord.Interaction):
        if not db.are_applications_open():
            return await interaction.response.send_message("❌ Приём заявок закрыт.", ephemeral=True)
        if db.is_blacklisted(interaction.user.id):
            return await interaction.response.send_message("❌ Вы в чёрном списке.", ephemeral=True)

        answers = [item.value for item in self.children]
        answers_json = json.dumps(answers, ensure_ascii=False)

        guild = interaction.guild
        user = interaction.user
        member = guild.get_member(user.id)

        embed1 = discord.Embed(
            title="📋 Новая заявка в семью",
            color=discord.Color.light_gray()
        )
        embed1.set_thumbnail(url=member.display_avatar.url)
        embed1.add_field(name="Пользователь", value=f"> {user.mention}", inline=False)
        embed1.add_field(name="ID", value=f"> {user.id}", inline=False)
        embed1.add_field(name="Дата регистрации", value=f"> {discord.utils.format_dt(user.created_at, style='D')}", inline=False)
        embed1.add_field(name="Присоединился", value=f"> {discord.utils.format_dt(member.joined_at, style='D')}", inline=False)
        embed1.add_field(name="Прошлые заявки", value=f"> {create_past_apps_text(guild, user.id)}", inline=False)
        embed1.add_field(name="Кто рассматривает", value="> Не назначен", inline=False)

        embed2 = discord.Embed(
            title="📝 Ответы на вопросы",
            color=0x2F3136
        )
        for i, (q, ans) in enumerate(zip(QUESTIONS, answers)):
            embed2.add_field(name=q, value=f"```{ans}```", inline=False)

        app_channel = self.bot.get_channel(REQUEST_CHANNEL_ID)
        if not app_channel:
            return await interaction.response.send_message("❌ Канал заявок не найден.", ephemeral=True)

        msg = await app_channel.send(embeds=[embed1, embed2])

        ping_msg = None
        inviter_role = guild.get_role(INVITER_ROLE_ID)
        if inviter_role:
            ping_msg = await app_channel.send(
                inviter_role.mention,
                allowed_mentions=discord.AllowedMentions(roles=True)
            )

        app_id = db.add_application(user.id, answers_json, msg.id, ping_msg.id if ping_msg else None)
        embed1.set_footer(text=f"Номер заявки: {app_id}")

        await msg.edit(embeds=[embed1, embed2], view=ApplicationButtons(self.bot))

        await interaction.response.send_message("✅ Заявка отправлена!", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("❌ Ошибка при отправке.", ephemeral=True)
        traceback.print_exc()


# ---------- Persistent View для кнопок внутри заявки ----------
class ApplicationButtons(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def get_application_data(self, interaction: discord.Interaction):
        message_id = interaction.message.id
        app_data = db.get_application_by_message(message_id)
        if not app_data:
            await interaction.response.send_message("❌ Заявка не найдена в базе данных.", ephemeral=True)
            return None, None
        return app_data, interaction.message

    async def can_interact(self, interaction: discord.Interaction, app_data):
        app_id, owner_id, _, _, _, _, claimed_by, _ = app_data
        leader_ids = [LEADER_ROLE_ID, DEPUTY_LEADER_ROLE_ID]
        if has_any_role(interaction.user, leader_ids):
            return True
        if claimed_by is None or claimed_by == interaction.user.id:
            return True
        return False

    async def update_reviewer(self, message, reviewer_id):
        if not message.embeds:
            return
        embed1 = message.embeds[0]
        new_embed = discord.Embed.from_dict(embed1.to_dict())
        for i, field in enumerate(new_embed.fields):
            if field.name == "Кто рассматривает":
                reviewer = message.guild.get_member(reviewer_id)
                new_embed.set_field_at(i, name="Кто рассматривает", value=f"> {reviewer.mention}", inline=False)
                break
        await message.edit(embeds=[new_embed, message.embeds[1]])

    async def _cleanup(self, message, ping_id):
        if message:
            await safe_delete(message)
        if ping_id:
            try:
                ping = await message.channel.fetch_message(ping_id)
                await safe_delete(ping)
            except:
                pass

    @discord.ui.button(label="📞 Вызвать на обзвон", style=discord.ButtonStyle.gray, custom_id="call_application")
    async def call_callback(self, interaction: discord.Interaction, button: Button):
        try:
            app_data, message = await self.get_application_data(interaction)
            if not app_data:
                return
            if not await self.can_interact(interaction, app_data):
                return await interaction.response.send_message("❌ Заявка уже обрабатывается.", ephemeral=True)

            app_id, user_id, _, _, _, _, claimed_by, _ = app_data
            member = interaction.guild.get_member(user_id)
            if not member:
                return await interaction.response.send_message("❌ Пользователь не найден.", ephemeral=True)

            role_ozon = interaction.guild.get_role(ROLE_OZON)
            if not role_ozon:
                return await interaction.response.send_message("❌ Роль обзвона не найдена.", ephemeral=True)

            # Немедленный ответ
            await interaction.response.send_message(f"✅ Роль {role_ozon.name} выдана.", ephemeral=True)

            # Фоновые задачи
            async def background():
                if claimed_by is None:
                    db.set_application_claimed(app_id, interaction.user.id)

                await member.add_roles(role_ozon, reason="Вызов на обзвон")

                voice_channel = interaction.guild.get_channel(VOICE_CHANNEL_ID)
                voice_link = f"https://discord.com/channels/{interaction.guild.id}/{VOICE_CHANNEL_ID}" if voice_channel else "голосовой канал"

                try:
                    embed = discord.Embed(
                        title="📞 Вызов на обзвон",
                        description=f"Вас вызвали на обзвон! Зайдите в {voice_link}.",
                        color=discord.Color.light_gray()
                    )
                    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
                    await member.send(embed=embed)
                except:
                    pass

                await self.update_reviewer(message, interaction.user.id)

            asyncio.create_task(background())
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message("❌ Внутренняя ошибка.", ephemeral=True)

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.success, custom_id="accept_application")
    async def accept_callback(self, interaction: discord.Interaction, button: Button):
        try:
            app_data, message = await self.get_application_data(interaction)
            if not app_data:
                return
            if not await self.can_interact(interaction, app_data):
                return await interaction.response.send_message("❌ Заявка уже обрабатывается.", ephemeral=True)

            app_id, user_id, _, _, _, _, _, ping_id = app_data
            member = interaction.guild.get_member(user_id)
            if not member:
                return await interaction.response.send_message("❌ Пользователь не найден.", ephemeral=True)

            # Немедленный ответ
            await interaction.response.send_message("✅ Заявка принята.", ephemeral=True)

            # Фоновые задачи
            async def background():
                roles = {
                    'ozon': interaction.guild.get_role(ROLE_OZON),
                    'guest': interaction.guild.get_role(ROLE_GUEST),
                    'famq': interaction.guild.get_role(ROLE_FAMQ),
                    'academy': interaction.guild.get_role(ROLE_ACADEMY)
                }
                if roles['ozon'] and roles['ozon'] in member.roles:
                    await member.remove_roles(roles['ozon'])
                if roles['guest'] and roles['guest'] in member.roles:
                    await member.remove_roles(roles['guest'])
                if roles['famq']:
                    await member.add_roles(roles['famq'])
                if roles['academy']:
                    await member.add_roles(roles['academy'])

                db.update_application_status(app_id, AppStatus.ACCEPTED.value, interaction.user.id)

                try:
                    embed = discord.Embed(
                        title="✅ Заявка принята",
                        description="Добро пожаловать в семью!",
                        color=discord.Color.green()
                    )
                    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
                    await member.send(embed=embed)
                except:
                    pass

                accepted_channel = self.bot.get_channel(ACCEPTED_CHANNEL_ID)
                if accepted_channel:
                    e1 = discord.Embed.from_dict(message.embeds[0].to_dict())
                    e2 = discord.Embed.from_dict(message.embeds[1].to_dict())
                    e1.add_field(name="Рассмотрел", value=interaction.user.mention, inline=False)
                    e1.add_field(name="Статус", value="✅ Принята", inline=False)
                    await send_to_channel(accepted_channel, embeds=[e1, e2])

                await self._cleanup(message, ping_id)

            asyncio.create_task(background())
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message("❌ Внутренняя ошибка.", ephemeral=True)

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger, custom_id="reject_application")
    async def reject_callback(self, interaction: discord.Interaction, button: Button):
        try:
            app_data, message = await self.get_application_data(interaction)
            if not app_data:
                return
            if not await self.can_interact(interaction, app_data):
                return await interaction.response.send_message("❌ Заявка уже обрабатывается.", ephemeral=True)

            modal = RejectModal(message.id, self.bot)
            await interaction.response.send_modal(modal)
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message("❌ Внутренняя ошибка.", ephemeral=True)


# ---------- Модалка отклонения ----------
class RejectModal(Modal, title="Отклонение заявки"):
    def __init__(self, message_id, bot):
        super().__init__()
        self.message_id = message_id
        self.bot = bot
        self.add_item(TextInput(
            label="Причина отказа",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500,
            placeholder="Укажите причину..."
        ))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            reason = self.children[0].value

            app_data = db.get_application_by_message(self.message_id)
            if not app_data:
                return await interaction.response.send_message("❌ Заявка не найдена.", ephemeral=True)

            app_id, user_id, _, _, _, _, _, ping_id = app_data
            member = interaction.guild.get_member(user_id)
            if not member:
                return await interaction.response.send_message("❌ Пользователь не найден.", ephemeral=True)

            # Немедленный ответ
            await interaction.response.send_message("✅ Заявка отклонена.", ephemeral=True)

            # Фоновые задачи
            async def background():
                db.update_application_status(app_id, AppStatus.REJECTED.value, interaction.user.id)

                try:
                    embed = discord.Embed(
                        title="❌ Заявка отклонена",
                        description=f"Причина: {reason}",
                        color=discord.Color.red()
                    )
                    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
                    await member.send(embed=embed)
                except:
                    pass

                role_ozon = interaction.guild.get_role(ROLE_OZON)
                if role_ozon and role_ozon in member.roles:
                    await member.remove_roles(role_ozon)

                rejected_channel = self.bot.get_channel(REJECTED_CHANNEL_ID)
                if rejected_channel:
                    try:
                        msg = await interaction.channel.fetch_message(self.message_id)
                        e1 = discord.Embed.from_dict(msg.embeds[0].to_dict())
                        e2 = discord.Embed.from_dict(msg.embeds[1].to_dict())
                        e1.add_field(name="Рассмотрел", value=interaction.user.mention, inline=False)
                        e1.add_field(name="Статус", value="❌ Отклонена", inline=False)
                        e1.add_field(name="Причина", value=reason, inline=False)
                        await send_to_channel(rejected_channel, embeds=[e1, e2])
                    except:
                        pass

                try:
                    msg = await interaction.channel.fetch_message(self.message_id)
                    await safe_delete(msg)
                except:
                    pass
                if ping_id:
                    try:
                        ping = await interaction.channel.fetch_message(ping_id)
                        await safe_delete(ping)
                    except:
                        pass

            asyncio.create_task(background())
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message("❌ Внутренняя ошибка.", ephemeral=True)


# ---------- Persistent View для кнопки подачи заявки ----------
class ApplyButtonView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="📋 Подать заявку в семью", style=discord.ButtonStyle.gray, custom_id="apply_button")
    async def apply_button_callback(self, interaction: discord.Interaction, button: Button):
        if not db.are_applications_open():
            return await interaction.response.send_message("❌ Приём заявок закрыт.", ephemeral=True)
        if db.is_blacklisted(interaction.user.id):
            return await interaction.response.send_message("❌ Вы в чёрном списке.", ephemeral=True)
        await interaction.response.send_modal(ApplicationModal(self.bot))


# ---------- Cog ----------
class Application(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        db.init_db()
        self.bot.add_view(ApplicationButtons(self.bot))
        self.bot.add_view(ApplyButtonView(self.bot))
        print("✅ Persistent view для заявок зарегистрированы")
        self.bot.loop.create_task(self.restore_application_buttons())

    async def restore_application_buttons(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(2)
        channel = self.bot.get_channel(REQUEST_CHANNEL_ID)
        if not channel:
            return
        count = 0
        async for message in channel.history(limit=200):
            if message.author == self.bot.user and len(message.embeds) == 2:
                if db.get_application_by_message(message.id):
                    await message.edit(view=ApplicationButtons(self.bot))
                    count += 1
        print(f"✅ Восстановлено {count} кнопок для заявок")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def fix_app_buttons(self, ctx):
        """Принудительно восстановить кнопки для всех заявок в канале."""
        channel = self.bot.get_channel(REQUEST_CHANNEL_ID)
        if not channel:
            return await ctx.send("❌ Канал заявок не найден.")
        count = 0
        async for message in channel.history(limit=500):
            if message.author == self.bot.user and len(message.embeds) == 2:
                if db.get_application_by_message(message.id):
                    await message.edit(view=ApplicationButtons(self.bot))
                    count += 1
        await ctx.send(f"✅ Восстановлено {count} кнопок.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_app(self, ctx):
        """Создаёт сообщение с кнопкой подачи заявки в заданном канале."""
        channel = self.bot.get_channel(APPLICATION_BUTTON_CHANNEL_ID)
        if not channel:
            return await ctx.send("❌ Канал для кнопки не найден.")

        inviter_role = ctx.guild.get_role(INVITER_ROLE_ID)
        inviter_mention = inviter_role.mention if inviter_role else "@Inviter"

        embed = discord.Embed(
            title="Добро пожаловать в семью REED!",
            description=(
                "Уведомления о приглашении на обзвон отправляются в личные сообщения.\n\n"
                f"> В среднем заявки обрабатываются в течение 2–4 часов — всё зависит от загруженности {inviter_mention}."
            ),
            color=0x000000
        )
        if APPLICATION_BANNER_URL:
            embed.set_image(url=APPLICATION_BANNER_URL)

        await channel.send(embed=embed, view=ApplyButtonView(self.bot))
        await ctx.send("✅ Кнопка заявок установлена.")

async def setup(bot):
    await bot.add_cog(Application(bot))
    print("🎉 Cog Application успешно загружен")