"""Tests for mcstats.stats.load_players, using the fake players in tests/fixtures/."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mcstats.stats import load_players

FIXTURES = Path(__file__).parent / "fixtures"
OTTER = "3f9c2a71-8d4e-4b6a-9c15-7e2d0b8a4f63"
FAKE_UUID = "00000000-0000-4000-8000-000000000000"  # made up, not in usercache


def by_name(players):
    return {p["name"]: p for p in players}


class LoadPlayersTests(unittest.TestCase):
    def setUp(self):
        self.players = by_name(load_players(FIXTURES))

    def test_each_player_has_name_hours_deaths_mob_kills_and_kills(self):
        self.assertEqual(set(self.players), {"CraftyOtter", "PixelMoth", "NewbieNova"})
        otter = self.players["CraftyOtter"]
        self.assertEqual(otter["uuid"], OTTER)
        self.assertEqual(otter["deaths"], 7)
        self.assertEqual(otter["mob_kills"], 55)
        self.assertEqual(otter["kills"], {"minecraft:zombie": 40, "minecraft:skeleton": 12, "minecraft:creeper": 3})
        moth = self.players["PixelMoth"]
        self.assertEqual(moth["deaths"], 2)
        self.assertEqual(moth["mob_kills"], 50)
        self.assertEqual(moth["kills"]["minecraft:skeleton"], 30)

    def test_hours_are_ticks_divided_by_72000(self):
        self.assertAlmostEqual(self.players["CraftyOtter"]["hours"], 18.0)  # 1,296,000 ticks
        self.assertAlmostEqual(self.players["PixelMoth"]["hours"], 6.0)  # 432,000 ticks
        self.assertAlmostEqual(self.players["NewbieNova"]["hours"], 2400 / 72000)

    def test_missing_sections_mean_zero(self):
        nova = self.players["NewbieNova"]
        self.assertEqual(nova["deaths"], 0)
        self.assertEqual(nova["mob_kills"], 0)
        self.assertEqual(nova["kills"], {})

    def test_missing_custom_section_means_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats_dir = Path(tmp) / "world" / "players" / "stats"
            stats_dir.mkdir(parents=True)
            (stats_dir / (FAKE_UUID + ".json")).write_text(json.dumps({"stats": {}, "DataVersion": 4556}))
            [p] = load_players(tmp)
        self.assertEqual((p["hours"], p["deaths"], p["mob_kills"], p["kills"]), (0, 0, 0, {}))

    def test_player_not_in_usercache_is_labelled_by_uuid(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIXTURES / "world", Path(tmp) / "world")
            shutil.copy(FIXTURES / "usercache.json", tmp)
            stats_dir = Path(tmp) / "world" / "players" / "stats"
            shutil.copy(stats_dir / (OTTER + ".json"), stats_dir / (FAKE_UUID + ".json"))
            players = by_name(load_players(tmp))
        self.assertIn("CraftyOtter", players)
        self.assertEqual(players[FAKE_UUID]["uuid"], FAKE_UUID)
        self.assertEqual(players[FAKE_UUID]["deaths"], 7)

    def test_missing_usercache_labels_everyone_by_uuid(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIXTURES / "world", Path(tmp) / "world")
            players = load_players(tmp)
        self.assertEqual(len(players), 3)
        for p in players:
            self.assertEqual(p["name"], p["uuid"])

    def test_server_dir_comes_from_mc_server_dir(self):
        with mock.patch.dict(os.environ, {"MC_SERVER_DIR": str(FIXTURES)}):
            players = by_name(load_players())
        self.assertEqual(players["CraftyOtter"]["deaths"], 7)

    def test_unset_mc_server_dir_raises_clear_error(self):
        env = {k: v for k, v in os.environ.items() if k != "MC_SERVER_DIR"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "MC_SERVER_DIR"):
                load_players()


if __name__ == "__main__":
    unittest.main()
