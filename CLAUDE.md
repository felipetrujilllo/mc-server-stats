# CLAUDE.md — mc-server-stats

Project context for Claude Code. Read this first every session.

## What this project is

A **live stats leaderboard + daily world map** for my self-hosted Minecraft server
(a small friends' server). Inspired by a homelab "server tour" video where the owner had
achievement leaderboards, a deaths board, a PvP board and a world render that updates daily.

It's also a **portfolio project** (SWE/DevOps resume, maybe a YouTube series),
so the code, Git history, README and infrastructure should be clean and explainable.

## How to work with me

- I'm a **beginner** with Linux. **Explain every command and every setting**: what it does and why.
- Give exact, copy-pasteable commands and say **where** each runs:
  my Mac, the Proxmox host (`root@gs63`), or the Minecraft container (`root@minecraft`).
- **Warn before anything destructive** (deleting data, `rm -rf`, restarting the server while people play).
- Be honest and concrete. If my plan is wrong, say so.
- Prefer small, reviewable steps and commits with clear messages.

## The server (where the data comes from)

| Item | Value |
|---|---|
| Host | Proxmox VE node `gs63` (MSI laptop). SSH alias `gs63` (user root) |
| Container | LXC **CT 100**, hostname `minecraft`, Debian 13, unprivileged |
| Enter it | `ssh gs63`, then `pct enter 100` (or `ssh -t gs63 pct enter 100`) |
| Server | **Paper 26.3** (Minecraft Java 26.3), Java 25, runs as user `minecraft` |
| Server dir | `/opt/minecraft` |
| Service | `systemctl {status,restart,stop} minecraft` (runs Java inside `screen` session `minecraft`) |
| Console | `screen -r minecraft`. Leave with **Control+A, then `d`**. Never Ctrl+C in there |
| Send a console command from the shell | `screen -S minecraft -p 0 -X stuff "COMMAND^M"` |
| Copy a file out of the container (on host) | `pct pull 100 /path/in/ct /path/on/host` |
| Plugins | Chunky 1.5.66, Simple Voice Chat 2.6.27 (bukkit), spark (bundled) |
| World | One folder `/opt/minecraft/world` (26.x keeps nether/end **inside** it), border 10,000×10,000 at 0,0, pre-generated |
| Timezones | Container (and so Minecraft logs) = **UTC**. Proxmox host = America/New_York |

**Never touch the live server from code without asking.** Read-only access to its files is the default.

## Data sources (verified on the real server, 26.3)

| Data | Path | Notes |
|---|---|---|
| Per-player stats | `/opt/minecraft/world/players/stats/<uuid>.json` | **26.x path** (older versions: `world/stats/`) |
| Per-player advancements | `/opt/minecraft/world/players/advancements/<uuid>.json` | Includes timestamps |
| UUID → name | `/opt/minecraft/usercache.json` | List of `{uuid, name, expiresOn}` |
| Live events | `/opt/minecraft/logs/latest.log` | Rotated to `logs/YYYY-MM-DD-N.log.gz` on each start |

### Stats file facts
- Shape: `{"stats": {"minecraft:custom": {...}, "minecraft:killed": {...}, "minecraft:killed_by": {...}, "minecraft:mined": {...}, ...}, "DataVersion": N}`
- `minecraft:custom` → `play_time`, `total_world_time`, `time_since_death`, `time_since_rest`, `sneak_time` are in **ticks** (20 / second; ÷ 72,000 = hours).
- Distances (`walk_one_cm`, `sprint_one_cm`, `swim_one_cm`, `fly_one_cm`, …) are in **centimeters**.
- `deaths`, `mob_kills`, `player_kills`, `jump`, `damage_dealt`, `damage_taken`, `leave_game` are counts.
- `minecraft:killed` = kills per mob type. `minecraft:killed_by` = deaths per mob type.
- **Missing keys/sections mean zero.** A brand-new player has no `minecraft:killed` at all. Always default to 0.

### Advancements file facts
- Shape: `{"minecraft:adventure/root": {"criteria": {"<name>": "2026-11-24 02:06:45 +0000"}, "done": true}, ..., "DataVersion": N}`
- Timestamps are **UTC**, format `YYYY-MM-DD HH:MM:SS +0000`.
- **Filter out `minecraft:recipes/...`**: those are recipe unlocks, not real advancements.
- `done: false` entries hold **partial progress** (e.g. `adventure/adventuring_time` lists biomes visited, `adventure/kill_all_mobs` lists mob types killed), which is useful for progress bars.
- Skip the `DataVersion` key when iterating.

### Freshness (important)
- The server only writes stats/advancement files on **autosave (~every 5 min)** and when a player **leaves**.
  Reading files alone gives totals up to ~5 min stale.
- Live data therefore comes from **tailing `latest.log`**: joins/leaves (who's online), deaths with cause,
  advancements earned (`<Name> has made the advancement [X]`), PvP.

### Log parsing safety
- Player names are `[A-Za-z0-9_]{3,16}`. Chat lines look like `<Name> message`.
- Anchor regexes to the log prefix (`^\[HH:MM:SS\] \[Server thread/INFO\]: `) and reject anything that's chat,
  so a chat message can't fake an event ("stdout injection").
- Log lines contain **player IP addresses** (e.g. `Name[/1.2.3.4:5678] logged in`). Never store, display or commit IPs.

## Architecture (plan)

```
CT 100 (Minecraft)                          Web container (Docker LXC, later)
├─ world/players/stats/*.json   ─┐
├─ world/players/advancements/  ─┼─►  collector ──► SQLite ──► API ──► web page
├─ usercache.json               ─┤     (files every ~1 min,     (FastAPI)  (+ map)
└─ logs/latest.log (live tail)  ─┘      log tailed live)
```

- The website runs in a **separate container** from the game server (isolation).
- Exposure: **LAN + Tailscale first**. Later maybe Cloudflare Tunnel. **No new router port forwards.**
- Open design question: how the web container gets the files (push/export script from CT 100
  vs. world on a shared host folder mounted read-only). Decide in Phase 0.

## Roadmap

- **Phase 0, Design:** explore real files ✅, write `docs/design.md` (features, services, ports, data flow, exposure).
- **Phase 1, MVP leaderboard:** Python reads stats + advancements + usercache → JSON → simple page
  (most play time, deaths, mob kills, advancements, top slayer per mob).
  *Done when friends can open the page.*
- **Phase 2, Live events:** tail `latest.log` → SQLite (deaths w/ cause, PvP, sessions, advancements),
  backfill from old `.log.gz`, small API. Fastest-advancement leaderboard (first join → earned).
  *Done when a death shows up within seconds.*
- **Phase 3, Nightly map:** BlueMap CLI renders a **copy** of the world (or last backup) after the 04:00 backup → static files.
  *Done when builds appear on the map next morning.*
- **Phase 4, Own Paper plugin (Java):** listens to game events and POSTs to the API (replaces log parsing). Tests + CI.
- **Throughout:** Docker Compose, README with diagram + screenshots, DB backups, Uptime Kuma check.

## Development workflow

- Develop on the **Mac** against local copies in `sample-data/` (git-ignored).
  Refresh them from the server:
  ```bash
  # on the Proxmox host
  mkdir -p /root/mc-sample
  pct pull 100 /opt/minecraft/usercache.json /root/mc-sample/usercache.json
  # …plus stats/advancements files and latest.log
  # on the Mac
  scp -r gs63:/root/mc-sample ./sample-data
  ```
- Python 3, standard library first. Add dependencies only when needed (pin them in `requirements.txt`).
- Code should take the server dir as a config value/env var (e.g. `MC_SERVER_DIR`), not hard-code paths.

## Never commit

- `sample-data/`, any real `*.log` / `*.log.gz` (contain IPs), real `usercache.json` / stats files (friends' names/UUIDs)
- Public IP addresses, passwords, tokens, `.env`
- For tests/README use **fake** sample data under `tests/fixtures/` with made-up players.
