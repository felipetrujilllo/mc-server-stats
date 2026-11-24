"""Render the leaderboard HTML page and write it atomically."""
import os
import tempfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path

# Our own 16x16 dirt-style pixel tile (not Mojang's texture file), inlined so the page stays one file.
DIRT = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' shape-rendering='crispEdges'>"
        "<rect width='16' height='16' fill='%23866043'/>"
        "<g fill='%23593d29'><rect x='1' y='1' width='2' height='1'/><rect x='6' y='2' width='1' height='2'/>"
        "<rect x='11' y='1' width='2' height='1'/><rect x='3' y='6' width='2' height='1'/><rect x='9' y='5' width='1' height='1'/>"
        "<rect x='13' y='7' width='2' height='1'/><rect x='0' y='10' width='1' height='2'/><rect x='6' y='9' width='2' height='1'/>"
        "<rect x='10' y='12' width='2' height='1'/><rect x='3' y='13' width='1' height='2'/><rect x='14' y='13' width='1' height='1'/></g>"
        "<g fill='%23b9855c'><rect x='4' y='3' width='1' height='1'/><rect x='14' y='3' width='1' height='1'/>"
        "<rect x='8' y='7' width='1' height='1'/><rect x='1' y='8' width='1' height='1'/><rect x='12' y='10' width='1' height='1'/>"
        "<rect x='5' y='11' width='1' height='1'/><rect x='8' y='14' width='1' height='1'/></g>"
        "<g fill='%2379553a'><rect x='8' y='0' width='2' height='1'/><rect x='0' y='4' width='1' height='1'/>"
        "<rect x='11' y='4' width='1' height='2'/><rect x='5' y='8' width='1' height='1'/><rect x='15' y='10' width='1' height='1'/>"
        "<rect x='1' y='14' width='1' height='1'/><rect x='12' y='15' width='2' height='1'/></g></svg>")

# dirt.png = the real texture, copied by hand next to index.html (Mojang's asset: never commit it).
# grass_block_side.png, sun.png and stone.png (title letters, logo-style): same, from the same jar. If dirt.png is missing, the drawn DIRT tile underneath shows instead.
# Monocraft.otf (text) + Monocraft-Black.otf (titles) = a Minecraft-style font (OFL, github.com/IdreesInc/Monocraft), also copied by hand; falls back to monospace.
# Layers top to bottom: sun (black bg screened away, as the game does), sky strip, one row of grass blocks, then dirt (64px grid, so grass sits on whole tiles).
# 8x6 pixel crown drawn for this page, shown before each first-place name.
CROWN = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 8 6' shape-rendering='crispEdges'>"
         "<g fill='%23f7c32e'><rect x='0' width='1' height='5'/><rect x='7' width='1' height='5'/><rect x='3' width='2' height='5'/>"
         "<rect x='2' y='1' width='4' height='4'/><rect x='1' y='2' width='6' height='3'/></g>"
         "<rect y='5' width='8' height='1' fill='%23c8901a'/><g fill='%23e0303a'><rect x='1' y='3' width='1' height='1'/>"
         "<rect x='6' y='3' width='1' height='1'/></g><rect x='3' y='3' width='2' height='1' fill='%2338c8e0'/></svg>")

CSS = """html{background:url(sun.png) right 64px top 0/128px no-repeat,linear-gradient(#78a7ff,#78a7ff) 0 0/100%% 128px no-repeat,url(grass_block_side.png) 0 128px/64px repeat-x,
url(dirt.png) 0 0/64px,url("%s") 0 0/64px;image-rendering:pixelated;
background-blend-mode:screen,normal,normal,normal,normal}
body{font-family:Monocraft,monospace;margin:0 0 2rem}
main{box-sizing:border-box;max-width:64rem;margin:96px auto 0;padding:16px;display:grid;grid-template-columns:1fr 1fr;gap:20px;
/* pixel corners: outline drawn by 4 one-axis shadows, so each corner pixel stays empty (stepped look) */
background:#7a3b22;box-shadow:inset 0 0 0 4px #a0522d,0 -6px #3b1a0e,0 6px #3b1a0e,-6px 0 #3b1a0e,6px 0 #3b1a0e}""" % DIRT + """
/* book look: leather cover (main), two cream pages, red stitching down the spine */
.page{padding:.5rem 1.5rem 1rem;background:#f6efd9;box-shadow:inset 0 0 0 4px #dccfae}
.page:first-child{border-right:4px dashed #b8262c}.page:last-child{border-left:4px dashed #b8262c}
@media(max-width:700px){main{grid-template-columns:1fr}.page{border:0!important}}
h2{margin:1rem 0 .5rem;padding:.3rem;text-align:center;font:900 1.1rem Monocraft,monospace;color:#f3e9dc;text-shadow:2px 2px #3e2418;
background:#8a5a44;box-shadow:inset 0 -4px #6b4232,0 -3px #3e2418,0 3px #3e2418,-3px 0 #3e2418,3px 0 #3e2418}
@font-face{font-family:Monocraft;font-weight:400;src:url(Monocraft.otf)}@font-face{font-family:Monocraft;font-weight:900;src:url(Monocraft-Black.otf)}
h1{margin:0;text-align:center;text-transform:uppercase;font-size:min(3.5rem,5.5vw);white-space:nowrap;line-height:128px;font-family:Monocraft,monospace;font-weight:900;
color:transparent;background:linear-gradient(#fff7,#fff7),url(stone.png) 0 0/32px,#a9a4a1;-webkit-background-clip:text;background-clip:text;
/* logo look: 4 chained 2px drops = deep dark 3D side, then a black outline */
filter:drop-shadow(0 2px 0 #3c3c3c) drop-shadow(0 2px 0 #333) drop-shadow(0 2px 0 #2a2a2a) drop-shadow(0 2px 0 #222) drop-shadow(2px 0 0 #000) drop-shadow(-2px 0 0 #000) drop-shadow(0 2px 0 #000) drop-shadow(0 -2px 0 #000)}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:.3rem .5rem;border-bottom:1px solid #dccfae}
td.n{text-align:right}
td.top::before{content:"";display:inline-block;width:16px;height:12px;margin-right:.4rem;vertical-align:-1px;background:url(\"""" + CROWN + """\") 0 0/100%}"""


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


def table(headers, rows, crown=False):
    """crown=True: rows sorted best first; every row tied for the top value (if above 0) gets a crown."""
    head = "".join("<th>{}</th>".format(h) for h in headers)
    top = rows[0][-1] if crown and rows else 0
    body = "".join(
        "<tr>" + "".join('<td class="n">{}</td>'.format(c) if isinstance(c, (int, float))
                         else '<td class="top">{}</td>'.format(escape(c)) if i == 0 and top > 0 and row[-1] == top
                         else "<td>{}</td>".format(escape(c))
                         for i, c in enumerate(row)) + "</tr>\n"
        for row in rows
    )
    return "<table><tr>{}</tr>\n{}</table>".format(head, body)


def render_page(players, now=None):
    """Return the full HTML page. Every player and mob name is HTML-escaped."""
    now = now or datetime.now(timezone.utc)
    sections = [
        ("Most play time", table(["Player", "Hours"], [(p["name"], round(p["hours"], 1)) for p in ranked(players, "hours")], crown=True)),
        ("Most deaths", table(["Player", "Deaths"], [(p["name"], p["deaths"]) for p in ranked(players, "deaths")], crown=True)),
        ("Most mob kills", table(["Player", "Mob kills"], [(p["name"], p["mob_kills"]) for p in ranked(players, "mob_kills")], crown=True)),
        ("Most advancements", table(["Player", "Advancements"], [(p["name"], p["advancements"]) for p in ranked(players, "advancements")], crown=True)),
        ("Top killer per mob", table(["Mob", "Player", "Kills"], top_killers(players))),
    ]
    boards = ['<section><h2>{}</h2>\n{}</section>'.format(title, t) for title, t in sections]
    # Two book pages: first three boards on the left, the rest on the right.
    body = '<div class="page">\n<p>Last updated {}</p>\n{}\n</div>\n<div class="page">\n{}\n</div>'.format(
        now.strftime("%Y-%m-%d %H:%M UTC"), "\n".join(boards[:3]), "\n".join(boards[3:]))
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
<main>
{body}
</main>
</body>
</html>
""".format(css=CSS, body=body)


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
