"""Fetch the Discord bot's live.json (who's online + today's play time) for the page's live box.

The bot polls the game server every 30 s and serves the result over HTTP. Only the known fields are
copied, with their types checked, so a broken or hostile response can't put anything else on the page.
"""
import json
import urllib.request


def clean_live(data):
    """Return the expected live.json fields with checked types, or None if the shape is wrong."""
    try:
        today = data.get("today") or {}
        players = [str(n) for n in data["players"]][:100]
        return {
            "updated": str(data["updated"]),
            "online": bool(data["online"]),
            "players": players,
            "count": len(players),
            "today": {
                "players": {str(n): int(s) for n, s in list((today.get("players") or {}).items())[:100]},
                "peak": int(today.get("peak") or 0),
                "peak_time": None if today.get("peak_time") is None else str(today["peak_time"]),
            },
        }
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def fetch_live(url, timeout=3):
    """live.json text ready to write, or None if the bot can't be reached or answers nonsense."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read(64 * 1024).decode("utf-8"))
    except (OSError, ValueError):
        return None
    cleaned = clean_live(data) if isinstance(data, dict) else None
    return None if cleaned is None else json.dumps(cleaned) + "\n"
