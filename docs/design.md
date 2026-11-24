# Design: how the website gets the server files

This page records where the leaderboard website lives and how it gets the Minecraft
server's files without being able to touch the game server. It covers the Phase 1 MVP
(tickets #5, #6, #7). Live events, the database and the world map come later.

Terms used below:
- **Proxmox host** (`gs63`): the machine that runs all the containers.
- **LXC container (CT)**: a lightweight isolated Linux system on the host, numbered (CT 100, CT 101).
- **Unprivileged container**: root inside the container is *not* root on the host, which limits damage if it is broken into.
- **Bind mount**: making one folder of the host visible inside a container, here **read-only**.
- **systemd timer**: Linux's built-in scheduler (like cron) that runs a job every N seconds.

## Data flow

```
CT 100 "minecraft" (game)          Proxmox host gs63                 CT 101 (website)
/opt/minecraft/                    every 60 s: deploy/export.sh      every 60 s: mcstats build
 ├─ usercache.json        ──tar──►  /var/tmp/mc-export-staging       /srv/mc-export (read-only)
 ├─ world/players/stats/            │ rsync -a --delete                │
 └─ world/players/advancements/     ▼                                  ▼
                                   /srv/mc-export  ──bind mount ro──► /var/www/mcstats/index.html
                                                                       │ port 8080
                                                                       ▼
                                                              friend's browser (home network)
```

## Export job (on the Proxmox host)

- A script `deploy/export.sh` (ticket #6) runs on the host **every 60 seconds** from a systemd timer.
- It runs `pct exec 100 -- tar -C /opt/minecraft -cf - usercache.json world/players/stats world/players/advancements`.
  `pct exec` runs a command inside CT 100; `tar ... -cf -` packs the files and streams them out.
  `tar` only **reads**, so CT 100 is never modified.
- The staging folder on the host, `/var/tmp/mc-export-staging`, is **emptied first** on every run,
  so a file deleted on the server doesn't linger there (and `--delete` below can remove it).
- The stream is unpacked into that staging folder with `tar --no-same-owner` (the copies are owned by
  host root, not by the container's user ID), then `chmod -R a+rX` makes them readable by everyone.
- If `tar` exits with code **1** (a file changed while it was read, e.g. an autosave mid-copy), that is only a
  warning: the run continues, and the build skips half-written JSON. Any worse error stops the run
  before `rsync`, so the previous good export stays in place.
- Then `rsync -a --delete /var/tmp/mc-export-staging/ /srv/mc-export/` updates the export folder.
  Why rsync: it writes each file under a temporary name and then renames it, so the website never
  reads a half-copied file. It also updates files *inside* the same folder; replacing the whole folder
  would break the bind mount, which would keep pointing at the old, deleted folder.
  `--delete` removes files that no longer exist on the server.
- Only those three items are copied. **Never `logs/`**: log lines contain player IP addresses.

## Web container (CT 101)

- **CT 101**, hostname `mcstats-web`, Debian 13, unprivileged, small: about 512 MB RAM, 1 CPU core, a few GB of disk (ticket #7).
  Setup steps: [deploy/web/README.md](../deploy/web/README.md) (step 1 checks with `pct list` that 101 is free).
- The host folder is bind-mounted read-only:
  `pct set 101 -mp0 /srv/mc-export,mp=/srv/mc-export,ro=1`
  (`mp0` = first mount point, `mp=` = path inside the container, `ro=1` = read-only).
  The export unpacks with `--no-same-owner`, so host root owns the copies, and `chmod -R a+rX`
  makes them readable by everyone. Because CT 101 is unprivileged, host root shows up as owner
  `nobody` inside it. That is fine: the files are world-readable and the site only reads them.
- A systemd timer in CT 101 runs, **every 60 seconds**, as a normal (non-root) user:
  `MC_SERVER_DIR=/srv/mc-export python3 -m mcstats build --out /var/www/mcstats`
  The build writes `index.html` atomically and skips any JSON file that is half-written.
- A systemd service serves the page, also as a non-root user:
  `python3 -m http.server 8080 --directory /var/www/mcstats`
  - shortcut: Python's built-in `http.server` is fine for a home-network page of static files,
    but it is not hardened; swap it for Caddy or nginx before any public exposure (Cloudflare Tunnel phase).

## Ports

| Port | What | Who can reach it |
|---|---|---|
| 25565 | Minecraft server (CT 100, already exists) | Players, as today |
| 8080 | Leaderboard website (CT 101, new) | Home network only |

## How friends reach it

- **Now (home network only):** open `http://<ct101-ip>:8080/`. Give CT 101 a DHCP reservation in
  the router (or a static IP) so the link doesn't change.
- **No router port forwarding.** Nothing new is opened to the internet.
- **Later: Tailscale** (not set up yet). Tailscale is a private network between your own devices,
  so friends outside the house can reach the page without a port forward. Two options, to pick when we get there:
  1. Tailscale on the Proxmox host as a *subnet router* (shares the home network with Tailscale devices).
  2. Tailscale inside CT 101 (an unprivileged container needs `/dev/net/tun` passed in).
- **Maybe after that:** Cloudflare Tunnel for a public link (requires the Caddy/nginx swap first).

## Freshness

The page can be up to about **7 minutes** behind in the worst case:
up to ~5 min until the server's autosave writes the files + up to 1 min until the export + up to 1 min until the build.
Updates within seconds come in Phase 2 by reading the live log.

## Security and privacy

- CT 100 is only read (`tar`), never changed; no accounts, keys or jobs are added inside it.
- CT 101 sees only the three exported items, through a **read-only** mount. It cannot write to
  `/srv/mc-export` or reach the game server's files.
- No log files are copied, so no IP addresses reach the website.
- No router port forwards; the page is home-network only until Tailscale is added.
- Both CT 101 services run as a non-root user.

## Alternatives considered

1. **Bind-mount CT 100's world folder straight into CT 101.** Rejected: the website would see the whole
   world, the two containers would be tied together, and user-ID mapping between two unprivileged containers is fiddly.
2. **CT 100 pushes the files (scp/rsync).** Rejected: needs login credentials and a scheduled job inside the
   game container, which means modifying it.
3. **Run the builder inside CT 100.** Rejected: breaks the goal of keeping the website separate from the game.

## Open items

- Set up Tailscale (host subnet router vs. inside CT 101).
- Replace `http.server` with Caddy or nginx before any public exposure.
