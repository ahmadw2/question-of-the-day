#!/usr/bin/env python3
"""
Bulk import questions into the QOTD database.

Supports two import modes:

1. DiscordChatExporter JSON export (recommended for importing from DMs):

    python3 import_questions.py <guild_id> --discord <json_file>

    Export your DMs using DiscordChatExporter (https://github.com/Tyrrrz/DiscordChatExporter):
      - Install: brew install --cask discordchatexporter  (or download from GitHub)
      - Export a DM as JSON: use the app GUI or CLI
      - Each message becomes a submission. Text, images, or both are preserved.
      - Messages from ALL users in the DM are imported. The submitter is the
        message author. Your own messages are skipped by default (use --include-self
        to include them).

2. CSV file (for manual entry):

    python3 import_questions.py <guild_id> --csv <csv_file>

    CSV format (no header row):
      user_id,question_text
      user_id,question_text,image_url

    Example:
      123456789012345678,What's your favorite movie?
      987654321098765432,,https://cdn.discordapp.com/attachments/.../image.png
      123456789012345678,Caption for this image,https://cdn.discordapp.com/.../pic.jpg
"""

import csv
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from database.db import init_db
from database.models import add_submission, user_in_rotation, insert_at_front
from utils.rotation_logic import ensure_in_rotation


def import_discord_json(guild_id, json_file, self_user_id=None):
    """Import from a DiscordChatExporter JSON export."""
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data.get("messages", [])
    count = 0
    skipped = 0
    users_seen = set()

    for msg in messages:
        author = msg.get("author", {})
        user_id = int(author.get("id", 0))

        # Skip bot messages
        if author.get("isBot", False):
            continue

        # Skip self unless requested
        if self_user_id and user_id == self_user_id:
            skipped += 1
            continue

        # Extract text content
        content = msg.get("content", "").strip()
        question_text = content if content else None

        # Extract image attachments
        image_url = None
        attachments = msg.get("attachments", [])
        for att in attachments:
            # Check if it's an image by content type or file extension
            content_type = att.get("contentType", "")
            filename = att.get("fileName", att.get("url", "")).lower()
            if content_type.startswith("image/") or any(filename.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
                image_url = att.get("url")
                break

        # Also check embeds for images
        if not image_url:
            for embed in msg.get("embeds", []):
                if embed.get("image"):
                    image_url = embed["image"].get("url")
                    break

        # Skip messages with no question content
        if not question_text and not image_url:
            skipped += 1
            continue

        add_submission(guild_id, user_id, question_text, image_url)
        users_seen.add(user_id)
        count += 1

        preview = question_text[:50] + "..." if question_text and len(question_text) > 50 else question_text
        label = preview or "(image)"
        print(f"  Imported: [{author.get('name', user_id)}] {label}")

    # Add users to rotation
    for uid in users_seen:
        ensure_in_rotation(guild_id, uid)

    print(f"\nDone! Imported {count} questions from {len(users_seen)} user(s). Skipped {skipped} messages.")


def import_csv(guild_id, csv_file):
    """Import from a CSV file."""
    count = 0
    users_seen = set()

    with open(csv_file, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                print(f"Skipping invalid row: {row}")
                continue

            user_id = int(row[0].strip())
            question_text = row[1].strip() or None
            image_url = row[2].strip() if len(row) > 2 and row[2].strip() else None

            if not question_text and not image_url:
                print(f"Skipping empty row for user {user_id}")
                continue

            add_submission(guild_id, user_id, question_text, image_url)
            users_seen.add(user_id)
            count += 1

            preview = question_text[:50] if question_text else "(image)"
            print(f"  Imported: [{user_id}] {preview}")

    for uid in users_seen:
        ensure_in_rotation(guild_id, uid)

    print(f"\nDone! Imported {count} questions from {len(users_seen)} user(s).")


def main():
    if len(sys.argv) < 4:
        print("Usage:")
        print("  python3 import_questions.py <guild_id> --discord <json_file> [--include-self <your_user_id>]")
        print("  python3 import_questions.py <guild_id> --csv <csv_file>")
        print()
        print("To export DMs, use DiscordChatExporter:")
        print("  https://github.com/Tyrrrz/DiscordChatExporter")
        print("  Export format: JSON")
        sys.exit(1)

    guild_id = int(sys.argv[1])
    mode = sys.argv[2]
    filepath = sys.argv[3]

    init_db()

    if mode == "--discord":
        self_user_id = None
        if "--include-self" not in sys.argv:
            # Try to find self user ID to skip
            print("Tip: Your own messages will be skipped by default.")
            print("     Use --include-self <your_user_id> to include them.")
            print()
        if "--include-self" in sys.argv:
            idx = sys.argv.index("--include-self")
            if idx + 1 < len(sys.argv):
                self_user_id = int(sys.argv[idx + 1])
                print(f"Including messages from user {self_user_id}")
            # When --include-self is provided with a user ID, we DON'T skip anyone
            self_user_id = None  # Don't skip anyone
        else:
            # Ask which user to skip
            print("Enter YOUR Discord user ID to skip your messages (or press Enter to import all):")
            user_input = input("> ").strip()
            if user_input:
                self_user_id = int(user_input)
                print(f"Skipping messages from user {self_user_id}")
            print()

        import_discord_json(guild_id, filepath, self_user_id)

    elif mode == "--csv":
        import_csv(guild_id, filepath)

    else:
        print(f"Unknown mode: {mode}")
        print("Use --discord or --csv")
        sys.exit(1)


if __name__ == "__main__":
    main()
