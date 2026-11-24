# mc-server-stats

Live stats leaderboard and daily world map for a self-hosted Minecraft (Paper) server.

> 🚧 Early work in progress. See [`CLAUDE.md`](CLAUDE.md) for the full plan and data notes.

## Planned features

- **Leaderboards:** play time, deaths (and what killed you), mob kills per mob type, advancements, distance traveled
- **Live feed:** who's online, deaths and advancements as they happen
- **Fastest advancement** times since first join
- **World map** re-rendered every night

## How it works

Minecraft already records per-player stats and advancements (with timestamps) as JSON files,
and writes live events to its log. A small collector reads both, stores them in SQLite, and a
web page shows the results. No game mods are required. A custom Paper plugin may replace log
parsing later.

## Stack (planned)

Python · SQLite · FastAPI · Docker Compose · Proxmox LXC · BlueMap
