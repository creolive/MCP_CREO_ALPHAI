"""BUG-064/087 T06 offline sketch-order fixture; never connects to Creo.

The missing original 30-segment slot is represented by a regular 30-gon
made of 30 independent line entities. Its area comes from geometry, not from
the historical profile report. ``--live`` deliberately refuses in this phase.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creo_mechdog.schema import validate_operations
from tools.test_dev049_tilted_cut import TILTED_FIXTURE, setup_operations, tilted_normal

SIDES = 30
RADIUS_MM = 5.0
RECTANGLE = {"type": "rectangle", "name": "rect", "min": [-4.0, -3.0], "max": [0.0, 3.0]}
ORDERS = (
    "rectangle_then_polygon",
    "polygon_then_rectangle",
    "new_face_rectangle",
    "fresh_part_rectangle",
)
STRATEGIES = ("autodim", "coordinates")
REFERENCES = ("datum_plane_id", "datum_feature_label")
SECOND_REFERENCES = ("available", "unavailable_candidate")

# --- BUG-097: four-stage separation and the smoke 3pt fixture -------------
#
# The plan requires the failure to be located to exactly one of four stages:
# frame validation, UV write, SectionRegenerate, CompleteFeature. The native
# log carries one marker family per stage; this scanner classifies a captured
# native.log (or a synthetic fixture in the unit tests) without a session.

STAGE_MARKERS = {
    "frame_validation": (
        "SKETCH_ANCHOR_PLANE=",
        "SKETCH_ANCHOR_AXIS=",
        "SKETCH_ANCHOR_SKIPPED=",
        "SKETCH_REFERENCE_INCOMPLETE",
        "PROJECT_REFERENCE",
        "SECTION_MATRIX_",
        "parallel to the support plane normal",
        "Sketch support must be planar",
        "No sketch orientation reference",
    ),
    "uv_write": (
        "SECTION_LOCATION_IDENTITY=",
        "COORDINATE_AXES ",
        "LINE_",
        "COORDINATE_DEVIATION",
    ),
    "section_regenerate": (
        "SKETCH_SOLVE=",
        "AutodimensionSketch=",
        "SectionRegenerate=",
        "SECTION_ERRORS phase=",
        "RegenerateSolvedSketch",
    ),
    "complete_feature": (
        "CompleteFeature=",
        "feature_error element=",
    ),
}

# smoke_3pt_min_repro.json (archived original 06_P12_v12_配方), re-expressed in
# this repository's contracts. The datum_plane reference uses the planned
# FEAT-053 explicit kind; until that schema lands, the fixture is recorded as
# blocked instead of being validated against a contract that does not exist.
# The external identity-only fallback is NOT copied: expectations below are
# derived from the frame semantics oracle in test_dev048_plane_frame.
SMOKE_3PT_POINTS = {
    "dpa0": [-95.191114, 40.0, -88.395141],
    "dpb0": [95.191114, 40.0, 88.395141],
    "dpd0": [94.701973, 50.416667, 89.27114],
}
SMOKE_3PT_TRIANGLE_UV = [[0.0, 0.0], [190.382228, 22.394433], [189.893088, 32.838154]]
SMOKE_3PT_DEPTH_MM = 9.87008714331235  # original precision, never rounded to 9.87
SMOKE_3PT_REPORTED_NORMAL = [-0.678, -0.093, 0.730]  # external report, 3-decimal rounding


def smoke_3pt_min_repro_operations() -> list[dict]:
    """The archived minimum case with an explicit three-point reference kind."""
    return [
        {
            "op": "datum_points",
            "label": "dpa0",
            "points": [{"name": "pa", "position": list(SMOKE_3PT_POINTS["dpa0"])}],
        },
        {
            "op": "datum_points",
            "label": "dpb0",
            "points": [{"name": "pb", "position": list(SMOKE_3PT_POINTS["dpb0"])}],
        },
        {
            "op": "datum_points",
            "label": "dpd0",
            "points": [{"name": "pd", "position": list(SMOKE_3PT_POINTS["dpd0"])}],
        },
        {
            "op": "datum_plane",
            "label": "pl00a",
            "reference": {
                "kind": "through_points",
                "points": ["dpa0", "dpb0", "dpd0"],
            },
        },
        {
            "op": "sketch",
            "label": "smk",
            "plane": {
                "reference": {"kind": "datum_feature", "label": "pl00a"},
                "origin": list(SMOKE_3PT_POINTS["dpa0"]),
                "u_axis": [190.382228, 0.0, 0.0],
            },
            "dimensioning": "coordinates",
            "entities": [
                {
                    "type": "polyline",
                    "name": "tri",
                    "points": [list(point) for point in SMOKE_3PT_TRIANGLE_UV],
                    "closed": True,
                }
            ],
        },
        {
            "op": "extrude",
            "label": "smk_ex",
            "sketch": "smk",
            "depth": SMOKE_3PT_DEPTH_MM,
            "direction": "symmetric",
            "new_body": True,
        },
    ]


def smoke_3pt_plane_oracle() -> dict:
    """Independent plane basis and the two externally observed mappings.

    The normal comes from the cross product of the datum chords (order
    pb-pa x pd-pa reproduces the report's sign); u is the input direction
    orthogonalized against that normal exactly as sketch_frame does, and
    v = n x u. The oracle must reproduce both external evidence points:

    - the pre-fix defect: with the placeholder identity treated as the location
      matrix, vertex UV (0,0)/(190.382228,22.394433) are written as world XY
      (-95.191114,40.000000)->(44.838428,45.875213), the values in the
      archived native.log excerpt;
    - the L1 fix: the frame-basis projection returns the input UV exactly and
      the world->section->world round trip closes on the real vertex positions.
    """
    from test_dev048_plane_frame import (
        IDENTITY_4X4,
        project_section_to_world,
        project_world_to_section,
        uv_mapping_choice,
    )

    pa = SMOKE_3PT_POINTS["dpa0"]
    pb = SMOKE_3PT_POINTS["dpb0"]
    pd = SMOKE_3PT_POINTS["dpd0"]

    def sub(a, b):
        return [a[i] - b[i] for i in range(3)]

    def cross(a, b):
        return [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ]

    def dot(a, b):
        return sum(a[i] * b[i] for i in range(3))

    def unit(a):
        length = math.sqrt(dot(a, a))
        return [component / length for component in a]

    normal = unit(cross(sub(pb, pa), sub(pd, pa)))
    preferred = [1.0, 0.0, 0.0]  # the input u_axis [190.382228,0,0] normalized
    projection = dot(normal, preferred)
    u_axis = unit([preferred[i] - normal[i] * projection for i in range(3)])
    v_axis = unit(cross(normal, u_axis))
    frame = {"normal": normal, "u_axis": u_axis, "v_axis": v_axis, "origin": list(pa)}
    mapping = uv_mapping_choice(IDENTITY_4X4, normal, pa)
    vertices = []
    for position, uv in enumerate(SMOKE_3PT_TRIANGLE_UV):
        world = [pa[i] + u_axis[i] * uv[0] + v_axis[i] * uv[1] for i in range(3)]
        via_location_matrix = project_world_to_section(
            uv, frame["origin"], u_axis, v_axis, False, IDENTITY_4X4
        )
        via_frame_basis = project_world_to_section(
            uv, frame["origin"], u_axis, v_axis, True, IDENTITY_4X4
        )
        restored = project_section_to_world(
            tuple(via_frame_basis), frame["origin"], u_axis, v_axis, True, IDENTITY_4X4
        )
        vertices.append(
            {
                "vertex": position,
                "input_uv": list(uv),
                "world_mm": world,
                "via_location_matrix_uv": list(via_location_matrix),
                "via_frame_basis_uv": list(via_frame_basis),
                "frame_basis_round_trip_error_mm": math.sqrt(
                    sum((restored[i] - world[i]) ** 2 for i in range(3))
                ),
            }
        )
    reported_normal_error = max(abs(normal[i] - SMOKE_3PT_REPORTED_NORMAL[i]) for i in range(3))
    external_buggy = {
        0: [-95.191114, 40.000000],
        1: [44.838428, 45.875213],
    }
    buggy_reproduced = all(
        max(
            abs(vertices[index]["via_location_matrix_uv"][axis] - external_buggy[index][axis])
            for axis in range(2)
        )
        <= 1e-6
        for index in external_buggy
    )
    frame_basis_exact = all(
        max(
            abs(vertices[index]["via_frame_basis_uv"][axis] - vertices[index]["input_uv"][axis])
            for axis in range(2)
        )
        <= 1e-9
        for index in range(len(SMOKE_3PT_TRIANGLE_UV))
    )
    return {
        "normal": normal,
        "reported_normal": SMOKE_3PT_REPORTED_NORMAL,
        "reported_normal_abs_error": reported_normal_error,
        "reported_normal_tolerance": 1e-3,
        "origin": list(pa),
        "u_axis_orthogonalized": u_axis,
        "u_axis_note": "the input [190.382228,0,0] is orthogonalized against the plane normal, "
        "matching sketch_frame; the raw direction is not in the plane",
        "v_axis": v_axis,
        "identity_loc_mapping": mapping,
        "vertices": vertices,
        "external_buggy_line_uv_reproduced": buggy_reproduced,
        "frame_basis_returns_input_uv": frame_basis_exact,
        "max_round_trip_error_mm": max(
            vertex["frame_basis_round_trip_error_mm"] for vertex in vertices
        ),
    }


def smoke_3pt_volume_oracle() -> dict:
    """Symmetric extrusion volume: shoelace area of the UV triangle x depth."""
    points = SMOKE_3PT_TRIANGLE_UV
    shoelace = (
        abs(
            sum(
                points[i][0] * points[(i + 1) % 3][1] - points[(i + 1) % 3][0] * points[i][1]
                for i in range(3)
            )
        )
        / 2
    )
    return {
        "triangle_area_mm2": shoelace,
        "depth_mm": SMOKE_3PT_DEPTH_MM,
        "symmetric_volume_mm3": shoelace * SMOKE_3PT_DEPTH_MM,
    }


def smoke_3pt_schema_gate() -> dict:
    """Whether this tree already accepts the explicit three-point contract."""
    try:
        validate_operations(smoke_3pt_min_repro_operations()[:4])
    except Exception as error:
        return {
            "accepted": False,
            "blocked_pending": "FEAT-053",
            "reason": f"{type(error).__name__}: {error}",
        }
    return {"accepted": True, "blocked_pending": None, "reason": None}


def smoke_3pt_fixture() -> dict:
    """The archived smoke case as a fixture: oracle, expectations, gate state."""
    return {
        "source": "docs/validation/feedback-0.10.0-2026-11-01/originals/06_P12_v12_配方/"
        "smoke_3pt_min_repro.json",
        "evidence_class": "substitute_fixture_not_original_job_replay",
        "operations": smoke_3pt_min_repro_operations(),
        "plane_oracle": smoke_3pt_plane_oracle(),
        "volume_oracle": smoke_3pt_volume_oracle(),
        "schema_gate": smoke_3pt_schema_gate(),
        "expected_l1_diagnostics": {
            "section_location_identity": 1,
            "uv_mapping": "frame_basis",
            "first_line_uv": "0.000000000,0.000000000 -> 190.382228,22.394433",
        },
        "original_l2_expectation": "ProFeatureWithoptionsRedefine may still fail; the "
        "feature_errors receipt must then carry element/type/error entries",
        "depth_precision_note": "9.87008714331235 kept verbatim; never rounded to 9.87",
    }


def scan_native_log_stages(log_text: str) -> dict:
    """Classify a native.log into the four BUG-097 stages and locate the failure.

    A stage counts as reached when any of its markers appears. A stage counts
    as failed only on explicit failure evidence (a nonzero completion code or
    a validation refusal); absence of a stage's markers means it was not
    reached, never that it passed.
    """
    stages: dict[str, dict] = {}
    for stage, markers in STAGE_MARKERS.items():
        found = [marker for marker in markers if marker in log_text]
        stages[stage] = {"reached": bool(found), "markers": found}
    stages["frame_validation"]["failed"] = any(
        marker in log_text
        for marker in (
            "parallel to the support plane normal",
            "Sketch support must be planar",
            "No sketch orientation reference",
        )
    )
    stages["uv_write"]["failed"] = "COORDINATE_DEVIATION" in log_text
    stages["section_regenerate"]["failed"] = any(
        marker in log_text
        for marker in ("SectionRegenerate=-1", "SKETCH_SOLVE=-1", "AutodimensionSketch=-1")
    )
    stages["complete_feature"]["failed"] = "CompleteFeature=-1" in log_text
    failure_stage = None
    for stage in ("complete_feature", "section_regenerate", "uv_write", "frame_validation"):
        if stages[stage]["failed"]:
            failure_stage = stage
            break
    return {
        "stages": stages,
        "failure_stage": failure_stage,
        "section_location_identity": "SECTION_LOCATION_IDENTITY=1" in log_text,
        "frame_basis_fallback": "using_frame_basis" in log_text,
        "feature_error_entries": log_text.count("feature_error element="),
    }


def independent_area_mm2() -> float:
    """Thirty isosceles triangles with circumradius 5 mm."""
    return SIDES * RADIUS_MM * RADIUS_MM * math.sin(2 * math.pi / SIDES) / 2


def polygon_entities() -> list[dict]:
    vertices = [
        [
            RADIUS_MM * math.cos(2 * math.pi * index / SIDES),
            RADIUS_MM * math.sin(2 * math.pi * index / SIDES),
        ]
        for index in range(SIDES)
    ]
    return [
        {
            "type": "line",
            "name": f"poly_{index:02d}",
            "start": vertices[index],
            "end": vertices[(index + 1) % SIDES],
        }
        for index in range(SIDES)
    ]


def sketch(
    kind: str, strategy: str, reference: str, plane_id: int, *, new_face: bool = False
) -> dict:
    if (
        kind not in {"rectangle", "polygon"}
        or strategy not in STRATEGIES
        or reference not in REFERENCES
    ):
        raise ValueError((kind, strategy, reference))
    if reference == "datum_plane_id":
        ref = {"kind": "datum_plane", "id": plane_id}
    else:
        ref = {"kind": "datum_feature", "label": "tilted_new" if new_face else "tilted"}
    if new_face and reference == "datum_plane_id":
        ref = {
            "kind": "datum_plane",
            "id": plane_id + 1,
        }  # Offline placeholder; resolve by geometry live.
    return {
        "op": "sketch",
        "label": f"{'new_face_' if new_face else ''}{kind}",
        "plane": {
            "reference": ref,
            "origin": [0.0, 0.0, 0.0],
            "u_axis": [0.809017, -0.587785, 0.0],
        },
        "entities": [
            dict(RECTANGLE) if kind == "rectangle" else entity
            for entity in (polygon_entities() if kind == "polygon" else [RECTANGLE])
        ],
        "dimensioning": strategy,
    }


def build_cases(run_tag: str, plane_id: int = TILTED_FIXTURE["id"]) -> list[dict]:
    """Each row represents a separate creo_new_part and ordered submissions.

    The unavailable second-reference branch is an inspection target. A real
    session must establish reference count/geometry before that branch may be
    scored; offline input cannot force Toolkit reference selection.
    """
    cases = []
    for strategy in STRATEGIES:
        for reference in REFERENCES:
            for second in SECOND_REFERENCES:
                for order in ORDERS:
                    code = f"{strategy[:2]}_{'id' if reference == 'datum_plane_id' else 'lb'}_{second[:2]}_{ORDERS.index(order)}"
                    first = "polygon" if order == "polygon_then_rectangle" else "rectangle"
                    steps = [first]
                    if order == "rectangle_then_polygon":
                        steps.append("polygon")
                    elif order == "polygon_then_rectangle":
                        steps.append("rectangle")
                    operations = [sketch(kind, strategy, reference, plane_id) for kind in steps]
                    if order == "new_face_rectangle":
                        operations = [
                            sketch("rectangle", strategy, reference, plane_id, new_face=True)
                        ]
                    setup = setup_operations()
                    if order == "new_face_rectangle":
                        setup.append({**setup[-1], "label": "tilted_new"})
                    cases.append(
                        {
                            "case": f"{strategy}_{reference}_{second}_{order}",
                            "model_name": f"t06_{code}_{run_tag}",
                            "new_part_required": True,
                            "setup_operations": setup,
                            "ordered_sketch_submissions": operations,
                            "reference_mode": reference,
                            "second_reference_target": second,
                            "second_reference_must_be_verified_live": True,
                            "fresh_tilted_face_required": order == "new_face_rectangle",
                            "failed_then_same_face_rectangle": {
                                "conditional": True,
                                "only_after": "legal_sketch_natural_failure_and_verified_rollback",
                                "operation": sketch("rectangle", strategy, reference, plane_id),
                            },
                        }
                    )
    return cases


def validate_cases(cases: list[dict]) -> None:
    names = [case["model_name"] for case in cases]
    if len(names) != len(set(names)):
        raise ValueError("duplicate model name")
    for case in cases:
        if len(case["model_name"]) > 31:
            raise ValueError("model name too long")
        validate_operations(case["setup_operations"])
        for operation in case["ordered_sketch_submissions"]:
            validate_operations([operation])
        validate_operations([case["failed_then_same_face_rectangle"]["operation"]])
    if len(cases) != 32:
        raise ValueError("incomplete sequence matrix")


def provenance() -> dict:
    from creo_mechdog.source_provenance import local_provenance as collect

    evidence = collect(
        ROOT,
        {"tools/test_tilted_sketch_lifecycle.py", "tests/unit/test_tilted_sketch_lifecycle.py"},
    )
    # Preserve the released report aliases while sharing source completeness checks.
    evidence["provenance_mode"] = "git" if evidence["git_status"] == "available" else "filesystem"
    evidence["git_unavailable"] = evidence["git_status"] != "available"
    evidence["commit"] = evidence["commit"] or ""
    evidence["branch"] = evidence["branch"] or ""
    return evidence


def offline_report(run_tag: str) -> dict:
    cases = build_cases(run_tag)
    validate_cases(cases)
    return {
        "task": "DEV-051 T06",
        "mode": "offline",
        "live_run": False,
        "original_30_segment_case": "missing_request_prt_job_native",
        "replacement": "regular_30gon_30_independent_lines_r5mm",
        "independent_area_oracle_mm2": independent_area_mm2(),
        "area_formula": "30/2 * 5^2 * sin(2*pi/30)",
        "tilted_normal": tilted_normal(),
        "cases": cases,
        "native_acceptance": "not_run",
        "contamination_hypothesis": "not_reproduced_offline",
        "bug097_stage_markers": {stage: list(markers) for stage, markers in STAGE_MARKERS.items()},
        "bug097_smoke_3pt_fixture": smoke_3pt_fixture(),
        "provenance": provenance(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.live or args.confirm_session_usable:
        parser.error(
            "T06 offline phase refuses --live and session confirmation; no Creo connection"
        )
    run_tag = uuid.uuid4().hex[:8]
    report = offline_report(run_tag)
    path = args.output or ROOT / "build" / "tilted_sketch_lifecycle" / run_tag / "report.json"
    if path.exists():
        parser.error(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
