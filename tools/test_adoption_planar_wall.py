"""FEAT-058 acceptance driver: native rectangular planar wall.

The offline half runs by default and decides everything that does not need Creo:
schema admission, the empty-sheetmetal rule, the feature-identity and
downstream-dependency rules, the square case, and the signed frame envelope
(including the sorted-world-bbox fixture that must be rejected).

The live half (``--live --confirm-session-usable``) builds the accepted shape on
the real session:

  1. create a sheetmetal model from the native sheetmetal template;
  2. create the 100x60x1 planar wall  -> 6000 mm3, feature id recorded;
  3. resize it to 120x80 in place      -> 9600 mm3, same feature id, gauge 1;
  4. run the refusal matrix (part model, non-empty model, unknown label, wall
     made by another operation);
  5. re-run the documented ``examples/sheetmetal_base_yz.json`` recipe on the
     conversion template to prove the previous first-wall contract still holds
     (42920 mm3).

Every verdict is written to ``build/planar_wall/adoption_<mode>.json`` and the
process exits non-zero when any check fails. Nothing here re-derives geometry:
the volume and the frame envelope come from the native result.

Usage:
  python tools/test_adoption_planar_wall.py
  python tools/test_adoption_planar_wall.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

LENGTH = 100.0
WIDTH = 60.0
THICKNESS = 1.0
RESIZED_LENGTH = 120.0
RESIZED_WIDTH = 80.0
SQUARE_SIDE = 60.0
BASE_PLATE_VOLUME_MM3 = 42920.0
SHEETMETAL_TEMPLATE = "mmns_part_sheetmetal_abs.prt"


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


def native_lines(job_id: str, tokens: tuple[str, ...]) -> list[str]:
    log = ROOT / "jobs" / job_id / "native.log"
    if not log.is_file():
        return []
    return [
        line
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
        if any(token in line for token in tokens)
    ][-12:]


def write_report(mode: str, report: dict) -> Path:
    target = ROOT / "build" / "planar_wall" / f"adoption_{mode}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


class Checks:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, name: str, ok: bool, detail: object = None) -> bool:
        self.items.append({"check": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    @property
    def failed(self) -> list[str]:
        return [item["check"] for item in self.items if not item["ok"]]


def model_record(model_type: str, has_solid: bool) -> dict:
    return {
        "model_type": model_type,
        "inspection_summary": {"has_solid": has_solid},
        "aliases": {},
    }


def offline_checks() -> Checks:
    from creo_mechdog import native_planar_wall as pwall
    from creo_mechdog.schema import validate_operations

    checks = Checks()
    create = {
        "op": "sheetmetal_planar_wall",
        "label": "wall",
        "plane": "XY",
        "length": LENGTH,
        "width": WIDTH,
        "thickness": THICKNESS,
    }
    resize = {
        "op": "resize_sheetmetal_planar_wall",
        "feature": "wall",
        "length": RESIZED_LENGTH,
        "width": RESIZED_WIDTH,
    }
    validated = validate_operations([create, resize])
    checks.add(
        "schema admits both operations",
        validated[0]["op"] == "sheetmetal_planar_wall"
        and validated[1]["op"] == "resize_sheetmetal_planar_wall",
    )
    for name, broken in (
        ("zero length refused", dict(create, length=0)),
        ("negative thickness refused", dict(create, thickness=-1)),
        ("over-long label refused", dict(create, label="w" * 26)),
        ("unknown plane refused", dict(create, plane="AB")),
    ):
        try:
            validate_operations([broken])
            checks.add(name, False, "no error raised")
        except Exception as error:  # noqa: BLE001 - the refusal is the evidence
            checks.add(name, True, str(error).splitlines()[0][:160])

    empty = model_record("sheetmetal", False)
    checks.add("create admitted on empty sheetmetal", pwall.create_problem(empty) is None)
    checks.add(
        "create refused on a part model",
        "sheetmetal" in (pwall.create_problem(model_record("part", False)) or ""),
    )
    checks.add(
        "create refused on a non-empty sheetmetal model",
        "already has geometry" in (pwall.create_problem(model_record("sheetmetal", True)) or ""),
    )

    aliases = {"wall": {"op": "sheetmetal_planar_wall", "feature_id": 49}}
    checks.add(
        "resize admitted for a planar wall", pwall.resize_problem(empty, resize, aliases) is None
    )
    checks.add(
        "resize refused for an unknown label",
        "Unknown" in (pwall.resize_problem(empty, resize, {}) or ""),
    )
    checks.add(
        "resize refused for a wall made by another operation",
        "only walls created by"
        in (
            pwall.resize_problem(
                empty, resize, {"wall": {"op": "sheetmetal_wall", "feature_id": 47}}
            )
            or ""
        ),
    )
    features = [{"id": 49, "child_ids": [52]}]
    checks.add(
        "resize refused with a downstream dependency",
        "downstream dependencies" in (pwall.resize_problem(empty, resize, aliases, features) or ""),
    )

    created = {
        "op": "sheetmetal_planar_wall",
        "feature": "wall",
        "feature_id": 49,
        "sketch": "wall_sk",
        "length": LENGTH,
        "width": WIDTH,
        "thickness": THICKNESS,
        "dimension_count": 8,
        "volume_mm3": LENGTH * WIDTH * THICKNESS,
        "frame": {
            "origin": [0.0, 0.0, 0.0],
            "u_axis": [1.0, 0.0, 0.0],
            "v_axis": [0.0, 1.0, 0.0],
            "normal": [0.0, 0.0, 1.0],
        },
        "envelope": {
            "u": {"min": 0.0, "max": LENGTH},
            "v": {"min": 0.0, "max": WIDTH},
            "n": {"min": 0.0, "max": THICKNESS},
        },
    }
    projection = pwall.result_projection(created)
    checks.add("created wall projection verified", projection["verified"], projection["problems"])
    checks.add("created perimeter covers four dimensions", projection["dimension_count"] >= 4)

    square = pwall.result_projection(
        dict(
            created,
            length=60.0,
            width=60.0,
            envelope={
                "u": {"min": 0.0, "max": 60.0},
                "v": {"min": 0.0, "max": 60.0},
                "n": {"min": 0.0, "max": THICKNESS},
            },
        )
    )
    checks.add(
        "square reported with both axes",
        square["square"] is True and square["verified"] and square["dimension_count"] >= 4,
        square["problems"],
    )
    under = pwall.result_projection(dict(created, dimension_count=1))
    checks.add("single-dimension square refused", not under["verified"], under["problems"])

    rotated = {
        "origin": [0.0, 0.0, 0.0],
        "u_axis": [0.0, 1.0, 0.0],
        "v_axis": [-1.0, 0.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
    }
    extents = pwall.signed_extents(rotated, [[-WIDTH, 0.0, 0.0], [0.0, LENGTH, THICKNESS]])
    checks.add(
        "signed envelope keeps u/v in frame axes",
        abs(extents["u"]["max"] - LENGTH) < 1e-9 and abs(extents["v"]["max"] - WIDTH) < 1e-9,
        extents,
    )
    sorted_box = {
        "u": {"min": 0.0, "max": WIDTH},
        "v": {"min": 0.0, "max": LENGTH},
        "n": {"min": 0.0, "max": THICKNESS},
    }
    checks.add(
        "sorted world bbox rejected",
        pwall.envelope_problem(rotated, sorted_box, LENGTH, WIDTH, THICKNESS) is not None,
    )

    resized = pwall.result_projection(
        dict(
            created,
            op="resize_sheetmetal_planar_wall",
            length=RESIZED_LENGTH,
            width=RESIZED_WIDTH,
            volume_mm3=RESIZED_LENGTH * RESIZED_WIDTH * THICKNESS,
            feature_id_before=49,
            envelope={
                "u": {"min": 0.0, "max": RESIZED_LENGTH},
                "v": {"min": 0.0, "max": RESIZED_WIDTH},
                "n": {"min": 0.0, "max": THICKNESS},
            },
        )
    )
    checks.add(
        "resize keeps feature identity", resized["feature_id_unchanged"] and resized["verified"]
    )
    rebuilt = pwall.result_projection(
        dict(
            created,
            op="resize_sheetmetal_planar_wall",
            feature_id_before=49,
            feature_id=57,
            length=RESIZED_LENGTH,
            width=RESIZED_WIDTH,
            envelope={
                "u": {"min": 0.0, "max": RESIZED_LENGTH},
                "v": {"min": 0.0, "max": RESIZED_WIDTH},
                "n": {"min": 0.0, "max": THICKNESS},
            },
        )
    )
    checks.add("rebuilt wall detected", not rebuilt["verified"], rebuilt["problems"])
    return checks


def live_checks(report: dict) -> Checks:
    import generic_bridge
    from creo_mechdog import native_planar_wall as pwall
    from creo_mechdog.schema import validate_operations

    checks = Checks()
    stamp = str(int(time.time()))

    setup = generic_bridge.submit(
        [],
        model_name=f"planar_wall_{stamp}",
        model_type="sheetmetal",
        template_name=SHEETMETAL_TEMPLATE,
    )
    setup_job = wait(setup["job_id"])
    summary = (setup_job.get("result") or {}).get("inspection_summary") or {}
    report["setup"] = {
        "job_id": setup["job_id"],
        "status": setup_job.get("status"),
        "message": setup_job.get("message"),
        "model_type": summary.get("model_type"),
        "has_solid": summary.get("has_solid"),
    }
    if not checks.add(
        "empty sheetmetal model created",
        setup_job.get("status") == "succeeded"
        and summary.get("model_type") == "sheetmetal"
        and summary.get("has_solid") is False,
        report["setup"],
    ):
        return checks

    model_id = setup_job["model_id"]
    report["model_id"] = model_id
    revision = generic_bridge.model_info(model_id).get("revision")

    create_op = {
        "op": "sheetmetal_planar_wall",
        "label": "wall",
        "plane": "XY",
        "length": LENGTH,
        "width": WIDTH,
        "thickness": THICKNESS,
        "direction": "positive",
    }
    validate_operations([create_op])
    submit = generic_bridge.submit([create_op], model_id=model_id, expected_revision=revision)
    job = wait(submit["job_id"])
    detail = operation_detail(job, "sheetmetal_planar_wall")
    projection = pwall.result_projection(detail)
    report["create"] = {
        "job_id": submit["job_id"],
        "status": job.get("status"),
        "message": job.get("message"),
        "revision": job.get("revision"),
        "saved_file_reloaded_and_verified": (job.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ),
        "volume_mm3": (job.get("result") or {}).get("inspection_summary", {}).get("volume_mm3"),
        "planar_wall": projection,
        "native_evidence": native_lines(submit["job_id"], ("PLANAR_WALL", "Toolkit call")),
    }
    if not checks.add(
        "native planar wall created", job.get("status") == "succeeded", job.get("message")
    ):
        return checks
    checks.add(
        "created volume is length*width*thickness",
        abs((projection["volume_mm3"] or 0) - LENGTH * WIDTH * THICKNESS) < 0.01,
        projection["volume_mm3"],
    )
    checks.add("created wall verified", projection["verified"], projection["problems"])
    checks.add(
        "created wall carries four+ point dimensions",
        (projection["dimension_count"] or 0) >= 4,
        projection["dimension_count"],
    )
    checks.add(
        "created wall saved, reloaded and verified",
        report["create"]["saved_file_reloaded_and_verified"] is True,
    )
    wall_feature = projection["feature_id"]
    wall_sketch = projection["sketch"]
    report["wall_feature_id"] = wall_feature

    # Refusal matrix on this live model (admission only: no job may be created).
    refusals = {}
    for name, ops, model_override in (
        (
            "create on a non-empty sheetmetal model",
            [dict(create_op, label="wall2")],
            None,
        ),
        (
            "resize unknown label",
            [
                {
                    "op": "resize_sheetmetal_planar_wall",
                    "feature": "no_such_wall",
                    "length": 10.0,
                    "width": 10.0,
                }
            ],
            None,
        ),
        (
            "resize a wall made by another operation",
            [
                {
                    "op": "resize_sheetmetal_planar_wall",
                    "feature": wall_sketch,
                    "length": 10.0,
                    "width": 10.0,
                }
            ],
            None,
        ),
    ):
        revision = generic_bridge.model_info(model_id).get("revision")
        try:
            generic_bridge.submit(ops, model_id=model_id, expected_revision=revision)
            refusals[name] = "NOT REFUSED"
        except ValueError as error:
            refusals[name] = str(error).splitlines()[0][:200]
        except Exception as error:  # noqa: BLE001 - record the real refusal text
            refusals[name] = f"{type(error).__name__}: {error}"[:200]
    checks.add(
        "live refusal matrix",
        all("NOT REFUSED" not in value for value in refusals.values()),
        refusals,
    )
    report["refusals"] = refusals

    resize_op = {
        "op": "resize_sheetmetal_planar_wall",
        "feature": "wall",
        "length": RESIZED_LENGTH,
        "width": RESIZED_WIDTH,
    }
    validate_operations([resize_op])
    revision = generic_bridge.model_info(model_id).get("revision")
    submit = generic_bridge.submit([resize_op], model_id=model_id, expected_revision=revision)
    job = wait(submit["job_id"])
    detail = operation_detail(job, "resize_sheetmetal_planar_wall")
    projection = pwall.result_projection(detail)
    report["resize"] = {
        "job_id": submit["job_id"],
        "status": job.get("status"),
        "message": job.get("message"),
        "revision": job.get("revision"),
        "saved_file_reloaded_and_verified": (job.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ),
        "volume_mm3": (job.get("result") or {}).get("inspection_summary", {}).get("volume_mm3"),
        "planar_wall": projection,
        "native_evidence": native_lines(submit["job_id"], ("PLANAR_WALL", "Toolkit call")),
    }
    if not checks.add(
        "in-place resize succeeded", job.get("status") == "succeeded", job.get("message")
    ):
        return checks
    checks.add(
        "resized volume is length*width*thickness",
        abs((projection["volume_mm3"] or 0) - RESIZED_LENGTH * RESIZED_WIDTH * THICKNESS) < 0.01,
        projection["volume_mm3"],
    )
    checks.add("resize verified", projection["verified"], projection["problems"])
    checks.add(
        "resize kept the wall feature id",
        projection["feature_id"] == wall_feature and projection["feature_id_unchanged"],
        {"before": wall_feature, "after": projection["feature_id"]},
    )
    measured_gauge = (projection["volume_mm3"] or 0) / (RESIZED_LENGTH * RESIZED_WIDTH)
    checks.add(
        "resize kept the 1 mm gauge",
        abs(measured_gauge - THICKNESS) < 1e-6,
        measured_gauge,
    )
    checks.add(
        "resized wall saved, reloaded and verified",
        report["resize"]["saved_file_reloaded_and_verified"] is True,
    )

    # Old contract: the documented conversion-template first wall still builds.
    setup = generic_bridge.submit(
        [], model_name=f"planar_wall_legacy_{stamp}", model_type="sheetmetal"
    )
    legacy_setup = wait(setup["job_id"])
    if checks.add("conversion-template model created", legacy_setup.get("status") == "succeeded"):
        legacy_model = legacy_setup["model_id"]
        example = json.loads(
            (ROOT / "examples" / "sheetmetal_base_yz.json").read_text(encoding="utf-8")
        )
        validate_operations(example["operations"])
        revision = generic_bridge.model_info(legacy_model).get("revision")
        submit = generic_bridge.submit(
            example["operations"], model_id=legacy_model, expected_revision=revision
        )
        job = wait(submit["job_id"])
        volume = (job.get("result") or {}).get("inspection_summary", {}).get("volume_mm3")
        report["legacy_contract"] = {
            "job_id": submit["job_id"],
            "status": job.get("status"),
            "message": job.get("message"),
            "volume_mm3": volume,
            "expected_volume_mm3": BASE_PLATE_VOLUME_MM3,
        }
        checks.add(
            "legacy sheetmetal_wall contract unchanged",
            job.get("status") == "succeeded"
            and isinstance(volume, (int, float))
            and abs(volume - BASE_PLATE_VOLUME_MM3) < 0.01,
            report["legacy_contract"],
        )

    # Square case: a 60x60 wall must keep both axes dimensioned and say it is
    # square instead of collapsing to one extent.
    setup = generic_bridge.submit(
        [],
        model_name=f"planar_wall_square_{stamp}",
        model_type="sheetmetal",
        template_name=SHEETMETAL_TEMPLATE,
    )
    square_setup = wait(setup["job_id"])
    if checks.add("square model created", square_setup.get("status") == "succeeded"):
        square_model = square_setup["model_id"]
        square_op = {
            "op": "sheetmetal_planar_wall",
            "label": "square",
            "plane": "XY",
            "length": SQUARE_SIDE,
            "width": SQUARE_SIDE,
            "thickness": THICKNESS,
        }
        validate_operations([square_op])
        revision = generic_bridge.model_info(square_model).get("revision")
        submit = generic_bridge.submit(
            [square_op], model_id=square_model, expected_revision=revision
        )
        job = wait(submit["job_id"])
        projection = pwall.result_projection(operation_detail(job, "sheetmetal_planar_wall"))
        report["square"] = {
            "job_id": submit["job_id"],
            "status": job.get("status"),
            "message": job.get("message"),
            "volume_mm3": (job.get("result") or {}).get("inspection_summary", {}).get("volume_mm3"),
            "planar_wall": projection,
        }
        checks.add(
            "square wall built with both axes",
            job.get("status") == "succeeded"
            and projection["square"] is True
            and (projection["dimension_count"] or 0) >= 4
            and abs((projection["volume_mm3"] or 0) - SQUARE_SIDE * SQUARE_SIDE * THICKNESS) < 0.01,
            report["square"],
        )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    args = parser.parse_args()
    mode = "live" if args.live else "offline"
    if args.live and not args.confirm_session_usable:
        raise SystemExit("pass --confirm-session-usable after checking the live session")

    report: dict = {
        "work_item": "FEAT-058",
        "mode": mode,
        "expected": {
            "create_volume_mm3": LENGTH * WIDTH * THICKNESS,
            "resize_volume_mm3": RESIZED_LENGTH * RESIZED_WIDTH * THICKNESS,
            "legacy_volume_mm3": BASE_PLATE_VOLUME_MM3,
        },
    }
    checks = offline_checks()
    if args.live:
        try:
            live = live_checks(report)
        except Exception as error:  # noqa: BLE001 - a crash is a failed run, not a pass
            report["live_error"] = f"{type(error).__name__}: {error}"
            report["traceback"] = traceback.format_exc()[-2000:]
            live = Checks()
            live.add("live run completed", False, report["live_error"])
        checks.items.extend(live.items)

    report["checks"] = checks.items
    report["failed"] = checks.failed
    report["passed"] = not checks.failed
    target = write_report(mode, report)
    print(
        json.dumps(
            {"report": str(target), "passed": report["passed"], "failed": report["failed"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
