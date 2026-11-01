"""DEV-051 T03 offline driver for the sheetmetal first-wall parameter contract.

Checks the fixed-frame depth/thickness matrix, the independent volume and
three-axis extent oracle, the closed-contour reference, the shared admission of
the standalone tool and execute_plan, and the legacy open-line regression. The
native source guard only proves that the committed fix is present in the
working tree; it is not native verification.

DEV-053 P08 (BUG-032 / FEAT-014 / FEAT-008) adds the frozen frame contract and
the three comparison groups: XY/depth1/t232, XY/depth232/t1/negative and the
standard YZ recipe (offset 92.5, depth 185, t 1, negative). Every group is
judged on bbox, COG, volume, the part-level thickness and the driving wall
faces - never on V=42920 alone, which all three groups share. It also checks
the wall_contract frame echo projection and the bounded wall-contour
(candidate edge) projection with wall_contour_status=eligible|ineligible|unknown,
real query codes and the current revision; eligible never promises flange
creation and never names itself "flange_available".

Default is strictly offline: no MCP client is instantiated and no Toolkit
connection is made. --live --confirm-session-usable runs the matrix against the
manually opened Creo session: five fresh models, one sheetmetal wall each, the
measured volume and the wall_contract record, then the closed-rectangle and
two-line rejections on the last model to prove the model and revision stay
untouched, then the three frame groups with the full bbox/COG/wall-face
assertions and the candidate-edge discovery. It never launches, restarts or
closes Creo, never injects a fault, never clears a protection and never
resubmits a job; a busy channel, an unknown terminal state or a polling timeout
stops the run and preserves the scene.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import re
import subprocess
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

from creo_mechdog.sheetmetal import (  # noqa: E402
    MATERIAL_SIDES,
    PRO_TK_BAD_CONTEXT,
    PRO_TK_NO_ERROR,
    normalize_wall_contract,
    project_wall_contour,
    wall_contour_status_from_code,
)
from tools.sheetmetal_live import (  # noqa: E402
    LiveRunner,
    LiveStop,
    failure_text,
    require_manual_start,
    unique_name,
)
from tools.sheetmetal_live import (
    new_run_id as live_run_id,
)
from tools.sheetmetal_live import (
    resolve_output as live_output,
)

LINE_LENGTH_MM = 185.0
MATRIX = ((1.0, 232.0), (232.0, 1.0), (1.0, 1.0), (2.0, 1.0), (0.5, 1.0))
REPORTED_VOLUME_MM3 = 9_957_440.0
VOLUME_TOLERANCE_MM3 = 0.01
BOUNDS_TOLERANCE_MM = 1e-6


# --- independent oracle ---------------------------------------------------
#
# Frozen frame semantics (DEV-053 P08), re-derived from the live-anchored
# recipes and cross-checked against the reported 2026-10-31 feedback:
#   * depth grows ONE-SIDED along the signed sketch normal
#     (direction=positive -> +normal, direction=negative -> -normal);
#   * thickness is the sheet gauge spread CENTERED on the sketch line,
#     in-plane perpendicular to it.
# The feedback's row-2 COG (0, 0.5, -116) proves the centered rule (a
# one-sided gauge would put the centroid at 0 or 1 for a line at v=0.5), and
# its row-1 COG (0, 0, 0.5) omits that same line offset: re-derived here the
# row-1 centroid is (0, 0.5, 0.5). The driver uses the derived values and
# records the correction.


def oracle_volume_mm3(depth: float, thickness: float, length: float = LINE_LENGTH_MM) -> float:
    """Line length x in-plane thin width x extrusion depth."""
    return length * thickness * depth


def oracle_bbox_mm(depth: float, thickness: float, length: float = LINE_LENGTH_MM) -> dict:
    """Extents per axis for a line along X on XY, extruded along +Z."""
    return {"x": length, "y": thickness, "z": depth}


def oracle_centroid_mm(depth: float, thickness: float, length: float = LINE_LENGTH_MM) -> dict:
    """Centroid for the legacy fixture line (0,0)->(length,0) on XY.

    The gauge is centered on the sketch line (y=0 here) and the depth grows
    one-sided along the signed sketch normal (+Z). (The pre-P08 formula grew
    the gauge one-sided to +Y; live bboxes - e.g. y in [-116,116] for a v=0
    line with t=232 - prove the centered rule.)
    """
    return {"x": length / 2.0, "y": 0.0, "z": depth / 2.0}


def near(actual: float, expected: float, tolerance: float = VOLUME_TOLERANCE_MM3) -> None:
    assert abs(actual - expected) <= max(tolerance, abs(expected) * 1e-9), (actual, expected)


# Named-plane frames as published by capabilities (u, v, sketch normal).
FRAMES = {
    "XY": {"u": (1.0, 0.0, 0.0), "v": (0.0, 1.0, 0.0), "normal": (0.0, 0.0, 1.0)},
    "XZ": {"u": (1.0, 0.0, 0.0), "v": (0.0, 0.0, 1.0), "normal": (0.0, -1.0, 0.0)},
    "YZ": {"u": (0.0, 1.0, 0.0), "v": (0.0, 0.0, 1.0), "normal": (1.0, 0.0, 0.0)},
}


def plate_oracle(
    plane: str,
    line: tuple[tuple[float, float], tuple[float, float]],
    depth: float,
    thickness: float,
    direction: str,
    offset: float = 0.0,
) -> dict:
    """Independent box oracle for one first wall on a named plane.

    line endpoints are (u, v) sketch coordinates and must run along +u/-u;
    offset shifts the sketch plane along the sketch normal. Returns the exact
    bounds, centroid, volume, the gauge axis index and the signed depth
    direction - everything a live case asserts, derived without reading any
    production code.
    """
    frame = FRAMES[plane]
    u, v, normal = frame["u"], frame["v"], frame["normal"]
    (u0, v0), (u1, v1) = line
    assert abs(v1 - v0) < 1e-12, "fixture lines must run along u so the gauge is along v"
    assert u1 != u0, "fixture line must be open with nonzero length"
    sign = 1.0 if direction == "positive" else -1.0
    low = [normal[i] * offset for i in range(3)]
    high = list(low)

    def spread(axis: tuple[float, float, float], a: float, b: float) -> None:
        for i in range(3):
            p, q = a * axis[i], b * axis[i]
            low[i] += min(p, q)
            high[i] += max(p, q)

    spread(u, min(u0, u1), max(u0, u1))
    mid_v = (v0 + v1) / 2.0
    spread(v, mid_v - thickness / 2.0, mid_v + thickness / 2.0)
    spread(normal, 0.0, sign * depth)
    length = abs(u1 - u0)
    centroid = [(low[i] + high[i]) / 2.0 for i in range(3)]
    gauge_axis = max(range(3), key=lambda i: abs(v[i]))
    depth_direction = [sign * normal[i] for i in range(3)]
    return {
        "bounds": [tuple(low), tuple(high)],
        "centroid_mm": centroid,
        "volume_mm3": length * thickness * depth,
        "line_length_mm": length,
        "gauge_axis": gauge_axis,
        "depth_direction": depth_direction,
        "sketch_normal": list(normal),
    }


# The three mandated comparison groups (DEV-053 P08). Frozen numbers are
# written out independently and cross-checked against plate_oracle below.
FRAME_GROUPS = (
    {
        "tag": "g1_xy_depth1_t232",
        "plane": "XY",
        "line": ((-92.5, 0.5), (92.5, 0.5)),
        "offset": 0.0,
        "depth": 1.0,
        "thickness": 232.0,
        "direction": "positive",
        "expected": {
            "bounds": [(-92.5, -115.5, 0.0), (92.5, 116.5, 1.0)],
            "centroid_mm": [0.0, 0.5, 0.5],
            "volume_mm3": 42_920.0,
            "part_thickness_mm": 232.0,
            "gauge_axis": 1,
        },
        "note": (
            "the historical 'old writing': a geometrically correct 185x232x1 horizontal "
            "plate, but the part is typed as a 232 mm sheet - the green/white wall faces "
            "are the 185x1 strips and every flange attach on the large-face boundary is "
            "PRO_TK_BAD_CONTEXT (-8). F5 reported COG (0,0,0.5) for this row; the derived "
            "centroid is (0,0.5,0.5) because the gauge is centered on the v=0.5 line - "
            "F5's own row-2 COG proves that rule."
        ),
    },
    {
        "tag": "g2_xy_depth232_t1_negative",
        "plane": "XY",
        "line": ((-92.5, 0.5), (92.5, 0.5)),
        "offset": 0.0,
        "depth": 232.0,
        "thickness": 1.0,
        "direction": "negative",
        "expected": {
            "bounds": [(-92.5, 0.0, -232.0), (92.5, 1.0, 0.0)],
            "centroid_mm": [0.0, 0.5, -116.0],
            "volume_mm3": 42_920.0,
            "part_thickness_mm": 1.0,
            "gauge_axis": 1,
        },
        "note": (
            "the corrected writing on XY: 1 mm gauge in Y, depth 232 down -Z. Volume and "
            "wall typing are right, but the plate is vertical (the reported cog "
            "(0,0.5,-116) matches exactly)."
        ),
    },
    {
        "tag": "g3_yz_offset92_depth185_t1_negative",
        "plane": "YZ",
        "line": ((-116.0, 0.5), (116.0, 0.5)),
        "offset": 92.5,
        "depth": 185.0,
        "thickness": 1.0,
        "direction": "negative",
        "expected": {
            "bounds": [(-92.5, -116.0, 0.0), (92.5, 116.0, 1.0)],
            "centroid_mm": [0.0, 0.0, 0.5],
            "volume_mm3": 42_920.0,
            "part_thickness_mm": 1.0,
            "gauge_axis": 2,
        },
        "note": (
            "the frozen standard recipe (examples/sheetmetal_base_yz.json): X+-92.5, "
            "Y+-116, Z[0,1], V=42920, COG (0,0,0.5) - the 185x232 faces at Z=0/1 are the "
            "green/white wall faces flanges attach to."
        ),
    },
)


# --- fixtures -------------------------------------------------------------


def wall_sketch(length: float = LINE_LENGTH_MM) -> dict:
    return {
        "op": "sketch",
        "label": "s1",
        "plane": "XY",
        "entities": [
            {"type": "line", "name": "wall_line", "start": [0.0, 0.0], "end": [length, 0.0]}
        ],
    }


def wall_op(depth: float, thickness: float, **overrides) -> dict:
    operation = {
        "op": "sheetmetal_wall",
        "label": "wall1",
        "sketch": "s1",
        "depth": depth,
        "thickness": thickness,
        "direction": "positive",
    }
    operation.update(overrides)
    return operation


# --- checks ---------------------------------------------------------------


def check_matrix() -> list[dict]:
    from creo_mechdog.schema import validate_operations

    rows = []
    for depth, thickness in MATRIX:
        validated = validate_operations([wall_sketch(), wall_op(depth, thickness)])
        operation = validated[1]
        assert operation["depth"] == depth, operation
        assert operation["thickness"] == thickness, operation
        assert operation["direction"] == "positive", operation
        volume = oracle_volume_mm3(depth, thickness)
        bbox = oracle_bbox_mm(depth, thickness)
        centroid = oracle_centroid_mm(depth, thickness)
        near(volume, LINE_LENGTH_MM * thickness * depth * 1.0)
        rows.append(
            {
                "depth_mm": depth,
                "thickness_mm": thickness,
                "line_length_mm": LINE_LENGTH_MM,
                "accepted": True,
                "depth_preserved": operation["depth"],
                "thickness_preserved": operation["thickness"],
                "expected_volume_mm3": volume,
                "expected_bbox_mm": bbox,
                "expected_centroid_mm": centroid,
                "native_result": "not_measured_offline",
            }
        )
    return rows


def check_reported_volume() -> dict:
    intended = oracle_volume_mm3(1.0, 232.0)
    replaced = LINE_LENGTH_MM * 232.0 * 232.0
    near(intended, 42_920.0)
    near(replaced, REPORTED_VOLUME_MM3, tolerance=0.5)
    return {
        "report": "0.3.2 S5: sheetmetal_wall(depth=1.0, thickness=232.0), 185 line",
        "reported_volume_mm3": REPORTED_VOLUME_MM3,
        "intended_volume_mm3": intended,
        "ratio": REPORTED_VOLUME_MM3 / intended,
        "reported_shape": "185 x 232 x 232 = line x thickness x thickness",
        "conclusion": (
            "The reported body keeps the 185 x 232 thin section and re-applies the "
            "232 thickness along the depth axis, so the requested depth 1 never reached "
            "the final geometry. Python passes both values unchanged, so the difference "
            "is in the native sheetmetal conversion, not the request."
        ),
        "explained_by": "depth_replaced_by_thickness_at_native_conversion",
    }


def check_closed_reference() -> dict:
    from creo_mechdog.schema import validate_operations

    rejected = []
    for entities, label in (
        (
            [{"type": "rectangle", "name": "plate", "min": [0.0, 0.0], "max": [40.0, 7.0]}],
            "rectangle",
        ),
        (
            [
                {
                    "type": "polyline",
                    "name": "outline",
                    "points": [[0.0, 0.0], [40.0, 0.0], [40.0, 7.0], [0.0, 7.0]],
                    "closed": True,
                }
            ],
            "closed_polyline",
        ),
        (
            [
                {
                    "type": "arc",
                    "name": "bend",
                    "center": [0.0, 0.0],
                    "radius": 20.0,
                    "start_angle": 0.0,
                    "end_angle": 90.0,
                }
            ],
            "arc",
        ),
        (
            [
                {"type": "line", "name": "l1", "start": [0.0, 0.0], "end": [90.0, 0.0]},
                {"type": "line", "name": "l2", "start": [90.0, 0.0], "end": [185.0, 0.0]},
            ],
            "two_line_chain",
        ),
        (
            [{"type": "centerline", "name": "axis", "start": [0.0, 0.0], "end": [185.0, 0.0]}],
            "centerline_only",
        ),
    ):
        try:
            validate_operations(
                [
                    {"op": "sketch", "label": "s1", "plane": "XY", "entities": entities},
                    wall_op(1.0, 1.0),
                ]
            )
        except ValueError as error:
            message = str(error)
            assert "exactly one open straight line" in message, (label, message)
            rejected.append({"section": label, "rejected": True, "message": message})
        else:
            raise AssertionError(f"{label} was accepted as a first wall section")
    return {"rejected": rejected, "model_untouched": "rejected_before_native_modelling"}


def check_paths() -> dict:
    from creo_mechdog.schema import validate_operations

    standalone = {
        "op": "sheetmetal_wall",
        "label": "wall1",
        "sketch": 12,
        "depth": 1.0,
        "thickness": 232.0,
        "direction": "positive",
    }
    tool = validate_operations([standalone])[0]
    assert tool == standalone, tool
    plan = validate_operations([wall_sketch(), wall_op(1.0, 232.0)])[1]
    assert plan["sketch"] == "s1" and plan["depth"] == 1.0 and plan["thickness"] == 232.0, plan
    legacy = validate_operations(
        [
            {
                "op": "sketch",
                "label": "s1",
                "plane": "XY",
                "entities": [
                    {"type": "line", "name": "wall_line", "start": [0.0, 0.0], "end": [40.0, 0.0]}
                ],
            },
            wall_op(30.0, 1.0),
        ]
    )[1]
    assert legacy["depth"] == 30.0 and legacy["thickness"] == 1.0, legacy
    near(oracle_volume_mm3(30.0, 1.0, 40.0), 1200.0)
    return {
        "standalone_tool": tool,
        "execute_plan": plan,
        "legacy_open_line_40_1_30": {
            "depth_mm": legacy["depth"],
            "thickness_mm": legacy["thickness"],
            "expected_volume_mm3": 1200.0,
        },
        "admission_shared_by": "creo_mechdog.schema.validate_operations",
    }


def frame_group_sketch(group: dict) -> dict:
    (u0, v0), (u1, v1) = group["line"]
    return {
        "op": "sketch",
        "label": "s1",
        "plane": group["plane"],
        "offset": group["offset"],
        "entities": [{"type": "line", "name": "wall_line", "start": [u0, v0], "end": [u1, v1]}],
    }


def frame_group_wall(group: dict) -> dict:
    return wall_op(group["depth"], group["thickness"], direction=group["direction"])


def near_bounds(actual, expected) -> None:
    for got, want in zip(actual, expected, strict=True):
        for a, b in zip(got, want, strict=True):
            near(a, b, BOUNDS_TOLERANCE_MM)


def near_vector(actual, expected, tolerance: float = BOUNDS_TOLERANCE_MM) -> None:
    for a, b in zip(actual, expected, strict=True):
        near(a, b, tolerance)


def check_frame_groups() -> dict:
    """The three comparison groups: bbox, COG, volume, part thickness, wall faces.

    The frozen numbers in FRAME_GROUPS and the independent plate_oracle
    derivation must agree exactly - neither side alone is trusted - and the
    G1/G3 pair proves why V=42920 can never be the whole verdict.
    """
    from creo_mechdog.schema import validate_operations

    rows = []
    for group in FRAME_GROUPS:
        derived = plate_oracle(
            group["plane"],
            group["line"],
            group["depth"],
            group["thickness"],
            group["direction"],
            group["offset"],
        )
        expected = group["expected"]
        near_vector(
            [c for corner in derived["bounds"] for c in corner],
            [c for corner in expected["bounds"] for c in corner],
        )
        near_vector(derived["centroid_mm"], expected["centroid_mm"])
        near(derived["volume_mm3"], expected["volume_mm3"])
        assert derived["gauge_axis"] == expected["gauge_axis"], (group["tag"], derived)
        assert group["thickness"] == expected["part_thickness_mm"], group["tag"]
        validated = validate_operations([frame_group_sketch(group), frame_group_wall(group)])
        operation = validated[1]
        assert operation["depth"] == group["depth"], operation
        assert operation["thickness"] == group["thickness"], operation
        assert operation["direction"] == group["direction"], operation
        rows.append(
            {
                "tag": group["tag"],
                "plane": group["plane"],
                "offset": group["offset"],
                "depth_mm": group["depth"],
                "thickness_mm": group["thickness"],
                "direction": group["direction"],
                "expected_bounds_mm": [list(corner) for corner in expected["bounds"]],
                "expected_centroid_mm": expected["centroid_mm"],
                "expected_volume_mm3": expected["volume_mm3"],
                "expected_part_thickness_mm": expected["part_thickness_mm"],
                "expected_gauge_axis": expected["gauge_axis"],
                "derived_matches_frozen": True,
                "wall_face_axis": expected["gauge_axis"],
                "note": group["note"],
                "native_result": "not_measured_offline",
            }
        )
    by_tag = {row["tag"]: row for row in rows}
    g1 = by_tag["g1_xy_depth1_t232"]
    g3 = by_tag["g3_yz_offset92_depth185_t1_negative"]
    assert g1["expected_volume_mm3"] == g3["expected_volume_mm3"] == 42_920.0
    assert g1["expected_part_thickness_mm"] == 232.0 and g3["expected_part_thickness_mm"] == 1.0
    assert g1["expected_gauge_axis"] != g3["expected_gauge_axis"]
    return {
        "groups": rows,
        "volume_alone_cannot_distinguish": {
            "shared_volume_mm3": 42_920.0,
            "g1_vs_g3_distinguishers": [
                "part_thickness_mm 232 vs 1",
                "gauge_axis Y(1) vs Z(2) - the green/white wall faces are the 185x1 strips "
                "vs the 185x232 faces",
                "centroid y 0.5 vs 0 (gauge centered on a v=0.5 vs v=0.5 line in different planes)",
            ],
            "rule": "judge bbox, COG, part thickness and the driving wall faces together",
        },
        "frame_rule": (
            "depth one-sided along the signed sketch normal; thickness centered on the "
            "sketch line, in-plane perpendicular"
        ),
        "passed": True,
    }


def check_example_recipe() -> dict:
    """examples/sheetmetal_base_yz.json must match the frozen G3 recipe exactly."""
    from creo_mechdog.schema import validate_operations

    recipe = json.loads((ROOT / "examples" / "sheetmetal_base_yz.json").read_text(encoding="utf-8"))
    assert recipe["model_type"] == "sheetmetal", recipe
    operations = validate_operations(recipe["operations"])
    sketch, wall = operations
    group = FRAME_GROUPS[2]
    assert sketch["plane"] == group["plane"] == "YZ", sketch
    assert sketch["offset"] == group["offset"] == 92.5, sketch
    (u0, v0), (u1, v1) = group["line"]
    assert sketch["entities"][0]["start"] == [u0, v0], sketch
    assert sketch["entities"][0]["end"] == [u1, v1], sketch
    assert wall["depth"] == group["depth"] == 185.0, wall
    assert wall["thickness"] == group["thickness"] == 1.0, wall
    assert wall["direction"] == group["direction"] == "negative", wall
    near(recipe["assertions"]["volume_mm3"], group["expected"]["volume_mm3"])
    derived = plate_oracle(
        group["plane"],
        group["line"],
        group["depth"],
        group["thickness"],
        group["direction"],
        group["offset"],
    )
    near(derived["volume_mm3"], 42_920.0)
    return {
        "file": "examples/sheetmetal_base_yz.json",
        "operations_accepted": True,
        "frozen_targets": {
            "bounds_mm": [list(corner) for corner in group["expected"]["bounds"]],
            "centroid_mm": group["expected"]["centroid_mm"],
            "volume_mm3": 42_920.0,
        },
        "edge_selection_rule": "select edges by geometry from the current inspection",
        "passed": True,
    }


def check_wall_contour_projection() -> dict:
    """Candidate-edge projection: wall edge, rim/side edge, query failure, missing."""
    assert wall_contour_status_from_code(PRO_TK_NO_ERROR) == "eligible"
    assert wall_contour_status_from_code(PRO_TK_BAD_CONTEXT) == "ineligible"
    assert wall_contour_status_from_code(-2) == "unknown"
    assert wall_contour_status_from_code(17) == "unknown"
    assert wall_contour_status_from_code(None) is None
    assert wall_contour_status_from_code("0") is None
    inspection = {
        "edges": [
            {"id": 211, "start": [0, 0, 0], "end": [185, 0, 0]},  # wall-face edge
            {"id": 224, "start": [0, 0, 0], "end": [0, 0, 1]},  # rim/side edge
            {"id": 236, "start": [0, 0, 0], "end": [0, 232, 0]},  # query failure
            {"id": 247, "start": [0, 0, 0], "end": [185, 232, 0]},  # not queried (budget)
        ],
        "wall_contour_check": {
            "query": "ProSmtedgeContourGet",
            "enabled": True,
            "bounded": True,
            "budget": 256,
            "edges": [
                {"edge_id": 211, "wall_contour_query_code": PRO_TK_NO_ERROR},
                {"edge_id": 224, "wall_contour_query_code": PRO_TK_BAD_CONTEXT},
                {"edge_id": 236, "wall_contour_query_code": -2},
                {"edge_id": 999, "wall_contour_query_code": PRO_TK_NO_ERROR},  # stale id
                {"edge_id": 253, "wall_contour_query_code": "0"},  # malformed
            ],
        },
    }
    projected = project_wall_contour(inspection, revision=3)
    edges = {record["id"]: record for record in projected["edges"]}
    assert edges[211]["wall_contour_status"] == "eligible", edges[211]
    assert edges[211]["wall_contour_query_code"] == PRO_TK_NO_ERROR
    assert edges[224]["wall_contour_status"] == "ineligible", edges[224]
    assert edges[236]["wall_contour_status"] == "unknown", edges[236]
    assert edges[236]["wall_contour_query_code"] == -2  # the real code is preserved
    assert "wall_contour_status" not in edges[247], edges[247]  # missing stays missing
    summary = projected["wall_contour_check"]
    assert summary["revision"] == 3, summary
    assert summary["checked_edges"] == 5, summary
    assert summary["eligible"] == 2, summary  # 211 and the stale 999 both counted
    assert summary["ineligible"] == 1 and summary["unknown"] == 2, summary
    assert summary["enabled"] is True and summary["bounded"] is True, summary
    malformed = [
        record for record in projected["wall_contour_records"] if record.get("edge_id") == 253
    ]
    assert malformed[0]["wall_contour_status"] == "unknown", malformed
    assert malformed[0]["wall_contour_query_code"] == "0", malformed  # raw value kept
    # eligible never promises a flange and never claims an unconditional flag
    assert "does not promise flange creation" in summary["meaning"], summary
    assert "flange_available" not in json.dumps(projected)
    missing = project_wall_contour({}, revision=None)
    assert missing["wall_contour_check"]["checked_edges"] == 0
    assert missing["wall_contour_check"]["revision"] is None
    assert all("wall_contour_status" not in record for record in missing["edges"] or [])
    string_revision = project_wall_contour(inspection, revision="3")
    assert string_revision["wall_contour_check"]["revision"] is None
    return {
        "status_table": {
            str(PRO_TK_NO_ERROR): "eligible",
            str(PRO_TK_BAD_CONTEXT): "ineligible",
            "other": "unknown",
        },
        "cases": [
            "wall_face_edge_eligible",
            "rim_side_edge_ineligible",
            "query_failure_unknown_with_real_code",
            "not_queried_edge_stays_missing",
            "malformed_code_degrades_to_unknown",
            "stale_edge_id_not_joined",
            "revision_stamped_only_as_int",
        ],
        "adjacent_bend_ends_note": (
            "eligible does not unlock the adjacent_bend_ends pre-creation rejection; "
            "that guard stays in native/advanced.cpp generic_sheetmetal_flange"
        ),
        "passed": True,
    }


def check_wall_contract_projection() -> dict:
    """wall_contract frame echo: measurements kept, malformation degrades to unknown."""
    assert normalize_wall_contract(None) is None
    assert normalize_wall_contract("wall_contract") is None
    block = {
        "line_length_mm": 185.0,
        "expected_volume_mm3": 42_920.0,
        "measured_volume_mm3": 42_920.0,
        "driving_face_id": 60,
        "driving_axis": 2,
        "part_thickness_before_mm": 3.71,
        "part_thickness_mm": 1.0,
        "part_thickness_synced": True,
        "frame": {
            "sketch_normal": [0.0, 0.0, 1.0],
            "sketch_origin": [0.0, 0.0, 0.0],
            "depth_direction": [0.0, 0.0, -1.0],
            "thickness_direction": [0.0, 0.0, 1.0],
            "material_side": "opposite_thickness_direction",
        },
        "wall_face_ids": [305, 306, "307", 3.5],
        "parameter_hint": "thickness >= depth: measured axes only",
    }
    entry = normalize_wall_contract(block)
    assert entry["frame"]["sketch_normal"] == [0.0, 0.0, 1.0], entry
    assert entry["frame"]["depth_direction"] == [0.0, 0.0, -1.0], entry
    assert entry["frame"]["material_side"] in MATERIAL_SIDES, entry
    assert entry["wall_face_ids"] == [305, 306], entry  # non-ints dropped
    assert entry["parameter_hint"].startswith("thickness >= depth"), entry
    degraded = normalize_wall_contract(
        {
            "frame": {
                "sketch_normal": [0.0, 0.0, 2.0],  # not unit -> unknown
                "depth_direction": [0.0, 0.0, 1.0],
                "thickness_direction": [1.0, 0.0, 0.0],
                "material_side": "left",  # not in the frozen enum
            },
            "wall_face_ids": "not-a-list",
        }
    )
    assert degraded["frame"]["sketch_normal"] is None, degraded
    assert degraded["frame"]["material_side"] is None, degraded
    assert degraded["frame"]["depth_direction"] == [0.0, 0.0, 1.0], degraded
    assert degraded["wall_face_ids"] is None, degraded
    legacy = normalize_wall_contract({"line_length_mm": 185.0})
    assert legacy["frame"] is None and legacy["wall_face_ids"] is None, legacy
    assert legacy["part_thickness_mm"] is None, legacy
    return {
        "rules": [
            "missing block stays missing",
            "non-unit direction degrades that field to null",
            "material_side only from the frozen enum",
            "wall_face_ids keeps integers only",
            "parameter_hint is advisory and never a rejection",
        ],
        "passed": True,
    }


# BUG-090: these SDK APIs are missing from some SDK generations (Creo 10 lacks
# ProSmtPartThicknessValueGet), so their calls may only compile inside the
# matching MECHDOG_HAS_<name> capability guard generated by tools/
# generate_constants.py.
GATED_SDK_CALLS = ("ProSmtPartThicknessGet", "ProSmtPartThicknessValueGet")


def unguarded_sdk_calls(source: str) -> list[str]:
    """Lines calling a gated SDK API outside its capability guard.

    A call is only accepted where the matching MECHDOG_HAS_<name> macro is
    defined: the positive branch of its #ifdef/#ifndef conditional. Comment text
    is not compiled and therefore never counts as a call.
    """
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    problems = []
    stack: list[tuple[list[str], bool]] = []
    for line in stripped.splitlines():
        directive = line.strip()
        if directive.startswith("#ifndef "):
            stack.append(([directive.split()[1]], False))
        elif directive.startswith("#ifdef "):
            stack.append(([directive.split()[1]], True))
        elif directive.startswith("#elif"):
            if stack:
                stack[-1] = (re.findall(r"defined\s*\(\s*(\w+)\s*\)", directive), True)
        elif directive.startswith("#else"):
            if stack:
                names, active = stack[-1]
                stack[-1] = (names, not active)
        elif directive.startswith("#endif"):
            if stack:
                stack.pop()
        elif directive.startswith("#if"):
            stack.append((re.findall(r"defined\s*\(\s*(\w+)\s*\)", directive), True))
        for name in GATED_SDK_CALLS:
            if re.search(r"\b" + name + r"\s*\(", line):
                macro = "MECHDOG_HAS_" + name
                if not any(active and macro in names for names, active in stack):
                    problems.append(line.strip())
    return problems


def check_native_source() -> dict:
    """Static guard only: proves the committed fix is in the tree, not that it runs."""
    source = (ROOT / "native" / "advanced.cpp").read_text(encoding="utf-8", errors="replace")
    generic = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8", errors="replace")
    checks = {
        "section_admission": "first_wall_line_length" in source,
        "thickness_axis_face": "if (fabs(normal[axis]) < 0.999)" in source,
        "volume_identity_guard": "SHEETMETAL_WALL_VOLUME" in source,
        "contract_recorded": '"wall_contract"' in source,
        "largest_face_heuristic_removed": "std::sort(e.begin(), e.end());" not in source,
        # BUG-032/T03: the native wall must read, sync and re-prove the
        # part-level sheetmetal thickness instead of trusting the geometry.
        "part_thickness_read": "ProSmtPartThicknessValueGet(" in source,
        "part_thickness_dimension_sync": "ProSmtPartThicknessGet" in source
        and "ProDimensionValueSet" in source,
        "part_thickness_regen_recheck": "SHEETMETAL_WALL_PART_THICKNESS" in source,
        "part_thickness_mismatch_fails": "did not sync the part thickness parameter" in source,
        # BUG-090: SDK-missing APIs stay out of the compile unit behind the
        # generated capability macros; every read shares one model-read helper
        # (definition, two first-wall checks, the relief record and the N06
        # adjacent-bend-ends pre-check), an unreadable thickness fails the
        # first wall explicitly and only the informational flange fields may
        # degrade to null.
        "part_thickness_api_gated": not unguarded_sdk_calls(source),
        "part_thickness_unified_read": source.count("part_thickness_read(") == 5,
        "part_thickness_parameter_fallback": "ProParameterValueWithUnitsGet" in source,
        "part_thickness_unknown_fails_wall": "could not read the part-level sheetmetal thickness"
        in source,
        "part_thickness_informational_null": "thickness_known ? J(thickness) : J()" in source,
        # P08/BUG-032: the measured frame echo and the measured wall faces.
        "frame_echo_recorded": '"frame"' in source and '"sketch_normal"' in source,
        "frame_depth_direction": '"depth_direction"' in source,
        "frame_thickness_direction": '"thickness_direction"' in source,
        "frame_material_side": '"material_side"' in source
        and '"opposite_thickness_direction"' in source,
        "wall_face_ids_echo": '"wall_face_ids"' in source and "PRO_SMT_SURF_FACE" in source,
        "parameter_hint_nonblocking": '"parameter_hint"' in source
        and "This hint does not reject" in source,
        # The corrected -8 guidance names the sketch plane/direction recipe and
        # the frozen example instead of only restating the parameters.
        "attach_error_names_the_sketch_recipe": "examples/sheetmetal_base_yz" in source,
        # FEAT-014: the adjacent-bend-ends pre-creation rejection must remain;
        # a successful candidate-edge query never unlocks it.
        "adjacent_bend_ends_guard_still_rejects": "adjacent_bend_ends" in source
        and "flange_adjacent_bend_end_evidence" in source,
        # P08/FEAT-014: bounded candidate-edge discovery in generic.cpp
        # inspection - sheetmetal parts only, budget-capped, read-only, real
        # query codes, never a fabricated status and never an unconditional
        # "flange_available" flag.
        "wall_contour_block_emitted": '"wall_contour_check"' in generic
        and '"ProSmtedgeContourGet"' in generic,
        "wall_contour_budget_bound": "WALL_CONTOUR_EDGE_BUDGET" in generic
        and "wall_contour_bounded" in generic,
        "wall_contour_real_code_kept": '"wall_contour_query_code"' in generic,
        "wall_contour_sheetmetal_gate_only": "PROMDLSTYPE_PART_SHEETMETAL" in generic
        and "wall_contour_query_enabled" in generic,
        "wall_contour_no_fabricated_status": '"eligible"' not in generic
        and '"ineligible"' not in generic,
        "flange_available_name_removed": "flange_available" not in source
        and "flange_available" not in generic,
    }
    missing = [name for name, present in checks.items() if not present]
    assert not missing, f"native source guard missing: {missing}"
    return {
        "static_source_assertions": checks,
        "unguarded_sdk_calls": unguarded_sdk_calls(source),
        "note": "Source presence only; native geometry is unverified until the live stage.",
    }


# --- live acceptance ------------------------------------------------------

LIVE_CASES = (
    {"tag": "t03_d1_t232", "depth": 1.0, "thickness": 232.0},
    {"tag": "t03_d232_t1", "depth": 232.0, "thickness": 1.0},
    {"tag": "t03_d1_t1", "depth": 1.0, "thickness": 1.0},
    {"tag": "t03_d2_t1", "depth": 2.0, "thickness": 1.0},
    {"tag": "t03_d05_t1", "depth": 0.5, "thickness": 1.0},
)

REJECTION_SECTIONS = (
    (
        "closed_rectangle",
        [{"type": "rectangle", "name": "plate", "min": [0.0, 0.0], "max": [185.0, 232.0]}],
    ),
    (
        "two_line_chain",
        [
            {"type": "line", "name": "l1", "start": [0.0, 0.0], "end": [90.0, 0.0]},
            {"type": "line", "name": "l2", "start": [90.0, 0.0], "end": [185.0, 0.0]},
        ],
    ),
)


def volume_verdict(
    depth: float, thickness: float, measured: float | None, length: float = LINE_LENGTH_MM
) -> dict:
    expected = oracle_volume_mm3(depth, thickness, length)
    tolerance = max(VOLUME_TOLERANCE_MM3, abs(expected) * 1e-3)
    if measured is None:
        return {
            "expected_volume_mm3": expected,
            "tolerance_mm3": tolerance,
            "abs_error_mm3": None,
            "passed": False,
        }
    error = abs(float(measured) - expected)
    return {
        "expected_volume_mm3": expected,
        "tolerance_mm3": tolerance,
        "abs_error_mm3": error,
        "passed": error <= tolerance,
    }


THICKNESS_TOLERANCE_MM = 1e-6


def thickness_verdict(thickness_mm: float, contract: dict) -> dict:
    """BUG-032: the native part-level thickness must agree with the request.

    A wall may only pass when its contract carries a *measured* native part
    thickness equal to the requested wall thickness. The 2026-10-29 round 6
    defect shape - geometry 1 mm while ProSmtPartThicknessValueGet reads the
    3.71 mm template default - is a thickness source contradiction and must
    fail here, even when the volume and bounding box are correct.
    """
    native = contract.get("part_thickness_mm")
    entry: dict = {
        "requested_thickness_mm": thickness_mm,
        "native_part_thickness_mm": native,
        "part_thickness_synced": contract.get("part_thickness_synced"),
    }
    if native is None:
        entry.update(
            passed=False,
            reason="wall_contract carries no measured native part thickness",
        )
        return entry
    error = abs(float(native) - float(thickness_mm))
    entry["abs_error_mm"] = error
    entry["passed"] = error <= THICKNESS_TOLERANCE_MM
    if not entry["passed"]:
        entry["reason"] = (
            "thickness source contradiction: the part-level sheetmetal thickness "
            f"({native} mm) does not match the requested wall thickness "
            f"({thickness_mm} mm); geometry alone does not prove the parameter"
        )
    return entry


async def run_matrix_case(runner: LiveRunner, case: dict) -> dict:
    """One fresh model, one first wall, one measured volume."""
    depth, thickness = case["depth"], case["thickness"]
    name = unique_name(case["tag"])
    created = await runner.submit(
        f"{case['tag']}:new-wall",
        "creo_execute_plan",
        {
            "model_name": name,
            "model_type": "sheetmetal",
            "operations": [wall_sketch(), wall_op(depth, thickness)],
        },
    )
    job_id, model_id = created["job_id"], created["model_id"]
    terminal = await runner.wait_job(job_id)
    entry: dict = {
        "case": case["tag"],
        "depth_mm": depth,
        "thickness_mm": thickness,
        "line_length_mm": LINE_LENGTH_MM,
        "model_name": name,
        "model_id": model_id,
        "job_id": job_id,
        "status": terminal.get("status"),
        "revision": terminal.get("revision"),
        "saved_file_reloaded_and_verified": (terminal.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ),
    }
    if terminal.get("status") != "succeeded":
        verdict = volume_verdict(depth, thickness, None)
        entry.update(
            expected_volume_mm3=verdict["expected_volume_mm3"],
            tolerance_mm3=verdict["tolerance_mm3"],
            failure=failure_text(terminal),
            passed=False,
            note="the wall was not created; the raw failure is kept, expectations unchanged",
        )
        return runner.case(entry)

    snapshot = await runner.snapshot(model_id)
    measured = runner.volume(snapshot)
    verdict = volume_verdict(depth, thickness, measured)
    contract = (runner.record(snapshot, "wall1") or {}).get("wall_contract") or {}
    thickness_check = thickness_verdict(thickness, contract)
    entry.update(
        measured_volume_mm3=measured,
        expected_volume_mm3=verdict["expected_volume_mm3"],
        tolerance_mm3=verdict["tolerance_mm3"],
        abs_error_mm3=verdict["abs_error_mm3"],
        wall_contract=contract,
        thickness_source=thickness_check,
        feature_types=runner.feature_types(snapshot),
        passed=bool(
            verdict["passed"]
            and thickness_check["passed"]
            and entry["saved_file_reloaded_and_verified"] is True
        ),
    )
    if (depth, thickness) == (1.0, 232.0):
        reproduces = measured is not None and abs(float(measured) - REPORTED_VOLUME_MM3) <= 0.5
        entry["reported_error_volume_mm3"] = REPORTED_VOLUME_MM3
        entry["reproduces_reported_error_volume"] = reproduces
    return runner.case(entry)


async def open_rejection_anchor(runner: LiveRunner) -> dict:
    """A sketch-only sheetmetal model, so the admission path is still observable.

    The rejection contract is Python-side admission; it does not need a wall. This
    anchor exists only when every matrix case failed, and it is recorded as such.
    """
    name = unique_name("t03_reject_anchor")
    created = await runner.submit(
        "rejection_anchor:new-sketch",
        "creo_execute_plan",
        {"model_name": name, "model_type": "sheetmetal", "operations": [wall_sketch()]},
    )
    terminal = await runner.wait_job(created["job_id"])
    runner.report["rejection_anchor"] = {
        "model_name": name,
        "model_id": created["model_id"],
        "job_id": created["job_id"],
        "status": terminal.get("status"),
        "reason": "no matrix case succeeded, so the rejection check uses a sketch-only model",
    }
    if terminal.get("status") != "succeeded":
        raise LiveStop(f"rejection anchor sketch failed: {failure_text(terminal)}")
    return {"model_id": created["model_id"]}


async def run_rejection_case(runner: LiveRunner, anchor: dict) -> dict:
    """Illegal first-wall sections must be refused before any feature exists."""
    model_id = anchor["model_id"]
    before = await runner.snapshot(model_id)
    revision = before.get("revision")
    volume = runner.volume(before)
    sections = []
    for name, entities in REJECTION_SECTIONS:
        answer = await runner.probe(
            "creo_execute_plan",
            {
                "model_id": model_id,
                "expected_revision": revision,
                "operations": [
                    {"op": "sketch", "label": "s1", "plane": "XY", "entities": entities},
                    wall_op(1.0, 1.0),
                ],
            },
        )
        body = answer["structured"] or {}
        message = body.get("error") or body.get("message") or answer["text"]
        sections.append(
            {
                "section": name,
                "rejected": bool(answer["is_error"]),
                "job_id": body.get("job_id"),
                "message": str(message)[:600],
            }
        )
    after = await runner.snapshot(model_id)
    unchanged = (
        after.get("revision") == revision
        and runner.volume(after) == volume
        and not any(section["job_id"] for section in sections)
    )
    return runner.case(
        {
            "case": "rejection_before_modelling",
            "model_id": model_id,
            "revision_before": revision,
            "revision_after": after.get("revision"),
            "volume_before_mm3": volume,
            "volume_after_mm3": runner.volume(after),
            "sections": sections,
            "model_and_revision_unchanged": unchanged,
            "passed": bool(unchanged and all(section["rejected"] for section in sections)),
        }
    )


async def run_frame_group_case(runner: LiveRunner, group: dict) -> dict:
    """One fresh model per comparison group with the full frame assertions.

    Verdict needs bbox, COG, volume, the part-level thickness and the driving
    wall faces together - V=42920 alone passes all three groups and proves
    nothing about orientation or wall typing.
    """
    expected = group["expected"]
    name = unique_name(group["tag"])
    created = await runner.submit(
        f"{group['tag']}:new-wall",
        "creo_execute_plan",
        {
            "model_name": name,
            "model_type": "sheetmetal",
            "operations": [frame_group_sketch(group), frame_group_wall(group)],
        },
    )
    job_id, model_id = created["job_id"], created["model_id"]
    terminal = await runner.wait_job(job_id)
    entry: dict = {
        "case": group["tag"],
        "plane": group["plane"],
        "offset": group["offset"],
        "depth_mm": group["depth"],
        "thickness_mm": group["thickness"],
        "direction": group["direction"],
        "model_name": name,
        "model_id": model_id,
        "job_id": job_id,
        "status": terminal.get("status"),
        "revision": terminal.get("revision"),
        "expected_bounds_mm": [list(corner) for corner in expected["bounds"]],
        "expected_centroid_mm": expected["centroid_mm"],
        "expected_volume_mm3": expected["volume_mm3"],
        "expected_part_thickness_mm": expected["part_thickness_mm"],
        "expected_gauge_axis": expected["gauge_axis"],
    }
    if terminal.get("status") != "succeeded":
        entry.update(failure=failure_text(terminal), passed=False)
        return runner.case(entry)

    snapshot = await runner.snapshot(model_id)
    inspection = runner.inspection(snapshot)
    measured = runner.volume(snapshot)
    bounds = active_body_bounds(inspection)
    centroid = inspection.get("center_of_gravity")
    (u0, _), (u1, _) = group["line"]
    verdict = volume_verdict(group["depth"], group["thickness"], measured, length=abs(u1 - u0))
    contract = (runner.record(snapshot, "wall1") or {}).get("wall_contract") or {}
    frame_contract = normalize_wall_contract(contract) or {}
    thickness_check = thickness_verdict(group["thickness"], frame_contract)
    frame = frame_contract.get("frame") or {}
    wall_face_ids = frame_contract.get("wall_face_ids")
    checks = {
        "volume": verdict["passed"],
        "bounds": bounds_match(bounds, expected["bounds"]),
        "centroid": isinstance(centroid, list)
        and all(
            abs(a - b) <= BOUNDS_TOLERANCE_MM
            for a, b in zip(centroid, expected["centroid_mm"], strict=True)
        ),
        "part_thickness": thickness_check["passed"],
        "driving_axis": frame_contract.get("driving_axis") == expected["gauge_axis"],
        "frame_normal": is_parallel(frame.get("sketch_normal"), group_plane_normal(group)),
        "depth_direction": is_parallel(
            frame.get("depth_direction"), expected_depth_direction(group)
        ),
        "thickness_direction": frame.get("thickness_direction") is not None,
        "material_side": frame.get("material_side") in MATERIAL_SIDES,
        "wall_faces": bool(wall_face_ids),
    }
    hint_expected = group["thickness"] >= group["depth"]
    checks["parameter_hint"] = (frame_contract.get("parameter_hint") is not None) == hint_expected
    projected = project_wall_contour(inspection, revision=snapshot.get("revision"))
    summary = projected["wall_contour_check"]
    checks["wall_contour_enabled"] = summary.get("enabled") is True
    checks["wall_contour_discovered"] = summary.get("eligible", 0) >= 2
    statuses = {
        record.get("wall_contour_status")
        for record in projected["edges"]
        if "wall_contour_status" in record
    }
    checks["wall_contour_statuses"] = statuses <= {"eligible", "ineligible", "unknown"}
    entry.update(
        measured_volume_mm3=measured,
        abs_error_mm3=verdict["abs_error_mm3"],
        measured_bounds_mm=[list(corner) for corner in bounds] if bounds else None,
        measured_centroid_mm=centroid,
        wall_contract=frame_contract,
        wall_contour_check=summary,
        checks=checks,
        saved_file_reloaded_and_verified=(terminal.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ),
    )
    entry["passed"] = bool(
        all(checks.values()) and entry["saved_file_reloaded_and_verified"] is True
    )
    return runner.case(entry)


def active_body_bounds(inspection: dict) -> list | None:
    for body in inspection.get("bodies") or []:
        bbox = body.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 2:
            return [tuple(corner) for corner in bbox]
    return None


def bounds_match(actual, expected) -> bool:
    if not isinstance(actual, list) or len(actual) != len(expected):
        return False
    for got, want in zip(actual, expected, strict=True):
        for a, b in zip(got, want, strict=True):
            try:
                if abs(float(a) - float(b)) > BOUNDS_TOLERANCE_MM:
                    return False
            except (TypeError, ValueError):
                return False
    return True


def group_plane_normal(group: dict) -> list[float]:
    return list(FRAMES[group["plane"]]["normal"])


def expected_depth_direction(group: dict) -> list[float]:
    sign = 1.0 if group["direction"] == "positive" else -1.0
    return [sign * value for value in FRAMES[group["plane"]]["normal"]]


def is_parallel(actual, expected) -> bool:
    if not isinstance(actual, list) or len(actual) != 3 or expected is None:
        return False
    dot = sum(a * b for a, b in zip(actual, expected, strict=True))
    return abs(abs(dot) - 1) <= 1e-6


async def live(output: Path, run_id: str) -> int:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=180) as client:
        runner = LiveRunner(
            client,
            output,
            "BUG-032 / DEV-051 T03 / DEV-053 P08",
            "first-wall depth/thickness matrix: live volume, wall_contract, pre-modelling "
            "rejection, the three frame groups and the candidate-edge discovery",
            run_id,
        )
        try:
            await runner.start()
            anchor = None
            for case in LIVE_CASES:
                entry = await run_matrix_case(runner, case)
                if entry["passed"] and anchor is None:
                    anchor = entry
            if anchor is None:
                anchor = await open_rejection_anchor(runner)
            await run_rejection_case(runner, anchor)
            for group in FRAME_GROUPS:
                await run_frame_group_case(runner, group)
        except BaseException as error:
            runner.report["stopped"] = f"{type(error).__name__}: {error}"
            runner.finish()
            raise
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    rows = [
        {
            key: case.get(key)
            for key in (
                "case",
                "status",
                "measured_volume_mm3",
                "expected_volume_mm3",
                "abs_error_mm3",
                "passed",
            )
        }
        for case in runner.report["cases"]
    ]
    print(json.dumps({"passed": runner.report["passed"], "cases": rows}, ensure_ascii=False))
    return 0 if runner.report["passed"] else 1


def run_unit_module() -> dict:
    from tests.unit import test_sheetmetal_contract

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_sheetmetal_contract)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    return {
        "module": "tests.unit.test_sheetmetal_contract",
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
        else ROOT / "build" / "sheetmetal_contract" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
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
    names.update(("tools/test_sheetmetal_contract.py", "tests/unit/test_sheetmetal_contract.py"))
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in sorted(names)
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


def write_offline_report(output: Path, run_id: str, results: dict) -> dict:
    report = {
        "task": "BUG-032 / DEV-051 T03 / DEV-053 P08",
        "scope": (
            "sheetmetal first wall: fixed-frame depth/thickness matrix, admission, the three "
            "frame comparison groups, the frozen YZ recipe and the wall-contour projection"
        ),
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: parameter contract, independent oracle, shared admission, "
            "frame groups and result projections validated. No Toolkit connection, no native "
            "geometry; live execution is scheduled separately by the orchestrator."
        ),
        "oracle": {
            "line_length_mm": LINE_LENGTH_MM,
            "volume_formula": "line_length_mm * thickness_mm * depth_mm",
            "bbox_axes": "x=line, y=in-plane thin width, z=extrusion depth",
            "frame_rule": (
                "depth one-sided along the signed sketch normal; thickness centered on the "
                "sketch line, in-plane perpendicular"
            ),
            "tolerance_mm3": VOLUME_TOLERANCE_MM3,
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
        run_id = live_run_id()
        return asyncio.run(live(live_output("sheetmetal_contract", run_id, args.output), run_id))

    run_id = new_run_id()
    output = resolve_output(args.output, run_id)
    results = {
        "matrix": check_matrix(),
        "reported_volume": check_reported_volume(),
        "closed_reference_and_rejections": check_closed_reference(),
        "paths_and_legacy": check_paths(),
        "frame_groups": check_frame_groups(),
        "example_recipe": check_example_recipe(),
        "wall_contour_projection": check_wall_contour_projection(),
        "wall_contract_projection": check_wall_contract_projection(),
        "native_source": check_native_source(),
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
