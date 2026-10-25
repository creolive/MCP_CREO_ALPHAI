"""Guard-root developer live-run entry (0.5.0 feedback batch 2, stage 3).

The main checkout service (E:\\Projects\\MCP_CREO_MechDog) normally owns the
Creo session. To run md050 final-source live drivers without the old service
touching the same Creo concurrently, this entry first holds the REAL toolkit
channel lock of the main worktree, then runs one or more md050 test child
processes sequentially. md050 children keep holding their own worktree lock
as usual; the two lock files are independent.

Guard discipline:
* non-blocking only — a busy guard lock stops immediately (exit code 2),
  never queues, retries, clears old owners or unknown protection;
* child exit is NOT evidence of job completion: a driver that asserts out,
  times out or dies on a protocol error can leave accepted md050 jobs running
  in detached runners. Before the guard is released (success, child failure
  or exception alike) this entry therefore, while still holding the guard:
    1. snapshots the md050 job directory set before starting any child, and
    2. polls ONLY the job directories accepted during this run to a terminal
       status (reading job.json; never submits, replays or reconnects), and
    3. probes the md050 toolkit lock to confirm the native channel is quiet.
  Only when every new job is terminal and the channel probe is free is the
  guard released. An unknown_outcome job (or a channel that cannot be proven
  quiet within --settle-timeout seconds) stops the remaining children, keeps
  every md050 protection untouched and exits with code 3: the report then
  states explicitly that a safe release could not be confirmed.
* nothing about the production lock mechanism changes — the guard is a local
  ROOT binding inside this developer entry, not a production config API.

Example (PowerShell, from this checkout):
.venv\\Scripts\\python.exe tools\\guarded_live_run.py `
    --guard-root E:\\Projects\\MCP_CREO_MechDog `
    --run ".venv\\Scripts\\python.exe tools\\test_assembly_matrix.py --session-health-verified" `
    --run ".venv\\Scripts\\python.exe tools\\test_assembly_pipeline.py --session-health-verified"
"""

from __future__ import annotations

import argparse
import json
import msvcrt
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bridge
from creo_mechdog.paths import SOURCE_PATHS
from tools.dev_check import git_state, source_hash

ROOT = SOURCE_PATHS.resource_root
BUSY_EXIT = 2
SETTLE_EXIT = 3
JOB_NAME = re.compile(r"^[0-9a-f]{32}$")
TERMINAL_STATES = ("succeeded", "failed", "unknown_outcome")


def _split_windows(command: str) -> list[str]:
    """Tokenize a developer-supplied child command (double quotes group)."""
    tokens = []
    for match in re.finditer(r'"([^"]*)"|(\S+)', command):
        tokens.append(match.group(1) if match.group(1) is not None else match.group(2))
    return tokens


def _report_dir() -> Path:
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%S") + f"{now.microsecond:06d}"
    directory = ROOT / f"build/guarded_live_{stamp}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _guard_owner(guard_root: Path) -> dict:
    try:
        value = bridge.read_json(guard_root / "toolkit-owner.lock")
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _enter_guard(guard_root: Path):
    """Hold the guard worktree's real channel lock (locally bound ROOT)."""
    original = bridge.ROOT
    bridge.ROOT = guard_root
    context = bridge.toolkit_lock(operation="guarded_live_run")
    try:
        context.__enter__()
    except BaseException:
        bridge.ROOT = original
        raise
    return context, original


def _exit_guard(context, guard_root: Path, original) -> None:
    bridge.ROOT = guard_root
    try:
        context.__exit__(None, None, None)
    finally:
        bridge.ROOT = original


def _snapshot_jobs(jobs_root: Path) -> set[str]:
    """Baseline of already-accepted md050 job directories (names only)."""
    try:
        return {entry.name for entry in jobs_root.iterdir() if entry.is_dir() and entry.name}
    except OSError:
        return set()


def _new_jobs(jobs_root: Path, baseline: set[str]) -> list[str]:
    try:
        current = {entry.name for entry in jobs_root.iterdir() if entry.is_dir() and entry.name}
    except OSError:
        return []
    return sorted(name for name in current - baseline if JOB_NAME.fullmatch(name))


def _read_status(jobs_root: Path, job_id: str) -> str | None:
    try:
        manifest = bridge.read_json(jobs_root / job_id / "job.json")
    except (OSError, ValueError):
        return None
    status = manifest.get("status")
    return status if isinstance(status, str) else None


def _channel_quiet(md050_root: Path) -> bool:
    """Non-blocking probe of the md050 toolkit byte lock (no owner write)."""
    lock = md050_root / "toolkit.lock"
    if not lock.exists():
        return True
    try:
        handle = open(lock, "r+b")
    except OSError:
        return False
    try:
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return True
    finally:
        handle.close()


def _settle(md050_root: Path, jobs_root: Path, baseline: set[str], budget_seconds: float) -> dict:
    """Confirm this run's accepted jobs are terminal and the channel is quiet.

    Polls only; never submits, replays, erases, or touches Creo. Returns a
    structured outcome; ``quiet`` is True only when a safe release is proven.
    While the guard is held, ``bridge.ROOT`` stays bound to the guard root, so
    the md050 paths are passed in explicitly.
    """
    deadline = time.monotonic() + budget_seconds
    new_jobs = _new_jobs(jobs_root, baseline)
    jobs = {name: _read_status(jobs_root, name) for name in new_jobs}
    while True:
        for name in new_jobs:
            jobs[name] = _read_status(jobs_root, name)
        pending = [name for name, status in jobs.items() if status not in TERMINAL_STATES]
        unknown = [name for name, status in jobs.items() if status == "unknown_outcome"]
        quiet = _channel_quiet(md050_root)
        if unknown:
            return {
                "status": "unknown_outcome",
                "quiet": False,
                "new_jobs": jobs,
                "note": (
                    "An accepted md050 job reported unknown_outcome; remaining "
                    "children were stopped and every md050 protection is left "
                    "untouched. A safe guard release is NOT confirmed."
                ),
            }
        if not pending and quiet:
            return {
                "status": "quiet",
                "quiet": True,
                "new_jobs": jobs,
                "note": (
                    "All jobs accepted during this run are terminal and the "
                    "md050 toolkit channel probe is free; the guard release "
                    "is proven safe."
                ),
            }
        if time.monotonic() >= deadline:
            return {
                "status": "not_quiet" if not quiet else "jobs_pending",
                "quiet": False,
                "new_jobs": jobs,
                "pending": pending,
                "note": (
                    "Channel quiet could not be proven within the settle budget "
                    "(%.0f s); a safe guard release is NOT confirmed."
                )
                % budget_seconds,
            }
        time.sleep(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--guard-root",
        default=r"E:\Projects\MCP_CREO_MechDog",
        help="worktree whose toolkit.lock guards the shared Creo session",
    )
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        help="child command to run under the guard; repeatable, runs sequentially",
    )
    parser.add_argument(
        "--settle-timeout",
        type=float,
        default=1200.0,
        help=(
            "seconds to wait for this run's accepted jobs to reach a terminal "
            "state and the md050 channel probe to free before declaring the "
            "release unproven (default 1200)"
        ),
    )
    arguments = parser.parse_args(argv)
    guard_root = Path(arguments.guard_root).resolve()
    if not guard_root.is_dir():
        raise SystemExit(f"Guard root is not a directory: {guard_root}")
    if guard_root == ROOT.resolve():
        raise SystemExit("Guard root must differ from this md050 worktree")
    directory = _report_dir()
    # Capture the md050 paths BEFORE the guard binds bridge.ROOT to the guard
    # root; settlement keeps using these explicit paths.
    md050_root = bridge.ROOT
    md050_jobs = bridge.JOBS
    baseline = _snapshot_jobs(md050_jobs)
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "guard_root": str(guard_root),
        "md050_root": str(ROOT),
        "baseline_job_count": len(baseline),
        "parent_source": git_state(ROOT),
        "parent_fingerprints": {
            name: source_hash(ROOT / name)
            for name in ("bridge.py", "server.py", "generic_bridge.py", "tools/guarded_live_run.py")
        },
        "child_source_note": (
            "children are md050 processes of this same tree; their identity is "
            "the parent fingerprint set above"
        ),
        "guard": None,
        "settle": None,
        "children": [],
        "success": False,
    }
    destination = directory / "report.json"

    def save():
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        context, original_root = _enter_guard(guard_root)
    except bridge.ToolkitBusy:
        report["guard"] = {
            "status": "busy",
            "action": "stopped without running any child; no queue, no retry",
            "owner_snapshot": _guard_owner(guard_root),
        }
        save()
        print(
            json.dumps(
                {
                    "status": "busy",
                    "guard_root": str(guard_root),
                    "owner": report["guard"]["owner_snapshot"],
                    "report": str(destination),
                },
                ensure_ascii=False,
            )
        )
        return BUSY_EXIT
    report["guard"] = {
        "status": "held",
        "owner_written_to": str(guard_root / "toolkit-owner.lock"),
        "note": (
            "guard held while children run and until this run's accepted jobs "
            "are confirmed terminal and the md050 channel probe is free; child "
            "exit alone is not treated as completion evidence"
        ),
    }
    save()
    children_ok = True
    exit_code = 0
    settle = {"status": "quiet", "quiet": True, "new_jobs": {}, "note": "no children ran"}
    try:
        for command in arguments.run:
            argv_child = _split_windows(command)
            started = time.monotonic()
            result = subprocess.run(argv_child, cwd=ROOT, capture_output=True, text=True)
            child_report = {
                "command": command,
                "returncode": result.returncode,
                "seconds": round(time.monotonic() - started, 3),
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            (directory / f"child_{len(report['children'])}.log").write_text(
                result.stdout + result.stderr, encoding="utf-8", errors="replace"
            )
            report["children"].append(child_report)
            save()
            if result.returncode != 0:
                children_ok = False
                exit_code = result.returncode
                report["guard"]["action"] = (
                    "a child exited non-zero; remaining children were not "
                    "started; the scene is being settled before any release "
                    "decision and left untouched"
                )
                save()
                # A failed driver is exactly the case that can leave accepted
                # jobs behind: settle before any release decision.
                settle = _settle(md050_root, md050_jobs, baseline, arguments.settle_timeout)
                report["settle"] = settle
                save()
                break
            # Child exit is not completion evidence: settle after EVERY child
            # so an unknown outcome or a still-running accepted job stops the
            # remaining drivers before they touch the session.
            settle = _settle(md050_root, md050_jobs, baseline, arguments.settle_timeout)
            report["settle"] = settle
            if not settle["quiet"]:
                children_ok = False
                exit_code = SETTLE_EXIT
                report["guard"]["action"] = (
                    "settlement after a child failed; remaining children were "
                    "not started and md050 protections are left untouched"
                )
                save()
                break
        if settle["quiet"]:
            report["guard"]["status"] = "released"
            report["guard"]["action"] = (
                "settled: all jobs accepted during this run are terminal and "
                "the md050 channel probe is free"
            )
            report["success"] = children_ok
            save()
            _exit_guard(context, guard_root, original_root)
            print(
                json.dumps(
                    {"status": "ok" if children_ok else "child_failed", "report": str(destination)},
                    ensure_ascii=False,
                )
            )
            return exit_code
        if "settle" not in report:
            report["settle"] = settle
            save()
        report["guard"]["status"] = "retained_unproven"
        report["guard"]["action"] = (
            "a safe release could NOT be proven; md050 protections are left "
            "untouched and the report marks this run as not safe to continue "
            "from automatically"
        )
        save()
        # Deliberately skip the normal owner-file cleanup: the reservation
        # evidence stays visible for operator reconciliation. The OS byte
        # lock still frees at process exit; the report never claims safety.
        print(
            json.dumps(
                {"status": settle["status"], "report": str(destination)},
                ensure_ascii=False,
            )
        )
        return SETTLE_EXIT
    except BaseException as exc:
        # Driver-side exception (assertion, timeout, protocol error): still
        # settle before deciding, and never claim a safe release we cannot
        # prove. Md050 jobs and protections stay untouched either way.
        try:
            settle = _settle(md050_root, md050_jobs, baseline, arguments.settle_timeout)
        except Exception:  # noqa: BLE001 - report the original failure instead
            settle = {
                "status": "settle_error",
                "quiet": False,
                "note": "settlement itself failed; a safe release is NOT confirmed",
            }
        report["settle"] = settle
        report["guard"]["status"] = "retained_unproven"
        report["guard"]["action"] = (
            f"guard run aborted with {type(exc).__name__}: {exc}; release safety "
            "was not confirmed and md050 protections were left untouched"
        )
        report["error"] = f"{type(exc).__name__}: {exc}"
        save()
        print(
            json.dumps(
                {"status": "aborted", "error": report["error"], "report": str(destination)},
                ensure_ascii=False,
            )
        )
        return SETTLE_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
