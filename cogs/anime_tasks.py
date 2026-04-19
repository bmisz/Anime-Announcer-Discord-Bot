from discord.ext import commands, tasks
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, time, timezone
import sqlite3
import asyncio
from pathlib import Path
from .util_methods import format_time, filter_ids, get_mention_string, load_query

load_dotenv()


class AnimeAnnouncerTasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = os.getenv("ANNOUNCEMENT_CHANNEL_ID")
        if self.channel_id is None:
            raise TypeError("ANNOUNCEMENT_CHANNEL_ID is not set.")
        self.query_anilist.start()
        # self.week_reminder.start()
        self.database_backup.start()

    @tasks.loop(minutes=25)
    async def query_anilist(self):
        CHANNEL = self.bot.get_channel(self.channel_id)
        if CHANNEL is None:
            CHANNEL = await self.bot.fetch_channel(self.channel_id)

        cursor: sqlite3.Cursor = self.bot.connection.cursor()

        cursor.execute("SELECT anime_id, user_id FROM tracked_anime")
        # rows = [(id, uid), (id2, uid2)...]
        rows: list[tuple[int, int]] = cursor.fetchall()
        if not rows:
            print("Not tracking any anime yet, skipping any checking.")
            return

        # returns: ids = [(showid0, [uid0, uid1...]), (showid1, [uid0, uid1...])]
        ids = filter_ids(rows)

        show_ids = [show[0] for show in ids]

        query = load_query("update_checker.graphql")

        variables = {"ids": show_ids}
        url = "https://graphql.anilist.co"

        try:
            response = requests.post(url, json={"query": query, "variables": variables})
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            print(f"An HTTP error occured: {err}")
            return
        data = response.json()

        changes = await self._look_for_changes(data, ids)

        if changes == False:
            print(f"Searched through {len(ids)} shows and found no changes.")

    async def _look_for_changes(
        self, anilist_data, ids: list[tuple[int, list[int]]]
    ) -> bool:
        WEEKLY_REMINDERS_ENABLED = 1
        WEEKLY_REMINDERS_DISABLED = 0
        CHANNEL = self.bot.get_channel(self.channel_id)
        if CHANNEL is None:
            CHANNEL = await self.bot.fetch_channel(self.channel_id)
        cursor = self.bot.connection.cursor()

        found_change = False

        for i, show in enumerate(anilist_data["data"]["Page"]["media"]):
            id = show["id"]
            users_who_track = ids[i][1]
            anilist_english_title = show["title"]["english"]
            anilist_status = show["status"]
            startDate = show["startDate"]
            anilist_next_airing_episode = (
                show["nextAiringEpisode"]["airingAt"]
                if show["nextAiringEpisode"]
                else None
            )
            anilist_startDate = (
                f"{startDate['year']}-{startDate['month']}-{startDate['day']}"
            )

            cursor.execute(
                "SELECT status, next_episode_airs, start_date, title_english FROM animes WHERE id = ?",
                (show["id"],),
            )
            row = cursor.fetchone()
            if not row:
                continue

            db_status, db_next_airing_episode, db_startDate, db_english_title = row

            if anilist_english_title != db_english_title:
                cursor.execute(
                    "UPDATE animes SET title_english = ? WHERE id = ?",
                    (anilist_english_title, id),
                )
                found_change = True

            # If anime concludes
            if anilist_status != db_status and anilist_status == "FINISHED":
                found_change = True

                cursor.execute(
                    "DELETE FROM tracked_anime WHERE anime_id = ?", (show["id"],)
                )
                cursor.execute("DELETE FROM animes WHERE id = ?", (show["id"],))

                print(f"Removing {show['id']} from database due to show concluding.")
                found_change = True
                mention_string = get_mention_string(users_who_track)
                await CHANNEL.send(
                    f"❌ **{db_english_title}** has concluded and has been removed from your tracking list. ❌\n{mention_string}"
                )
                continue

            # If anime starts releasing
            if anilist_status == "RELEASING" and db_status == "NOT_YET_RELEASED":
                found_change = True
                cursor.execute(
                    "UPDATE animes SET status = ? WHERE id = ?",
                    (anilist_status, show["id"]),
                )
                print(
                    f"Changing database status: {db_status} -> {anilist_status}. ({id})"
                )
                found_change = True
                db_status = "RELEASING"
                mention_string = get_mention_string(users_who_track)
                await CHANNEL.send(
                    f"🚨 **{db_english_title}** has started airing! 🚨\n{mention_string}"
                )
                continue

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
                    "next_episode_airs",
                    "next episode airing time",
                ),
                (
                    anilist_startDate,
                    db_startDate,
                    "start_date",
                    "start date",
                ),
            ]

            for j, (new_val, old_val, db_column, label) in enumerate(changes_to_look_for):
                is_checking_airing = j == 2 and changes_to_look_for[1][1] == "RELEASING"
                new_val_is_new = new_val is not None and new_val != old_val
                if is_checking_airing and new_val_is_new:
                    # This is an exception for weekly reminders
                    print("Weekly reminder loop entered.")
                    cursor.execute("SELECT user_id from tracked_anime WHERE anime_id = ? AND weekly_reminders_toggled = ?", (id, 1))
                    row = cursor.fetchall()
                    uids = [user_ids[0] for user_ids in row]
                    if len(uids) > 0:
                        await CHANNEL.send(f"🚨AIRING REMINDER🚨\n**{db_english_title}** has aired a new episode.\n{get_mention_string(uids)}")
                    continue
                    
                if new_val is not None and new_val != old_val:
                    cursor.execute(
                        f"UPDATE animes SET {db_column} = ? WHERE id = ?",
                        (new_val, show["id"]),
                    )
                    print(f"{label} changed: {old_val} --> {new_val}.")

                    if "next_episode_airs" in db_column:
                        new_val = format_time(unix_epoch_time=new_val)
                        old_val = format_time(unix_epoch_time=old_val)
                    elif "startDate" in db_column:
                        new_val = format_time(date=new_val)
                        old_val = format_time(date=old_val)
                    user_mention_string = get_mention_string(users_who_track)
                    await CHANNEL.send(
                        f"⚠️ UPDATE ⚠️: **{db_english_title}'s ({id})** {label} has changed. \n**{old_val} ➡️ {new_val}**\n{user_mention_string}"
                    )

                    found_change = True

            if found_change:
                self.bot.connection.commit()

        return found_change

    @tasks.loop(time=time(hour=21, tzinfo=timezone.utc))
    async def reminder(self):
        """
        ts is out of commission for now im not doing this rn
        """
        # CHANNEL = self.bot.get_channel(self.channel_id)
        # if CHANNEL is None:
        #     CHANNEL = await self.bot.fetch_channel(self.channel_id)

        # # One week in seconds
        # ONE_WEEK = 60 * 60 * 24 * 7

        # NOW = int(datetime.now(timezone.utc).timestamp())

        # cursor = self.bot.connection.cursor()
        # cursor.execute(
        #     "SELECT a.id, a.title_english, a.next_episode_airs, weekly_reminder_sent FROM tracked_anime"
        # )

        # rows = cursor.fetchall()

        # if not rows:
        #     print("Not tracking any anime yet, skipping checking for weekly reminder.")
        #     return

        # for id, english_title, next_episode_airs, weekly_reminder_already_sent in rows:
        #     weekly_reminder_already_sent = bool(weekly_reminder_already_sent)
        #     if weekly_reminder_already_sent == True:
        #         print(f"{english_title} has already had a 1 week reminder sent.")
        #         continue
        #     if next_episode_airs == None:
        #         print(f"{english_title} has no scheduled next episode yet.")
        #         continue

        #     time_to_next_ep = next_episode_airs - NOW
        #     if 0 < time_to_next_ep <= ONE_WEEK:
        #         cursor.execute(
        #             "UPDATE tracked_anime SET weekly_reminder_sent = 1 WHERE anilist_id = ?",
        #             (id,),
        #         )
        #         self.bot.connection.commit()
        #         await CHANNEL.send(
        #             f"🔔 **{english_title}** is less than one week from airing it's first episode! 🔔"
        #         )

    @tasks.loop(hours=72)
    async def database_backup(self):
        if not os.path.exists("backups"):
            os.makedirs("backups")

        def create_backup(backups_folder_path, source_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = Path(backups_folder_path) / f"database_backup_{timestamp}.db"

            with sqlite3.connect(source_path) as src:
                with sqlite3.connect(backup_file) as dest:
                    src.backup(dest)
            print(f"Database backup completed!: {backup_file}")

        try:
            root = Path(__file__).parent.parent
            dest = (root / "backups").resolve()
            anime_bot_db = (root / "anime_bot.db").resolve()

            await asyncio.to_thread(create_backup, dest, anime_bot_db)

        except Exception as e:
            print(f"Backup failed: {e}")

    @query_anilist.before_loop
    async def before_query_anilist(self):
        print("Waiting until bot is initialized until querying AniList...")
        await self.bot.wait_until_ready()

    @reminder.before_loop
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
