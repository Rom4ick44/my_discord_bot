import discord
from discord.ext import commands
import asyncio
import os
from config import TOKEN

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.message_content = True
intents.members = True
intents.guilds = True
intents.bans = True
intents.moderation = True
intents.voice_states = True
intents.messages = True
intents.guild_messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

async def load_extensions():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('__'):
            await bot.load_extension(f'cogs.{filename[:-3]}')
            print(f'Загружен cog: {filename}')

@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен!')
    print('Команды:', [cmd.name for cmd in bot.commands])

async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())