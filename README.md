# Anime Announcer

A Discord bot to track upcoming anime you and your server are interested in.

It uses the AniList API to track changes in the AniList database and notify the people who track of such changes.

It'll notify you when a release date changes, a new episode airs, or when a season finishes. Also has neat info panels for any anime.

## Examples
<img width="783" height="629" alt="Screenshot_2026-10-11-222240" src="https://github.com/user-attachments/assets/14f88a49-48c4-4da2-ae55-3d6fa280c83e" />

![image](https://github.com/user-attachments/assets/466e1835-5609-4582-a6a1-7ed5f5df431c)

## Usage
Navigate to the [Discord Developer Portal](https://discord.com/developers/home) and create an application. Follow the instructions and once completed: Navigate to the 'Bot' section to copy your token and paste it into your `.env`(only use .env if not using docker and using systemd. Otherwise just put token in docker-compose.yml) file in the directory you cloned the repository to. (Example in `.env.example`)
### Docker Compose
1. Navigate to the [Discord Developer Portal](https://discord.com/developers/home) and create an application.
2. Follow the instructions and once completed: Navigate to the 'Bot' section to copy your token
3. Paste the token in your docker-compose.yml
4. Find the channel ID of the channel you want the bot to make announcements in.
5. Paste it in your docker-compose.yml
6. docker compose up -d
```yaml
services:
  anime-announcer:
    image: bmiz/anime-announcer-discord-bot:latest
    container_name: anime-announcer-discord-bot
    restart: unless-stopped
    environment:
      DISCORD_TOKEN: "paste_your_bot_token_here"
      ANNOUNCEMENT_CHANNEL_ID: "123456789012345678"
```
### Systemd
1. Wherever you would like, clone this repository.
2. Create an animebot.service file (mines in /etc/systemd/system/animebot.service)
3. Paste in the file below, or create your own
4. Fill in `User and ExecStart` fields with necessary info.
```ini
[Unit]
Description=Discord Anime Bot
After=network-online.target
Wants=online.target

[Service]
User=yourUser
WorkingDirectory=/path/to/Anime-Announcer-Discord-Bot/
ExecStart=/path/to/your/python -u /path/to/where/you/cloned/the/repo/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
### Commands

`!info {id | name}` (Gives current info known about show)\
`!list` (Lists shows the user who sent the command is currently tracking.)\
`!track {id | name}` (Adds show to database and begins querying the API to check for updates.)\
`!untrack {id | name}`\
`!shutdown`\
`!ping` (returns your current ping in ms)\
`!toggle_reminders {id | name}` (Toggles reminders for a currently releasing show for the user)

<sub>Can you tell I like Vinland Saga?</sub>
