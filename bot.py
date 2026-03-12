import discord
from discord.ext import commands

import config
from database.db import init_db

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

EXTENSIONS = [
    "commands.qotd_add",
    "commands.queue",
    "scheduler.daily_post",
]


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    # Clear guild-specific commands to remove duplicates
    guild = discord.Object(id=config.GUILD_ID)
    bot.tree.clear_commands(guild=guild)
    await bot.tree.sync(guild=guild)
    # Sync globally
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} slash commands")


async def main():
    init_db()
    async with bot:
        for ext in EXTENSIONS:
            await bot.load_extension(ext)
        await bot.start(config.BOT_TOKEN)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
