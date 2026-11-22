# Backlog

## Goal
A live stats leaderboard (and later a nightly world map) for a small self-hosted Minecraft
server, built from the files the server already writes. Also a portfolio project, so code,
history and infrastructure should be clean and explainable.

## Success criteria
- Friends can open the page (Phase 1 "done" definition)
- Numbers match the server's own stats files
- Game server stays untouched: read-only access, no IPs stored or shown, no new port forwards

## Vertical slice (MVP)
**Outcome:** A friend opens a URL on the LAN/Tailscale and sees leaderboards (play time, deaths, mob kills, advancements, top slayer per mob) built from the real server files.
**End-to-end path:** stats/advancements/usercache files in CT 100 -> Proxmox host job copies them read-only to `/srv/mc-export` every minute -> web container (CT 101) mounts that folder read-only -> Python build parses files and writes static `index.html` -> small web server on port 8080 -> browser
**Out of scope for the slice:** log tailing / live feed, PvP, SQLite, FastAPI / JSON API, Docker Compose, BlueMap, Paper plugin, Cloudflare, styling polish, distance boards, advancement progress bars, fastest-advancement times, player skins, auth

## Tasks
Tracked as GitHub issues. Regenerate this snapshot with `gh issue list --state all`.

| Issue | Task | Size | Status |
|-------|------|------|--------|
| #1 | Make fake players for testing | S | open |
| #2 | Read each player's stats | M | open |
| #3 | Count real advancements (skip recipe unlocks) | S | open |
| #4 | Turn the numbers into a leaderboard page | M | open |
| #5 | Decide how the website gets the server files | S | open |
| #6 | Copy the player files out every minute | M | open |
| #7 | Put the website in its own container | M | open |
| #8 | Test everything end to end + README how-to | S | open |

Critical path: #1 -> #2 + #3 -> #4 -> #7, with #5 -> #6 -> #7 in parallel. #8 follows #4.
