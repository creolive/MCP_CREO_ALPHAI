"""BUG-009 developer MCP timeline: two real clients, immediate reuse and contention."""

import argparse
import asyncio
import hashlib
import json
import platform
import sys
import time
import traceback
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from version import VERSION


def provenance() -> dict:
    from creo_mechdog.source_provenance import local_provenance

    identity = local_provenance(ROOT)
    return {
        "source_commit": identity["commit"],
        "dirty": identity["dirty"],
        "git_status": identity["git_status"],
    }


async def run(output: Path, rounds: int, resume_jobs: list[str]) -> dict:
    identity = provenance()
    report = {
        "work_item": "BUG-009",
        "version": VERSION,
        "mode": "real MCP and Creo",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": identity["commit"],
        "dirty": identity["dirty"],
        "git_status": identity["git_status"],
        "source_fingerprints": {
            name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for name in (
                "bridge.py",
                "generic_bridge.py",
                "server.py",
                "creo_startup.py",
                "native/worker.cpp",
                "tools/test_toolkit_channel.py",
            )
        },
        "environment": {"os": platform.platform(), "python": sys.version},
        "timeline": [],
        "jobs": [],
        "success": False,
    }
    start = time.perf_counter()

    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    async def call(client, name, args, *, allow_busy=False, allow_error=False):
        event = {
            "client": client_ids[id(client)],
            "tool": name,
            "arguments": args,
            "start_at": datetime.now(timezone.utc).isoformat(),
            "start_ms": round((time.perf_counter() - start) * 1000, 3),
        }
        report["timeline"].append(event)
        try:
            result = await client.call_tool(name, args)
            data = result.structured_content
            event.update(
                is_error=result.is_error,
                response=data,
                raw_content=[block.model_dump(mode="json") for block in result.content],
            )
            if name == "creo_capabilities" and data:
                # Full capability tables are unrelated to scheduling; retain runtime identity.
                event["response"] = {k: data[k] for k in ("version", "runtime", "tool_count")}
                event.pop("raw_content")
            if result.is_error and not allow_error:
                if allow_busy and data and data.get("status") == "busy":
                    assert data["accepted"] is False
                    assert data["retry_after_seconds"] > 0 and data["retry_guidance"]
                else:
                    raise RuntimeError(f"{name}: {result.content}")
            return data
        finally:
            event.update(
                end_ms=round((time.perf_counter() - start) * 1000, 3),
                end_at=datetime.now(timezone.utc).isoformat(),
            )
            save()

    async def poll(client, created, success=True):
        for _ in range(600):
            data = await call(
                client, "creo_get_job", {"job_id": created["job_id"], "detail": "compact"}
            )
            if data["status"] not in ("queued", "running"):
                report["jobs"].append(data)
                if success:
                    assert data["status"] == "succeeded", data
                    if not data.get("readonly"):
                        assert data["result"]["saved_file_reloaded_and_verified"] is True
                return data
            await asyncio.sleep(0.1)
        raise TimeoutError(f"Job {created['job_id']} still active; no resubmission")

    client_ids = {}
    try:
        async with AsyncExitStack() as stack:
            clients = []
            for index in range(2):
                client = await stack.enter_async_context(
                    Client(
                        StdioServerParameters(
                            command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT
                        ),
                        read_timeout_seconds=60,
                    )
                )
                clients.append(client)
                client_ids[id(client)] = f"client_{index + 1}"
            a, b = clients
            cap = await call(a, "creo_capabilities", {})
            report["runtime"] = cap["runtime"]
            for client in clients:
                for _ in range(120):
                    state = await call(client, "creo_startup_status", {})
                    if state["state"] == "ready":
                        break
                    if state["state"] in (
                        "timeout",
                        "configuration_error",
                        "selection_required",
                        "disabled",
                    ):
                        raise RuntimeError(f"Startup unavailable: {state}")
                    await asyncio.sleep(0.5)
                else:
                    raise TimeoutError("Startup not ready; no modeling submitted")
            report["session"] = await call(a, "creo_session_status", {})
            assert report["session"]["connected"]
            for job_id in resume_jobs:
                await poll(a, {"job_id": job_id})
            initial = await call(
                a,
                "creo_execute_plan",
                {
                    "model_name": f"bug009_{int(time.time())}",
                    "operations": [
                        {
                            "op": "sketch",
                            "label": "profile",
                            "entities": [
                                {"type": "rectangle", "name": "r", "min": [-5, -5], "max": [5, 5]}
                            ],
                        },
                        {"op": "extrude", "label": "solid", "sketch": "profile", "depth": 6},
                    ],
                    "assertions": {"volume_mm3": 600, "require_solid": True},
                },
            )
            current = await poll(a, initial)
            mid = current["model_id"]
            # Intentionally no delay between observed terminal and the next admission.
            for index in range(rounds):
                created = await call(
                    clients[index % 2],
                    "creo_save_model",
                    {"model_id": mid, "expected_revision": current["revision"]},
                )
                current = await poll(clients[index % 2], created)
            report["immediate_followups_passed"] = rounds
            # Calls overlap on the wire; native execution remains serialized.
            exports = await asyncio.gather(
                *[
                    call(
                        clients[index % 2],
                        "creo_export_model",
                        {"model_id": mid, "format": fmt},
                        allow_busy=True,
                    )
                    for index, fmt in enumerate(("stl", "step", "iges"))
                ]
            )
            accepted = [value for value in exports if value.get("job_id")]
            rejected = [value for value in exports if value.get("status") == "busy"]
            assert accepted and rejected, exports
            assert all(
                value["blocking_model_id"] in (None, mid)
                and (value["owner_determined"] or value["owner_snapshot"] is None)
                for value in rejected
            )
            for task in accepted:
                busy = await call(b, "creo_refresh_model", {"model_id": mid}, allow_busy=True)
                assert busy["status"] == "busy" and busy["blocking_job_id"] == task["job_id"], busy
                assert busy["blocking_model_id"] == mid, busy
                report["running_job_owner_identified"] = True
                # Registry/cache/job queries must remain available during native execution.
                await asyncio.gather(
                    call(b, "creo_get_job", {"job_id": task["job_id"], "detail": "compact"}),
                    call(b, "creo_list_models", {"limit": 1}),
                    call(b, "creo_inspect_model", {"model_id": mid}),
                )
                await poll(a, task)
            report["concurrent_export_accepted"] = len(accepted)
            report["concurrent_export_busy"] = len(rejected)
            writes = await asyncio.gather(
                *[
                    call(
                        client,
                        "creo_save_model",
                        {"model_id": mid, "expected_revision": current["revision"]},
                        allow_busy=True,
                    )
                    for client in clients
                ]
            )
            accepted = [value for value in writes if value.get("job_id")]
            assert len(accepted) == 1, writes
            current = await poll(a, accepted[0])
            report["parallel_writes_single_acceptance"] = True
            # A later stale write must still fail, without being accepted as busy/success.
            await call(
                a,
                "creo_save_model",
                {"model_id": mid, "expected_revision": current["revision"] - 1},
                allow_error=True,
            )
            stale = report["timeline"][-1]
            assert stale["is_error"] and "Stale revision" in str(stale["raw_content"]), stale
            report["stale_revision_rejected"] = True
            failed = await call(
                a,
                "creo_execute_plan",
                {
                    "model_id": mid,
                    "expected_revision": current["revision"],
                    "operations": [
                        {"op": "set_parameters", "values": {"BUG009_PROBE": 1}},
                        {
                            "op": "extrude",
                            "label": "invalid_extrude",
                            "sketch": "missing_profile",
                            "depth": 1,
                        },
                    ],
                },
            )
            failure = await poll(a, failed, success=False)
            assert failure["status"] == "failed" and failure["result"]["rollback_succeeded"], (
                failure
            )
            refreshed = await call(b, "creo_refresh_model", {"model_id": mid})
            refreshed = await poll(b, refreshed)
            assert refreshed["revision"] == current["revision"]
            assert abs(refreshed["result"]["inspection"]["volume_mm3"] - 600) < 0.01
            report["rollback_then_reuse"] = True
            report["success"] = True
    except Exception as exc:
        report["failure"] = f"{type(exc).__name__}: {exc}"
        report["failure_traceback"] = "".join(traceback.format_exception(exc))
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save()
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "success",
                    "failure",
                    "immediate_followups_passed",
                    "concurrent_export_busy",
                    "rollback_then_reuse",
                )
                if k in report
            }
        ),
        flush=True,
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/bug009-mcp.json")
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--resume-job", action="append", default=[])
    args = parser.parse_args()
    raise SystemExit(
        0 if asyncio.run(run(args.output, args.rounds, args.resume_job))["success"] else 1
    )
