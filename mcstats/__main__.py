"""Command line: python3 -m mcstats build --out <folder>  |  python3 -m mcstats serve --out <folder> --port N"""
import argparse
import functools
import http.server
import os
import subprocess
import sys

from mcstats.live import fetch_live
from mcstats.page import render_page, render_stats_json, write_page
from mcstats.stats import load_players


def serve(out, port):
    """Dev preview: rebuild on every page load, so edits to the code show up on refresh."""
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                # A fresh process re-imports the code, so edits to page.py take effect.
                subprocess.run([sys.executable, "-m", "mcstats", "build", "--out", out])
            super().do_GET()

    print("serving http://localhost:{}/ (Ctrl+C to stop)".format(port), flush=True)
    handler = functools.partial(Handler, directory=out)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(prog="mcstats")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="write <out>/index.html + stats.json from the server in MC_SERVER_DIR "
                                          "(+ live.json from the Discord bot at LIVE_URL, if set)")
    build.add_argument("--out", required=True, help="folder to write index.html into")
    dev = sub.add_parser("serve", help="dev preview on localhost, rebuilt on every page load")
    dev.add_argument("--out", required=True, help="folder to build into and serve")
    dev.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "serve":
        return serve(args.out, args.port)
    try:
        players = load_players()
    except (RuntimeError, FileNotFoundError) as e:
        sys.exit("error: {}".format(e))
    write_page(args.out, render_page(players))
    write_page(args.out, render_stats_json(players), name="stats.json")
    live_url = os.environ.get("LIVE_URL")
    if live_url:
        live = fetch_live(live_url)
        if live is None:  # bot down: keep the old file; the page hides it once it is 3 minutes old
            print("warning: no live data from {}".format(live_url), file=sys.stderr)
        else:
            write_page(args.out, live, name="live.json")


if __name__ == "__main__":
    main()
