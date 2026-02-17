# Notes

## Plan outline

TODO:

## Graphql useful query objects

Media Object:

- id
  - Find in URL of the anilist page
- description
- nextAiringEpisode { airingAt }
  - Returns the time in seconds since Unix epoch
  - Returns null if show is finished airing.
  - Also returns null if the show has no official release date but does have a release year/season
- startDate solves problem above by returning null for what it doesnt know and values for what it does.

## Storage

Maybe use SQLite or just a plain json file with backups we'll see.

## What I actually want from this bot

[Lines prefixed with ? are maybe not feasible]

- It should be able to give me a notification when scheduling changes (i.e: delays, setting scheduling dates that were previously unknown)
- ?Announce when trailers or teasers come out for upcoming anime i follow
- Give reminders when a new show is 7 days away from airing episode 1
