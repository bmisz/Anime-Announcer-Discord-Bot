from datetime import datetime, time, timezone
import requests
import os
import sqlite3
from discord.ext import commands, tasks
from langdetect import detect

class AnimeAnnouncer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = 1469512207355347143
        self.query_anilist.start()

    @staticmethod
    def _determine_english_title(synonym_list):
        for synonym in synonym_list:
            language_of_syn = detect(synonym)
            if language_of_syn == 'en':
                return synonym
        return None     # No synonyms were in english

    @staticmethod
    def convert_epoch_to_local(unix_epoch_time):
        dt_unix = datetime.fromtimestamp(unix_epoch_time)
        formatted_time = dt_unix.strftime("%a %d %b, %I:%M%p")
        return formatted_time
    
    @commands.command(name="track")
    async def track(self, ctx, anime_id: str = ""):
        try: 
            anime_id_int = int(anime_id)
        except ValueError:
            await ctx.send("This is not a valid integer ID")
            return
        if anime_id == "":
            await ctx.send("Please enter an ID to start tracking.")
        else:
            query = '''
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
            '''

            variables = {
                'id': anime_id_int
            }
            url = 'https://graphql.anilist.co'

            response = requests.post(url, json={'query': query, 'variables': variables})
            data = response.json()
            anime = data['data']['Media']

            if anime['status'] == "FINISHED":
                await ctx.send("Show is finished and therefore has no reason to be tracked. Not added. ")
                return
            
            start_date = f"{anime['startDate']['year']}-{anime['startDate']['month']}-{anime['startDate']['day']}"

            next_ep = anime['nextAiringEpisode']['airingAt'] if anime['nextAiringEpisode'] else None

            sql = """
                INSERT OR REPLACE INTO tracked_anime 
                (anilist_id, title_english, title_romaji, next_episode_time, startDate, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """

            cursor = self.bot.connection.cursor()
            
            cursor.execute("SELECT 1 FROM tracked_anime WHERE anilist_id = ?", (anime_id_int,))
            if cursor.fetchone():
                await ctx.send("You've already started tracking this show.")
                return

            if anime['title']['english'] is None:
                english_title = self._determine_english_title(anime['synonyms'])
                if english_title is None:
                    english_title = anime['title']['romaji']   
            else:
                english_title = anime['title']['english']

            cursor.execute(
                sql, (
                    anime['id'], 
                    english_title, 
                    anime['title']['romaji'], 
                    next_ep, 
                    start_date, 
                    anime['status']
                )
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
        
        cursor = self.bot.connection.cursor()
        cursor.execute("SELECT title_english FROM tracked_anime WHERE anilist_id = ?", (anime_id_int,))
        name = cursor.fetchone()
        name = name[0]
        cursor.execute("DELETE FROM tracked_anime WHERE anilist_id = ?", (anime_id_int,))
        self.bot.connection.commit()
        await ctx.send(f"Stopped tracking **{name} ({anime_id_int})**")

    @commands.command(name="list")
    async def list(self, ctx):
        cursor = self.bot.connection.cursor()
        cursor.execute("SELECT anilist_id, title_english FROM tracked_anime")
        rows = cursor.fetchall()
        if not rows:
            await ctx.send("**You're not currently tracking any animes, to get started use !track *id.***")
            return
        rows_as_strings = []
        for id, title in rows:
            rows_as_strings.append(f"**• {title}** *(ID: {id})*")
        
        rows_as_strings.insert(0, "# Tracked Animes:")
        final_string = "\n".join(rows_as_strings)
        
        await ctx.send(final_string)

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
        
        query = '''
        query ($ids: [Int]) {                                  # Define which variables will be used in the query (id)
            Page {
                media (id_in: $ids, type: ANIME) {                    # Insert our variables into the query arguments (id) (type: ANIME is hard-coded in the query)
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
        '''

        variables = {
            'ids': ids
        }
        url = 'https://graphql.anilist.co'

        response = requests.post(url, json={'query': query, 'variables': variables})
        data = response.json()

        changes = self._look_for_changes(data)

        if changes == False:
            print(f"Searched through {len(ids)} shows and found no changes.")

    async def _look_for_changes(self, anilist_data):
        CHANNEL = self.bot.get_channel(self.channel_id)
        cursor = self.bot.connection.cursor()
        found_change = False

        for show in anilist_data['data']['Page']['media']:
            anilist_english_name = show['title']['english']
            anilist_status = show['status']
            anilist_time = show['nextAiringEpisode']['airingAt'] if show['nextAiringEpisode'] else None
            startDate_as_unix_epoch = show['startDate']
            anilist_startDate = f"{startDate_as_unix_epoch['year']}-{startDate_as_unix_epoch['month']}-{startDate_as_unix_epoch['day']}"
  

            cursor.execute("SELECT status, next_episode_time, startDate, title_english FROM tracked_anime WHERE anilist_id = ?", (show['id'],))
            row = cursor.fetchone()
            if row:
                db_status = row[0]
                db_time = row[1]
                db_startDate = row[2]
                db_english_title = row[3]

            
            if (anilist_english_name != db_english_title) and (anilist_english_name is not None):
                print(f"English title has changed from {db_english_title} to {anilist_english_name}")
                found_change = True
                cursor.execute("UPDATE tracked_anime SET title_english = ? WHERE anilist_id = ?", (anilist_english_name, show['id']))
            
            if anilist_status != db_status and anilist_status == "FINISHED":
                found_change = True
                cursor.execute("DELETE FROM tracked_anime WHERE anilist_id = ?", (show['id'],))
                print(f"Removing {show['id']} from database due to show concluding.")
                self.bot.connection.commit()
                await CHANNEL.send(f"❌ **{db_english_title}** has concluded and has been removed from your tracking list. ❌")
                continue

            if anilist_status == "RELEASING" and db_status == "NOT_YET_RELEASED":
                found_change = True
                cursor.execute("UPDATE tracked_anime SET status = ? WHERE anilist_id = ?", (anilist_status, show['id']))
                print(f"Changing database status: {db_status} -> {anilist_status}. ({show['id']})")
                self.bot.connection.commit()
                await CHANNEL.send(f"🚨 **{db_english_title}** has started airing! 🚨")
            
            elif anilist_status != db_status:
                found_change = True
                cursor.execute("UPDATE tracked_anime SET status = ? WHERE anilist_id = ?", (anilist_status, show['id']))
                print(f"Changing database status: {db_status} -> {anilist_status}. ({show['id']})")
                self.bot.connection.commit()
                await CHANNEL.send(f"⚠️ UPDATE ⚠️: **{db_english_title}**'s status has changed. \n{db_status} ➡️ {anilist_status}")
            
            if anilist_startDate != db_startDate:
                found_change = True
                cursor.execute("UPDATE tracked_anime SET startDate = ? WHERE anilist_id = ?", (anilist_startDate, show['id']))
                print(f"Changing database startDate: {db_startDate} -> {anilist_startDate}. ({show['id']})")
                self.bot.connection.commit()
                await CHANNEL.send(f"⚠️ UPDATE ⚠️: **{db_english_title}**'s start date has changed. \n{db_startDate} ➡️ {anilist_startDate}")

            if anilist_time != db_time:
                found_change = True
                cursor.execute("UPDATE tracked_anime SET next_episode_time = ? WHERE anilist_id = ?", (anilist_time, show['id']))
                print(f"Changing database time: {db_time} -> {anilist_time}. ({show['id']})")
                self.bot.connection.commit()
                await CHANNEL.send(f"⚠️ UPDATE ⚠️: **{db_english_title}**'s next episode airing time has changed. \n{db_time} ➡️ {self.convert_epoch_to_local(anilist_time)}")
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
        cursor.execute("SELECT anilist_id, title_english, next_episode_time, weekly_reminder_sent FROM tracked_anime")

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
                cursor.execute("UPDATE tracked_anime SET weekly_reminder_sent = 1 WHERE anilist_id = ?", (id,))
                self.bot.connection.commit()
                await CHANNEL.send(f"🔔 **{english_title}** is less than one week from airing it's first episode! 🔔")
            
    @tasks.loop(hours=72)
    async def database_backup(self):
        if not os.path.exists('backups'):
            os.makedirs('backups')

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backups/database_backup_{timestamp}.db"

        try:
            source = self.bot.connection
            dest = sqlite3.connect(backup_file)

            with dest:
                source.backup(dest)
            
            print(f"✅ Backup successful: {backup_file}")
        except Exception as e:
            print(f"❌ Backup failed: {e}")
        finally:
            dest.close()

    @query_anilist.before_loop
    async def before_query_anilist(self):
        print('Waiting until bot is initilized until querying AniList...')
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(AnimeAnnouncer(bot))