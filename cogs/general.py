from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        await ctx.send(f"{round(self.bot.latency * 1000)}ms")

    @commands.command()
    async def checkid(self, ctx):
        user_id = ctx.author.id
        await ctx.send(f"Your Discord ID is: {user_id}")

    @commands.command()
    async def shutdown(self, ctx):
        await ctx.send("Shutting down...")
        await self.bot.close()

    @commands.command()
    async def echo(self, ctx, *, message: str):
        await ctx.send(message)


async def setup(bot):
    await bot.add_cog(General(bot))
