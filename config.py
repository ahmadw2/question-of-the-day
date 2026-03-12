import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
QOTD_CHANNEL_ID = int(os.environ["QOTD_CHANNEL_ID"])
GUILD_ID = int(os.environ["GUILD_ID"])
