"""FEAT-035 A03 live probe: does a standard M6 hole really carry the thread?

Creates an isolated 50x50x10 plate, adds one M6 standard hole, then prints the
hole receipt and the extracted feature tree so the thread elements can be read
back. The Python gate is bypassed only inside this process (monkeypatched), so
the committed code keeps refusing until the probe result is accepted.

Usage: python tools/probe_standard_hole.py --confirm-session-usable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import creo_mechdog.schema as schema  # noqa: E402

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

HOLE_TEMPLATE = {
    "op": "hole",
    "label": "h_m6_std",
    "diameter": 6.0,
    "depth": 8.0,
    "standard": {
        "series": "ISO",
        "size": "M6",
        "fastener_id": "M6x1",
        "tap_drill_mm": 5.0,
        "thread_depth": 6.0,
    },
}

PLATE_TOP_Z = 10.0


def _axis_of(normal: object) -> str | None:
    """Name of the principal axis a plane normal runs along, else None."""
    if not isinstance(normal, list) or len(normal) != 3:
        return None
    for name, index in (("x", 0), ("y", 1), ("z", 2)):
        if abs(abs(normal[index]) - 1.0) < 1e-6 and all(
            abs(normal[other]) < 1e-6 for other in range(3) if other != index
        ):
            return name
    return None


def pick_geometry(inspection: dict) -> dict:
    """Real ids for the plate top face and the two locating datum planes.

    Hard-coded ids are invalid in a fresh model (-23 PRO_TK_NOT_EXIST), so the
    hole references come from the plate's own inspection artifact.
    """
    surfaces = [item for item in (inspection.get("surfaces") or []) if isinstance(item, dict)]
    datum_planes = [
        item for item in (inspection.get("datum_planes") or []) if isinstance(item, dict)
    ]
    top = [
        item
        for item in surfaces
        if _axis_of(item.get("normal")) == "z"
        and isinstance(item.get("origin"), list)
        and abs(item["origin"][2] - PLATE_TOP_Z) < 1e-6
    ]
    datum_x = [item for item in datum_planes if _axis_of(item.get("normal")) == "x"]
    datum_y = [item for item in datum_planes if _axis_of(item.get("normal")) == "y"]
    return {
        "top_face_id": top[0].get("id") if top else None,
        "datum_x_id": datum_x[0].get("id") if datum_x else None,
        "datum_y_id": datum_y[0].get("id") if datum_y else None,
        "surface_count": len(surfaces),
        "datum_plane_count": len(datum_planes),
    }


def hole_op(geometry: dict) -> dict:
    """M6 standard hole centred on the plate top face, 25 mm from both datums."""
    operation = dict(HOLE_TEMPLATE)
    operation.update(
        {
            "placement": {"kind": "surface", "id": geometry["top_face_id"]},
            "reference1": {"kind": "datum_plane", "id": geometry["datum_x_id"]},
            "reference2": {"kind": "datum_plane", "id": geometry["datum_y_id"]},
            "offset1": 25.0,
            "offset2": 25.0,
        }
    )
    return operation


def load_inspection(record: dict) -> dict:
    """Read the verified inspection artifact of a terminal job."""
    ref = (record.get("result") or {}).get("inspection_ref") or {}
    path = ref.get("file") if isinstance(ref, dict) else None
    if not path:
        raise SystemExit(f"job {record.get('job_id')} has no inspection artifact")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", default="build/probe_standard_hole.json")
    args = parser.parse_args()
    if not args.confirm_session_usable:
        raise SystemExit("pass --confirm-session-usable after checking the live session")

    # Probe-only bypass: the wheel is not opened for callers.
    schema.require_native_support = lambda: None

    import generic_bridge  # noqa: E402

    def wait(job_id: str, timeout: float = 300.0) -> dict:
        """Poll the accepted job; never resubmit while it is pending."""
        import time

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

    report: dict = {}
    run_name = "bp_plate_a03_" + str(int(__import__("time").time()))
    created = generic_bridge.submit(PLATE_PLAN, model_name=run_name)
    plate_job = wait(created["job_id"])
    report["plate"] = {
        "job_id": created["job_id"],
        "status": plate_job.get("status"),
        "model_id": plate_job.get("model_id"),
        "revision": plate_job.get("revision"),
        "message": plate_job.get("message"),
    }
    if plate_job.get("status") != "succeeded":
        target = ROOT / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report["plate"], ensure_ascii=False))
        return 1

    model_id = plate_job["model_id"]
    revision = plate_job["revision"]
    geometry = pick_geometry(load_inspection(plate_job))
    report["plate"]["geometry"] = geometry
    if not all(geometry[key] for key in ("top_face_id", "datum_x_id", "datum_y_id")):
        target = ROOT / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "no_geometry", "geometry": geometry}, ensure_ascii=False))
        return 1

    operation = hole_op(geometry)
    report["hole_operation"] = operation
    accepted = generic_bridge.submit([operation], model_id=model_id, expected_revision=revision)
    hole = wait(accepted["job_id"])
    report["hole_job_id"] = accepted["job_id"]
    report["hole"] = hole

    result = hole.get("result") or {}
    operations = result.get("operations") or [{}]
    operation_result = operations[0] if isinstance(operations[0], dict) else {}
    report["hole_outcome"] = {
        "status": hole.get("status"),
        "message": hole.get("message"),
        "failed_stage": result.get("failed_stage"),
        "toolkit_code": result.get("toolkit_code"),
        "failed_operation_index": result.get("failed_operation_index"),
        "rollback_succeeded": result.get("rollback_succeeded"),
        "material_removed_mm3": operation_result.get("material_removed_mm3"),
        "depth_basis": operation_result.get("depth_basis"),
        "thread_metadata": operation_result.get("thread_metadata"),
        "saved_file_reloaded_and_verified": result.get("saved_file_reloaded_and_verified"),
    }

    target = ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "geometry": geometry,
                "outcome": report["hole_outcome"],
                "report": str(target),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if hole.get("status") == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
