import requests
from datetime import datetime
import discord
from strip_markdown import strip_markdown
from discord.ext import commands
from langdetect import detect
from .util_methods import format_time, determine_english_title, load_query
from core import AnimeAnnouncerBot


class AnimeAnnouncerCommands(commands.Cog):
    def __init__(self, bot: AnimeAnnouncerBot):
        self.bot = bot

    @commands.command(name="info")
    async def info(self, ctx, anime_id: str = ""):
        try:
            anime_id_int = int(anime_id)
        except ValueError:
            await ctx.send("This is not a valid integer ID")
            return
        if anime_id == "":
            await ctx.send("Please enter an ID you track to get info on it")
            return
        query = load_query("info.graphql")
        variables = {"id": anime_id_int}
        url = "https://graphql.anilist.co"

        response = requests.post(url, json={"query": query, "variables": variables})
        data = response.json()

        if data["data"]["Media"] is None:
            print("'data[data][Media]' returned None in info command.")
        anime = data["data"]["Media"]

        title = anime["title"]["english"]
        if title is None:
            title = determine_english_title(anime["synonyms"])
            if title is None:
                title = anime["title"]["romaji"]

        if anime["nextAiringEpisode"] is None:
            next_ep = "This anime has concluded."
        else:
            next_ep = f"Next episode is on: {format_time(unix_epoch_time=anime["nextAiringEpisode"]["airingAt"])}"

        description = strip_markdown(anime["description"])
        embed = discord.Embed(
            title=title,
            description=description,
            color=0x206694,
        )
        embed.set_image(url=anime["coverImage"]["large"])
        embed.add_field(name="Average Score", value=anime["averageScore"], inline=True)
        embed.add_field(name="Next Episode", value=next_ep, inline=True)

        await ctx.send(embed=embed)

    @commands.command(name="track")
    async def track(self, ctx: commands.Context, anime_id: str = ""):
        try:
            anime_id_int = int(anime_id)
        except ValueError:
            await ctx.send("This is not a valid integer ID")
            return
        if anime_id == "":
            await ctx.send("Please enter an ID to start tracking.")
        else:
            user_id = ctx.author.id
            query = load_query("track.graphql")

            variables = {"id": anime_id_int}
            url = "https://graphql.anilist.co"

            response = requests.post(url, json={"query": query, "variables": variables})
            data = response.json()
            anime = data["data"]["Media"]

            if anime["status"] == "FINISHED":
                await ctx.send(
                    "Show is finished and therefore has no reason to be tracked. Not added. "
                )
                return

            start_date = f"{anime["startDate"]["year"]}-{anime["startDate"]["month"]}-{anime["startDate"]["day"]}"

            next_ep = (
                anime["nextAiringEpisode"]["airingAt"]
                if anime["nextAiringEpisode"]
                else None
            )

            cursor = self.bot.connection.cursor()

            cursor.execute(
                "SELECT 1 FROM tracked_anime WHERE user_id = ? AND anime_id = ?",
                (user_id, anime_id_int),
            )
            if cursor.fetchone():
                await ctx.send("You've already started tracking this show.")
                return

            if anime["title"]["english"] is None:
                english_title = determine_english_title(anime["synonyms"])
                if english_title is None:
                    english_title = anime["title"]["romaji"]
            else:
                english_title = anime["title"]["english"]

            cursor.execute(
                """
                INSERT OR IGNORE INTO animes 
                (id, title_english, title_romaji, next_episode_airs, start_date, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    anime["id"],
                    english_title,
                    anime["title"]["romaji"],
                    next_ep,
                    start_date,
                    anime["status"],
                ),
            )
            cursor.execute(
                """
                INSERT INTO tracked_anime
                (anime_id, user_id, anime_nickname, weekly_reminders_toggled)
                VALUES (?, ?, ?, ?)
                """,
                (anime_id_int, user_id, None, 0),
            )

            self.bot.connection.commit()

            await ctx.send(f"Now tracking **{english_title} ({anime_id_int})**")

    @commands.command(name="untrack")
    async def untrack(self, ctx, anime_id: str = ""):
        try:
            anime_id_int = int(anime_id)
        except ValueError:
            await ctx.send("This is not a valid integer ID")
            return
        if anime_id == "":
            await ctx.send("Please enter an ID to stop tracking.")
            return

        user_id = ctx.author.id
        cursor = self.bot.connection.cursor()
        cursor.execute(
            "SELECT title_english FROM animes WHERE id = ?",
            (anime_id_int,),
        )
        name = cursor.fetchone()[0]

        cursor.execute(
            "DELETE FROM tracked_anime WHERE anime_id = ? AND user_id = ?",
            (anime_id_int, user_id),
        )
        self.bot.connection.commit()

        cursor.execute(
            "SELECT 1 from tracked_anime WHERE anime_id = ?", (anime_id_int,)
        )
        if not cursor.fetchone():
            # Delete from saved anime database if no ones tracking it anymore
            cursor.execute("DELETE FROM animes WHERE id = ?", (anime_id_int,))
            self.bot.connection.commit()
        await ctx.send(f"Stopped tracking **{name} ({anime_id_int})**")

    @commands.command(name="list")
    async def list(self, ctx):
        user_id = ctx.author.id
        cursor = self.bot.connection.cursor()
        cursor.execute(
            "SELECT a.title_english, a.id FROM tracked_anime t JOIN animes a ON t.anime_id = a.id WHERE t.user_id = ?",
            (user_id,),
        )
        rows = cursor.fetchall()
        if not rows:
            await ctx.send(
                "**You're not currently tracking any animes, to get started use !track *id.***"
            )
            return
        rows_as_strings = []
        for title, anime_id in rows:
            rows_as_strings.append(f"**• {title}** *(ID: {anime_id})*")

        rows_as_strings.insert(0, "# Tracked Animes:")
        final_string = "\n".join(rows_as_strings)

        await ctx.send(final_string)


async def setup(bot):
    await bot.add_cog(AnimeAnnouncerCommands(bot))
