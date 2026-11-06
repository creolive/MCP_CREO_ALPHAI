"""FEAT-014 R09: native_planar four-wall route and miter calibration driver.

The 2026-11-06 four-wall evidence used wall_sketch + sheetmetal_wall. The
original feedback D instead built the plate with native_planar and resize, so
that combination is verified here separately:

* create the native planar wall 180x230x1, resize it to 185x232x1, then build
  four flanges (h80 / R2.54 / Y0.5) one job each, always from the current top
  edge; the third and fourth walls carry the explicit miter request;
* measure the real corner effect instead of trusting the element echo: each
  wall's horizontal top face is read from inspection surfaces (bbox), its run
  is compared with the plate span and the shortfall per end is recorded;
* the width/offset and thickness/radius matrix re-runs the same box with a
  different miter gap and a different bend radius;
* the follow-up case unfolds all bends, refolds them and checks that a refused
  or failed modification keeps the revision and the saved geometry.

Default is strictly offline: no MCP client, no Toolkit connection, no job.
``--live --confirm-session-usable`` starts the formal live run on the single
shared dev service; the report is written under
build/sheetmetal_planar_box/<run_id>/ and never overwritten.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
import uuid
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))
if str(_SOURCE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT / "src"))

from creo_mechdog.schema import validate_operations  # noqa: E402
from tests.unit import test_sheetmetal_flange as fx  # noqa: E402
from tools.sheetmetal_live import (  # noqa: E402
    LiveRunner,
    LiveStop,
    failure_text,
    require_manual_start,
    unique_name,
)
from tools.test_sheetmetal_box_live import local_provenance, wall_record  # noqa: E402

ROOT = _SOURCE_ROOT

PLANAR_LENGTH_MM = 180.0
PLANAR_WIDTH_MM = 230.0
RESIZED_LENGTH_MM = 185.0
RESIZED_WIDTH_MM = 232.0
THICKNESS_MM = fx.PLATE_THICKNESS_MM
HEIGHT_MM = fx.FLANGE_HEIGHT_MM
RADIUS_MM = fx.FLANGE_RADIUS_MM
Y_FACTOR = fx.FLANGE_Y_FACTOR
ANGLE_DEG = fx.FLANGE_ANGLE_DEG
BUDGET_SECONDS = 420.0
MITER_GAP_MM = THICKNESS_MM
MITER = {"width": MITER_GAP_MM, "offset": MITER_GAP_MM}

#: (+x, -x) attach to free edges; (-y, +y) abut the existing bends, so only
#: those carry the explicit miter request.
WALL_SEQUENCE = (
    ("+x", "f_px", False),
    ("-x", "f_nx", False),
    ("-y", "f_ny", True),
    ("+y", "f_py", True),
)

#: A small independent matrix over the miter gap and the bend radius; the
#: baseline box above is the third combination (gap 1.0 / radius 2.54).
MATRIX = (
    {"name": "gap_2_r2_54", "miter": {"width": 2.0, "offset": 2.0}, "radius": 2.54},
    {"name": "gap_1_r1_5", "miter": {"width": 1.0, "offset": 1.0}, "radius": 1.5},
)

SIDE_RUN_AXIS = {"+x": 1, "-x": 1, "-y": 0, "+y": 0}
SIDE_PLANE_AXIS = {"+x": 0, "-x": 0, "-y": 1, "+y": 1}


# --- plans -----------------------------------------------------------------


def plate_operations() -> tuple[list[dict], list[dict]]:
    """The create plan and the in-place resize plan, validated separately."""
    create = [
        {
            "op": "sheetmetal_planar_wall",
            "label": "wall_pw",
            "plane": "XY",
            "length": PLANAR_LENGTH_MM,
            "width": PLANAR_WIDTH_MM,
            "thickness": THICKNESS_MM,
            "direction": "positive",
        }
    ]
    resize = [
        {
            "op": "resize_sheetmetal_planar_wall",
            "feature": "wall_pw",
            "length": RESIZED_LENGTH_MM,
            "width": RESIZED_WIDTH_MM,
        }
    ]
    return create, resize


def flange_operation(reference: dict, label: str, *, radius: float, miter: dict | None) -> dict:
    operation = {
        "op": "sheetmetal_flange",
        "label": label,
        "edge": dict(reference["edge"]),
        "height": HEIGHT_MM,
        "angle": ANGLE_DEG,
        "radius": radius,
        "flip": False,
        "y_factor": Y_FACTOR,
    }
    if miter is not None:
        operation["miter_cuts"] = dict(miter)
    return operation


# --- geometric calibration -------------------------------------------------


def top_horizontal_faces(inspection: dict, top_z: float, tolerance: float = 0.2) -> list[dict]:
    """Planar faces whose two bbox planes sit on the measured top of the box."""
    faces = []
    for surface in inspection.get("surfaces") or []:
        normal = surface.get("normal")
        bbox = surface.get("bbox")
        if not normal or not isinstance(bbox, list) or len(bbox) != 2:
            continue
        if abs(abs(float(normal[2])) - 1.0) > 1e-6:
            continue
        low, high = bbox[0], bbox[1]
        if abs(float(low[2]) - top_z) > tolerance or abs(float(high[2]) - top_z) > tolerance:
            continue
        faces.append(
            {
                "surface_id": surface.get("id"),
                "bbox_mm": [
                    [float(value) for value in low],
                    [float(value) for value in high],
                ],
            }
        )
    return faces


def wall_top_faces(
    faces: list[dict], plate_bounds: tuple, side: str, edge_span_mm: float | None
) -> dict | None:
    """Union of the wall's own top faces versus the edge it was attached to.

    The top face of a bent wall is split into several patches by the bend
    zones, so the union extent is the honest reading. It is compared with the
    measured attachment edge, never with the plate span: the plate span minus
    the edge span is the ordinary bend consumption, not a miter cut.
    """
    plane_axis = SIDE_PLANE_AXIS[side]
    run_axis = SIDE_RUN_AXIS[side]
    plane = plate_bounds[1][plane_axis] if side[0] == "+" else plate_bounds[0][plane_axis]
    candidates = []
    for face in faces:
        low, high = face["bbox_mm"]
        centre = (low[plane_axis] + high[plane_axis]) / 2.0
        if abs(centre - plane) > 2.0 * THICKNESS_MM:
            continue
        candidates.append(face)
    if not candidates:
        return None
    run_low = min(face["bbox_mm"][0][run_axis] for face in candidates)
    run_high = max(face["bbox_mm"][1][run_axis] for face in candidates)
    run_mm = run_high - run_low
    relation = "unmeasured"
    if edge_span_mm is not None:
        difference = run_mm - float(edge_span_mm)
        if abs(difference) <= 0.01:
            relation = "matches"
        elif difference > 0:
            relation = "exceeds"
        else:
            relation = "short"
    return {
        "side": side,
        "face_count": len(candidates),
        "surface_ids": [face["surface_id"] for face in candidates],
        "run_low_mm": round(run_low, 6),
        "run_high_mm": round(run_high, 6),
        "run_mm": round(run_mm, 6),
        "edge_span_mm": edge_span_mm,
        "relation": relation,
        "covers_attachment_edge": relation == "matches",
    }


def corner_patches(faces: list[dict], plate_bounds: tuple, margin: float = 6.0) -> dict:
    """Horizontal top faces inside each top corner square: the notch bbox.

    A miter cut changes the material at a corner, so the corner square is
    described by every top face overlapping it. The bbox of those patches is
    the only geometric claim recorded here; the face shape is not inferred
    from a bbox.
    """
    low, high = plate_bounds
    corners = {}
    for x_sign, y_sign, key in (
        (1, 1, "+x+y"),
        (1, -1, "+x-y"),
        (-1, 1, "-x+y"),
        (-1, -1, "-x-y"),
    ):
        x_edge = high[0] if x_sign > 0 else low[0]
        y_edge = high[1] if y_sign > 0 else low[1]
        x_band = (x_edge - margin, x_edge + 1.0) if x_sign > 0 else (x_edge - 1.0, x_edge + margin)
        y_band = (y_edge - margin, y_edge + 1.0) if y_sign > 0 else (y_edge - 1.0, y_edge + margin)
        picks = []
        for face in faces:
            face_low, face_high = face["bbox_mm"]
            if face_high[0] < x_band[0] or face_low[0] > x_band[1]:
                continue
            if face_high[1] < y_band[0] or face_low[1] > y_band[1]:
                continue
            picks.append(face)
        patches = [
            {
                "surface_id": face["surface_id"],
                "bbox_mm": face["bbox_mm"],
            }
            for face in picks
        ]
        corners[key] = {
            "corner_square_mm": [margin, margin],
            "patch_count": len(patches),
            "patches": patches,
        }
    return corners


def volume_cross_check(
    plate_volume_mm3: float | None, wall_records: list[dict], measured_volume_mm3: float | None
) -> dict:
    """Uncut expectation from independent increments; a cross-check only.

    The increments are independent wall volumes, so the sum double counts the
    corner material two walls share. The delta is therefore reported as a
    bounded observation and never alone as the cut volume.
    """
    from tests.unit import test_sheetmetal_relief as relief

    if plate_volume_mm3 is None or measured_volume_mm3 is None:
        return {"status": "unavailable", "reason": "plate or box volume missing"}
    increments = []
    for record in wall_records:
        span = record.get("edge_span_mm")
        if span is None:
            return {"status": "unavailable", "reason": "a wall has no measured span"}
        increments.append(relief.bent_wall_increment_mm3(float(span)))
    expected = plate_volume_mm3 + sum(increments)
    return {
        "status": "measured",
        "uncut_expectation_mm3": round(expected, 6),
        "measured_volume_mm3": round(measured_volume_mm3, 6),
        "measured_minus_expectation_mm3": round(measured_volume_mm3 - expected, 6),
        "increments_mm3": [round(value, 6) for value in increments],
        "statement": (
            "independent wall increments double count shared corner material; the delta is "
            "a bounded cross-check, not the miter cut volume"
        ),
    }


def calibration_verdict(wall_records: list[dict], corners: dict) -> dict:
    """Per-wall top-face coverage plus the four corner patch boxes.

    Nothing here is derived from the miter request echo: the wall verdict only
    compares the measured top faces with the measured attachment edge, and the
    corner verdict only lists the faces inside each corner square.
    """
    walls = {}
    for record in wall_records:
        top = record.get("top_faces")
        if top is None:
            walls[record["label"]] = {
                "verdict": "unmeasured",
                "miter_cuts": record.get("miter_cuts"),
            }
            continue
        walls[record["label"]] = {
            "verdict": {
                "matches": "top_run_matches_attachment_edge",
                "exceeds": "top_run_exceeds_attachment_edge",
                "short": "top_run_short_of_attachment_edge",
            }.get(top["relation"], "unmeasured"),
            "run_mm": top["run_mm"],
            "edge_span_mm": top["edge_span_mm"],
            "face_count": top["face_count"],
            "miter_cuts": record.get("miter_cuts"),
        }
    return {
        "walls": walls,
        "corners": corners,
        "measured_walls": sum(1 for entry in walls.values() if entry["verdict"] != "unmeasured"),
        "statement": (
            "top-face union is compared with the attachment edge, not the plate span; an "
            "exceeding run means the miter end reaches past the shortened attachment edge, "
            "and the corner boxes list the faces that actually exist in each corner square"
        ),
    }


def matrix_summary(cases: list[dict]) -> dict:
    """Differential volume across identical boxes that differ only in gap/radius.

    The same plate and the same four walls are rebuilt for every combination,
    so the volume difference against the baseline box isolates the effect of
    the miter gap or of the bend radius. A per-corner figure is the difference
    divided by four corners and is labeled as such.
    """
    baseline = next((case for case in cases if case.get("group") == "planar_box"), None)
    if baseline is None or baseline.get("box_volume_mm3") is None:
        return {"status": "unavailable", "reason": "no baseline box volume"}
    base_volume = float(baseline["box_volume_mm3"])
    rows = []
    for case in cases:
        group = case.get("group") or ""
        if not group.startswith("matrix_") or case.get("box_volume_mm3") is None:
            continue
        delta = float(case["box_volume_mm3"]) - base_volume
        rows.append(
            {
                "group": group,
                "radius": case.get("radius"),
                "miter_cuts": case.get("miter_cuts"),
                "box_volume_mm3": round(float(case["box_volume_mm3"]), 6),
                "volume_delta_mm3": round(delta, 6),
                "delta_per_corner_mm3": round(delta / 4.0, 6),
                "four_walls_complete": case.get("four_walls_complete"),
            }
        )
    return {
        "status": "measured" if rows else "unavailable",
        "baseline": {
            "miter_cuts": baseline.get("miter_cuts"),
            "radius": baseline.get("radius"),
            "box_volume_mm3": round(base_volume, 6),
        },
        "rows": rows,
        "statement": (
            "volume difference between identical boxes isolates the gap or radius effect; "
            "delta_per_corner is that difference divided by four corners, not a measured "
            "single-corner volume"
        ),
    }


# --- offline ---------------------------------------------------------------


def offline_checks() -> dict:
    create, resize = plate_operations()
    validated_create = validate_operations(create)
    validated_resize = validate_operations(resize)
    reference = fx.select_wall_edge(fx.box_inspection(), fx.PLATE_BOUNDS, "+x", face="top")
    validated_walls = {}
    for side, label, use_miter in WALL_SEQUENCE:
        operation = flange_operation(
            reference, label, radius=RADIUS_MM, miter=MITER if use_miter else None
        )
        validated_walls[label] = validate_operations([operation])[0]

    # A synthetic box: the +x top face is split into two patches whose union
    # covers the 232 mm attachment edge, while the -x face stops 10 mm short.
    faces = [
        {"surface_id": 1, "bbox_mm": [[92.5, -116.0, 81.0], [93.5, 0.0, 81.0]]},
        {"surface_id": 2, "bbox_mm": [[92.5, 0.0, 81.0], [93.5, 116.0, 81.0]]},
        {"surface_id": 3, "bbox_mm": [[-93.5, -111.0, 81.0], [-92.5, 111.0, 81.0]]},
    ]
    plate_bounds = ((-92.5, -116.0, 0.0), (92.5, 116.0, 1.0))
    synthetic = {
        "split_but_full": wall_top_faces(faces, plate_bounds, "+x", 232.0),
        "short": wall_top_faces(faces, plate_bounds, "-x", 232.0),
        "missing": wall_top_faces(
            top_horizontal_faces({"surfaces": []}, 81.0), plate_bounds, "+x", 232.0
        ),
    }
    assert synthetic["split_but_full"]["relation"] == "matches", synthetic
    assert synthetic["split_but_full"]["face_count"] == 2, synthetic
    assert synthetic["split_but_full"]["run_mm"] == 232.0, synthetic
    assert synthetic["short"]["relation"] == "short", synthetic
    assert synthetic["missing"] is None

    corners = corner_patches(faces, plate_bounds)
    assert len(corners) == 4 and corners["+x+y"]["patch_count"] == 1, corners

    sample = [
        {
            "label": "f_px",
            "edge_span_mm": 232.0,
            "miter_cuts": None,
            "top_faces": synthetic["split_but_full"],
        },
        {
            "label": "f_ny",
            "edge_span_mm": 232.0,
            "miter_cuts": MITER,
            "top_faces": synthetic["short"],
        },
    ]
    verdict = calibration_verdict(sample, corners)
    assert verdict["walls"]["f_px"]["verdict"] == "top_run_matches_attachment_edge", verdict
    assert verdict["walls"]["f_ny"]["verdict"] == "top_run_short_of_attachment_edge", verdict
    cross = volume_cross_check(42_920.0, sample, 100_000.0)
    assert cross["status"] == "measured", cross
    matrix = matrix_summary(
        [
            {"group": "planar_box", "box_volume_mm3": 100.0, "miter_cuts": MITER, "radius": 2.54},
            {
                "group": "matrix_gap_2",
                "box_volume_mm3": 99.0,
                "miter_cuts": {"width": 2.0, "offset": 2.0},
                "radius": 2.54,
            },
        ]
    )
    assert matrix["rows"][0]["volume_delta_mm3"] == -1.0, matrix

    return {
        "create_plan_validated": validated_create[0]["op"],
        "resize_plan_validated": validated_resize[0]["op"],
        "walls": {
            label: {
                "miter_cuts": value.get("miter_cuts"),
                "height": value["height"],
                "radius": value["radius"],
            }
            for label, value in validated_walls.items()
        },
        "miter_only_on_bending_ends": [label for _, label, use_miter in WALL_SEQUENCE if use_miter]
        == ["f_ny", "f_py"],
        "calibration_helper": {
            "split_but_full": synthetic["split_but_full"],
            "short": synthetic["short"],
            "missing_face_is_null": synthetic["missing"] is None,
            "corner_patch_keys": sorted(corners),
        },
        "matrix": [entry["name"] for entry in MATRIX],
        "followup_available": {
            "unbend_refold": True,
            "height_edit": False,
            "flange_delete": False,
            "note": (
                "creo_sheetmetal_unbend/bend_back exist; there is no flange height-edit or "
                "flange-delete operation, so those two plan lines stay unsupported instead "
                "of being simulated"
            ),
        },
    }


# --- live ------------------------------------------------------------------


def operation_detail(job: dict, op: str) -> dict:
    for item in (job.get("result") or {}).get("operations") or []:
        if isinstance(item, dict) and item.get("op") == op:
            return item
    return {}


def _bbox(snapshot: dict) -> list | None:
    from tools.test_sheetmetal_box_live import bbox_of

    return bbox_of(snapshot)


async def create_plate(runner: LiveRunner, case_name: str) -> tuple[dict, dict | None]:
    """Empty native sheetmetal model, planar wall 180x230x1, resize to 185x232x1."""
    from creo_mechdog import native_planar_wall as pwall

    model_name = unique_name(f"pw_{case_name[:18]}")
    created = await runner.submit(
        f"{case_name}:new",
        "creo_new_sheetmetal",
        {"model_name": model_name, "template": "native_planar"},
    )
    created_terminal = await runner.wait_job(created["job_id"], budget=BUDGET_SECONDS)
    entry = {
        "model_name": model_name,
        "model_id": created.get("model_id"),
        "new_job_id": created["job_id"],
        "new_status": created_terminal.get("status"),
        "new_revision": created_terminal.get("revision"),
    }
    if created_terminal.get("status") != "succeeded":
        entry.update(failure=failure_text(created_terminal), passed=False)
        return runner.case(entry), None

    snapshot = await runner.snapshot(entry["model_id"])
    create_plan, resize_plan = plate_operations()
    validate_operations(create_plan)
    validate_operations(resize_plan)
    create_job = await runner.submit(
        f"{case_name}:create",
        "creo_execute_plan",
        {
            "model_id": entry["model_id"],
            "expected_revision": snapshot.get("revision"),
            "operations": create_plan,
        },
    )
    create_terminal = await runner.wait_job(create_job["job_id"], budget=BUDGET_SECONDS)
    create_projection = pwall.result_projection(
        operation_detail(create_terminal, "sheetmetal_planar_wall")
    )
    entry["create"] = {
        "job_id": create_job["job_id"],
        "status": create_terminal.get("status"),
        "message": create_terminal.get("message"),
        "revision": create_terminal.get("revision"),
        "saved_file_reloaded_and_verified": (create_terminal.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ),
        "planar_wall": create_projection,
    }
    if create_terminal.get("status") != "succeeded":
        entry.update(failure=failure_text(create_terminal), passed=False)
        return runner.case(entry), None

    snapshot = await runner.snapshot(entry["model_id"])
    resize_job = await runner.submit(
        f"{case_name}:resize",
        "creo_execute_plan",
        {
            "model_id": entry["model_id"],
            "expected_revision": snapshot.get("revision"),
            "operations": resize_plan,
        },
    )
    resize_terminal = await runner.wait_job(resize_job["job_id"], budget=BUDGET_SECONDS)
    resize_projection = pwall.result_projection(
        operation_detail(resize_terminal, "resize_sheetmetal_planar_wall")
    )
    entry["resize"] = {
        "job_id": resize_job["job_id"],
        "status": resize_terminal.get("status"),
        "message": resize_terminal.get("message"),
        "revision": resize_terminal.get("revision"),
        "saved_file_reloaded_and_verified": (resize_terminal.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ),
        "planar_wall": resize_projection,
    }
    if resize_terminal.get("status") != "succeeded":
        entry.update(failure=failure_text(resize_terminal), passed=False)
        return runner.case(entry), None

    after = await runner.snapshot(entry["model_id"])
    entry["plate_bbox_mm"] = _bbox(after)
    entry["plate_volume_mm3"] = LiveRunner.volume(after)
    entry["plate_revision"] = after.get("revision")
    expected_volume = RESIZED_LENGTH_MM * RESIZED_WIDTH_MM * THICKNESS_MM
    entry["assertions"] = {
        "created_wall_verified": create_projection.get("verified") is True,
        "created_thickness_1mm": create_projection.get("thickness_measured_mm") == THICKNESS_MM,
        "created_volume_180x230": abs(
            (create_projection.get("volume_mm3") or 0)
            - PLANAR_LENGTH_MM * PLANAR_WIDTH_MM * THICKNESS_MM
        )
        < 0.01,
        "resize_feature_kept": resize_projection.get("feature_id")
        == create_projection.get("feature_id"),
        "resize_volume_185x232": abs((resize_projection.get("volume_mm3") or 0) - expected_volume)
        < 0.01,
        "resize_thickness_loaded_and_measured": (
            resize_projection.get("thickness_loaded_mm") == THICKNESS_MM
            and resize_projection.get("thickness_measured_mm") == THICKNESS_MM
        ),
        "resize_saved_and_reloaded": entry["resize"]["saved_file_reloaded_and_verified"] is True,
        "plate_bbox_is_185x232x1": _bbox_is(after, RESIZED_LENGTH_MM, RESIZED_WIDTH_MM),
    }
    entry["passed"] = all(entry["assertions"].values())
    return runner.case(entry), after


def _bbox_is(snapshot: dict, length: float, width: float) -> bool:
    bounds = _bbox(snapshot)
    if bounds is None:
        return False
    low, high = bounds
    spans = [high[0] - low[0], high[1] - low[1], high[2] - low[2]]
    return (
        abs(spans[0] - length) <= 0.01
        and abs(spans[1] - width) <= 0.01
        and abs(spans[2] - THICKNESS_MM) <= 0.01
    )


async def build_walls(
    runner: LiveRunner,
    case_name: str,
    plate_entry: dict,
    snapshot: dict,
    *,
    radius: float,
    miter: dict,
) -> dict:
    """Four flanges, one job each, every edge re-selected from the current model."""
    plate_bounds = fx.active_bbox(LiveRunner.inspection(snapshot))
    revision = snapshot.get("revision")
    verdict = {
        "group": case_name,
        "radius": radius,
        "miter_cuts": miter,
        "plate_bounds_mm": [list(plate_bounds[0]), list(plate_bounds[1])],
        "four_walls_complete": False,
        "passed": False,
    }
    records = []
    for side, label, use_miter in WALL_SEQUENCE:
        current = await runner.snapshot(plate_entry["model_id"])
        try:
            reference = fx.select_wall_edge(
                LiveRunner.inspection(current), plate_bounds, side, face="top", allow_shortened=True
            )
        except fx.EdgeSelectionError as error:
            records.append(
                {
                    "label": label,
                    "side": side,
                    "outcome": "driver_edge_selection_error",
                    "error": f"EdgeSelectionError: {error}",
                }
            )
            break
        operation = flange_operation(
            reference, label, radius=radius, miter=miter if use_miter else None
        )
        submitted = await runner.submit(
            f"{case_name}:{label}",
            "creo_sheetmetal_flange",
            {
                "model_id": plate_entry["model_id"],
                "expected_revision": current.get("revision"),
                **{key: value for key, value in operation.items() if key not in ("op",)},
            },
        )
        terminal = await runner.wait_job(submitted["job_id"], budget=BUDGET_SECONDS)
        after = await runner.snapshot(plate_entry["model_id"])
        record = wall_record(
            label,
            side,
            reference,
            terminal,
            after,
            revision,
            LiveRunner.volume(current),
            None,
        )
        record["outcome"] = "succeeded" if terminal.get("status") == "succeeded" else "failed"
        record["miter_cuts"] = miter if use_miter else None
        record["radius"] = radius
        record["added_mm3"] = (
            LiveRunner.volume(after) - LiveRunner.volume(current)
            if LiveRunner.volume(after) is not None and LiveRunner.volume(current) is not None
            else None
        )
        record["top_faces"] = None
        records.append(record)
        if terminal.get("status") == "succeeded":
            revision = record.get("revision_after")
    final = await runner.snapshot(plate_entry["model_id"])
    top = _bbox(final)
    faces = top_horizontal_faces(LiveRunner.inspection(final), top[1][2]) if top else []
    for record in records:
        if record["outcome"] == "succeeded":
            record["top_faces"] = wall_top_faces(
                faces, plate_bounds, record["side"], record.get("edge_span_mm")
            )
    corners = corner_patches(faces, plate_bounds)
    verdict.update(
        walls=records,
        box_volume_mm3=LiveRunner.volume(final),
        box_bbox_mm=top,
        top_face_count=len(faces),
        calibration=calibration_verdict(records, corners),
        volume_cross_check=volume_cross_check(
            plate_entry.get("plate_volume_mm3"), records, LiveRunner.volume(final)
        ),
    )
    complete = len(records) == len(WALL_SEQUENCE) and all(
        record["outcome"] == "succeeded" and record.get("saved_file_reloaded_and_verified") is True
        for record in records
    )
    measured = all(record.get("top_faces") is not None for record in records)
    verdict.update(
        four_walls_complete=complete,
        calibration_measured=measured,
        passed=complete and measured,
    )
    return runner.case(verdict)


async def run_baseline_box(runner: LiveRunner) -> dict:
    entry, snapshot = await create_plate(runner, "planar_box")
    if snapshot is None:
        return entry
    return await build_walls(runner, "planar_box", entry, snapshot, radius=RADIUS_MM, miter=MITER)


async def run_matrix(runner: LiveRunner) -> None:
    for combination in MATRIX:
        case_name = f"matrix_{combination['name']}"
        entry, snapshot = await create_plate(runner, case_name)
        if snapshot is None:
            continue
        await build_walls(
            runner,
            case_name,
            entry,
            snapshot,
            radius=float(combination["radius"]),
            miter=dict(combination["miter"]),
        )


def fixed_surface_of(inspection: dict, plate_bounds: tuple) -> dict | None:
    """The plate's own bottom face: horizontal, at the slab's low Z, largest area."""
    target = plate_bounds[0][2]
    best = None
    for surface in inspection.get("surfaces") or []:
        normal = surface.get("normal")
        bbox = surface.get("bbox")
        if not normal or not isinstance(bbox, list) or len(bbox) != 2:
            continue
        if abs(abs(float(normal[2])) - 1.0) > 1e-6:
            continue
        low, high = bbox
        if abs(float(low[2]) - target) > 0.2 or abs(float(high[2]) - target) > 0.2:
            continue
        area = abs(float(high[0]) - float(low[0])) * abs(float(high[1]) - float(low[1]))
        if best is None or area > best[0]:
            best = (area, surface.get("id"))
    return {"kind": "surface", "id": best[1]} if best else None


async def run_followup(runner: LiveRunner) -> dict:
    """Unfold all bends, refold them, then a refused and a failed modification."""
    entry, snapshot = await create_plate(runner, "followup")
    if snapshot is None:
        return entry
    box = await build_walls(runner, "followup", entry, snapshot, radius=RADIUS_MM, miter=MITER)
    verdict = {"group": "followup", "box": box.get("group"), "passed": False, "steps": []}
    if box.get("four_walls_complete") is not True:
        verdict["statement"] = "the follow-up needs a complete four-wall box first"
        return runner.case(verdict)

    current = await runner.snapshot(entry["model_id"])
    plate_bounds = fx.active_bbox(LiveRunner.inspection(current))
    fixed = fixed_surface_of(LiveRunner.inspection(current), plate_bounds)
    verdict["fixed_surface"] = fixed
    if fixed is None:
        verdict["statement"] = "no horizontal plate face was readable; unbend not attempted"
        return runner.case(verdict)
    box_volume = LiveRunner.volume(current)

    unbend = await runner.submit(
        "followup:unbend",
        "creo_sheetmetal_unbend",
        {
            "model_id": entry["model_id"],
            "expected_revision": current.get("revision"),
            "label": "unbend_all",
            "fixed_surface": fixed,
        },
    )
    unbend_terminal = await runner.wait_job(unbend["job_id"], budget=BUDGET_SECONDS)
    after_unbend = await runner.snapshot(entry["model_id"])
    verdict["steps"].append(
        {
            "step": "unbend_all",
            "job_id": unbend["job_id"],
            "status": unbend_terminal.get("status"),
            "message": unbend_terminal.get("message"),
            "saved_file_reloaded_and_verified": (unbend_terminal.get("result") or {}).get(
                "saved_file_reloaded_and_verified"
            ),
            "volume_before_mm3": box_volume,
            "volume_after_mm3": LiveRunner.volume(after_unbend),
            "bbox_after_mm": _bbox(after_unbend),
            "revision_before": current.get("revision"),
            "revision_after": after_unbend.get("revision"),
        }
    )
    if unbend_terminal.get("status") != "succeeded":
        verdict["statement"] = "the unfold step failed; refold was not attempted"
        verdict["passed"] = False
        return runner.case(verdict)

    bend_back = await runner.submit(
        "followup:bend_back",
        "creo_sheetmetal_bend_back",
        {
            "model_id": entry["model_id"],
            "expected_revision": after_unbend.get("revision"),
            "label": "bend_back_all",
            "fixed_surface": fixed,
        },
    )
    bend_terminal = await runner.wait_job(bend_back["job_id"], budget=BUDGET_SECONDS)
    after_back = await runner.snapshot(entry["model_id"])
    verdict["steps"].append(
        {
            "step": "bend_back_all",
            "job_id": bend_back["job_id"],
            "status": bend_terminal.get("status"),
            "message": bend_terminal.get("message"),
            "saved_file_reloaded_and_verified": (bend_terminal.get("result") or {}).get(
                "saved_file_reloaded_and_verified"
            ),
            "volume_before_mm3": LiveRunner.volume(after_unbend),
            "volume_after_mm3": LiveRunner.volume(after_back),
            "bbox_after_mm": _bbox(after_back),
            "revision_before": after_unbend.get("revision"),
            "revision_after": after_back.get("revision"),
        }
    )

    before_failure = await runner.snapshot(entry["model_id"])
    refused = None
    refusal_job = None
    refusal_status = None
    try:
        submitted = await runner.submit(
            "followup:refused_resize",
            "creo_execute_plan",
            {
                "model_id": entry["model_id"],
                "expected_revision": before_failure.get("revision"),
                "operations": plate_operations()[1],
            },
        )
    except LiveStop as error:
        refused = str(error)[:400]
    else:
        refusal_job = submitted["job_id"]
        refusal_terminal = await runner.wait_job(refusal_job, budget=BUDGET_SECONDS)
        refusal_status = refusal_terminal.get("status")
    after_refusal = await runner.snapshot(entry["model_id"])
    verdict["steps"].append(
        {
            "step": "resize_parent_with_children",
            "refused_before_job": refused is not None,
            "error": refused,
            "job_id": refusal_job,
            "status": refusal_status,
            "revision_before": before_failure.get("revision"),
            "revision_after": after_refusal.get("revision"),
            "note": (
                "a planar wall that already parents flanges may be refused before the job "
                "or by the native executor; either way the revision must not change"
            ),
        }
    )
    before_failure = after_refusal

    failing = await runner.submit(
        "followup:failed_flange",
        "creo_sheetmetal_flange",
        {
            "model_id": entry["model_id"],
            "expected_revision": before_failure.get("revision"),
            "label": "f_bad",
            "edge": {"kind": "edge", "id": 999999},
            "height": HEIGHT_MM,
            "angle": ANGLE_DEG,
            "radius": RADIUS_MM,
            "flip": False,
            "y_factor": Y_FACTOR,
        },
    )
    failing_terminal = await runner.wait_job(failing["job_id"], budget=BUDGET_SECONDS)
    after_failure = await runner.snapshot(entry["model_id"])
    verdict["steps"].append(
        {
            "step": "failed_flange",
            "job_id": failing["job_id"],
            "status": failing_terminal.get("status"),
            "message": failing_terminal.get("message"),
            "failure": failure_text(failing_terminal),
            "rollback_status": (failing_terminal.get("result") or {}).get("rollback_status"),
            "revision_before": before_failure.get("revision"),
            "revision_after": after_failure.get("revision"),
            "volume_before_mm3": LiveRunner.volume(before_failure),
            "volume_after_mm3": LiveRunner.volume(after_failure),
        }
    )
    steps = {step["step"]: step for step in verdict["steps"]}
    verdict["unsupported"] = {
        "height_edit": "no flange height-edit operation exists",
        "flange_delete": "no flange delete operation exists",
    }
    verdict["assertions"] = {
        "unbend_succeeded": steps["unbend_all"]["status"] == "succeeded",
        "unbend_saved_and_reloaded": steps["unbend_all"].get("saved_file_reloaded_and_verified")
        is True,
        "bend_back_succeeded": steps["bend_back_all"]["status"] == "succeeded",
        "bend_back_saved_and_reloaded": steps["bend_back_all"].get(
            "saved_file_reloaded_and_verified"
        )
        is True,
        "volume_restored": _volume_restored(
            steps["bend_back_all"].get("volume_after_mm3"), box_volume
        ),
        "parent_resize_stopped": steps["resize_parent_with_children"]["refused_before_job"] is True
        or steps["resize_parent_with_children"]["status"] == "failed",
        "parent_resize_revision_unchanged": steps["resize_parent_with_children"]["revision_after"]
        == steps["resize_parent_with_children"]["revision_before"],
        "failed_flange_rolled_back": steps["failed_flange"]["rollback_status"] == "succeeded",
        "failed_flange_revision_unchanged": steps["failed_flange"]["revision_after"]
        == steps["failed_flange"]["revision_before"],
        "failed_flange_volume_unchanged": _close(
            steps["failed_flange"].get("volume_after_mm3"),
            steps["failed_flange"].get("volume_before_mm3"),
        ),
    }
    verdict["passed"] = all(verdict["assertions"].values())
    return runner.case(verdict)


def _close(left: float | None, right: float | None, tolerance: float = 1e-6) -> bool:
    if left is None or right is None:
        return False
    return abs(float(left) - float(right)) <= tolerance


def _volume_restored(volume_after: float | None, volume_before: float | None) -> bool:
    if volume_after is None or volume_before is None or volume_before == 0:
        return False
    return abs(float(volume_after) - float(volume_before)) <= 0.01 * abs(float(volume_before))


# --- entry -----------------------------------------------------------------


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "sheetmetal_planar_box" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


async def live(cases: tuple[str, ...], output: Path, run_id: str) -> int:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    runner: LiveRunner | None = None
    teardown = None
    try:
        async with Client(params, read_timeout_seconds=300) as client:
            runner = LiveRunner(
                client,
                output,
                "FEAT-014 R09 / BUG-047",
                (
                    "native_planar plate 180x230x1 -> resize 185x232x1 -> four flanges "
                    "(h80/R2.54/Y0.5, current top edge per wall, miter on the third and fourth) "
                    "plus the measured corner calibration, the gap/radius matrix and the "
                    "unfold/refold follow-up"
                ),
                run_id,
            )
            runner.report["source"] = local_provenance()
            await runner.start()
            try:
                if "planar_box" in cases:
                    await run_baseline_box(runner)
                if "calibration" in cases:
                    await _calibration_only(runner)
                if "matrix" in cases:
                    await run_matrix(runner)
                if "followup" in cases:
                    await run_followup(runner)
                runner.report["matrix_summary"] = matrix_summary(runner.report["cases"])
            except BaseException as error:
                runner.report["stopped"] = f"{type(error).__name__}: {error}"
    except BaseException as error:  # teardown failures must not orphan the server
        teardown = f"{type(error).__name__}: {error}"
    if runner is None:
        raise RuntimeError(f"MCP client never started: {teardown}")
    if teardown:
        runner.report["client_teardown"] = teardown[:600]
    if runner.report.get("matrix_summary") is None:
        runner.report["matrix_summary"] = matrix_summary(runner.report["cases"])
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if runner.report["passed"] else 1


async def _calibration_only(runner: LiveRunner) -> None:
    """The baseline box already carries the calibration block; reuse its run."""
    if any(case.get("group") == "planar_box" for case in runner.report["cases"]):
        return
    entry, snapshot = await create_plate(runner, "calibration")
    if snapshot is None:
        return
    await build_walls(runner, "calibration", entry, snapshot, radius=RADIUS_MM, miter=MITER)


CASES = ("planar_box", "calibration", "matrix", "followup")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--case", choices=CASES, action="append", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.live and not args.confirm_session_usable:
        print(
            "live runs require --confirm-session-usable after human session checks", file=sys.stderr
        )
        return 2
    try:
        run_id = new_run_id()
        output = resolve_output(args.output, run_id)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    cases = tuple(args.case) if args.case else CASES
    if args.live:
        try:
            require_manual_start(ROOT / "config.json")
        except (ValueError, OSError) as error:
            print(f"LIVE_REFUSED: {error}", file=sys.stderr)
            return 2
        return asyncio.run(live(cases, output, run_id))

    report = {
        "task": "FEAT-014 R09 native_planar route",
        "run_id": run_id,
        "mode": "offline",
        "native_acceptance": "not_run",
        "source": local_provenance(),
        "checks": offline_checks(),
        "not_verified": [
            "no model was created and no wall was built offline",
            "the corner cut amount is measured only from live inspection surfaces",
            "the width/offset and radius matrix, the unfold/refold follow-up and the failed "
            "modification rollback are unrun here",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name("report.sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"report_sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
