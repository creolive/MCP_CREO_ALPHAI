"""BUG-008 developer acceptance of cold and warm retry through fresh real MCP clients."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import subprocess
import sys
import time
import traceback
from contextlib import AsyncExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "tools.test_startup_retry", *sys.argv[1:]], cwd=ROOT)
    )

from mcp import Client
from mcp.client.stdio import StdioServerParameters

import bridge
import creo_startup
from version import VERSION


def protected_files() -> dict:
    values = {}
    for model_id in ("27143ef77ce641938543e0ca44cc3c03", "5f68fea957134ddc8ecc26016dcf58a4"):
        model = ROOT / "models" / model_id / "model.json"
        values[str(model)] = hashlib.sha256(model.read_bytes()).hexdigest()
        part = Path(bridge.read_json(model)["part_file"])
        values[str(part)] = hashlib.sha256(part.read_bytes()).hexdigest()
    manifest = ROOT / "jobs/272513b7238040c68dce4b923725d870/job.json"
    values[str(manifest)] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    return values


def provenance() -> dict:
    from creo_mechdog.source_provenance import local_provenance

    identity = local_provenance(ROOT)
    return {
        "source_commit": identity["commit"],
        "dirty": identity["dirty"],
        "git_status": identity["git_status"],
    }


async def run(args) -> dict:
    settings = creo_startup.Settings.load()
    before = creo_startup.inventory(settings)
    if before["uncertain"] or (args.require_cold and before["processes"]):
        raise RuntimeError(
            "Cold retry test requires no existing Creo; this script never closes a session"
        )
    identity = provenance()
    report = {
        "work_item": "BUG-008",
        "version": VERSION,
        "started_at": bridge.now(),
        "source_commit": identity["commit"],
        "dirty": identity["dirty"],
        "git_status": identity["git_status"],
        "environment": {
            "os": platform.platform(),
            "python": sys.version,
            "creo_root": bridge.config()["creo_root"],
        },
        "source_fingerprints": {
            name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for name in (
                "bridge.py",
                "generic_bridge.py",
                "creo_startup.py",
                "server.py",
                "src/creo_mechdog/startup_state.py",
                "src/creo_mechdog/windows_boot.py",
                "src/creo_mechdog/recovery.py",
                "native/worker.cpp",
                "native/result_delivery.h",
                "tools/test_startup_retry.py",
            )
        },
        "worker_sha256": hashlib.sha256((ROOT / "build/creo_worker.exe").read_bytes()).hexdigest(),
        "inventory_before": before,
        "protected_before": protected_files(),
        "timeline": [],
        "jobs": [],
        "success": False,
    }
    shared = creo_startup.CreoStartup()._target_directory(settings) / "state.json"
    report["windows_session"] = creo_startup.windows_session()
    report["shared_state_file"] = str(shared)
    history = shared.parent / "history"
    report["history_before"] = sorted(path.name for path in history.glob("*.bin"))
    try:
        report["shared_before"] = bridge.read_json(shared) if shared.is_file() else None
    except (OSError, ValueError) as exc:
        raw = shared.read_bytes()
        report["shared_before"] = {
            "read_error": type(exc).__name__,
            "message": str(exc),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        (args.output.parent / "shared-before.bin").write_bytes(raw)

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    async def call(client, name, values):
        event = {
            "tool": name,
            "arguments": values,
            "started_at": bridge.now(),
            "start_counter": time.perf_counter(),
        }
        report["timeline"].append(event)
        try:
            result = await client.call_tool(name, values)
            data = result.structured_content
            event.update(
                is_error=result.is_error,
                response=data,
                raw_content=[block.model_dump(mode="json") for block in result.content],
            )
            if name == "creo_capabilities":
                event["response"] = {key: data[key] for key in ("version", "runtime", "scheduling")}
                event.pop("raw_content")
            assert not result.is_error, event
            return data
        finally:
            event.update(finished_at=bridge.now(), end_counter=time.perf_counter())
            save()

    async def terminal(client, require_ready=False):
        deadline = time.monotonic() + 310
        while time.monotonic() < deadline:
            value = await call(client, "creo_startup_status", {})
            if value["state"] not in creo_startup.ACTIVE:
                if require_ready:
                    assert value["state"] == "ready" and value["connected"], value
                return value
            await asyncio.sleep(1)
        raise TimeoutError(
            "Startup total test budget expired; no process or reservation was removed"
        )

    async def job(client, name, values):
        created = await call(client, name, values)
        deadline = time.monotonic() + 720
        while time.monotonic() < deadline:
            value = await call(
                client, "creo_get_job", {"job_id": created["job_id"], "detail": "full"}
            )
            if value["status"] not in ("queued", "running"):
                report["jobs"].append(value)
                assert value["status"] == "succeeded", value
                assert value["result"]["saved_file_reloaded_and_verified"] is True, value
                assert (
                    value["result"]["delivery_complete"] and value["result"]["disconnect_code"] == 0
                ), value
                return value
            await asyncio.sleep(0.2)
        raise TimeoutError(f"Job {created['job_id']} has no terminal result; no resubmission")

    parameters = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT
    )
    try:
        async with AsyncExitStack() as stack:
            clients = [
                await stack.enter_async_context(Client(parameters, read_timeout_seconds=30))
                for _ in range(2)
            ]
            first, second = clients
            report["runtime"] = (await call(first, "creo_capabilities", {}))["runtime"]
            assert (
                report["runtime"]["code_root"] == str(ROOT)
                and not report["runtime"]["source_changed_since_startup"]
            )
            report["initial_states"] = await asyncio.gather(
                *(terminal(client) for client in clients)
            )
            report["cold_automatic_startup"] = not before["processes"] and all(
                state.get("connected") for state in report["initial_states"]
            )
            if args.expect_reboot_recovery:
                assert report["cold_automatic_startup"], report["initial_states"]
                recovery = report["initial_states"][0]["startup_recovery"]
                assert recovery["status"] == "reconciled_previous_boot"
                archive = Path(recovery["archive_file"])
                assert (
                    hashlib.sha256(archive.read_bytes()).hexdigest()
                    == report["shared_before"]["sha256"]
                )
                report["startup_archive"] = recovery
            report["inventory_before_retry"] = creo_startup.inventory(settings)
            report["cold_explicit_retry"] = (
                not before["processes"] and not report["inventory_before_retry"]["processes"]
            )
            report["retry_responses"] = await asyncio.gather(
                *(call(client, "creo_startup_status", {"retry": True}) for client in clients)
            )
            events = [event for event in report["timeline"] if event["arguments"].get("retry")]
            report["retry_rpc_overlap_seconds"] = min(
                event["end_counter"] for event in events
            ) - max(event["start_counter"] for event in events)
            assert report["retry_rpc_overlap_seconds"] > 0, events
            report["ready_states"] = await asyncio.gather(
                *(terminal(client, True) for client in clients)
            )
            report["session"] = await call(first, "creo_session_status", {})
            assert report["session"]["connected"] and report["session"]["toolkit_code"] == 0
            report["inventory_after_retry"] = creo_startup.inventory(settings)
            assert (
                not report["inventory_after_retry"]["uncertain"]
                and report["inventory_after_retry"]["processes"]
                and all(p["matches"] for p in report["inventory_after_retry"]["processes"])
            )
            if report["inventory_before_retry"]["processes"]:
                assert report["inventory_before_retry"] == report["inventory_after_retry"]
            # A later single request must also return a usable result.
            report["single_retry"] = await call(first, "creo_startup_status", {"retry": True})
            await terminal(first, True)
            stable = creo_startup.inventory(settings)
            assert [(p["pid"], p["created"]) for p in stable["processes"]] == [
                (p["pid"], p["created"]) for p in report["inventory_after_retry"]["processes"]
            ]
            report["no_duplicate_launch"] = True
            created = await job(
                first, "creo_new_part", {"model_name": f"bug008_retry_{int(time.time())}"}
            )
            edited = await job(
                first,
                "creo_execute_plan",
                {
                    "model_id": created["model_id"],
                    "expected_revision": created["revision"],
                    "operations": [
                        {
                            "op": "sketch",
                            "label": "retry_profile",
                            "entities": [
                                {"type": "rectangle", "name": "r", "min": [-2, -3], "max": [2, 3]}
                            ],
                        },
                        {
                            "op": "extrude",
                            "label": "retry_solid",
                            "sketch": "retry_profile",
                            "depth": 5,
                        },
                        {"op": "set_parameters", "values": {"RETRY_VERIFIED": 1}},
                    ],
                    "assertions": {"require_solid": True, "volume_mm3": 120},
                },
            )
            state = edited["result"]["inspection"]
            assert (
                abs(state["volume_mm3"] - 120) < 0.001
                and state["parameters"]["RETRY_VERIFIED"]["value"] == 1
            )
            assert edited["revision"] == 2
            report["historical_unknown"] = await call(
                second,
                "creo_get_job",
                {"job_id": "272513b7238040c68dce4b923725d870", "detail": "compact"},
            )
        report["protected_after"] = protected_files()
        assert report["protected_before"] == report["protected_after"]
        report["shared_after"] = bridge.read_json(shared)
        report["history_after"] = sorted(path.name for path in history.glob("*.bin"))
        if args.expect_reboot_recovery:
            assert len(set(report["history_after"]) - set(report["history_before"])) == 1
        report["inventory_after_clients_close"] = creo_startup.inventory(settings)
        assert [(p["pid"], p["created"]) for p in report["inventory_after_retry"]["processes"]] == [
            (p["pid"], p["created"]) for p in report["inventory_after_clients_close"]["processes"]
        ]
        report["success"] = True
    except Exception as exc:
        report.update(failure=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
    finally:
        report["finished_at"] = bridge.now()
        save()
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("success", "failure", "cold_explicit_retry")
                if key in report
            }
        ),
        flush=True,
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-cold", action="store_true")
    parser.add_argument("--expect-reboot-recovery", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/bug008-retry/native.json")
    args = parser.parse_args()
    raise SystemExit(0 if asyncio.run(run(args))["success"] else 1)
