import io
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from database import models
from utils.rotation_logic import ensure_in_rotation
import config


class QOTDQueue(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="qotd_queue", description="[Admin] Show the next 10 queued QOTD submissions")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def qotd_queue(self, interaction: discord.Interaction):
        queue = models.get_queue_preview(interaction.guild_id, limit=10)

        if not queue:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return

        lines = []
        for i, entry in enumerate(queue, 1):
            user_mention = f"<@{entry['user_id']}>"
            preview = entry["question_text"][:60] + "..." if entry["question_text"] and len(entry["question_text"]) > 60 else entry["question_text"]
            if preview:
                lines.append(f"**{i}.** (ID: {entry['id']}) {user_mention} — {preview}")
            else:
                lines.append(f"**{i}.** (ID: {entry['id']}) {user_mention} — *(image)*")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @qotd_queue.error
    async def qotd_queue_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need Manage Server permission to use this command.", ephemeral=True
            )

    @app_commands.command(name="qotd_stats", description="Show top QOTD contributors")
    async def qotd_stats(self, interaction: discord.Interaction):
        stats = models.get_top_contributors(interaction.guild_id, limit=10)

        if not stats:
            await interaction.response.send_message("No submissions yet.", ephemeral=True)
            return

        lines = []
        for i, entry in enumerate(stats, 1):
            user_mention = f"<@{entry['user_id']}>"
            lines.append(
                f"**{i}.** {user_mention} — {entry['total']} submitted, {entry['posted_count']} posted"
            )

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="qotd_delete", description="Delete a queued submission by ID")
    @app_commands.describe(submission_id="The submission ID (shown in /qotd_my_questions or /qotd_queue)")
    async def qotd_delete(self, interaction: discord.Interaction, submission_id: int):
        sub = models.get_submission_by_id(submission_id)
        if not sub:
            await interaction.response.send_message("Submission not found.", ephemeral=True)
            return
        if sub["posted"]:
            await interaction.response.send_message("That submission has already been posted.", ephemeral=True)
            return

        is_admin = interaction.user.guild_permissions.manage_guild
        is_owner = sub["user_id"] == interaction.user.id

        if not is_owner and not is_admin:
            await interaction.response.send_message("You can only delete your own submissions.", ephemeral=True)
            return

        models.delete_submission(submission_id)

        remaining = models.get_unposted_count(sub["guild_id"], sub["user_id"])
        if remaining == 0:
            models.remove_from_rotation(sub["guild_id"], sub["user_id"])

        await interaction.response.send_message(
            f"Deleted submission #{submission_id}.", ephemeral=True
        )

    @app_commands.command(name="qotd_edit", description="Edit a queued submission by ID")
    @app_commands.describe(
        submission_id="The submission ID (shown in /qotd_my_questions or /qotd_queue)",
        question_text="New question text",
        image="New image to attach",
    )
    async def qotd_edit(
        self,
        interaction: discord.Interaction,
        submission_id: int,
        question_text: Optional[str] = None,
        image: Optional[discord.Attachment] = None,
    ):
        if not question_text and not image:
            await interaction.response.send_message(
                "You must provide new question text, a new image, or both.", ephemeral=True
            )
            return

        sub = models.get_submission_by_id(submission_id)
        if not sub:
            await interaction.response.send_message("Submission not found.", ephemeral=True)
            return
        if sub["posted"]:
            await interaction.response.send_message("That submission has already been posted.", ephemeral=True)
            return

        is_admin = interaction.user.guild_permissions.manage_guild
        is_owner = sub["user_id"] == interaction.user.id

        if not is_owner and not is_admin:
            await interaction.response.send_message("You can only edit your own submissions.", ephemeral=True)
            return

        image_url = image.url if image else None
        models.update_submission(submission_id, question_text=question_text, image_url=image_url)

        await interaction.response.send_message(
            f"Updated submission #{submission_id}.", ephemeral=True
        )

    @app_commands.command(name="qotd_preview", description="[Admin] Preview a queued submission")
    @app_commands.describe(submission_id="The submission ID to preview (defaults to next in queue)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def qotd_preview(self, interaction: discord.Interaction, submission_id: Optional[int] = None):
        if not config.ADMIN_CHANNEL_ID:
            await interaction.response.send_message(
                "ADMIN_CHANNEL_ID is not configured in the environment.", ephemeral=True
            )
            return

        admin_channel = self.bot.get_channel(config.ADMIN_CHANNEL_ID)
        if not admin_channel:
            await interaction.response.send_message(
                "Could not find the admin channel.", ephemeral=True
            )
            return

        if submission_id is not None:
            sub = models.get_submission_by_id(submission_id)
            if not sub or sub["posted"]:
                await interaction.response.send_message(
                    "Submission not found or already posted.", ephemeral=True
                )
                return
        else:
            queue = models.get_queue_preview(interaction.guild_id, limit=1)
            if not queue:
                await interaction.response.send_message("The queue is empty.", ephemeral=True)
                return
            sub = models.get_submission_by_id(queue[0]["id"])

        has_image = bool(sub["image_url"])
        has_text = bool(sub["question_text"])

        header = f"**[PREVIEW]** Submission #{sub['id']} by <@{sub['user_id']}>"

        if has_image:
            image_bytes = None
            try:
                async with self.bot.http._HTTPClient__session.get(sub["image_url"]) as resp:
                    if resp.status == 200:
                        image_bytes = await resp.read()
            except Exception:
                pass

            content = header
            if has_text:
                content += f"\n\n{sub['question_text']}"

            if image_bytes:
                filename = sub["image_url"].split("/")[-1].split("?")[0]
                file = discord.File(io.BytesIO(image_bytes), filename=filename)
                await admin_channel.send(content, file=file)
            else:
                await admin_channel.send(f"{content}\n{sub['image_url']}")
        else:
            await admin_channel.send(f"{header}\n\n{sub['question_text']}")

        await interaction.response.send_message(
            f"Preview of submission #{sub['id']} sent to the admin channel.", ephemeral=True
        )

    @qotd_preview.error
    async def qotd_preview_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need Manage Server permission to use this command.", ephemeral=True
            )

    @app_commands.command(name="qotd_priority", description="[Admin] Push a submission to post next")
    @app_commands.describe(submission_id="The submission ID (shown in /qotd_queue)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def qotd_priority(self, interaction: discord.Interaction, submission_id: int):
        success = models.prioritize_submission(interaction.guild_id, submission_id)
        if success:
            await interaction.response.send_message(
                f"Submission #{submission_id} will be posted next.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Submission not found or already posted.", ephemeral=True
            )

    @qotd_priority.error
    async def qotd_priority_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need Manage Server permission to use this command.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(QOTDQueue(bot))
