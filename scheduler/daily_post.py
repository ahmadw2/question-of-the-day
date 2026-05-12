import io
from datetime import datetime, time
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from database import models
from utils.rotation_logic import advance_rotation
import config


async def post_qotd(bot: commands.Bot, guild_id: int) -> bool:
    """
    Post the next QOTD for a guild. Returns True if a question was posted.

    Steps:
    1. Get the user at position 0 in the rotation (next up).
    2. Fetch their oldest unposted submission.
    3. Post it to the configured channel.
    4. Mark the submission as posted.
    5. Advance the rotation (move user to back, or remove if no questions left).
    """
    rotation = models.get_rotation(guild_id)
    if not rotation:
        return False

    next_user = rotation[0]
    user_id = next_user["user_id"]

    submission = models.get_oldest_unposted(guild_id, user_id)
    if not submission:
        # User has no unposted questions; remove and try next
        models.remove_from_rotation(guild_id, user_id)
        return await post_qotd(bot, guild_id)

    channel_id = config.QOTD_CHANNEL_ID
    channel = bot.get_channel(channel_id)
    if not channel:
        return False

    today = datetime.now().strftime("%B %-d, %Y")

    has_image = bool(submission["image_url"])
    has_text = bool(submission["question_text"])

    if has_image:
        # Download image from Discord CDN and re-upload as an attachment
        image_bytes = None
        try:
            async with bot.http._HTTPClient__session.get(submission["image_url"]) as resp:
                if resp.status == 200:
                    image_bytes = await resp.read()
        except Exception:
            pass

        # Message 1: date + optional text + image
        header = f"**{today}**"
        if has_text:
            header += f"\n\n{submission['question_text']}"

        if image_bytes:
            filename = submission["image_url"].split("/")[-1].split("?")[0]
            file = discord.File(io.BytesIO(image_bytes), filename=filename)
            await channel.send(header, file=file)
        else:
            await channel.send(f"{header}\n{submission['image_url']}")

        # Message 2: attribution
        await channel.send(f"*Submitted by <@{user_id}>*")
    else:
        # Text-only submission: single message
        await channel.send(
            f"**{today}**\n\n{submission['question_text']}\n\n*Submitted by <@{user_id}>*"
        )

    models.mark_posted(submission["id"])
    advance_rotation(guild_id, user_id)
    return True


class DailyPost(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.daily_qotd.start()

    async def cog_unload(self):
        self.daily_qotd.cancel()

    @tasks.loop(time=time(hour=0, minute=0, tzinfo=ZoneInfo("America/Los_Angeles")))
    async def daily_qotd(self):
        """Post QOTD at midnight Pacific time."""
        await post_qotd(self.bot, config.GUILD_ID)

    @daily_qotd.before_loop
    async def before_daily(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="qotd_next", description="[Admin] Manually trigger the next QOTD post")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def qotd_next(self, interaction: discord.Interaction):
        posted = await post_qotd(self.bot, interaction.guild_id)
        if posted:
            await interaction.response.send_message("QOTD posted!", ephemeral=True)
        else:
            await interaction.response.send_message("No questions in the queue.", ephemeral=True)

    @qotd_next.error
    async def qotd_next_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need Manage Server permission to use this command.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(DailyPost(bot))
