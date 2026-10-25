"""Guard-root developer live-run entry (0.5.0 feedback batch 2, stage 4).

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
  in detached runners. Before the guard is released this entry therefore,
  while still holding the guard:
    1. snapshots the md050 job directory set before starting any child
       (only FileNotFoundError means "no jobs directory yet"; any other I/O
       error aborts the run before the guard is even taken),
    2. polls ONLY the job directories accepted during this run to a terminal
       status (reading job.json; never submits, replays or reconnects),
       rediscovering new job directories every poll round so batch children
       accepted while a previous job is still settling are never missed, and
    3. requires THREE independent proofs before releasing the REAL byte lock:
       every accepted job is terminal, no md050 native worker is alive
       (checked against native_checkpoint.json native_pid process identities
       and a read-only image scan for this worktree's build\\creo_worker.exe —
       an idle lock alone never proves an orphan worker stopped), and the
       md050 toolkit byte-lock probe is free.
* Release outcomes once the proof is complete:
    - all quiet (no unknown_outcome) — guard released, exit 0;
    - an unknown_outcome job but the worker is provably stopped and the
      channel free — the guard IS released (unknown does not mean "hold the
      lock forever"), remaining children are still forbidden, md050 model/job
      unknown protections are left untouched, and the run exits 3 as a
      failure. This entry never ends Creo, kills workers, clears protection,
      reconnects or resubmits anything.
* If the proof cannot be completed (jobs still pending, worker/channel state
  unprovable, discovery I/O error), --settle-timeout only writes a report
  alert: this process KEEPS RUNNING and KEEPS HOLDING the real OS byte lock
  until the release becomes provable. Returning early would let process exit
  free the OS lock, which is exactly what must not happen. Operator
  interruption (Ctrl+C) is the only early exit; it drops the OS lock without
  any safety claim and never touches md050 state.
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
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bridge
from creo_mechdog.paths import SOURCE_PATHS
from creo_mechdog.recovery import process_identity
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
    """Baseline of already-accepted md050 job directories (names only).

    Only FileNotFoundError means the jobs directory genuinely does not exist
    yet; any other OSError propagates so the run aborts BEFORE the guard lock
    is taken instead of mistaking unreadable state for "no jobs".
    """
    try:
        return {entry.name for entry in jobs_root.iterdir() if entry.is_dir() and entry.name}
    except FileNotFoundError:
        return set()


def _new_jobs(jobs_root: Path, baseline: set[str]) -> list[str]:
    try:
        current = {entry.name for entry in jobs_root.iterdir() if entry.is_dir() and entry.name}
    except FileNotFoundError:
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


def _image_path_pids(target: Path) -> set[int] | None:
    """Read-only scan for live processes whose image path equals ``target``.

    Returns None when the process table itself cannot be enumerated (the scan
    is then unprovable and the caller must stay conservative); an empty set
    proves no such process is running. Never opens process tokens for
    writing, never terminates anything.
    """
    if os.name != "nt":
        return set()
    if not target.is_file():
        return set()
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot_api = kernel.CreateToolhelp32Snapshot
    snapshot_api.argtypes = (wintypes.DWORD, wintypes.DWORD)
    snapshot_api.restype = wintypes.HANDLE
    first = kernel.Process32FirstW
    next_ = kernel.Process32NextW
    open_process = kernel.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    image_name = kernel.QueryFullProcessImageNameW
    image_name.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_wchar_p,
        ctypes.POINTER(wintypes.DWORD),
    )
    image_name.restype = wintypes.BOOL

    class _PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    wanted = str(target).lower()
    matches: set[int] = set()
    handle = snapshot_api(0x2, 0)  # TH32CS_SNAPPROCESS
    if handle == ctypes.c_void_p(-1).value:
        return None
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        has_entry = first(handle, ctypes.byref(entry))
        while has_entry:
            process = open_process(0x1000, False, entry.th32ProcessID)  # QUERY_LIMITED
            if process:
                try:
                    size = wintypes.DWORD(32767)
                    buffer = ctypes.create_unicode_buffer(32768)
                    if image_name(process, 0, buffer, ctypes.byref(size)):
                        if buffer.value.lower() == wanted:
                            matches.add(entry.th32ProcessID)
                finally:
                    close(process)
            has_entry = next_(handle, ctypes.byref(entry))
    finally:
        close(handle)
    return matches


def _md050_worker_state(md050_root: Path, job_dirs: list[Path]) -> dict:
    """Read-only evidence about md050 native workers.

    Two independent signals, because an idle toolkit byte lock never proves
    an orphaned native worker stopped:
    * the ``native_pid`` recorded in each accepted job's
      native_checkpoint.json, checked against the live process table with the
      process creation time (a recycled PID is not the same process); and
    * a read-only image scan for any live process whose executable path is
      exactly this worktree's build\\creo_worker.exe (catches orphans left by
      earlier crashed runs whose jobs this round never saw).
    ``alive`` is True when any signal shows a live or indeterminate worker;
    the release proof requires ``alive`` False and a completed (non-None)
    image scan.
    """
    exe = (md050_root / "build" / "creo_worker.exe").resolve()
    observed: list[dict] = []
    checkpoint_pids: set[int] = set()
    for directory in job_dirs:
        try:
            checkpoint = bridge.read_json(directory / "native_checkpoint.json")
        except (OSError, ValueError, TypeError):
            continue
        pid = checkpoint.get("native_pid")
        if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:
            checkpoint_pids.add(pid)
    alive = False
    for pid in sorted(checkpoint_pids):
        identity = process_identity(pid)
        observed.append({"source": "native_checkpoint", **identity})
        if identity.get("alive") is not False:
            # alive, or existence unverifiable: not provably stopped.
            alive = True
    image_pids = _image_path_pids(exe)
    if image_pids is None:
        observed.append({"source": "image_scan", "error": "process table unreadable"})
        alive = True
        scan_complete = False
    else:
        scan_complete = True
        for pid in sorted(image_pids):
            observed.append({"source": "image_scan", "pid": pid, "alive": True})
            alive = True
    return {"alive": alive, "scan_complete": scan_complete, "observed": observed}


def _settle(
    md050_root: Path,
    jobs_root: Path,
    baseline: set[str],
    budget_seconds: float,
    on_alert=None,
) -> dict:
    """Wait until a guard release is provable, then return the proof.

    Polls only; never submits, replays, erases, kills, reconnects or touches
    Creo. This function returns ONLY when every accepted job of this run is
    terminal, no md050 native worker is provably alive, the md050 byte-lock
    probe is free and discovery had no I/O error. When ``status`` is
    ``unknown_outcome`` the release is still proven (the lock may be freed)
    but the run must be reported as a failure. Until the proof completes, the
    settle budget only triggers a report/alert via ``on_alert``; this loop
    keeps holding the real guard lock and polling. While the guard is held,
    ``bridge.ROOT`` stays bound to the guard root, so the md050 paths are
    passed in explicitly.
    """
    deadline = time.monotonic() + budget_seconds
    jobs: dict[str, str | None] = {}
    alert_written = False
    while True:
        discovery_error = None
        try:
            discovered = _new_jobs(jobs_root, baseline)
        except OSError as exc:
            discovery_error = f"{type(exc).__name__}: {exc}"
            discovered = []
        for name in discovered:
            jobs.setdefault(name, None)
        for name in jobs:
            jobs[name] = _read_status(jobs_root, name)
        pending = [name for name, status in jobs.items() if status not in TERMINAL_STATES]
        unknown = [name for name, status in jobs.items() if status == "unknown_outcome"]
        quiet = _channel_quiet(md050_root)
        workers = _md050_worker_state(md050_root, [jobs_root / name for name in jobs])
        provable = (
            discovery_error is None
            and not pending
            and quiet
            and not workers["alive"]
            and workers["scan_complete"]
        )
        if provable:
            if unknown:
                return {
                    "status": "unknown_outcome",
                    "quiet": True,
                    "released": True,
                    "new_jobs": jobs,
                    "workers": workers,
                    "note": (
                        "Every accepted job is terminal and no md050 native "
                        "worker is alive, so the guard lock CAN be released "
                        "safely; however an accepted job reported "
                        "unknown_outcome: remaining children were stopped, the "
                        "run is a failure, and every md050 model/job unknown "
                        "protection is left untouched (this entry never ends "
                        "Creo, kills workers or clears protection)."
                    ),
                }
            return {
                "status": "quiet",
                "quiet": True,
                "released": True,
                "new_jobs": jobs,
                "workers": workers,
                "note": (
                    "All jobs accepted during this run are terminal, no md050 "
                    "native worker (checkpoint identity or creo_worker.exe "
                    "image scan) is alive, and the md050 channel probe is "
                    "free; the guard release is proven safe."
                ),
            }
        if time.monotonic() >= deadline and not alert_written:
            alert_written = True
            alert = {
                "status": "waiting_for_proof",
                "at": datetime.now(timezone.utc).isoformat(),
                "settle_budget_seconds": budget_seconds,
                "new_jobs": jobs,
                "pending": pending,
                "unknown": unknown,
                "channel_probe_free": quiet,
                "discovery_error": discovery_error,
                "workers": workers,
                "note": (
                    "The settle budget elapsed but a safe guard release is "
                    "still unproven. This entry keeps running and keeps "
                    "holding the REAL toolkit byte lock until the release "
                    "becomes provable; it never ends Creo, kills workers or "
                    "clears protections. Operator interruption (Ctrl+C) ends "
                    "the process and is the only way the OS lock is dropped "
                    "without proof."
                ),
            }
            if on_alert is not None:
                on_alert(alert)
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
            "seconds before the report records an unproven-settlement alert; "
            "the guard keeps holding the real lock and polling until a safe "
            "release is provable (default 1200)"
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
    # A genuinely absent jobs directory is fine; any other I/O error must
    # abort before the guard lock is taken (unreadable state is never
    # mistaken for "no jobs").
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

    def alert(update: dict):
        report["settle"] = update
        report["guard"]["action"] = (
            "settlement budget elapsed without proof; this entry is still "
            "holding the real guard lock and polling until a safe release is "
            "provable"
        )
        try:
            save()
        except OSError as exc:  # an unreadable report dir must never drop the lock
            print(f"guard report could not be written: {exc}", file=sys.stderr)

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
            "are confirmed terminal, no md050 native worker is alive and the "
            "md050 channel probe is free; child exit alone is not treated as "
            "completion evidence"
        ),
    }
    save()
    children_ok = True
    exit_code = 0
    settle = {
        "status": "quiet",
        "quiet": True,
        "released": True,
        "new_jobs": {},
        "note": "no children ran",
    }
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
                settle = _settle(
                    md050_root, md050_jobs, baseline, arguments.settle_timeout, on_alert=alert
                )
                report["settle"] = settle
                save()
                break
            # Child exit is not completion evidence: settle after EVERY child
            # so an unknown outcome or a still-running accepted job stops the
            # remaining drivers before they touch the session.
            settle = _settle(
                md050_root, md050_jobs, baseline, arguments.settle_timeout, on_alert=alert
            )
            report["settle"] = settle
            if settle["status"] != "quiet":
                children_ok = False
                exit_code = SETTLE_EXIT
                report["guard"]["action"] = (
                    "settlement after a child found an unknown outcome; "
                    "remaining children were not started and every md050 "
                    "protection is left untouched"
                )
                save()
                break
        # _settle returns only once a release is proven; the OS lock is freed
        # exactly here and nowhere else (operator Ctrl+C excepted).
        report["guard"]["status"] = "released"
        report["guard"]["action"] = (
            "settled: all jobs accepted during this run are terminal, no md050 "
            "native worker (checkpoint identity or creo_worker.exe image scan) "
            "is alive, and the md050 channel probe is free"
        )
        report["success"] = children_ok and settle["status"] == "quiet"
        save()
        _exit_guard(context, guard_root, original_root)
        print(
            json.dumps(
                {
                    "status": "ok" if report["success"] else settle["status"],
                    "report": str(destination),
                },
                ensure_ascii=False,
            )
        )
        return 0 if report["success"] else exit_code
    except KeyboardInterrupt:
        # Operator interruption: the process exit drops the OS byte lock. No
        # safety claim is made and md050 jobs/protections stay untouched.
        report["guard"]["status"] = "interrupted_while_holding"
        report["guard"]["action"] = (
            "operator interrupted the entry; the OS byte lock is dropped by "
            "process exit without any release-safety claim; md050 jobs and "
            "protections were not touched by this entry"
        )
        save()
        raise
    except BaseException as exc:
        # Driver-side exception (assertion, timeout, protocol error): still
        # settle before deciding, and never claim a safe release we cannot
        # prove. Md050 jobs and protections stay untouched either way. A
        # settle-internal failure is treated as unprovable: keep holding and
        # retry instead of dropping the OS lock early.
        report["guard"]["action"] = (
            f"guard run aborted with {type(exc).__name__}: {exc}; settling "
            "before any release decision, staying conservative"
        )
        save()
        while True:
            try:
                settle = _settle(
                    md050_root, md050_jobs, baseline, arguments.settle_timeout, on_alert=alert
                )
                break
            except KeyboardInterrupt:
                raise
            except Exception as settle_exc:  # noqa: BLE001 - stay conservative, keep the lock
                print(
                    f"guard settlement retry after {type(settle_exc).__name__}: {settle_exc}",
                    file=sys.stderr,
                )
                time.sleep(1)
        report["settle"] = settle
        report["guard"]["status"] = "released"
        report["guard"]["action"] = (
            f"guard run aborted with {type(exc).__name__}: {exc}; release was "
            "only performed after every accepted job reached a terminal state, "
            "no md050 native worker was alive and the channel probe was free; "
            "md050 protections were left untouched"
        )
        report["success"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
        save()
        _exit_guard(context, guard_root, original_root)
        print(
            json.dumps(
                {"status": "aborted", "error": report["error"], "report": str(destination)},
                ensure_ascii=False,
            )
        )
        return SETTLE_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
