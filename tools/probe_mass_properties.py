"""FEAT-057 probe: what does the model itself report for mass properties?

Creates a 10x20x30 block, then asks the read-only ``mass_properties`` operation
what Creo reports. The point of the run is to see whether a fresh part carries a
material (and therefore a mass) or only a volume, before any acceptance claim.

Usage:
  python tools/probe_mass_properties.py --confirm-session-usable
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

PLAN = [
    {
        "op": "sketch",
        "label": "mp_sketch",
        "plane": "XY",
        "entities": [
            {
                "type": "rectangle",
                "name": "mpblk",
                "min": [0.0, 0.0],
                "max": [10.0, 20.0],
            }
        ],
    },
    {
        "op": "extrude",
        "label": "mpblk",
        "sketch": "mp_sketch",
        "depth": 30.0,
        "mode": "add",
        "direction": "positive",
        "depth_type": "blind",
    },
]


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
    raise SystemExit(f"job {job_id} never finished: {record.get('status')}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", default="build/probe_mass_properties.json")
    args = parser.parse_args()
    if not args.confirm_session_usable:
        raise SystemExit("pass --confirm-session-usable after checking the live session")

    import generic_bridge

    created = generic_bridge.submit(PLAN, model_name="mp_block_" + str(int(time.time())))
    job = wait(created["job_id"])
    report: dict = {
        "create": {
            "job_id": created["job_id"],
            "status": job.get("status"),
            "message": job.get("message"),
        }
    }
    if job.get("status") != "succeeded":
        write(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    model_id = job["model_id"]
    report["model_id"] = model_id
    for label, operation in (
        ("no_density", {"op": "mass_properties"}),
        ("requested_steel", {"op": "mass_properties", "density_g_cm3": 7.85}),
    ):
        accepted = generic_bridge.submit([operation], model_id=model_id, readonly=True)
        query = wait(accepted["job_id"])
        record = {
            "job_id": accepted["job_id"],
            "status": query.get("status"),
            "message": query.get("message"),
        }
        for entry in (query.get("result") or {}).get("operations") or []:
            if isinstance(entry, dict) and entry.get("mass_properties"):
                record["mass_properties"] = entry["mass_properties"]
        report[label] = record
    write(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["requested_steel"].get("mass_properties") else 1


def write(path: str, report: dict) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
