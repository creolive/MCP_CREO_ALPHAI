"""FEAT-035 T12 drivers: offline contract report; live remainder via --live.

The three cases already accepted on 2026-10-29 (counterbore flat seat, 90
degree countersink, 180 degree contract refusal) run only with
``--include-passed-cases`` and are never redone by default. The default live
run covers the remaining contract scope: blind depth, direction (hole axis
along the placement normal), supported dimension edits, failure rollback and
save/reload consistency. Every case carries an independent geometry oracle
(removed volume against the flat-bottom analytical formula, face-count delta,
dimension readback and cylinder face axis/bbox); a tool "success" alone never
passes a case.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.unit import test_native_countersink as fixture  # noqa: E402
from tools.sheetmetal_live import (  # noqa: E402
    LiveRunner,
    failure_text,
    require_manual_start,
    unique_name,
)

HANG_BUDGET_SECONDS = 180.0
PLATE_VOLUME_MM3 = 50.0 * 50.0 * 10.0
PLATE_TOP_Z = 10.0
PLATE_PLAN = [
    {
        "op": "sketch",
        "label": "plate_sketch",
        "plane": "XY",
        "entities": [
            {"type": "rectangle", "name": "plate", "min": [0.0, 0.0], "max": [50.0, 50.0]}
        ],
    },
    {
        "op": "extrude",
        "label": "plate",
        "sketch": "plate_sketch",
        "depth": 10.0,
        "mode": "add",
        "direction": "positive",
        "depth_type": "blind",
    },
]


def plane_record(record: dict) -> dict:
    normal = record.get("normal")
    origin = record.get("origin")
    return {
        "id": record.get("id"),
        "normal": normal if isinstance(normal, list) else None,
        "origin": origin if isinstance(origin, list) else None,
    }


def pick_geometry(snapshot: dict) -> dict:
    """Top face (+Z at z=10), side face (x=0) and the datum planes of the plate."""
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    surfaces = [
        plane_record(item)
        for item in (inspection.get("surfaces") or [])
        if isinstance(item, dict) and isinstance(item.get("normal"), list)
    ]
    datum_planes = [
        plane_record(item)
        for item in (inspection.get("datum_planes") or [])
        if isinstance(item, dict) and isinstance(item.get("normal"), list)
    ]

    def unit_axis(normal: list) -> str | None:
        if len(normal) != 3:
            return None
        for name, index in (("x", 0), ("y", 1), ("z", 2)):
            if abs(abs(normal[index]) - 1.0) < 1e-6 and all(
                abs(normal[other]) < 1e-6 for other in range(3) if other != index
            ):
                return name
        return None

    top = [
        item
        for item in surfaces
        if unit_axis(item["normal"]) == "z"
        and item["origin"]
        and abs(item["origin"][2] - 10.0) < 1e-6
    ]
    side_x0 = [
        item
        for item in surfaces
        if unit_axis(item["normal"]) == "x" and item["origin"] and abs(item["origin"][0]) < 1e-6
    ]
    datum_x = [item for item in datum_planes if unit_axis(item["normal"]) == "x"]
    datum_y = [item for item in datum_planes if unit_axis(item["normal"]) == "y"]
    datum_z = [item for item in datum_planes if unit_axis(item["normal"]) == "z"]
    return {
        "surfaces": surfaces,
        "datum_planes": datum_planes,
        "top_face_id": top[0]["id"] if top else None,
        "side_x0_face_id": side_x0[0]["id"] if side_x0 else None,
        "datum_x_id": datum_x[0]["id"] if datum_x else None,
        "datum_y_id": datum_y[0]["id"] if datum_y else None,
        "datum_z_id": datum_z[0]["id"] if datum_z else None,
    }


def hole_op(
    geometry: dict,
    label: str,
    *,
    face_key: str = "top_face_id",
    ref1_key: str = "datum_x_id",
    ref2_key: str = "datum_y_id",
    offset1: float = 25.0,
    offset2: float = 25.0,
    **option,
) -> dict:
    operation = fixture.BASE | {
        "label": label,
        "placement": {"kind": "surface", "id": geometry[face_key]},
        "reference1": {"kind": "datum_plane", "id": geometry[ref1_key]},
        "reference2": {"kind": "datum_plane", "id": geometry[ref2_key]},
        "offset1": offset1,
        "offset2": offset2,
    }
    operation.update(option)
    return operation


# Accepted on 2026-10-29; run only with --include-passed-cases.
CASES = {
    "cbore_flat_seat": {"counterbore": {"diameter": 10, "depth": 2}},
    "csink_90": {"countersink": {"diameter": 10, "angle": 90}},
}

# The 2026-10-29 rejection case, part of the same accepted set.
PASSED_REJECTION_CASE = "countersink_180_contract"

# Remaining contract scope: blind depth on the plate top face.
BLIND_CASES = {
    "blind_straight": {"depth": 7.0},
    "blind_counterbore": {"depth": 8.0, "counterbore": {"diameter": 10, "depth": 2}},
    "blind_countersink": {"depth": 8.0, "countersink": {"diameter": 10, "angle": 90}},
}

# The remainder cases that are not one of the BLIND_CASES: each has its own
# runner and its own expectations.
DIRECTION_CASE = "direction_side_normal"
FLIP_GUARD_CASE = "direction_flip_guard"
EDIT_CASE = "edit_dimension_values"

# The full default remainder set, in run order.
REMAINDER_CASES = (
    *BLIND_CASES,
    DIRECTION_CASE,
    FLIP_GUARD_CASE,
    EDIT_CASE,
)

# Model-name tags per case. The repository caps a name at 28 characters and
# the live harness appends "_" plus six hex digits, so a tag must stay at 21
# characters or less. The case names themselves are too long for that, which
# is why the tag is shortened instead of the case key.
MODEL_NAME_TAGS = {
    "blind_straight": "t12_blind_straight",
    "blind_counterbore": "t12_blind_cbore",
    "blind_countersink": "t12_blind_csink",
    "direction_side_normal": "t12_side_normal",
    "direction_flip_guard": "t12_flip_guard",
    "edit_dimension_values": "t12_edit_dims",
    "cbore_flat_seat": "t12_cbore_seat",
    "csink_90": "t12_csink_90",
    "countersink_180_contract": "t12_angle180",
}
MODEL_NAME_MAX_LENGTH = 28


def model_name_for(case_key: str) -> str:
    """A fresh model name for one case, inside the 28 character rule."""
    tag = MODEL_NAME_TAGS.get(case_key)
    if tag is None:
        raise ValueError(f"no model-name tag registered for case {case_key!r}")
    name = unique_name(tag)
    if len(name) > MODEL_NAME_MAX_LENGTH:
        raise ValueError(f"model name {name!r} exceeds the {MODEL_NAME_MAX_LENGTH} character rule")
    return name


def resolve_case_selection(requested: list[str] | None) -> list[str]:
    """Resolve a --case selection against the remainder cases.

    Only the six remainder cases can be selected: the three cases accepted on
    2026-10-29 are deliberately not selectable here, so a rerun can never be
    mistaken for the new acceptance set. An unknown or repeated name is
    refused before any connection.
    """
    if not requested:
        return list(REMAINDER_CASES)
    known = set(REMAINDER_CASES)
    unknown = [name for name in requested if name not in known]
    if unknown:
        raise ValueError(
            f"unknown case(s) {sorted(unknown)}; the remainder cases are "
            f"{sorted(known)} (the 2026-10-29 cases are not selectable here)"
        )
    repeated = sorted({name for name in requested if requested.count(name) > 1})
    if repeated:
        raise ValueError(f"repeated case(s) {repeated}")
    return [name for name in REMAINDER_CASES if name in set(requested)]


# Independent cylinder-face expectations (radius, axis, trimmed bbox).
#
# The native splits every revolved surface into two seam-split half faces,
# so these describe the union of the halves: the box that frames the hole.
#
# The plain branch (no counterbore, no countersink) is the legacy straight
# hole: its bore runs from the placement face down to a flat bottom exactly
# `depth` below it. The custom branch ends in a 118 degree drill point and
# is now dimensioned till that point (FEAT-035/T12), so its full-diameter
# bore stops one drill-point height above the tip vertex and the tip vertex
# sits exactly `depth` below the placement face.
BLIND_CYLINDERS = {
    "blind_straight": [
        {
            "radius": 3.0,
            "axis_normal": [0, 0, 1],
            "bbox_axis": 2,
            "bbox_range": fixture.oracle_bore_span(6.0, 7.0, {}),
            "bbox_center": {0: 25.0, 1: 25.0},
        },
    ],
    "blind_counterbore": [
        {
            "radius": 3.0,
            "axis_normal": [0, 0, 1],
            "bbox_axis": 2,
            "bbox_range": fixture.oracle_bore_span(6.0, 8.0, BLIND_CASES["blind_counterbore"]),
            "bbox_center": {0: 25.0, 1: 25.0},
        },
        {
            "radius": 5.0,
            "axis_normal": [0, 0, 1],
            "bbox_axis": 2,
            "bbox_range": (8.0, 10.0),
            "bbox_center": {0: 25.0, 1: 25.0},
        },
    ],
    "blind_countersink": [
        {
            "radius": 3.0,
            "axis_normal": [0, 0, 1],
            "bbox_axis": 2,
            "bbox_range": fixture.oracle_bore_span(6.0, 8.0, BLIND_CASES["blind_countersink"]),
            "bbox_center": {0: 25.0, 1: 25.0},
        },
    ],
}


def feature_counts(snapshot: dict) -> dict:
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    counts: dict[str, int] = {}
    for feature in inspection.get("features") or []:
        if isinstance(feature, dict):
            name = str(feature.get("type_name") or "other")
            counts[name] = counts.get(name, 0) + 1
    return counts


def reload_flag(terminal: dict | None) -> bool | None:
    """Reload evidence from the job result block, never from the terminal top."""
    result = (terminal or {}).get("result")
    block = result if isinstance(result, dict) else {}
    return block.get("saved_file_reloaded_and_verified")


def depth_probe(
    placement_value: float,
    axis_index: int,
    direction: int,
    expected_depth: float,
    diameter: float,
    semantics: str,
) -> dict:
    """The depth reading a case expects, for the measured depth comparison."""
    return {
        "placement_value": placement_value,
        "axis_index": axis_index,
        "direction": direction,
        "expected_depth": expected_depth,
        "tip_height": fixture.oracle_tip_height(diameter),
        "expected_semantics": semantics,
    }


def judge_geometry(
    entry: dict,
    terminal: dict,
    after: dict,
    *,
    label: str,
    expected_removed: float,
    expected_face_delta: int,
    expected_dims: dict,
    variants: dict,
    expected_variant: str,
    cylinder_expectations: list | None = None,
    probe: dict | None = None,
) -> tuple[dict, list]:
    """Independent checks: volume, face delta, dimension readback, cylinder face."""
    after_volume = LiveRunner.volume(after)
    base = entry.get("base_volume_mm3")
    removed = None if after_volume is None or base is None else base - after_volume
    counts = feature_counts(after)
    faces = fixture.face_count(after)
    dims = fixture.hole_dimensions(after, label)
    matched = None if removed is None else fixture.closest_variant(removed, variants, tol=1.0)
    result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
    operations = result.get("operations") or []
    problems: list[str] = []
    evidence = None
    semantics = None
    if probe is not None:
        evidence = fixture.hole_depth_evidence(
            after, probe["placement_value"], probe["axis_index"], probe["direction"]
        )
        semantics = fixture.depth_semantics(evidence, probe["expected_depth"], probe["tip_height"])
    fields = {
        "revision": after.get("revision"),
        "volume_mm3": after_volume,
        "removed_mm3": removed,
        "expected_removed_mm3": expected_removed,
        "abs_error_mm3": None if removed is None else abs(removed - expected_removed),
        "variant_values_mm3": variants,
        "matched_variant": matched,
        "feature_types": counts,
        "feature_delta": {
            key: counts.get(key, 0) - entry.get("base_features", {}).get(key, 0)
            for key in set(counts) | set(entry.get("base_features", {}))
        },
        "face_count": faces,
        "base_faces": entry.get("base_faces"),
        "expected_face_delta": expected_face_delta,
        "dimension_values": [dim.get("value") for dim in dims],
        "missing_dimensions": fixture.missing_dimension_values(dims, expected_dims),
        "operation_result": operations[0] if operations else None,
        "saved_file_reloaded_and_verified": reload_flag(terminal),
        "depth_evidence": evidence,
        "depth_semantics": semantics,
    }
    if fields["abs_error_mm3"] is None or fields["abs_error_mm3"] > 1.0:
        excess = None if removed is None else removed - expected_removed
        problems.append(
            f"removed {removed!r} outside 1 mm3 of the contract oracle {expected_removed!r}"
            f" (excess {excess!r} mm3)"
        )
    if matched != expected_variant:
        detail = "" if semantics is None else f" (measured depth semantics {semantics!r})"
        problems.append(
            f"removal matches {matched!r}, not the contract oracle {expected_variant!r}{detail}"
        )
    if probe is not None and semantics != probe["expected_semantics"]:
        problems.append(
            f"measured depth semantics {semantics!r}, not the contract {probe['expected_semantics']!r}"
        )
    if fields["feature_delta"].get("hole", 0) != 1:
        problems.append(f"hole feature delta={fields['feature_delta'].get('hole')!r}")
    if fields["base_faces"] is not None and faces is not None:
        if faces - fields["base_faces"] != expected_face_delta:
            problems.append(f"face delta={faces - fields['base_faces']} != {expected_face_delta}")
    if fields["missing_dimensions"]:
        problems.append(f"dimension readback missing {fields['missing_dimensions']}")
    if fields["saved_file_reloaded_and_verified"] is not True:
        problems.append("saved_file_reloaded_and_verified is not true")
    for expectation in cylinder_expectations or []:
        radius = expectation["radius"]
        groups = fixture.cylinder_groups(after, radius)
        if not groups:
            problems.append(f"no cylinder face of radius {radius}")
            continue
        for group in groups:
            normal = expectation.get("axis_normal")
            if normal is not None and not fixture.axis_is_parallel(group.get("axis"), normal):
                problems.append(
                    f"radius {radius} cylinder axis {group.get('axis')} not parallel to {normal}"
                )
            bbox = group.get("bbox")
            if not (isinstance(bbox, list) and len(bbox) == 2):
                problems.append(f"radius {radius} cylinder has no bbox")
                continue
            axis_index = expectation.get("bbox_axis")
            bbox_range = expectation.get("bbox_range")
            if axis_index is not None and bbox_range is not None:
                lo = bbox[0][axis_index] if isinstance(bbox[0], list) else None
                hi = bbox[1][axis_index] if isinstance(bbox[1], list) else None
                if (
                    lo is None
                    or hi is None
                    or abs(lo - bbox_range[0]) > 0.5
                    or abs(hi - bbox_range[1]) > 0.5
                ):
                    problems.append(
                        f"radius {radius} cylinder bbox axis{axis_index} "
                        f"[{lo},{hi}] != {tuple(bbox_range)}"
                    )
            for index, value in (expectation.get("bbox_center") or {}).items():
                if not (isinstance(bbox[0], list) and isinstance(bbox[1], list)):
                    continue
                mid = (bbox[0][index] + bbox[1][index]) / 2
                if abs(mid - value) > 0.5:
                    problems.append(f"radius {radius} cylinder center axis{index} {mid} != {value}")
    return fields, problems


async def make_plate(runner: LiveRunner, case_key: str) -> tuple | None:
    """Create the 50x50x10 plate; record a failed case and return None on failure."""
    name = model_name_for(case_key)
    made = await runner.submit(
        f"{case_key}:create",
        "creo_execute_plan",
        {"model_name": name, "model_type": "part", "operations": PLATE_PLAN},
    )
    base = await runner.wait_job(made["job_id"], budget=HANG_BUDGET_SECONDS)
    entry = {
        "case": case_key,
        "model_name": name,
        "model_id": made["model_id"],
        "base_job_id": made["job_id"],
        "base_status": base.get("status"),
    }
    if base.get("status") != "succeeded":
        entry.update(failure=failure_text(base), passed=False)
        runner.case(entry)
        return None
    snapshot = await runner.snapshot(made["model_id"])
    geometry = pick_geometry(snapshot)
    entry["geometry"] = {
        key: geometry[key]
        for key in ("top_face_id", "side_x0_face_id", "datum_x_id", "datum_y_id", "datum_z_id")
    }
    entry["base_volume_mm3"] = LiveRunner.volume(snapshot)
    entry["base_features"] = feature_counts(snapshot)
    entry["base_faces"] = fixture.face_count(snapshot)
    if entry["base_volume_mm3"] is None or abs(entry["base_volume_mm3"] - PLATE_VOLUME_MM3) > 0.5:
        entry["problems"] = [f"plate volume {entry['base_volume_mm3']!r} != {PLATE_VOLUME_MM3}"]
        entry["passed"] = False
        runner.case(entry)
        return None
    return entry, geometry, snapshot


async def case_blind(runner: LiveRunner, case_key: str, option: dict) -> None:
    plate = await make_plate(runner, case_key)
    if plate is None:
        return
    entry, geometry, snapshot = plate
    entry["option"] = option
    hole = await runner.submit(
        f"{case_key}:hole",
        "creo_execute_plan",
        {
            "model_id": entry["model_id"],
            "expected_revision": snapshot.get("revision"),
            "operations": [hole_op(geometry, "blind_hole", **option)],
        },
    )
    terminal = await runner.wait_job(hole["job_id"], budget=HANG_BUDGET_SECONDS)
    entry.update(hole_job_id=hole["job_id"], hole_status=terminal.get("status"))
    if terminal.get("status") != "succeeded":
        entry.update(failure=failure_text(terminal), passed=False)
        runner.case(entry)
        return
    after = await runner.snapshot(entry["model_id"])
    expected_dims = {"diameter": 6.0, "depth": option["depth"]}
    if "counterbore" in option:
        expected_dims["counterbore_diameter"] = float(option["counterbore"]["diameter"])
        expected_dims["counterbore_depth"] = float(option["counterbore"]["depth"])
    if "countersink" in option:
        expected_dims["countersink_diameter"] = float(option["countersink"]["diameter"])
        expected_dims["countersink_angle"] = float(option["countersink"]["angle"])
    fields, problems = judge_geometry(
        entry,
        terminal,
        after,
        label="blind_hole",
        expected_removed=fixture.oracle_contract(6.0, option["depth"], option, blind=True),
        expected_face_delta=fixture.oracle_faces_native(option, blind=True),
        expected_dims=expected_dims,
        variants=fixture.oracle_variants(6.0, option["depth"], option, blind=True),
        expected_variant=fixture.contract_variant_key(option, blind=True),
        cylinder_expectations=BLIND_CYLINDERS[case_key],
        probe=depth_probe(
            placement_value=PLATE_TOP_Z,
            axis_index=2,
            direction=-1,
            expected_depth=option["depth"],
            diameter=6.0,
            semantics=fixture.expected_depth_semantics(option, blind=True),
        ),
    )
    entry.update(fields)
    entry["problems"] = problems
    entry["passed"] = not problems
    runner.case(entry)


async def case_direction_side(runner: LiveRunner) -> None:
    """Hole on the x=0 face: the axis must follow the face normal, not -Z."""
    case_key = "direction_side_normal"
    plate = await make_plate(runner, case_key)
    if plate is None:
        return
    entry, geometry, snapshot = plate
    entry["option"] = {"depth": 7.0}
    required = ("side_x0_face_id", "datum_y_id", "datum_z_id")
    if not all(geometry.get(key) for key in required):
        entry["problems"] = [f"plate side geometry unresolved: {required}"]
        entry["passed"] = False
        runner.case(entry)
        return
    hole = await runner.submit(
        f"{case_key}:hole",
        "creo_execute_plan",
        {
            "model_id": entry["model_id"],
            "expected_revision": snapshot.get("revision"),
            "operations": [
                hole_op(
                    geometry,
                    "side_hole",
                    face_key="side_x0_face_id",
                    ref1_key="datum_y_id",
                    ref2_key="datum_z_id",
                    offset1=25.0,
                    offset2=5.0,
                    depth=7.0,
                )
            ],
        },
    )
    terminal = await runner.wait_job(hole["job_id"], budget=HANG_BUDGET_SECONDS)
    entry.update(hole_job_id=hole["job_id"], hole_status=terminal.get("status"))
    if terminal.get("status") != "succeeded":
        entry.update(failure=failure_text(terminal), passed=False)
        runner.case(entry)
        return
    after = await runner.snapshot(entry["model_id"])
    fields, problems = judge_geometry(
        entry,
        terminal,
        after,
        label="side_hole",
        expected_removed=fixture.oracle_contract(6.0, 7.0, {}, blind=True),
        expected_face_delta=fixture.oracle_faces_native({}, blind=True),
        expected_dims={"diameter": 6.0, "depth": 7.0},
        variants=fixture.oracle_variants(6.0, 7.0, {}, blind=True),
        expected_variant=fixture.contract_variant_key({}, blind=True),
        cylinder_expectations=[
            {
                "radius": 3.0,
                "axis_normal": [1, 0, 0],
                "bbox_axis": 0,
                "bbox_range": (0.0, 7.0),
                "bbox_center": {1: 25.0, 2: 5.0},
            },
        ],
        probe=depth_probe(
            placement_value=0.0,
            axis_index=0,
            direction=1,
            expected_depth=7.0,
            diameter=6.0,
            semantics=fixture.expected_depth_semantics({}, blind=True),
        ),
    )
    entry.update(fields)
    entry["problems"] = problems
    entry["passed"] = not problems
    runner.case(entry)


async def case_flip_guard(runner: LiveRunner) -> None:
    """flip=true drills out of the material: readable refusal, rollback, recovery."""
    case_key = "direction_flip_guard"
    plate = await make_plate(runner, case_key)
    if plate is None:
        return
    entry, geometry, snapshot = plate
    entry["option"] = {"depth": 7.0, "flip": True}
    problems: list[str] = []
    hole = await runner.submit(
        f"{case_key}:hole",
        "creo_execute_plan",
        {
            "model_id": entry["model_id"],
            "expected_revision": snapshot.get("revision"),
            "operations": [hole_op(geometry, "flipped_hole", depth=7.0, flip=True)],
        },
    )
    terminal = await runner.wait_job(hole["job_id"], budget=HANG_BUDGET_SECONDS)
    entry.update(hole_job_id=hole["job_id"], hole_status=terminal.get("status"))
    if terminal.get("status") != "failed":
        problems.append(
            f"expected the material guard to fail the job, got {terminal.get('status')!r}"
        )
    else:
        entry["failure"] = failure_text(terminal)
        result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
        entry["rollback_succeeded"] = result.get("rollback_succeeded")
        if result.get("rollback_succeeded") is not True:
            problems.append(f"rollback_succeeded={result.get('rollback_succeeded')!r}")
    after = await runner.snapshot(entry["model_id"])
    entry["post_volume_mm3"] = LiveRunner.volume(after)
    entry["post_faces"] = fixture.face_count(after)
    entry["post_features"] = feature_counts(after)
    if entry["post_volume_mm3"] is None or abs(entry["post_volume_mm3"] - PLATE_VOLUME_MM3) > 0.5:
        problems.append("model volume changed on the rejected flip hole")
    if entry["post_faces"] != entry["base_faces"]:
        problems.append("face count changed on the rejected flip hole")
    recovery = await runner.submit(
        f"{case_key}:recovery",
        "creo_execute_plan",
        {
            "model_id": entry["model_id"],
            "expected_revision": after.get("revision"),
            "operations": [
                hole_op(geometry, "recovery_hole", offset1=15.0, offset2=15.0, depth=7.0)
            ],
        },
    )
    terminal = await runner.wait_job(recovery["job_id"], budget=HANG_BUDGET_SECONDS)
    entry.update(recovery_job_id=recovery["job_id"], recovery_status=terminal.get("status"))
    if terminal.get("status") != "succeeded":
        problems.append(f"recovery hole status={terminal.get('status')!r}")
        entry["recovery_failure"] = failure_text(terminal)
    else:
        final = await runner.snapshot(entry["model_id"])
        fields, recovery_problems = judge_geometry(
            entry,
            terminal,
            final,
            label="recovery_hole",
            expected_removed=fixture.oracle_contract(6.0, 7.0, {}, blind=True),
            expected_face_delta=fixture.oracle_faces_native({}, blind=True),
            expected_dims={"diameter": 6.0, "depth": 7.0},
            variants=fixture.oracle_variants(6.0, 7.0, {}, blind=True),
            expected_variant=fixture.contract_variant_key({}, blind=True),
            cylinder_expectations=[],
            probe=depth_probe(
                placement_value=PLATE_TOP_Z,
                axis_index=2,
                direction=-1,
                expected_depth=7.0,
                diameter=6.0,
                semantics=fixture.expected_depth_semantics({}, blind=True),
            ),
        )
        entry["recovery"] = fields
        problems.extend(f"recovery: {item}" for item in recovery_problems)
    entry["problems"] = problems
    entry["passed"] = not problems
    runner.case(entry)


async def case_edit_dimensions(runner: LiveRunner) -> None:
    """Real dimension IDs from inspection; edit diameter and seat depth only."""
    case_key = "edit_dimension_values"
    plate = await make_plate(runner, case_key)
    if plate is None:
        return
    entry, geometry, snapshot = plate
    option = {"depth": 8.0, "counterbore": {"diameter": 10, "depth": 2}}
    entry["option"] = option
    problems: list[str] = []
    hole = await runner.submit(
        f"{case_key}:hole",
        "creo_execute_plan",
        {
            "model_id": entry["model_id"],
            "expected_revision": snapshot.get("revision"),
            "operations": [hole_op(geometry, "edit_hole", **option)],
        },
    )
    terminal = await runner.wait_job(hole["job_id"], budget=HANG_BUDGET_SECONDS)
    entry.update(hole_job_id=hole["job_id"], hole_status=terminal.get("status"))
    if terminal.get("status") != "succeeded":
        entry.update(failure=failure_text(terminal), passed=False)
        runner.case(entry)
        return
    after = await runner.snapshot(entry["model_id"])
    fields, create_problems = judge_geometry(
        entry,
        terminal,
        after,
        label="edit_hole",
        expected_removed=fixture.oracle_contract(6.0, 8.0, option, blind=True),
        expected_face_delta=fixture.oracle_faces_native(option, blind=True),
        expected_dims={
            "diameter": 6.0,
            "depth": 8.0,
            "counterbore_diameter": 10.0,
            "counterbore_depth": 2.0,
        },
        variants=fixture.oracle_variants(6.0, 8.0, option, blind=True),
        expected_variant=fixture.contract_variant_key(option, blind=True),
        cylinder_expectations=BLIND_CYLINDERS["blind_counterbore"],
        probe=depth_probe(
            placement_value=PLATE_TOP_Z,
            axis_index=2,
            direction=-1,
            expected_depth=8.0,
            diameter=6.0,
            semantics=fixture.expected_depth_semantics(option, blind=True),
        ),
    )
    entry["create_stage"] = fields
    problems.extend(f"create: {item}" for item in create_problems)

    def pick_dim(value: float):
        for dim in fixture.hole_dimensions(after, "edit_hole"):
            if isinstance(dim.get("value"), (int, float)) and dim.get("id") is not None:
                if abs(float(dim["value"]) - value) <= 1e-3:
                    return dim["id"]
        return None

    diameter_id, cbore_depth_id = pick_dim(6.0), pick_dim(2.0)
    entry["dimension_ids"] = {"diameter": diameter_id, "counterbore_depth": cbore_depth_id}
    if diameter_id is None or cbore_depth_id is None:
        problems.append("could not resolve real dimension IDs for diameter/counterbore depth")
        entry["problems"] = problems
        entry["passed"] = False
        runner.case(entry)
        return
    edit = await runner.submit(
        f"{case_key}:edit",
        "creo_set_dimensions",
        {
            "model_id": entry["model_id"],
            "expected_revision": after.get("revision"),
            "values": [
                {"id": diameter_id, "value": 7.0},
                {"id": cbore_depth_id, "value": 3.0},
            ],
        },
    )
    terminal = await runner.wait_job(edit["job_id"], budget=HANG_BUDGET_SECONDS)
    entry.update(edit_job_id=edit["job_id"], edit_status=terminal.get("status"))
    if terminal.get("status") != "succeeded":
        problems.append(f"edit job status={terminal.get('status')!r}")
        entry["edit_failure"] = failure_text(terminal)
        entry["problems"] = problems
        entry["passed"] = False
        runner.case(entry)
        return
    final = await runner.snapshot(entry["model_id"])
    edited = {"counterbore": {"diameter": 10, "depth": 3}}
    fields, edit_problems = judge_geometry(
        entry,
        terminal,
        final,
        label="edit_hole",
        expected_removed=fixture.oracle_contract(7.0, 8.0, edited, blind=True),
        expected_face_delta=fixture.oracle_faces_native(edited, blind=True),
        expected_dims={
            "diameter": 7.0,
            "depth": 8.0,
            "counterbore_diameter": 10.0,
            "counterbore_depth": 3.0,
        },
        variants=fixture.oracle_variants(7.0, 8.0, edited, blind=True),
        expected_variant=fixture.contract_variant_key(edited, blind=True),
        cylinder_expectations=[
            {
                "radius": 3.5,
                "axis_normal": [0, 0, 1],
                "bbox_axis": 2,
                "bbox_range": fixture.oracle_bore_span(7.0, 8.0, edited),
                "bbox_center": {0: 25.0, 1: 25.0},
            },
            {
                "radius": 5.0,
                "axis_normal": [0, 0, 1],
                "bbox_axis": 2,
                "bbox_range": (7.0, 10.0),
                "bbox_center": {0: 25.0, 1: 25.0},
            },
        ],
        probe=depth_probe(
            placement_value=PLATE_TOP_Z,
            axis_index=2,
            direction=-1,
            expected_depth=8.0,
            diameter=7.0,
            semantics=fixture.expected_depth_semantics(edited, blind=True),
        ),
    )
    entry["edit_stage"] = fields
    problems.extend(f"edit: {item}" for item in edit_problems)
    if fields.get("revision") == entry["create_stage"].get("revision"):
        problems.append("edit did not change the model revision")
    entry["problems"] = problems
    entry["passed"] = not problems
    runner.case(entry)


async def run_passed_cases(runner: LiveRunner) -> None:
    """The three cases accepted on 2026-10-29; only with --include-passed-cases."""
    for case, option in CASES.items():
        name = model_name_for(case)
        made = await runner.submit(
            f"{case}:create",
            "creo_execute_plan",
            {"model_name": name, "model_type": "part", "operations": PLATE_PLAN},
        )
        base = await runner.wait_job(made["job_id"], budget=HANG_BUDGET_SECONDS)
        entry = {
            "case": case,
            "option": option,
            "model_name": name,
            "model_id": made["model_id"],
            "base_job_id": made["job_id"],
            "base_status": base.get("status"),
        }
        if base.get("status") != "succeeded":
            entry.update(failure=failure_text(base), passed=False)
            runner.case(entry)
            continue
        before = await runner.snapshot(made["model_id"])
        geometry = pick_geometry(before)
        entry["geometry"] = {
            key: geometry[key] for key in ("top_face_id", "datum_x_id", "datum_y_id")
        }
        entry["base_volume_mm3"] = LiveRunner.volume(before)
        entry["base_features"] = feature_counts(before)
        if not all(geometry[key] for key in ("top_face_id", "datum_x_id", "datum_y_id")):
            entry["problems"] = ["plate geometry could not be resolved from inspection"]
            entry["passed"] = False
            runner.case(entry)
            continue
        hole = await runner.submit(
            f"{case}:hole",
            "creo_execute_plan",
            {
                "model_id": made["model_id"],
                "expected_revision": before.get("revision"),
                "operations": [hole_op(geometry, "seated_hole", **option)],
            },
        )
        terminal = await runner.wait_job(hole["job_id"], budget=HANG_BUDGET_SECONDS)
        entry.update(hole_job_id=hole["job_id"], hole_status=terminal.get("status"))
        if terminal.get("status") != "succeeded":
            entry.update(failure=failure_text(terminal), passed=False)
            runner.case(entry)
            continue
        after = await runner.snapshot(made["model_id"])
        after_volume = LiveRunner.volume(after)
        removed = (
            None
            if after_volume is None or entry["base_volume_mm3"] is None
            else entry["base_volume_mm3"] - after_volume
        )
        expected_removed = fixture.oracle_removed(6.0, 10.0, option)
        counts = feature_counts(after)
        result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
        operations = result.get("operations") or []
        entry.update(
            revision=after.get("revision"),
            volume_mm3=after_volume,
            removed_mm3=removed,
            expected_removed_mm3=expected_removed,
            abs_error_mm3=None if removed is None else abs(removed - expected_removed),
            volume_abs_error_mm3=None
            if after_volume is None
            else abs(after_volume - (PLATE_VOLUME_MM3 - expected_removed)),
            feature_types=counts,
            feature_delta={
                key: counts.get(key, 0) - entry["base_features"].get(key, 0)
                for key in set(counts) | set(entry["base_features"])
            },
            operation_result=operations[0] if operations else None,
            saved_file_reloaded_and_verified=result.get("saved_file_reloaded_and_verified"),
        )
        entry["problems"] = []
        if entry["volume_abs_error_mm3"] is None or entry["volume_abs_error_mm3"] > 1.0:
            entry["problems"].append("volume outside 1 mm3 of the flat-bottom oracle")
        if entry["feature_delta"].get("hole", 0) != 1:
            entry["problems"].append(f"hole feature delta={entry['feature_delta'].get('hole')!r}")
        entry["passed"] = not entry["problems"]
        runner.case(entry)

    reject = await runner.probe(
        "creo_execute_plan",
        {
            "model_name": model_name_for(PASSED_REJECTION_CASE),
            "model_type": "part",
            "operations": [
                {
                    **fixture.BASE,
                    "label": "sink_180",
                    "countersink": {"diameter": 10, "angle": 180},
                }
            ],
        },
    )
    body = reject["structured"] or {}
    runner.case(
        {
            "case": "countersink_180_contract",
            "rejected": bool(reject["is_error"]),
            "job_id": body.get("job_id"),
            "message": str(body.get("error") or body.get("message") or reject["text"])[:600],
            "passed": bool(reject["is_error"] and not body.get("job_id")),
        }
    )


async def run_live(
    output: Path | None, include_passed: bool, selection: list[str] | None = None
) -> int:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    run_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    target = output or ROOT / "build" / "native_countersink" / run_id / "report.json"
    if target.exists():
        raise SystemExit(f"refusing to overwrite {target}")
    cases = resolve_case_selection(selection)
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=180) as client:
        runner = LiveRunner(
            client,
            target,
            "FEAT-035 / DEV-051 T12",
            "hole-type remainder: blind depth, direction along the placement normal, "
            "supported dimension edits, failure rollback and save/reload consistency; "
            "the three passed 2026-10-29 cases run only with --include-passed-cases",
            run_id,
        )
        try:
            await runner.start()
            runner.report["hang_budget_seconds"] = HANG_BUDGET_SECONDS
            runner.report["plate_volume_mm3"] = PLATE_VOLUME_MM3
            runner.report["selected_cases"] = cases
            runner.report["remainder_cases"] = list(REMAINDER_CASES)
            if include_passed:
                await run_passed_cases(runner)
            for case_key in cases:
                if case_key in BLIND_CASES:
                    await case_blind(runner, case_key, BLIND_CASES[case_key])
                elif case_key == DIRECTION_CASE:
                    await case_direction_side(runner)
                elif case_key == FLIP_GUARD_CASE:
                    await case_flip_guard(runner)
                elif case_key == EDIT_CASE:
                    await case_edit_dimensions(runner)
        except BaseException as error:
            runner.report["stopped"] = f"{type(error).__name__}: {error}"
            runner.finish()
            raise
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    rows = [
        {key: case.get(key) for key in ("case", "hole_status", "removed_mm3", "problems", "passed")}
        for case in runner.report["cases"]
    ]
    print(json.dumps({"passed": runner.report["passed"], "cases": rows}, ensure_ascii=False))
    return 0 if runner.report["passed"] else 1


def provenance() -> dict:
    from creo_mechdog.source_provenance import local_provenance

    evidence = local_provenance(
        ROOT,
        ("tests/unit/test_native_countersink.py", "tools/test_native_countersink.py"),
    )
    return {
        "commit": evidence["commit"],
        "branch": evidence["branch"],
        "dirty": evidence["dirty"],
        "git_status": evidence["git_status"],
        **{
            key: evidence[key]
            for key in ("source_scope", "source_status", "source_errors", "source_file_count")
        },
        "source_fingerprint": evidence["source_fingerprint"],
        "environment": evidence["environment"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument(
        "--include-passed-cases",
        action="store_true",
        help="also rerun the three cases accepted on 2026-10-29 (off by default)",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        default=None,
        metavar="NAME",
        help=(
            "run only these remainder cases (repeatable); the 2026-10-29 cases are not "
            "selectable here. Unknown or repeated names are refused before any connection."
        ),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        selection = resolve_case_selection(args.cases)
    except ValueError as error:
        print(f"REFUSED BEFORE CONNECTION: {error}", file=sys.stderr)
        return 2
    if args.live:
        if not args.confirm_session_usable:
            print("live runs require --confirm-session-usable", file=sys.stderr)
            return 2
        return asyncio.run(run_live(args.output, args.include_passed_cases, selection))
    suite = unittest.defaultTestLoader.loadTestsFromModule(fixture)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    report = {
        "task": "DEV-051 T12 / FEAT-035",
        "mode": "offline",
        "native_acceptance": "not_run",
        "unit": {
            "run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
        },
        "remainder_cases": list(REMAINDER_CASES),
        "selected_cases": selection,
        "accepted_2026_10_29_cases": [*CASES, PASSED_REJECTION_CASE],
        "case_selection_rule": (
            "the default run covers exactly the six remainder cases; --case narrows that "
            "set; the three cases accepted on 2026-10-29 are only reachable through "
            "--include-passed-cases and are never part of the remainder acceptance set"
        ),
        "oracle_mm3": {
            "counterbore_through": fixture.oracle_removed(
                6, 10, {"counterbore": {"diameter": 10, "depth": 2}}
            ),
            "countersink_through": fixture.oracle_removed(
                6, 10, {"countersink": {"diameter": 10, "angle": 90}}
            ),
            "blind_straight": fixture.oracle_contract(6, 7, {}, blind=True),
            "blind_counterbore": fixture.oracle_contract(
                6, 8, {"counterbore": {"diameter": 10, "depth": 2}}, blind=True
            ),
            "blind_countersink": fixture.oracle_contract(
                6, 8, {"countersink": {"diameter": 10, "angle": 90}}, blind=True
            ),
            "direction_side_normal": fixture.oracle_contract(6, 7, {}, blind=True),
            "edit_after_diameter7_depth3": fixture.oracle_contract(
                7, 8, {"counterbore": {"diameter": 10, "depth": 3}}, blind=True
            ),
            "assumption": "the blind custom hole is dimensioned till its drill tip "
            "(PRO_HLE_DEP_TIP_DIM_SCHEME): the tip vertex sits `depth` below the "
            "placement face, so the removal is the flat-bottom reference minus two "
            "thirds of the 118 degree cone body; the plain straight hole keeps its "
            "flat bottom and its overall depth; the till-shoulder and "
            "seat-measured drill depth variants are reported for diagnosis and "
            "never pass a case",
        },
        "faces_added_over_plate": {
            "contract": {
                key: fixture.oracle_faces(option, blind=True) for key, option in BLIND_CASES.items()
            },
            "native": {
                key: fixture.oracle_faces_native(option, blind=True)
                for key, option in BLIND_CASES.items()
            },
            "note": "the native splits every revolved surface into two seam-split half "
            "faces, and the blind custom hole ends in a 118 degree drill point (two "
            "half-cone faces); since the fix dimensions that hole till its tip, the "
            "contract shape and the native shape now carry the same point and agree",
        },
        "depth_semantics": {
            "plain_branch": "depth is the overall depth from the placement face and the "
            "hole ends in a flat bottom (measured removal matched the flat oracle to "
            "2.8e-12 mm3)",
            "custom_branch": "depth is the overall depth from the placement face down to "
            "the drill tip vertex; the full-diameter bore stops one tip height "
            "(1.802582 mm at diameter 6) higher, so the removed volume is the "
            "flat-bottom reference minus two thirds of the cone body",
            "measured_removals_before_the_fix_mm3": {
                "blind_straight": 197.92033717615413,
                "blind_counterbore": 343.7145697324486,
                "blind_countersink": 289.26029707022826,
            },
            "note": "the two custom removals above were measured on 2026-10-30 with "
            "the till-shoulder scheme; after the fix they must come back as the "
            "contract_tip_overall values in oracle_mm3",
            "drill_point_tip_height_mm": fixture.oracle_tip_height(6.0),
            "drill_point_cone_mm3": fixture.oracle_tip_extra(6.0),
            "drill_point_cone_body_mm3": fixture.oracle_tip_body(6.0),
        },
        "pending_live": [
            "blind straight / blind counterbore / blind countersink: volume, face delta, "
            "dimension readback and cylinder bbox/axis",
            "direction_side_normal: cylinder axis parallel to the placement normal",
            "direction_flip_guard: readable guard refusal, rollback_succeeded, unchanged "
            "model and a legal recovery hole",
            "edit_dimension_values: real dimension ID edits of diameter and counterbore depth, "
            "post-edit oracle and revision change",
            "save/reload parameter and geometry consistency is checked in every case via "
            "saved_file_reloaded_and_verified and the reloaded snapshot",
        ],
        "out_of_scope": [
            "the three 2026-10-29 cases are not rerun by default",
            "hole type / placement / flip redefinition edits (only dimension value edits "
            "on the created hole are claimed)",
            "thread and standard hole series, exit countersink, dual counterbore, "
            "non-linear placements, Creo 9/10",
        ],
        "sdk": "Creo 12.4 ProHole.h custom-hole CBORE/CSINK/DRILLDEPTH/DEPTH_DIM_TYPE; "
        "the blind custom branch writes PRO_HLE_DEP_TIP_DIM_SCHEME (Dimension till tip) "
        "per native/generic.cpp, so its depth is the overall depth to the drill tip "
        "vertex; the plain straight branch keeps its own element tree and its "
        "flat-bottomed overall depth",
        "provenance": provenance(),
    }
    run_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    output = args.output or ROOT / "build" / "native_countersink" / run_id / "report.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    output.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    output.with_suffix(".sha256").write_text(digest + "  report.json\n", encoding="ascii")
    print(json.dumps({"report": str(output), "sha256": digest, "passed": result.wasSuccessful()}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
