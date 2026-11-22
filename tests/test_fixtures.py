"""Sanity checks for the fake fixtures in tests/fixtures/ (made-up players only)."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).parent.parent
STATS = FIXTURES / "world" / "players" / "stats"
ADV = FIXTURES / "world" / "players" / "advancements"
NAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def uuid_of(name):
    return next(e["uuid"] for e in load(FIXTURES / "usercache.json") if e["name"] == name)


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.cache = load(FIXTURES / "usercache.json")

    def test_usercache_has_three_valid_players(self):
        self.assertIsInstance(self.cache, list)
        self.assertEqual(len(self.cache), 3)
        for entry in self.cache:
            self.assertEqual(set(entry), {"uuid", "name", "expiresOn"})
            self.assertRegex(entry["name"], NAME_RE)
        self.assertEqual(len({e["uuid"] for e in self.cache}), 3)

    def test_each_player_has_stats_and_advancements(self):
        for entry in self.cache:
            stats = load(STATS / (entry["uuid"] + ".json"))
            self.assertIsInstance(stats["stats"], dict)
            self.assertIn("DataVersion", stats)
            adv = load(ADV / (entry["uuid"] + ".json"))
            self.assertIn("DataVersion", adv)

    def test_new_player_has_no_killed_or_mined(self):
        stats = load(STATS / (uuid_of("NewbieNova") + ".json"))["stats"]
        self.assertNotIn("minecraft:killed", stats)
        self.assertNotIn("minecraft:mined", stats)
        self.assertNotIn("minecraft:killed_by", stats)

    def test_mid_player_has_two_real_and_five_recipe_advancements(self):
        adv = load(ADV / (uuid_of("PixelMoth") + ".json"))
        done = [k for k, v in adv.items() if k != "DataVersion" and v["done"]]
        recipes = [k for k in done if k.startswith("minecraft:recipes/")]
        self.assertEqual(len(done) - len(recipes), 2)
        self.assertEqual(len(recipes), 5)

    def test_fixture_usercache_not_gitignored(self):
        if shutil.which("git") is None:
            self.skipTest("git not available")
        result = subprocess.run(
            ["git", "check-ignore", "-q", "tests/fixtures/usercache.json"], cwd=REPO
        )
        self.assertEqual(result.returncode, 1, "fixture usercache.json is git-ignored")

    def test_only_fake_names_and_no_ips(self):
        # Allow-list, not a deny-list: listing real names here would publish them.
        names = {e["name"] for e in self.cache}
        self.assertEqual(names, {"CraftyOtter", "PixelMoth", "NewbieNova"})
        ipv4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
        for path in FIXTURES.rglob("*"):
            if path.is_file():
                self.assertIsNone(ipv4.search(path.read_text(encoding="utf-8")), str(path))


if __name__ == "__main__":
    unittest.main()
