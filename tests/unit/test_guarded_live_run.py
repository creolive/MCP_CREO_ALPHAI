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

# Creates an accepted-looking md050 job directory in "running" state, then
# exits; an optional detached writer finalizes it later. This models a driver
# that dies before its accepted job reaches a terminal state.
LEAVER = r"""
import json
import pathlib
import subprocess
import sys

job = pathlib.Path(sys.argv[1]) / sys.argv[2]
job.mkdir(parents=True)
(job / "job.json").write_text(json.dumps({"status": "running"}), encoding="ascii")
if len(sys.argv) > 3:
    subprocess.Popen([sys.executable, sys.argv[3], str(job)], close_fds=True)
if len(sys.argv) > 4:
    raise SystemExit(int(sys.argv[4]))
"""

FINISH = r"""
import json
import pathlib
import sys
import time

time.sleep(1.5)
pathlib.Path(sys.argv[1], "job.json").write_text(
    json.dumps({"status": "succeeded"}), encoding="ascii"
)
"""

UNKNOWN = r"""
import json
import pathlib
import sys

job = pathlib.Path(sys.argv[1]) / sys.argv[2]
job.mkdir(parents=True)
(job / "job.json").write_text(json.dumps({"status": "unknown_outcome"}), encoding="ascii")
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
        (self.md050 / "jobs").mkdir()
        self.probe = self.temp / "probe.py"
        self.probe.write_text(PROBE, encoding="ascii")
        self.marker_script = self.temp / "marker.py"
        self.marker_script.write_text(MARKER, encoding="ascii")
        self.leaver = self.temp / "leaver.py"
        self.leaver.write_text(LEAVER, encoding="ascii")
        self.finish = self.temp / "finish.py"
        self.finish.write_text(FINISH, encoding="ascii")
        self.unknown = self.temp / "unknown.py"
        self.unknown.write_text(UNKNOWN, encoding="ascii")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(guarded, "ROOT", self.md050))
        self.stack.enter_context(patch.object(bridge, "ROOT", self.md050))
        self.stack.enter_context(patch.object(bridge, "JOBS", self.md050 / "jobs"))
        self.stack.enter_context(patch.object(guarded, "git_state", return_value={"commit": None}))
        self.stack.enter_context(patch.object(guarded, "source_hash", return_value="hash"))

    def command(self, script, *args):
        quoted = " ".join(f'"{value}"' for value in (script, *args))
        return f'"{sys.executable}" {quoted}'

    def read_report(self):
        reports = list((self.md050 / "build").glob("guarded_live_*/report.json"))
        self.assertEqual(len(reports), 1)
        return json.loads(reports[0].read_text(encoding="utf-8"))

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

    def test_child_exit_with_running_job_guard_waits_for_terminal_then_releases(self):
        # The child exits 0 but leaves an accepted job running; a detached
        # writer finalizes it afterwards. Child exit alone must not release
        # the guard; settlement must confirm the terminal state first.
        job_id = "d" * 32
        code = guarded.main(
            [
                "--guard-root",
                str(self.guard),
                "--run",
                self.command(self.leaver, str(self.md050 / "jobs"), job_id, self.finish),
            ]
        )
        self.assertEqual(code, 0)
        self.assertFalse((self.guard / "toolkit-owner.lock").exists())
        report = self.read_report()
        self.assertEqual(report["settle"]["status"], "quiet")
        self.assertEqual(report["settle"]["new_jobs"], {job_id: "succeeded"})
        self.assertTrue(report["settle"]["quiet"])
        self.assertEqual(report["guard"]["status"], "released")

    def test_unknown_outcome_retains_guard_and_stops_remaining_children(self):
        job_id = "e" * 32
        second = self.temp / "second_ran.txt"
        code = guarded.main(
            [
                "--guard-root",
                str(self.guard),
                "--run",
                self.command(self.unknown, str(self.md050 / "jobs"), job_id),
                "--run",
                self.command(self.marker_script, str(second)),
                "--settle-timeout",
                "5",
            ]
        )
        self.assertEqual(code, guarded.SETTLE_EXIT)
        self.assertFalse(second.exists())
        report = self.read_report()
        self.assertEqual(report["guard"]["status"], "retained_unproven")
        self.assertFalse(report["settle"]["quiet"])
        self.assertFalse(report["success"])
        # The unknown job's protection is left untouched.
        manifest = json.loads(
            (self.md050 / "jobs" / job_id / "job.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "unknown_outcome")

    def test_failing_child_with_lingering_job_still_settles_before_release(self):
        job_id = "f" * 32
        code = guarded.main(
            [
                "--guard-root",
                str(self.guard),
                "--run",
                self.command(self.leaver, self.md050 / "jobs", job_id, self.finish, 3),
                "--settle-timeout",
                "30",
            ]
        )
        self.assertEqual(code, 3)
        self.assertFalse((self.guard / "toolkit-owner.lock").exists())
        report = self.read_report()
        self.assertEqual(report["settle"]["status"], "quiet")
        self.assertEqual(report["settle"]["new_jobs"], {job_id: "succeeded"})
        self.assertEqual(report["guard"]["status"], "released")
        self.assertFalse(report["success"])

    def test_channel_busy_after_child_exit_release_not_proven(self):
        # Someone still holds the md050 toolkit lock after the child exits;
        # the guard must not claim a safe release.
        marker = self.temp / "child_ran.txt"
        with patch.object(bridge, "ROOT", self.md050):
            with bridge.toolkit_lock(operation="other_holder"):
                code = guarded.main(
                    [
                        "--guard-root",
                        str(self.guard),
                        "--run",
                        self.command(self.marker_script, str(marker)),
                        "--settle-timeout",
                        "2",
                    ]
                )
        self.assertEqual(code, guarded.SETTLE_EXIT)
        report = self.read_report()
        self.assertFalse(report["settle"]["quiet"])
        self.assertEqual(report["guard"]["status"], "retained_unproven")
        self.assertFalse(report["success"])


if __name__ == "__main__":
    unittest.main()
