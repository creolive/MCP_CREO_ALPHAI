"""Check language regressions against reviewed debt, then run Windows unit tests."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import runpy
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = Path("docs/development/style-baseline.json")
CONFIG_FILES = ("pyproject.toml", ".clang-format", "requirements-dev.txt")
DEFAULT_UNIT_TIMEOUT_SECONDS = 900


def positive_seconds(text: str) -> int:
    """Parse a positive integer second budget, rejecting everything else."""
    try:
        seconds = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"must be a positive integer number of seconds: {text!r}"
        ) from None
    if seconds <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive number of seconds: {seconds}")
    return seconds


def read_source(path: Path) -> str:
    """Normalize checkout line endings so Windows Git settings do not alter the baseline."""
    return path.read_text(encoding="utf-8-sig")


def source_hash(path: Path) -> str:
    return hashlib.sha256(read_source(path).encode("utf-8")).hexdigest()


def command(args: list[str], *, cwd: Path, accepted: tuple[int, ...] = (0,)) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode not in accepted:
        raise RuntimeError(f"Command failed ({result.returncode}): {args}\n{result.stderr}")
    return result.stdout


def lint_entries(diagnostics: list[dict], root: Path) -> list[dict]:
    entries: Counter[tuple[str, str, str, str]] = Counter()
    for item in diagnostics:
        code = item.get("code")
        if not code or code == "invalid-syntax":
            raise RuntimeError("Python syntax errors cannot be accepted into the style baseline")
        path = Path(item["filename"]).resolve()
        relative = path.relative_to(root.resolve()).as_posix()
        lines = read_source(path).splitlines()
        row = item["location"]["row"]
        context = lines[row - 1].strip() if 1 <= row <= len(lines) else ""
        entries[(relative, code, item["message"], context)] += 1
    return [
        {"path": path, "code": code, "message": message, "source": context, "count": count}
        for (path, code, message, context), count in sorted(entries.items())
    ]


def collect_styles(root: Path) -> dict:
    # Import lazily: guard tests can run without launching a formatter or Creo.
    from clang_format import get_executable

    tool_versions = {name: importlib.metadata.version(name) for name in ("ruff", "clang-format")}
    for line in (root / "requirements-dev.txt").read_text(encoding="utf-8").splitlines():
        if "==" in line:
            name, expected = line.strip().split("==", 1)
            if name in tool_versions and tool_versions[name] != expected:
                raise RuntimeError(f"Install requirements-dev.txt: {name} must be {expected}")
    ruff = [sys.executable, "-m", "ruff"]
    lint = json.loads(
        command(ruff + ["check", ".", "--output-format", "json"], cwd=root, accepted=(0, 1))
    )
    formatted = json.loads(
        command(
            ruff + ["format", "--check", "--output-format", "json", "."],
            cwd=root,
            accepted=(0, 1),
        )
    )
    formatting = {}
    for item in formatted:
        path = Path(item["filename"]).resolve()
        formatting[path.relative_to(root.resolve()).as_posix()] = source_hash(path)
    cpp_files = sorted(
        path
        for path in (root / "native").rglob("*")
        if path.suffix in {".cpp", ".h", ".hpp", ".c", ".cxx"}
        and "third_party" not in path.relative_to(root / "native").parts
    )
    for path in cpp_files:
        rendered = command(
            [get_executable("clang-format"), "--style=file", "--fallback-style=none", str(path)],
            cwd=root,
        )
        if rendered != read_source(path):
            formatting[path.relative_to(root).as_posix()] = source_hash(path)
    python_files = [
        Path(line)
        for line in command(ruff + ["check", "--show-files", "."], cwd=root).splitlines()
        if line.strip()
    ]
    source = hashlib.sha256()
    for path in sorted(python_files + cpp_files):
        source.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        source.update(source_hash(path).encode("ascii") + b"\n")
    return {
        "schema_version": 1,
        "tool_versions": tool_versions,
        "configuration": {name: source_hash(root / name) for name in CONFIG_FILES},
        "lint": lint_entries(lint, root),
        "unformatted": dict(sorted(formatting.items())),
        "cpp_files_checked": len(cpp_files),
        "python_files_checked": len(python_files),
        "source_sha256": source.hexdigest(),
    }


def lint_counter(entries: list[dict]) -> Counter:
    return Counter(
        {
            (item["path"], item["code"], item["message"], item["source"]): item["count"]
            for item in entries
        }
    )


def regressions(current: dict, baseline: dict) -> list[str]:
    errors = []
    for key in ("schema_version", "tool_versions", "configuration"):
        if current[key] != baseline.get(key):
            errors.append(f"Baseline {key} differs; review the change before updating the baseline")
    for (path, code, message, context), count in (
        lint_counter(current["lint"]) - lint_counter(baseline.get("lint", []))
    ).items():
        errors.append(f"{path}: {code} {message} ({count} new): {context}")
    for path, digest in current["unformatted"].items():
        if baseline.get("unformatted", {}).get(path) != digest:
            errors.append(f"{path}: new or changed file must pass its formatter")
    return errors


def git_state(root: Path) -> dict:
    try:
        repository = Path(command(["git", "rev-parse", "--show-toplevel"], cwd=root).strip())
        if repository.resolve() != root.resolve():
            return {"commit": None, "dirty": None}
        commit = command(["git", "rev-parse", "HEAD"], cwd=root).strip()
        dirty = bool(command(["git", "status", "--porcelain"], cwd=root).strip())
        return {"commit": commit, "dirty": dirty}
    except (OSError, RuntimeError):
        return {"commit": None, "dirty": None}


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict", action="store_true", help="Reject all debt, ignoring the baseline"
    )
    parser.add_argument(
        "--skip-unit", action="store_true", help="Check styles only; never native proof"
    )
    parser.add_argument(
        "--unit-timeout-seconds",
        type=positive_seconds,
        default=DEFAULT_UNIT_TIMEOUT_SECONDS,
        help="Positive unit-test budget in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--write-baseline", action="store_true", help="Explicit reviewed debt snapshot"
    )
    parser.add_argument("--reason", help="Work-item ID and rationale for a baseline change")
    parser.add_argument("--work-item", help="Work-item ID for this validation run")
    args = parser.parse_args(argv)
    if args.write_baseline and (not args.reason or not args.reason.strip()):
        parser.error("--write-baseline requires --reason with the work-item ID and rationale")
    if args.write_baseline and args.strict:
        parser.error("--write-baseline cannot be combined with --strict")
    report = {
        "work_item": args.work_item,
        "version": runpy.run_path(str(ROOT / "version.py"))["VERSION"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"os": platform.system(), "python": platform.python_version()},
        "source": git_state(ROOT),
        "native_validation": "not_run",
        "unit_tests": "not_run",
        "unit_test_timeout_seconds": args.unit_timeout_seconds,
        "success": False,
    }
    try:
        current = collect_styles(ROOT)
        report["style_summary"] = {
            "lint_findings": sum(item["count"] for item in current["lint"]),
            "unformatted_files": len(current["unformatted"]),
            "cpp_files_checked": current["cpp_files_checked"],
            "python_files_checked": current["python_files_checked"],
        }
        report["source"]["checked_source_sha256"] = current["source_sha256"]
        report["tools"] = current["tool_versions"]
        report["configuration"] = current["configuration"]
        if args.write_baseline:
            baseline = {
                **current,
                "reason": args.reason,
                "timestamp_utc": report["timestamp_utc"],
                "source": report["source"],
            }
            save_json(ROOT / BASELINE, baseline)
            report["baseline_written"] = True
        elif args.strict:
            if current["lint"] or current["unformatted"]:
                raise RuntimeError(
                    "Strict style checks failed; see style_summary for remaining debt"
                )
        else:
            baseline = json.loads((ROOT / BASELINE).read_text(encoding="utf-8"))
            errors = regressions(current, baseline)
            if errors:
                report["regressions"] = errors
                raise RuntimeError(
                    f"{len(errors)} style regression(s); see build/development_check.json"
                )
        if not args.skip_unit:
            if os.name != "nt":
                raise RuntimeError("Run unit validation on Windows; --skip-unit is styles only")
            report["unit_tests"] = "running"
            try:
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools/test_unit.py")],
                    cwd=ROOT,
                    timeout=args.unit_timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                report["unit_tests"] = "timed_out"
                raise
            report["unit_tests"] = "passed" if result.returncode == 0 else "failed"
            if result.returncode:
                raise RuntimeError("Unit validation failed")
        report["success"] = True
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
        report["error"] = str(exc)
    save_json(ROOT / "build/development_check.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
