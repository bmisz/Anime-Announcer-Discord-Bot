import discord
import sqlite3
import datetime
import time
import requests
from discord.ext import commands, tasks

class AnimeAnnouncer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = 1473084542934843402
        self.query_anilist.start()


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
                await ctx.send("Show is finished and is therefore has no reason to be tracked. Not added. ")
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

            await ctx.send(f"Now tracking **{anime_id_int}**")

    @commands.command(name="untrack")
    async def untrack(self, ctx, anime_id: str = ""):
        try:
            anime_id_int = int(anime_id)
        except ValueError:
            await ctx.send("This is not a valid integer ID")
            return
        if anime_id == "":
            await ctx.send("Please enter an ID to stop tracking.")
        else:
            sql = "DELETE FROM tracked_anime WHERE anilist_id = ?"
            cursor = self.bot.connection.cursor()
            cursor.execute(sql, (anime_id_int,))
            self.bot.connection.commit()
            await ctx.send(f"Stopped tracking **{anime_id_int}**")

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

        for show in data['data']['Page']['media']:
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

            found_change = False
            
            if (anilist_english_name != db_english_title) and (anilist_english_name is not None):
                print(f"English title has changed from {db_english_title} to {anilist_english_name}")
                found_change = True
                cursor.execute("UPDATE tracked_anime SET title_english = ? WHERE anilist_id = ?", (anilist_english_name, show['id']))
            
            if anilist_status != db_status and anilist_status == "FINISHED":
                found_change = True
                cursor.execute("DELETE FROM tracked_anime WHERE anilist_id = ?", (show['id'],))
                self.bot.connection.commit()
                await CHANNEL.send(f"❌ **{show['title']['english']}** has concluded and has been removed from your tracking list. ❌")
                continue

            if anilist_status == "RELEASING" and db_status == "NOT_YET_RELEASED":
                found_change = True
                cursor.execute("UPDATE tracked_anime SET status = ? WHERE anilist_id = ?", (anilist_status, show['id']))
                self.bot.connection.commit()
                await CHANNEL.send(f"🚨 **{show['title']['english']}** has started airing! 🚨")
            
            elif anilist_status != db_status:
                found_change = True
                cursor.execute("UPDATE tracked_anime SET status = ? WHERE anilist_id = ?", (anilist_status, show['id']))
                self.bot.connection.commit()
                await CHANNEL.send(f"⚠️ UPDATE ⚠️: **{show['title']['english']}**'s status has changed. \n{db_status} ➡️ {anilist_status}")
            
            if anilist_startDate != db_startDate:
                found_change = True
                cursor.execute("UPDATE tracked_anime SET startDate = ? WHERE anilist_id = ?", (anilist_startDate, show['id']))
                self.bot.connection.commit()
                await CHANNEL.send(f"⚠️ UPDATE ⚠️: **{show['title']['english']}**'s start date has changed. \n{db_startDate} ➡️ {anilist_startDate}")

            if anilist_time != db_time:
                found_change = True
                cursor.execute("UPDATE tracked_anime SET next_episode_time = ? WHERE anilist_id = ?", (anilist_time, show['id']))
                self.bot.connection.commit()
                await CHANNEL.send(f"⚠️ UPDATE ⚠️: **{show['title']['english']}**'s next episode airing time has changed. \n{db_time} ➡️ {anilist_time}")

        if not found_change:
            print(f"Checked {len(ids)} shows. No changes found.")


    time = datetime.time(hour=21, tzinfo=datetime.UTC)
    @tasks.loop(time=time)
    async def week_reminder(self):
        CHANNEL = self.bot.get_channel(self.channel_id)
        if CHANNEL is None:
            CHANNEL = await self.bot.fetch_channel(self.channel_id)
    
        # One week in seconds
        ONE_WEEK = 60 * 60 * 24 * 7 

        NOW = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        
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
            if time_to_next_ep <= ONE_WEEK:
                cursor.execute("UPDATE tracked_anime SET weekly_reminder_sent = 1 WHERE anilist_id = ?", (id,))
                self.bot.connection.commit()
                await CHANNEL.send(f"🔔 **{english_title}** is less than one week from airing it's first episode! 🔔")
            
            
    @query_anilist.before_loop
    async def before_query_anilist(self):
        print('Waiting until bot is initilized until querying AniList...')
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(AnimeAnnouncer(bot))