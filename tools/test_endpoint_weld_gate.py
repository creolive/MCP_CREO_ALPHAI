"""BUG-101: endpoint weldability gate driver (offline only).

The 0.10.0 feedback reported a 10-ring/40-arc sketch whose endpoints closed only
through the 1e-4 mm clustering tolerance (max gap 8.215e-7 mm): counts looked
perfect, extrude returned ProFeatureWithoptionsCreate=-1, and the snapped copy
(7.83e-13 mm) succeeded at volume 1849.8028532376422 mm3. The original
gear10.json / gear10_snapped.json are still missing (BUG-049), so this driver
uses fixed square substitutes and never claims to replay that case.

What is locked offline:

* the reported gap bracket (7.83e-13 usable, 8.215e-7 rejected) maps to
  weldable=True / weldable=False against the published 1e-9 mm epsilon;
* an explicit weld_tolerance_mm request is reported as such and can only be set
  by the caller, never inferred;
* the sketch profile publishes the verdict and a bounded pair sample, so the
  caller learns it before extruding;
* the native extrude failure message names the cluster spread instead of
  "the cause is not determined" when a section closes through tolerance.

No Toolkit connection is made. The live stage (which gap the kernel actually
welds on this machine) belongs to the single assigned session and is not
implemented here; ``native_acceptance`` is therefore always ``not_run``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog import operation_results, profile_diagnostics  # noqa: E402
from creo_mechdog.weldability import WELD_TOLERANCE_MM, weldability_from_report  # noqa: E402

ROOT = _SOURCE_ROOT
SIDE_MM = 10.0
# 7.83e-13 and 8.215e-7 bracket the kernel behaviour reported on 2026-10-31.
GAP_SAMPLES_MM = (0.0, 7.83e-13, 5.60521460071685e-07, 8.21534262415399e-07, 9.99e-05, 2e-04)
EXPECTED = {
    0.0: (True, True),
    7.83e-13: (True, True),
    5.60521460071685e-07: (True, False),
    8.21534262415399e-07: (True, False),
    9.99e-05: (True, False),
    2e-04: (False, False),
}


def square(gap_mm: float) -> list[dict[str, Any]]:
    """A closed-at-tolerance square whose last endpoint stops ``gap_mm`` short."""
    return [
        {"type": "line", "name": "s0", "start": [0.0, 0.0], "end": [SIDE_MM, 0.0]},
        {"type": "line", "name": "s1", "start": [SIDE_MM, 0.0], "end": [SIDE_MM, SIDE_MM]},
        {"type": "line", "name": "s2", "start": [SIDE_MM, SIDE_MM], "end": [0.0, SIDE_MM]},
        {"type": "line", "name": "s3", "start": [0.0, SIDE_MM], "end": [gap_mm, 0.0]},
    ]


def analyze(gap_mm: float) -> dict[str, Any]:
    entities = square(gap_mm)
    report = profile_diagnostics.analyze_profile(entities)
    verdict = weldability_from_report(report)
    projected: dict[str, Any] = {}
    result = {"operations": [{"op": "sketch", "index": 0, "label": "gate", "succeeded": True}]}
    operation_results.annotate_profiles(
        result, [{"op": "sketch", "label": "gate", "entities": entities}]
    )
    projected = result["operations"][0].get("profile", {})
    closed, weldable = EXPECTED[gap_mm]
    observed = projected.get("weldability", {})
    return {
        "gap_mm": gap_mm,
        "closed_contour_count": report["closed_contour_count"],
        "open_contour_count": report["open_contour_count"],
        "expected_closed": closed,
        "expected_weldable": weldable,
        "weldable": verdict["weldable"],
        "max_endpoint_gap_mm": verdict["max_endpoint_gap_mm"],
        "exceeding_pairs_total": verdict["exceeding_pairs"]["total"],
        "sample_size": len(verdict["exceeding_pairs"]["sample"]),
        "note": verdict["note"],
        "projection_matches": observed.get("weldable") == verdict["weldable"],
        "passed": (
            (report["closed_contour_count"] > 0) == closed
            and verdict["weldable"] is weldable
            and observed.get("weldable") == verdict["weldable"]
        ),
    }


def explicit_tolerance_checks() -> dict[str, Any]:
    report = profile_diagnostics.analyze_profile(square(8.21534262415399e-07))
    loosened = weldability_from_report(report, weld_tolerance_mm=1e-6)
    rejected = False
    try:
        weldability_from_report(report, weld_tolerance_mm=0.0)
    except ValueError:
        rejected = True
    return {
        "measured_tolerance_mm": WELD_TOLERANCE_MM,
        "requested_verdict": loosened["weldable"],
        "requested_source": loosened["tolerance_source"],
        "zero_tolerance_rejected": rejected,
        "passed": (
            loosened["weldable"] is True
            and loosened["tolerance_source"] == "request"
            and rejected
            and WELD_TOLERANCE_MM == profile_diagnostics.EXACT_TOLERANCE_MM
        ),
    }


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "bug101_weld_gate" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict[str, Any]:
    from version import VERSION

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout.strip()

    names = set(
        git("ls-files", "--", "*.py", "native/*.h", "native/*.hpp", "native/*.cpp").splitlines()
    )
    names.update(("tools/test_endpoint_weld_gate.py", "tests/unit/test_endpoint_weld_gate.py"))
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in sorted(names)
        if (ROOT / name).exists()
    }
    return {
        "version": VERSION,
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "dirty": bool(git("status", "--porcelain")),
        "source_sha256": hashes,
        "source_fingerprint": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "auto_start_creo": False,
        "human_session_confirmation": True,
    }


def offline_checks(run_id: str) -> dict[str, Any]:
    cases = [analyze(gap) for gap in GAP_SAMPLES_MM]
    tolerance = explicit_tolerance_checks()
    passed = all(case["passed"] for case in cases) and tolerance["passed"]
    return {
        "task": "BUG-101 / R10-01 endpoint weldability gate",
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: substitute square fixtures, published 1e-9 mm epsilon, sketch "
            "projection lock. No Toolkit connection and no claim about which gaps this machine's "
            "kernel welds; the live bracket belongs to the assigned session."
        ),
        "missing_originals": ["scripts/gear10.json", "scripts/gear10_snapped.json"],
        "weld_tolerance_mm": WELD_TOLERANCE_MM,
        "cases": cases,
        "explicit_tolerance": tolerance,
        "passed": passed,
        "provenance": local_provenance(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None, help="report path (never overwritten)")
    args = parser.parse_args(argv)
    run_id = new_run_id()
    output = resolve_output(args.output, run_id)
    report = offline_checks(run_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for case in report["cases"]:
        print(
            f"gap={case['gap_mm']:.6g} closed={case['closed_contour_count']} "
            f"weldable={case['weldable']} pairs={case['exceeding_pairs_total']}"
        )
    print(f"report: {output}")
    print("offline: PASS" if report["passed"] else "offline: FAIL")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
