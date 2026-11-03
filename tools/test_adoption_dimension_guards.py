"""FEAT-004 / A02 acceptance driver: dimension guards against stale observations.

Default run is offline: it exercises the shared judgement
(`check_dimension_guard`) on the four pinned attributes and the tolerance
boundary, so the case table keeps its meaning without Creo. ``--live`` creates a
50x30x10 block, reads the real dimension ids/symbols/owners, and records what the
native executor does for a matching pin, a stale pin, a wrong owner/symbol, a
relation-driven dimension, a batch whose second entry is stale, and a legacy
payload without pins.

Usage:
  python tools/test_adoption_dimension_guards.py
  python tools/test_adoption_dimension_guards.py --live --confirm-session-usable
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

from creo_mechdog.dimension_guards import (  # noqa: E402
    check_dimension_guard,
    has_guard,
    value_tolerance,
)

PLAN = [
    {
        "op": "sketch",
        "label": "dim_sketch",
        "plane": "XY",
        "entities": [
            {"type": "rectangle", "name": "dimblk", "min": [0.0, 0.0], "max": [50.0, 30.0]}
        ],
    },
    {
        "op": "extrude",
        "label": "dimblk",
        "sketch": "dim_sketch",
        "depth": 10.0,
        "mode": "add",
        "direction": "positive",
        "depth_type": "blind",
    },
]

CURRENT = {
    "id": 9,
    "symbol": "d9",
    "value": 10.0,
    "relation_driven": False,
    "owner_feature_id": 40,
    "owner_feature_name": "DIMBLK",
}


def offline_checks() -> list[dict]:
    """Judgement-only cases: no Creo, no payload submission."""
    cases: list[dict] = []

    def outcome(name: str, requested: dict, expected: str | None) -> None:
        try:
            check_dimension_guard(CURRENT, requested)
        except ValueError as error:
            cases.append(
                {
                    "case": name,
                    "kind": "offline_guard",
                    "expected": expected,
                    "observed": str(error),
                    "pass": expected is not None and expected in str(error),
                }
            )
        else:
            cases.append(
                {
                    "case": name,
                    "kind": "offline_guard",
                    "expected": expected,
                    "observed": "allowed",
                    "pass": expected is None,
                }
            )

    outcome("matching_pins", {"id": 9, "expected_value": 10.0, "expected_symbol": "d9"}, None)
    outcome(
        "stale_value",
        {"id": 9, "expected_value": 10.0 + 100 * value_tolerance(10.0)},
        "guard failed on value",
    )
    outcome("wrong_symbol", {"id": 9, "expected_symbol": "d0"}, "guard failed on symbol")
    outcome("wrong_owner", {"id": 9, "expected_owner": "OTHER"}, "guard failed on owner")
    outcome("owner_by_id", {"id": 9, "expected_owner": 41}, "guard failed on owner")
    outcome("no_pins_legacy", {"id": 9}, None)

    driven = dict(CURRENT, relation_driven=True)
    try:
        check_dimension_guard(driven, {"id": 9})
    except ValueError as error:
        cases.append(
            {
                "case": "relation_driven",
                "kind": "offline_guard",
                "expected": "controlled by relations",
                "observed": str(error),
                "pass": "controlled by relations" in str(error),
            }
        )
    else:
        cases.append(
            {
                "case": "relation_driven",
                "kind": "offline_guard",
                "expected": "controlled by relations",
                "observed": "allowed",
                "pass": False,
            }
        )

    unknown = dict(CURRENT, value=None)
    try:
        check_dimension_guard(unknown, {"id": 9, "expected_value": 10.0})
    except ValueError as error:
        cases.append(
            {
                "case": "unknown_current_value",
                "kind": "offline_guard",
                "expected": "current value is unknown",
                "observed": str(error),
                "pass": "current value is unknown" in str(error),
            }
        )
    else:
        cases.append(
            {
                "case": "unknown_current_value",
                "kind": "offline_guard",
                "expected": "current value is unknown",
                "observed": "allowed",
                "pass": False,
            }
        )

    cases.append(
        {
            "case": "legacy_payload_has_no_guard",
            "kind": "offline_guard",
            "observed": has_guard({"id": 9, "value": 10}),
            "pass": has_guard({"id": 9, "value": 10}) is False,
        }
    )
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", default="build/acceptance_dimension_guards.json")
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
    except Exception as error:  # keep the evidence even when the fixture breaks
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


def run_live(generic_bridge) -> tuple[list[dict], bool]:
    cases: list[dict] = []
    created = generic_bridge.submit(PLAN, model_name="dim_guard_" + str(int(time.time())))
    job = wait(created["job_id"])
    cases.append(
        {
            "case": "fixture_block",
            "kind": "setup",
            "job_id": created["job_id"],
            "status": job.get("status"),
            "message": job.get("message"),
            "pass": job.get("status") == "succeeded",
        }
    )
    if job.get("status") != "succeeded":
        return cases, False

    model_id = job["model_id"]
    dimensions = read_dimensions(generic_bridge, model_id)
    depth = pick(dimensions, lambda record: record.get("value") == 10.0)
    width = pick(dimensions, lambda record: record.get("value") == 50.0)
    if depth is None or width is None:
        cases.append({"case": "fixture_dimensions", "kind": "setup", "pass": False})
        return cases, False

    def submit(operations: list[dict]) -> dict:
        accepted = generic_bridge.submit(
            operations, model_id=model_id, expected_revision=revision_of(generic_bridge, model_id)
        )
        return wait(accepted["job_id"])

    def guarded(name: str, payload: dict, expected: str | None, observed_value: float) -> None:
        operation = {"op": "set_dimensions", "values": [payload]}
        job = submit([operation])
        message = str(job.get("message") or "")
        after = find_dimension(generic_bridge, model_id, depth["id"])
        value = after.get("value") if after else None
        expected_status = "succeeded" if expected is None else "failed"

        def close(candidate: float | None) -> bool:
            return (
                isinstance(candidate, (int, float))
                and abs(float(candidate) - observed_value) < 1e-6
            )

        checks = {
            "status": job.get("status") == expected_status,
            "saved_reload": (job.get("result") or {}).get("saved_file_reloaded_and_verified")
            is True
            if expected is None
            else True,
            "readback": close(value),
        }
        if expected is not None:
            checks["message"] = expected in message
            checks["rolled_back"] = (job.get("result") or {}).get("rollback_succeeded") is True
        cases.append(
            {
                "case": name,
                "kind": "dimension_guard",
                "job_id": job.get("job_id"),
                "status": job.get("status"),
                "message": message,
                "payload": payload,
                "observed_value": value,
                "checks": checks,
                "pass": all(checks.values()),
            }
        )

    base = {
        "id": depth["id"],
        "symbol": depth.get("symbol"),
        "owner": depth.get("owner_feature_name"),
        "value": depth.get("value"),
    }

    guarded(
        "matching_pin_accepted",
        {
            "id": base["id"],
            "value": 12.0,
            "expected_value": base["value"],
            "expected_symbol": base["symbol"],
            "expected_owner": base["owner"],
        },
        None,
        12.0,
    )
    guarded(
        "stale_value_refused",
        {
            "id": base["id"],
            "value": 13.0,
            "expected_value": base["value"],
            "expected_symbol": base["symbol"],
        },
        "guard failed on value",
        12.0,
    )
    guarded(
        "wrong_owner_refused",
        {
            "id": base["id"],
            "value": 13.0,
            "expected_owner": "NOT_THE_OWNER",
        },
        "guard failed on owner",
        12.0,
    )
    guarded(
        "wrong_symbol_refused",
        {
            "id": base["id"],
            "value": 13.0,
            "expected_symbol": "d0",
        },
        "guard failed on symbol",
        12.0,
    )
    guarded(
        "legacy_payload_accepted",
        {"id": base["id"], "value": 11.0},
        None,
        11.0,
    )

    # Batch: the first entry would succeed, the second pins a stale value, so
    # the whole plan must roll back and leave both dimensions untouched.
    width_value = width.get("value")
    before_width = find_dimension(generic_bridge, model_id, width["id"])
    before_depth = find_dimension(generic_bridge, model_id, depth["id"])
    batch = [
        {
            "op": "set_dimensions",
            "values": [{"id": width["id"], "value": float(width_value) + 5.0}],
        },
        {
            "op": "set_dimensions",
            "values": [
                {
                    "id": depth["id"],
                    "value": 20.0,
                    "expected_value": 10.0,
                }
            ],
        },
    ]
    job = submit(batch)
    after_width = find_dimension(generic_bridge, model_id, width["id"])
    after_depth = find_dimension(generic_bridge, model_id, depth["id"])
    message = str(job.get("message") or "")
    checks = {
        "failed": job.get("status") == "failed",
        "guard_message": "guard failed on value" in message,
        "rolled_back": (job.get("result") or {}).get("rollback_succeeded") is True,
        "width_untouched": same_value(after_width, before_width),
        "depth_untouched": same_value(after_depth, before_depth),
    }
    cases.append(
        {
            "case": "batch_rollback",
            "kind": "dimension_guard",
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "message": message,
            "checks": checks,
            "pass": all(checks.values()),
        }
    )

    # Relation-driven dimension: after a relation owns it, an edit must be refused.
    driven = submit([{"op": "set_relations", "lines": [f"{base['symbol']} = 9"]}])
    relation_record = find_dimension(generic_bridge, model_id, depth["id"])
    guarded_record = relation_record or {}
    edit = submit([{"op": "set_dimensions", "values": [{"id": depth["id"], "value": 14.0}]}])
    edit_message = str(edit.get("message") or "")
    checks = {
        "relation_applied": driven.get("status") == "succeeded"
        and guarded_record.get("relation_driven") is True,
        "edit_failed": edit.get("status") == "failed",
        "relation_message": "controlled by relations" in edit_message,
        "value_kept": same_value(
            find_dimension(generic_bridge, model_id, depth["id"]), relation_record
        ),
    }
    cases.append(
        {
            "case": "relation_driven_refused",
            "kind": "dimension_guard",
            "job_id": edit.get("job_id"),
            "status": edit.get("status"),
            "message": edit_message,
            "observed": {"relation_driven": guarded_record.get("relation_driven")},
            "checks": checks,
            "pass": all(checks.values()),
        }
    )

    editable = submit(
        [
            {
                "op": "set_dimensions",
                "values": [{"id": width["id"], "value": float(width_value) + 1.0}],
            }
        ]
    )
    cases.append(
        {
            "case": "model_still_editable",
            "kind": "recovery",
            "job_id": editable.get("job_id"),
            "status": editable.get("status"),
            "pass": editable.get("status") == "succeeded",
        }
    )
    return cases, all(case["pass"] for case in cases)


def same_value(left: dict | None, right: dict | None) -> bool:
    if not left or not right:
        return False
    return abs(float(left.get("value") or 0.0) - float(right.get("value") or 0.0)) < 1e-6


def pick(dimensions: list[dict], predicate) -> dict | None:
    for record in dimensions:
        if record.get("editable") and predicate(record):
            return record
    return None


def read_dimensions(generic_bridge, model_id: str) -> list[dict]:
    view = generic_bridge.inspect_model(model_id, detail="full", section="dimensions", limit=50)
    return list((view.get("data") or {}).get("dimensions") or [])


def find_dimension(generic_bridge, model_id: str, dimension_id: int) -> dict | None:
    for record in read_dimensions(generic_bridge, model_id):
        if record.get("id") == dimension_id:
            return record
    return None


def revision_of(generic_bridge, model_id: str) -> int:
    return int(generic_bridge.model_info(model_id).get("revision") or 0)


if __name__ == "__main__":
    raise SystemExit(main())
