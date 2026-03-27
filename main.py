import os
from dotenv import load_dotenv
from core import AnimeAnnouncerBot

load_dotenv()

if __name__ == "__main__":
    bot = AnimeAnnouncerBot()
    token = os.getenv("DISCORD_TOKEN")
    if token is None:
        raise TypeError("DISCORD_TOKEN environment variable is not set")
    bot.run(token)
