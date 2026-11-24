#!/usr/bin/env bash
# Copies the player files out of the Minecraft container (CT 100) into /srv/mc-export.
# Runs as root on the Proxmox host, every minute, from mc-export.timer. See deploy/README.md.
# It only ever runs `tar -c` (read) inside the container, so the game server is never changed.
set -euo pipefail

# Production defaults; the tests override these with fakes.
CTID="${CTID:-100}"
MC_DIR="${MC_DIR:-/opt/minecraft}"
STAGING="${STAGING:-/var/tmp/mc-export-staging}"
EXPORT_DIR="${EXPORT_DIR:-/srv/mc-export}"
PCT="${PCT:-pct}"

# This script deletes the staging folder, so refuse an empty path or "/" (also "//" etc.).
for dir in "$STAGING" "$EXPORT_DIR"; do
  if [[ -z "${dir//\//}" ]]; then
    echo "export.sh: refusing to use '$dir' as a folder" >&2
    exit 2
  fi
done

# Start from an empty staging folder, so files deleted on the server don't linger here.
rm -rf -- "$STAGING"
mkdir -p -- "$STAGING"

# Only these three items. Never logs/: log lines contain player IP addresses.
# --no-same-owner: copies are owned by host root, not the container's user id.
# set +e so we can read both exit codes from PIPESTATUS instead of stopping at the first failure.
set +e
"$PCT" exec "$CTID" -- tar -C "$MC_DIR" -cf - usercache.json world/players/stats world/players/advancements \
  | tar -C "$STAGING" --no-same-owner -xf -
codes=("${PIPESTATUS[@]}")
set -e

# GNU tar exits 1 when a file changed while being read (an autosave mid-copy): only a warning,
# the leaderboard build skips half-written JSON. Anything worse: stop and keep the last good export.
# Exit 1 only counts as that warning if the unpack also worked: pct itself can exit 1 on errors too.
if [[ "${codes[1]}" -ne 0 || "${codes[0]}" -gt 1 ]]; then
  echo "export.sh: copy failed (pct/tar exit ${codes[0]}, unpack exit ${codes[1]}); export left unchanged" >&2
  exit 1
elif [[ "${codes[0]}" -eq 1 ]]; then
  echo "export.sh: warning: a file changed while it was copied; it will be fresh next minute" >&2
fi

# An empty stream can unpack "successfully" into nothing; never let that wipe the export.
if [[ ! -f "$STAGING/usercache.json" ]]; then
  echo "export.sh: copy is missing usercache.json; export left unchanged" >&2
  exit 1
fi

# Readable by everyone (the website's non-root user), whatever umask the server used.
chmod -R a+rX "$STAGING"

# rsync replaces each file via temp name + rename and keeps the same folder, so the bind mount stays valid.
mkdir -p -- "$EXPORT_DIR"
rsync -a --delete "$STAGING"/ "$EXPORT_DIR"/
