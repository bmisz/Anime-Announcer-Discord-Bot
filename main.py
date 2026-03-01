import discord
import os
import sqlite3
from discord.ext import commands
from dotenv import load_dotenv

# Load your token from the .env file
load_dotenv()

class MyAnimeBot(commands.Bot):
    def __init__(self):

        intents = discord.Intents.default()
        intents.message_content = True 
        
        self.connection = sqlite3.connect('anime_bot.db')
        self.cursor = self.connection.cursor()
        

        super().__init__(
            command_prefix="!", 
            intents=intents,
        )

    async def setup_hook(self):
        """This runs before the bot connects to Discord."""
        # This is where you load your Cogs (the other .py files)
        for filename in os.listdir('./cogs'):
            if filename == 'util_methods.py':
                print("Skipping utils file in cogs init.")
                continue
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                extensionLocation = filename.index('.')
                cogName = filename[:extensionLocation]
                print(f'Successfully loaded {cogName} cog.')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracked_anime (
                anilist_id INTEGER PRIMARY KEY,
                title_english TEXT,
                title_romaji TEXT,
                next_episode_time INTEGER,
                startDate TEXT,
                status TEXT
            )
        ''')

    async def on_ready(self):
        """This runs when the bot is officially online."""
        if self.user:
            print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

# Create the instance and run it
if __name__ == "__main__":
    bot = MyAnimeBot()
    token = os.getenv('DISCORD_TOKEN')
    if token is None:
        raise ValueError("DISCORD_TOKEN environment variable is not set")
    bot.run(token)