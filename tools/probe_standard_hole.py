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

HOLE_OP = {
    "op": "hole",
    "label": "h_m6_std",
    "placement": {"kind": "surface", "id": 1},
    "reference1": {"kind": "datum_plane", "id": 2},
    "reference2": {"kind": "datum_plane", "id": 3},
    "diameter": 6.0,
    "depth": 20.0,
    "standard": {"series": "ISO", "size": "M6", "thread_depth": 10.0},
}


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
    accepted = generic_bridge.submit([dict(HOLE_OP)], model_id=model_id, expected_revision=revision)
    hole = wait(accepted["job_id"])
    report["hole_job_id"] = accepted["job_id"]
    report["hole"] = hole

    target = ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": hole.get("status"),
                "model_id": model_id,
                "revision": hole.get("revision"),
                "report": str(target),
            },
            ensure_ascii=False,
        )
    )
    return 0 if hole.get("status") == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
