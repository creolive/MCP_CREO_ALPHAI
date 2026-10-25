"""guard-root developer entry regressions (offline; no Creo, no Toolkit).

These tests verify the REAL lock behavior: an independent probe process
genuinely tries to acquire the guard byte lock, so "the lock is still held"
is proven by an OS-level contention observation, never by report strings
alone. Lock retention paths run the guard entry as a real subprocess (the
entry is supposed to stay alive holding the OS lock); completion paths may
run it in-process.
"""

import json
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import bridge
import tools.guarded_live_run as guarded

REPO_ROOT = Path(bridge.__file__).resolve().parent

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

# Leaves a TERMINAL job whose native_checkpoint.json still names a live
# process: the guard must not treat "terminal + lock free" as proof while the
# recorded native worker identity is alive.
ORPHAN_WORKER = r"""
import json
import pathlib
import subprocess
import sys

job = pathlib.Path(sys.argv[1]) / sys.argv[2]
job.mkdir(parents=True)
(job / "job.json").write_text(json.dumps({"status": "succeeded"}), encoding="ascii")
sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(8)"])
(job / "native_checkpoint.json").write_text(
    json.dumps({"native_pid": sleeper.pid}), encoding="ascii"
)
"""

# Accepts job A, then a late batch child accepts job B while A is still
# pending; both are finalized by detached writers. The guard must discover B
# after polling started and wait for it.
LATE_PARENT = r"""
import json
import pathlib
import subprocess
import sys

jobs = pathlib.Path(sys.argv[1])
first = jobs / sys.argv[2]
first.mkdir(parents=True)
(first / "job.json").write_text(json.dumps({"status": "running"}), encoding="ascii")
subprocess.Popen([sys.executable, sys.argv[3], str(first)], close_fds=True)
subprocess.Popen(
    [sys.executable, sys.argv[4], str(jobs), sys.argv[5], sys.argv[3]], close_fds=True
)
"""

LATE_CHILD = r"""
import json
import pathlib
import subprocess
import sys
import time

time.sleep(2.5)
jobs = pathlib.Path(sys.argv[1])
late = jobs / sys.argv[2]
late.mkdir(parents=True)
(late / "job.json").write_text(json.dumps({"status": "running"}), encoding="ascii")
subprocess.Popen([sys.executable, sys.argv[3], str(late)], close_fds=True)
"""

# Replaces the md050 jobs directory with a plain file mid-run: discovery hits
# a non-FileNotFoundError I/O error which must never be mistaken for "empty".
BREAK_DISCOVERY = r"""
import os
import sys

os.rmdir(sys.argv[1])
with open(sys.argv[1], "w", encoding="ascii") as handle:
    handle.write("not a directory")
"""

# Runs the guard entry in a real subprocess with the md050 paths bound to a
# temporary directory (bridge.ROOT/JOBS are process-local).
LAUNCHER = r"""
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import bridge
import tools.guarded_live_run as guarded

md050 = Path(sys.argv[2])
bridge.ROOT = md050
bridge.JOBS = md050 / "jobs"
guarded.ROOT = md050
# The temporary md050 tree has no git identity or source files; stub the
# report-only helpers exactly like the in-process patches do.
guarded.git_state = lambda root: {"commit": None}
guarded.source_hash = lambda path: "hash"
raise SystemExit(guarded.main(sys.argv[3:]))
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
        self.orphan_worker = self.temp / "orphan_worker.py"
        self.orphan_worker.write_text(ORPHAN_WORKER, encoding="ascii")
        self.late_parent = self.temp / "late_parent.py"
        self.late_parent.write_text(LATE_PARENT, encoding="ascii")
        self.late_child = self.temp / "late_child.py"
        self.late_child.write_text(LATE_CHILD, encoding="ascii")
        self.break_discovery = self.temp / "break_discovery.py"
        self.break_discovery.write_text(BREAK_DISCOVERY, encoding="ascii")
        self.launcher = self.temp / "launcher.py"
        self.launcher.write_text(LAUNCHER, encoding="ascii")
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

    def probe_guard_lock(self):
        """Ask an independent process to try acquiring the guard byte lock."""
        marker = self.temp / f"probe_{time.monotonic_ns()}.txt"
        result = subprocess.run(
            [sys.executable, str(self.probe), str(self.guard / "toolkit.lock"), str(marker)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return marker.read_text(encoding="ascii")

    def read_report(self):
        reports = list((self.md050 / "build").glob("guarded_live_*/report.json"))
        self.assertEqual(len(reports), 1)
        return json.loads(reports[0].read_text(encoding="utf-8"))

    def launch_guard_subprocess(self, *args):
        self.guard_log = self.temp / f"guard_sub_{time.monotonic_ns()}.log"
        self.guard_stream = self.guard_log.open("w", encoding="utf-8")
        self.addCleanup(self.guard_stream.close)
        return subprocess.Popen(
            [
                sys.executable,
                str(self.launcher),
                str(REPO_ROOT),
                str(self.md050),
                *args,
            ],
            cwd=REPO_ROOT,
            stdout=self.guard_stream,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def guard_output(self):
        return self.guard_log.read_text(encoding="utf-8", errors="replace")

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
        # The guard released cleanly and removed its owner record; an
        # independent probe really acquires the lock afterwards.
        self.assertFalse((self.guard / "toolkit-owner.lock").exists())
        self.assertEqual(self.probe_guard_lock(), "free")
        report = self.read_report()
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
        report = self.read_report()
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
        self.assertEqual(self.probe_guard_lock(), "free")

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
        self.assertEqual(self.probe_guard_lock(), "free")
        report = self.read_report()
        self.assertEqual(report["settle"]["status"], "quiet")
        self.assertEqual(report["settle"]["new_jobs"], {job_id: "succeeded"})
        self.assertTrue(report["settle"]["quiet"])
        self.assertEqual(report["guard"]["status"], "released")

    def test_unknown_outcome_releases_after_proof_but_fails_and_stops_children(self):
        # unknown_outcome does NOT mean "hold the lock forever": once every
        # accepted job is terminal and no md050 native worker is alive, the
        # guard lock is released — but the run fails, remaining children are
        # forbidden and every md050 unknown protection stays untouched.
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
        self.assertEqual(report["guard"]["status"], "released")
        self.assertEqual(report["settle"]["status"], "unknown_outcome")
        self.assertTrue(report["settle"]["quiet"])
        self.assertFalse(report["success"])
        self.assertEqual(self.probe_guard_lock(), "free")
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
        self.assertEqual(self.probe_guard_lock(), "free")
        report = self.read_report()
        self.assertEqual(report["settle"]["status"], "quiet")
        self.assertEqual(report["settle"]["new_jobs"], {job_id: "succeeded"})
        self.assertEqual(report["guard"]["status"], "released")
        self.assertFalse(report["success"])

    def test_late_job_accepted_during_polling_is_accumulated(self):
        # Job A is accepted, and while A is still pending a batch child
        # accepts job B. B appears only after polling started; the guard must
        # rediscover it every round and wait for BOTH jobs.
        first = "a" * 32
        late = "b" * 32
        code = guarded.main(
            [
                "--guard-root",
                str(self.guard),
                "--run",
                self.command(
                    self.late_parent,
                    str(self.md050 / "jobs"),
                    first,
                    self.finish,
                    self.late_child,
                    late,
                ),
            ]
        )
        self.assertEqual(code, 0)
        report = self.read_report()
        self.assertEqual(report["settle"]["status"], "quiet")
        self.assertEqual(report["settle"]["new_jobs"], {first: "succeeded", late: "succeeded"})
        self.assertEqual(self.probe_guard_lock(), "free")

    def test_live_checkpoint_native_pid_blocks_release_until_it_exits(self):
        # The accepted job is already terminal, but its checkpoint still names
        # a live process: "terminal + lock free" is not proof. The guard must
        # keep holding until the recorded native identity exits.
        job_id = "0" * 31 + "9"
        code = guarded.main(
            [
                "--guard-root",
                str(self.guard),
                "--run",
                self.command(self.orphan_worker, str(self.md050 / "jobs"), job_id),
            ]
        )
        self.assertEqual(code, 0)
        report = self.read_report()
        self.assertEqual(report["settle"]["status"], "quiet")
        self.assertEqual(report["settle"]["new_jobs"], {job_id: "succeeded"})
        self.assertFalse(report["settle"]["workers"]["alive"])
        self.assertEqual(self.probe_guard_lock(), "free")

    def test_baseline_io_error_aborts_before_guard_is_taken(self):
        # An unreadable jobs directory at baseline must abort the run BEFORE
        # the guard lock is taken; it is never mistaken for "no jobs".
        (self.md050 / "jobs").rmdir()
        (self.md050 / "jobs").write_text("not a directory", encoding="ascii")
        with self.assertRaises(NotADirectoryError):
            guarded.main(
                [
                    "--guard-root",
                    str(self.guard),
                    "--run",
                    self.command(self.marker_script, str(self.temp / "child_ran.txt")),
                ]
            )
        self.assertFalse((self.guard / "toolkit-owner.lock").exists())
        self.assertEqual(self.probe_guard_lock(), "free")

    def test_unproven_settle_keeps_holding_real_lock_past_budget(self):
        # The md050 channel stays busy after the child exits, so a safe
        # release is never provable. Past the settle budget the entry must
        # STILL be alive and STILL holding the real guard byte lock; only
        # terminating the process frees it.
        marker = self.temp / "child_ran.txt"
        process = self.launch_guard_subprocess(
            "--guard-root",
            str(self.guard),
            "--run",
            self.command(self.marker_script, str(marker)),
            "--settle-timeout",
            "2",
        )
        try:
            with patch.object(bridge, "ROOT", self.md050):
                with bridge.toolkit_lock(operation="other_holder"):
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline and not marker.exists():
                        time.sleep(0.2)
                    self.assertTrue(
                        marker.exists(),
                        f"guard never ran its child:\n{self.guard_output()}",
                    )
                    time.sleep(3.5)  # settle budget (2 s) has elapsed
                    self.assertEqual(self.probe_guard_lock(), "busy")
                    report = self.read_report()
                    self.assertEqual(report["settle"]["status"], "waiting_for_proof")
                    self.assertFalse(report["settle"]["channel_probe_free"])
                    self.assertFalse(report["success"])
        finally:
            process.terminate()
            process.wait(timeout=30)
        self.assertEqual(self.probe_guard_lock(), "free")

    def test_discovery_io_error_during_settle_keeps_holding_real_lock(self):
        # Mid-run the jobs directory becomes unreadable (not absent): the
        # guard must treat the round as unprovable and keep holding the real
        # lock past the settle budget instead of releasing.
        process = self.launch_guard_subprocess(
            "--guard-root",
            str(self.guard),
            "--run",
            self.command(self.break_discovery, str(self.md050 / "jobs")),
            "--settle-timeout",
            "2",
        )
        try:
            time.sleep(3.5)
            self.assertIsNone(
                process.poll(), f"guard exited while unproven:\n{self.guard_output()}"
            )
            self.assertEqual(self.probe_guard_lock(), "busy")
            report = self.read_report()
            self.assertEqual(report["settle"]["status"], "waiting_for_proof")
            self.assertTrue(report["settle"]["discovery_error"])
        finally:
            process.terminate()
            process.wait(timeout=30)
        self.assertEqual(self.probe_guard_lock(), "free")


if __name__ == "__main__":
    unittest.main()
