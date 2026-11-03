"""BUG-111 live fixture: rotation range and repeated keep_original copies.

Runs against an already open Creo session through the stdio server:

1. one managed part with one extruded plate;
2. a five-copy batch inside the published -180..180 degree range, which is the
   batch size the external Creo 10 report said starts failing at the fifth copy;
3. a seven-copy batch (the P12 blade count) to see whether the failure position
   is the copy index or the geometry;
4. a single 225 degree request, which must be refused before submission with
   its equivalent angle instead of reaching the kernel;
5. a single -135 degree request, which is the same rotation and must be judged
   by the kernel on its own merits.

The run records whatever happens: a rejection at copy five is a valid result
and the report says so. The point is that each outcome now names the operation,
the backend and the angles. Nothing is asserted about Creo's internals and no
model outside this run is touched.

Usage (after a human confirms the session is operable):
    .venv\\Scripts\\python.exe tools\\test_geometry_transform_copies.py --confirmed-session-usable
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
REPORT = ROOT / "build" / "geometry_transform_copies_report.json"

PLATE = [[0.0, 0.0], [120.0, 0.0], [120.0, 40.0], [0.0, 40.0]]
FIVE = (45.0, 90.0, 135.0, 180.0, -135.0)
SEVEN = (45.0, 90.0, 135.0, 180.0, -135.0, -90.0, -45.0)


def _environment() -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "root": str(ROOT),
    }


def _calls(result: dict) -> list[dict]:
    body = result.get("result")
    if not isinstance(body, dict):
        return []
    operations = body.get("operations")
    return (
        [item for item in operations if isinstance(item, dict)]
        if isinstance(operations, list)
        else []
    )


def _failure(result: dict):
    body = result.get("result")
    if not isinstance(body, dict):
        return None
    return {
        key: body.get(key)
        for key in (
            "failed_operation_index",
            "failed_stage",
            "failed_toolkit_call",
            "failed_transform",
        )
        if key in body
    } or None


async def call(client, name: str, arguments: dict) -> dict:
    response = await client.call_tool(name, arguments)
    if response.is_error:
        raise RuntimeError(f"{name}: {response.content}")
    return response.structured_content


async def rejected(client, name: str, arguments: dict) -> str:
    response = await client.call_tool(name, arguments)
    if not response.is_error:
        raise RuntimeError(f"{name} was expected to be refused before submission")
    return " ".join(block.text for block in response.content if hasattr(block, "text"))


async def run_job(client, name: str, arguments: dict, record: dict) -> dict:
    created = await call(client, name, arguments)
    job_id = created["job_id"]
    print(f"{name} job={job_id} model={created.get('model_id')}", flush=True)
    result = created
    for _ in range(330):
        result = await call(client, "creo_get_job", {"job_id": job_id})
        if result["status"] not in ("queued", "running"):
            break
        await asyncio.sleep(1)
    entry = {
        "tool": name,
        "label": arguments.get("label"),
        "job_id": job_id,
        "status": result["status"],
        "stage": result.get("stage"),
        "message": result.get("message"),
        "rotation_deg": arguments.get("rotation"),
        "keep_original": arguments.get("keep_original"),
        "operations": [
            {
                key: operation.get(key)
                for key in ("index", "execution_status", "effect_status")
                if key in operation
            }
            for operation in _calls(result)
        ],
        "failure": _failure(result),
        "saved_file_reloaded_and_verified": (
            result.get("result", {}).get("saved_file_reloaded_and_verified")
            if isinstance(result.get("result"), dict)
            else None
        ),
    }
    record["calls"].append(entry)
    print(f"  status={result['status']} message={str(result.get('message'))[:160]}", flush=True)
    return result


def _transform(model_id: str, revision: int, label: str, angle: float) -> dict:
    return {
        "model_id": model_id,
        "expected_revision": revision,
        "label": label,
        "references": [{"kind": "body"}],
        "translation": [0, 0, 0],
        "rotation": [0, 0, angle],
        "keep_original": True,
    }


async def scenario(record: dict) -> None:
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT)
    )
    async with Client(parameters) as connected:
        status = await call(connected, "creo_session_status", {})
        record["session"] = {"connected": status.get("connected")}
        assert status["connected"], status
        part = await call(connected, "creo_new_part", {})
        model_id, revision = part["model_id"], part["revision"]
        record["model_id"] = model_id
        sketch = await run_job(
            connected,
            "creo_create_sketch",
            {
                "model_id": model_id,
                "expected_revision": revision,
                "label": "r13_plate_profile",
                "entities": [
                    {
                        "type": "polyline",
                        "name": "r13_plate_outline",
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
        solid = await run_job(
            connected,
            "creo_extrude",
            {
                "model_id": model_id,
                "expected_revision": revision,
                "label": "r13_plate",
                "sketch": "r13_plate_profile",
                "depth": 6,
            },
            record,
        )
        if solid["status"] == "succeeded":
            revision = solid["revision"]

        # 225 degrees is out of range: the refusal must happen before a job exists
        # and must name -135, so the caller never sees a bare kernel -1 for it.
        record["out_of_range_refusal"] = await rejected(
            connected,
            "creo_geometry_transform",
            _transform(model_id, revision, "r13_copy_225", 225.0),
        )
        # The same rotation inside the range.
        single = await run_job(
            connected,
            "creo_geometry_transform",
            _transform(model_id, revision, "r13_copy_neg135", -135.0),
            record,
        )
        if single["status"] == "succeeded":
            revision = single["revision"]
        # A five-op batch: each op is one copy, exactly as the external report ran it.
        batch = {
            "model_id": model_id,
            "expected_revision": revision,
            "operations": [
                {
                    "op": "geometry_transform",
                    "label": f"r13_five_{index}",
                    "references": [{"kind": "body"}],
                    "rotation": [0, 0, angle],
                    "keep_original": True,
                }
                for index, angle in enumerate(FIVE)
            ],
        }
        five = await run_job(connected, "creo_execute_plan", batch, record)
        if five["status"] == "succeeded":
            revision = five["revision"]
        seven = {
            "model_id": model_id,
            "expected_revision": revision,
            "operations": [
                {
                    "op": "geometry_transform",
                    "label": f"r13_seven_{index}",
                    "references": [{"kind": "body"}],
                    "rotation": [0, 0, angle],
                    "keep_original": True,
                }
                for index, angle in enumerate(SEVEN)
            ],
        }
        result = await run_job(connected, "creo_execute_plan", seven, record)
        record["final_revision"] = result.get("revision") or revision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BUG-111 transform rotation/copy fixture")
    parser.add_argument(
        "--confirmed-session-usable",
        action="store_true",
        help="required: a human already confirmed the open Creo session is operable",
    )
    parser.add_argument("--output", default=str(REPORT))
    arguments = parser.parse_args(argv)
    if not arguments.confirmed_session_usable:
        print("live runs require --confirmed-session-usable after human session checks")
        return 2
    output = Path(arguments.output)
    record: dict = {
        "work_item": "BUG-111",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": _environment(),
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
    record["success"] = error is None and all(
        item["status"] in ("succeeded", "failed") for item in record["calls"]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: record[key] for key in ("success", "error") if key in record}, indent=2))
    print(f"report: {output}")
    return 0 if record["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
