"""B3/F06 live acceptance: per-operation progress in the compact job view.

The 0.19.0 report measured a 20 op plan at about 8 minutes with a 3.9 MB
``native.log`` and could not tell which operation was running. B3 added
``PROGRESS`` markers to ``native/generic.cpp`` and parsed them into
``creo_get_job(detail="compact").native_progress``.

This driver is the live half of that acceptance:

* submit a 20 op plan (plate + nine through cuts) and sample the compact view
  every ``--sample-seconds`` while it runs;
* check ``operation_index``/``operation_total``/``operation_label``/
  ``operation_state``/``progress_text`` advance monotonically with a fixed
  total, ``log_bytes`` grows and ``truncated`` flips once the log passes the
  8192 B tail;
* check the terminal job still reports ``stage=verified``, an advanced revision
  and the analytic final volume;
* submit a plan whose fourth operation removes no material and check
  ``result.failed_operation_index``, ``rollback_succeeded`` and that every
  earlier operation is ``rolled_back``.

Live runs need a usable Creo session, so ``--live`` and
``--confirm-session-usable`` are both required. Without them the driver reads
nothing and connects to nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
import time
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
PROGRESS_KEYS = (
    "readable",
    "stage",
    "sub_stage",
    "operation_index",
    "operation_total",
    "operation_label",
    "operation_state",
    "progress_text",
    "log_bytes",
    "truncated",
    "log_over_soft_limit",
    "reason",
)
RUN_TAG = time.strftime("%H%M%S")
TAIL_BYTES = 8192
PROGRESS_TEXT = re.compile(r"^(\d+)/(\d+) (sketch|extrude|revolve):(\S+|-) (start|done)$")
REPORT: dict = {"run_tag": RUN_TAG, "checks": {}, "failures": [], "samples": {}, "jobs": {}}


def check(condition, message):
    REPORT["checks"][message] = bool(condition)
    if not condition:
        REPORT["failures"].append(message)
        print(f"  FAILURE: {message}", flush=True)
    return condition


def close(actual, expected, tolerance=0.01):
    return actual is not None and abs(actual - expected) <= tolerance


def plate_and_cuts(holes):
    """Plate (2 ops) plus ``holes`` through cuts (2 ops each)."""
    ops = [
        {
            "op": "sketch",
            "label": "sk_base",
            "plane": "XY",
            "entities": [{"type": "rectangle", "name": "base", "min": [-30, -20], "max": [30, 20]}],
        },
        {
            "op": "extrude",
            "label": "plate",
            "sketch": "sk_base",
            "depth": 10,
            "mode": "add",
            "direction": "positive",
        },
    ]
    grid = [
        (-20, -10),
        (-10, -10),
        (0, -10),
        (10, -10),
        (20, -10),
        (-20, 10),
        (-10, 10),
        (0, 10),
        (10, 10),
    ][:holes]
    for index, (cx, cy) in enumerate(grid, start=1):
        ops.append(
            {
                "op": "sketch",
                "label": f"sk_h{index}",
                "plane": "XY",
                "entities": [
                    {"type": "circle", "name": f"h{index}", "center": [cx, cy], "radius": 2}
                ],
            }
        )
        ops.append(
            {
                "op": "extrude",
                "label": f"cut_h{index}",
                "sketch": f"sk_h{index}",
                "mode": "cut",
                "direction": "positive",
                "depth_type": "through_all",
            }
        )
    return ops


def failing_plan():
    """Plate plus a cut outside the material: a real failure at index 3."""
    ops = plate_and_cuts(0)
    ops.extend(
        [
            {
                "op": "sketch",
                "label": "sk_far",
                "plane": "XY",
                "entities": [{"type": "circle", "name": "far", "center": [500, 500], "radius": 2}],
            },
            {
                "op": "extrude",
                "label": "cut_far",
                "sketch": "sk_far",
                "mode": "cut",
                "direction": "positive",
                "depth": 10,
            },
        ]
    )
    return ops


async def call(client, name, args):
    result = await client.call_tool(name, args)
    if result.is_error:
        raise RuntimeError(f"{name}: {result.content}")
    return result.structured_content


async def wait_ready(client):
    for _ in range(120):
        status = await call(client, "creo_startup_status", {})
        if status.get("state") == "ready" and status.get("connected"):
            return True
        await asyncio.sleep(3)
    return False


async def new_model(client, name):
    created = await call(client, "creo_new_part", {"model_name": name})
    for _ in range(240):
        state = await call(
            client, "creo_get_job", {"job_id": created["job_id"], "detail": "compact"}
        )
        if state["status"] not in ("queued", "running"):
            break
        await asyncio.sleep(1)
    return state["model_id"], state.get("revision"), state.get("status")


async def run_plan(client, model_id, revision, operations, sample_seconds):
    submitted = await call(
        client,
        "creo_execute_plan",
        {"model_id": model_id, "expected_revision": revision, "operations": operations},
    )
    job_id = submitted["job_id"]
    samples = []
    final = None
    for _ in range(900):
        state = await call(client, "creo_get_job", {"job_id": job_id, "detail": "compact"})
        progress = state.get("native_progress") or {}
        snapshot = {key: progress.get(key) for key in PROGRESS_KEYS}
        if snapshot.get("operation_index") is not None:
            samples.append(snapshot)
        if state["status"] not in ("queued", "running"):
            final = state
            break
        await asyncio.sleep(sample_seconds)
    return job_id, samples, final


def check_samples(name, samples, expected_total):
    minimum = 3 if expected_total >= 10 else 2
    check(
        len(samples) >= minimum,
        f"{name}: at least {minimum} compact samples carried progress",
    )
    if not samples:
        return
    check(
        all(item["operation_total"] == expected_total for item in samples),
        f"{name}: operation_total stays {expected_total}",
    )
    indices = [item["operation_index"] for item in samples]
    check(indices[0] == 1, f"{name}: progress starts at operation 1")
    check(indices == sorted(indices), f"{name}: operation_index never goes backwards")
    check(
        all(PROGRESS_TEXT.match(item["progress_text"] or "") for item in samples),
        f"{name}: progress_text is index/total op:label state",
    )
    check(
        {item["operation_state"] for item in samples} <= {"start", "done"},
        f"{name}: operation_state is start or done",
    )
    check(
        all(item["readable"] for item in samples),
        f"{name}: every sample reads native.log",
    )
    check(
        samples[-1]["log_bytes"] >= samples[0]["log_bytes"],
        f"{name}: log_bytes does not shrink between samples",
    )
    check(
        {item["truncated"] for item in samples} == {False, True}
        if max(item["log_bytes"] for item in samples) > TAIL_BYTES
        else True,
        f"{name}: truncated flips once the log passes the {TAIL_BYTES} B tail",
    )
    check(
        max(indices) == expected_total,
        f"{name}: progress reaches the final operation",
    )


async def main_async(args):
    if not (args.live and args.confirm_session_usable):
        print("refused: pass --live --confirm-session-usable to touch the session")
        return 2
    params = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT)
    )
    async with Client(params) as client:
        if not await wait_ready(client):
            print("refused: session never became ready; see creo_startup_status")
            return 2
        operations = plate_and_cuts(args.holes)
        model_id, revision, status = await new_model(client, f"b3_progress_{RUN_TAG}")
        check(status == "succeeded", "model creation succeeded before the plan")
        job_id, samples, final = await run_plan(
            client, model_id, revision, operations, args.sample_seconds
        )
        REPORT["jobs"]["plan"] = job_id
        REPORT["samples"]["plan"] = samples
        REPORT["plan_operations"] = len(operations)
        check_samples("plan", samples, len(operations))
        check(final is not None and final["status"] == "succeeded", "20 op plan succeeded")
        if final:
            check(final.get("stage") == "verified", "20 op plan ends at stage=verified")
            check(
                final.get("revision") is not None and final["revision"] > revision,
                "20 op plan advanced the revision",
            )
        inspected = await call(
            client, "creo_inspect_model", {"model_id": model_id, "detail": "compact"}
        )
        volume = (inspected.get("inspection") or {}).get("volume_mm3")
        expected = 24000 - args.holes * math.pi * 4 * 10
        REPORT["plan_volume_mm3"] = volume
        REPORT["plan_expected_volume_mm3"] = expected
        check(close(volume, expected), "20 op plan volume matches the analytic value")

        model2, revision2, status2 = await new_model(client, f"b3_progress_fail_{RUN_TAG}")
        check(status2 == "succeeded", "second model creation succeeded")
        job2, samples2, final2 = await run_plan(
            client, model2, revision2, failing_plan(), args.sample_seconds
        )
        REPORT["jobs"]["failing"] = job2
        REPORT["samples"]["failing"] = samples2
        check_samples("failing", samples2, 4)
        check(final2 is not None and final2["status"] == "failed", "failure plan failed")
        if final2:
            result = final2.get("result") or {}
            REPORT["failing_result"] = {
                key: result.get(key)
                for key in ("failed_operation_index", "rollback_succeeded", "operations_total")
            }
            check(
                result.get("failed_operation_index") == 3,
                "failing plan reports failed_operation_index=3",
            )
            check(result.get("rollback_succeeded") is True, "failing plan rolled back")
            check(
                final2.get("revision") in (None, revision2),
                "failing plan left the revision unchanged",
            )
            operations_result = result.get("operations") or []
            check(
                all(op.get("effect_status") == "rolled_back" for op in operations_result),
                "every operation of the failing plan is rolled_back",
            )
            check(
                [op.get("index") for op in operations_result] == [0, 1, 2, 3],
                "operation results keep zero-based indexes",
            )
    REPORT["success"] = not REPORT["failures"]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"failures={REPORT['failures']}", flush=True)
    return 0 if not REPORT["failures"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="required: touch the session")
    parser.add_argument(
        "--confirm-session-usable",
        action="store_true",
        help="required: the caller confirmed this session may be used",
    )
    parser.add_argument("--holes", type=int, default=9, help="through cuts (2 ops each)")
    parser.add_argument("--sample-seconds", type=float, default=1.0)
    parser.add_argument("--output", default="build/job_progress_live.json")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
