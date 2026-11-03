"""FEAT-035 / A03 acceptance driver: standard threaded holes.

Default run is offline: it checks the frozen table, the schema guards and the
volume oracle without touching Creo, so the case table keeps its judgement when
the session is unavailable. ``--live`` additionally creates the fixture plate,
submits every positive case and records what Creo really built.

Positive cases are judged only by what the job returns: the created feature's
own thread readback, its material removal against the table's tap drill, the
`saved_file_reloaded_and_verified` flag and a strictly increasing feature id.
Negative cases must be refused before a job exists (schema) or by the native
chart guard (in-process resolver override), never by a plain hole that looks
threaded.

Usage:
  python tools/test_adoption_standard_holes.py
  python tools/test_adoption_standard_holes.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import probe_standard_hole as probe  # noqa: E402

from creo_mechdog import hole_standards  # noqa: E402
from creo_mechdog.schema import HoleOp  # noqa: E402

PLATE = [
    {
        "op": "sketch",
        "label": "accept_plate_sketch",
        "plane": "XY",
        "entities": [
            {"type": "rectangle", "name": "plate", "min": [0.0, 0.0], "max": [60.0, 60.0]}
        ],
    },
    {
        "op": "extrude",
        "label": "accept_plate",
        "sketch": "accept_plate_sketch",
        "depth": 12.0,
        "mode": "add",
        "direction": "positive",
        "depth_type": "blind",
    },
]
PLATE_TOP_Z = 12.0
PLATE_BOTTOM_Z = 0.0
FLIP_CASE = "iso_m5x0_8_flip"

# name, series, size, thread_depth, depth, offsets, flip
POSITIVE_CASES = [
    ("iso_m6x1", "ISO", "M6", 8.0, 10.0, (15.0, 15.0), False),
    ("iso_m8x1_25", "ISO", "M8", 10.0, 12.0, (45.0, 15.0), False),
    ("iso_m5x0_8_flip", "ISO", "M5", 6.0, 8.0, (15.0, 45.0), True),
]

# Plain-hole regressions on the same plate: the old receipts must not change.
PLAIN_CASES = [
    ("plain_straight", {"diameter": 6.0}, None),
    (
        "plain_counterbore",
        {"diameter": 10.0, "counterbore": {"diameter": 16.0, "depth": 3.0}},
        None,
    ),
    (
        "plain_countersink",
        {"diameter": 10.0, "countersink": {"diameter": 16.0, "angle": 90.0}},
        None,
    ),
]
PLAIN_OFFSETS = [(45.0, 45.0), (30.0, 30.0), (45.0, 30.0)]

# name, standard overrides, expected message fragment
SCHEMA_REJECTIONS = [
    ("unknown_size", {"size": "M7", "thread_depth": 6.0}, "is not in ISO"),
    ("path_escape", {"size": "../M6", "thread_depth": 6.0}, "not paths"),
    ("over_table_limit", {"size": "M6", "thread_depth": 13.0}, "table limit"),
    ("beyond_tip", {"size": "M6", "thread_depth": 6.0, "depth": 4.0}, "strictly inside"),
]


def oracle(series: str, size: str, thread_depth: float, depth: float) -> dict:
    """Expected geometry for one standard hole, from the frozen table only."""
    row = hole_standards.resolve_standard_hole(series, size)
    tap = row["tap_drill_diameter_mm"]
    cone = hole_standards.tip_cone_height_mm(tap)
    cylinder = math.pi / 4.0 * tap**2 * depth
    cone_volume = math.pi / 3.0 * (tap / 2.0) ** 2 * cone
    return {
        "table_id": row["table_id"],
        "table_sha256": row["table_sha256"],
        "fastener_id": row["fastener_id"],
        "tap_drill_mm": tap,
        "tip_depth_mm": depth + cone,
        "thread_depth_mm": thread_depth,
        "volume_mm3": [cylinder, cylinder + cone_volume],
        "nominal_diameter_mm": row["nominal_diameter_mm"],
    }


def standard_payload(series: str, size: str, thread_depth: float, depth: float) -> dict:
    return {"series": series, "size": size, "thread_depth": thread_depth, "depth": depth}


def positive_operation(
    geometry: dict,
    label: str,
    series: str,
    size: str,
    thread_depth: float,
    depth: float,
    offsets: tuple[float, float],
    flip: bool,
) -> dict:
    return {
        "op": "hole",
        "label": label,
        "placement": {"kind": "surface", "id": geometry["top_face_id"]},
        "reference1": {"kind": "datum_plane", "id": geometry["datum_x_id"]},
        "reference2": {"kind": "datum_plane", "id": geometry["datum_y_id"]},
        "offset1": offsets[0],
        "offset2": offsets[1],
        "depth": depth,
        "flip": flip,
        "standard": {"series": series, "size": size, "thread_depth": thread_depth},
    }


def plain_operation(geometry: dict, label: str, payload: dict, offsets: tuple[float, float]):
    operation = {
        "op": "hole",
        "label": label,
        "placement": {"kind": "surface", "id": geometry["top_face_id"]},
        "reference1": {"kind": "datum_plane", "id": geometry["datum_x_id"]},
        "reference2": {"kind": "datum_plane", "id": geometry["datum_y_id"]},
        "offset1": offsets[0],
        "offset2": offsets[1],
    }
    operation.update(payload)
    return operation


def offline_checks() -> list[dict]:
    """No Creo: prove the case table, the oracle and the schema guards agree."""
    results = []
    for name, series, size, thread, depth, _offsets, _flip in POSITIVE_CASES:
        expectation = oracle(series, size, thread, depth)
        payload = standard_payload(series, size, thread, depth)
        parsed = HoleOp.model_validate(
            {
                "op": "hole",
                "label": "offline_" + name,
                "placement": {"kind": "surface", "id": 1},
                "reference1": {"kind": "datum_plane", "id": 2},
                "reference2": {"kind": "datum_plane", "id": 3},
                "depth": payload.pop("depth"),
                "standard": payload,
            }
        )
        inside_tip = thread < expectation["tip_depth_mm"]
        results.append(
            {
                "case": name,
                "kind": "offline_positive",
                "thread_depth_mm": parsed.standard.thread_depth,
                "tip_depth_mm": round(expectation["tip_depth_mm"], 6),
                "volume_mm3": [round(value, 6) for value in expectation["volume_mm3"]],
                "thread_inside_tip": inside_tip,
                "pass": inside_tip,
            }
        )
    for name, overrides, fragment in SCHEMA_REJECTIONS:
        payload = {
            "op": "hole",
            "label": "offline_" + name,
            "placement": {"kind": "surface", "id": 1},
            "reference1": {"kind": "datum_plane", "id": 2},
            "reference2": {"kind": "datum_plane", "id": 3},
            "depth": overrides.get("depth", 20.0),
            "standard": {
                "series": "ISO",
                "size": "M6",
                "thread_depth": 6.0,
                **{key: value for key, value in overrides.items() if key != "depth"},
            },
        }
        try:
            HoleOp.model_validate(payload)
        except ValueError as error:
            results.append(
                {
                    "case": name,
                    "kind": "offline_rejection",
                    "expected": fragment,
                    "observed": str(error),
                    "pass": fragment in str(error),
                }
            )
        else:
            results.append(
                {
                    "case": name,
                    "kind": "offline_rejection",
                    "expected": fragment,
                    "observed": "accepted",
                    "pass": False,
                }
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", default="build/acceptance_standard_holes.json")
    args = parser.parse_args()

    report: dict = {"live": bool(args.live), "cases": offline_checks()}
    offline_ok = all(case["pass"] for case in report["cases"])
    if not args.live:
        report["offline_ok"] = offline_ok
        report["success"] = offline_ok
        write(args.output, report)
        print(json.dumps({"offline_ok": offline_ok, "report": args.output}, ensure_ascii=False))
        return 0 if offline_ok else 1
    if not args.confirm_session_usable:
        raise SystemExit("pass --confirm-session-usable after checking the live session")

    import generic_bridge

    try:
        live, ok = run_live(generic_bridge)
    except Exception as error:  # a broken fixture must still leave its evidence
        live, ok = (
            [{"case": "driver_error", "kind": "error", "observed": str(error), "pass": False}],
            False,
        )
    report["cases"].extend(live)
    report["success"] = offline_ok and ok
    write(args.output, report)
    print(
        json.dumps(
            {
                "success": report["success"],
                "failed_cases": [case["case"] for case in report["cases"] if not case["pass"]],
                "report": args.output,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["success"] else 1


def write(path: str, report: dict) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def wait(job_id: str, timeout: float = 300.0) -> dict:
    terminal = {"succeeded", "failed", "aborted", "cancelled"}
    deadline = time.time() + timeout
    record: dict = {}
    while time.time() < deadline:
        path = ROOT / "jobs" / job_id / "job.json"
        if path.is_file():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") in terminal:
                return record
        time.sleep(1.0)
    raise SystemExit(f"job {job_id} did not reach a terminal state: {record.get('status')}")


def submit_and_wait(plan: list[dict], **kwargs) -> dict:
    import generic_bridge

    accepted = generic_bridge.submit(plan, **kwargs)
    return wait(accepted["job_id"])


def pick_bottom_face(inspection: dict) -> int | None:
    """Id of the plate's z=0 face, where a flipped blind hole cuts upwards."""
    for item in inspection.get("surfaces") or []:
        if not isinstance(item, dict):
            continue
        if probe._axis_of(item.get("normal")) != "z":
            continue
        origin = item.get("origin")
        if isinstance(origin, list) and abs(origin[2] - PLATE_BOTTOM_Z) < 1e-6:
            return item.get("id")
    return None


def pick_xy_datum(inspection: dict) -> int | None:
    """Id of the z-normal datum plane: same plane as the plate bottom."""
    for item in inspection.get("datum_planes") or []:
        if isinstance(item, dict) and probe._axis_of(item.get("normal")) == "z":
            return item.get("id")
    return None


def operation_result(job: dict) -> dict:
    operations = (job.get("result") or {}).get("operations") or [{}]
    return operations[0] if isinstance(operations[0], dict) else {}


def current_revision(generic_bridge, model_id: str) -> int:
    """Registry revision after a job: a failed job may still move it."""
    return int(generic_bridge.model_info(model_id).get("revision") or 0)


def run_live(generic_bridge) -> tuple[list[dict], bool]:
    cases: list[dict] = []
    # The reused geometry picker keys the top face by the probe plate height.
    probe.PLATE_TOP_Z = PLATE_TOP_Z
    run_name = "accept_std_" + str(int(time.time()))
    plate = submit_and_wait(PLATE, model_name=run_name)
    cases.append(
        {
            "case": "fixture_plate",
            "kind": "setup",
            "status": plate.get("status"),
            "model_id": plate.get("model_id"),
            "revision": plate.get("revision"),
            "pass": plate.get("status") == "succeeded",
        }
    )
    if plate.get("status") != "succeeded":
        return cases, False

    model_id = plate["model_id"]
    inspection = probe.load_inspection(plate)
    geometry = probe.pick_geometry(inspection)
    geometry["bottom_face_id"] = pick_bottom_face(inspection)
    geometry["datum_xy_id"] = pick_xy_datum(inspection)
    if not all(
        geometry[key]
        for key in ("top_face_id", "bottom_face_id", "datum_xy_id", "datum_x_id", "datum_y_id")
    ):
        cases.append(
            {"case": "fixture_geometry", "kind": "setup", "geometry": geometry, "pass": False}
        )
        return cases, False

    last_feature_id = 0
    revision = plate["revision"]
    for name, series, size, thread, depth, offsets, flip in POSITIVE_CASES:
        expectation = oracle(series, size, thread, depth)
        operation = positive_operation(
            geometry, "h_" + name, series, size, thread, depth, offsets, flip
        )
        if name == FLIP_CASE:
            # Placement on the z=0 datum plane: the default cut leaves the solid,
            # so only flip=true removes material. direction proves the flag.
            operation["placement"] = {"kind": "datum_plane", "id": geometry["datum_xy_id"]}
        try:
            job = submit_and_wait([operation], model_id=model_id, expected_revision=revision)
        except ValueError as error:
            cases.append(
                {"case": name, "kind": "standard_hole", "refused": str(error), "pass": False}
            )
            continue
        result = operation_result(job)
        removed = result.get("material_removed_mm3")
        low, high = expectation["volume_mm3"]
        tolerance = max(1e-3, high * 0.01)
        checks = {
            "status_succeeded": job.get("status") == "succeeded",
            "thread_verified": result.get("thread_metadata_verified") is True,
            "readback_depth": isinstance(result.get("thread_readback"), dict)
            and abs(float(result["thread_readback"].get("thread_depth_mm") or -1.0) - thread)
            <= 1e-6,
            "removal_in_range": isinstance(removed, (int, float))
            and (low - tolerance) <= float(removed) <= (high + tolerance),
            "saved_reload": (job.get("result") or {}).get("saved_file_reloaded_and_verified")
            is True,
            "new_feature": isinstance(result.get("feature_id"), int)
            and result["feature_id"] > last_feature_id,
        }
        if name == FLIP_CASE:
            # Native reports the placement point and the cut extent, not a
            # direction: the flipped hole must span the blind depth *inside* the
            # plate (z 0..12), which the removal oracle already matches.
            axes = result.get("axes") or []
            axis = axes[0] if axes and isinstance(axes[0], dict) else {}
            start, end = axis.get("start"), axis.get("end")
            inside = (
                isinstance(start, list)
                and isinstance(end, list)
                and min(start[2], end[2]) >= PLATE_BOTTOM_Z - 1e-6
                and max(start[2], end[2]) <= PLATE_TOP_Z + 1e-6
                and abs(abs(start[2] - end[2]) - depth) <= 1e-6
            )
            checks["axis_inside_plate"] = inside
        if isinstance(result.get("feature_id"), int):
            last_feature_id = result["feature_id"]
        revision = current_revision(generic_bridge, model_id)
        cases.append(
            {
                "case": name,
                "kind": "standard_hole",
                "job_id": job.get("job_id"),
                "status": job.get("status"),
                "message": job.get("message"),
                "flip": flip,
                "expected": {
                    "tap_drill_mm": expectation["tap_drill_mm"],
                    "volume_range_mm3": [round(low, 4), round(high, 4)],
                },
                "observed": {
                    "feature_id": result.get("feature_id"),
                    "material_removed_mm3": removed,
                    "thread_metadata": result.get("thread_metadata"),
                    "thread_metadata_verified": result.get("thread_metadata_verified"),
                    "thread_readback": result.get("thread_readback"),
                    "saved_file_reloaded_and_verified": (job.get("result") or {}).get(
                        "saved_file_reloaded_and_verified"
                    ),
                },
                "checks": checks,
                "pass": all(checks.values()),
            }
        )

    # Contrast for the flip case: the same placement without flip must not cut,
    # which is what proves the flag (not the face) decided the direction.
    contrast = positive_operation(
        geometry, "h_flip_contrast", "ISO", "M5", 6.0, 8.0, (15.0, 45.0), False
    )
    contrast["placement"] = {"kind": "datum_plane", "id": geometry["datum_xy_id"]}
    job = submit_and_wait([contrast], model_id=model_id, expected_revision=revision)
    result = operation_result(job)
    message = str(job.get("message") or "")
    checks = {
        "failed": job.get("status") == "failed",
        "removes_no_material": "removes no material" in message.lower(),
        "no_feature_created": not isinstance(result.get("feature_id"), int),
    }
    cases.append(
        {
            "case": "flip_off_no_material",
            "kind": "flip_contrast",
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "message": message,
            "checks": checks,
            "pass": all(checks.values()),
        }
    )
    revision = current_revision(generic_bridge, model_id)

    for position, (name, payload, _unused) in enumerate(PLAIN_CASES):
        operation = plain_operation(geometry, "h_" + name, payload, PLAIN_OFFSETS[position])
        job = submit_and_wait([operation], model_id=model_id, expected_revision=revision)
        result = operation_result(job)
        checks = {
            "status_succeeded": job.get("status") == "succeeded",
            "no_thread_metadata": "thread_metadata" not in result,
            "no_thread_verified": "thread_metadata_verified" not in result,
            "material_removed": isinstance(result.get("material_removed_mm3"), (int, float))
            and float(result["material_removed_mm3"]) > 0.0,
            "saved_reload": (job.get("result") or {}).get("saved_file_reloaded_and_verified")
            is True,
        }
        revision = current_revision(generic_bridge, model_id)
        cases.append(
            {
                "case": name,
                "kind": "plain_regression",
                "job_id": job.get("job_id"),
                "status": job.get("status"),
                "message": job.get("message"),
                "observed": {
                    "material_removed_mm3": result.get("material_removed_mm3"),
                    "depth_basis": result.get("depth_basis"),
                },
                "checks": checks,
                "pass": all(checks.values()),
            }
        )

    # Schema rejections must not create a job at all.
    for name, overrides, fragment in SCHEMA_REJECTIONS:
        payload = {
            "op": "hole",
            "label": "h_reject_" + name,
            "placement": {"kind": "surface", "id": geometry["top_face_id"]},
            "reference1": {"kind": "datum_plane", "id": geometry["datum_x_id"]},
            "reference2": {"kind": "datum_plane", "id": geometry["datum_y_id"]},
            "offset1": 30.0,
            "offset2": 30.0,
            "depth": overrides.get("depth", 10.0),
            "standard": {
                "series": "ISO",
                "size": "M6",
                "thread_depth": 6.0,
                **{key: value for key, value in overrides.items() if key != "depth"},
            },
        }
        try:
            generic_bridge.submit([payload], model_id=model_id, expected_revision=revision)
        except ValueError as error:
            cases.append(
                {
                    "case": name,
                    "kind": "schema_rejection",
                    "expected": fragment,
                    "observed": str(error),
                    "pass": fragment in str(error),
                }
            )
        else:
            cases.append(
                {
                    "case": name,
                    "kind": "schema_rejection",
                    "expected": fragment,
                    "observed": "accepted",
                    "pass": False,
                }
            )

    native = native_chart_refusal(generic_bridge, geometry, model_id, revision)
    cases.append(native)
    if native.get("revision") is not None:
        revision = native["revision"]
    rollback = rollback_case(generic_bridge, geometry, model_id, revision)
    cases.append(rollback)

    return cases, all(case["pass"] for case in cases)


def _bogus_resolver(real):
    def resolve(series: str, size: str) -> dict:
        row = dict(real(series, size))
        # Absent from the installed ISO chart (checked against ISO.hol); the
        # chart, not this table, decides availability.
        row["fastener_id"] = "M6x9"
        return row

    return resolve


def native_chart_refusal(generic_bridge, geometry: dict, model_id: str, revision: int) -> dict:
    """A row the installed chart does not have must fail, not become a plain hole."""
    import creo_mechdog.schema as schema
    from creo_mechdog import hole_standards as standards

    real_schema = schema.resolve_standard_hole
    real_prepare = standards.resolve_standard_hole
    schema.resolve_standard_hole = _bogus_resolver(real_schema)
    standards.resolve_standard_hole = _bogus_resolver(real_prepare)
    try:
        operation = positive_operation(
            geometry, "h_chart_missing", "ISO", "M6", 6.0, 10.0, (30.0, 45.0), False
        )
        job = submit_and_wait([operation], model_id=model_id, expected_revision=revision)
    finally:
        schema.resolve_standard_hole = real_schema
        standards.resolve_standard_hole = real_prepare
    message = str(job.get("message") or "")
    after = current_revision(generic_bridge, model_id)
    checks = {
        "failed": job.get("status") == "failed",
        "mentions_chart": "hole chart" in message,
        "revision_unchanged": after == revision,
    }
    return {
        "case": "chart_missing_size",
        "kind": "native_rejection",
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "message": message,
        "checks": checks,
        "pass": all(checks.values()),
        "revision": after,
    }


def rollback_case(generic_bridge, geometry: dict, model_id: str, revision: int) -> dict:
    """A plan whose second hole fails must roll back and leave a usable model."""
    good = plain_operation(geometry, "h_rb_good", {"diameter": 6.0, "depth": 6.0}, (30.0, 15.0))
    bad = positive_operation(geometry, "h_rb_bad", "ISO", "M8", 10.0, 12.0, (30.0, 45.0), False)
    bad["reference1"] = {"kind": "datum_plane", "id": 999999}
    job = submit_and_wait([good, bad], model_id=model_id, expected_revision=revision)
    result = job.get("result") or {}
    after_rollback = current_revision(generic_bridge, model_id)
    follow_up = plain_operation(
        geometry, "h_rb_after", {"diameter": 5.0, "depth": 5.0}, (15.0, 30.0)
    )
    after = submit_and_wait([follow_up], model_id=model_id, expected_revision=after_rollback)
    checks = {
        "plan_failed": job.get("status") == "failed",
        "rollback_confirmed": result.get("rollback_succeeded") is True,
        "revision_unchanged": after_rollback == revision,
        "model_still_editable": after.get("status") == "succeeded",
    }
    return {
        "case": "deliberate_failure_rollback",
        "kind": "rollback",
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "message": job.get("message"),
        "failed_operation_index": result.get("failed_operation_index"),
        "checks": checks,
        "pass": all(checks.values()),
    }


if __name__ == "__main__":
    raise SystemExit(main())
