"""Render the leaderboard HTML page and write it atomically."""
import os
import tempfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path

CSS = """body{font-family:system-ui,sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:.3rem .5rem;border-bottom:1px solid #ccc}
td.n{text-align:right}"""


def ranked(players, key):
    """Highest first; ties broken by name so the page is stable between builds."""
    return sorted(players, key=lambda p: (-p[key], p["name"]))


def top_killers(players):
    """One (mob, player name, count) row per mob anyone has killed, highest count first."""
    best = {}
    for p in sorted(players, key=lambda p: p["name"]):
        for mob, count in p["kills"].items():
            if count > 0 and count > best.get(mob, (None, 0))[1]:
                best[mob] = (p["name"], count)
    rows = [(mob.replace("minecraft:", "").replace("_", " "), name, count) for mob, (name, count) in best.items()]
    return sorted(rows, key=lambda r: (-r[2], r[0]))


def table(headers, rows):
    head = "".join("<th>{}</th>".format(h) for h in headers)
    body = "".join(
        "<tr>" + "".join('<td class="n">{}</td>'.format(c) if isinstance(c, (int, float)) else "<td>{}</td>".format(escape(c))
                         for c in row) + "</tr>\n"
        for row in rows
    )
    return "<table><tr>{}</tr>\n{}</table>".format(head, body)


def render_page(players, now=None):
    """Return the full HTML page. Every player and mob name is HTML-escaped."""
    now = now or datetime.now(timezone.utc)
    sections = [
        ("Most play time", table(["Player", "Hours"], [(p["name"], round(p["hours"], 1)) for p in ranked(players, "hours")])),
        ("Most deaths", table(["Player", "Deaths"], [(p["name"], p["deaths"]) for p in ranked(players, "deaths")])),
        ("Most mob kills", table(["Player", "Mob kills"], [(p["name"], p["mob_kills"]) for p in ranked(players, "mob_kills")])),
        ("Most advancements", table(["Player", "Advancements"], [(p["name"], p["advancements"]) for p in ranked(players, "advancements")])),
        ("Top killer per mob", table(["Mob", "Player", "Kills"], top_killers(players))),
    ]
    body = "\n".join('<section><h2>{}</h2>\n{}</section>'.format(title, t) for title, t in sections)
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Server leaderboard</title>
<style>{css}</style>
</head>
<body>
<h1>Server leaderboard</h1>
<p>Last updated {updated}</p>
{body}
</body>
</html>
""".format(css=CSS, updated=now.strftime("%Y-%m-%d %H:%M UTC"), body=body)


def write_page(out_dir, html):
    """Write out_dir/index.html via a temp file + rename, so readers never see a half-written page."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out_dir, prefix=".index-", suffix=".tmp")  # same folder: rename stays atomic
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        os.chmod(tmp, 0o644)  # mkstemp makes 0600; the web server user must be able to read it
        os.replace(tmp, out_dir / "index.html")
    except BaseException:
        os.unlink(tmp)
        raise
