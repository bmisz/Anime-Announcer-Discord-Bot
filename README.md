# Anime Announcer

A Discord bot to track upcoming anime you and your server are interested in.

It uses the AniList API to track changes in the AniList database and notify the people who track of such changes.

## Example

![image](https://github.com/user-attachments/assets/466e1835-5609-4582-a6a1-7ed5f5df431c)

## Usage

Navigate to the [Discord Developer Portal](https://discord.com/developers/home) and create an application. Follow the instructions and once completed: Navigate to the 'Bot' section to copy your token and paste it into your `.env` file in the directory you cloned the repository to. (Example in `.env.example`)

I use a systemd service on my old laptop that I converted to a server to run the bot, as it ideally should be running 24/7 to check for changes at all times. I would suggest this way but if you have other ways you would like to run it you just need to execute the main.py file at some point and let it run.

### Commands

`!info {id}` (Gives current info known about show)\
`!list` (Lists shows the user who sent the command is currently tracking.)\
`!track {id}` (Adds show to database and begins querying the API to check for updates.)\
`!untrack {id}`\
`!shutdown`\
`!ping`