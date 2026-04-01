import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
import asyncio
import re
import database as db
from config import (
    EVENTS_CREATION_CHANNEL_ID, EVENTS_CHANNEL_ID, EVENTS_LOG_CHANNEL_ID,
    EVENT_PRIVILEGED_ROLES, EVENT_ADMIN_ROLES, EVENT_VOICE_CHANNEL_ID
)

# ---------- Вспомогательные функции ----------
def has_event_admin(interaction, event_data):
    if interaction.user.id == event_data['creator_id']:
        return True
    user_roles = [r.id for r in interaction.user.roles]
    return any(role in user_roles for role in EVENT_ADMIN_ROLES)

async def send_log(guild, text):
    channel = guild.get_channel(EVENTS_LOG_CHANNEL_ID)
    if channel:
        await channel.send(text)

def format_participants_list(event_id, role):
    users = db.get_participants(event_id, role)
    if not users:
        return "Никого"
    return "\n".join([f"<@{uid}>" for uid in users])

def format_info_embed(event_data, event_id):
    embed = discord.Embed(
        title=event_data['title'],
        color=0x2F3136
    )
    embed.add_field(name="Тип", value=event_data['type'].capitalize(), inline=True)
    if event_data['server']:
        embed.add_field(name="Сервер", value=event_data['server'], inline=True)
    if event_data['time']:
        embed.add_field(name="Время", value=event_data['time'], inline=True)
    embed.add_field(name="Лимит", value=str(event_data['limit']), inline=True)
    if event_data['group_name']:
        embed.add_field(name="Группа", value=event_data['group_name'], inline=True)
    embed.add_field(name="ID мероприятия", value=str(event_id), inline=False)
    embed.set_footer(text=f"Создатель: {event_data['creator_id']}")
    return embed

def format_main_embed(event_id, limit, title):
    main_count = db.count_participants(event_id, 'main')
    embed = discord.Embed(
        title=f"Основной состав | {main_count}/{limit}",
        color=0x2F3136
    )
    embed.add_field(name="Список", value=format_participants_list(event_id, 'main'), inline=False)
    return embed

def format_sub_embed(event_id):
    sub_count = db.count_participants(event_id, 'sub')
    embed = discord.Embed(
        title=f"Запасной состав | {sub_count}",
        color=0x2F3136
    )
    embed.add_field(name="Список", value=format_participants_list(event_id, 'sub'), inline=False)
    return embed

# ---------- Модальные окна ----------
class CreateEventModal(Modal, title="Создание мероприятия"):
    def __init__(self, event_type):
        super().__init__()
        self.event_type = event_type
        self.add_item(TextInput(label="Название", required=True, max_length=100))
        self.add_item(TextInput(label="Лимит (целое число)", required=True, placeholder="35"))
        self.add_item(TextInput(label="Время", required=True, placeholder="16:16"))
        self.add_item(TextInput(label="Сервер", required=False, placeholder="Denver"))
        self.add_item(TextInput(label="Группа", required=False, placeholder="Z6AXX"))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            limit = int(self.children[1].value)
        except ValueError:
            return await interaction.followup.send("❌ Лимит должен быть числом.", ephemeral=True)

        title = self.children[0].value
        time = self.children[2].value
        server = self.children[3].value if len(self.children) > 3 else None
        group = self.children[4].value if len(self.children) > 4 else None

        event_channel = interaction.guild.get_channel(EVENTS_CHANNEL_ID)
        if not event_channel:
            return await interaction.followup.send("❌ Канал для мероприятий не настроен.", ephemeral=True)

        # Отправляем три сообщения
        info_embed = discord.Embed(
            title=title,
            color=0x2F3136
        )
        info_embed.add_field(name="Тип", value=self.event_type.capitalize(), inline=True)
        if server:
            info_embed.add_field(name="Сервер", value=server, inline=True)
        info_embed.add_field(name="Время", value=time, inline=True)
        info_embed.add_field(name="Лимит", value=str(limit), inline=True)
        if group:
            info_embed.add_field(name="Группа", value=group, inline=True)
        info_embed.add_field(name="ID мероприятия", value="Сохранение...", inline=False)
        info_embed.set_footer(text=f"Создатель: {interaction.user.id}")

        main_embed = discord.Embed(
            title=f"Основной состав | 0/{limit}",
            color=0x2F3136
        )
        main_embed.add_field(name="Список", value="Никого", inline=False)

        sub_embed = discord.Embed(
            title="Запасной состав | 0",
            color=0x2F3136
        )
        sub_embed.add_field(name="Список", value="Никого", inline=False)

        info_msg = await event_channel.send(embed=info_embed)
        main_msg = await event_channel.send(embed=main_embed)
        sub_msg = await event_channel.send(embed=sub_embed)

        event_id = db.add_event(
            info_msg.id, main_msg.id, sub_msg.id,
            event_channel.id, interaction.user.id,
            self.event_type, title, server, time, None, limit, group
        )

        event_data = db.get_event_by_message(info_msg.id)
        # Прикрепляем view к третьему сообщению (sub_msg)
        view = EventView(event_id, event_data, info_msg.id, main_msg.id, sub_msg.id)
        await sub_msg.edit(view=view)  # добавляем кнопки к sub_msg
        # Обновляем остальные сообщения без view
        await info_msg.edit(embed=format_info_embed(event_data, event_id))
        await main_msg.edit(embed=format_main_embed(event_id, limit, title))
        # sub_msg уже имеет правильный embed и view

        await interaction.followup.send(f"✅ Мероприятие создано! {info_msg.jump_url}", ephemeral=True)
        await send_log(interaction.guild, f"✅ Создано мероприятие **{title}** (ID {event_id}) пользователем {interaction.user.mention}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.followup.send("❌ Ошибка при создании.", ephemeral=True)
        print(error)

class EditEventModal(Modal, title="Редактирование мероприятия"):
    def __init__(self, event_data, info_msg_id, main_msg_id, sub_msg_id):
        super().__init__()
        self.event_data = event_data
        self.info_msg_id = info_msg_id
        self.main_msg_id = main_msg_id
        self.sub_msg_id = sub_msg_id
        self.add_item(TextInput(label="Название", default=event_data['title'], required=True, max_length=100))
        self.add_item(TextInput(label="Лимит", default=str(event_data['limit']), required=True))
        self.add_item(TextInput(label="Время", default=event_data['time'], required=True))
        self.add_item(TextInput(label="Сервер", default=event_data['server'] or "", required=False))
        self.add_item(TextInput(label="Группа", default=event_data['group_name'] or "", required=False))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            limit = int(self.children[1].value)
        except ValueError:
            return await interaction.followup.send("❌ Лимит должен быть числом.", ephemeral=True)

        updates = {
            'title': self.children[0].value,
            'limit': limit,
            'time': self.children[2].value,
            'server': self.children[3].value,
            'group_name': self.children[4].value,
        }
        db.update_event(self.event_data['id'], **updates)

        new_event_data = db.get_event_by_message(self.info_msg_id)
        new_event_data['message_id_info'] = self.info_msg_id
        new_event_data['message_id_main'] = self.main_msg_id
        new_event_data['message_id_sub'] = self.sub_msg_id

        channel = interaction.guild.get_channel(new_event_data['channel_id'])
        if channel:
            try:
                info_msg = await channel.fetch_message(self.info_msg_id)
                main_msg = await channel.fetch_message(self.main_msg_id)
                sub_msg = await channel.fetch_message(self.sub_msg_id)
                await info_msg.edit(embed=format_info_embed(new_event_data, self.event_data['id']))
                await main_msg.edit(embed=format_main_embed(self.event_data['id'], limit, new_event_data['title']))
                await sub_msg.edit(embed=format_sub_embed(self.event_data['id']))
            except:
                pass
        await interaction.followup.send("✅ Мероприятие обновлено.", ephemeral=True)
        await send_log(interaction.guild, f"📝 Отредактировано мероприятие **{self.event_data['title']}** (ID {self.event_data['id']}) пользователем {interaction.user.mention}")

class ImportModal(Modal, title="Импорт участников"):
    def __init__(self, event_id, role, event_data, info_msg_id, main_msg_id, sub_msg_id):
        super().__init__()
        self.event_id = event_id
        self.role = role
        self.event_data = event_data
        self.info_msg_id = info_msg_id
        self.main_msg_id = main_msg_id
        self.sub_msg_id = sub_msg_id
        self.add_item(TextInput(label="ID пользователей (через запятую)", required=True, placeholder="123456789, 987654321"))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        ids_text = self.children[0].value
        user_ids = re.findall(r'\d+', ids_text)
        added = 0
        for uid_str in user_ids:
            uid = int(uid_str)
            if db.add_participant(self.event_id, uid, self.role):
                added += 1
        await interaction.followup.send(f"✅ Добавлено {added} участников в {'основной' if self.role=='main' else 'запасной'} состав.", ephemeral=True)

        channel = interaction.guild.get_channel(self.event_data['channel_id'])
        if channel:
            try:
                main_msg = await channel.fetch_message(self.main_msg_id)
                sub_msg = await channel.fetch_message(self.sub_msg_id)
                await main_msg.edit(embed=format_main_embed(self.event_id, self.event_data['limit'], self.event_data['title']))
                await sub_msg.edit(embed=format_sub_embed(self.event_id))
            except:
                pass
        await send_log(interaction.guild, f"📥 Импорт участников в мероприятие {self.event_id} (роль {self.role}) пользователем {interaction.user.mention}")

class AddParticipantModal(Modal, title="Вписать участника"):
    def __init__(self, event_id, event_data, info_msg_id, main_msg_id, sub_msg_id):
        super().__init__()
        self.event_id = event_id
        self.event_data = event_data
        self.info_msg_id = info_msg_id
        self.main_msg_id = main_msg_id
        self.sub_msg_id = sub_msg_id
        self.add_item(TextInput(label="ID пользователя", required=True, placeholder="123456789"))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            uid = int(self.children[0].value)
        except ValueError:
            return await interaction.followup.send("❌ Некорректный ID.", ephemeral=True)
        if db.add_participant(self.event_id, uid, 'sub'):
            await interaction.followup.send(f"✅ Пользователь <@{uid}> добавлен в запасной состав.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Пользователь уже в списках.", ephemeral=True)

        channel = interaction.guild.get_channel(self.event_data['channel_id'])
        if channel:
            try:
                sub_msg = await channel.fetch_message(self.sub_msg_id)
                await sub_msg.edit(embed=format_sub_embed(self.event_id))
            except:
                pass
        await send_log(interaction.guild, f"✍️ Вписан участник <@{uid}> в мероприятие {self.event_id} пользователем {interaction.user.mention}")

class RemoveParticipantModal(Modal, title="Выписать участника"):
    def __init__(self, event_id, event_data, info_msg_id, main_msg_id, sub_msg_id):
        super().__init__()
        self.event_id = event_id
        self.event_data = event_data
        self.info_msg_id = info_msg_id
        self.main_msg_id = main_msg_id
        self.sub_msg_id = sub_msg_id
        self.add_item(TextInput(label="ID пользователя", required=True, placeholder="123456789"))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            uid = int(self.children[0].value)
        except ValueError:
            return await interaction.followup.send("❌ Некорректный ID.", ephemeral=True)
        db.remove_participant(self.event_id, uid)
        await interaction.followup.send(f"✅ Пользователь <@{uid}> удалён из всех списков.", ephemeral=True)

        channel = interaction.guild.get_channel(self.event_data['channel_id'])
        if channel:
            try:
                main_msg = await channel.fetch_message(self.main_msg_id)
                sub_msg = await channel.fetch_message(self.sub_msg_id)
                await main_msg.edit(embed=format_main_embed(self.event_id, self.event_data['limit'], self.event_data['title']))
                await sub_msg.edit(embed=format_sub_embed(self.event_id))
            except:
                pass
        await send_log(interaction.guild, f"🚫 Выписан участник <@{uid}> из мероприятия {self.event_id} пользователем {interaction.user.mention}")

# ---------- Select для административных действий ----------
class AdminSelect(Select):
    def __init__(self, event_id, event_data, info_msg_id, main_msg_id, sub_msg_id):
        self.event_id = event_id
        self.event_data = event_data
        self.info_msg_id = info_msg_id
        self.main_msg_id = main_msg_id
        self.sub_msg_id = sub_msg_id
        options = [
            discord.SelectOption(label="✏️ Редактировать информацию", value="edit"),
            discord.SelectOption(label="🔓 Открыть/закрыть", value="toggle_open"),
            discord.SelectOption(label="📋 Экспорт списков", value="export"),
            discord.SelectOption(label="📥 Импорт списков", value="import"),
            discord.SelectOption(label="🧹 Очистить списки", value="clear"),
            discord.SelectOption(label="✍️ Вписать участника", value="add"),
            discord.SelectOption(label="🚫 Выписать участника", value="remove"),
            discord.SelectOption(label="🎤 Проверка по войсу", value="voice_check"),
            discord.SelectOption(label="✅ Завершить", value="finish"),
        ]
        super().__init__(placeholder="Административные действия...", min_values=1, max_values=1, options=options, custom_id=f"admin_select_{event_id}")

    async def callback(self, interaction: discord.Interaction):
        if not has_event_admin(interaction, self.event_data):
            return await interaction.response.send_message("❌ У вас нет прав на это действие.", ephemeral=True)

        action = self.values[0]

        if action in ("edit", "import", "add", "remove"):
            if action == "edit":
                modal = EditEventModal(self.event_data, self.info_msg_id, self.main_msg_id, self.sub_msg_id)
                await interaction.response.send_modal(modal)
            elif action == "import":
                view = RoleSelectView(self.event_id, self.event_data, self.info_msg_id, self.main_msg_id, self.sub_msg_id)
                await interaction.response.send_message("Выберите состав для импорта:", view=view, ephemeral=True)
            elif action == "add":
                modal = AddParticipantModal(self.event_id, self.event_data, self.info_msg_id, self.main_msg_id, self.sub_msg_id)
                await interaction.response.send_modal(modal)
            elif action == "remove":
                modal = RemoveParticipantModal(self.event_id, self.event_data, self.info_msg_id, self.main_msg_id, self.sub_msg_id)
                await interaction.response.send_modal(modal)
            return

        await interaction.response.defer(ephemeral=True)

        if action == "toggle_open":
            new_state = 0 if self.event_data['is_open'] else 1
            db.update_event(self.event_id, is_open=new_state)
            self.event_data['is_open'] = new_state
            channel = interaction.guild.get_channel(self.event_data['channel_id'])
            if channel:
                try:
                    info_msg = await channel.fetch_message(self.info_msg_id)
                    await info_msg.edit(embed=format_info_embed(self.event_data, self.event_id))
                except:
                    pass
            state_text = "открыта" if new_state else "закрыта"
            await interaction.followup.send(f"✅ Регистрация {state_text}.", ephemeral=True)
            await send_log(interaction.guild, f"🔓 Регистрация на мероприятие **{self.event_data['title']}** {state_text} пользователем {interaction.user.mention}")

        elif action == "export":
            main_ids = db.get_participants(self.event_id, 'main')
            sub_ids = db.get_participants(self.event_id, 'sub')
            main_text = ", ".join(str(uid) for uid in main_ids) if main_ids else "пусто"
            sub_text = ", ".join(str(uid) for uid in sub_ids) if sub_ids else "пусто"
            await interaction.followup.send(
                f"**Основной состав:**\n{main_text}\n\n**Запасной состав:**\n{sub_text}",
                ephemeral=True
            )

        elif action == "clear":
            view = ClearSelectView(self.event_id, self.event_data, self.info_msg_id, self.main_msg_id, self.sub_msg_id)
            await interaction.followup.send("Выберите, какой состав очистить:", view=view, ephemeral=True)

        elif action == "voice_check":
            voice_channel = interaction.guild.get_channel(EVENT_VOICE_CHANNEL_ID)
            if not voice_channel:
                await interaction.followup.send("❌ Голосовой канал для проверки не настроен.", ephemeral=True)
                return
            main_participants = db.get_participants(self.event_id, 'main')
            if not main_participants:
                await interaction.followup.send("В основном составе никого нет.", ephemeral=True)
                return
            members_in_voice = [m.id for m in voice_channel.members]
            missing = [uid for uid in main_participants if uid not in members_in_voice]
            if missing:
                missing_mentions = " ".join(f"<@{uid}>" for uid in missing)
                await interaction.followup.send(f"❌ Следующие участники отсутствуют в войсе:\n{missing_mentions}", ephemeral=True)
            else:
                await interaction.followup.send("✅ Все участники основного состава находятся в войс-канале.", ephemeral=True)

        elif action == "finish":
            db.delete_event(self.event_id)
            channel = interaction.guild.get_channel(self.event_data['channel_id'])
            if channel:
                try:
                    info_msg = await channel.fetch_message(self.info_msg_id)
                    main_msg = await channel.fetch_message(self.main_msg_id)
                    sub_msg = await channel.fetch_message(self.sub_msg_id)
                    embed = discord.Embed(
                        title=self.event_data['title'],
                        description="Мероприятие завершено.",
                        color=0x1E1F22
                    )
                    await info_msg.edit(embed=embed)
                    await main_msg.delete()
                    await sub_msg.delete()
                except:
                    pass
            await interaction.followup.send("✅ Мероприятие завершено.", ephemeral=True)
            await send_log(interaction.guild, f"🏁 Завершено мероприятие **{self.event_data['title']}** (ID {self.event_id}) пользователем {interaction.user.mention}")

# ---------- Select для выбора состава при импорте ----------
class RoleSelectView(View):
    def __init__(self, event_id, event_data, info_msg_id, main_msg_id, sub_msg_id):
        super().__init__(timeout=60)
        self.event_id = event_id
        self.event_data = event_data
        self.info_msg_id = info_msg_id
        self.main_msg_id = main_msg_id
        self.sub_msg_id = sub_msg_id

    @discord.ui.select(placeholder="Выберите состав", options=[
        discord.SelectOption(label="Основной состав", value="main"),
        discord.SelectOption(label="Запасной состав", value="sub")
    ])
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.Select):
        role = select.values[0]
        modal = ImportModal(self.event_id, role, self.event_data, self.info_msg_id, self.main_msg_id, self.sub_msg_id)
        await interaction.response.send_modal(modal)

class ClearSelectView(View):
    def __init__(self, event_id, event_data, info_msg_id, main_msg_id, sub_msg_id):
        super().__init__(timeout=60)
        self.event_id = event_id
        self.event_data = event_data
        self.info_msg_id = info_msg_id
        self.main_msg_id = main_msg_id
        self.sub_msg_id = sub_msg_id

    @discord.ui.select(placeholder="Выберите состав", options=[
        discord.SelectOption(label="Основной состав", value="main"),
        discord.SelectOption(label="Запасной состав", value="sub"),
        discord.SelectOption(label="Оба состава", value="both")
    ])
    async def select_clear(self, interaction: discord.Interaction, select: discord.ui.Select):
        choice = select.values[0]
        if choice == "both":
            db.clear_participants(self.event_id)
            await interaction.response.send_message("✅ Все списки очищены.", ephemeral=True)
        else:
            db.clear_participants(self.event_id, choice)
            await interaction.response.send_message(f"✅ {choice.capitalize()} состав очищен.", ephemeral=True)

        channel = interaction.guild.get_channel(self.event_data['channel_id'])
        if channel:
            try:
                main_msg = await channel.fetch_message(self.main_msg_id)
                sub_msg = await channel.fetch_message(self.sub_msg_id)
                await main_msg.edit(embed=format_main_embed(self.event_id, self.event_data['limit'], self.event_data['title']))
                await sub_msg.edit(embed=format_sub_embed(self.event_id))
            except:
                pass

# ---------- Кнопки для всех пользователей ----------
class RegisterButton(Button):
    def __init__(self, event_id, event_data, info_msg_id, main_msg_id, sub_msg_id):
        super().__init__(label="📝 Откинуть +", style=discord.ButtonStyle.primary, custom_id=f"register_{event_id}")
        self.event_id = event_id
        self.event_data = event_data
        self.info_msg_id = info_msg_id
        self.main_msg_id = main_msg_id
        self.sub_msg_id = sub_msg_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not self.event_data['is_open']:
            return await interaction.followup.send("❌ Регистрация на мероприятие закрыта.", ephemeral=True)

        user_id = interaction.user.id
        participants = db.get_participants(self.event_id)
        if any(p[0] == user_id for p in participants):
            return await interaction.followup.send("❌ Вы уже записаны.", ephemeral=True)

        user_roles = [r.id for r in interaction.user.roles]
        is_privileged = any(role in user_roles for role in EVENT_PRIVILEGED_ROLES)

        if is_privileged:
            main_count = db.count_participants(self.event_id, 'main')
            if main_count >= self.event_data['limit']:
                return await interaction.followup.send("❌ Основной состав уже заполнен.", ephemeral=True)
            db.add_participant(self.event_id, user_id, 'main')
            await interaction.followup.send("✅ Вы записаны в основной состав!", ephemeral=True)
            await send_log(interaction.guild, f"📝 {interaction.user.mention} записался в основной состав мероприятия **{self.event_data['title']}**")
        else:
            db.add_participant(self.event_id, user_id, 'sub')
            await interaction.followup.send("✅ Вы записаны в запасной состав!", ephemeral=True)
            await send_log(interaction.guild, f"📝 {interaction.user.mention} записался в запасной состав мероприятия **{self.event_data['title']}**")

        channel = interaction.guild.get_channel(self.event_data['channel_id'])
        if channel:
            try:
                main_msg = await channel.fetch_message(self.main_msg_id)
                sub_msg = await channel.fetch_message(self.sub_msg_id)
                await main_msg.edit(embed=format_main_embed(self.event_id, self.event_data['limit'], self.event_data['title']))
                await sub_msg.edit(embed=format_sub_embed(self.event_id))
            except:
                pass

class UnregisterButton(Button):
    def __init__(self, event_id, event_data, info_msg_id, main_msg_id, sub_msg_id):
        super().__init__(label="❌ Убрать +", style=discord.ButtonStyle.danger, custom_id=f"unregister_{event_id}")
        self.event_id = event_id
        self.event_data = event_data
        self.info_msg_id = info_msg_id
        self.main_msg_id = main_msg_id
        self.sub_msg_id = sub_msg_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        participants = db.get_participants(self.event_id)
        if not any(p[0] == user_id for p in participants):
            return await interaction.followup.send("❌ Вы не записаны на мероприятие.", ephemeral=True)

        db.remove_participant(self.event_id, user_id)
        await interaction.followup.send("✅ Вы удалены из списков.", ephemeral=True)
        await send_log(interaction.guild, f"❌ {interaction.user.mention} удалился из мероприятия **{self.event_data['title']}**")

        channel = interaction.guild.get_channel(self.event_data['channel_id'])
        if channel:
            try:
                main_msg = await channel.fetch_message(self.main_msg_id)
                sub_msg = await channel.fetch_message(self.sub_msg_id)
                await main_msg.edit(embed=format_main_embed(self.event_id, self.event_data['limit'], self.event_data['title']))
                await sub_msg.edit(embed=format_sub_embed(self.event_id))
            except:
                pass

class MoveButton(Button):
    def __init__(self, event_id, event_data, info_msg_id, main_msg_id, sub_msg_id):
        super().__init__(label="🔄 Перенести", style=discord.ButtonStyle.secondary, custom_id=f"move_{event_id}")
        self.event_id = event_id
        self.event_data = event_data
        self.info_msg_id = info_msg_id
        self.main_msg_id = main_msg_id
        self.sub_msg_id = sub_msg_id

    async def callback(self, interaction: discord.Interaction):
        if not has_event_admin(interaction, self.event_data):
            return await interaction.response.send_message("❌ У вас нет прав на это действие.", ephemeral=True)

        participants = db.get_participants(self.event_id)
        if not participants:
            return await interaction.response.send_message("❌ Списки пусты.", ephemeral=True)

        options = []
        for uid, role in participants:
            user = interaction.guild.get_member(uid)
            name = user.display_name if user else str(uid)
            options.append(discord.SelectOption(label=name, value=str(uid), description=f"Текущий состав: {role}"))

        select = discord.ui.Select(placeholder="Выберите участника", options=options)

        async def select_callback(interaction2):
            user_id = int(select.values[0])
            view = MoveDirectionView(self.event_id, user_id, self.event_data, self.info_msg_id, self.main_msg_id, self.sub_msg_id)
            await interaction2.response.send_message("Куда переместить?", view=view, ephemeral=True)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Выберите участника для перемещения:", view=view, ephemeral=True)

class MoveDirectionView(View):
    def __init__(self, event_id, user_id, event_data, info_msg_id, main_msg_id, sub_msg_id):
        super().__init__(timeout=60)
        self.event_id = event_id
        self.user_id = user_id
        self.event_data = event_data
        self.info_msg_id = info_msg_id
        self.main_msg_id = main_msg_id
        self.sub_msg_id = sub_msg_id

    @discord.ui.select(placeholder="Куда переместить?", options=[
        discord.SelectOption(label="В основной состав", value="main"),
        discord.SelectOption(label="В запасной состав", value="sub")
    ])
    async def select_direction(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer(ephemeral=True)

        direction = select.values[0]
        current_role = None
        participants = db.get_participants(self.event_id)
        for uid, role in participants:
            if uid == self.user_id:
                current_role = role
                break
        if current_role == direction:
            return await interaction.followup.send("❌ Пользователь уже в этом составе.", ephemeral=True)

        if direction == 'main':
            main_count = db.count_participants(self.event_id, 'main')
            if main_count >= self.event_data['limit']:
                return await interaction.followup.send("❌ Основной состав заполнен.", ephemeral=True)
            db.remove_participant(self.event_id, self.user_id)
            db.add_participant(self.event_id, self.user_id, 'main')
        else:
            db.remove_participant(self.event_id, self.user_id)
            db.add_participant(self.event_id, self.user_id, 'sub')

        channel = interaction.guild.get_channel(self.event_data['channel_id'])
        if channel:
            try:
                main_msg = await channel.fetch_message(self.main_msg_id)
                sub_msg = await channel.fetch_message(self.sub_msg_id)
                await main_msg.edit(embed=format_main_embed(self.event_id, self.event_data['limit'], self.event_data['title']))
                await sub_msg.edit(embed=format_sub_embed(self.event_id))
            except:
                pass

        await interaction.followup.send(f"✅ Пользователь <@{self.user_id}> перемещён в {direction} состав.", ephemeral=True)
        await send_log(interaction.guild, f"🔄 Пользователь <@{self.user_id}> перемещён в {direction} состав мероприятия **{self.event_data['title']}** пользователем {interaction.user.mention}")

# ---------- Основной View мероприятия ----------
class EventView(View):
    def __init__(self, event_id, event_data, info_msg_id, main_msg_id, sub_msg_id):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.event_data = event_data
        self.info_msg_id = info_msg_id
        self.main_msg_id = main_msg_id
        self.sub_msg_id = sub_msg_id
        self.add_item(RegisterButton(event_id, event_data, info_msg_id, main_msg_id, sub_msg_id))
        self.add_item(UnregisterButton(event_id, event_data, info_msg_id, main_msg_id, sub_msg_id))
        self.add_item(MoveButton(event_id, event_data, info_msg_id, main_msg_id, sub_msg_id))
        self.add_item(AdminSelect(event_id, event_data, info_msg_id, main_msg_id, sub_msg_id))

# ---------- Ког ----------
class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(PersistentCreateButtonView(self.bot))
        self.bot.loop.create_task(self.restore_events())

    async def restore_events(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(2)
        channel = self.bot.get_channel(EVENTS_CHANNEL_ID)
        if not channel:
            return
        async for message in channel.history(limit=200):
            if message.author == self.bot.user and message.embeds:
                event_data = db.get_event_by_message(message.id)
                if event_data:
                    info_msg_id = event_data['message_id_info']
                    main_msg_id = event_data['message_id_main']
                    sub_msg_id = event_data['message_id_sub']
                    view = EventView(event_data['id'], event_data, info_msg_id, main_msg_id, sub_msg_id)
                    # Восстанавливаем view на сообщении с запасным составом
                    try:
                        sub_msg = await channel.fetch_message(sub_msg_id)
                        await sub_msg.edit(view=view)
                    except:
                        pass

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_events(self, ctx):
        channel = self.bot.get_channel(EVENTS_CREATION_CHANNEL_ID)
        if not channel:
            return await ctx.send("❌ Канал для создания мероприятий не найден.")
        embed = discord.Embed(
            title="📅 Создание мероприятия",
            description="Нажмите кнопку ниже, чтобы создать новое мероприятие.",
            color=0x2F3136
        )
        view = PersistentCreateButtonView(self.bot)
        await channel.send(embed=embed, view=view)
        await ctx.send("✅ Кнопка создания мероприятий установлена.")

class PersistentCreateButtonView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="📅 Создать мероприятие", style=discord.ButtonStyle.primary, custom_id="create_event_button")
    async def create_event(self, interaction: discord.Interaction, button: Button):
        options = [
            discord.SelectOption(label="Капт", value="capt"),
            discord.SelectOption(label="MCL/ВЗЗ/ВЗМ", value="mcl"),
            discord.SelectOption(label="Другие мероприятия", value="other")
        ]
        select = discord.ui.Select(placeholder="Выберите тип мероприятия", options=options)

        async def select_callback(interaction2):
            event_type = select.values[0]
            modal = CreateEventModal(event_type)
            await interaction2.response.send_modal(modal)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Выберите тип мероприятия:", view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Events(bot))
    print("🎉 Cog Events успешно загружен")