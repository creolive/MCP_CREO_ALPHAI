"""FEAT-051 / N04: round/chamfer/draft result observability driver.

Freezes the fixture matrix behind the frozen contract in
docs/work-items/FEAT-051.md: per-operation volume evidence, draft geometry
readback and tree-proven reference application for round/chamfer/draft.

The fixtures pair every detail operation with an independent analytic
expectation (corner cross-section x edge length for rounds, triangle prism for
chamfers, cylinder/frustum difference for the 11 degree draft). The 11 degree
cylinder mirrors the external 0.8.5 report's analytic case as a bounded
reference sample; which flip direction removes material depends on the neutral
face orientation, so the flip pair is judged by exact magnitudes with opposite
signs and the observed sign is recorded, never assumed.

Unit coverage: the public creation tools are metric-only (creo_new_part is
mmns) and fault injection is forbidden, so the inch / mixed / unknown unit
matrix is exercised offline through synthetic native records and the cube
scale rule the native executor implements; the live stage covers the mmns case
end-to-end and records the model's real length unit.

Default is strictly offline. Only --live --confirm-session-usable starts an
MCP client. The driver never launches or stops Creo, clears protection,
injects faults, or resubmits a job.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402

ROOT = SOURCE_PATHS.resource_root

VOLUME_TOLERANCE_MM3 = 0.01
OBSERVATION_KEYS = (
    "volume_before_mm3",
    "volume_after_mm3",
    "material_delta_mm3",
    "material_measurement",
    "draft_geometry",
    "reference_application",
)

BOX = {"length_mm": 40.0, "width_mm": 30.0, "height_mm": 20.0}
ROUND_RADIUS_MM = 3.0
CHAMFER_DISTANCE_MM = 2.0
CYLINDER_RADIUS_MM = 3.0
CYLINDER_HEIGHT_MM = 3.0
DRAFT_ANGLE_DEG = 11.0

# Unit matrix: value_mm3 = native_volume * scale_to_mm^3. A null scale is the
# unknown-unit case: values must stay null and the status must stay unknown.
UNIT_CASES = (
    {"name": "mm", "scale_to_mm": 1.0, "native_volume": 100.0, "expected_mm3": 100.0},
    {
        "name": "inch",
        "scale_to_mm": 25.4,
        "native_volume": 8.0,
        "expected_mm3": 8.0 * 25.4**3,
    },
    {
        "name": "mixed_other",
        "scale_to_mm": 10.0,
        "native_volume": 2.5,
        "expected_mm3": 2500.0,
    },
    {"name": "unknown", "scale_to_mm": None, "native_volume": 2.5, "expected_mm3": None},
)


# --- analytic oracles -------------------------------------------------------


def corner_cross_section_area(radius: float) -> float:
    """Area between the square corner and the fillet quarter circle."""
    return radius * radius * (1.0 - math.pi / 4.0)


def round_delta_mm3(length: float, radius: float, concave: bool) -> float:
    """Signed material change of one constant round on a straight edge.

    A convex edge removes the corner cross-section x length; a concave edge
    adds the same amount.
    """
    magnitude = length * corner_cross_section_area(radius)
    return magnitude if concave else -magnitude


def chamfer_delta_mm3(length: float, distance: float) -> float:
    """Signed material change of one equal-distance chamfer on a straight edge."""
    return -(length * distance * distance / 2.0)


def cylinder_volume(radius: float, height: float) -> float:
    return math.pi * radius * radius * height


def frustum_volume(r_top: float, r_bottom: float, height: float) -> float:
    return math.pi * height / 3.0 * (r_top * r_top + r_top * r_bottom + r_bottom * r_bottom)


def draft_delta_mm3(radius: float, height: float, angle_deg: float, inward: bool) -> float:
    """Signed material change of a one-end draft on a standalone cylinder.

    The neutral plane is the top face; the taper shifts the bottom radius by
    height*tan(angle), inward shrinking the bottom and outward growing it.
    """
    shift = height * math.tan(math.radians(angle_deg))
    r_bottom = radius - shift if inward else radius + shift
    return frustum_volume(radius, r_bottom, height) - cylinder_volume(radius, height)


def volume_to_mm3(native_volume: float, scale_to_mm: float | None) -> float | None:
    """The conversion rule the native executor implements (cube of the scale)."""
    if scale_to_mm is None:
        return None
    return native_volume * scale_to_mm**3


def numeric_oracles_agree(tolerance: float = 1e-6) -> bool:
    """Slice/grid cross-checks of the two closed-form oracles used above."""
    steps = 20000
    radius = ROUND_RADIUS_MM
    quarter_disk = 0.0
    for index in range(steps):
        x = radius * (index + 0.5) / steps
        quarter_disk += math.sqrt(max(radius * radius - x * x, 0.0)) * (radius / steps)
    if abs((radius * radius - quarter_disk) - corner_cross_section_area(radius)) > tolerance:
        return False
    r, h, angle = CYLINDER_RADIUS_MM, CYLINDER_HEIGHT_MM, DRAFT_ANGLE_DEG
    shift_per_z = math.tan(math.radians(angle))
    frustum = 0.0
    for index in range(steps):
        z = h * (index + 0.5) / steps
        rz = r - z * shift_per_z
        frustum += math.pi * rz * rz * (h / steps)
    inward = frustum - cylinder_volume(r, h)
    return abs(inward - draft_delta_mm3(r, h, angle, True)) <= tolerance


# --- fixtures ---------------------------------------------------------------


def box_operations() -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "box_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "polyline",
                    "name": "box_rect",
                    "points": [
                        [0.0, 0.0],
                        [BOX["length_mm"], 0.0],
                        [BOX["length_mm"], BOX["width_mm"]],
                        [0.0, BOX["width_mm"]],
                    ],
                    "closed": True,
                }
            ],
            "dimensioning": "coordinates",
        },
        {"op": "extrude", "label": "box", "sketch": "box_profile", "depth": BOX["height_mm"]},
    ]


def l_prism_operations() -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "l_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "polyline",
                    "name": "l_shape",
                    "points": [
                        [0.0, 0.0],
                        [40.0, 0.0],
                        [40.0, 20.0],
                        [20.0, 20.0],
                        [20.0, 40.0],
                        [0.0, 40.0],
                    ],
                    "closed": True,
                }
            ],
            "dimensioning": "coordinates",
        },
        {"op": "extrude", "label": "l_prism", "sketch": "l_profile", "depth": 20.0},
    ]


def cylinder_operations(with_axis: bool = False) -> list[dict]:
    operations = [
        {
            "op": "sketch",
            "label": "cyl_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "circle",
                    "name": "cyl",
                    "center": [0.0, 0.0],
                    "radius": CYLINDER_RADIUS_MM,
                }
            ],
            "dimensioning": "coordinates",
        },
        {
            "op": "extrude",
            "label": "cyl_boss",
            "sketch": "cyl_profile",
            "depth": CYLINDER_HEIGHT_MM,
        },
    ]
    if with_axis:
        operations.append(
            {
                "op": "datum_axis",
                "label": "cyl_axis",
                # Default datum planes 2 (X-normal) and 4 (Y-normal) intersect
                # on the Z axis, which is the cylinder axis at origin. A live
                # surface id is not known before the base plan runs (the
                # 2026-10-31 live run proved surface id 1 does not exist).
                "references": [
                    {"kind": "datum_plane", "id": 2},
                    {"kind": "datum_plane", "id": 4},
                ],
            }
        )
    return operations


def edge_round_template(radius: float = ROUND_RADIUS_MM) -> list[dict]:
    return [
        {
            "op": "round",
            "label": "edge_round",
            "size": radius,
            "references": [{"edge": {"kind": "edge", "id": 1}}],
        }
    ]


def chamfer_template(distance: float = CHAMFER_DISTANCE_MM) -> list[dict]:
    return [
        {
            "op": "chamfer",
            "label": "edge_breaks",
            "size": distance,
            "references": [
                {
                    "surfaces": [
                        {"kind": "surface", "id": 1},
                        {"kind": "surface", "id": 2},
                    ]
                }
                for _ in range(3)
            ],
        }
    ]


def draft_template(label: str, flip: bool, pull: bool) -> list[dict]:
    operation = {
        "op": "draft",
        "label": label,
        "surfaces": [{"kind": "surface", "id": 1}],
        "neutral_plane": {"kind": "surface", "id": 2},
        "angle": DRAFT_ANGLE_DEG,
        "flip": flip,
    }
    if pull:
        operation["pull_direction"] = {"kind": "axis", "id": 1}
    return [operation]


def build_cases(tag: str = "00000000") -> list[dict]:
    """The offline/live fixture matrix with independent expectations.

    ``expected_delta_mm3`` is a list of acceptable analytic values: single-value
    cases judge one expected change; the draft flip cases accept the inward or
    outward frustum value because the flip-to-direction mapping depends on the
    neutral face orientation and must be observed, not assumed.
    """
    inward = draft_delta_mm3(CYLINDER_RADIUS_MM, CYLINDER_HEIGHT_MM, DRAFT_ANGLE_DEG, True)
    outward = draft_delta_mm3(CYLINDER_RADIUS_MM, CYLINDER_HEIGHT_MM, DRAFT_ANGLE_DEG, False)

    def name(label: str) -> str:
        return f"n04_{label}_{tag}"[:31]

    return [
        {
            "case": "round_convex",
            "scenario": "convex vertical edge round on the 40x30x20 box",
            "base_operations": box_operations(),
            "operations": edge_round_template(),
            "resolve": {"kind": "edge_round", "edge_at": [0.0, 0.0], "edge_length_mm": 20.0},
            "expected_delta_mm3": [round_delta_mm3(20.0, ROUND_RADIUS_MM, concave=False)],
            "judge": "single",
            "model_name": name("box_round_cvx"),
        },
        {
            "case": "round_concave",
            "scenario": "concave inner-corner round on the L prism (adds material)",
            "base_operations": l_prism_operations(),
            "operations": edge_round_template(),
            "resolve": {"kind": "edge_round", "edge_at": [20.0, 20.0], "edge_length_mm": 20.0},
            "expected_delta_mm3": [round_delta_mm3(20.0, ROUND_RADIUS_MM, concave=True)],
            "judge": "single",
            "model_name": name("l_round_ccv"),
        },
        {
            "case": "chamfer_three_face_pairs",
            "scenario": "one chamfer with three face-pair sets on three box edges",
            "base_operations": box_operations(),
            "operations": chamfer_template(),
            "resolve": {
                "kind": "face_pairs",
                "pairs": [
                    [([0.0, 1.0, 0.0], 0.0), ([1.0, 0.0, 0.0], 0.0)],
                    [([0.0, 1.0, 0.0], 0.0), ([1.0, 0.0, 0.0], 40.0)],
                    [([0.0, 1.0, 0.0], 30.0), ([1.0, 0.0, 0.0], 40.0)],
                ],
            },
            "expected_delta_mm3": [3 * chamfer_delta_mm3(20.0, CHAMFER_DISTANCE_MM)],
            "judge": "single",
            "model_name": name("box_chm3"),
        },
        {
            "case": "draft_flip_false",
            "scenario": "11 degree cylinder draft, flip false (direction self-evidenced)",
            "base_operations": cylinder_operations(),
            "operations": draft_template("draft_a", flip=False, pull=False),
            "resolve": {"kind": "draft", "with_axis": False},
            "expected_delta_mm3": [inward, outward],
            "judge": "single",
            "model_name": name("cyl_dr_f0"),
        },
        {
            "case": "draft_flip_true",
            "scenario": "11 degree cylinder draft, flip true (opposite of flip false)",
            "base_operations": cylinder_operations(),
            "operations": draft_template("draft_b", flip=True, pull=False),
            "resolve": {"kind": "draft", "with_axis": False},
            "expected_delta_mm3": [inward, outward],
            "judge": "single",
            "model_name": name("cyl_dr_f1"),
        },
        {
            "case": "draft_default_pull",
            "scenario": "pull direction omitted: readback must show the neutral plane",
            "base_operations": cylinder_operations(),
            "operations": draft_template("draft_c", flip=True, pull=False),
            "resolve": {"kind": "draft", "with_axis": False},
            "expected_delta_mm3": [inward, outward],
            "judge": "pull_default",
            "model_name": name("cyl_dr_pd"),
        },
        {
            "case": "draft_explicit_pull",
            "scenario": "explicit axis pull direction: readback must show the axis",
            "base_operations": cylinder_operations(with_axis=True),
            "operations": draft_template("draft_d", flip=True, pull=True),
            "resolve": {"kind": "draft", "with_axis": True},
            "expected_delta_mm3": [inward, outward],
            "judge": "pull_explicit",
            "model_name": name("cyl_dr_pe"),
        },
        {
            "case": "batch_mid_failure",
            "scenario": "good round, failing round (edge 999999), trailing chamfer",
            "base_operations": box_operations(),
            "operations": [
                {
                    "op": "round",
                    "label": "round_ok",
                    "size": ROUND_RADIUS_MM,
                    "references": [{"edge": {"kind": "edge", "id": 1}}],
                },
                {
                    "op": "round",
                    "label": "round_bad",
                    "size": ROUND_RADIUS_MM,
                    "references": [{"edge": {"kind": "edge", "id": 999999}}],
                },
                {
                    "op": "chamfer",
                    "label": "breaks_late",
                    "size": CHAMFER_DISTANCE_MM,
                    "references": [
                        {
                            "surfaces": [
                                {"kind": "surface", "id": 1},
                                {"kind": "surface", "id": 2},
                            ]
                        }
                    ],
                },
            ],
            "resolve": {"kind": "batch"},
            "expected_delta_mm3": None,
            "judge": "batch_failure",
            "model_name": name("box_batch"),
        },
        {
            "case": "zero_delta",
            "scenario": "projection rule: a legal zero delta is reported as zero",
            "base_operations": [],
            "operations": [],
            "resolve": {"kind": "projection_only"},
            "expected_delta_mm3": [0.0],
            "judge": "projection_only",
            "model_name": name("zero_delta"),
        },
    ]


def external_reference_sample() -> dict:
    """Bounded sample of the external 0.8.5 11 degree cylinder case."""
    return {
        "source": (
            "docs/validation/feedback-0.8.x-2026-10-30/"
            "20261030_CREO_v0.8.5_细节特征无体积回报_拔模方向只能靠体积反查.md"
        ),
        "reported": {
            "flip_false_delta_mm3": 17.564,
            "flip_true_delta_mm3": -15.406,
            "analytic_inward_mm3": -15.416,
            "geometry": "R3 x 3 cylinder, neutral = boss end face, 11 degree",
        },
        "our_analytic": {
            "inward_mm3": draft_delta_mm3(
                CYLINDER_RADIUS_MM, CYLINDER_HEIGHT_MM, DRAFT_ANGLE_DEG, True
            ),
            "outward_mm3": draft_delta_mm3(
                CYLINDER_RADIUS_MM, CYLINDER_HEIGHT_MM, DRAFT_ANGLE_DEG, False
            ),
        },
        "note": (
            "Bounded reference sample. The flip-to-direction mapping depends on the "
            "neutral face orientation and is observed from the signed material delta, "
            "never assumed or force-fitted here."
        ),
    }


# --- pure judgements --------------------------------------------------------


def judge_measurement(record: Any, expected_deltas: list[float], tolerance: float = 0.01) -> dict:
    """Judge one measured block against the analytic expectations.

    Only measured values count: a null delta or a non-measured status is
    recorded as unknown and never passes.
    """
    if not isinstance(record, dict):
        return {"status": "unknown", "reason": "no operation record"}
    measurement = record.get("material_measurement")
    status = measurement.get("status") if isinstance(measurement, dict) else None
    delta = record.get("material_delta_mm3")
    if delta is None or status != "measured":
        return {
            "status": "unknown",
            "measured_delta_mm3": delta,
            "measurement_status": status,
            "reason": "measurement not established",
        }
    for expected in expected_deltas:
        if abs(delta - expected) <= tolerance:
            return {
                "status": "pass",
                "measured_delta_mm3": delta,
                "matched_expected_mm3": expected,
                "abs_error_mm3": abs(delta - expected),
            }
    return {
        "status": "fail",
        "measured_delta_mm3": delta,
        "expected_deltas_mm3": list(expected_deltas),
    }


def terminal_model_revision(terminal: Any, context: str) -> int:
    """Read the model revision a terminal job reports from its top-level manifest.

    Job manifests carry the model revision as a top-level ``revision`` key
    (generic_bridge.run_generic_job records it on success); it is NOT inside
    ``result``. The 2026-10-30 N04 live run died on ``result.revision`` with a
    bare KeyError before the matrix started. A terminal without a usable
    revision fails with a clear message naming the context instead.
    """
    if isinstance(terminal, dict):
        revision = terminal.get("revision")
        if isinstance(revision, int) and not isinstance(revision, bool):
            return revision
        raise RuntimeError(
            f"{context}: job terminal carries no top-level int revision "
            f"(revision={revision!r}, keys={sorted(terminal)}); the model revision "
            "lives on the job manifest top level, not in result"
        )
    raise RuntimeError(
        f"{context}: job terminal is not a dict ({type(terminal).__name__}); "
        "cannot read the top-level revision"
    )


def judge_pull_readback(geometry: Any, expected_reference: dict) -> str:
    """The draft readback must name the reference the plan actually used.

    "pass" only when the tree-read pull reference resolves to the expected
    geometry id; an unreadable reference is "unknown" and a different id fails.
    """
    pull = geometry.get("pull_direction") if isinstance(geometry, dict) else None
    if not isinstance(pull, dict) or pull.get("id") is None:
        return "unknown"
    return "pass" if pull.get("id") == expected_reference.get("id") else "fail"


def judge_batch_failure(operations: Any) -> dict:
    """The mid-batch failure verdict: rollback labels, no fabricated readings."""
    problems: list[str] = []
    if not isinstance(operations, list) or len(operations) != 3:
        return {"status": "fail", "problems": ["expected exactly three terminal records"]}
    good, failed, late = operations
    if good.get("effect_status") != "rolled_back":
        problems.append("prior change is not marked rolled_back")
    if not all(key in good for key in OBSERVATION_KEYS[:4]):
        problems.append("prior change lost its material measurement")
    if failed.get("execution_status") != "failed":
        problems.append("second record is not the failed operation")
    measurement = failed.get("material_measurement")
    if not isinstance(measurement, dict):
        problems.append("failed operation has no material measurement block")
    else:
        if measurement.get("after_query_code") is not None:
            problems.append("failed operation reports an after-side query code")
    if failed.get("volume_after_mm3") is not None or failed.get("material_delta_mm3") is not None:
        problems.append("failed operation fabricated after-side readings")
    if late.get("execution_status") != "not_executed":
        problems.append("trailing record is not not_executed")
    for key in OBSERVATION_KEYS:
        if key in late:
            problems.append(f"not_executed record carries readings ({key})")
    return {"status": "pass" if not problems else "fail", "problems": problems}


# --- live geometry selection (pure) ------------------------------------------


def select_vertical_edges(edges: list[dict], length_mm: float, tol: float = 1e-6) -> list[int]:
    picked: list[int] = []
    for edge in edges or []:
        start, end = edge.get("start"), edge.get("end")
        if not isinstance(start, list) or not isinstance(end, list) or len(start) != 3:
            continue
        vertical = abs(start[0] - end[0]) <= tol and abs(start[1] - end[1]) <= tol
        length = abs(end[2] - start[2])
        if vertical and abs(length - length_mm) <= tol:
            picked.append(edge["id"])
    return picked


def select_vertical_edge_at(
    edges: list[dict], x: float, y: float, length_mm: float, tol: float = 1e-6
) -> int | None:
    for edge in edges or []:
        start, end = edge.get("start"), edge.get("end")
        if not isinstance(start, list) or not isinstance(end, list) or len(start) != 3:
            continue
        vertical = abs(start[0] - end[0]) <= tol and abs(start[1] - end[1]) <= tol
        length = abs(end[2] - start[2])
        if vertical and abs(length - length_mm) <= tol:
            if abs(start[0] - x) <= tol and abs(start[1] - y) <= tol:
                return edge["id"]
    return None


def select_plane_surface(
    surfaces: list[dict], normal: list[float], offset: float, tol: float = 1e-6
) -> int | None:
    norm = math.sqrt(sum(value * value for value in normal))
    if norm <= tol:
        return None
    unit = [value / norm for value in normal]
    for surface in surfaces or []:
        candidate = surface.get("normal")
        origin = surface.get("origin")
        if not isinstance(candidate, list) or not isinstance(origin, list):
            continue
        length = math.sqrt(sum(value * value for value in candidate))
        if length <= tol:
            continue
        alignment = abs(sum(a / length * b for a, b in zip(candidate, unit)))
        if abs(alignment - 1.0) > 1e-6:
            continue
        distance = sum(a * b for a, b in zip(origin, unit))
        if abs(distance - offset) <= tol:
            return surface["id"]
    return None


def select_cylinder_surface(
    surfaces: list[dict], radius_mm: float, tol: float = 1e-6
) -> int | None:
    for surface in surfaces or []:
        radius = surface.get("radius")
        if isinstance(radius, (int, float)) and abs(radius - radius_mm) <= tol:
            return surface["id"]
    return None


def resolve_case_operations(case: dict, model_state: dict) -> list[dict]:
    """Substitute real model ids into one case's detail-operations template."""
    resolve = case.get("resolve", {})
    kind = resolve.get("kind")
    edges = model_state.get("edges") or []
    surfaces = model_state.get("surfaces") or []
    if kind == "edge_round":
        edge_id = select_vertical_edge_at(
            edges, resolve["edge_at"][0], resolve["edge_at"][1], resolve["edge_length_mm"]
        )
        if edge_id is None:
            raise RuntimeError(f"{case['case']}: no vertical edge at {resolve['edge_at']}")
        operation = dict(case["operations"][0])
        operation["references"] = [{"edge": {"kind": "edge", "id": edge_id}}]
        return [operation]
    if kind == "face_pairs":
        references = []
        for pair in resolve["pairs"]:
            ids = []
            for normal, offset in pair:
                surface_id = select_plane_surface(surfaces, normal, offset)
                if surface_id is None:
                    raise RuntimeError(f"{case['case']}: no plane for {normal} @ {offset}")
                ids.append(surface_id)
            references.append({"surfaces": [{"kind": "surface", "id": i} for i in ids]})
        operation = dict(case["operations"][0])
        operation["references"] = references
        return [operation]
    if kind == "draft":
        surface_id = select_cylinder_surface(surfaces, CYLINDER_RADIUS_MM)
        neutral_id = select_plane_surface(surfaces, [0.0, 0.0, 1.0], CYLINDER_HEIGHT_MM)
        if surface_id is None or neutral_id is None:
            raise RuntimeError(f"{case['case']}: cylinder or neutral plane not found")
        operation = dict(case["operations"][0])
        operation["surfaces"] = [{"kind": "surface", "id": surface_id}]
        operation["neutral_plane"] = {"kind": "surface", "id": neutral_id}
        if resolve.get("with_axis"):
            axes = model_state.get("datum_axes") or []
            if not axes:
                raise RuntimeError(f"{case['case']}: no datum axis for explicit pull")
            operation["pull_direction"] = {"kind": "axis", "id": axes[0]["id"]}
        return [operation]
    if kind == "batch":
        edge_id = select_vertical_edge_at(edges, 0.0, 0.0, 20.0)
        if edge_id is None:
            raise RuntimeError(f"{case['case']}: no vertical edge for the good round")
        operations = [dict(op) for op in case["operations"]]
        operations[0]["references"] = [{"edge": {"kind": "edge", "id": edge_id}}]
        pair_ids = []
        for normal, offset in (((0.0, 1.0, 0.0), 0.0), ((1.0, 0.0, 0.0), 0.0)):
            surface_id = select_plane_surface(surfaces, list(normal), offset)
            if surface_id is None:
                raise RuntimeError(f"{case['case']}: no plane for the trailing chamfer")
            pair_ids.append(surface_id)
        operations[2]["references"] = [
            {"surfaces": [{"kind": "surface", "id": i} for i in pair_ids]}
        ]
        return operations
    return []


# --- offline stage -----------------------------------------------------------


def unit_matrix_rows() -> list[dict]:
    rows = []
    for case in UNIT_CASES:
        converted = volume_to_mm3(case["native_volume"], case["scale_to_mm"])
        rows.append(
            {
                "name": case["name"],
                "scale_to_mm": case["scale_to_mm"],
                "native_volume": case["native_volume"],
                "converted_mm3": converted,
                "expected_mm3": case["expected_mm3"],
                "matches": converted == case["expected_mm3"],
            }
        )
    return rows


def projection_rows() -> list[dict]:
    """Synthetic native records through the public projection, one per rule."""
    from creo_mechdog import operation_results

    rows = []
    for name, record in (
        (
            "measured_mm",
            {
                "op": "draft",
                "index": 0,
                "label": "draft_a",
                "succeeded": True,
                "volume_before_mm3": 100.0,
                "volume_after_mm3": 84.584,
                "material_delta_mm3": -15.416,
                "material_measurement": {
                    "status": "measured",
                    "before_query_code": 0,
                    "after_query_code": 0,
                },
            },
        ),
        (
            "zero_delta",
            {
                "op": "round",
                "index": 0,
                "label": "edge_round",
                "succeeded": True,
                "volume_before_mm3": 50.0,
                "volume_after_mm3": 50.0,
                "material_delta_mm3": 0.0,
                "material_measurement": {
                    "status": "measured",
                    "before_query_code": 0,
                    "after_query_code": 0,
                },
            },
        ),
        (
            "unknown_units",
            {
                "op": "round",
                "index": 0,
                "label": "edge_round",
                "succeeded": True,
                "volume_before_mm3": None,
                "volume_after_mm3": None,
                "material_delta_mm3": None,
                "material_measurement": {
                    "status": "unknown",
                    "before_query_code": 0,
                    "after_query_code": 0,
                },
            },
        ),
    ):
        annotated = operation_results.annotate_native_result(
            {"success": True, "operations": [dict(record)]}, readonly=False, inputs=[]
        )
        projected = annotated["operations"][0]
        rows.append(
            {
                "row": name,
                "pass_through": all(projected.get(key) == record.get(key) for key in record),
                "measured_delta_mm3": projected.get("material_delta_mm3"),
                "measurement_status": projected.get("material_measurement", {}).get("status"),
            }
        )
    return rows


def offline_checks(run_id: str) -> dict:
    from creo_mechdog.schema import validate_operations

    tag = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8]
    cases = build_cases(tag)
    rows = []
    for case in cases:
        if case["operations"]:
            validate_operations(case["operations"])
        if case["base_operations"]:
            validate_operations(case["base_operations"])
        rows.append(
            {
                "case": case["case"],
                "scenario": case["scenario"],
                "judge": case["judge"],
                "expected_delta_mm3": case["expected_delta_mm3"],
                "model_name": case["model_name"],
            }
        )
    if not numeric_oracles_agree():
        raise AssertionError("numeric oracle cross-check failed")
    return {
        "run_id": run_id,
        "cases": rows,
        "unit_matrix": unit_matrix_rows(),
        "projection_rows": projection_rows(),
        "numeric_oracles_agree": True,
        "external_reference_sample": external_reference_sample(),
        "volume_tolerance_mm3": VOLUME_TOLERANCE_MM3,
    }


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "post090_n04" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
    """Collect source evidence even when running from an extracted release."""
    from creo_mechdog.source_provenance import local_provenance as collect

    return collect(
        ROOT,
        (
            "tools/test_detail_feature_observation.py",
            "tests/unit/test_detail_feature_observation.py",
        ),
    )


def write_report(output: Path, report: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def write_offline_report(output: Path, run_id: str, results: dict) -> dict:
    report = {
        "task": "FEAT-051 / N04 detail feature result observability",
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: fixture matrix, independent analytic oracles, unit-matrix "
            "conversion semantics and projection locks validated; no Toolkit connection and "
            "no native geometry result. Live acceptance of the measured deltas, draft readback "
            "and reference application is NOT claimed here."
        ),
        "cases": results["cases"],
        "unit_matrix": results["unit_matrix"],
        "unit_matrix_scope": (
            "inch/mixed/unknown are synthetic projection and conversion-oracle rows: the "
            "public creation tools only make metric (mmns) parts and fault injection is "
            "forbidden, so those unit systems are covered offline only"
        ),
        "projection_rows": results["projection_rows"],
        "numeric_oracles_agree": results["numeric_oracles_agree"],
        "external_reference_sample": results["external_reference_sample"],
        "volume_tolerance_mm3": results["volume_tolerance_mm3"],
        "provenance": local_provenance(),
    }
    write_report(output, report)
    return report


# --- live stage --------------------------------------------------------------


class DetailFeatureAcceptance:
    """Serial live runner: one base model per fixture case, then the detail plan.

    Every case compares the measured material delta against the independent
    analytic expectation, checks the draft readback and the tree-proven
    application counts, and cross-checks the delta against two model-volume
    snapshots. The batch case checks rollback labeling and unexecuted records.
    """

    def __init__(self, client: Any, output: Path, run_id: str) -> None:
        self.client = client
        self.output = output
        self.run_id = run_id
        self.submitted: set[str] = set()
        self.report: dict = {
            "task": "FEAT-051 / N04 detail feature result observability",
            "run_id": run_id,
            "mode": "live",
            "live_run": True,
            "native_acceptance": "running",
            "cases": [],
            "calls": [],
            "external_reference_sample": external_reference_sample(),
            "volume_tolerance_mm3": VOLUME_TOLERANCE_MM3,
            "provenance": local_provenance(),
        }

    def save(self) -> None:
        write_report(self.output, self.report)

    async def call(self, name: str, args: dict) -> dict:
        self.report["calls"].append({"tool": name, "args": args, "at": time.time()})
        self.save()
        result = await self.client.call_tool(name, args)
        if getattr(result, "is_error", False):
            raise RuntimeError(f"{name} failed: {result.content}")
        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            return structured
        for item in getattr(result, "content", []) or []:
            text = getattr(item, "text", None)
            if text:
                decoded = json.loads(text)
                if isinstance(decoded, dict):
                    return decoded
        raise RuntimeError(f"{name} returned no structured payload")

    async def wait_job(self, job_id: str, budget: float = 600) -> dict:
        deadline = time.monotonic() + budget
        while True:
            terminal = await self.call("creo_get_job", {"job_id": job_id, "detail": "full"})
            status = terminal.get("status")
            if status not in ("queued", "running"):
                return terminal
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Job {job_id} did not reach a terminal state within {budget}s; "
                    "budget exhausted, do not resubmit"
                )
            await asyncio.sleep(1)

    async def submit_once(self, case_key: str, args: dict) -> dict:
        if case_key in self.submitted:
            raise RuntimeError(f"Case {case_key} already submitted; never resubmit")
        self.submitted.add(case_key)
        return await self.call("creo_execute_plan", args)

    async def snapshot(self, model_id: str) -> dict:
        from creo_mechdog.query_client import read_full_model

        return await read_full_model(self.call, model_id)

    @staticmethod
    def operation(record: dict, label: str) -> dict:
        for item in record.get("result", {}).get("operations", []):
            if item.get("label") == label:
                return item
        return {}

    async def run_case(self, case: dict, tag: str) -> dict:
        row: dict = {
            "case": case["case"],
            "scenario": case["scenario"],
            "judge": case["judge"],
            "expected_delta_mm3": case["expected_delta_mm3"],
        }
        if case["judge"] == "projection_only":
            row["status"] = "not_applicable_live"
            self.report["cases"].append(row)
            self.save()
            return row

        created = await self.submit_once(
            f"{case['case']}:base",
            {"operations": case["base_operations"], "model_name": case["model_name"]},
        )
        created_terminal = await self.wait_job(created["job_id"])
        if created_terminal.get("status") != "succeeded":
            raise RuntimeError(f"base creation failed for {case['case']}: {created_terminal}")
        model_id = created["model_id"]
        before = await self.snapshot(model_id)
        before_volume = before["inspection"]["volume_mm3"]
        model_state = {
            "edges": before["inspection"].get("edges", []),
            "surfaces": before["inspection"].get("surfaces", []),
            "datum_axes": before["inspection"].get("datum_axes", []),
        }
        operations = resolve_case_operations(case, model_state)
        created_revision = terminal_model_revision(
            created_terminal, f"{case['case']}:base creation"
        )
        submitted = await self.submit_once(
            case["case"],
            {
                "model_id": model_id,
                "expected_revision": created_revision,
                "operations": operations,
            },
        )
        terminal = await self.wait_job(submitted["job_id"])
        status = terminal.get("status")
        result = terminal.get("result", {})
        row.update(
            {
                "model_id": model_id,
                "base_job_id": created_terminal["job_id"],
                "job_id": submitted["job_id"],
                "status": status,
                "elapsed_seconds": terminal.get("elapsed_seconds"),
                "saved_file_reloaded_and_verified": result.get("saved_file_reloaded_and_verified"),
                "rollback_succeeded": result.get("rollback_succeeded"),
                "length_unit": (result.get("inspection") or {}).get("length_unit"),
            }
        )
        labels = [op.get("label") for op in operations]
        records = result.get("operations", [])
        row["operations"] = [
            {key: item.get(key) for key in (*OBSERVATION_KEYS, "execution_status", "effect_status")}
            for item in records
        ]
        if case["judge"] == "batch_failure":
            if status != "failed":
                raise RuntimeError(f"{case['case']}: expected a failed terminal, got {status}")
            row["batch_verdict"] = judge_batch_failure(records)
            if result.get("rollback_succeeded") is not True:
                row["batch_verdict"] = {
                    "status": "fail",
                    "problems": ["rollback_succeeded is not true"],
                }
            if result.get("saved_file_reloaded_and_verified") is True:
                row["batch_verdict"] = {
                    "status": "fail",
                    "problems": ["a failed plan must not claim a verified save"],
                }
        else:
            if status != "succeeded":
                raise RuntimeError(f"{case['case']}: expected success, got {status}")
            if result.get("saved_file_reloaded_and_verified") is not True:
                raise RuntimeError(f"{case['case']}: save/reload verification missing")
            record = self.operation(terminal, labels[0])
            row["measurement_verdict"] = judge_measurement(
                record, case["expected_delta_mm3"], VOLUME_TOLERANCE_MM3
            )
            after = await self.snapshot(model_id)
            after_volume = after["inspection"]["volume_mm3"]
            row["independent_delta_mm3"] = (
                after_volume - before_volume if after_volume is not None else None
            )
            application = record.get("reference_application") or {}
            row["reference_application"] = application
            application_ok = application.get("requested_set_count") == len(
                operations[0].get("references") or operations[0].get("surfaces") or []
            ) and application.get("applied_set_count") == application.get("requested_set_count")
            row["application_verdict"] = (
                "pass"
                if application_ok
                else ("unknown" if application.get("applied_set_count") is None else "fail")
            )
            if case["judge"].startswith("pull"):
                geometry = record.get("draft_geometry") or {}
                row["draft_geometry"] = geometry
                expected_reference = (
                    operations[0].get("pull_direction")
                    if case["judge"] == "pull_explicit"
                    else operations[0].get("neutral_plane")
                )
                row["pull_verdict"] = judge_pull_readback(geometry, expected_reference or {})
        self.report["cases"].append(row)
        self.save()
        return row

    async def run_all(self) -> None:
        from tools.mcp_readiness import wait_for_startup

        self.report["capabilities"] = await self.call("creo_capabilities", {})
        self.report["environment"] = await self.call("creo_check_environment", {})
        self.save()
        await wait_for_startup(self.client, self.report, self.output)
        status = await self.call("creo_session_status", {})
        assert status["connected"] is True, status
        try:
            tag = hashlib.sha256(self.run_id.encode("utf-8")).hexdigest()[:8]
            rows = []
            for case in build_cases(tag):
                rows.append(await self.run_case(case, tag))
            flip_rows = [r for r in rows if r["case"] in ("draft_flip_false", "draft_flip_true")]
            if len(flip_rows) == 2:
                deltas = [
                    (r.get("measurement_verdict") or {}).get("measured_delta_mm3")
                    for r in flip_rows
                ]
                self.report["flip_pair_opposite_signs"] = (
                    None if any(d is None for d in deltas) else (deltas[0] * deltas[1] < 0)
                )
            self.report.update(native_acceptance="recorded")
        except Exception as error:
            self.report.update(error=f"{type(error).__name__}: {error}")
            raise
        finally:
            self.save()


async def live(output: Path, run_id: str) -> None:
    from tools.test_t05_native import require_manual_start

    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=60,
    ) as client:
        runner = DetailFeatureAcceptance(client, output, run_id)
        runner.save()
        await runner.run_all()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    run_id = new_run_id()
    try:
        output = resolve_output(args.output, run_id)
    except ValueError as error:
        print(f"REFUSED BEFORE CONNECTION: {error}")
        return 2

    if not (args.live and args.confirm_session_usable):
        if args.live or args.confirm_session_usable:
            reason = "both --live and --confirm-session-usable are required"
        else:
            reason = "no live flags given"
        print(f"OFFLINE ONLY ({reason}): no MCP client, no Toolkit call, no Creo connection.")
        results = offline_checks(run_id)
        write_offline_report(output, run_id, results)
        print(f"offline_cases={len(results['cases'])} validated")
        print(f"unit_matrix={len(results['unit_matrix'])} rows (inch/mixed/unknown synthetic)")
        print(f"numeric_oracles_agree={results['numeric_oracles_agree']}")
        print(f"report={output}")
        print("LIVE NOT RUN: no native measurement was produced or claimed.")
        return 0

    asyncio.run(live(output, run_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
