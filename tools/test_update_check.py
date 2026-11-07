"""FEAT-020 developer stdio MCP acceptance, with optional controlled network failure.

This is a local developer test, not a WorkBuddy black-box test. --network-failure
injects a sanitized network failure in a fresh server process; it does not disconnect
the operating system. --create requires a real Toolkit-ready session and verifies
a new small plate, its geometry and saved-file reload.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from version import VERSION

OFFLINE_SERVER = """
import server
from creo_mechdog import update_check
async def offline():
    raise update_check.UpdateFailure('Controlled developer-test network failure')
update_check.fetch_releases = offline
server.mcp.run(transport='stdio')
"""


def provenance() -> dict:
    from creo_mechdog.source_provenance import local_provenance

    identity = local_provenance(ROOT)
    return {
        "commit": identity["commit"],
        "dirty": identity["dirty"],
        "git_status": identity["git_status"],
    }


async def run(args: argparse.Namespace) -> dict:
    identity = provenance()
    report = {
        "work_item": "FEAT-020",
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "commit": identity["commit"],
        "dirty": identity["dirty"],
        "git_status": identity["git_status"],
        "python": sys.version,
        "windows": platform.platform(),
        "transport": "stdio",
        "client_mode": "legacy" if args.classic else "auto",
        "network": "controlled developer injection" if args.network_failure else "real GitHub",
        "calls": [],
        "modeling": {"status": "not_requested"},
        "success": False,
    }
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", OFFLINE_SERVER] if args.network_failure else [str(ROOT / "server.py")],
        cwd=ROOT,
    )

    async def call(client, name, inputs):
        started = time.monotonic()
        result = await client.call_tool(name, inputs)
        value = result.structured_content
        report["calls"].append(
            {
                "tool": name,
                "input": inputs,
                "elapsed_seconds": time.monotonic() - started,
                "is_error": result.is_error,
                "result": value,
                "content": [item.model_dump(mode="json") for item in result.content]
                if result.is_error
                else None,
            }
        )
        assert not result.is_error, result
        return value

    try:
        async with Client(
            params, mode="legacy" if args.classic else "auto", read_timeout_seconds=15
        ) as client:
            report["instructions"] = client.instructions
            assert "creo_check_update" in client.instructions
            assert "once per latest_version" in client.instructions
            tools = (await client.list_tools()).tools
            report["tool_count"] = len(tools)
            tool = next(tool for tool in tools if tool.name == "creo_check_update")
            report["update_tool"] = tool.model_dump(mode="json")
            assert tool.annotations.read_only_hint and tool.annotations.open_world_hint
            capabilities = await call(client, "creo_capabilities", {})
            report["runtime"] = capabilities["runtime"]
            assert not report["runtime"]["source_changed_since_startup"]
            assert Path(report["runtime"]["code_root"]).resolve() == ROOT
            assert capabilities["version"] == VERSION
            assert capabilities["tool_count"] == len(tools) == 82
            checked = await call(client, "creo_check_update", {"force": True})
            if args.network_failure:
                assert checked["status"] == "failed"
                assert checked["latest_version"] is None
                assert checked["error"] == "Controlled developer-test network failure"
            else:
                assert checked["status"] in ("update_available", "up_to_date"), checked
                assert checked["latest_version"] and checked["release_url"].startswith(
                    "https://github.com/wudahua/MCP_CREO_MechDog/releases/"
                )
            cached = await call(client, "creo_check_update", {})
            caps = await call(client, "creo_capabilities", {})
            state = await call(client, "creo_startup_status", {})
            assert cached["from_cache"]
            assert cached == caps["update"] == state["update"]
            report["update"] = cached
            report["startup"] = state
            report["environment"] = await call(client, "creo_check_environment", {})
            if args.create:
                if args.retry_startup:
                    state = await call(client, "creo_startup_status", {"retry": True})
                # Respect the normal readiness gate; never submit a duplicate on timeout.
                deadline = time.monotonic() + 130
                while (
                    state["state"]
                    not in (
                        "ready",
                        "timeout",
                        "configuration_error",
                        "disabled",
                        "selection_required",
                    )
                    and time.monotonic() < deadline
                ):
                    await asyncio.sleep(1)
                    state = await call(client, "creo_startup_status", {})
                report["startup"] = state
                if state["state"] != "ready":
                    report["modeling"] = {"status": "unverified", "reason": state}
                else:
                    created = await call(
                        client, "creo_create_plate", {"length": 20, "width": 10, "thickness": 2}
                    )
                    for _ in range(90):
                        job = await call(
                            client,
                            "creo_get_job",
                            {"job_id": created["job_id"], "detail": "compact"},
                        )
                        if job["status"] in ("succeeded", "failed", "unknown_outcome"):
                            break
                        await asyncio.sleep(1)
                    else:
                        raise TimeoutError("Modeling has no confirmed outcome; do not resubmit")
                    report["modeling"] = job
                    assert job["status"] == "succeeded", job
                    assert job["result"]["saved_file_reloaded_and_verified"]
                    native = job["result"]
                    volume = native.get(
                        "volume_mm3", native.get("inspection", {}).get("volume_mm3")
                    )
                    assert volume is not None and abs(volume - 400) < 0.01
            report["update_interfaces_verified"] = True
            report["success"] = not args.create or report["modeling"].get("status") == "succeeded"
    except Exception as exc:
        report["failure"] = str(exc)
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                key: report.get(key)
                for key in ("success", "tool_count", "update", "modeling", "failure")
            },
            ensure_ascii=False,
        )
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classic", action="store_true")
    parser.add_argument("--network-failure", action="store_true")
    parser.add_argument("--create", action="store_true")
    parser.add_argument(
        "--retry-startup",
        action="store_true",
        help="Explicit recheck after confirming any prior launch outcome; may start Creo",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "build/feat020-mcp.json")
    args = parser.parse_args()
    return 0 if asyncio.run(run(args))["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
