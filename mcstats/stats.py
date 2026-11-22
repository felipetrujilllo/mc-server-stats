"""Read each player's stats file into plain dicts for the leaderboard."""
import json
import os
import sys
from pathlib import Path

TICKS_PER_HOUR = 72000  # 20 ticks/second * 3600 seconds


def count_advancements(advancements):
    """Count finished real advancements, skipping recipe unlocks and the DataVersion key."""
    return sum(
        1 for key, value in advancements.items()
        if key != "DataVersion"
        and not key.startswith("minecraft:recipes/")
        and isinstance(value, dict)
        and value.get("done") is True
    )


def load_players(server_dir=None):
    """Return one dict per stats file in <server_dir>/world/players/stats/.

    server_dir defaults to the MC_SERVER_DIR environment variable.
    """
    if server_dir is None:
        server_dir = os.environ.get("MC_SERVER_DIR")
        if not server_dir:
            raise RuntimeError("MC_SERVER_DIR is not set: point it at the Minecraft server folder")
    server_dir = Path(server_dir)

    names = {}
    cache_path = server_dir / "usercache.json"
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            names = {e["uuid"]: e["name"] for e in json.load(f)}

    stats_dir = server_dir / "world" / "players" / "stats"
    if not stats_dir.is_dir():
        # An empty leaderboard would hide a wrong MC_SERVER_DIR, so fail loudly.
        raise FileNotFoundError("no stats folder at {}: is MC_SERVER_DIR the server folder?".format(stats_dir))
    adv_dir = server_dir / "world" / "players" / "advancements"
    players = []
    for path in sorted(stats_dir.glob("*.json")):
        uuid = path.stem
        adv_path = adv_dir / path.name
        try:
            with open(path, encoding="utf-8") as f:
                stats = json.load(f).get("stats", {})
            advancements = 0  # a player can have stats but no advancements file yet
            if adv_path.exists():
                with open(adv_path, encoding="utf-8") as f:
                    advancements = count_advancements(json.load(f))
        except ValueError as e:
            # The server may be mid-autosave; this player is picked up on the next build.
            print("warning: skipping {} (unreadable JSON: {})".format(f.name, e), file=sys.stderr)
            continue
        custom = stats.get("minecraft:custom", {})  # missing sections/keys mean zero
        players.append({
            "uuid": uuid,
            "name": names.get(uuid, uuid),
            "hours": custom.get("minecraft:play_time", 0) / TICKS_PER_HOUR,
            "deaths": custom.get("minecraft:deaths", 0),
            "mob_kills": custom.get("minecraft:mob_kills", 0),
            "kills": stats.get("minecraft:killed", {}),
            "advancements": advancements,
        })
    return players
