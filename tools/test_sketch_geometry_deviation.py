"""Q02 geometry fidelity driver: sketch solve deviation, default offline.

Builds and validates the case matrix for the unified ``geometry_deviation``
contract (sketch create + in-place edit, coordinates/autodim/auto modes,
principal and dictionary planes, default and explicit ``geometry_tolerance_mm``).
The arc-mixed contour is a rounded equilateral triangle whose area, radius and
prism volume come from independent analytic formulas, not from the feedback's
approximate reference values.

Default mode never touches Creo. ``--live --confirm-session-usable`` runs the
matrix against a real session; that phase belongs to the integration owner and
is refused unless both flags are given.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creo_mechdog.geometry_deviation import (
    AUTODIM_WARNING_THRESHOLD_MM,
    COORDINATES_DEFAULT_TOLERANCE_MM,
)
from creo_mechdog.schema import validate_operations

TRIANGLE_CIRCUMRADIUS_MM = 30.0
FILLET_RADIUS_MM = 8.0
INTERIOR_ANGLE_DEG = 60.0
CORNER_ANGLES_DEG = (90.0, 210.0, 330.0)
EXTRUDE_DEPTH_MM = 10.0
TILTED_U_AXIS = [0.809017, -0.587785, 0.0]


def _xy(distance: float, angle_deg: float) -> list[float]:
    a = math.radians(angle_deg)
    return [distance * math.cos(a), distance * math.sin(a)]


def fillet_center(corner_deg: float) -> list[float]:
    offset = FILLET_RADIUS_MM / math.sin(math.radians(INTERIOR_ANGLE_DEG / 2))
    return _xy(TRIANGLE_CIRCUMRADIUS_MM - offset, corner_deg)


def tangent_point(corner_deg: float, side_offset_deg: float) -> list[float]:
    center = fillet_center(corner_deg)
    foot = _xy(FILLET_RADIUS_MM, corner_deg + side_offset_deg)
    return [center[0] + foot[0], center[1] + foot[1]]


def rounded_triangle_entities() -> list[dict]:
    entities = []
    for index, corner in enumerate(CORNER_ANGLES_DEG):
        nxt = CORNER_ANGLES_DEG[(index + 1) % len(CORNER_ANGLES_DEG)]
        entities.append(
            {
                "type": "line",
                "name": f"side_{index}",
                "start": tangent_point(corner, 60.0),
                "end": tangent_point(nxt, -60.0),
            }
        )
        entities.append(
            {
                "type": "arc",
                "name": f"fillet_{index}",
                "center": fillet_center(corner),
                "radius": FILLET_RADIUS_MM,
                "start_angle": corner - 60.0,
                "end_angle": (corner + 60.0) % 360.0,
                "dir": 1,
            }
        )
    return entities


def oracle_area_mm2() -> float:
    hexagon = []
    for corner in CORNER_ANGLES_DEG:
        hexagon.append(tangent_point(corner, -60.0))
        hexagon.append(tangent_point(corner, 60.0))
    shoelace = abs(
        sum(
            hexagon[i][0] * hexagon[(i + 1) % len(hexagon)][1]
            - hexagon[(i + 1) % len(hexagon)][0] * hexagon[i][1]
            for i in range(len(hexagon))
        )
    ) / 2
    sweep = math.radians(180.0 - INTERIOR_ANGLE_DEG)
    segment = 0.5 * FILLET_RADIUS_MM**2 * (sweep - math.sin(sweep))
    return shoelace + 3 * segment


def oracle_volume_mm3() -> float:
    return oracle_area_mm2() * EXTRUDE_DEPTH_MM


MODES = ("coordinates", "autodim", "auto")
TOLERANCE_SIDES = ("default", "explicit")
PLANES = ("XY", "dictionary_tilted")


def sketch_op(mode: str, tolerance_side: str, plane: str, *, edit: bool = False) -> dict:
    tolerance = (
        0.002 if mode == "autodim" else 4 * COORDINATES_DEFAULT_TOLERANCE_MM
    )
    op = {
        "op": "update_sketch_geometry" if edit else "sketch",
        **({} if edit else {"label": "profile", "plane": "XY" if plane == "XY" else {
            "reference": {"kind": "datum_plane", "id": 11},
            "origin": [0.0, 0.0, 0.0],
            "u_axis": TILTED_U_AXIS,
        }}),
        **({} if not edit else {"sketch": "profile"}),
        "entities": rounded_triangle_entities(),
        "dimensioning": mode,
    }
    if tolerance_side == "explicit":
        op["geometry_tolerance_mm"] = tolerance
    return op


def build_plan(mode: str, tolerance_side: str, plane: str) -> list[dict]:
    """Create, solidify, edit in place: the two-stage measurement follows both."""
    return [
        sketch_op(mode, tolerance_side, plane),
        {"op": "extrude", "label": "solid", "sketch": "profile", "depth": EXTRUDE_DEPTH_MM},
        sketch_op(mode, tolerance_side, plane, edit=True),
    ]


def build_cases(run_tag: str) -> list[dict]:
    cases = []
    for mode_index, mode in enumerate(MODES):
        for tolerance_side in TOLERANCE_SIDES:
            for plane in PLANES:
                name = f"{mode}_{tolerance_side}_{plane}"
                cases.append(
                    {
                        "case": name,
                        "model_name": f"q02_{mode_index:02d}_{tolerance_side[:2]}_{plane[:2]}_{run_tag}",
                        "new_part_required": True,
                        "operations": build_plan(mode, tolerance_side, plane),
                        "expected": {
                            "profile_area_mm2": oracle_area_mm2(),
                            "prism_volume_mm3": oracle_volume_mm3(),
                            "arc_radius_mm": FILLET_RADIUS_MM,
                            "arc_entity_names": [f"fillet_{i}" for i in range(3)],
                            "identity_rule": "sample entity names must match input names",
                            "two_stage_scope": ["section_regenerate", "complete_feature"],
                        },
                    }
                )
    # Negative admission cases (offline only): the strict tolerance contract.
    cases.append(
        {
            "case": "rejected_bool_tolerance",
            "operations": [sketch_op("coordinates", "default", "XY")
                           | {"geometry_tolerance_mm": True}],
            "expect_admission_error": True,
        }
    )
    cases.append(
        {
            "case": "rejected_zero_tolerance",
            "operations": [sketch_op("coordinates", "default", "XY")
                           | {"geometry_tolerance_mm": 0}],
            "expect_admission_error": True,
        }
    )
    cases.append(
        {
            "case": "rejected_negative_tolerance",
            "operations": [sketch_op("autodim", "default", "XY")
                           | {"geometry_tolerance_mm": -1e-3}],
            "expect_admission_error": True,
        }
    )
    return cases


def validate_cases(cases: list[dict]) -> None:
    names = [case.get("model_name") for case in cases if case.get("model_name")]
    if len(names) != len(set(names)):
        raise ValueError("duplicate model name")
    for case in cases:
        if len(case["model_name"]) > 31 if "model_name" in case else False:
            raise ValueError("model name too long")
        if case.get("expect_admission_error"):
            try:
                validate_operations(case["operations"])
            except Exception:
                continue
            raise ValueError(f"{case['case']} was expected to be rejected")
        validate_operations(case["operations"])
    if len(cases) != len(MODES) * len(TOLERANCE_SIDES) * len(PLANES) + 3:
        raise ValueError("incomplete case matrix")


def provenance() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True, timeout=15
        ).stdout.strip()

    names = set(
        git("ls-files", "--", "*.py", "native/*.h", "native/*.hpp", "native/*.cpp").splitlines()
    )
    names.update(
        {"tools/test_sketch_geometry_deviation.py", "tests/unit/test_sketch_geometry_deviation.py"}
    )
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in sorted(names)
    }
    return {
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "dirty": bool(git("status", "--porcelain")),
        "source_fingerprint": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
    }


def offline_report(run_tag: str) -> dict:
    cases = build_cases(run_tag)
    validate_cases(cases)
    return {
        "task": "Q02 geometry fidelity (FEAT-010/BUG-049)",
        "mode": "offline",
        "live_run": False,
        "default_thresholds": {
            "coordinates_rejection_mm": COORDINATES_DEFAULT_TOLERANCE_MM,
            "autodim_warning_mm": AUTODIM_WARNING_THRESHOLD_MM,
            "sample_limit": 20,
        },
        "fixture": "rounded_equilateral_triangle_3_lines_3_arcs",
        "independent_oracle": {
            "area_mm2": oracle_area_mm2(),
            "prism_volume_mm3": oracle_volume_mm3(),
            "area_formula": "tangent-point hexagon shoelace + 3 circular segments",
            "note": "feedback reference values are not used as assertions",
        },
        "cases": cases,
        "native_acceptance": "not_run",
        "provenance": provenance(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.live and not args.confirm_session_usable:
        parser.error("--live requires --confirm-session-usable and verified session admission")
    run_tag = uuid.uuid4().hex[:8]
    report = offline_report(run_tag)
    if args.live:
        # The live phase belongs to the integration owner: it drives a real
        # session through the case matrix and asserts the geometry_deviation
        # contract, revision, rollback and save/reload evidence per case.
        # Offline-phase builds the matrix only; live execution is not
        # implemented here so it can never bypass admission checks.
        report["live_execution"] = (
            "prepared_only; run by integration owner with verified admission"
        )
    path = args.output or ROOT / "build" / "sketch_geometry_deviation" / run_tag / "report.json"
    if path.exists():
        parser.error(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
