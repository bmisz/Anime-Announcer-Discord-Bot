import discord
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # A simple "ping" command to check if the bot is alive
    @commands.command(name="ping")
    async def ping(self, ctx):
        """Checks the bot's latency."""
        await ctx.send(f"🏓 Pong! {round(self.bot.latency * 1000)}ms")

    # A command that repeats what you say
    @commands.command(name="echo")
    async def echo(self, ctx, *, message: str):
        """Repeats your message."""
        await ctx.send(message)

    # A "meaningless" foo command that takes an argument
    @commands.command(name="foo")
    async def foo(self, ctx, bar: str = "Nothing"):
        """Just a foo command."""
        await ctx.send(f"You provided: {bar}")

# This function is required for the bot to load this file
async def setup(bot):
    await bot.add_cog(General(bot))