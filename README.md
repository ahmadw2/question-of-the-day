# QOTD Discord Bot

A private Discord bot for managing a **Question of the Day (QOTD)** channel with an automated posting schedule and a fair rotation system for contributors.

The bot allows users to submit questions privately and automatically posts one question per day at midnight. Designed for small community servers.

---

## Features

- Slash command submissions
- Text or image questions
- Automated midnight posting
- Round-robin contributor rotation
- New contributor priority (skip-to-front rule)
- SQLite storage
- Admin override commands
- Queue preview

---

## Example QOTD Post

**March 8, 2026**

What is a soundtrack from a video game you love but dislike the game itself? 💿

*Submitted by <@user_id>*

Image submissions are split across two messages:

**Message 1**

> **March 8, 2026**
>
> *(image)*

**Message 2**

> *Submitted by <@user_id>*

---

## Commands

### `/qotd_submit`
Submit a new question. Parameters: `question_text` (optional), `image` (optional) — at least one must be provided. Responses are **ephemeral** (only visible to the submitter).

### `/qotd_queue`
Shows the next questions in the queue.

### `/qotd_next`
Admin command that manually posts the next QOTD. Useful for testing.

### `/qotd_add`
Admin override to insert a question on behalf of a user. Parameters: `question_text`, `image`, `submitter_user`.

---

## Rotation Algorithm

The bot uses a **round-robin queue of users**, not questions.

When the bot posts a question:
1. The next user in the rotation is selected
2. Their oldest unposted question is used
3. The user is moved to the end of the rotation

### New User Priority Rule

If a new contributor submits a question and is not already in the rotation, they are inserted at the **front** of the queue.

**Example:**

Current rotation: `Bob → Joe → Amy`

Pip submits a question: `Pip → Bob → Joe → Amy`

After Pip's question posts: `Bob → Joe → Amy → Pip`

This ensures new contributors are featured quickly while maintaining long-term fairness.

---

## Project Structure
```
question-of-the-day/
├── bot.py
├── config.py
├── requirements.txt
├── database/
│   ├── db.py
│   └── models.py
├── commands/
│   ├── qotd_submit.py
│   └── queue.py
├── scheduler/
│   └── daily_post.py
└── utils/
    └── rotation.py
```

---

## Database

SQLite database file: `qotd.db`

### `submissions`
| Column | Description |
|---|---|
| `id` | Primary key |
| `guild_id` | Discord server ID |
| `user_id` | Submitter ID |
| `question_text` | Text content (nullable) |
| `image_url` | Image URL (nullable) |
| `created_at` | Submission timestamp |

### `rotation_order`
| Column | Description |
|---|---|
| `guild_id` | Discord server ID |
| `user_id` | User ID |
| `position` | Position in rotation |

### `guild_settings`
| Column | Description |
|---|---|
| `guild_id` | Discord server ID |
| `qotd_channel_id` | Target channel ID |

---

## Setup

### 1. Create a Discord Bot

Create an application in the [Discord Developer Portal](https://discord.com/developers/applications) and generate a bot token.

Required permissions: Send Messages, Embed Links, Attach Files, Read Message History.

Enable: **MESSAGE CONTENT INTENT**

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file:
```
DISCORD_TOKEN=your_bot_token
```

### 4. Run the Bot
```bash
python bot.py
```

---

## Hosting

**Raspberry Pi** — great for a small always-on community bot. No monthly cost, runs 24/7, extremely low power usage.

The bot runs as a systemd service (`qotd.service`). To deploy updates:

```bash
git pull
sudo systemctl restart qotd
```

To check status or view logs:

```bash
sudo systemctl status qotd
sudo journalctl -u qotd -f
```

**Cloud (e.g. Railway)** — runs the bot continuously with minimal setup. Good if you don't want to manage hardware.

---

## Storage

The bot uses SQLite. Posted questions can optionally be deleted after posting to keep the database small. Typical storage usage stays well under a few megabytes even after years of use.

---

## Security

The bot only processes commands through Discord's gateway connection — no public API endpoints are exposed. Additional protections include guild ID restrictions and optional admin-only commands.

---

## Future Improvements

- QOTD statistics and contributor leaderboards
- Moderation queue
- Web dashboard
- Analytics

---

## License

Private project for community server use.