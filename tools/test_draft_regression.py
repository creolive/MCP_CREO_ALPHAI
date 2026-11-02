"""BUG-102: draft-on-chamfered-face regression driver (offline stage only).

The 0.10.0 feedback reports that a 40x30x10 block with chamfer(2) and round(R3)
accepted a 10 deg draft in 0.9.0 (+264.19 mm3) and fails with
``ProFeatureWithoptionsCreate=-1`` in 0.10.0. FEAT-051 added three element-tree
flags to the same code path, so the first thing to prove is *which* variable
changed the outcome - not to assume the geometry is impossible.

Offline stage (this script):

* freezes the reported fixture and the single-variable A/B element sets;
* proves the native code still carries both the flags under test and the
  failure receipt fields;
* prints the exact live steps the assigned session must run, in order.

No Toolkit connection is made, no geometry is created, and nothing here claims
the regression is fixed or that the geometry is invalid. ``live_stage`` is
always ``not_run``.
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

ROOT = _SOURCE_ROOT
FIXTURE = {
    "block": {"length_mm": 40.0, "width_mm": 30.0, "height_mm": 10.0, "volume_mm3": 12000.0},
    "chamfer": {"size_mm": 2.0, "reported_delta_mm3": -20.0},
    "round": {"radius_mm": 3.0, "reported_delta_mm3": -19.314168},
    "draft": {"angle_deg": 10.0, "surface_id_reported": 69},
    "reported_deltas_mm3": {"0.9.0_flip_false": 264.19, "0.9.0_flip_true": -264.79},
}

# Single-variable A/B: only one element flag changes per variant. The current
# production tree is A; B removes the FEAT-051 additions so a live run can tell
# element-tree tightening apart from a genuinely infeasible angle.
VARIANTS = {
    "A_current": {
        "PRO_E_DRAFT_TWEAK_OR_INTERSEC": "PRO_DRAFT_UI_INTERSECT",
        "PRO_E_DRAFT_EXTEND": "PRO_DRAFT_UI_NO_EXTEND",
        "PRO_E_DRAFT_SPLIT": "PRO_DRAFT_UI_SPLIT_NONE",
    },
    "B_no_extend": {
        "PRO_E_DRAFT_TWEAK_OR_INTERSEC": "PRO_DRAFT_UI_INTERSECT",
        "PRO_E_DRAFT_EXTEND": None,
        "PRO_E_DRAFT_SPLIT": "PRO_DRAFT_UI_SPLIT_NONE",
    },
    "B_no_split": {
        "PRO_E_DRAFT_TWEAK_OR_INTERSEC": "PRO_DRAFT_UI_INTERSECT",
        "PRO_E_DRAFT_EXTEND": "PRO_DRAFT_UI_NO_EXTEND",
        "PRO_E_DRAFT_SPLIT": None,
    },
    "B_no_intersect": {
        "PRO_E_DRAFT_TWEAK_OR_INTERSEC": None,
        "PRO_E_DRAFT_EXTEND": "PRO_DRAFT_UI_NO_EXTEND",
        "PRO_E_DRAFT_SPLIT": "PRO_DRAFT_UI_SPLIT_NONE",
    },
}

LIVE_STEPS = (
    "Confirm session usability (no unknown protection, no accepted job pending); never launch, "
    "restart or stop Creo from the driver.",
    "new part 40x30x10, chamfer size 2, round R3; inspect and record the surface id actually "
    "used for the side face (do not reuse the reported id 69).",
    "Variant A: draft angle 10, flip false, neutral plane = the side face's normal plane; record "
    "the terminal state, error text and draft_failure block if it fails.",
    "Variant B (one flag removed per run, rebuild between runs): repeat the same draft and record "
    "whether it succeeds; a single change from fail to success identifies the element flag.",
    "If both A and B fail while angle 5 succeeds on the same face, classify the case as a geometry "
    "conflict and record the angle sweep (5, 7.5, 10) instead of a flag regression.",
)


def native_source(name: str) -> str:
    return (ROOT / "native" / name).read_text(encoding="utf-8")


def offline_checks() -> dict[str, Any]:
    source = native_source("advanced.cpp")
    draft = source[
        source.index("static J generic_draft(") : source.index("static void generic_sweep(")
    ]
    flags = []
    for name, values in VARIANTS.items():
        present = {flag: (value is None or value in draft) for flag, value in values.items()}
        flags.append({"variant": name, "expected_flags": values, "present_in_source": present})
    checks = {
        "fixture_frozen": FIXTURE["draft"]["angle_deg"] == 10.0
        and FIXTURE["chamfer"]["size_mm"] == 2.0
        and FIXTURE["round"]["radius_mm"] == 3.0,
        "flags_present_in_current_tree": all(
            value in draft for value in VARIANTS["A_current"].values()
        ),
        "failure_receipt_fields": all(
            token in draft
            for token in ("draft_failure", "requested_flip", "element_errors", "classification")
        ),
        "no_geometry_verdict_in_driver": "infeasible" not in json.dumps(FIXTURE),
    }
    checks["passed"] = all(value for key, value in checks.items() if key != "passed")
    return {
        "task": "BUG-102 / R10-02 draft regression A/B",
        "mode": "offline",
        "live_stage": "not_run",
        "statement": (
            "Offline stage only: fixture, A/B element sets and receipt fields frozen. No Toolkit "
            "connection, no geometry created, no verdict on whether the regression is fixed."
        ),
        "fixture": FIXTURE,
        "variants": flags,
        "live_steps": list(LIVE_STEPS),
        "checks": checks,
    }


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "bug102_draft" / run_id / "report.json"
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

    names = set(git("ls-files", "--", "*.py", "native/*.h", "native/*.cpp").splitlines())
    names.update(("tools/test_draft_regression.py", "tests/unit/test_draft_observation.py"))
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    run_id = new_run_id()
    output = resolve_output(args.output, run_id)
    report = {"run_id": run_id, **offline_checks(), "provenance": local_provenance()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for check, value in report["checks"].items():
        print(f"{check}: {value}")
    print(f"report: {output}")
    print("offline: PASS" if report["checks"]["passed"] else "offline: FAIL")
    return 0 if report["checks"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
