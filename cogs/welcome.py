import discord
from discord.ext import commands
from datetime import datetime
from config import WELCOME_CHANNEL_ID, LOG_CHANNEL_ID, REQUEST_CHANNEL_ID

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✅ Cog Welcome инициализирован")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        print(f"👤 Событие on_member_join для {member}")

        welcome_channel = self.bot.get_channel(WELCOME_CHANNEL_ID)
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)

        if not welcome_channel or not log_channel:
            print("❌ Каналы не найдены, проверьте ID")
            return

        guild = member.guild
        request_link = f"https://discord.com/channels/{guild.id}/{REQUEST_CHANNEL_ID}"
        results_link = f"https://discord.com/channels/{guild.id}/{RESULTS_CHANNEL_ID}"

        await welcome_channel.send(f"{member.mention}")

        welcome_embed = discord.Embed(
            title=f"**{member.display_name}** присоединился к серверу!",
            description=(
                f"Подать заявку в семью можно в канале: [Заявка]({request_link})\n"
                f"Информация об итогах заявки находится здесь: [Итоги заявок]({results_link})"
            ),
            color=0x000000
        )
        banner_url = "https://cdn.discordapp.com/attachments/.../banner.png"  # замените
        welcome_embed.set_image(url=banner_url)
        welcome_embed.set_footer(text=f"Всего участников: {guild.member_count}")

        await welcome_channel.send(embed=welcome_embed)

        log_embed = discord.Embed(
            title="🆕 Новый участник",
            description=f"Пользователь {member.mention} присоединился к серверу.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        log_embed.set_thumbnail(url=member.display_avatar.url)
        log_embed.add_field(name="Имя", value=str(member), inline=True)
        log_embed.add_field(name="ID", value=member.id, inline=True)
        log_embed.add_field(name="Аккаунт создан", value=discord.utils.format_dt(member.created_at, style='F'), inline=True)
        log_embed.add_field(name="Присоединился к серверу", value=discord.utils.format_dt(member.joined_at, style='F'), inline=True)
        log_embed.set_footer(text=f"ID: {member.id}")

        await log_channel.send(embed=log_embed)
        print("✅ Приветствие отправлено")

    @commands.command()
    async def testjoin(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author
        await self.on_member_join(member)
        await ctx.send("✅ Тестовое приветствие отправлено (проверь каналы).", delete_after=5)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
    print("🎉 Cog Welcome успешно загружен")