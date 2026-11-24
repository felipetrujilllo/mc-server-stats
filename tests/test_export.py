"""Tests for deploy/export.sh (ticket #6), run locally against a fake `pct` and a fake server dir."""
import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "deploy" / "export.sh"
FIXTURES = Path(__file__).parent / "fixtures"
FAKE_IP = "10.0.0.5"

# Fake `pct`: accepts only `exec <ctid> -- tar ...`, logs its args, then runs that tar locally.
FAKE_PCT = """#!/bin/bash
[ "$1" = exec ] && [ "$2" = 100 ] && [ "$3" = -- ] && [ "$4" = tar ] || { echo "fake pct: bad call: $*" >&2; exit 99; }
echo "$*" >> "$FAKE_PCT_LOG"
shift 3
# FAKE_PCT_STREAM simulates a broken copy: nothing at all, or bytes that aren't a tar archive.
case "${FAKE_PCT_STREAM:-}" in
  empty) exit "${FAKE_PCT_EXIT:-0}" ;;
  garbage) echo garbage; exit "${FAKE_PCT_EXIT:-0}" ;;
  # cut off mid-copy: usercache.json (packed first) arrives, the rest doesn't
  truncated) COPYFILE_DISABLE=1 "$@" | head -c 3000; exit "${FAKE_PCT_EXIT:-0}" ;;
esac
COPYFILE_DISABLE=1 "$@" || exit $?   # COPYFILE_DISABLE: stop macOS tar adding ._ metadata files
exit "${FAKE_PCT_EXIT:-0}"
"""


def snapshot(root):
    """(relative path, size, mtime, sha256) of every file under root."""
    out = set()
    for p in Path(root).rglob("*"):
        if p.is_file():
            st = p.stat()
            out.add((str(p.relative_to(root)), st.st_size, st.st_mtime_ns,
                     hashlib.sha256(p.read_bytes()).hexdigest()))
    return out


def files(root):
    return {str(p.relative_to(root)) for p in Path(root).rglob("*") if p.is_file()}


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.server = self.tmp / "server"
        shutil.copytree(FIXTURES, self.server)
        (self.server / "README.md").unlink()  # fixture docs, not part of a real server dir
        (self.server / "logs").mkdir()
        (self.server / "logs" / "latest.log").write_text(
            f"[12:00:00] [Server thread/INFO]: CraftyOtter[/{FAKE_IP}:5555] logged in\n")
        (self.server / "world" / "region").mkdir()
        (self.server / "world" / "region" / "r.0.0.mca").write_bytes(b"not a real region file")
        self.export = self.tmp / "export"
        self.log = self.tmp / "pct.log"
        pct = self.tmp / "pct"
        pct.write_text(FAKE_PCT)
        pct.chmod(0o755)
        self.env = dict(os.environ, PCT=str(pct), MC_DIR=str(self.server),
                        STAGING=str(self.tmp / "staging"), EXPORT_DIR=str(self.export),
                        FAKE_PCT_LOG=str(self.log))
        self.expected = {"usercache.json"} | {
            f"world/players/{d}/{p.name}" for d in ("stats", "advancements")
            for p in (FIXTURES / "world" / "players" / d).iterdir()}

    def run_export(self, **env):
        return subprocess.run(["/bin/bash", str(SCRIPT)], env={**self.env, **env},
                              capture_output=True, text=True)

    def assert_ok(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_copies_only_the_three_items(self):
        self.assert_ok(self.run_export())
        self.assertEqual(files(self.export), self.expected)
        for rel in self.expected:
            self.assertEqual((self.export / rel).read_bytes(), (self.server / rel).read_bytes(), rel)

    def test_never_copies_logs_or_other_world_files(self):
        self.assert_ok(self.run_export())
        self.assertFalse((self.export / "logs").exists())
        self.assertFalse((self.export / "world" / "region").exists())
        for p in self.export.rglob("*"):
            if p.is_file():
                self.assertNotIn(FAKE_IP.encode(), p.read_bytes(), p)

    def test_running_twice_gives_same_result(self):
        self.assert_ok(self.run_export())
        first = {(f, (self.export / f).read_bytes()) for f in files(self.export)}
        self.assert_ok(self.run_export())
        self.assertEqual({(f, (self.export / f).read_bytes()) for f in files(self.export)}, first)

    def test_file_deleted_on_server_disappears_from_export(self):
        self.assert_ok(self.run_export())
        gone = "world/players/stats/6d0b4e92-1a7c-4f3e-b258-9e81c3a5d7f0.json"
        (self.server / gone).unlink()
        self.assert_ok(self.run_export())
        self.assertEqual(files(self.export), self.expected - {gone})

    def test_never_changes_the_server(self):
        before = snapshot(self.server)
        self.assert_ok(self.run_export())
        self.assert_ok(self.run_export())
        self.assertEqual(snapshot(self.server), before)
        calls = self.log.read_text().splitlines()
        self.assertEqual(len(calls), 2)
        for line in calls:
            # Only ever a create (read-only) tar inside the container.
            self.assertTrue(line.startswith(f"exec 100 -- tar -C {self.server} -cf - "), line)
            self.assertNotRegex(line, r" -[a-zA-Z]*[xru]|--delete|--remove")

    def test_tar_exit_1_is_only_a_warning(self):
        r = self.run_export(FAKE_PCT_EXIT="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("warning", r.stderr)
        self.assertEqual(files(self.export), self.expected)

    def test_tar_exit_2_keeps_previous_export(self):
        self.assert_ok(self.run_export())
        before = snapshot(self.export)
        (self.server / "world/players/stats/6d0b4e92-1a7c-4f3e-b258-9e81c3a5d7f0.json").unlink()
        r = self.run_export(FAKE_PCT_EXIT="2")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(snapshot(self.export), before)

    def test_broken_copy_keeps_previous_export(self):
        # pct exiting 1 looks like tar's harmless "file changed" warning; it must not hide a failed copy.
        self.assert_ok(self.run_export())
        before = snapshot(self.export)
        for stream in ("empty", "garbage", "truncated"):
            for code in ("0", "1"):
                r = self.run_export(FAKE_PCT_STREAM=stream, FAKE_PCT_EXIT=code)
                self.assertNotEqual(r.returncode, 0, (stream, code, r.stderr))
                self.assertIn("export left unchanged", r.stderr)
                self.assertEqual(snapshot(self.export), before, (stream, code))

    def test_refuses_root_folder(self):
        # A fake `rm` first on PATH makes this harmless even if the safety check were broken.
        fakebin = self.tmp / "bin"
        fakebin.mkdir()
        (fakebin / "rm").write_text(f'#!/bin/sh\necho "$@" >> {self.tmp}/rm.log\nexit 1\n')
        (fakebin / "rm").chmod(0o755)
        path = f"{fakebin}:{os.environ['PATH']}"
        # (An empty STAGING="" falls back to the default path via ${VAR:-default}, so it is not tested here.)
        for var, value in (("STAGING", "/"), ("EXPORT_DIR", "/"), ("STAGING", "//")):
            r = self.run_export(PATH=path, **{var: value})
            self.assertNotEqual(r.returncode, 0, (var, value))
            self.assertIn("refusing", r.stderr)
        self.assertFalse((self.tmp / "rm.log").exists())
        self.assertFalse(self.log.exists())  # pct was never called

    def test_exported_files_are_world_readable(self):
        os.chmod(self.server / "usercache.json", 0o600)  # like a strict server umask
        self.assert_ok(self.run_export())
        for p in [self.export, *self.export.rglob("*")]:
            mode = p.stat().st_mode
            want = stat.S_IROTH | (stat.S_IXOTH if p.is_dir() else 0)
            self.assertEqual(mode & want, want, f"{p}: {oct(mode)}")


class UnitFilesTest(unittest.TestCase):
    def test_timer_runs_every_minute(self):
        t = (ROOT / "deploy" / "mc-export.timer").read_text()
        self.assertIn("[Timer]", t)
        self.assertRegex(t, r"(?m)^(OnUnitActiveSec=1min|OnCalendar=minutely)$")
        self.assertRegex(t, r"(?m)^WantedBy=timers\.target$")

    def test_service_is_oneshot_and_path_matches_readme(self):
        s = (ROOT / "deploy" / "mc-export.service").read_text()
        self.assertRegex(s, r"(?m)^Type=oneshot$")
        exec_start = re.search(r"(?m)^ExecStart=(\S+)$", s).group(1)
        readme = (ROOT / "deploy" / "README.md").read_text()
        self.assertIn(f"install -m 755 export.sh {exec_start}", readme)


class ShellcheckTest(unittest.TestCase):
    def test_shellcheck_clean(self):
        sc = shutil.which("shellcheck") or shutil.which("shellcheck", path="/opt/homebrew/bin")
        if not sc:
            self.skipTest("shellcheck not installed (brew install shellcheck)")
        r = subprocess.run([sc, str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
