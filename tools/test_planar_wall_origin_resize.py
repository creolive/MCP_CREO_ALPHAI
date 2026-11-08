"""FEAT-058/H01: origin/plateau resize matrix for the native planar wall.

The 0.17.4 external report showed a non-zero ``origin`` resize solving the
wrong volume: 185x232x1 at origin [-92.5,-116] resized to 100x60 produced
17200 mm3 (100 x (116+56)) and was refused. The native rectangle is driven by
coordinate dimensions, which are distances to the section axes, so a corner
that must move to the other side of the origin has to be written as a negative
dimension value.

This driver keeps the offline default (schema + geometry arithmetic only) and
runs the live matrix only with ``--live --confirm-session-usable``:

* origins zero/positive/negative/mixed, with targets that cross and do not
  cross the origin distance;
* identity, shrink and grow, XY/XZ/YZ, positive/negative thickness direction;
* a resize inside the creating plan and a resize in a later job;
* a native save (save, reload, verify) followed by a resize that reads the
  saved part back from disk; a literal session erase is unavailable for a
  managed model, so it is neither claimed nor simulated;
* every case records job id, terminal status, volume, measured bbox and
  envelope, feature id, revision and saved_file_reloaded_and_verified.

Reports land under build/planar_wall_origin_resize/<run_id>/report.json and are
never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from creo_mechdog.schema import validate_operations  # noqa: E402
from tools.sheetmetal_live import require_manual_start, unique_name  # noqa: E402

THICKNESS = 1.0
BUDGET_SECONDS = 300.0
TERMINAL = {"succeeded", "failed", "aborted", "cancelled", "unknown_outcome"}

#: name, plane, direction, origin, create LxW, list of steps.
#: A step is ("resize", L, W) in its own job, ("resize_same_plan", L, W) appended
#: to the creating plan, or ("save_then_resize", L, W): a native save (which
#: saves, reloads and verifies) plus a resize job that reads the part back from
#: disk. A literal session erase is not available for a managed model: the erase
#: tool refuses managed targets and re-adopting the saved file is refused as
#: managed_output/source_origin_mismatch.
CASES = (
    ("xy_neg_cross", "XY", "positive", (-92.5, -116.0), (185.0, 232.0), [("resize", 100.0, 60.0)]),
    (
        "xy_neg_identity",
        "XY",
        "positive",
        (-92.5, -116.0),
        (185.0, 232.0),
        [("resize", 185.0, 232.0)],
    ),
    (
        "xy_neg_shrink",
        "XY",
        "positive",
        (-92.5, -116.0),
        (185.0, 232.0),
        [("resize", 180.0, 230.0)],
    ),
    (
        "xy_neg_no_cross",
        "XY",
        "positive",
        (-92.5, -116.0),
        (185.0, 232.0),
        [("resize", 100.0, 200.0)],
    ),
    (
        "xy_neg_cross_consecutive",
        "XY",
        "positive",
        (-92.5, -116.0),
        (185.0, 232.0),
        [("resize", 100.0, 60.0), ("resize", 150.0, 180.0)],
    ),
    ("xy_neg_grow", "XY", "positive", (-92.5, -116.0), (100.0, 60.0), [("resize", 185.0, 232.0)]),
    ("xy_zero_cross", "XY", "positive", (0.0, 0.0), (185.0, 232.0), [("resize", 100.0, 60.0)]),
    ("xy_positive", "XY", "positive", (60.0, 40.0), (100.0, 60.0), [("resize", 60.0, 40.0)]),
    ("xy_mixed", "XY", "positive", (-92.5, 40.0), (100.0, 60.0), [("resize", 50.0, 30.0)]),
    ("xz_neg_cross", "XZ", "positive", (-92.5, -116.0), (185.0, 232.0), [("resize", 100.0, 60.0)]),
    ("yz_neg_cross", "YZ", "positive", (-92.5, -116.0), (185.0, 232.0), [("resize", 100.0, 60.0)]),
    (
        "xy_neg_negative_direction",
        "XY",
        "negative",
        (-92.5, -116.0),
        (185.0, 232.0),
        [("resize", 100.0, 60.0)],
    ),
    (
        "xy_neg_same_plan",
        "XY",
        "positive",
        (-92.5, -116.0),
        (185.0, 232.0),
        [("resize_same_plan", 100.0, 60.0)],
    ),
    (
        "xy_neg_save_reload",
        "XY",
        "positive",
        (-92.5, -116.0),
        (185.0, 232.0),
        [("save_then_resize", 100.0, 60.0)],
    ),
)


# --- expectations -----------------------------------------------------------


def expected_bbox(plane: str, direction: str, origin, length: float, width: float):
    """The signed box the native frame documents for each named plane."""
    u0, v0 = origin
    if plane == "XY":
        low = (u0, v0, -THICKNESS if direction == "negative" else 0.0)
        high = (u0 + length, v0 + width, 0.0 if direction == "negative" else THICKNESS)
    elif plane == "XZ":
        low = (u0, -THICKNESS if direction == "positive" else 0.0, v0)
        high = (u0 + length, 0.0 if direction == "positive" else THICKNESS, v0 + width)
    else:  # YZ
        low = (-THICKNESS if direction == "negative" else 0.0, u0, v0)
        high = (0.0 if direction == "negative" else THICKNESS, u0 + length, v0 + width)
    return [list(low), list(high)]


def expected_envelope(plane: str, direction: str, origin, length: float, width: float):
    """The signed frame envelope; the recorded frame origin is the sketch frame
    origin (world zero for the named planes), so the rectangle offset shows."""
    u0, v0 = origin
    return {
        "u": [u0, u0 + length],
        "v": [v0, v0 + width],
        "n": [-THICKNESS, 0.0] if direction == "negative" else [0.0, THICKNESS],
    }


def wall_operation(plane, direction, origin, length, width) -> dict:
    return {
        "op": "sheetmetal_planar_wall",
        "label": "base",
        "plane": plane,
        "length": length,
        "width": width,
        "thickness": THICKNESS,
        "direction": direction,
        "origin": list(origin),
    }


def resize_operation(length, width) -> dict:
    return {
        "op": "resize_sheetmetal_planar_wall",
        "feature": "base",
        "length": length,
        "width": width,
    }


def close(left: float, right: float, tolerance: float = 0.01) -> bool:
    return abs(float(left) - float(right)) <= tolerance


def bbox_matches(measured, expected) -> bool:
    if not measured or len(measured) != 2:
        return False
    return all(
        close(a, b) for point, target in zip(measured, expected) for a, b in zip(point, target)
    )


def envelope_matches(measured: dict, expected: dict) -> bool:
    if not isinstance(measured, dict):
        return False
    return all(
        close(measured.get(axis, {}).get(edge, 1e18), expected[axis][index])
        for axis in ("u", "v", "n")
        for index, edge in enumerate(("min", "max"))
    )


# --- offline ----------------------------------------------------------------


def offline_checks() -> dict:
    rows = []
    for name, plane, direction, origin, (length, width), steps in CASES:
        operations = [wall_operation(plane, direction, origin, length, width)]
        validate_operations(operations)
        for kind, step_length, step_width in steps:
            if kind != "reload_resize":
                validate_operations([resize_operation(step_length, step_width)])
        target_length, target_width = steps[-1][1], steps[-1][2]
        rows.append(
            {
                "case": name,
                "plane": plane,
                "expected_bbox_mm": expected_bbox(
                    plane, direction, origin, target_length, target_width
                ),
                "expected_envelope_mm": expected_envelope(
                    plane, direction, origin, target_length, target_width
                ),
                "expected_volume_mm3": target_length * target_width * THICKNESS,
            }
        )
    # The reported failure: 100 x (116 + 56) is what an unsigned corner on the
    # wrong side produces; the crossing case must expect 100 x 60 instead.
    repro = next(row for row in rows if row["case"] == "xy_neg_cross")
    assert close(repro["expected_volume_mm3"], 6000.0), repro
    assert repro["expected_bbox_mm"][0][1] == -116.0, repro
    assert repro["expected_bbox_mm"][1][1] == -56.0, repro
    assert not close(100.0 * (116.0 + 56.0), repro["expected_volume_mm3"]), repro
    return {
        "cases": rows,
        "crossing_case_is_100x60_not_100x172": True,
        "case_count": len(rows),
    }


# --- live -------------------------------------------------------------------


def wait(job_id: str, timeout: float = BUDGET_SECONDS) -> dict:
    deadline = time.time() + timeout
    record: dict = {}
    while time.time() < deadline:
        path = ROOT / "jobs" / job_id / "job.json"
        if path.is_file():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") in TERMINAL:
                return record
        time.sleep(1.0)
    raise RuntimeError(f"job {job_id} never reached a terminal state: {record.get('status')}")


def inspection_of(job_id: str) -> dict:
    for path in sorted((ROOT / "jobs" / job_id).glob("inspection-verified-*.json")):
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def measured_bbox(state: dict):
    low = high = None
    for body in state.get("bodies") or []:
        box = body.get("bbox") if isinstance(body, dict) else None
        if not isinstance(box, list) or len(box) != 2:
            continue
        if low is None:
            low, high = list(box[0]), list(box[1])
            continue
        low = [min(a, b) for a, b in zip(low, box[0])]
        high = [max(a, b) for a, b in zip(high, box[1])]
    return [low, high] if low else None


def operation_detail(job: dict, op: str) -> dict:
    for item in (job.get("result") or {}).get("operations") or []:
        if isinstance(item, dict) and item.get("op") == op:
            return item
    return {}


def saved_and_reloaded(job: dict):
    return (job.get("result") or {}).get("saved_file_reloaded_and_verified")


class Session:
    """Serial submissions on the single Toolkit channel."""

    def __init__(self) -> None:
        import generic_bridge

        self.bridge = generic_bridge
        self.calls: list[dict] = []

    def submit(
        self, operations: list[dict], model_id: str | None = None, model_name: str | None = None
    ) -> tuple[str, dict]:
        if model_id is None:
            submitted = self.bridge.submit(
                operations,
                model_name=model_name,
                model_type="sheetmetal",
                template_name="mmns_part_sheetmetal_abs.prt",
            )
        else:
            revision = self.bridge.model_info(model_id).get("revision")
            submitted = self.bridge.submit(
                operations, model_id=model_id, expected_revision=revision
            )
        terminal = wait(submitted["job_id"])
        self.calls.append({"job_id": submitted["job_id"], "status": terminal.get("status")})
        return submitted["job_id"], terminal

    def save_and_reload(self, model_id: str) -> tuple[str, dict]:
        """Native save: regenerate, save a new version, reload it and verify."""
        return self.submit([{"op": "save"}], model_id=model_id)


def run_case(session: Session, case) -> dict:
    name, plane, direction, origin, (length, width), steps = case
    entry: dict = {
        "case": name,
        "plane": plane,
        "direction": direction,
        "origin": list(origin),
        "steps": [],
    }
    model_name = unique_name(f"h01_{name[:14]}")
    create_plan = [wall_operation(plane, direction, origin, length, width)]
    same_plan = [step for step in steps if step[0] == "resize_same_plan"]
    if same_plan:
        create_plan.extend(resize_operation(step[1], step[2]) for step in same_plan)

    job_id, terminal = session.submit(create_plan, model_name=model_name)
    model_id = terminal.get("model_id")
    create_detail = operation_detail(terminal, "sheetmetal_planar_wall")
    entry["steps"].append(
        {
            "step": "create",
            "model_id": model_id,
            "job_id": job_id,
            "status": terminal.get("status"),
            "message": terminal.get("message"),
            "revision": terminal.get("revision"),
            "saved_file_reloaded_and_verified": saved_and_reloaded(terminal),
            "volume_mm3": create_detail.get("volume_mm3"),
            "feature_id": create_detail.get("feature_id"),
        }
    )
    if terminal.get("status") != "succeeded" or not model_id:
        entry["passed"] = False
        entry["failure"] = "the wall was not created"
        return entry
    feature_id = create_detail.get("feature_id")
    entry["model_id"] = model_id
    entry["feature_id"] = feature_id

    runs: list[tuple[str, float, float, str, dict]] = [
        ("resize_same_plan", step[1], step[2], job_id, terminal) for step in same_plan
    ]
    target_model = model_id
    for kind, step_length, step_width in steps:
        if kind == "resize_same_plan":
            continue
        if kind == "save_then_resize":
            save_job, save_terminal = session.save_and_reload(target_model)
            entry["steps"].append(
                {
                    "step": "save_reload",
                    "job_id": save_job,
                    "status": save_terminal.get("status"),
                    "message": save_terminal.get("message"),
                    "revision": save_terminal.get("revision"),
                    "saved_file_reloaded_and_verified": saved_and_reloaded(save_terminal),
                }
            )
        step_job, step_terminal = session.submit(
            [resize_operation(step_length, step_width)], model_id=target_model
        )
        runs.append((kind, step_length, step_width, step_job, step_terminal))

    for kind, step_length, step_width, step_job, step_terminal in runs:
        state = inspection_of(step_job)
        detail = operation_detail(step_terminal, "resize_sheetmetal_planar_wall")
        entry["steps"].append(
            {
                "step": kind,
                "job_id": step_job,
                "status": step_terminal.get("status"),
                "message": step_terminal.get("message"),
                "revision": step_terminal.get("revision"),
                "saved_file_reloaded_and_verified": saved_and_reloaded(step_terminal),
                "volume_mm3": state.get("volume_mm3"),
                "bbox_mm": measured_bbox(state),
                "planar_wall": projection(detail),
            }
        )

    if not runs:
        entry["passed"] = False
        entry["failure"] = "the case carries no resize step"
        return entry
    last = entry["steps"][-1]
    final_length, final_width = runs[-1][1], runs[-1][2]
    expected_volume = final_length * final_width * THICKNESS
    bbox = expected_bbox(plane, direction, origin, final_length, final_width)
    envelope = expected_envelope(plane, direction, origin, final_length, final_width)
    entry["expected"] = {
        "volume_mm3": expected_volume,
        "bbox_mm": bbox,
        "envelope_mm": envelope,
        "feature_id": feature_id,
    }
    planar = last.get("planar_wall") or {}
    entry["assertions"] = {
        "resize_succeeded": last.get("status") == "succeeded",
        "volume_matches": last.get("volume_mm3") is not None
        and close(last["volume_mm3"], expected_volume),
        "bbox_matches": bbox_matches(last.get("bbox_mm"), bbox),
        "envelope_matches": envelope_matches(planar.get("envelope"), envelope),
        "feature_id_kept": planar.get("feature_id") == feature_id
        and planar.get("feature_id_before") == feature_id,
        "origin_kept": planar.get("origin") == [origin[0], origin[1]],
        "thickness_kept": planar.get("thickness") == THICKNESS,
        "saved_and_reloaded": last.get("saved_file_reloaded_and_verified") is True,
        # A same-plan create+resize is one job, so its revision is the creating
        # revision; the comparison baseline is then the empty model (0).
        "revision_advanced": isinstance(last.get("revision"), int)
        and last["revision"] > (0 if same_plan else entry["steps"][0].get("revision", 0)),
    }
    entry["passed"] = all(entry["assertions"].values())
    return entry


def projection(detail: dict) -> dict:
    if not detail:
        return {}
    keys = (
        "feature_id",
        "feature_id_before",
        "origin",
        "length",
        "width",
        "thickness",
        "volume_mm3",
        "envelope",
        "bounds_mm",
        "dimension_count",
        "verified",
        "thickness_measured_mm",
        "thickness_verified",
    )
    return {key: detail.get(key) for key in keys}


def source_identity() -> dict:
    files = (
        "native/planar_wall.cpp",
        "native/planar_wall.h",
        "native/generic.cpp",
        "src/creo_mechdog/native_planar_wall.py",
        "tools/test_planar_wall_origin_resize.py",
    )
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in files
        if (ROOT / name).is_file()
    }
    worker = ROOT / "build" / "creo_worker.exe"
    return {
        "source_sha256": hashes,
        "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest()
        if worker.is_file()
        else None,
    }


def live(output: Path, run_id: str, only: tuple[str, ...]) -> int:
    session = Session()
    report = {
        "task": "FEAT-058/H01 origin resize matrix",
        "run_id": run_id,
        "mode": "live",
        "started_at": time.time(),
        "source": source_identity(),
        "cases": [],
    }
    selected = [case for case in CASES if not only or case[0] in only]
    for case in selected:
        try:
            entry = run_case(session, case)
        except Exception as error:  # noqa: BLE001 - a busy channel or refusal ends the run
            # The channel is shared with every other client: a busy rejection,
            # an unknown state or a refusal means no further submission in this
            # session. Accepted jobs are never resubmitted.
            report["stopped"] = f"{type(error).__name__}: {error}"[:600]
            report["stopped_at_case"] = case[0]
            report.setdefault("not_run", []).extend(
                remaining[0] for remaining in selected[selected.index(case) + 1 :]
            )
            break
        report["cases"].append(entry)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"{case[0]}: {'PASS' if entry.get('passed') else 'FAIL'} "
            f"{json.dumps(entry.get('assertions', {}))}"
        )
    report["calls"] = session.calls
    report["finished_at"] = time.time()
    report["passed"] = (
        not report.get("stopped")
        and len(report["cases"]) == len(selected)
        and all(entry.get("passed") for entry in report["cases"])
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name("report.sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report {output}")
    print(f"report_sha256 {digest}")
    print(f"passed {report['passed']}")
    return 0 if report["passed"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--case", action="append", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.live and not args.confirm_session_usable:
        print("live runs require --confirm-session-usable", file=sys.stderr)
        return 2
    run_id = f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    if args.live:
        try:
            require_manual_start(ROOT / "config.json")
        except (ValueError, OSError) as error:
            print(f"LIVE_REFUSED: {error}", file=sys.stderr)
            return 2
        output = (
            args.output or ROOT / "build" / "planar_wall_origin_resize" / run_id / "report.json"
        )
        if output.exists():
            print(f"refusing to overwrite {output}", file=sys.stderr)
            return 2
        return live(output, run_id, tuple(args.case or ()))
    report = {
        "task": "FEAT-058/H01 origin resize matrix",
        "run_id": run_id,
        "mode": "offline",
        "native_acceptance": "not_run",
        "checks": offline_checks(),
        "not_verified": [
            "no model was created offline; every volume/bbox claim needs --live",
        ],
    }
    output = args.output or ROOT / "build" / "planar_wall_origin_resize" / run_id / "offline.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
