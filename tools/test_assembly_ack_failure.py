"""BUG-110 live probe: does a failed assembly have a way out?

Builds a small source part, creates an assembly, then submits an assembly job
that is meant to fail natively (a mate constraint pointing at a surface id that
cannot exist). Two outcomes are both interesting and both are recorded:

* the job rolls back cleanly and the assembly stays ``ready`` -> the zero-change
  rule already covers this case, no acknowledgement is needed;
* the assembly lands in ``failed`` -> the probe inspects it and, when
  ``ack_failure`` is offered, applies it and verifies that the revision, the
  model file and the component bindings are untouched.

Nothing is asserted about Creo's internals. The report states what happened.

Usage (after a human confirmed the session is operable):
    .venv\\Scripts\\python.exe tools\\test_assembly_ack_failure.py --confirmed-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "build" / "assembly_ack_failure_report.json"
PLATE = [[0.0, 0.0], [60.0, 0.0], [60.0, 20.0], [0.0, 20.0]]


async def call(client, name: str, arguments: dict) -> dict:
    response = await client.call_tool(name, arguments)
    if response.is_error:
        raise RuntimeError(f"{name}: {response.content}")
    return response.structured_content


async def job(
    client, name: str, arguments: dict, record: dict, expect_failure: bool = False
) -> dict:
    created = await call(client, name, arguments)
    job_id = created["job_id"]
    result = created
    for _ in range(300):
        result = await call(client, "creo_get_job", {"job_id": job_id})
        if result["status"] not in ("queued", "running"):
            break
        await asyncio.sleep(0.5)
    record["calls"].append(
        {
            "tool": name,
            "job_id": job_id,
            "status": result["status"],
            "stage": result.get("stage"),
            "message": str(result.get("message"))[:400],
            "revision": result.get("revision"),
            "model_unchanged": (result.get("result") or {}).get("model_unchanged"),
            "rollback_status": (result.get("result") or {}).get("rollback_status"),
            "failed_operation_index": (result.get("result") or {}).get("failed_operation_index"),
        }
    )
    print(f"{name} job={job_id} status={result['status']}", flush=True)
    if expect_failure and result["status"] == "succeeded":
        raise RuntimeError(f"{name} was expected to fail but succeeded")
    return result


async def wait_ready(client, record: dict, budget: float = 300.0) -> dict:
    deadline = time.monotonic() + budget
    seen: list[dict] = []
    while time.monotonic() < deadline:
        status = await call(client, "creo_session_status", {})
        if status.get("connected"):
            record["startup_wait"] = seen
            return status
        state = status.get("state") or status.get("connection_state")
        seen.append({"state": state, "message": str(status.get("message"))[:160]})
        if state in ("disabled", "selection_required", "configuration_error"):
            raise RuntimeError(f"session cannot become ready: {state}: {status.get('message')}")
        await asyncio.sleep(3)
    record["startup_wait"] = seen
    raise RuntimeError(f"session did not become connected within {budget:.0f}s")


async def scenario(record: dict) -> None:
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT)
    )
    async with Client(parameters) as connected:
        status = await wait_ready(connected, record)
        record["session"] = {"connected": status.get("connected")}

        suffix = int(time.time()) % 100000
        part = await call(connected, "creo_new_part", {"model_name": f"r13src{suffix}"})
        source_id = part["model_id"]
        source = await job(
            connected,
            "creo_get_job",
            {"job_id": part["job_id"]},
            record,
        )
        revision = source["revision"]
        sketch = await job(
            connected,
            "creo_create_sketch",
            {
                "model_id": source_id,
                "expected_revision": revision,
                "label": "r13_ack_profile",
                "entities": [
                    {
                        "type": "polyline",
                        "name": "r13_ack_outline",
                        "points": PLATE,
                        "closed": True,
                    }
                ],
                "dimensioning": "coordinates",
            },
            record,
        )
        if sketch["status"] == "succeeded":
            revision = sketch["revision"]
        solid = await job(
            connected,
            "creo_extrude",
            {
                "model_id": source_id,
                "expected_revision": revision,
                "label": "r13_ack_plate",
                "sketch": "r13_ack_profile",
                "depth": 5,
            },
            record,
        )
        if solid["status"] == "succeeded":
            revision = solid["revision"]
        surface_ids: list[int] = []
        try:
            surfaces = await call(
                connected, "creo_inspect_model", {"model_id": source_id, "section": "surfaces"}
            )
            listing = surfaces.get("surfaces") or surfaces.get("items") or []
            surface_ids = [
                item.get("id")
                for item in listing
                if isinstance(item, dict) and isinstance(item.get("id"), int)
            ]
            record["source_surface_ids"] = surface_ids[:8]
        except Exception as failure:  # noqa: BLE001 - recorded, the failure is the point
            record["inspect_error"] = str(failure)[:400]
        # A surface id that cannot exist in a fresh assembly is enough to make the
        # native constraint fail; a real component id makes the case more faithful.
        component_surface = surface_ids[0] if surface_ids else 1

        assembly = await call(connected, "creo_new_assembly", {"model_name": f"r13asm{suffix}"})
        assembly_id = assembly["model_id"]
        record["assembly_model_id"] = assembly_id
        built = await job(connected, "creo_get_job", {"job_id": assembly["job_id"]}, record)
        assembly_revision = built["revision"]
        record["revision_before"] = assembly_revision

        # A mate against surface id 999999 cannot exist in a fresh assembly, so the
        # native constraint creation must fail after the job was accepted.
        failed = await job(
            connected,
            "creo_assemble_component",
            {
                "model_id": assembly_id,
                "expected_revision": assembly_revision,
                "label": "r13_ack_pin",
                "source_model_id": source_id,
                "placement": "constraints",
                "constraints": [
                    {
                        "type": "mate",
                        "assembly_reference": {"kind": "surface", "id": 999999},
                        "component_reference": {"kind": "surface", "id": component_surface},
                    }
                ],
            },
            record,
            expect_failure=True,
        )
        record["failed_job_id"] = record["calls"][-1]["job_id"]
        record["failed_job_status"] = failed["status"]

        inspected = await call(connected, "creo_reconcile_model", {"model_id": assembly_id})
        record["inspect_after_failure"] = {
            key: inspected.get(key)
            for key in ("mode", "model_id", "status", "revision", "pending_job", "evidence_token")
        }
        actions = inspected.get("actions")
        record["inspect_actions"] = (
            actions
            if not isinstance(actions, list)
            else [
                {
                    "action": item.get("action"),
                    "available": item.get("available"),
                    "reason": item.get("reason"),
                }
                for item in actions
            ]
        )
        if inspected.get("status") != "failed":
            record["outcome"] = "failure_rollback_left_model_ready"
            record["note"] = (
                "the failed assembly job did not leave the model in failed state; "
                "no acknowledgement was needed, which is the zero-change behaviour this "
                "batch also wanted to confirm"
            )
            # The action still has to exist and stay guarded: on a ready model it
            # must refuse, otherwise the new exit would silently hide real failures.
            try:
                await call(
                    connected,
                    "creo_reconcile_model",
                    {
                        "model_id": assembly_id,
                        "mode": "apply",
                        "action": "ack_failure",
                        "confirm_failure_ack": True,
                        "expected_revision": inspected["revision"],
                        "expected_pending_job_id": inspected.get("pending_job"),
                        "evidence_token": inspected.get("evidence_token"),
                        "idempotency_key": f"r13-ack-guard-{int(time.time())}",
                    },
                )
                record["ack_on_ready"] = "unexpectedly accepted"
            except Exception as failure:  # noqa: BLE001 - the refusal is the expected answer
                record["ack_on_ready"] = str(failure)[:300]
            return

        token = inspected.get("evidence_token")
        acknowledged = await call(
            connected,
            "creo_reconcile_model",
            {
                "model_id": assembly_id,
                "mode": "apply",
                "action": "ack_failure",
                "confirm_failure_ack": True,
                "expected_revision": inspected["revision"],
                "expected_pending_job_id": inspected.get("pending_job"),
                "evidence_token": token,
                "idempotency_key": f"r13-ack-{int(time.time())}",
            },
        )
        record["ack_result"] = {
            key: acknowledged.get(key)
            for key in (
                "mode",
                "action",
                "model_id",
                "status",
                "revision",
                "reconciliation",
                "note",
                "message",
            )
        }
        record["outcome"] = "ack_failure_applied"
        after = await call(connected, "creo_reconcile_model", {"model_id": assembly_id})
        record["inspect_after_ack"] = {
            key: after.get(key) for key in ("status", "revision", "pending_job", "actions")
        }
        components = await call(connected, "creo_list_components", {"model_id": assembly_id})
        record["components_after_ack"] = {
            "count": len(components.get("components") or []),
            "revision": components.get("revision"),
        }
        record["revision_unchanged"] = (
            after.get("revision") == record["revision_before"] == acknowledged.get("revision")
        )


def describe(failure: BaseException) -> str:
    """Flatten nested ExceptionGroups so the report keeps the real cause."""
    if isinstance(failure, BaseExceptionGroup):
        return " | ".join(describe(item) for item in failure.exceptions)
    return f"{type(failure).__name__}: {failure}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BUG-110 assembly ack_failure probe")
    parser.add_argument("--confirmed-session-usable", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    arguments = parser.parse_args(argv)
    if not arguments.confirmed_session_usable:
        print("live runs require --confirmed-session-usable after human session checks")
        return 2
    record: dict = {
        "work_item": "BUG-110",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "calls": [],
        "success": False,
    }
    started = time.monotonic()
    error = None
    try:
        asyncio.run(scenario(record))
    except Exception as failure:  # noqa: BLE001 - the report is the product here
        error = f"{type(failure).__name__}: {failure}"
    record["elapsed_s"] = round(time.monotonic() - started, 1)
    if error:
        record["error"] = error
    record["success"] = error is None
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: record[key] for key in ("success", "outcome", "error") if key in record}, indent=2
        )
    )
    print(f"report: {output}")
    return 0 if record["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
