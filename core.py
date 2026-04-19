import sqlite3
import discord
import os
from discord.ext import commands


class AnimeAnnouncerBot(commands.Bot):
    def __init__(self):

        intents = discord.Intents.default()
        intents.message_content = True

        self.connection = sqlite3.connect("anime_bot.db")
        self.connection.execute("PRAGMA foreign_keys = ON;")
        self.cursor = self.connection.cursor()

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self):
        """This runs before the bot connects to Discord."""
        # Cogs load here
        for filename in os.listdir("./cogs"):
            if filename == "util_methods.py":
                print("Skipping utils file in cogs init.")
                continue
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
                extensionLocation = filename.index(".")
                cog_name = filename[:extensionLocation]
                print(f"Successfully loaded {cog_name} cog.")
        self.cursor.executescript(
            # CREATE TABLE IF NOT EXISTS users {    This table is Unnecessary at the moment.
            #     user_id INTEGER PRIMARY KEY,
            #     name TEXT
            # }
            """
            CREATE TABLE IF NOT EXISTS animes (
                id INTEGER PRIMARY KEY,
                title_english TEXT,
                title_romaji TEXT,
                next_episode_airs INTEGER,
                start_date TEXT,
                status TEXT
            );
            CREATE TABLE IF NOT EXISTS tracked_anime (
                anime_id INTEGER,
                user_id INTEGER,
                anime_nickname TEXT,
                weekly_reminders_toggled INTEGER DEFAULT 0 CHECK (weekly_reminders_toggled IN (0, 1)),
                PRIMARY KEY (user_id, anime_id),
                FOREIGN KEY (anime_id) REFERENCES animes(id)
            );
        """
        )

    async def on_ready(self):
        if self.user:
            print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------------------")
