"""Read each player's stats file into plain dicts for the leaderboard."""
import json
import os
from pathlib import Path

TICKS_PER_HOUR = 72000  # 20 ticks/second * 3600 seconds


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

    players = []
    for path in sorted((server_dir / "world" / "players" / "stats").glob("*.json")):
        uuid = path.stem
        with open(path, encoding="utf-8") as f:
            stats = json.load(f).get("stats", {})
        custom = stats.get("minecraft:custom", {})  # missing sections/keys mean zero
        players.append({
            "uuid": uuid,
            "name": names.get(uuid, uuid),
            "hours": custom.get("minecraft:play_time", 0) / TICKS_PER_HOUR,
            "deaths": custom.get("minecraft:deaths", 0),
            "mob_kills": custom.get("minecraft:mob_kills", 0),
            "kills": stats.get("minecraft:killed", {}),
        })
    return players
