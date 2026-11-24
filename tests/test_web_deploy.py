"""Tests for deploy/web/ (ticket #7): the unit files agree with each other and the guide,
and their exact commands build and serve the page locally."""
import configparser
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "deploy" / "web"
FIXTURES = Path(__file__).parent / "fixtures"
EXPORT, OUT, PORT = "/srv/mc-export", "/var/www/mcstats", "8080"


def unit(name):
    # strict=False: systemd allows repeated keys; interpolation off: units may contain '%'.
    p = configparser.ConfigParser(strict=False, interpolation=None)
    p.optionxform = str  # keep key case (ExecStart, not execstart)
    p.read(WEB / name, encoding="utf-8")
    return p


BUILD, TIMER, SERVE = unit("mcstats-build.service"), unit("mcstats-build.timer"), unit("mcstats-web.service")
GUIDE = (WEB / "README.md").read_text(encoding="utf-8")


def build_env():
    return dict(line.split("=", 1) for line in BUILD["Service"]["Environment"].split())


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class UnitFilesTest(unittest.TestCase):
    def test_build_service(self):
        s = BUILD["Service"]
        self.assertEqual(s["Type"], "oneshot")
        self.assertEqual(s["User"], "mcstats")
        self.assertEqual(build_env()["MC_SERVER_DIR"], EXPORT)
        self.assertEqual(shlex.split(s["ExecStart"]), ["/usr/bin/python3", "-m", "mcstats", "build", "--out", OUT])
        self.assertIn(OUT, s["ReadWritePaths"].split())  # ProtectSystem=strict would block the write otherwise

    def test_build_timer(self):
        t = TIMER["Timer"]
        self.assertEqual(t["OnBootSec"], "1min")
        self.assertEqual(t["OnUnitActiveSec"], "1min")
        self.assertEqual(TIMER["Install"]["WantedBy"], "timers.target")

    def test_web_service(self):
        s = SERVE["Service"]
        self.assertEqual(s["User"], "mcstats")
        self.assertEqual(shlex.split(s["ExecStart"]),
                         ["/usr/bin/python3", "-m", "http.server", PORT, "--directory", OUT])
        self.assertNotIn("ReadWritePaths", s)  # serving only reads
        self.assertEqual(SERVE["Install"]["WantedBy"], "multi-user.target")


class PathsConsistentTest(unittest.TestCase):
    def test_served_dir_is_build_output(self):
        out = shlex.split(BUILD["Service"]["ExecStart"])[-1]
        served = shlex.split(SERVE["Service"]["ExecStart"])[-1]
        self.assertEqual(out, served)

    def test_working_dir_is_clone_path(self):
        clone = re.search(r"^git clone \S+ (\S+)$", GUIDE, re.M)
        self.assertIsNotNone(clone, "guide has no `git clone <url> <dir>` line")
        self.assertEqual(clone.group(1), BUILD["Service"]["WorkingDirectory"])

    def test_mount_is_server_dir_and_read_only(self):
        m = re.search(r"^pct set 101 -mp0 (\S+)$", GUIDE, re.M)
        self.assertIsNotNone(m, "guide has no `pct set 101 -mp0 ...` line")
        source, *opts = m.group(1).split(",")
        opts = dict(o.split("=", 1) for o in opts)
        self.assertEqual(opts["mp"], build_env()["MC_SERVER_DIR"])
        self.assertEqual(source, EXPORT)
        self.assertEqual(opts["ro"], "1")

    def test_no_ipv4_addresses(self):
        for p in WEB.iterdir():
            self.assertIsNone(re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", p.read_text(encoding="utf-8")), p.name)


class EndToEndTest(unittest.TestCase):
    """Runs the units' own ExecStart lines, with temp dirs and a free port swapped in."""

    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        self.export, self.out = tmp / "export", tmp / "www"
        shutil.copytree(FIXTURES, self.export)
        self.out.mkdir()
        self.port = str(free_port())

    def cmd(self, cfg):
        args = shlex.split(cfg["Service"]["ExecStart"])
        swap = {"/usr/bin/python3": sys.executable, OUT: str(self.out), PORT: self.port}
        return [swap.get(a, a) for a in args]

    def test_build_then_serve(self):
        env = {**build_env(), "MC_SERVER_DIR": str(self.export)}
        subprocess.run(self.cmd(BUILD), cwd=ROOT, env=env, check=True, timeout=30)
        self.assertTrue((self.out / "index.html").is_file())

        server = subprocess.Popen(self.cmd(SERVE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(server.wait, 5)
        self.addCleanup(server.terminate)
        url = "http://127.0.0.1:{}/".format(self.port)
        deadline = time.monotonic() + 5
        while True:
            try:
                with urllib.request.urlopen(url, timeout=1) as r:
                    status, body = r.status, r.read().decode("utf-8")
                break
            except OSError:
                if time.monotonic() > deadline or server.poll() is not None:
                    raise
                time.sleep(0.1)
        self.assertEqual(status, 200)
        for name in ("CraftyOtter", "PixelMoth", "NewbieNova"):
            self.assertIn(name, body)


if __name__ == "__main__":
    unittest.main()
