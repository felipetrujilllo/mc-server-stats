# deploy/

Files that run on the **Proxmox host** (`gs63`), not in a container.

| File | What it is |
|---|---|
| `export.sh` | Copies `usercache.json`, `world/players/stats/` and `world/players/advancements/` out of CT 100 into `/srv/mc-export`. Never copies `logs/` (IP addresses). Only reads CT 100. |
| `mc-export.service` | systemd unit that runs the script once (`Type=oneshot`). |
| `mc-export.timer` | systemd timer that starts the service every minute. |

## Install

All commands run on: **Proxmox host (`root@gs63`)**, from a copy of this repo's `deploy/` folder.

```bash
install -m 755 export.sh /usr/local/bin/mc-export.sh
```
Copies the script to where the service expects it (`/usr/local/bin/mc-export.sh`); mode 755 = root can edit, everyone can run it.

```bash
install -m 644 mc-export.service mc-export.timer /etc/systemd/system/
```
Puts the two unit files where systemd looks for admin-installed units.

```bash
systemctl daemon-reload
```
Tells systemd to re-read its unit files so it sees the new ones.

```bash
systemctl enable --now mc-export.timer
```
`enable` = start the timer at every boot; `--now` = also start it right away.

## Check it works

```bash
systemctl list-timers mc-export.timer
```
Shows when the export last ran and when it runs next (should be under a minute away).

```bash
journalctl -u mc-export.service -n 20
```
Shows the last 20 log lines of the export. No output except "Finished" lines means it is working;
a "warning: a file changed" line now and then is normal (an autosave happened mid-copy).

```bash
ls -la /srv/mc-export /srv/mc-export/world/players/stats
```
Lists the exported files; there should be `usercache.json` and a `world/` folder, and no `logs/`.

Test locally on a Mac (no server needed): `python3 -m unittest tests.test_export -v` and `shellcheck deploy/*.sh`.
