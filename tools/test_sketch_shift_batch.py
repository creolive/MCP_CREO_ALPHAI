"""BUG-108 live fixture: does a thin oblique profile still translate as a whole?

Runs against an already open Creo session through the stdio server:
one managed part, three long thin triangles (260 x 20.9) created with
coordinate dimensioning at the default 1e-5 mm gate, plus one with an explicit
``geometry_tolerance_mm`` so the released-but-moved path is observable.

The run records whatever happens. A rejection is a valid result: the point is
to see ``sketch_shifted`` agree with the coordinate log and to learn whether the
origin pin removed the 0.004 mm whole-profile translation. R13 adds the
shape-versus-translation verdict (``rigid``, ``shape_deviation_mm``,
``translation_mm``, ``accepted_rigid``) to the record, so a rigid move that the
1e-2 mm limit accepts is visible next to its measured shape residual instead of
being inferred from a success code. Nothing is asserted about the shift itself,
and no model outside this run is touched.

Usage (after a human confirms the session is operable):
    .venv\\Scripts\\python.exe tools\\test_sketch_shift_batch.py --confirmed-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mcp_readiness import wait_for_startup  # noqa: E402
from version import VERSION  # noqa: E402

REPORT = ROOT / "build/sketch_shift_batch.json"
TRIANGLE = [[0, 0], [260, 0], [130, 20.9]]


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _environment() -> dict:
    worker = ROOT / "build/creo_worker.exe"
    return {
        "version": VERSION,
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(_git("status", "--porcelain")),
        "source_fingerprint": (
            (ROOT / "build/source.sha256").read_text(encoding="utf-8").strip()
            if (ROOT / "build/source.sha256").is_file()
            else None
        ),
        "worker_bytes": worker.stat().st_size if worker.is_file() else None,
        "worker_sha256": (
            hashlib.sha256(worker.read_bytes()).hexdigest() if worker.is_file() else None
        ),
    }


async def call(client: Client, name: str, args: dict) -> dict:
    response = await client.call_tool(name, args)
    if response.is_error:
        raise RuntimeError(f"{name}: {response.content}")
    return response.structured_content


async def run_job(client: Client, name: str, args: dict, record: dict) -> dict:
    created = await call(client, name, args)
    job_id = created["job_id"]
    print(f"{name} job={job_id} model={created.get('model_id')}", flush=True)
    result = created
    for _ in range(330):
        result = await call(client, "creo_get_job", {"job_id": job_id})
        if result["status"] not in ("queued", "running"):
            break
        await asyncio.sleep(1)
    record["calls"].append(
        {
            "tool": name,
            "label": args.get("label") or args.get("sketch"),
            "job_id": job_id,
            "status": result["status"],
            "stage": result.get("stage"),
            "message": result.get("message"),
            "sketch_shifted": _shifted(result),
            "geometry_deviation": _deviation(result),
        }
    )
    print(f"  status={result['status']} message={str(result.get('message'))[:160]}", flush=True)
    return result


def _operations(result: dict) -> list[dict]:
    body = result.get("result")
    if not isinstance(body, dict):
        return []
    operations = body.get("operations")
    return (
        [item for item in operations if isinstance(item, dict)]
        if isinstance(operations, list)
        else []
    )


def _shifted(result: dict):
    for operation in _operations(result):
        if "sketch_shifted" in operation:
            return operation["sketch_shifted"]
    return None


def _deviation(result: dict):
    for operation in _operations(result):
        if "geometry_deviation" in operation:
            deviation = operation["geometry_deviation"]
            if isinstance(deviation, dict):
                return {
                    key: deviation.get(key)
                    for key in (
                        "available",
                        "max_deviation_mm",
                        "shape_deviation_mm",
                        "residual_mm",
                        "rigid",
                        "translation_mm",
                        "accepted_rigid",
                        "tolerance_source",
                        "exceeds_warning",
                        "shift_detected",
                        "accepted_by_request",
                    )
                }
    return None


def _sketch(model_id: str, revision: int, label: str, points, tolerance: float | None) -> dict:
    payload = {
        "model_id": model_id,
        "expected_revision": revision,
        "label": label,
        "entities": [
            {
                "type": "polyline",
                "name": f"{label}_outline",
                "points": points,
                "closed": True,
            }
        ],
        "dimensioning": "coordinates",
    }
    if tolerance is not None:
        payload["geometry_tolerance_mm"] = tolerance
    return payload


async def scenario(record: dict) -> None:
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT)
    )
    async with Client(parameters) as connected:
        await wait_for_startup(connected, record, REPORT)
        status = await call(connected, "creo_session_status", {})
        record["session"] = {"connected": status.get("connected")}
        assert status["connected"], status
        part = await run_job(connected, "creo_new_part", {}, record)
        model_id = part["model_id"]
        revision = part["revision"]
        for index, offset in enumerate((0.0, 40.0, -260.0)):
            points = [[x + offset, y] for x, y in TRIANGLE]
            label = f"s01{chr(ord('x') + index)}"
            outcome = await run_job(
                connected,
                "creo_create_sketch",
                _sketch(model_id, revision, label, points, None),
                record,
            )
            if outcome["status"] == "succeeded":
                revision = outcome["revision"]
        # Explicit request tolerance: the released-but-moved path.
        released = await run_job(
            connected,
            "creo_create_sketch",
            _sketch(model_id, revision, "s01t", [[0, 80], [260, 80], [130, 100.9]], 0.01),
            record,
        )
        if released["status"] == "succeeded":
            revision = released["revision"]
        # One solid op so the session also proves save + reload verification
        # still holds with the new pin and block in place.
        solid = await run_job(
            connected,
            "creo_extrude",
            {
                "model_id": model_id,
                "expected_revision": revision,
                "label": "bug108_shift_solid",
                "sketch": "s01x",
                "depth": 5,
            },
            record,
        )
        body = solid.get("result") if isinstance(solid.get("result"), dict) else {}
        record["saved_file_reloaded_and_verified"] = bool(
            body.get("saved_file_reloaded_and_verified")
        )
        record["model_id"] = model_id
        record["revision"] = solid.get("revision") or revision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BUG-108 sketch shift live fixture")
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
        "work_item": "BUG-108",
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
        call_item["status"] in ("succeeded", "failed") for call_item in record["calls"]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: record[key] for key in ("success", "error") if key in record}, indent=2))
    print(f"report: {output}")
    return 0 if record["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
