# deploy/web/

Files for the **web container, CT 101** (hostname `mcstats-web`). It rebuilds the leaderboard page
every minute from `/srv/mc-export` (read-only) and serves it on port 8080 to the home network.
Background: [docs/design.md](../../docs/design.md), section "Web container (CT 101)".

| File | What it is |
|---|---|
| `mcstats-build.service` | Runs `python3 -m mcstats build` once as user `mcstats` (`Type=oneshot`). Writes `/var/www/mcstats/index.html`. |
| `mcstats-build.timer` | Starts the build every minute. |
| `mcstats-web.service` | Serves `/var/www/mcstats` on port 8080 with Python's built-in web server, as user `mcstats`. |

Each command below says where it runs:
- **Mac**: your laptop's Terminal.
- **Proxmox host** (`root@gs63`): after `ssh gs63`.
- **Web container** (`root@mcstats-web`): after `pct enter 101` on the host (leave it again with `exit`).

## Step 0: Install the export first (ticket #6)

The website reads the files the export copies out of CT 100. If you haven't yet, follow
[deploy/README.md](../README.md) on the host, then check:

Run on: **Proxmox host**
```bash
ls -l /srv/mc-export/usercache.json
```
Shows the exported name list. "No such file or directory" means the export isn't running yet: fix that first.

## Step 1: Check the container ID and storage names

Run on: **Proxmox host**
```bash
pct list
```
Lists existing containers. **101 must not be in the list.** If it is, pick a free ID and use it everywhere below instead of 101.

```bash
pvesm status --content vztmpl
```
Shows the storages that can hold container templates (normally `local`). Use that name where the steps say `local`.

```bash
pvesm status --content rootdir
```
Shows the storages that can hold container disks (normally `local-lvm`). Use that name where the steps say `local-lvm`.

## Step 2: Download the Debian 13 template

Run on: **Proxmox host**
```bash
pveam update
```
Refreshes Proxmox's list of downloadable container templates.

```bash
pveam available --section system | grep debian-13
```
Shows the Debian 13 template's file name, e.g. `debian-13-standard_13.<x>-<y>_amd64.tar.zst`. Copy the exact name.

```bash
pveam list local | grep debian-13
```
Shows whether you already have it (CT 100 is Debian 13 too, so it may be there). If it is, skip the next command.

```bash
pveam download local <template>
```
Downloads the template into the `local` storage. Replace `<template>` with the name you copied.

## Step 3: Create CT 101

Run on: **Proxmox host**
```bash
pct create 101 local:vztmpl/<template> --hostname mcstats-web --memory 512 --cores 1 --rootfs local-lvm:4 --net0 name=eth0,bridge=vmbr0,ip=dhcp --unprivileged 1 --onboot 1 --start 0
```
Creates the container without starting it. What each part means:
- `101`: the container ID. `local:vztmpl/<template>`: the template from step 2.
- `--hostname mcstats-web`: its name on the network and in the prompt.
- `--memory 512 --cores 1 --rootfs local-lvm:4`: 512 MB RAM, 1 CPU core, a 4 GB disk on `local-lvm`.
- `--net0 name=eth0,bridge=vmbr0,ip=dhcp`: one network card on the same bridge as CT 100; the router hands out the address.
- `--unprivileged 1`: root inside the container is not root on the host.
- `--onboot 1`: start it when the host boots. `--start 0`: don't start it yet (we add the mount first).

It may ask for a root password; pick one and keep it in your password manager (`pct enter` doesn't need it).

**Or in the Proxmox web UI** (instead of the `pct create` command; same result).
Run on: **Mac** (browser): open `https://<gs63-ip>:8006` and log in, then click **Create CT**:
1. **General**: CT ID `101`, Hostname `mcstats-web`, **Unprivileged container** checked, set a root password.
2. **Template**: the Debian 13 template from step 2.
3. **Disks**: 4 GB on `local-lvm`.
4. **CPU**: 1 core.
5. **Memory**: 512 MB, Swap 512 MB.
6. **Network**: name `eth0`, bridge `vmbr0`, IPv4 **DHCP**.
7. **DNS**: leave the defaults.
8. **Confirm**: leave **Start after created UNchecked** (we add the mount first), then click Finish.

Then select CT 101 → **Options** → **Start at boot** → Yes (the UI version of `--onboot 1`).

> The read-only bind mount in step 4 **cannot be done in the web UI**: its "Add → Mount Point" only creates
> storage-backed volumes, not host folders. Run step 4 in a shell on the host: `ssh gs63` from the Mac,
> or the node's **Shell** button in the web UI (click `gs63` in the left tree, then Shell).

## Step 4: Give it the export folder, read-only, and start it

Run on: **Proxmox host**
```bash
pct set 101 -mp0 /srv/mc-export,mp=/srv/mc-export,ro=1
```
Makes the host's `/srv/mc-export` appear at `/srv/mc-export` inside CT 101. `mp0` = first mount point,
`mp=` = path inside the container, `ro=1` = **read-only**, so the website can never change the export.

```bash
pct start 101
```
Boots the container.

```bash
pct enter 101
```
Opens a root shell inside CT 101. The prompt changes to `root@mcstats-web`. Steps 5 to 7 run there.

## Step 5: Install Python and git

Run on: **Web container**
```bash
apt update && apt install -y python3 git
```
`apt update` refreshes the package list; `apt install -y` installs Python (runs the site) and git (fetches the code). `-y` = don't ask "are you sure".

## Step 6: Create the user, fetch the code, create the output folder

Run on: **Web container**
```bash
useradd --system --create-home --shell /usr/sbin/nologin mcstats
```
Creates a service account `mcstats` that both services run as. `--system` = not a person's account,
`--shell /usr/sbin/nologin` = nobody can log in as it.

```bash
git clone https://github.com/felipetrujilllo/mc-server-stats.git /opt/mc-server-stats
```
Downloads this repo into `/opt/mc-server-stats` (public repo, no login needed). It stays owned by root,
so the `mcstats` user can run the code but not change it.

```bash
install -d -o mcstats -g mcstats /var/www/mcstats
```
Creates the folder the page is written to and served from, owned by `mcstats` (the only folder it may write).

## Step 7: Install and start the services

Run on: **Web container**
```bash
cp /opt/mc-server-stats/deploy/web/mcstats-build.service /opt/mc-server-stats/deploy/web/mcstats-build.timer /opt/mc-server-stats/deploy/web/mcstats-web.service /etc/systemd/system/
```
Copies the three unit files to where systemd looks for admin-installed units.

```bash
systemctl daemon-reload
```
Tells systemd to re-read its unit files so it sees the new ones.

```bash
systemctl enable --now mcstats-build.timer mcstats-web.service
```
`enable` = start both at every boot; `--now` = also start them right away. The timer builds the page within a minute.

```bash
systemctl start mcstats-build.service
```
Optional: builds the page right now instead of waiting for the timer.

## Check it works

These checks prove the ticket on the real server. The automated tests (`python3 -m unittest tests.test_web_deploy -v`
on the Mac) only prove the unit files and these commands work together locally.

Run on: **Web container**
```bash
systemctl list-timers mcstats-build.timer
```
Shows when the build last ran and when it runs next (should be under a minute away). Proves: rebuilt every minute.

```bash
journalctl -u mcstats-build.service -n 20
```
Shows the last 20 log lines of the build. Only "Finished" lines is good; an `error:` line tells you what's wrong
(e.g. `no stats folder` = the mount or the export is missing).

```bash
ls -l /var/www/mcstats
```
There should be an `index.html` whose time is less than a minute old (run it twice, a minute apart, to see it change).

```bash
touch /srv/mc-export/x
```
Tries to create a file in the export. It **must fail** with `Read-only file system`. Proves: CT 101 can read but not change the export.
(If it doesn't fail, delete the file with `rm /srv/mc-export/x` and redo step 4.)

```bash
ls /srv/mc-export
```
Shows `usercache.json` and `world`. Proves: CT 101 can read the export.

```bash
systemctl status mcstats-web.service
```
Should say `active (running)`. Press `q` to leave.

```bash
ip -4 addr show eth0
```
Shows the container's address on the `inet` line (`inet <ct101-ip>/24 ...`). Write down `<ct101-ip>`.
(Or, on the **Proxmox host**: `pct exec 101 -- hostname -I`.)

Run on: **Mac**
```bash
curl -s http://<ct101-ip>:8080/ | grep -o '<title>.*</title>'
```
Fetches the page and prints its title: `<title>Server leaderboard</title>`. Proves: served on port 8080 and reachable from the Mac.

Then open `http://<ct101-ip>:8080/` in a browser. You should see the leaderboard with a real player's name.

## Give it a fixed address

The address comes from your router's DHCP and can change after a reboot, which would break the link you send friends.
In the router's admin page, find the DHCP / "address reservation" setting and reserve the current address for CT 101's
MAC address (on the **Proxmox host**, `pct config 101 | grep net0` shows it as `hwaddr=`).
Do **not** add a port forward: the page is home-network only for now (see docs/design.md).

## Updating later

Run on: **Web container**
```bash
git -C /opt/mc-server-stats pull
```
Fetches the newest code. The build reads the code fresh on every run, so changes show up within a minute; no restart needed.
If a unit file changed, repeat step 7's `cp` and `systemctl daemon-reload`, then `systemctl restart mcstats-web.service`.

## Optional: live box from the Discord bot

The build also writes `stats.json` (the same boards as the page), which the Discord bot reads for
`/mc leaderboard`. In the other direction, the bot serves `live.json` (who's online now and today's
play time). Set `LIVE_URL` and each build copies it next to the page, where a small box shows it.
The address stays out of the repo, in a drop-in file that only exists in this container.

Run on: **Web container**
```bash
mkdir -p /etc/systemd/system/mcstats-build.service.d
printf '[Service]\nEnvironment=LIVE_URL=http://<bot-ip>:8081/live.json\n' > /etc/systemd/system/mcstats-build.service.d/live.conf
systemctl daemon-reload
```
Replace `<bot-ip>` with the bot container's address. If the bot is down, the build keeps working and
the page hides the box once its data is 3 minutes old.

## Undo

> **Warning: `pct destroy` permanently deletes CT 101 and everything inside it.** It does not touch CT 100
> (the game server) or the host's `/srv/mc-export`; those keep working.

Run on: **Proxmox host**
```bash
pct stop 101
```
Shuts the container down (the website goes offline).

```bash
pct destroy 101
```
Deletes the container and its disk. Double-check the number: `pct list` should show 101 is `mcstats-web`.
