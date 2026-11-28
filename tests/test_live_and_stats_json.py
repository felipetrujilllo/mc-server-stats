"""Tests for stats.json (read by the Discord bot) and live.json (copied from the bot by each build)."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mcstats.live import clean_live, fetch_live
from mcstats.page import render_page, render_stats_json
from mcstats.stats import load_players

FIXTURES = (Path(__file__).parent / "fixtures").resolve()
REPO = Path(__file__).parent.parent.resolve()
LIVE = {"updated": "2026-11-28T02:00:00+00:00", "online": True, "players": ["CraftyOtter"], "count": 1,
        "today": {"players": {"CraftyOtter": 600}, "peak": 1, "peak_time": "01:30"}}


def serve_json(test, body, status=200):
    """Start a throwaway HTTP server that answers every GET with body; return its URL."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *a):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    test.addCleanup(server.server_close)
    test.addCleanup(server.shutdown)
    return "http://127.0.0.1:{}/live.json".format(server.server_address[1])


class StatsJsonTests(unittest.TestCase):
    def setUp(self):
        self.players = load_players(FIXTURES)
        self.stats = json.loads(render_stats_json(self.players))

    def test_same_boards_as_page_in_same_order(self):
        html = render_page(self.players)
        titles = [b["title"] for b in self.stats["boards"]]
        self.assertEqual(len(titles), 5)
        self.assertEqual(sorted(titles, key=html.index), titles)

    def test_rows_are_player_then_value_highest_first(self):
        play = self.stats["boards"][0]
        self.assertEqual(play["unit"], "hours")
        values = [r[-1] for r in play["rows"]]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertTrue(all(len(r) == 2 for r in play["rows"]))

    def test_per_mob_rows_put_player_first(self):
        mobs = self.stats["boards"][-1]
        names = {p["name"] for p in self.players}
        self.assertTrue(mobs["rows"])
        for player, mob, kills in mobs["rows"]:
            self.assertIn(player, names)
            self.assertNotIn("minecraft:", mob)
            self.assertIsInstance(kills, int)

    def test_has_utc_timestamp(self):
        self.assertRegex(self.stats["updated"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


class CleanLiveTests(unittest.TestCase):
    def test_keeps_known_fields(self):
        self.assertEqual(clean_live(LIVE), LIVE)

    def test_drops_unknown_fields_and_recounts(self):
        cleaned = clean_live({**LIVE, "count": 99, "evil": "<script>"})
        self.assertNotIn("evil", cleaned)
        self.assertEqual(cleaned["count"], 1)

    def test_wrong_shape_is_none(self):
        for bad in ({}, {"updated": "x", "online": True, "players": 5}, {**LIVE, "today": {"players": {"a": "x"}}}):
            self.assertIsNone(clean_live(bad), bad)


class FetchLiveTests(unittest.TestCase):
    def test_fetches_and_cleans(self):
        self.assertEqual(json.loads(fetch_live(serve_json(self, json.dumps(LIVE)))), LIVE)

    def test_bot_down_or_garbage_is_none(self):
        self.assertIsNone(fetch_live("http://127.0.0.1:9/live.json", timeout=1))
        self.assertIsNone(fetch_live(serve_json(self, "not json")))
        self.assertIsNone(fetch_live(serve_json(self, "{}", status=500)))


class BuildWritesJsonTests(unittest.TestCase):
    def build(self, out, **env):
        return subprocess.run([sys.executable, "-m", "mcstats", "build", "--out", out], cwd=REPO,
                              env=dict(os.environ, MC_SERVER_DIR=str(FIXTURES), **env), capture_output=True, text=True)

    def test_build_writes_stats_json_and_no_live_json_without_live_url(self):
        env = {k: v for k, v in os.environ.items() if k != "LIVE_URL"}
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, "-m", "mcstats", "build", "--out", tmp], cwd=REPO,
                               env=dict(env, MC_SERVER_DIR=str(FIXTURES)), capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(len(json.loads((Path(tmp) / "stats.json").read_text())["boards"]), 5)
            self.assertFalse((Path(tmp) / "live.json").exists())
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["index.html", "stats.json"])

    def test_build_copies_live_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.build(tmp, LIVE_URL=serve_json(self, json.dumps(LIVE)))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads((Path(tmp) / "live.json").read_text()), LIVE)

    def test_bot_down_keeps_old_live_json_and_still_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "live.json").write_text("old")
            r = self.build(tmp, LIVE_URL="http://127.0.0.1:9/live.json")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("no live data", r.stderr)
            self.assertEqual((Path(tmp) / "live.json").read_text(), "old")
            self.assertTrue((Path(tmp) / "index.html").exists())

    def test_page_has_hidden_live_box(self):
        html = render_page(load_players(FIXTURES))
        self.assertIn('<aside class="live" id="live" hidden></aside>', html)
        self.assertIn('fetch("live.json"', html)
        self.assertNotIn("innerHTML", html)


if __name__ == "__main__":
    unittest.main()
