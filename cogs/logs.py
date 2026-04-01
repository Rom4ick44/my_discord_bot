import discord
from discord.ext import commands
from datetime import datetime, timedelta
import database as db
from config import LOGGING_CHANNEL_ID

class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = LOGGING_CHANNEL_ID
        print("✅ Cog Logs загружен")

    async def send_log(self, guild, embed):
        """Отправляет embed в канал логов и записывает в БД."""
        # Запись в БД
        action_type = embed.title.split()[0] if embed.title else "unknown"
        user_id = None
        for field in embed.fields:
            if field.name == "Пользователь":
                # Поле может содержать упоминание, извлекаем ID
                import re
                match = re.search(r'<@!?(\d+)>', field.value)
                if match:
                    user_id = int(match.group(1))
                break
        db.add_log(guild.id, user_id, action_type, embed.description or str(embed.to_dict()))

        # Отправка в канал
        channel = guild.get_channel(self.log_channel_id)
        if channel:
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = discord.Embed(
            title="📥 Участник зашёл",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Пользователь", value=member.mention)
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Аккаунт создан", value=discord.utils.format_dt(member.created_at, style='R'))
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = discord.Embed(
            title="📤 Участник вышел",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Пользователь", value=member.mention)
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Причина", value="Покинул сервер")
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        changes = []
        if before.nick != after.nick:
            changes.append(f"Ник: {before.nick} → {after.nick}")
        if before.roles != after.roles:
            added = [r.mention for r in after.roles if r not in before.roles]
            removed = [r.mention for r in before.roles if r not in after.roles]
            if added:
                changes.append(f"Добавлены роли: {', '.join(added)}")
            if removed:
                changes.append(f"Удалены роли: {', '.join(removed)}")
        if not changes:
            return
        embed = discord.Embed(
            title="🔄 Обновление участника",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=after.display_avatar.url)
        embed.add_field(name="Пользователь", value=after.mention)
        embed.add_field(name="Изменения", value="\n".join(changes), inline=False)
        await self.send_log(after.guild, embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel:
            return
        embed = discord.Embed(
            title="🔊 Голосовое состояние",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Пользователь", value=member.mention)
        if before.channel is None and after.channel is not None:
            embed.description = f"Подключился к {after.channel.mention}"
        elif before.channel is not None and after.channel is None:
            embed.description = f"Отключился от {before.channel.mention}"
        elif before.channel != after.channel:
            embed.description = f"Переместился из {before.channel.mention} в {after.channel.mention}"
        await self.send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot:
            return
        if before.content == after.content:
            return
        embed = discord.Embed(
            title="✏️ Редактирование сообщения",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Автор", value=before.author.mention)
        embed.add_field(name="Канал", value=before.channel.mention)
        embed.add_field(name="Было", value=before.content[:1024] or "[пусто]")
        embed.add_field(name="Стало", value=after.content[:1024] or "[пусто]")
        embed.add_field(name="Ссылка", value=f"[Перейти]({after.jump_url})", inline=False)
        await self.send_log(before.guild, embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return
        embed = discord.Embed(
            title="🗑️ Удаление сообщения",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Автор", value=message.author.mention)
        embed.add_field(name="Канал", value=message.channel.mention)
        embed.add_field(name="Содержание", value=message.content[:1024] or "[пусто]")
        embed.add_field(name="Ссылка", value=message.jump_url, inline=False)
        await self.send_log(message.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(
            title="📁 Создание канала",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Название", value=channel.mention)
        embed.add_field(name="Тип", value=str(channel.type))
        embed.add_field(name="Категория", value=channel.category.name if channel.category else "Нет")
        await self.send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(
            title="🗑️ Удаление канала",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Название", value=channel.name)
        embed.add_field(name="Тип", value=str(channel.type))
        embed.add_field(name="Категория", value=channel.category.name if channel.category else "Нет")
        await self.send_log(channel.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        embed = discord.Embed(
            title="✨ Создание роли",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Название", value=role.mention)
        embed.add_field(name="Цвет", value=str(role.color))
        embed.add_field(name="Позиция", value=role.position)
        await self.send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        embed = discord.Embed(
            title="❌ Удаление роли",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Название", value=role.name)
        embed.add_field(name="Цвет", value=str(role.color))
        await self.send_log(role.guild, embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(f"Имя: {before.name} → {after.name}")
        if before.color != after.color:
            changes.append(f"Цвет: {before.color} → {after.color}")
        if before.position != after.position:
            changes.append(f"Позиция: {before.position} → {after.position}")
        if not changes:
            return
        embed = discord.Embed(
            title="📝 Изменение роли",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Роль", value=after.mention)
        embed.add_field(name="Изменения", value="\n".join(changes), inline=False)
        await self.send_log(after.guild, embed)

    # ---------- Поиск по логам ----------
    @commands.group(name="logs", invoke_without_command=True)
    async def logs_group(self, ctx):
        """Поиск по логам. Используйте !logs search [параметры]"""
        await ctx.send_help(ctx.command)

    @logs_group.command(name="search")
    async def search_logs(self, ctx, user: discord.Member = None, action: str = None, days: int = 7, limit: int = 20):
        """Поиск логов. Примеры:
        !logs search @User action:join days:3 limit:10
        !logs search action:voice
        """
        # Парсим дополнительные параметры (можно передавать в любом порядке)
        # Для простоты будем использовать именованные аргументы через ключи
        # Реализуем простой парсинг строки команды
        args = ctx.message.content.split()[2:]  # пропускаем !logs search
        user_id = user.id if user else None
        action_type = None
        start_date = None
        end_date = None
        for arg in args:
            if arg.startswith("action:"):
                action_type = arg.split(":")[1]
            elif arg.startswith("days:"):
                days = int(arg.split(":")[1])
            elif arg.startswith("limit:"):
                limit = int(arg.split(":")[1])
        if days:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()

        logs = db.search_logs(ctx.guild.id, user_id, action_type, start_date, None, limit)
        if not logs:
            await ctx.send("📭 Логов не найдено.")
            return

        embed = discord.Embed(title="📜 Результаты поиска", color=discord.Color.blue())
        for log in logs:
            log_id, log_user_id, log_action, details, timestamp = log
            user = ctx.guild.get_member(log_user_id) or f"<@{log_user_id}>"
            dt = datetime.fromisoformat(timestamp).strftime("%d.%m.%Y %H:%M:%S")
            embed.add_field(
                name=f"{log_action} - {dt}",
                value=f"**Пользователь:** {user}\n**Детали:** {details[:200]}",
                inline=False
            )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Logs(bot))
    print("🎉 Cog Logs успешно загружен")