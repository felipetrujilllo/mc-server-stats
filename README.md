# mc-server-stats

Live stats leaderboard (and, later, a daily world map) for a self-hosted Minecraft server (Paper)
running on my home Proxmox server.

## What works today (Phase 1)

A leaderboard page with five boards, rebuilt every minute from the server's own stats files:

- **Most play time**
- **Most deaths**
- **Most mob kills**
- **Most advancements** (real ones only; recipe unlocks are skipped)
- **Top killer per mob** (who has killed the most of each mob type)

First place on each board gets a crown. The page has a Minecraft-style look: sky, grass and dirt
background and a blocky font.

## How it works

```
gs63 (Proxmox host)
├─ CT 100  Minecraft server ── writes stats/advancements/usercache files
├─ export  every minute, copies only those files (never logs, which hold IPs) → /srv/mc-export
└─ CT 101  website: mounts /srv/mc-export read-only, rebuilds index.html every minute,
           serves it on port 8080 (home network only, no router port forwards)
```

The page is plain HTML and CSS written by Python's standard library: no framework, no JavaScript,
no dependencies. Details and the reasoning are in [docs/design.md](docs/design.md).

## Run it locally (Mac)

Needs Python 3.9+. Everything uses fake players from `tests/fixtures/`, so no server is needed.

| Command | What it does |
|---|---|
| `make serve` | Live preview at http://localhost:8000. Rebuilds on every refresh, so code changes show up right away. Ctrl+C stops it. |
| `make dev` | Builds the page once into `out/` and opens it. |
| `make real` | Same, from a copy of real server data in `sample-data/` (git-ignored). |
| `make test` | Runs all tests (`python3 -m unittest`) and `shellcheck` on the deploy script. |

Without `make`: `MC_SERVER_DIR=$PWD/tests/fixtures python3 -m mcstats build --out out`.

### Optional art files (not in the repo)

The page looks for these next to `index.html` and falls back gracefully when they're missing:

- `dirt.png`, `grass_block_side.png`, `sun.png`, `stone.png`: textures from the Minecraft game files.
  They're Mojang's, so they are **never committed**; copy them into `out/` by hand for local previews.
  Without them the page shows a hand-drawn dirt tile instead.
- `Monocraft.otf`, `Monocraft-Black.otf`: the [Monocraft](https://github.com/IdreesInc/Monocraft) font (OFL licence).
  Without them the page uses the system's monospace font.

## Deploy

1. **Export job on the Proxmox host:** [deploy/README.md](deploy/README.md)
2. **Website container (CT 101):** [deploy/web/README.md](deploy/web/README.md)

To ship a code change: push to GitHub, then on the host run `pct exec 101 -- git -C /opt/mc-server-stats pull`.
The next build (within a minute) uses the new code.

## Project layout

| Path | What |
|---|---|
| `mcstats/stats.py` | Reads stats, advancements and usercache into one record per player |
| `mcstats/page.py` | Turns those records into the HTML page and writes it safely (temp file + rename) |
| `mcstats/__main__.py` | The `build` and `serve` commands |
| `deploy/` | Export script and systemd units for the Proxmox host |
| `deploy/web/` | systemd units and setup guide for the website container |
| `docs/design.md` | Data flow, ports, exposure, security decisions |
| `tests/` | Unit and end-to-end tests; `tests/fixtures/` holds the fake players |

## Roadmap

- [x] **Phase 0:** design ([docs/design.md](docs/design.md))
- [x] **Phase 1:** leaderboard page, live on the home network
- [ ] Public link for friends (Tailscale Funnel or Cloudflare Tunnel, with Caddy in front)
- [ ] **Phase 2:** live events from the server log (deaths with cause, PvP, who's online), fastest advancements
- [ ] **Phase 3:** nightly world map (BlueMap)
- [ ] **Phase 4:** own Paper plugin that sends events directly
