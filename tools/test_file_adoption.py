"""FEAT-048 live MCP path-adoption scenario; run only after session clearance.

Supply 1-19 independent external part paths, optionally including an unhealthy,
non-mm or dependent source to exercise a known refusal beside a healthy source.
A duplicate of the first path is added automatically. Sources may be resident;
the tool reports that provenance explicitly. This driver never erases sources,
restarts Creo, clears protection, or injects failures. Unknown outcomes stop it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from creo_mechdog.file_adoption import lifetime_seconds
from creo_mechdog.paths import SOURCE_PATHS
from creo_mechdog.reconciliation import identity

ROOT = SOURCE_PATHS.resource_root


async def scenario(paths: list[str], report: dict) -> None:
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=lifetime_seconds(len(paths)),
    ) as client:

        async def call(name, arguments):
            response = await client.call_tool(name, arguments)
            report["calls"].append(
                {
                    "tool": name,
                    "arguments": arguments,
                    "is_error": response.is_error,
                    "result": response.structured_content,
                }
            )
            if response.is_error:
                raise RuntimeError(f"{name}: {response.content}")
            return response.structured_content

        async def current():
            page = await call("creo_list_session_models", {"limit": 50})
            models = list(page["models"])
            while page.get("next_cursor"):
                page = await call(
                    "creo_list_session_models", {"limit": 50, "cursor": page["next_cursor"]}
                )
                models.extend(page["models"])
            assert all(m.get("is_current") is not None for m in models), (
                "Current-model identity unavailable"
            )
            return [
                (m.get("name"), m.get("model_type"), m.get("origin"))
                for m in models
                if m["is_current"]
            ]

        before = await current()
        inspection = await call("creo_adopt_file", {"file_path": paths})
        assert inspection["status"] == "succeeded", inspection
        assert before == await current(), "Inspect changed the current model"
        assert inspection["items"][-1]["reason"] == "duplicate_source"
        source_files = [i["file"] for i in inspection["items"] if i.get("file")]
        for file in source_files:
            assert identity(Path(file["path"])) == file
        arguments = {
            "file_path": paths,
            "mode": "apply",
            "evidence_token": inspection["evidence_token"],
            "idempotency_key": f"feat048-{uuid.uuid4().hex}",
        }
        accepted = await call("creo_adopt_file", arguments)
        terminal = accepted
        deadline = time.monotonic() + lifetime_seconds(len(paths))
        while terminal["status"] in ("queued", "running"):
            assert time.monotonic() < deadline, "Parent exceeded documented bounded lifetime"
            await asyncio.sleep(1)
            terminal = await call(
                "creo_get_job", {"job_id": accepted["job_id"], "detail": "compact"}
            )
        assert terminal["status"] != "unknown_outcome", terminal
        assert terminal["item_counts"]["succeeded"] > 0, (
            "Supply at least one healthy external source"
        )
        assert terminal["partial_result"] and not terminal["all_adopted"]
        for item in terminal["items"]:
            if item["status"] == "succeeded":
                assert item["revision"] == 1
                assert item["result"]["saved_file_reloaded_and_verified"] is True
                assert item["result"]["source_unchanged"] is True
                assert item["result"]["window_unchanged"] is True
        assert before == await current(), "Apply changed the current model"
        for file in source_files:
            assert identity(Path(file["path"])) == file
        replay = await call("creo_adopt_file", arguments)
        assert replay["job_id"] == terminal["job_id"]
        assert replay["items"] == terminal["items"]
        report.update(
            success=True,
            parent_job_id=terminal["job_id"],
            untested=[
                "unknown/native timeout injection",
                "concurrent clients",
                "all other Creo versions",
            ],
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+")
    arguments = parser.parse_args()
    if not 1 <= len(arguments.sources) <= 19:
        parser.error("Provide 1-19 sources; driver appends one duplicate")
    report = {
        "started_at": time.time(),
        "calls": [],
        "success": False,
        "scope": "Developer integration through MCP; not WorkBuddy acceptance",
    }
    try:
        asyncio.run(scenario([*arguments.sources, arguments.sources[0]], report))
    finally:
        destination = ROOT / "build/file_adoption_integration.json"
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
