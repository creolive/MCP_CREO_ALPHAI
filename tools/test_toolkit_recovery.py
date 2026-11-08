"""BUG-008 developer evidence: controlled helper failures and real MCP/Creo recovery checks."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import subprocess
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    raise SystemExit(
        subprocess.call(
            [sys.executable, "-m", "tools.test_toolkit_recovery", *sys.argv[1:]], cwd=ROOT
        )
    )

from mcp import Client
from mcp.client.stdio import StdioServerParameters

import bridge
import generic_bridge as general
from creo_mechdog.query_client import read_full_model
from creo_mechdog.recovery import process_identity
from version import VERSION


def controlled(output: Path) -> dict:
    """Compile the actual delivery implementation with a fake disconnect callback."""
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    script = output / "build-fixture.cmd"
    exe = output / "delivery-fixture.exe"
    script.write_text(
        f'@echo off\ncall "{bridge.config()["vcvars64"]}"\nif errorlevel 1 exit /b 1\n'
        f'cl /nologo /MD /EHsc /std:c++17 /I"{ROOT / "native"}" "{ROOT / "tools/test_result_delivery.cpp"}" /Fo"{output / "fixture.obj"}" /Fe"{exe}"\n',
        encoding="utf-8",
    )
    build = subprocess.run(
        ["cmd.exe", "/d", "/c", str(script)],
        cwd=output,
        capture_output=True,
        timeout=120,
        creationflags=bridge.HIDDEN,
    )
    (output / "build-fixture.log").write_bytes(build.stdout + build.stderr)
    assert build.returncode == 0, "Controlled helper build failed; inspect build-fixture.log"
    evidence = {"mode": "controlled C++ helper; no Creo calls or real PRT", "cases": []}
    for mode, expected in (
        ("normal", 0),
        ("hang", 31),
        ("hang_default", 31),
        ("disconnect_failure", 0),
        ("write_failure", 32),
    ):
        directory = output / f"{mode}_{time.time_ns()}"
        directory.mkdir()
        (directory / "scenario.txt").write_text(mode, encoding="utf-8")
        began = time.monotonic()
        proc = subprocess.run(
            [str(exe), "generic", str(directory)], timeout=25, creationflags=bridge.HIDDEN
        )
        checkpoint = bridge.read_json(directory / "native_checkpoint.json")
        result = (
            bridge.read_json(directory / "native_result.json")
            if (directory / "native_result.json").is_file()
            else None
        )
        case = {
            "scenario": mode,
            "exit_code": proc.returncode,
            "elapsed_seconds": time.monotonic() - began,
            "checkpoint": checkpoint,
            "result": result,
        }
        evidence["cases"].append(case)
        assert proc.returncode == expected, case
        assert checkpoint["delivery_complete"] is False, case
        if mode in ("hang", "hang_default"):
            assert result is None and checkpoint["completion_stage"] == "disconnect_timeout", case
            assert case["elapsed_seconds"] < (23 if mode == "hang_default" else 2), case
            if mode == "hang_default":
                assert (
                    case["elapsed_seconds"] >= 20 and checkpoint["disconnect_budget_seconds"] == 20
                ), case
        elif mode == "normal":
            assert result["delivery_complete"] and result["disconnect_code"] == 0, case
        elif mode == "write_failure":
            assert result is None, case
    # Exercise the real Python runner against the compiled fake helper. No fake
    # success is committed: its timeout must retain the model reservation.
    from unittest.mock import patch

    fixture = output / f"registry_{time.time_ns()}"
    fixture.mkdir()
    template = fixture / "Common Files/templates/mmns_part_solid_abs.prt"
    template.parent.mkdir(parents=True)
    template.write_bytes(b"fixture only; never passed to Creo")
    with (
        patch.object(bridge, "ROOT", fixture),
        patch.object(bridge, "JOBS", fixture / "jobs"),
        patch.object(general, "MODELS", fixture / "models"),
        patch.object(bridge, "config", return_value={"creo_root": str(fixture)}),
        patch.object(bridge, "build_native", return_value=exe),
        patch.object(bridge, "native_environment", return_value={}),
    ):
        with patch.object(bridge.subprocess, "Popen"):
            created = general.submit([])
        directory = bridge.job_path(created["job_id"])
        (directory / "scenario.txt").write_text("hang", encoding="utf-8")
        bridge.run_job(created["job_id"])
        unknown = bridge.get_job(created["job_id"], detail="compact")
        model = general.model_info(created["model_id"])
        assert unknown["status"] == "unknown_outcome" and model["revision"] == 0
        assert model["pending_job"] == created["job_id"]
        try:
            general.submit([], model_id=created["model_id"], expected_revision=0)
        except bridge.ToolkitBusy as exc:
            rejection = exc.payload
        else:
            raise AssertionError("Unknown outcome was allowed to write again")
        evidence["unknown_protection"] = {
            "job": unknown,
            "revision": model["revision"],
            "rejection": rejection,
        }
        # A real sleeping OS process exercises the public 2 s probe's 9 s outer
        # budget without contacting or damaging the user's Creo session.
        marker = fixture / "probe-pid.txt"
        real_run = subprocess.run

        def sleeping_probe(*args, **kwargs):
            code = f"import os,pathlib,time;pathlib.Path({str(marker)!r}).write_text(str(os.getpid()));time.sleep(60)"
            return real_run([sys.executable, "-c", code], **kwargs)

        began = time.monotonic()
        with patch.object(bridge.subprocess, "run", side_effect=sleeping_probe):
            probe = bridge.session_status(2)
        elapsed = time.monotonic() - began
        stopped = process_identity(int(marker.read_text()))
        assert probe["connection_state"] == "probe_timeout" and probe["probe_budget_seconds"] == 9
        assert 9 <= elapsed < 12 and stopped["alive"] is False, (elapsed, stopped)
        evidence["probe_timeout"] = {
            "result": probe,
            "elapsed_seconds": elapsed,
            "helper_after": stopped,
        }
    evidence["success"] = True
    return evidence


async def native(report: dict, save) -> None:
    """Real protocol calls; no fault injection in the user's Creo session."""
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT
    )

    async def call(client, name, args, allow_error=False):
        event = {
            "tool": name,
            "arguments": args,
            "started_at": bridge.now(),
            "start": time.monotonic(),
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
            if name == "creo_capabilities":
                event["response"] = {key: data[key] for key in ("version", "runtime", "scheduling")}
                event.pop("raw_content")
            assert allow_error or not result.is_error, event
            return data
        finally:
            event.update(
                finished_at=bridge.now(), elapsed_seconds=time.monotonic() - event["start"]
            )
            save()

    async def ready(client):
        deadline = time.monotonic() + 310
        while time.monotonic() < deadline:
            state = await call(client, "creo_startup_status", {})
            if state["state"] == "ready":
                assert state["connected"] and state["verified_at"], state
                return state
            assert state["state"] in (
                "checking",
                "waiting_for_channel",
                "building_worker",
                "starting",
                "waiting_for_connection",
            ), state
            await asyncio.sleep(0.2)
        raise TimeoutError("Real startup did not finish; no modeling submitted")

    async def job(client, tool, args, success=True):
        created = await call(client, tool, args)
        deadline = time.monotonic() + 720
        while time.monotonic() < deadline:
            value = await call(
                client, "creo_get_job", {"job_id": created["job_id"], "detail": "full"}
            )
            if value["status"] not in ("queued", "running"):
                report["jobs"].append(value)
                if success:
                    assert value["status"] == "succeeded", value
                    if not value.get("readonly"):
                        assert value["result"]["saved_file_reloaded_and_verified"], value
                    assert (
                        value["result"]["delivery_complete"]
                        and value["result"]["disconnect_code"] == 0
                    ), value
                return value
            await asyncio.sleep(0.2)
        raise TimeoutError(f"Job {created['job_id']} still active; no replay or unlocking")

    async with AsyncExitStack() as stack:
        clients = [
            await stack.enter_async_context(Client(parameters, read_timeout_seconds=30))
            for _ in range(2)
        ]
        a, b = clients
        report["runtime"] = (await call(a, "creo_capabilities", {}))["runtime"]
        assert not report["runtime"]["source_changed_since_startup"]
        await asyncio.gather(*(ready(client) for client in clients))
        report["session_before"] = await call(a, "creo_session_status", {})
        assert (
            report["session_before"]["connected"] and report["session_before"]["toolkit_code"] == 0
        )
        # Read only: never reconcile this historical unknown task by guessing its outcome.
        report["historical_unknown_job"] = await call(
            a, "creo_get_job", {"job_id": "272513b7238040c68dce4b923725d870", "detail": "compact"}
        )
        first = await job(a, "creo_new_part", {"model_name": f"bug008_{int(time.time())}"})
        mid = first["model_id"]
        model = await job(
            a,
            "creo_execute_plan",
            {
                "model_id": mid,
                "expected_revision": first["revision"],
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
        edited = await job(
            a,
            "creo_set_parameters",
            {
                "model_id": mid,
                "expected_revision": model["revision"],
                "values": {"BUG008_MARKER": 8},
            },
        )
        assert edited["revision"] == model["revision"] + 1
        before = edited["result"]["part_file"]
        before_hash = hashlib.sha256(Path(before).read_bytes()).hexdigest()
        failure = await job(
            a,
            "creo_execute_plan",
            {
                "model_id": mid,
                "expected_revision": edited["revision"],
                "operations": [
                    {"op": "set_parameters", "values": {"BUG008_SHOULD_ROLLBACK": 1}},
                    {
                        "op": "extrude",
                        "label": "invalid_extrude",
                        "sketch": "missing_profile",
                        "depth": 1,
                    },
                ],
            },
            success=False,
        )
        assert failure["status"] == "failed" and failure["result"]["rollback_succeeded"], failure
        report["overlapping_retry_requests"] = await asyncio.gather(
            *(call(client, "creo_startup_status", {"retry": True}) for client in clients)
        )
        report["retry_ready_states"] = await asyncio.gather(*(ready(client) for client in clients))
        report["session_after"] = await call(b, "creo_session_status", {})
        assert report["session_after"]["connected"] and report["session_after"]["toolkit_code"] == 0
        independent = await job(
            b, "creo_new_part", {"model_name": f"bug008_after_{int(time.time())}"}
        )
        await job(
            b,
            "creo_execute_plan",
            {
                "model_id": independent["model_id"],
                "expected_revision": independent["revision"],
                "operations": [
                    {
                        "op": "sketch",
                        "label": "after_profile",
                        "entities": [
                            {"type": "rectangle", "name": "r", "min": [-2, -3], "max": [2, 3]}
                        ],
                    },
                    {
                        "op": "extrude",
                        "label": "after_solid",
                        "sketch": "after_profile",
                        "depth": 5,
                    },
                    {"op": "set_parameters", "values": {"RECOVERED": 1}},
                ],
                "assertions": {"require_solid": True, "volume_mm3": 120},
            },
        )
        plate = await job(
            b,
            "creo_create_plate",
            {
                "length": 20,
                "width": 10,
                "thickness": 3,
                "model_name": f"bug008_plate_{int(time.time())}",
            },
        )
        assert abs(plate["result"]["volume_mm3"] - 600) < 0.01
        await job(
            b,
            "creo_new_drawing",
            {"source_model_id": mid, "model_name": f"bug008_drw_{int(time.time())}"},
        )
        refreshed = await job(a, "creo_refresh_model", {"model_id": mid})
        assert refreshed["revision"] == edited["revision"]
        assert abs(refreshed["result"]["inspection"]["volume_mm3"] - 600) < 0.01
        full = await read_full_model(lambda tool, args: call(a, tool, args), mid)
        report["final_inspection"] = full
        parameters_text = json.dumps(full["inspection"].get("parameters"))
        assert (
            "BUG008_MARKER" in parameters_text and "BUG008_SHOULD_ROLLBACK" not in parameters_text
        ), parameters_text
        assert hashlib.sha256(Path(before).read_bytes()).hexdigest() == before_hash
        report["original_saved_checkpoint"] = {
            "path": before,
            "sha256": before_hash,
            "unchanged": True,
        }
        report["native_success"] = True


def provenance() -> dict:
    from creo_mechdog.source_provenance import local_provenance

    identity = local_provenance(ROOT)
    return {
        "source_commit": identity["commit"],
        "dirty": identity["dirty"],
        "git_status": identity["git_status"],
    }


async def run(args) -> dict:
    identity = provenance()
    report = {
        "work_item": "BUG-008",
        "version": VERSION,
        "started_at": bridge.now(),
        "source_commit": identity["source_commit"],
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
                "src/creo_mechdog/recovery.py",
                "native/worker.cpp",
                "native/generic.cpp",
                "native/drawing.cpp",
                "native/result_delivery.h",
                "tools/test_result_delivery.cpp",
                "tools/test_toolkit_recovery.py",
            )
        },
        "timeline": [],
        "jobs": [],
        "success": False,
    }

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    try:
        if args.controlled:
            report["controlled"] = controlled(args.output.parent / "delivery-fixture")
        if args.native:
            report["worker_sha256"] = hashlib.sha256(
                (ROOT / "build/creo_worker.exe").read_bytes()
            ).hexdigest()
            await native(report, save)
        report["success"] = True
    except Exception as exc:
        import traceback

        report["failure"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
    finally:
        report["finished_at"] = bridge.now()
        save()
    print(
        json.dumps({key: report[key] for key in ("success", "failure") if key in report}),
        flush=True,
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controlled", action="store_true")
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/bug008/recovery.json")
    args = parser.parse_args()
    if not args.controlled and not args.native:
        parser.error("Select --controlled and/or --native")
    raise SystemExit(0 if asyncio.run(run(args))["success"] else 1)
