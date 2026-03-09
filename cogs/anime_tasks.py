from discord.ext import commands, tasks
import requests
import os
from datetime import datetime, time, timezone
import sqlite3
from .util_methods import format_time


class AnimeAnnouncerTasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = 1469512207355347143
        self.query_anilist.start()
        self.week_reminder.start()
        self.database_backup.start()

    @tasks.loop(minutes=30)
    async def query_anilist(self):
        CHANNEL = self.bot.get_channel(self.channel_id)
        if CHANNEL is None:
            CHANNEL = await self.bot.fetch_channel(self.channel_id)

        cursor = self.bot.connection.cursor()
        cursor.execute("SELECT anilist_id FROM tracked_anime")

        rows = cursor.fetchall()
        ids = [row[0] for row in rows]

        if not ids:
            print("Not tracking any anime yet, skipping any checking.")
            return

        query = """
        query ($ids: [Int]) {
            Page {
                media (id_in: $ids, type: ANIME) {
                    id
                    nextAiringEpisode { airingAt }
                    status
                    startDate {
                        year
                        month
                        day
                    }
                    title {
                        english
                        romaji
                    }
                }
            }
        }
        """

        variables = {"ids": ids}
        url = "https://graphql.anilist.co"

        response = requests.post(url, json={"query": query, "variables": variables})
        data = response.json()

        changes = await self._look_for_changes(data)

        if changes == False:
            print(f"Searched through {len(ids)} shows and found no changes.")

    async def _look_for_changes(self, anilist_data) -> bool:
        CHANNEL = self.bot.get_channel(self.channel_id)
        cursor = self.bot.connection.cursor()

        print("Looking for changes...")
        found_change = False

        for show in anilist_data["data"]["Page"]["media"]:
            anilist_english_title = show["title"]["english"]
            anilist_status = show["status"]
            anilist_next_airing_episode = (
                show["nextAiringEpisode"]["airingAt"]
                if show["nextAiringEpisode"]
                else None
            )
            startDate = show["startDate"]
            anilist_startDate = (
                f"{startDate['year']}-{startDate['month']}-{startDate['day']}"
            )

            cursor.execute(
                "SELECT status, next_episode_time, startDate, title_english FROM tracked_anime WHERE anilist_id = ?",
                (show["id"],),
            )
            row = cursor.fetchone()
            if not row:
                continue

            db_status, db_next_airing_episode, db_startDate, db_english_title = row

            if anilist_status != db_status and anilist_status == "FINISHED":
                found_change = True
                cursor.execute(
                    "DELETE FROM tracked_anime WHERE anilist_id = ?", (show["id"],)
                )
                print(f"Removing {show['id']} from database due to show concluding.")
                self.bot.connection.commit()
                await CHANNEL.send(
                    f"❌ **{db_english_title}** has concluded and has been removed from your tracking list. ❌"
                )
                continue

            if anilist_status == "RELEASING" and db_status == "NOT_YET_RELEASED":
                found_change = True
                cursor.execute(
                    "UPDATE tracked_anime SET status = ? WHERE anilist_id = ?",
                    (anilist_status, show["id"]),
                )
                print(
                    f"Changing database status: {db_status} -> {anilist_status}. ({show['id']})"
                )
                self.bot.connection.commit()
                db_status = "RELEASING"
                await CHANNEL.send(f"🚨 **{db_english_title}** has started airing! 🚨")

            changes_to_look_for = [
                # anilist_info, db_info, db_column name, display_name
                (
                    anilist_english_title,
                    db_english_title,
                    "title_english",
                    "english title",
                ),
                (
                    anilist_status,
                    db_status,
                    "status",
                    "status",
                ),
                (
                    anilist_next_airing_episode,
                    db_next_airing_episode,
                    "next_episode_time",
                    "next episode airing time",
                ),
                (
                    anilist_startDate,
                    db_startDate,
                    "startDate",
                    "start date",
                ),
            ]

            for new_val, old_val, db_column, label in changes_to_look_for:
                if new_val is not None and new_val != old_val:
                    cursor.execute(
                        f"UPDATE tracked_anime SET {db_column} = ? WHERE anilist_id = ?",
                        (new_val, show["id"]),
                    )
                    print(f"{label} changed: {old_val} --> {new_val}.")

                    if "next_episode_time" in db_column:
                        new_val = format_time(unix_epoch_time=new_val)
                        old_val = format_time(unix_epoch_time=old_val)
                    await CHANNEL.send(
                        f"⚠️ UPDATE ⚠️: **{db_english_title}**'s {label} has changed. \n**{old_val} ➡️ {new_val}**"
                    )

                    found_change = True
        if found_change:
            self.bot.connection.commit()

        return found_change

    @tasks.loop(time=time(hour=21, tzinfo=timezone.utc))
    async def week_reminder(self):
        CHANNEL = self.bot.get_channel(self.channel_id)
        if CHANNEL is None:
            CHANNEL = await self.bot.fetch_channel(self.channel_id)

        # One week in seconds
        ONE_WEEK = 60 * 60 * 24 * 7

        NOW = int(datetime.now(timezone.utc).timestamp())

        cursor = self.bot.connection.cursor()
        cursor.execute(
            "SELECT anilist_id, title_english, next_episode_time, weekly_reminder_sent FROM tracked_anime"
        )

        rows = cursor.fetchall()

        if not rows:
            print("Not tracking any anime yet, skipping checking for weekly reminder.")
            return

        for id, english_title, next_episode_time, weekly_reminder_already_sent in rows:
            weekly_reminder_already_sent = bool(weekly_reminder_already_sent)
            if weekly_reminder_already_sent == True:
                print(f"{english_title} has already had a 1 week reminder sent.")
                continue
            if next_episode_time == None:
                print(f"{english_title} has no scheduled next episode yet.")
                continue

            time_to_next_ep = next_episode_time - NOW
            if 0 < time_to_next_ep <= ONE_WEEK:
                cursor.execute(
                    "UPDATE tracked_anime SET weekly_reminder_sent = 1 WHERE anilist_id = ?",
                    (id,),
                )
                self.bot.connection.commit()
                await CHANNEL.send(
                    f"🔔 **{english_title}** is less than one week from airing it's first episode! 🔔"
                )

    @tasks.loop(hours=72)
    async def database_backup(self):
        if not os.path.exists("backups"):
            os.makedirs("backups")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backups/database_backup_{timestamp}.db"

        try:
            source = self.bot.connection
            dest = sqlite3.connect(backup_file)

            with dest:
                source.backup(dest)

            print(f"Backup successful: {backup_file}")
        except Exception as e:
            print(f"Backup failed: {e}")
        finally:
            dest.close()

    @query_anilist.before_loop
    async def before_query_anilist(self):
        print("Waiting until bot is initialized until querying AniList...")
        await self.bot.wait_until_ready()

    @week_reminder.before_loop
    async def before_week_reminder(self):
        print(
            "Waiting until bot is initialized before starting weekly reminders task..."
        )
        await self.bot.wait_until_ready()

    @database_backup.before_loop
    async def before_database_backup(self):
        print(
            "Waiting until bot is initialized before starting database backup task..."
        )
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(AnimeAnnouncerTasks(bot))
