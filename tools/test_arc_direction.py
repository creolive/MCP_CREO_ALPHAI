"""FEAT-034/T02 offline driver for the explicit arc direction.

Validates the strict "dir" contract, the legacy start/end regression numbers
and the independent analytic segment oracle against the analyzer, plus the
measured-arc result projection. Every expected value is computed by the oracle
in this file from the direction declared in the test input; no production
normalization or analysis helper is called to produce an expectation.

Default is strictly offline: no MCP client is instantiated and no Toolkit
connection is made. --live requires --confirm-session-usable and is refused
here: the live native acceptance of FEAT-034 runs as a separate integration
step on the shared dev service, never from this driver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import unittest
import uuid
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402

ROOT = SOURCE_PATHS.resource_root

RADIUS_MM = 10.0
DEPTH_MM = 5.0
VOLUME_90_MM3 = 125.0 * math.pi - 250.0
VOLUME_270_MM3 = 375.0 * math.pi + 250.0
VOLUME_TOLERANCE_MM3 = 0.01


# --- independent oracle (never calls production normalization) ------------


def oracle_sweep_deg(start_deg: float, end_deg: float, direction: int) -> float:
    if direction > 0:
        return (end_deg - start_deg) % 360.0
    return (start_deg - end_deg) % 360.0


def oracle_segment_volume_mm3(
    start_deg: float,
    end_deg: float,
    direction: int,
    radius: float = RADIUS_MM,
    depth: float = DEPTH_MM,
) -> float:
    theta = math.radians(oracle_sweep_deg(start_deg, end_deg, direction))
    return depth * 0.5 * radius * radius * (theta - math.sin(theta))


def on_circle(angle_deg: float) -> list[float]:
    angle = math.radians(angle_deg)
    return [RADIUS_MM * math.cos(angle), RADIUS_MM * math.sin(angle)]


def arc_entity(
    *,
    start_deg: float = 0.0,
    end_deg: float = 90.0,
    direction: int | None = None,
    name: str = "arc_a",
) -> dict:
    entity = {
        "type": "arc",
        "name": name,
        "center": [0.0, 0.0],
        "radius": RADIUS_MM,
        "start_angle": start_deg,
        "end_angle": end_deg,
    }
    if direction is not None:
        entity["dir"] = direction
    return entity


def arc_with_chord(
    start_deg: float = 0.0, end_deg: float = 90.0, direction: int | None = None
) -> list[dict]:
    chord = {
        "type": "line",
        "name": "chord",
        "start": on_circle(end_deg),
        "end": on_circle(start_deg),
    }
    return [arc_entity(start_deg=start_deg, end_deg=end_deg, direction=direction), chord]


def near(actual: float, expected: float, tolerance: float) -> None:
    assert math.isfinite(actual), actual
    assert abs(actual - expected) <= max(tolerance, abs(expected) * 1e-9), (actual, expected)


# --- checks ---------------------------------------------------------------


def check_contract() -> list[dict]:
    from pydantic import ValidationError

    from creo_mechdog.schema import Arc, SketchGeometryOp, SketchOp

    accepted = []
    for start_deg, end_deg, direction in (
        (0.0, 90.0, None),
        (0.0, 90.0, 1),
        (0.0, 90.0, -1),
        (0.0, 180.0, 1),
        (0.0, 270.0, 1),
        (350.0, 10.0, 1),
        (10.0, 350.0, -1),
    ):
        arc = Arc.model_validate(
            arc_entity(start_deg=start_deg, end_deg=end_deg, direction=direction)
        )
        expected_dir = 1 if direction is None else direction
        assert arc.dir == expected_dir, arc
        accepted.append(
            {
                "start_angle_deg": start_deg,
                "end_angle_deg": end_deg,
                "dir": direction,
                "accepted_dir": arc.dir,
            }
        )
        SketchOp(
            op="sketch",
            label="s1",
            entities=[arc_entity(start_deg=start_deg, end_deg=end_deg, direction=direction)],
        )
        SketchGeometryOp(
            op="update_sketch_geometry",
            sketch="s1",
            entities=[arc_entity(start_deg=start_deg, end_deg=end_deg, direction=direction)],
        )

    rejected = []
    for bad in (True, False, 1.0, -1.0, "1", None, 0, 2, -2, [1], {"dir": 1}):
        entity = arc_entity()
        entity["dir"] = bad
        try:
            Arc.model_validate(entity)
        except ValidationError as error:
            assert "strict integer" in str(error), (bad, error)
            rejected.append({"input": repr(bad), "reason": "strict_integer"})
        else:
            raise AssertionError(f"dir={bad!r} was accepted")

    for label, entity in (
        ("start_angle_inf", arc_entity(start_deg=float("inf"))),
        ("end_angle_nan", arc_entity(end_deg=float("nan"))),
        ("zero_sweep", arc_entity(start_deg=0.0, end_deg=0.0)),
        ("full_circle", arc_entity(start_deg=0.0, end_deg=360.0)),
        ("full_circle_wrapped", arc_entity(start_deg=90.0, end_deg=450.0)),
        ("full_circle_clockwise", arc_entity(start_deg=0.0, end_deg=360.0, direction=-1)),
    ):
        try:
            Arc.model_validate(entity)
        except ValidationError as error:
            assert label.endswith("inf") or label.endswith("nan") or "circle" in str(error), (
                label,
                error,
            )
            rejected.append({"input": label, "reason": "finite_or_circle"})
        else:
            raise AssertionError(f"{label} was accepted")
    return [{"accepted": accepted, "rejected": rejected}]


def check_legacy_oracle() -> list[dict]:
    from creo_mechdog.profile_diagnostics import analyze_profile, validate_solid_profile

    cases = (
        ("legacy_0_to_90", 0.0, 90.0, None, VOLUME_90_MM3),
        ("legacy_90_to_0", 90.0, 0.0, None, VOLUME_270_MM3),
        ("explicit_cw_90_to_0", 90.0, 0.0, -1, VOLUME_90_MM3),
        ("explicit_cw_0_to_90", 0.0, 90.0, -1, VOLUME_270_MM3),
    )
    checked = []
    for name, start_deg, end_deg, direction, expected in cases:
        entities = arc_with_chord(start_deg, end_deg, direction)
        report = analyze_profile(entities)
        volume = abs(report["material_area_mm2"]) * DEPTH_MM
        oracle = oracle_segment_volume_mm3(start_deg, end_deg, direction or 1)
        near(volume, oracle, VOLUME_TOLERANCE_MM3)
        near(volume, expected, VOLUME_TOLERANCE_MM3)
        validate_solid_profile(entities, "coordinates")
        checked.append(
            {
                "case": name,
                "start_angle_deg": start_deg,
                "end_angle_deg": end_deg,
                "dir": direction,
                "oracle_sweep_deg": oracle_sweep_deg(start_deg, end_deg, direction or 1),
                "oracle_volume_mm3": oracle,
                "analyzed_volume_mm3": volume,
                "expected_volume_mm3": expected,
                "abs_difference_mm3": abs(volume - expected),
            }
        )
    near(VOLUME_90_MM3 + VOLUME_270_MM3, DEPTH_MM * math.pi * RADIUS_MM**2, 1e-9)
    return checked


def check_sweeps_and_frames() -> list[dict]:
    from creo_mechdog.profile_diagnostics import analyze_profile

    sweeps = []
    for start_deg, end_deg, direction, expected in (
        (0.0, 180.0, 1, 180.0),
        (0.0, 270.0, 1, 270.0),
        (350.0, 10.0, 1, 20.0),
        (10.0, 350.0, 1, 340.0),
        (0.0, 90.0, -1, 270.0),
        (90.0, 0.0, -1, 90.0),
    ):
        echo = analyze_profile(
            [arc_entity(start_deg=start_deg, end_deg=end_deg, direction=direction)]
        )["arc_geometry"][0]
        near(echo["sweep_deg"], expected, 1e-9)
        near(oracle_sweep_deg(start_deg, end_deg, direction), expected, 1e-9)
        assert echo["source"] == "input", echo
        sweeps.append(
            {
                "start_angle_deg": start_deg,
                "end_angle_deg": end_deg,
                "dir": direction,
                "sweep_deg": echo["sweep_deg"],
                "start_uv": echo["start_uv"],
                "end_uv": echo["end_uv"],
                "start_tangent_uv": echo["start_tangent_uv"],
                "end_tangent_uv": echo["end_tangent_uv"],
                "frame": echo["frame"],
            }
        )

    turn = 37.0
    rotated = arc_with_chord(0.0, 90.0, 1)
    for entity in rotated:
        if entity["type"] == "arc":
            entity["center"] = [3.0, -2.0]
            entity["start_angle"] = turn
            entity["end_angle"] = 90.0 + turn
        else:
            start, end = on_circle(90.0 + turn), on_circle(turn)
            entity["start"] = [3.0 + start[0], -2.0 + start[1]]
            entity["end"] = [3.0 + end[0], -2.0 + end[1]]
    rotated_volume = abs(analyze_profile(rotated)["material_area_mm2"]) * DEPTH_MM
    near(rotated_volume, VOLUME_90_MM3, VOLUME_TOLERANCE_MM3)

    flipped = arc_with_chord(0.0, 90.0, 1)
    for entity in flipped:
        if entity["type"] == "arc":
            entity["start_angle"] = 0.0
            entity["end_angle"] = -90.0
            entity["dir"] = -1
        else:
            entity["start"] = on_circle(-90.0)
            entity["end"] = on_circle(0.0)
    flipped_report = analyze_profile(flipped)
    flipped_echo = flipped_report["arc_geometry"][0]
    assert flipped_echo["dir"] == -1, flipped_echo
    near(flipped_echo["sweep_deg"], 90.0, 1e-9)
    flipped_volume = abs(flipped_report["material_area_mm2"]) * DEPTH_MM
    near(flipped_volume, oracle_segment_volume_mm3(0.0, -90.0, -1), VOLUME_TOLERANCE_MM3)

    return [
        {"sweeps": sweeps},
        {
            "rotated_frame_volume_mm3": rotated_volume,
            "rotated_frame_expected_mm3": VOLUME_90_MM3,
            "flipped_frame_volume_mm3": flipped_volume,
            "flipped_frame_oracle_mm3": oracle_segment_volume_mm3(0.0, -90.0, -1),
            "flipped_frame_dir": flipped_echo["dir"],
            "flipped_frame_sweep_deg": flipped_echo["sweep_deg"],
        },
    ]


def check_edit_and_downstream() -> list[dict]:
    from pydantic import ValidationError

    from creo_mechdog.profile_diagnostics import analyze_profile
    from creo_mechdog.schema import SketchGeometryOp

    update = SketchGeometryOp(
        op="update_sketch_geometry",
        sketch="rev_sk",
        entities=arc_with_chord(0.0, 90.0, -1),
        dimensioning="autodim",
    )
    after = (
        abs(
            analyze_profile([entity.model_dump() for entity in update.entities])[
                "material_area_mm2"
            ]
        )
        * DEPTH_MM
    )
    near(after, VOLUME_270_MM3, VOLUME_TOLERANCE_MM3)

    illegal = []
    for label, entity in (
        ("dir_zero", arc_entity(direction=0)),
        ("dir_float", arc_entity(direction=-1.0)),
        ("full_circle", arc_entity(start_deg=45.0, end_deg=405.0)),
    ):
        try:
            SketchGeometryOp(op="update_sketch_geometry", sketch="rev_sk", entities=[entity])
        except ValidationError as error:
            illegal.append(
                {"input": label, "rejected": True, "message": str(error).splitlines()[0]}
            )
        else:
            raise AssertionError(f"{label} was accepted")

    before = abs(analyze_profile(arc_with_chord(0.0, 90.0, 1))["material_area_mm2"]) * DEPTH_MM
    near(before + after, DEPTH_MM * math.pi * RADIUS_MM**2, VOLUME_TOLERANCE_MM3)
    return [
        {
            "update_volume_mm3": after,
            "update_expected_mm3": VOLUME_270_MM3,
            "before_volume_mm3": before,
            "before_plus_after_mm3": before + after,
            "circle_volume_mm3": DEPTH_MM * math.pi * RADIUS_MM**2,
            "illegal_edits": illegal,
        }
    ]


def check_echo_projection() -> list[dict]:
    from creo_mechdog import operation_results

    entities = arc_with_chord(0.0, 90.0, -1)
    inputs = [{"op": "sketch", "label": "s1", "entities": entities}]

    measured = [
        {
            "name": "arc_a",
            "source": "native",
            "query_code": 0,
            "frame": "sketch_local",
            "start_uv": [1.0, 2.0],
            "end_uv": [3.0, 4.0],
            "start_tangent_uv": [0.0, -1.0],
            "end_tangent_uv": [1.0, 0.0],
            "dir": -1,
            "sweep_deg": 270.0,
        }
    ]
    projected = operation_results.annotate_native_result(
        {
            "success": True,
            "operations": [
                {
                    "op": "sketch",
                    "index": 0,
                    "label": "s1",
                    "succeeded": True,
                    "arc_geometry": measured,
                }
            ],
        },
        readonly=False,
        inputs=inputs,
    )["operations"][0]["arc_geometry"]
    assert projected[0]["source"] == "native", projected
    assert projected[0]["start_uv"] == [1.0, 2.0], projected

    unknown = operation_results.annotate_native_result(
        {
            "success": True,
            "operations": [{"op": "sketch", "index": 0, "label": "s1", "succeeded": True}],
        },
        readonly=False,
        inputs=inputs,
    )["operations"][0]["arc_geometry"]
    assert unknown[0]["source"] == "unknown", unknown
    for key in operation_results._ARC_MEASURED_FIELDS:
        assert unknown[0][key] is None, (key, unknown[0])
    assert unknown[0]["start_uv"] != on_circle(0.0), (
        "request values must never be echoed as measured"
    )

    coded = operation_results.annotate_native_result(
        {
            "success": True,
            "operations": [
                {
                    "op": "sketch",
                    "index": 0,
                    "label": "s1",
                    "succeeded": True,
                    "arc_geometry": [{"name": "arc_a", "source": "unknown", "query_code": 42}],
                }
            ],
        },
        readonly=False,
        inputs=inputs,
    )["operations"][0]["arc_geometry"]
    assert coded[0]["query_code"] == 42, coded

    return [
        {
            "native_projection": projected,
            "unknown_projection": unknown,
            "unknown_with_code": coded,
            "request_echo_forbidden": True,
        }
    ]


def run_unit_module() -> dict:
    from tests.unit import test_arc_direction

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_arc_direction)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    return {
        "module": "tests.unit.test_arc_direction",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "successful": result.wasSuccessful(),
    }


# --- provenance and report ------------------------------------------------


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    """Refuse to overwrite an existing report before anything else runs."""
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "arc_direction" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
    from creo_mechdog.source_provenance import local_provenance as collect

    evidence = collect(ROOT, ("tools/test_arc_direction.py", "tests/unit/test_arc_direction.py"))
    # Preserve the released report aliases while sharing source completeness checks.
    evidence["provenance_mode"] = "git" if evidence["git_status"] == "available" else "filesystem"
    evidence["git_unavailable"] = evidence["git_status"] != "available"
    evidence["commit"] = evidence["commit"] or ""
    evidence["branch"] = evidence["branch"] or ""
    return evidence


def write_offline_report(output: Path, run_id: str, results: dict) -> dict:
    report = {
        "task": "FEAT-034 / DEV-051 T02",
        "scope": "explicit arc direction: contract, legacy regression and independent oracle",
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: dir contract, legacy start/end regression, independent "
            "segment oracle and result echo projection validated. No Toolkit connection, "
            "no native geometry result."
        ),
        "oracle": {
            "radius_mm": RADIUS_MM,
            "depth_mm": DEPTH_MM,
            "volume_90_mm3": VOLUME_90_MM3,
            "volume_270_mm3": VOLUME_270_MM3,
            "independent_of_production_normalization": True,
        },
        "checks": results,
        "unit_module": run_unit_module(),
        "provenance": local_provenance(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.live and not args.confirm_session_usable:
        print("live runs require --confirm-session-usable", file=sys.stderr)
        return 2
    if args.live:
        print(
            "FEAT-034 live native acceptance is a separate integration step on the shared "
            "dev service; this driver never instantiates an MCP client or connects to Creo.",
            file=sys.stderr,
        )
        return 2

    run_id = new_run_id()
    output = resolve_output(args.output, run_id)
    results = {
        "contract": check_contract(),
        "legacy_oracle": check_legacy_oracle(),
        "sweeps_and_frames": check_sweeps_and_frames(),
        "edit_and_downstream": check_edit_and_downstream(),
        "echo_projection": check_echo_projection(),
    }
    report = write_offline_report(output, run_id, results)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name("report.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"report_sha256: {digest}")
    print(f"unit_module: {report['unit_module']}")
    return 0 if report["unit_module"]["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
