"""Command line: python3 -m mcstats build --out <folder>"""
import argparse
import sys

from mcstats.page import render_page, write_page
from mcstats.stats import load_players


def main():
    parser = argparse.ArgumentParser(prog="mcstats")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="write <out>/index.html from the server in MC_SERVER_DIR")
    build.add_argument("--out", required=True, help="folder to write index.html into")
    args = parser.parse_args()
    try:
        players = load_players()
    except (RuntimeError, FileNotFoundError) as e:
        sys.exit("error: {}".format(e))
    write_page(args.out, render_page(players))


if __name__ == "__main__":
    main()
