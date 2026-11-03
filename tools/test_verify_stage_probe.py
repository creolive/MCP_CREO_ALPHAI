"""BUG-109 live probe: see where a job actually is at each poll.

Submits a normal new-part / sketch / extrude sequence through the stdio server and
samples ``creo_get_job`` at 200 ms during each job. What the report keeps:

* every distinct ``stage`` value the job published, with the elapsed time when it
  was first and last seen;
* the bounded ``native_progress`` block (sub stage, stall seconds, log bytes);
* the ``STAGE name=`` lines the executor wrote for the job, so the receipt and the
  log can be compared line by line.

A run where every job finishes is still useful: it shows the sub-stage names and
that ``native_progress`` does not disturb a normal job. Nothing is asserted about
timings, and no model outside this run is touched.

Usage (after a human confirmed the session is operable):
    .venv\\Scripts\\python.exe tools\\test_verify_stage_probe.py --confirmed-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "build" / "verify_stage_probe_report.json"
JOBS = ROOT / "jobs"
STAGE_LINE = re.compile(r"STAGE name=(\S+) elapsed_ms=(\S+) since_start_ms=(\S+) ts=(\d+)")

PLATE = [[0.0, 0.0], [80.0, 0.0], [80.0, 30.0], [0.0, 30.0]]


async def call(client, name: str, arguments: dict) -> dict:
    response = await client.call_tool(name, arguments)
    if response.is_error:
        raise RuntimeError(f"{name}: {response.content}")
    return response.structured_content


def stage_sample(job: dict) -> dict:
    progress = job.get("native_progress")
    return {
        "at_s": round(time.monotonic(), 2),
        "status": job.get("status"),
        "stage": job.get("stage"),
        "sub_stage": progress.get("sub_stage") if isinstance(progress, dict) else None,
        "idle_seconds": progress.get("idle_seconds") if isinstance(progress, dict) else None,
    }


async def watch(client, job_id: str, entry: dict) -> dict:
    """Poll one job and keep a compact stage timeline plus the last native_progress."""
    timeline: dict[str, dict] = {}
    last_progress = None
    last = {}
    for _ in range(600):
        job = await call(client, "creo_get_job", {"job_id": job_id})
        last = job
        progress = job.get("native_progress")
        if isinstance(progress, dict):
            last_progress = progress
        stage = job.get("stage") or job.get("status")
        sub = progress.get("sub_stage") if isinstance(progress, dict) else None
        key = f"{stage}/{sub}" if sub else str(stage)
        now = time.monotonic()
        if key not in timeline:
            timeline[key] = {
                "first_seen_s": round(now, 2),
                "last_seen_s": round(now, 2),
                "samples": 0,
            }
        else:
            timeline[key]["last_seen_s"] = round(now, 2)
        timeline[key]["samples"] += 1
        if job.get("status") not in ("queued", "running"):
            break
        await asyncio.sleep(0.2)
    entry.update(
        status=last.get("status"),
        stage=last.get("stage"),
        message=last.get("message"),
        revision=last.get("revision"),
        stage_timeline=timeline,
        native_progress=last_progress,
        verify_stages=(last.get("result") or {}).get("verify_stages"),
    )
    started = min((item["first_seen_s"] for item in timeline.values()), default=0.0)
    entry["observed_span_s"] = round(
        max((item["last_seen_s"] for item in timeline.values()), default=0.0) - started, 2
    )
    return last


def native_stage_lines(job_id: str) -> list[dict]:
    """Read one job's executor log; keep only its STAGE lines."""
    path = JOBS / job_id / "native.log"
    if not path.exists():
        return []
    lines = []
    for text in path.read_text(encoding="utf-8", errors="replace").splitlines():
        found = STAGE_LINE.search(text)
        if found:
            lines.append(
                {
                    "name": found.group(1),
                    "elapsed_ms": float(found.group(2)),
                    "since_start_ms": float(found.group(3)),
                    "ts": int(found.group(4)),
                }
            )
    return lines[-80:]


async def wait_ready(client, record: dict, budget: float = 300.0) -> dict:
    """Wait for the service's own startup (worker verify) to settle, then report."""
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
        record["session"] = {
            "connected": status.get("connected"),
            "release_numeric": status.get("release_numeric"),
            "connection_state": status.get("connection_state"),
        }

        model_name = f"r13stage{int(time.time()) % 1000000}"
        record["model_name"] = model_name
        part = await call(connected, "creo_new_part", {"model_name": model_name})
        record["model_id"] = part["model_id"]
        first = {"tool": "creo_new_part", "job_id": part["job_id"]}
        record["calls"].append(first)
        current = await watch(connected, part["job_id"], first)
        if current.get("status") != "succeeded":
            raise RuntimeError(f"new_part failed: {current.get('message')}")
        revision = current["revision"]

        for tool, payload in (
            (
                "creo_create_sketch",
                {
                    "label": "r13_stage_profile",
                    "entities": [
                        {
                            "type": "polyline",
                            "name": "r13_stage_outline",
                            "points": PLATE,
                            "closed": True,
                        }
                    ],
                    "dimensioning": "coordinates",
                },
            ),
            (
                "creo_extrude",
                {"label": "r13_stage_plate", "sketch": "r13_stage_profile", "depth": 5},
            ),
        ):
            created = await call(
                connected,
                tool,
                {"model_id": part["model_id"], "expected_revision": revision, **payload},
            )
            entry = {"tool": tool, "job_id": created["job_id"]}
            record["calls"].append(entry)
            current = await watch(connected, created["job_id"], entry)
            revision = current["revision"]

        for entry in record["calls"]:
            entry["native_stage_lines"] = native_stage_lines(entry["job_id"])
        record["final_revision"] = revision
        # A finished job must not keep streaming a progress block.
        finished = await call(connected, "creo_get_job", {"job_id": record["calls"][-1]["job_id"]})
        record["native_progress_on_finished_job"] = "native_progress" in finished


def describe(failure: BaseException) -> str:
    """Flatten nested ExceptionGroups so the report keeps the real cause."""
    if isinstance(failure, BaseExceptionGroup):
        return " | ".join(describe(item) for item in failure.exceptions)
    return f"{type(failure).__name__}: {failure}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BUG-109 verify_model stage probe")
    parser.add_argument("--confirmed-session-usable", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    arguments = parser.parse_args(argv)
    if not arguments.confirmed_session_usable:
        print("live runs require --confirmed-session-usable after human session checks")
        return 2
    record: dict = {
        "work_item": "BUG-109",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "calls": [],
        "success": False,
    }
    started = time.monotonic()
    error = None
    try:
        asyncio.run(scenario(record))
    except BaseException as failure:  # noqa: BLE001 - the report is the product here
        error = describe(failure)
    record["elapsed_s"] = round(time.monotonic() - started, 1)
    if error:
        record["error"] = error
    record["success"] = error is None and all(
        entry.get("status") == "succeeded" for entry in record["calls"]
    )
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: record[key] for key in ("success", "error") if key in record}, indent=2))
    print(f"report: {output}")
    return 0 if record["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
