import os
from dotenv import load_dotenv
from core import AnimeAnnouncerBot

load_dotenv()

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    channel_id = os.getenv("ANNOUNCEMENT_CHANNEL_ID")
    if token is None:
        raise TypeError("DISCORD_TOKEN environment variable is not set. Check your .env")
    if channel_id is None:
        raise TypeError("ANNOUNCEMENT_CHANNEL_ID environment variable is not set. Check your .env")
    bot = AnimeAnnouncerBot()
    bot.run(token)
