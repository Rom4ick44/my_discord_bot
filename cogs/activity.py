import discord
from discord.ext import commands, tasks
import asyncio
import datetime
import database as db
from config import ACTIVITY_CHECK_DAYS, ACTIVITY_CHECK_HOUR, CURATOR_ROLE_ID

class Activity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.start_after_delay())
        print("✅ Система проверки активности инициализирована")

    async def start_after_delay(self):
        await self.bot.wait_until_ready()
        # Ждём 1 час перед первым запуском (чтобы не проверять сразу после перезапуска)
        await asyncio.sleep(3600)
        self.check_activity.start()

    def cog_unload(self):
        self.check_activity.cancel()

    @tasks.loop(hours=ACTIVITY_CHECK_HOUR)
    async def check_activity(self):
        await self.bot.wait_until_ready()
        now = datetime.datetime.now()
        print(f"[{now}] Запуск проверки активности...")
        portfolios = db.get_all_portfolios()
        for channel_id, owner_id, rank, tier, pinned_by, thread_rp_id, thread_gang_id, created_at in portfolios:
            # Проверяем только портфели ранга Academy
            if rank != 'Academy':
                continue

            # Пропускаем портфели младше 4 дней
            created = datetime.datetime.fromisoformat(created_at)
            if (now - created).days < 4:
                continue

            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue
            thread_rp = channel.get_thread(thread_rp_id)
            thread_gang = channel.get_thread(thread_gang_id)

            if thread_rp:
                await self._check_thread_activity(thread_rp, owner_id, pinned_by, "РП мероприятия")
            if thread_gang:
                await self._check_thread_activity(thread_gang, owner_id, pinned_by, "Гангейм и Капты")

            await asyncio.sleep(1)

    async def _check_thread_activity(self, thread, owner_id, pinned_by, thread_name):
        after = datetime.datetime.now() - datetime.timedelta(days=ACTIVITY_CHECK_DAYS)
        messages = []
        async for msg in thread.history(after=after, limit=100):
            if not msg.author.bot:
                messages.append(msg)
                break

        if not messages:
            await self._send_inactivity_warning(thread, owner_id, pinned_by, thread_name)

    async def _send_inactivity_warning(self, thread, owner_id, pinned_by, thread_name):
        # Уведомление в ЛС куратору (или всей роли)
        if pinned_by:
            curator = thread.guild.get_member(pinned_by)
            if curator:
                try:
                    await curator.send(
                        f"⚠️ Пользователь <@{owner_id}> неактивен в своём портфеле (ветка {thread_name}) за последние {ACTIVITY_CHECK_DAYS} дней."
                    )
                except:
                    pass
        else:
            curator_role = thread.guild.get_role(CURATOR_ROLE_ID)
            if curator_role:
                for member in curator_role.members:
                    try:
                        await member.send(
                            f"⚠️ Пользователь <@{owner_id}> неактивен в своём портфеле (ветка {thread_name}) за последние {ACTIVITY_CHECK_DAYS} дней."
                        )
                    except:
                        pass

    @check_activity.before_loop
    async def before_check_activity(self):
        await self.bot.wait_until_ready()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def check_activity_now(self, ctx):
        """Принудительная проверка активности (для теста)."""
        await ctx.send("🔄 Запускаю проверку активности...")
        await self.check_activity()
        await ctx.send("✅ Проверка завершена.")

async def setup(bot):
    await bot.add_cog(Activity(bot))
    print("🎉 Cog Activity успешно загружен")