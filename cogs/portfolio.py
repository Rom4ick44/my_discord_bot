import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
import traceback
import asyncio
import database as db
from config import (
    ACADEMY_ROLE_ID, REED_ROLE_ID, MAIN_ROLE_ID, HIGH_ROLE_ID,
    ACADEMY_CATEGORY_ID, REED_CATEGORY_ID, MAIN_CATEGORY_ID, HIGH_CATEGORY_ID,
    PORTFOLIO_CREATION_CHANNEL_ID, PORTFOLIO_ACCESS_ROLES,
    CURATOR_ROLE_ID, GREEN_REQUESTS_CHANNEL_ID, GREEN_LOG_CHANNEL_ID
)

RANK_TO_CATEGORY = {
    'Academy': ACADEMY_CATEGORY_ID,
    'Reed': REED_CATEGORY_ID,
    'Main': MAIN_CATEGORY_ID,
    'High': HIGH_CATEGORY_ID
}

RANK_TO_ROLE = {
    'Academy': ACADEMY_ROLE_ID,
    'Reed': REED_ROLE_ID,
    'Main': MAIN_ROLE_ID,
    'High': HIGH_ROLE_ID
}

def get_user_rank(member):
    if HIGH_ROLE_ID in [r.id for r in member.roles]:
        return 'High'
    if MAIN_ROLE_ID in [r.id for r in member.roles]:
        return 'Main'
    if REED_ROLE_ID in [r.id for r in member.roles]:
        return 'Reed'
    if ACADEMY_ROLE_ID in [r.id for r in member.roles]:
        return 'Academy'
    return None

def has_access(user):
    user_roles = [r.id for r in user.roles]
    return any(role in user_roles for role in PORTFOLIO_ACCESS_ROLES)

async def refresh_portfolio_embed(channel):
    portfolio = db.get_portfolio_by_channel(channel.id)
    if not portfolio:
        return
    owner_id, rank, tier, pinned_by, _, _ = portfolio
    owner = channel.guild.get_member(owner_id)
    if not owner:
        return

    embed = discord.Embed(
        title="📁 Личный канал участника",
        description=(
            "- Присылайте в текстовый канал видео откатов с МП (желательно геймплей от 10 минут с сильными лобби).\n"
            "- Изучайте залазы, это важно для участия в мейн-составе на каптах.\n"
            "- Пожалуйста, прикрепляйте откаты с лучшей стрельбой и демонстрацией понимания игры."
        ),
        color=0x2F3136
    )
    embed.set_author(name=owner.display_name, icon_url=owner.display_avatar.url)
    embed.add_field(name="Текущий Ранг", value=rank if rank else "Нет ранга", inline=True)
    embed.add_field(name="Текущий Тир", value=str(tier) if tier else "Нет тира", inline=True)
    pinned_user = channel.guild.get_member(pinned_by) if pinned_by else None
    embed.add_field(name="Закреплён", value=pinned_user.mention if pinned_user else "Никто", inline=True)
    embed.set_footer(text=f"Владелец: {owner}")

    async for message in channel.history(limit=10):
        if message.author == channel.guild.me and message.embeds:
            await message.edit(embed=embed)
            return
    await channel.send(embed=embed)

# ---------- Селект для действий (ранг, тир) ----------
class PortfolioActionSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Удалить канал", value="delete", description="Удалить этот портфель", emoji="🗑️"),
            discord.SelectOption(label="Повысить ранг", value="rank_up", description="Повысить ранг владельца", emoji="⬆️"),
            discord.SelectOption(label="Понизить ранг", value="rank_down", description="Понизить ранг владельца", emoji="⬇️"),
            discord.SelectOption(label="Закрепиться", value="pin", description="Закрепиться за портфелем", emoji="📌"),
            discord.SelectOption(label="Открепиться", value="unpin", description="Открепиться от портфеля", emoji="🔓"),
        ]
        # !!! ВАЖНО: timeout=None делает селект persistent
        super().__init__(placeholder="Выберите действие...", min_values=1, max_values=1, options=options, custom_id="portfolio_action")

    async def callback(self, interaction: discord.Interaction):
        # ... (весь код остается без изменений) ...
        try:
            if not has_access(interaction.user):
                return await interaction.response.send_message("❌ У вас нет прав для управления портфелями.", ephemeral=True)

            action = self.values[0]
            channel = interaction.channel
            portfolio = db.get_portfolio_by_channel(channel.id)
            if not portfolio:
                return await interaction.response.send_message("❌ Портфель не найден в БД.", ephemeral=True)

            owner_id, current_rank, current_tier, pinned_by, _, _ = portfolio
            owner = interaction.guild.get_member(owner_id)

            if action == "delete":
                await interaction.response.send_message("✅ Канал будет удалён.", ephemeral=True)
                await channel.delete(reason="Портфель удалён")
                db.delete_portfolio(channel.id)
                return

            await interaction.response.send_message("✅ Действие выполняется...", ephemeral=True)

            async def background():
                try:
                    if action == "rank_up":
                        if not owner:
                            return
                        if current_rank == 'High':
                            return
                        rank_order = ['Academy', 'Reed', 'Main', 'High']
                        next_rank = rank_order[rank_order.index(current_rank) + 1]
                        await owner.remove_roles(interaction.guild.get_role(RANK_TO_ROLE[current_rank]))
                        await owner.add_roles(interaction.guild.get_role(RANK_TO_ROLE[next_rank]))
                        new_category = interaction.guild.get_channel(RANK_TO_CATEGORY[next_rank])
                        await channel.edit(category=new_category)
                        db.update_portfolio_rank(channel.id, next_rank)
                        await refresh_portfolio_embed(channel)

                    elif action == "rank_down":
                        if not owner:
                            return
                        if current_rank == 'Academy':
                            return
                        rank_order = ['Academy', 'Reed', 'Main', 'High']
                        prev_rank = rank_order[rank_order.index(current_rank) - 1]
                        await owner.remove_roles(interaction.guild.get_role(RANK_TO_ROLE[current_rank]))
                        await owner.add_roles(interaction.guild.get_role(RANK_TO_ROLE[prev_rank]))
                        new_category = interaction.guild.get_channel(RANK_TO_CATEGORY[prev_rank])
                        await channel.edit(category=new_category)
                        db.update_portfolio_rank(channel.id, prev_rank)
                        await refresh_portfolio_embed(channel)

                    elif action == "pin":
                        db.update_portfolio_pinned(channel.id, interaction.user.id)
                        await refresh_portfolio_embed(channel)

                    elif action == "unpin":
                        db.update_portfolio_pinned(channel.id, None)
                        await refresh_portfolio_embed(channel)
                except Exception as e:
                    print(f"Ошибка в фоне PortfolioActionSelect: {e}")
                    traceback.print_exc()

            asyncio.create_task(background())

        except Exception as e:
            print(f"Ошибка в PortfolioActionSelect: {e}")
            traceback.print_exc()
            await interaction.response.send_message("❌ Внутренняя ошибка.", ephemeral=True)


class PortfolioTierSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Тир 1", value="1", description="Установить тир 1"),
            discord.SelectOption(label="Тир 2", value="2", description="Установить тир 2"),
            discord.SelectOption(label="Тир 3", value="3", description="Установить тир 3"),
        ]
        # !!! ВАЖНО: timeout=None делает селект persistent
        super().__init__(placeholder="Выберите тир...", min_values=1, max_values=1, options=options, custom_id="portfolio_tier")

    async def callback(self, interaction: discord.Interaction):
        # ... (весь код остается без изменений) ...
        try:
            if not has_access(interaction.user):
                return await interaction.response.send_message("❌ У вас нет прав для управления портфелями.", ephemeral=True)

            tier = int(self.values[0])
            channel = interaction.channel

            await interaction.response.send_message(f"✅ Устанавливается тир {tier}...", ephemeral=True)

            async def background():
                db.update_portfolio_tier(channel.id, tier)
                await refresh_portfolio_embed(channel)

            asyncio.create_task(background())

        except Exception as e:
            print(f"Ошибка в PortfolioTierSelect: {e}")
            traceback.print_exc()
            await interaction.response.send_message("❌ Внутренняя ошибка.", ephemeral=True)


# ---------- Модальные окна для запросов (без изменений) ----------
class PromotionRequestModal(Modal, title="Запрос повышения"):
    # ... (весь код оставляем как есть) ...
    def __init__(self, channel_id):
        super().__init__()
        self.channel_id = channel_id
        self.add_item(TextInput(
            label="Причина повышения",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500,
            placeholder="Опишите, почему вы хотите повыситься..."
        ))

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.children[0].value

        portfolio = db.get_portfolio_by_channel(self.channel_id)
        if not portfolio:
            return await interaction.response.send_message("❌ Ошибка: портфель не найден.", ephemeral=True)

        pinned_by = portfolio[3]
        curator = interaction.guild.get_member(pinned_by) if pinned_by else None

        if curator:
            try:
                embed = discord.Embed(
                    title="📈 Запрос повышения",
                    description=f"Пользователь {interaction.user.mention} ({interaction.user}) хочет повыситься.",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Причина", value=reason, inline=False)
                embed.add_field(name="Портфель", value=interaction.channel.mention)
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                await curator.send(embed=embed)
            except:
                curator_role = interaction.guild.get_role(CURATOR_ROLE_ID)
                if curator_role:
                    for member in curator_role.members:
                        try:
                            await member.send(embed=embed)
                        except:
                            pass
        else:
            curator_role = interaction.guild.get_role(CURATOR_ROLE_ID)
            if curator_role:
                embed = discord.Embed(
                    title="📈 Запрос повышения",
                    description=f"Пользователь {interaction.user.mention} ({interaction.user}) хочет повыситься.",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Причина", value=reason, inline=False)
                embed.add_field(name="Портфель", value=interaction.channel.mention)
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                for member in curator_role.members:
                    try:
                        await member.send(embed=embed)
                    except:
                        pass

        await interaction.response.send_message("✅ Запрос отправлен куратору.", ephemeral=True)


class VodRequestModal(Modal, title="Запрос разбора отката"):
    def __init__(self, channel_id):
        super().__init__()
        self.channel_id = channel_id
        self.add_item(TextInput(
            label="Ссылка на видео",
            required=True,
            placeholder="https://youtu.be/..."
        ))
        self.add_item(TextInput(
            label="Дополнительная информация",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500,
            placeholder="Что хотите улучшить? Какие моменты разобрать?"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        # ... (весь код оставляем как есть) ...
        link = self.children[0].value
        description = self.children[1].value or "—"

        portfolio = db.get_portfolio_by_channel(self.channel_id)
        if not portfolio:
            return await interaction.response.send_message("❌ Ошибка: портфель не найден.", ephemeral=True)

        pinned_by = portfolio[3]
        curator = interaction.guild.get_member(pinned_by) if pinned_by else None

        if curator:
            try:
                embed = discord.Embed(
                    title="🎥 Запрос разбора отката",
                    description=f"Пользователь {interaction.user.mention} просит разобрать откат.",
                    color=discord.Color.purple()
                )
                embed.add_field(name="Ссылка", value=link, inline=False)
                embed.add_field(name="Комментарий", value=description, inline=False)
                embed.add_field(name="Портфель", value=interaction.channel.mention)
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                await curator.send(embed=embed)
            except:
                curator_role = interaction.guild.get_role(CURATOR_ROLE_ID)
                if curator_role:
                    for member in curator_role.members:
                        try:
                            await member.send(embed=embed)
                        except:
                            pass
        else:
            curator_role = interaction.guild.get_role(CURATOR_ROLE_ID)
            if curator_role:
                embed = discord.Embed(
                    title="🎥 Запрос разбора отката",
                    description=f"Пользователь {interaction.user.mention} просит разобрать откат.",
                    color=discord.Color.purple()
                )
                embed.add_field(name="Ссылка", value=link, inline=False)
                embed.add_field(name="Комментарий", value=description, inline=False)
                embed.add_field(name="Портфель", value=interaction.channel.mention)
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                for member in curator_role.members:
                    try:
                        await member.send(embed=embed)
                    except:
                        pass

        await interaction.response.send_message("✅ Запрос отправлен куратору.", ephemeral=True)


class GreenRequestModal(Modal, title="Запрос грина"):
    def __init__(self, channel_id):
        super().__init__()
        self.channel_id = channel_id
        self.add_item(TextInput(
            label="Сколько грина нужно?",
            required=True,
            placeholder="например: 100"
        ))
        self.add_item(TextInput(
            label="Ваш уровень закладчика (1-3)",
            required=True,
            placeholder="1, 2 или 3"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        # ... (весь код оставляем как есть) ...
        try:
            amount = int(self.children[0].value)
            level = int(self.children[1].value)
        except ValueError:
            return await interaction.response.send_message("❌ Введите числа.", ephemeral=True)

        if level not in (1, 2, 3):
            return await interaction.response.send_message("❌ Уровень закладчика должен быть 1, 2 или 3.", ephemeral=True)

        req_id = db.add_green_request(interaction.user.id, amount, level, self.channel_id)

        thread_name = "Развоз грина"
        existing_thread = None
        for thread in interaction.channel.threads:
            if thread.name == thread_name:
                existing_thread = thread
                break
        if not existing_thread:
            thread = await interaction.channel.create_thread(name=thread_name, type=discord.ChannelType.public_thread)
            thread_id = thread.id
        else:
            thread_id = existing_thread.id

        channel = interaction.guild.get_channel(GREEN_REQUESTS_CHANNEL_ID)
        if not channel:
            return await interaction.response.send_message("❌ Канал для запросов грина не настроен.", ephemeral=True)

        high_role = interaction.guild.get_role(HIGH_ROLE_ID)
        content = f"{high_role.mention} Новый запрос грина!" if high_role else None

        embed = discord.Embed(
            title="💰 Запрос грина",
            description=f"Пользователь {interaction.user.mention} запросил грин.",
            color=discord.Color.gold()
        )
        embed.add_field(name="Количество", value=amount)
        embed.add_field(name="Уровень закладчика", value=level)
        embed.add_field(name="Портфель", value=interaction.channel.mention)
        embed.add_field(name="Ветка развоза", value=f"<#{thread_id}>")
        embed.set_footer(text=f"ID запроса: {req_id}")

        view = GreenRequestView(req_id)
        msg = await channel.send(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions(roles=True))

        db.update_green_request_message(req_id, msg.id)

        await interaction.response.send_message("✅ Запрос отправлен. Ожидайте решения.", ephemeral=True)


class GreenRequestView(View):
    def __init__(self, req_id):
        super().__init__(timeout=None)
        self.req_id = req_id
        button = Button(label="💰 Грин выдан", style=discord.ButtonStyle.success, custom_id=f"green_grant_{req_id}")
        button.callback = self.grant_green
        self.add_item(button)

    async def grant_green(self, interaction: discord.Interaction):
        # ... (весь код оставляем как есть) ...
        if not has_access(interaction.user):
            return await interaction.response.send_message("❌ Недостаточно прав.", ephemeral=True)

        req_data = db.get_green_request(self.req_id)
        if not req_data:
            return await interaction.response.send_message("❌ Запрос не найден.", ephemeral=True)

        user_id, amount, level, _ = req_data

        db.update_green_request_status(self.req_id, 'granted', interaction.user.id)

        log_channel = interaction.guild.get_channel(GREEN_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="✅ Грин выдан",
                description=f"Запрос #{self.req_id} выполнен.",
                color=discord.Color.green()
            )
            embed.add_field(name="Кому", value=f"<@{user_id}>")
            embed.add_field(name="Количество", value=amount)
            embed.add_field(name="Выдал", value=interaction.user.mention)
            await log_channel.send(embed=embed)

        user = interaction.guild.get_member(user_id)
        if user:
            try:
                embed = discord.Embed(
                    title="💰 Грин получен",
                    description=f"Ваш запрос на грин (ID {self.req_id}) был одобрен.\nКоличество: {amount}",
                    color=discord.Color.green()
                )
                await user.send(embed=embed)
            except:
                pass

        await interaction.response.send_message("✅ Грин отмечен как выданный.", ephemeral=True)
        await interaction.message.delete()


# ---------- Селект для запросов ----------
class PortfolioRequestSelect(Select):
    def __init__(self, channel_id):
        options = [
            discord.SelectOption(label="📈 Запрос повышения", value="promotion"),
            discord.SelectOption(label="🎥 Разбор отката", value="vod"),
            discord.SelectOption(label="💰 Запрос грина", value="green")
        ]
        # !!! ВАЖНО: timeout=None делает селект persistent
        super().__init__(placeholder="Выберите запрос...", min_values=1, max_values=1,
                         options=options, custom_id=f"request_select_{channel_id}")

    async def callback(self, interaction: discord.Interaction):
        action = self.values[0]
        if action == "promotion":
            modal = PromotionRequestModal(interaction.channel.id)
            await interaction.response.send_modal(modal)
        elif action == "vod":
            modal = VodRequestModal(interaction.channel.id)
            await interaction.response.send_modal(modal)
        elif action == "green":
            modal = GreenRequestModal(interaction.channel.id)
            await interaction.response.send_modal(modal)


# ---------- Основной View портфеля ----------
class PortfolioView(View):
    def __init__(self, channel_id):
        # !!! ВАЖНО: timeout=None делает весь view persistent
        super().__init__(timeout=None)
        self.add_item(PortfolioActionSelect())
        self.add_item(PortfolioTierSelect())
        self.add_item(PortfolioRequestSelect(channel_id))


# ---------- Persistent View для кнопки создания портфеля ----------
class CreatePortfolioView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="📂 Создать портфель", style=discord.ButtonStyle.gray, custom_id="create_portfolio")
    async def create_button_callback(self, interaction: discord.Interaction, button: Button):
        # ... (весь код оставляем как есть) ...
        await interaction.response.defer(ephemeral=True)

        try:
            if db.get_portfolio_by_owner(interaction.user.id):
                return await interaction.followup.send("❌ У вас уже есть личный канал.", ephemeral=True)

            rank = get_user_rank(interaction.user)
            if not rank:
                return await interaction.followup.send("❌ У вас нет роли для создания портфеля.", ephemeral=True)

            category_id = RANK_TO_CATEGORY.get(rank)
            if not category_id:
                return await interaction.followup.send("❌ Категория для этого ранга не настроена.", ephemeral=True)

            category = interaction.guild.get_channel(category_id)
            if not category:
                return await interaction.followup.send("❌ Категория не найдена.", ephemeral=True)

            channel_name = f"📂-{interaction.user.name}-{interaction.user.discriminator}"
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=False)
            }
            for role_id in PORTFOLIO_ACCESS_ROLES:
                role = interaction.guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            new_channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)

            embed = discord.Embed(
                title="📁 Личный канал участника",
                description=(
                    "- Присылайте в текстовый канал видео откатов с МП (желательно геймплей от 10 минут с сильными лобби).\n"
                    "- Изучайте залазы, это важно для участия в мейн-составе на каптах.\n"
                    "- Пожалуйста, прикрепляйте откаты с лучшей стрельбой и демонстрацией понимания игры."
                ),
                color=0x2F3136
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.add_field(name="Текущий Ранг", value=rank, inline=True)
            embed.add_field(name="Текущий Тир", value="Нет тира", inline=True)
            embed.add_field(name="Закреплён", value="Никто", inline=True)
            embed.set_footer(text=f"Владелец: {interaction.user}")

            await new_channel.send(content=f"Добро пожаловать, {interaction.user.mention}!", embed=embed, view=PortfolioView(new_channel.id))

            thread_rp = await new_channel.create_thread(name="РП мероприятия", type=discord.ChannelType.public_thread)
            thread_gang = await new_channel.create_thread(name="Гангейм и Капты", type=discord.ChannelType.public_thread)

            db.create_portfolio(
                channel_id=new_channel.id,
                owner_id=interaction.user.id,
                rank=rank,
                tier=0,
                pinned_by=None,
                thread_rp_id=thread_rp.id,
                thread_gang_id=thread_gang.id
            )

            await interaction.followup.send(f"✅ Ваш личный канал создан: {new_channel.mention}", ephemeral=True)
        except Exception as e:
            print(f"Ошибка в create_portfolio: {e}")
            traceback.print_exc()
            await interaction.followup.send("❌ Внутренняя ошибка.", ephemeral=True)


# ---------- Cog ----------
class Portfolio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # !!! ВАЖНО: Регистрируем view глобально
        self.bot.add_view(CreatePortfolioView(self.bot))
        self.bot.add_view(PortfolioView(0))  # Регистрируем основной view с любым channel_id (для persistent)
        print("✅ Persistent view для портфелей и кнопки создания зарегистрированы")
        self.bot.loop.create_task(self.restore_portfolios())

    async def restore_portfolios(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(2)
        portfolios = db.get_all_portfolios()
        restored = 0
        for channel_id, owner_id, rank, tier, pinned_by, thread_rp_id, thread_gang_id in portfolios:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                db.delete_portfolio(channel_id)
                continue
            async for message in channel.history(limit=10):
                if message.author == channel.guild.me and message.embeds:
                    await message.edit(view=PortfolioView(channel_id))
                    restored += 1
                    break
        print(f"✅ Восстановлено {restored} портфелей")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        # ... (код без изменений) ...
        portfolio = db.get_portfolio_by_owner(member.id)
        if portfolio:
            channel = member.guild.get_channel(portfolio[0])
            if channel:
                await channel.delete(reason="Участник покинул сервер")
            db.delete_portfolio(portfolio[0])

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_portfolio_panel(self, ctx):
        # ... (код без изменений) ...
        channel = self.bot.get_channel(PORTFOLIO_CREATION_CHANNEL_ID)
        if not channel:
            return await ctx.send("❌ Канал для панели не найден. Проверьте PORTFOLIO_CREATION_CHANNEL_ID.")

        embed = discord.Embed(
            title="📁 Создание личного портфеля",
            description="Нажмите кнопку ниже, чтобы создать свой личный канал.",
            color=0x000000
        )

        view = CreatePortfolioView(self.bot)
        await channel.send(embed=embed, view=view)
        await ctx.send("✅ Панель создания портфелей установлена.")

async def setup(bot):
    await bot.add_cog(Portfolio(bot))
    print("🎉 Cog Portfolio успешно загружен")