"""R10: probe the sketch-frame translation the first-wall ``origin`` needs.

The planned ``origin:[u0,v0]`` is a sketch-local offset in mm: the rectangle
stays 185x232 but the wall starts at (u0, v0) instead of (0, 0). Two routes can
implement it:

  frame   move the sketch frame origin to (u0, v0) and keep the rectangle at
          0..L / 0..W (the explicit plane frame already accepts ``origin``);
  offset  keep the named plane frame untouched and move the rectangle to
          u0..u0+L / v0..v0+W.

This probe measures both on a solid part without touching product code. For
each case it records the sketch frame Creo actually placed (origin/u/v/n) and
the measured u/v/n envelope of an extruded 1 mm box, so the route is chosen on
geometry rather than on the shape of the request.

Measured outcome (2026-11-06, Creo 12.4): the ``frame`` route reproduces the
``offset`` envelope on XY and YZ, but on XZ the explicit plane keeps the support
normal (+Y) instead of the named convention (-Y), so v = cross(n, u) points at
-Z and the wall lands on the opposite side. The product therefore keeps the
named plane frame and moves the rectangle to u0..u0+L / v0..v0+W; the resize
recovers each corner side from the section location matrix because a coordinate
dimension is only a distance from an axis.

Nothing here creates or edits Creo models unless ``--live`` is passed together
with ``--confirm-session-usable``; the offline run only mirrors the envelope
arithmetic and checks the payloads against the current schema.

Usage:
  .\\.venv\\Scripts\\python.exe tools\\test_first_wall_origin.py
  .\\.venv\\Scripts\\python.exe tools\\test_first_wall_origin.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

LENGTH = 185.0
WIDTH = 232.0
DEPTH = 1.0
ORIGIN = (-92.5, -116.0)
SOLID_TEMPLATE = "mmns_part_solid_abs.prt"
SHEETMETAL_TEMPLATE = "mmns_part_sheetmetal_abs.prt"
TOLERANCE_MM = 1e-6
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
RUN_ID = format(int(time.time()), "x")
SOURCE_FILES = (
    "native/generic.cpp",
    "native/planar_wall.cpp",
    "src/creo_mechdog/schema.py",
    "tools/test_first_wall_origin.py",
)


def local_rectangle() -> list[list[float]]:
    return [[0.0, 0.0], [LENGTH, WIDTH]]


def offset_rectangle() -> list[list[float]]:
    return [[ORIGIN[0], ORIGIN[1]], [ORIGIN[0] + LENGTH, ORIGIN[1] + WIDTH]]


def cases() -> tuple[tuple[str, object, list[list[float]], str], ...]:
    frame_plane = {
        "reference": {"kind": "datum_plane", "axis": "z", "offset": 0},
        "origin": [ORIGIN[0], ORIGIN[1], 0.0],
        "u_axis": [1.0, 0.0, 0.0],
    }
    frame_xz = {
        "reference": {"kind": "datum_plane", "axis": "y", "offset": 0},
        "origin": [ORIGIN[0], 0.0, ORIGIN[1]],
        "u_axis": [1.0, 0.0, 0.0],
    }
    frame_yz = {
        "reference": {"kind": "datum_plane", "axis": "x", "offset": 0},
        "origin": [0.0, ORIGIN[0], ORIGIN[1]],
        "u_axis": [0.0, 1.0, 0.0],
    }
    return (
        ("xy_named", "XY", local_rectangle(), "positive"),
        ("xy_offset", "XY", offset_rectangle(), "positive"),
        ("xy_offset_negative", "XY", offset_rectangle(), "negative"),
        ("xy_frame_origin", frame_plane, local_rectangle(), "positive"),
        ("xy_frame_origin_negative", frame_plane, local_rectangle(), "negative"),
        ("xz_offset", "XZ", offset_rectangle(), "positive"),
        ("xz_frame_origin", frame_xz, local_rectangle(), "positive"),
        ("yz_offset", "YZ", offset_rectangle(), "positive"),
        ("yz_frame_origin", frame_yz, local_rectangle(), "positive"),
    )


def sketch_operation(case: tuple[str, object, list[list[float]], str]) -> dict:
    name, plane, rectangle, _ = case
    return {
        "op": "sketch",
        "label": name,
        "plane": plane,
        "entities": [
            {
                "type": "rectangle",
                "name": "wall",
                "min": rectangle[0],
                "max": rectangle[1],
            }
        ],
        "dimensioning": "coordinates",
    }


def operations(case: tuple[str, object, list[list[float]], str]) -> list[dict]:
    name, _, _, direction = case
    return [
        sketch_operation(case),
        {
            "op": "extrude",
            "label": name + "_pr",
            "sketch": name,
            "depth": DEPTH,
            "direction": direction,
        },
    ]


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def envelope(bounds: list[list[float]], frame: dict) -> dict:
    """Mirror of native/planar_wall.cpp::planar_wall_envelope."""
    low, high = bounds
    origin = frame["origin"]

    def extent(axis: list[float]) -> list[float]:
        values = []
        for corner in range(8):
            point = [high[i] if (corner >> i) & 1 else low[i] for i in range(3)]
            values.append(dot([p - o for p, o in zip(point, origin)], axis))
        return [min(values), max(values)]

    return {
        "u": extent(frame["u_axis"]),
        "v": extent(frame["v_axis"]),
        "n": extent(frame["normal"]),
    }


def expected_frame(plane: object) -> dict:
    """The named-plane u/v/n documented by native/generic.cpp::sketch_frame."""
    if plane == "XY":
        return {"u_axis": [1.0, 0.0, 0.0], "normal": [0.0, 0.0, 1.0]}
    if plane == "XZ":
        return {"u_axis": [1.0, 0.0, 0.0], "normal": [0.0, -1.0, 0.0]}
    if plane == "YZ":
        return {"u_axis": [0.0, 1.0, 0.0], "normal": [1.0, 0.0, 0.0]}
    return {}


def close(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= TOLERANCE_MM


def intervals_match(actual: list[float], expected: list[float]) -> bool:
    return close(actual[0], expected[0]) and close(actual[1], expected[1])


class Checks:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, name: str, ok: bool, detail: object = None) -> bool:
        self.items.append({"check": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    @property
    def failed(self) -> list[str]:
        return [item["check"] for item in self.items if not item["ok"]]

    @property
    def passed(self) -> bool:
        return not self.failed


def offline_checks() -> Checks:
    from creo_mechdog.schema import validate_operations

    checks = Checks()
    for case in cases():
        try:
            validate_operations(operations(case))
            checks.add(f"{case[0]}: payload accepted by the current schema", True)
        except Exception as error:  # noqa: BLE001 - the refusal text is the evidence
            checks.add(f"{case[0]}: payload accepted by the current schema", False, str(error))
    # The offset route is the one that must keep the named-plane frame.
    named = expected_frame("XY")
    bounds = [[ORIGIN[0], ORIGIN[1], 0.0], [ORIGIN[0] + LENGTH, ORIGIN[1] + WIDTH, DEPTH]]
    frame = {
        "origin": [0.0, 0.0, 0.0],
        "u_axis": named["u_axis"],
        "v_axis": [0.0, 1.0, 0.0],
        "normal": named["normal"],
    }
    measured = envelope(bounds, frame)
    checks.add(
        "offline: offset rectangle keeps the signed envelope",
        intervals_match(measured["u"], [ORIGIN[0], ORIGIN[0] + LENGTH])
        and intervals_match(measured["v"], [ORIGIN[1], ORIGIN[1] + WIDTH])
        and intervals_match(measured["n"], [0.0, DEPTH]),
        measured,
    )
    return checks


def source_identity() -> dict:
    from creo_mechdog.source_provenance import local_provenance

    evidence = local_provenance(ROOT, SOURCE_FILES)
    worker = ROOT / "build" / "creo_worker.exe"
    return {
        "commit": evidence["commit"],
        "branch": evidence["branch"],
        "dirty": evidence["dirty"],
        "git_status": evidence["git_status"],
        "source_sha256": evidence["source_sha256"],
        "source_fingerprint": evidence["source_fingerprint"],
        "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest()
        if worker.is_file()
        else None,
    }


def wait(job_id: str, timeout: float = 300.0) -> dict:
    terminal = {"succeeded", "failed", "aborted", "cancelled", "unknown_outcome"}
    deadline = time.time() + timeout
    record: dict = {}
    while time.time() < deadline:
        path = ROOT / "jobs" / job_id / "job.json"
        if path.is_file():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") in terminal:
                return record
        time.sleep(1.0)
    raise SystemExit(f"job {job_id} never finished: {record.get('status')}")


def operation_detail(job: dict, op: str) -> dict:
    for item in (job.get("result") or {}).get("operations") or []:
        if isinstance(item, dict) and item.get("op") == op:
            return item
    return {}


def inspection_of(job_id: str) -> dict:
    for path in sorted((ROOT / "jobs" / job_id).glob("inspection-verified-*.json")):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {}


def solid_bounds(inspection: dict) -> list[list[float]] | None:
    low = high = None
    for body in inspection.get("bodies") or []:
        bbox = body.get("bbox") if isinstance(body, dict) else None
        if not isinstance(bbox, list) or len(bbox) != 2:
            continue
        if low is None:
            low, high = list(bbox[0]), list(bbox[1])
            continue
        low = [min(a, b) for a, b in zip(low, bbox[0])]
        high = [max(a, b) for a, b in zip(high, bbox[1])]
    return [low, high] if low is not None else None


class Live:
    """Thin wrapper over generic_bridge for one model at a time."""

    def __init__(self) -> None:
        import generic_bridge

        self.bridge = generic_bridge

    def model(self, index: int) -> dict:
        submit = self.bridge.submit(
            [],
            model_name=f"fo_{RUN_ID}_{index}",
            model_type="part",
            template_name=SOLID_TEMPLATE,
        )
        return wait(submit["job_id"])

    def plan(self, model_id: str, operations: list[dict]) -> tuple[str, dict]:
        revision = self.bridge.model_info(model_id).get("revision")
        submit = self.bridge.submit(operations, model_id=model_id, expected_revision=revision)
        return submit["job_id"], wait(submit["job_id"])


def live_checks(report: dict) -> Checks:
    checks = Checks()
    live = Live()
    results: dict[str, dict] = report.setdefault("cases", {})

    for index, case in enumerate(cases()):
        name = case[0]
        setup = live.model(index)
        if not checks.add(
            f"{name}: empty part created",
            setup.get("status") == "succeeded",
            setup.get("message"),
        ):
            continue
        model_id = setup.get("model_id")
        if not model_id:
            checks.add(f"{name}: model id reported", False, setup.get("status"))
            continue
        job_id, job = live.plan(model_id, operations(case))
        sketch = operation_detail(job, "sketch")
        inspection = inspection_of(job_id)
        bounds = solid_bounds(inspection)
        entry = {
            "job_id": job_id,
            "status": job.get("status"),
            "message": job.get("message"),
            "sketch_frame": {
                "origin": sketch.get("origin"),
                "u_axis": sketch.get("u_axis"),
                "v_axis": sketch.get("v_axis"),
                "normal": sketch.get("normal"),
            },
            "section_location": sketch.get("section_location"),
            "bounds_mm": bounds,
            "center_of_gravity": inspection.get("center_of_gravity"),
            "volume_mm3": inspection.get("volume_mm3"),
            "saved_file_reloaded_and_verified": (job.get("result") or {}).get(
                "saved_file_reloaded_and_verified"
            ),
        }
        results[name] = entry
        if not checks.add(
            f"{name}: sketch and extrude succeeded",
            job.get("status") == "succeeded",
            job.get("message"),
        ):
            continue
        if not checks.add(f"{name}: material bbox measured", bool(bounds), bounds):
            continue
        frame = {
            "origin": sketch.get("origin"),
            "u_axis": sketch.get("u_axis"),
            "v_axis": sketch.get("v_axis"),
            "normal": sketch.get("normal"),
        }
        if None in frame.values():
            checks.add(f"{name}: sketch frame reported", False, frame)
            continue
        measured = envelope(bounds, frame)
        entry["envelope"] = measured
        checks.add(
            f"{name}: 185x232x1 volume",
            close(entry["volume_mm3"] or 0, 42920.0),
            entry["volume_mm3"],
        )
        checks.add(
            f"{name}: envelope along u/v",
            intervals_match(measured["u"], [case[2][0][0], case[2][1][0]])
            and intervals_match(measured["v"], [case[2][0][1], case[2][1][1]]),
            measured,
        )
    # Named plane vs offset route: the signed envelope and the frame must agree.
    baseline = results.get("xy_named") or {}
    offset = results.get("xy_offset") or {}
    if baseline.get("envelope") and offset.get("envelope"):
        checks.add(
            "offset route keeps the named XY frame",
            offset["sketch_frame"]["u_axis"] == baseline["sketch_frame"]["u_axis"]
            and offset["sketch_frame"]["normal"] == baseline["sketch_frame"]["normal"],
            {"named": baseline["sketch_frame"], "offset": offset["sketch_frame"]},
        )
        checks.add(
            "offset route keeps the XY growth direction",
            intervals_match(offset["envelope"]["n"], baseline["envelope"]["n"]),
            {"named": baseline["envelope"]["n"], "offset": offset["envelope"]["n"]},
        )
        checks.add(
            "xy offset wall starts at the requested origin",
            close((offset["bounds_mm"] or [[0, 0, 0]])[0][0], ORIGIN[0])
            and close((offset["bounds_mm"] or [[0, 0, 0]])[0][1], ORIGIN[1]),
            offset.get("bounds_mm"),
        )
    negative = results.get("xy_offset_negative") or {}
    if offset.get("envelope") and negative.get("envelope"):
        checks.add(
            "negative direction mirrors the n envelope only",
            intervals_match(negative["envelope"]["n"], [-DEPTH, 0.0])
            and intervals_match(negative["envelope"]["u"], offset["envelope"]["u"]),
            {"positive": offset["envelope"], "negative": negative["envelope"]},
        )
    for plane in ("xz_offset", "yz_offset", "yz_frame_origin"):
        entry = results.get(plane) or {}
        named = expected_frame(plane.split("_")[0].upper())
        if entry.get("envelope") and named:
            checks.add(
                f"{plane}: named frame is preserved",
                entry["sketch_frame"]["u_axis"] == named["u_axis"]
                and entry["sketch_frame"]["normal"] == named["normal"],
                entry["sketch_frame"],
            )
    # Probe finding: the explicit XZ frame takes the support normal (+Y) instead
    # of the named convention (-Y), so v = cross(n, u) points at -Z and the
    # rectangle lands on the opposite side. That is why the product keeps the
    # named frame and moves the rectangle (offset route) instead.
    xz_frame = results.get("xz_frame_origin") or {}
    if xz_frame.get("bounds_mm"):
        bounds = xz_frame["bounds_mm"]
        checks.add(
            "xz explicit frame mirrors v onto -Z (offset route chosen)",
            close(xz_frame["sketch_frame"]["normal"][1], 1.0)
            and intervals_match([bounds[0][2], bounds[1][2]], [ORIGIN[1] - WIDTH, ORIGIN[1]]),
            {"frame_normal": xz_frame["sketch_frame"]["normal"], "bounds_mm": bounds},
        )
    # The frame route reproduces the offset route on the planes where the named
    # frame survives the explicit plane (XZ diverges as recorded above).
    for plane in ("xy", "yz"):
        offset = results.get(f"{plane}_offset") or {}
        frame = results.get(f"{plane}_frame_origin") or {}
        if offset.get("bounds_mm") and frame.get("bounds_mm"):
            checks.add(
                f"{plane}: frame route reproduces the offset geometry",
                all(
                    close(a, b)
                    for actual, expected in zip(frame["bounds_mm"], offset["bounds_mm"])
                    for a, b in zip(actual, expected)
                ),
                {"offset": offset["bounds_mm"], "frame": frame["bounds_mm"]},
            )
    frame_negative = results.get("xy_frame_origin_negative") or {}
    if frame_negative.get("envelope"):
        checks.add(
            "frame route keeps the requested growth direction",
            intervals_match(frame_negative["envelope"]["n"], [-DEPTH, 0.0]),
            frame_negative["envelope"],
        )
    checks.items.extend(wall_checks(report).items)
    return checks


def wall_operation(
    plane: str = "XY",
    origin: tuple[float, float] | None = None,
    direction: str = "positive",
    length: float = LENGTH,
    width: float = WIDTH,
) -> dict:
    operation = {
        "op": "sheetmetal_planar_wall",
        "label": "wall",
        "plane": plane,
        "length": length,
        "width": width,
        "thickness": DEPTH,
        "direction": direction,
    }
    if origin is not None:
        operation["origin"] = list(origin)
    return operation


def resize_operation(length: float, width: float) -> dict:
    return {
        "op": "resize_sheetmetal_planar_wall",
        "feature": "wall",
        "length": length,
        "width": width,
    }


def bounds_match(actual: list[list[float]] | None, expected: list[list[float]]) -> bool:
    if not actual:
        return False
    return all(
        close(a, b) for point, target in zip(actual, expected) for a, b in zip(point, target)
    )


def wall_checks(report: dict) -> Checks:
    """R10 product acceptance: the origin on the real planar wall."""
    from creo_mechdog import native_planar_wall as pwall

    checks = Checks()
    live = Live()
    models: dict[str, dict] = report.setdefault("walls", {})
    counter = {"next": 100}

    def new_model(template: str = SHEETMETAL_TEMPLATE, model_type: str = "sheetmetal") -> str:
        setup = live.bridge.submit(
            [],
            model_name=f"fw_{RUN_ID}_{counter['next']}",
            model_type=model_type,
            template_name=template,
        )
        counter["next"] += 1
        return wait(setup["job_id"]).get("model_id")

    def run(model_id: str, operations: list[dict], op: str, name: str) -> tuple[str, dict, dict]:
        job_id, job = live.plan(model_id, operations)
        projection = pwall.result_projection(operation_detail(job, op))
        inspection = inspection_of(job_id)
        entry = {
            "job_id": job_id,
            "status": job.get("status"),
            "message": job.get("message"),
            "revision": job.get("revision"),
            "saved_file_reloaded_and_verified": (job.get("result") or {}).get(
                "saved_file_reloaded_and_verified"
            ),
            "projection": projection,
            "bounds_mm": solid_bounds(inspection),
            "center_of_gravity": inspection.get("center_of_gravity"),
            "volume_mm3": inspection.get("volume_mm3"),
        }
        models[name] = entry
        return job_id, job, entry

    def expect_wall(
        name: str,
        entry: dict,
        expected_bounds: list[list[float]],
        expected_volume: float,
        checks: Checks,
    ) -> None:
        checks.add(f"{name}: created", entry["status"] == "succeeded", entry["message"])
        checks.add(
            f"{name}: wall verified",
            entry["projection"].get("verified") is True,
            entry["projection"].get("problems"),
        )
        checks.add(
            f"{name}: signed frame envelope",
            entry["projection"].get("origin") is not None
            and bounds_match(entry["bounds_mm"], expected_bounds),
            {"bounds": entry["bounds_mm"], "expected": expected_bounds},
        )
        checks.add(
            f"{name}: volume", close(entry["volume_mm3"] or 0, expected_volume), entry["volume_mm3"]
        )
        checks.add(f"{name}: saved and reloaded", entry["saved_file_reloaded_and_verified"] is True)

    # A) the documented 185x232x1 wall around the model origin
    model_id = new_model()
    _, _, entry = run(
        model_id, [wall_operation(origin=ORIGIN)], "sheetmetal_planar_wall", "xy_origin"
    )
    expect_wall(
        "xy_origin",
        entry,
        [[ORIGIN[0], ORIGIN[1], 0.0], [ORIGIN[0] + LENGTH, ORIGIN[1] + WIDTH, DEPTH]],
        LENGTH * WIDTH * DEPTH,
        checks,
    )
    checks.add(
        "xy_origin: centred on the model origin",
        entry["center_of_gravity"] is not None
        and all(close(a, b) for a, b in zip(entry["center_of_gravity"], [0.0, 0.0, 0.5])),
        entry["center_of_gravity"],
    )
    checks.add(
        "xy_origin: reported origin",
        entry["projection"].get("origin") == [ORIGIN[0], ORIGIN[1]],
        entry["projection"].get("origin"),
    )

    # B) the default wall is unchanged
    model_id = new_model()
    _, _, entry = run(model_id, [wall_operation()], "sheetmetal_planar_wall", "xy_default")
    expect_wall(
        "xy_default",
        entry,
        [[0.0, 0.0, 0.0], [LENGTH, WIDTH, DEPTH]],
        LENGTH * WIDTH * DEPTH,
        checks,
    )

    # C/D) the other two named planes keep their own frame
    model_id = new_model()
    _, _, entry = run(
        model_id, [wall_operation("XZ", ORIGIN)], "sheetmetal_planar_wall", "xz_origin"
    )
    expect_wall(
        "xz_origin",
        entry,
        [[ORIGIN[0], -DEPTH, ORIGIN[1]], [ORIGIN[0] + LENGTH, 0.0, ORIGIN[1] + WIDTH]],
        LENGTH * WIDTH * DEPTH,
        checks,
    )
    model_id = new_model()
    _, _, entry = run(
        model_id, [wall_operation("YZ", ORIGIN)], "sheetmetal_planar_wall", "yz_origin"
    )
    expect_wall(
        "yz_origin",
        entry,
        [[0.0, ORIGIN[0], ORIGIN[1]], [DEPTH, ORIGIN[0] + LENGTH, ORIGIN[1] + WIDTH]],
        LENGTH * WIDTH * DEPTH,
        checks,
    )

    # E) the growth direction still mirrors only along the normal
    model_id = new_model()
    _, _, entry = run(
        model_id,
        [wall_operation(origin=ORIGIN, direction="negative")],
        "sheetmetal_planar_wall",
        "xy_origin_negative",
    )
    expect_wall(
        "xy_origin_negative",
        entry,
        [[ORIGIN[0], ORIGIN[1], -DEPTH], [ORIGIN[0] + LENGTH, ORIGIN[1] + WIDTH, 0.0]],
        LENGTH * WIDTH * DEPTH,
        checks,
    )

    # F) resize in the same plan keeps origin and feature identity
    model_id = new_model()
    job_id, job, entry = run(
        model_id,
        [wall_operation(origin=ORIGIN), resize_operation(200.0, 250.0)],
        "resize_sheetmetal_planar_wall",
        "resize_same_plan",
    )
    expect_wall(
        "resize_same_plan",
        entry,
        [[ORIGIN[0], ORIGIN[1], 0.0], [ORIGIN[0] + 200.0, ORIGIN[1] + 250.0, DEPTH]],
        200.0 * 250.0 * DEPTH,
        checks,
    )
    checks.add(
        "resize_same_plan: feature identity kept",
        entry["projection"].get("feature_id_unchanged") is True,
        entry["projection"].get("feature_id_before"),
    )
    created = (job.get("result") or {}).get("operations") or []
    first = next((item for item in created if item.get("op") == "sheetmetal_planar_wall"), {})
    checks.add(
        "resize_same_plan: wall kept its id",
        first.get("feature_id") is not None
        and first.get("feature_id") == entry["projection"].get("feature_id"),
        {"created": first.get("feature_id"), "resized": entry["projection"].get("feature_id")},
    )

    # G) a resize in a later job still honours the recorded origin
    model_id = new_model()
    run(model_id, [wall_operation(origin=ORIGIN)], "sheetmetal_planar_wall", "resize_cross_create")
    _, _, entry = run(
        model_id,
        [resize_operation(200.0, 250.0)],
        "resize_sheetmetal_planar_wall",
        "resize_cross_job",
    )
    expect_wall(
        "resize_cross_job",
        entry,
        [[ORIGIN[0], ORIGIN[1], 0.0], [ORIGIN[0] + 200.0, ORIGIN[1] + 250.0, DEPTH]],
        200.0 * 250.0 * DEPTH,
        checks,
    )

    # H) a second wall is refused before dispatch: no job, no geometry change,
    #    and the wall created with the origin stays resizable afterwards.
    #    Native rollback of the wall itself is covered by the R09 failure matrix
    #    (set_dimensions on an unknown id), not re-injected here.
    model_id = new_model()
    run(model_id, [wall_operation(origin=ORIGIN)], "sheetmetal_planar_wall", "refusal_create")
    before = live.bridge.model_info(model_id)
    second = dict(wall_operation(origin=ORIGIN), label="wall2")
    refusal = None
    try:
        live.plan(model_id, [second])
    except ValueError as error:
        refusal = str(error)
    after = live.bridge.model_info(model_id)
    models["second_wall_refusal"] = {
        "refusal": refusal,
        "revision_before": before.get("revision"),
        "revision_after": after.get("revision"),
    }
    checks.add("second_wall_refusal: refused before dispatch", refusal is not None, refusal)
    checks.add(
        "second_wall_refusal: revision unchanged",
        before.get("revision") == after.get("revision"),
        {"before": before.get("revision"), "after": after.get("revision")},
    )
    _, job, entry = run(
        model_id,
        [resize_operation(200.0, 250.0)],
        "resize_sheetmetal_planar_wall",
        "refusal_then_resize",
    )
    expect_wall(
        "refusal_then_resize",
        entry,
        [[ORIGIN[0], ORIGIN[1], 0.0], [ORIGIN[0] + 200.0, ORIGIN[1] + 250.0, DEPTH]],
        200.0 * 250.0 * DEPTH,
        checks,
    )
    return checks


def report_directory() -> Path:
    target = ROOT / "build" / "first_wall_origin" / STAMP
    target.mkdir(parents=True, exist_ok=True)
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    args = parser.parse_args()
    mode = "live" if args.live else "offline"
    if args.live and not args.confirm_session_usable:
        raise SystemExit("pass --confirm-session-usable after checking the live session")

    directory = report_directory()
    report: dict = {
        "work_item": "R10",
        "mode": mode,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "run_stamp": STAMP,
        "run_id": RUN_ID,
        "origin_mm": list(ORIGIN),
        "size_mm": [LENGTH, WIDTH, DEPTH],
        "source": source_identity(),
    }
    checks = offline_checks()
    if args.live:
        checks.items.extend(live_checks(report).items)
    report["checks"] = checks.items
    report["failed"] = checks.failed
    report["passed"] = checks.passed
    target = directory / f"origin_{mode}.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = checks.failed
    print(f"{mode}: {len(checks.items) - len(failed)}/{len(checks.items)} checks passed")
    for name in failed:
        print(f"  FAILED {name}")
    print(f"report {target.relative_to(ROOT)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
