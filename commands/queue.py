import discord
from discord import app_commands
from discord.ext import commands

from database import models
from utils.rotation_logic import ensure_in_rotation


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

    @app_commands.command(name="qotd_delete", description="[Admin] Delete a queued submission by ID")
    @app_commands.describe(submission_id="The submission ID (shown in /qotd_queue)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def qotd_delete(self, interaction: discord.Interaction, submission_id: int):
        sub = models.get_submission_by_id(submission_id)
        if not sub:
            await interaction.response.send_message("Submission not found.", ephemeral=True)
            return
        if sub["posted"]:
            await interaction.response.send_message("That submission has already been posted.", ephemeral=True)
            return

        models.delete_submission(submission_id)

        # If the user has no remaining questions, remove them from rotation
        remaining = models.get_unposted_count(sub["guild_id"], sub["user_id"])
        if remaining == 0:
            models.remove_from_rotation(sub["guild_id"], sub["user_id"])

        await interaction.response.send_message(
            f"Deleted submission #{submission_id}.", ephemeral=True
        )

    @qotd_delete.error
    async def qotd_delete_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
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
