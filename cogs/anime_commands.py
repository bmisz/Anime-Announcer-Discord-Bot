import requests
from datetime import datetime
from discord.ext import commands
from langdetect import detect
from .util_methods import format_time, determine_english_title
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
        cursor = self.bot.connection.cursor()
        # Ignore this for multi- user feature for now as !info is going to be reworked soon
        cursor.execute(
            "SELECT * FROM tracked_anime WHERE anilist_id = ?", (anime_id_int,)
        )
        row = cursor.fetchone()
        if row:
            (
                anilist_id,
                title_english,
                title_romaji,
                next_episode_airs,
                start_date,
                status,
                weekly_reminder_sent,
            ) = row
            final_message = (
                f"# **{title_english}** *{anilist_id}*\n"
                f"**Romaji Title:** {title_romaji}\n"
                f"**Status:** {status}\n"
                f"**Start date:** {start_date}\n"
                f"**Next episode airs:** {format_time(unix_epoch_time=next_episode_airs)}\n"
                f"**Weekly reminder sent?:** {"Yes" if weekly_reminder_sent == 1 else "No"}"
            )
            await ctx.send(final_message)

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

            query = """
            query ($id: Int) {
                Media (id: $id, type: ANIME) {
                    id
                    nextAiringEpisode { airingAt }
                    status
                    startDate{
                        year
                        month
                        day
                    }
                    title{
                        english
                        romaji
                    }
                    synonyms
                }
            }
            """

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

            sql = """
                INSERT OR IGNORE INTO animes 
                (id, title_english, title_romaji, next_episode_airs, start_date, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """

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
                sql,
                (
                    anime["id"],
                    english_title,
                    anime["title"]["romaji"],
                    next_ep,
                    start_date,
                    anime["status"],
                ),
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
            "SELECT t.user_id, a.title_english, a.id FROM tracked_anime t JOIN animes a ON t.anime_id = a.id WHERE t.user_id = ?",
            (user_id,),
        )
        rows = cursor.fetchall()
        if not rows:
            await ctx.send(
                "**You're not currently tracking any animes, to get started use !track *id.***"
            )
            return
        rows_as_strings = []
        for id, title in rows:
            rows_as_strings.append(f"**• {title}** *(ID: {id})*")

        rows_as_strings.insert(0, "# Tracked Animes:")
        final_string = "\n".join(rows_as_strings)

        await ctx.send(final_string)


async def setup(bot):
    await bot.add_cog(AnimeAnnouncerCommands(bot))
