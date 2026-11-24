"""Tests for the leaderboard page (mcstats.page) and the build command, using fake fixtures."""
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mcstats.page import render_page, write_page
from mcstats.stats import load_players

FIXTURES = (Path(__file__).parent / "fixtures").resolve()
REPO = Path(__file__).parent.parent.resolve()
NAMES = ["CraftyOtter", "PixelMoth", "NewbieNova"]


def section(html, title):
    """The HTML of one board, from its <h2> to the end of its <section>."""
    match = re.search(r"<h2>{}</h2>(.*?)</section>".format(re.escape(title)), html, re.S)
    assert match, title
    return match.group(1)


def name_order(html):
    return sorted((n for n in NAMES if n in html), key=html.index)


def rows(html):
    return [re.findall(r"<td[^>]*>(.*?)</td>", r) for r in re.findall(r"<tr>(.*?)</tr>", html)][1:]


class ServeCommandTests(unittest.TestCase):
    def test_serve_builds_fresh_page_on_each_load(self):
        import socket, time, urllib.request
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.Popen(
                [sys.executable, "-m", "mcstats", "serve", "--out", tmp, "--port", str(port)],
                cwd=REPO, env=dict(os.environ, MC_SERVER_DIR=str(FIXTURES)),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.addCleanup(proc.wait)
            self.addCleanup(proc.terminate)
            url = "http://127.0.0.1:{}/".format(port)
            for _ in range(50):
                try:
                    body = urllib.request.urlopen(url, timeout=2).read().decode()
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                self.fail("serve never answered")
            for name in NAMES:  # the folder started empty, so the GET itself built the page
                self.assertIn(name, body)
            (Path(tmp) / "index.html").write_text("stale")
            self.assertIn("CraftyOtter", urllib.request.urlopen(url, timeout=2).read().decode())


class BuildCommandTests(unittest.TestCase):
    def run_build(self, env, out):
        return subprocess.run([sys.executable, "-m", "mcstats", "build", "--out", out],
                              cwd=REPO, env=env, capture_output=True, text=True)

    def test_build_writes_index_html_with_all_players(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_build(dict(os.environ, MC_SERVER_DIR=str(FIXTURES)), tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            html = (Path(tmp) / "index.html").read_text(encoding="utf-8")
        for name in NAMES:
            self.assertIn(name, html)

    def test_build_without_mc_server_dir_fails_with_message(self):
        env = {k: v for k, v in os.environ.items() if k != "MC_SERVER_DIR"}
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_build(env, tmp)
            self.assertFalse((Path(tmp) / "index.html").exists())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MC_SERVER_DIR", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_build_with_wrong_folder_fails_with_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_build(dict(os.environ, MC_SERVER_DIR=tmp), str(Path(tmp) / "out"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stats", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class RenderPageTests(unittest.TestCase):
    def setUp(self):
        self.html = render_page(load_players(FIXTURES))

    def test_page_is_html5_with_charset_viewport_title_and_utc_time(self):
        self.assertTrue(self.html.startswith("<!DOCTYPE html>"))
        self.assertIn('<meta charset="utf-8">', self.html)
        self.assertIn('name="viewport"', self.html)
        self.assertIn("<title>", self.html)
        self.assertRegex(self.html, r"Last updated \d{4}-\d\d-\d\d \d\d:\d\d UTC")

    def test_play_time_highest_first_rounded_to_one_decimal(self):
        board = section(self.html, "Most play time")
        self.assertEqual(name_order(board), ["CraftyOtter", "PixelMoth", "NewbieNova"])  # 18h, 6h, 0.03h
        self.assertEqual([r[1] for r in rows(board)], ["18.0", "6.0", "0.0"])

    def test_deaths_highest_first(self):
        board = section(self.html, "Most deaths")
        self.assertEqual(name_order(board), ["CraftyOtter", "PixelMoth", "NewbieNova"])  # 7, 2, 0
        self.assertEqual([r[1] for r in rows(board)], ["7", "2", "0"])

    def test_mob_kills_highest_first(self):
        board = section(self.html, "Most mob kills")
        self.assertEqual(name_order(board), ["CraftyOtter", "PixelMoth", "NewbieNova"])  # 55, 50, 0

    def test_advancements_highest_first(self):
        board = section(self.html, "Most advancements")
        self.assertEqual(name_order(board), ["CraftyOtter", "PixelMoth", "NewbieNova"])  # 5, 2, 0

    def test_players_with_zero_still_listed(self):
        self.assertIn("NewbieNova", section(self.html, "Most deaths"))

    def test_top_killer_per_mob(self):
        board = rows(section(self.html, "Top killer per mob"))
        self.assertEqual(board, [
            ["zombie", "CraftyOtter", "40"],
            ["skeleton", "PixelMoth", "30"],
            ["spider", "PixelMoth", "15"],
            ["creeper", "CraftyOtter", "3"],
        ])

    def test_ties_broken_by_name_and_zero_kills_skipped(self):
        players = [
            {"name": "Zed_", "hours": 1.0, "deaths": 3, "mob_kills": 0, "advancements": 0,
             "kills": {"minecraft:zombie": 4, "minecraft:cave_spider": 0}},
            {"name": "Amy", "hours": 1.0, "deaths": 3, "mob_kills": 0, "advancements": 0,
             "kills": {"minecraft:zombie": 4}},
        ]
        html = render_page(players)
        self.assertLess(section(html, "Most deaths").index("Amy"), section(html, "Most deaths").index("Zed_"))
        self.assertEqual(rows(section(html, "Top killer per mob")), [["zombie", "Amy", "4"]])

    def test_crown_on_first_place_ties_share_it_and_zero_gets_none(self):
        self.assertEqual(re.findall(r'<td class="top">(.*?)</td>', section(self.html, "Most deaths")), ["CraftyOtter"])
        self.assertNotIn('class="top"', section(self.html, "Top killer per mob"))
        players = [
            {"name": "Amy", "hours": 2.0, "deaths": 0, "mob_kills": 0, "advancements": 0, "kills": {}},
            {"name": "Zed_", "hours": 2.0, "deaths": 0, "mob_kills": 0, "advancements": 0, "kills": {}},
        ]
        html = render_page(players)
        self.assertEqual(re.findall(r'<td class="top">(.*?)</td>', section(html, "Most play time")), ["Amy", "Zed_"])
        self.assertNotIn('class="top"', section(html, "Most deaths"))

    def test_names_are_html_escaped(self):
        players = [{"name": "<b>", "hours": 1.0, "deaths": 1, "mob_kills": 1, "advancements": 1,
                    "kills": {"minecraft:<i>": 2}}]
        html = render_page(players)
        self.assertIn("<td>&lt;b&gt;</td>", html)
        self.assertNotIn("<b>", html)
        self.assertNotIn("<i>", html)
        self.assertIn("&lt;i&gt;", html)


class WritePageTests(unittest.TestCase):
    def test_writes_index_and_leaves_no_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "new" / "site"  # created if missing
            write_page(out, "<p>hi</p>")
            self.assertEqual(os.listdir(out), ["index.html"])
            self.assertEqual((out / "index.html").read_text(encoding="utf-8"), "<p>hi</p>")

    def test_failed_swap_keeps_old_page_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_page(tmp, "old page")
            with mock.patch("mcstats.page.os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    write_page(tmp, "new page")
            self.assertEqual(os.listdir(tmp), ["index.html"])
            self.assertEqual((Path(tmp) / "index.html").read_text(encoding="utf-8"), "old page")

    def test_page_is_readable_by_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_page(tmp, "x")
            mode = os.stat(Path(tmp) / "index.html").st_mode
        self.assertTrue(mode & stat.S_IROTH)


if __name__ == "__main__":
    unittest.main()
