"""Guard-root developer live-run entry (0.5.0 feedback batch 2, stage 2).

The main checkout service (E:\\Projects\\MCP_CREO_MechDog) normally owns the
Creo session. To run md050 final-source live drivers without the old service
touching the same Creo concurrently, this entry first holds the REAL toolkit
channel lock of the main worktree, then runs one or more md050 test child
processes sequentially. md050 children keep holding their own worktree lock
as usual; the two lock files are independent.

Guard discipline:
* non-blocking only — a busy guard lock stops immediately (exit code 2),
  never queues, retries, clears old owners or unknown protection;
* the guard covers the full child lifetime; child drivers poll every accepted
  job to a terminal state before exiting, so the guard cannot be released
  while an accepted job is still unfinished;
* nothing about the production lock mechanism changes — the guard is a local
  ROOT binding inside this developer entry, not a production config API.

Example:
.venv\\Scripts\\python.exe tools\\guarded_live_run.py ^
    --guard-root E:\\Projects\\MCP_CREO_MechDog ^
    --run ".venv\\Scripts\\python.exe tools\\test_assembly_matrix.py --session-health-verified" ^
    --run ".venv\\Scripts\\python.exe tools\\test_assembly_pipeline.py --session-health-verified"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import bridge
from creo_mechdog.paths import SOURCE_PATHS
from tools.dev_check import git_state, source_hash

ROOT = SOURCE_PATHS.resource_root
BUSY_EXIT = 2


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
    arguments = parser.parse_args(argv)
    guard_root = Path(arguments.guard_root).resolve()
    if not guard_root.is_dir():
        raise SystemExit(f"Guard root is not a directory: {guard_root}")
    if guard_root == ROOT.resolve():
        raise SystemExit("Guard root must differ from this md050 worktree")
    directory = _report_dir()
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "guard_root": str(guard_root),
        "md050_root": str(ROOT),
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
        "note": "guard held for the full child lifetimes; released only after the last child exits",
    }
    save()
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
                report["guard"]["action"] = (
                    "a child failed; remaining children were not started; the guard "
                    "was still released normally and the scene was left untouched"
                )
                save()
                return result.returncode
    finally:
        _exit_guard(context, guard_root, original_root)
        report["guard"]["status"] = "released"
        save()
    report["success"] = True
    save()
    print(json.dumps({"status": "ok", "report": str(destination)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
