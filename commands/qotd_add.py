from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from database import models
from utils.rotation_logic import ensure_in_rotation


class QOTDAdd(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="qotd_submit", description="Submit a question for QOTD")
    @app_commands.describe(
        question_text="Your question text",
        image="An image to include with the question",
    )
    async def qotd_submit(
        self,
        interaction: discord.Interaction,
        question_text: Optional[str] = None,
        image: Optional[discord.Attachment] = None,
    ):
        if not question_text and not image:
            await interaction.response.send_message(
                "You must provide either question text or an image.", ephemeral=True
            )
            return

        image_url = image.url if image else None
        guild_id = interaction.guild_id
        user_id = interaction.user.id

        models.add_submission(guild_id, user_id, question_text, image_url)
        ensure_in_rotation(guild_id, user_id)

        await interaction.response.send_message(
            "Your question has been submitted!", ephemeral=True
        )

    @app_commands.command(name="qotd_add", description="[Admin] Submit a question on behalf of a user")
    @app_commands.describe(
        submitter_user="The user to submit on behalf of",
        question_text="The question text",
        image="An image to include with the question",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def qotd_add(
        self,
        interaction: discord.Interaction,
        submitter_user: discord.Member,
        question_text: Optional[str] = None,
        image: Optional[discord.Attachment] = None,
    ):
        if not question_text and not image:
            await interaction.response.send_message(
                "You must provide either question text or an image.", ephemeral=True
            )
            return

        image_url = image.url if image else None
        guild_id = interaction.guild_id

        models.add_submission(guild_id, submitter_user.id, question_text, image_url)
        ensure_in_rotation(guild_id, submitter_user.id)

        await interaction.response.send_message(
            f"Question submitted on behalf of {submitter_user.mention}.", ephemeral=True
        )

    @app_commands.command(name="qotd_my_questions", description="View your queued questions")
    async def qotd_my_questions(self, interaction: discord.Interaction):
        subs = models.get_user_submissions(interaction.guild_id, interaction.user.id)
        # Only show unposted questions
        subs = [s for s in subs if not s["posted"]]

        if not subs:
            await interaction.response.send_message("You have no queued questions.", ephemeral=True)
            return

        lines = []
        for s in subs:
            preview = s["question_text"][:50] + "..." if s["question_text"] and len(s["question_text"]) > 50 else s["question_text"]
            if preview:
                lines.append(f"• (ID: {s['id']}) {preview}")
            else:
                lines.append(f"• (ID: {s['id']}) *(image)*")

        # Ephemeral messages have a 2000 char limit, so truncate if needed
        output = "\n".join(lines)
        if len(output) > 1900:
            output = output[:1900] + "\n..."

        await interaction.response.send_message(output, ephemeral=True)

    @qotd_add.error
    async def qotd_add_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need Manage Server permission to use this command.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(QOTDAdd(bot))
