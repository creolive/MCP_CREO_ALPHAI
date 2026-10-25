"""guard-root developer entry regressions (offline; no Creo, no Toolkit)."""

import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import bridge
import tools.guarded_live_run as guarded

PROBE = r"""
import msvcrt
import pathlib
import sys

handle = open(sys.argv[1], "r+b")
try:
    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
except OSError:
    pathlib.Path(sys.argv[2]).write_text("busy", encoding="ascii")
else:
    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    pathlib.Path(sys.argv[2]).write_text("free", encoding="ascii")
"""

MARKER = r"""
import pathlib
import sys

pathlib.Path(sys.argv[1]).write_text("ran", encoding="ascii")
"""


class GuardedLiveRun(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="guard_live_")
        self.addCleanup(temporary.cleanup)
        self.temp = Path(temporary.name).resolve()
        self.guard = self.temp / "main_worktree"
        self.guard.mkdir()
        (self.guard / "toolkit.lock").write_bytes(b"")
        self.md050 = self.temp / "md050"
        (self.md050 / "build").mkdir(parents=True)
        self.probe = self.temp / "probe.py"
        self.probe.write_text(PROBE, encoding="ascii")
        self.marker_script = self.temp / "marker.py"
        self.marker_script.write_text(MARKER, encoding="ascii")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(guarded, "ROOT", self.md050))
        self.stack.enter_context(patch.object(bridge, "ROOT", self.md050))
        self.stack.enter_context(patch.object(guarded, "git_state", return_value={"commit": None}))
        self.stack.enter_context(patch.object(guarded, "source_hash", return_value="hash"))

    def command(self, script, *args):
        quoted = " ".join(f'"{value}"' for value in (script, *args))
        return f'"{sys.executable}" {quoted}'

    def test_guard_held_for_full_child_lifetime_then_released(self):
        marker = self.temp / "probe_result.txt"
        code = guarded.main(
            [
                "--guard-root",
                str(self.guard),
                "--run",
                self.command(self.probe, str(self.guard / "toolkit.lock"), str(marker)),
            ]
        )
        self.assertEqual(code, 0)
        # While the child ran, the guard lock was genuinely held.
        self.assertEqual(marker.read_text(encoding="ascii"), "busy")
        # The guard released cleanly and removed its owner record.
        self.assertFalse((self.guard / "toolkit-owner.lock").exists())
        reports = list((self.md050 / "build").glob("guarded_live_*/report.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertEqual(report["guard"]["status"], "released")
        self.assertEqual(report["children"][0]["returncode"], 0)
        self.assertTrue(report["success"])

    def test_busy_guard_stops_without_running_children(self):
        marker = self.temp / "child_ran.txt"
        with patch.object(bridge, "ROOT", self.guard):
            with bridge.toolkit_lock(operation="other_owner"):
                code = guarded.main(
                    [
                        "--guard-root",
                        str(self.guard),
                        "--run",
                        self.command(self.marker_script, str(marker)),
                    ]
                )
        self.assertEqual(code, guarded.BUSY_EXIT)
        self.assertFalse(marker.exists())
        reports = list((self.md050 / "build").glob("guarded_live_*/report.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertEqual(report["guard"]["status"], "busy")
        self.assertEqual(report["children"], [])

    def test_failing_child_stops_sequence_but_guard_released(self):
        first = self.temp / "first_ran.txt"
        second = self.temp / "second_ran.txt"
        failing = f'"{sys.executable}" -c "import sys;sys.exit(3)"'
        code = guarded.main(
            [
                "--guard-root",
                str(self.guard),
                "--run",
                self.command(self.probe, str(self.guard / "toolkit.lock"), str(first)),
                "--run",
                failing,
                "--run",
                self.command(self.marker_script, str(second)),
            ]
        )
        self.assertEqual(code, 3)
        self.assertTrue(first.exists())
        self.assertFalse(second.exists())
        self.assertFalse((self.guard / "toolkit-owner.lock").exists())


if __name__ == "__main__":
    unittest.main()
