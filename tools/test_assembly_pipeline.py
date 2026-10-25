"""FEAT-008 batch-2 live official assembly rebuild pipeline scenario.

Exercises the documented pipeline end to end through real MCP calls:
inspect the original assembly -> adopt sources by path -> new managed
assembly -> insert several components in ONE execute_plan job -> unified
save/erase/reload -> readback verification, then source_snapshot semantics
(source edit leaves inserted snapshots unchanged; remove + re-assemble
regenerates from the current source revision).

Run only after independently verifying session health and authorization under
AGENTS.md (same conditions as tools/test_assembly_matrix.py). Every fixture is
created by this run; historical protected models are never touched. The
script never erases the session, recovers unknown outcomes, retries rejected
submissions, or injects failures. For md050 runs, wrap with
tools/guarded_live_run.py so the main worktree service cannot touch the same
Creo concurrently. WorkBuddy acceptance is a separate pure-MCP activity.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from creo_mechdog.paths import SOURCE_PATHS
from tools.dev_check import git_state, source_hash
from tools.mcp_readiness import wait_for_startup

ROOT = SOURCE_PATHS.resource_root


def block(label: str, size: list[float], depth: float) -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": f"{label}_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "outline",
                    "min": [-size[0] / 2, -size[1] / 2],
                    "max": [size[0] / 2, size[1] / 2],
                }
            ],
        },
        {"op": "extrude", "label": label, "sketch": f"{label}_profile", "depth": depth},
    ]


async def run() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = ROOT / f"build/assembly_pipeline_live_{stamp}/report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "work_items": ["FEAT-008", "FEAT-012", "FEAT-048", "DEV-046"],
        "source": git_state(ROOT),
        "source_fingerprints": {
            name: source_hash(ROOT / name)
            for name in (
                "server.py",
                "generic_bridge.py",
                "src/creo_mechdog/schema.py",
                "src/creo_mechdog/file_adoption.py",
                "src/creo_mechdog/component_changes.py",
                "native/advanced.cpp",
                "native/constraint_names.h",
                "native/assembly_pose.h",
                "tools/test_assembly_pipeline.py",
            )
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
        "calls": [],
        "jobs": [],
        "assertions": [],
        "success": False,
        "session_health": "operator attested before invocation",
        "workbuddy": "not performed by this developer integration script",
    }

    def save():
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def note(text: str):
        report["assertions"].append(text)
        save()

    parameters = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT
    )
    try:
        async with Client(parameters, mode="legacy", read_timeout_seconds=90) as client:

            async def call(name, arguments, error=False):
                reply = await client.call_tool(name, arguments)
                report["calls"].append(
                    {"tool": name, "arguments": arguments, "reply": reply.model_dump(mode="json")}
                )
                save()
                assert reply.is_error == error, str(reply)
                return reply.structured_content

            async def job(name, arguments):
                created = await call(name, arguments)
                deadline = asyncio.get_running_loop().time() + 330
                while asyncio.get_running_loop().time() < deadline:
                    result = await call(
                        "creo_get_job", {"job_id": created["job_id"], "detail": "full"}
                    )
                    if result["status"] not in ("queued", "running"):
                        break
                    await asyncio.sleep(1)
                else:
                    raise TimeoutError("Poll existing job only; do not resubmit")
                report["jobs"].append(result)
                save()
                assert result["status"] == "succeeded", result
                assert result["result"]["saved_file_reloaded_and_verified"] is True, result
                if "expected_revision" in arguments:
                    assert result["revision"] == arguments["expected_revision"] + 1, result
                return result

            def identity(result):
                return {"model_id": result["model_id"], "expected_revision": result["revision"]}

            await wait_for_startup(client, report, destination)
            report["environment"] = await call("creo_check_environment", {})

            # 1-2. Source fixtures: two healthy millimeter parts saved on disk.
            source_a = await job(
                "creo_execute_plan",
                {"model_name": "pipe_src_a", "operations": block("body", [40, 30], 6)},
            )
            source_b = await job(
                "creo_execute_plan",
                {"model_name": "pipe_src_b", "operations": block("cap", [12, 12], 18)},
            )
            part_file_a = source_a["result"]["part_file"]
            part_file_b = source_b["result"]["part_file"]
            note("source parts saved on disk with verified reload")

            # 3. Original assembly (this run's fixture), then read-only inspect.
            original = await job("creo_new_assembly", {"model_name": "pipe_orig_asm"})
            original = await job(
                "creo_execute_plan",
                {
                    **identity(original),
                    "operations": [
                        {
                            "op": "assemble_component",
                            "label": "orig_a",
                            "source_model_id": source_a["model_id"],
                            "translation": [0, 0, 0],
                        },
                        {
                            "op": "assemble_component",
                            "label": "orig_b",
                            "source_model_id": source_b["model_id"],
                            "translation": [50, 0, 0],
                        },
                    ],
                },
            )
            assert original["component_changes"]["status"] == "committed"
            assert len(original["component_changes"]["changes"]) == 2
            inspected = await call(
                "creo_inspect_session_assembly", {"name": "pipe_orig_asm", "limit": 50}
            )
            assert inspected["total"] == 2, inspected
            assert all(item["transform_to_parent"] for item in inspected["components"]), inspected
            note("original assembly inspected read-only with normalized mm transforms")

            # 4. Adopt both sources by path (inspect -> apply), one parent job.
            paths = [part_file_a, part_file_b]
            evidence = await call("creo_adopt_file", {"file_path": paths, "mode": "inspect"})
            assert evidence["available"] and evidence["item_count"] == 2, evidence
            adopted = await call(
                "creo_adopt_file",
                {
                    "file_path": paths,
                    "mode": "apply",
                    "evidence_token": evidence["evidence_token"],
                    "idempotency_key": f"pipe-{stamp}",
                },
            )
            deadline = asyncio.get_running_loop().time() + 400
            while adopted["status"] in ("queued", "running"):
                assert asyncio.get_running_loop().time() < deadline
                await asyncio.sleep(1)
                adopted = await call(
                    "creo_get_job", {"job_id": adopted["job_id"], "detail": "compact"}
                )
            report["jobs"].append(adopted)
            save()
            assert adopted["status"] == "succeeded" and adopted["all_adopted"], adopted
            adopted_ids = {item["input_path"]: item["model_id"] for item in adopted["items"]}
            assert len(set(adopted_ids.values())) == 2
            note("both sources adopted by path with independent durable commits")

            # 5-6. New managed assembly; ONE job inserts three components.
            assembly = await job("creo_new_assembly", {"model_name": "pipe_rebuilt_asm"})
            batch = await job(
                "creo_execute_plan",
                {
                    **identity(assembly),
                    "operations": [
                        {
                            "op": "assemble_component",
                            "label": "plate_a",
                            "source_model_id": adopted_ids[part_file_a],
                            "translation": [0, 0, 0],
                            "placement": "fixed",
                        },
                        {
                            "op": "assemble_component",
                            "label": "plate_b",
                            "source_model_id": adopted_ids[part_file_b],
                            "translation": [0, 0, 12],
                            "rotation_matrix": [[0, 1, 0], [-1, 0, 0], [0, 0, 1]],
                            "placement": "fixed",
                        },
                        {
                            "op": "assemble_component",
                            "label": "plate_b_second",
                            "source_model_id": adopted_ids[part_file_b],
                            "translation": [60, 0, 12],
                            "rotation_matrix": [[0, 1, 0], [-1, 0, 0], [0, 0, 1]],
                            "placement": "fixed",
                        },
                    ],
                },
            )
            changes = batch["component_changes"]
            assert changes["status"] == "committed" and len(changes["changes"]) == 3, changes
            assert all(change["op"] == "added" for change in changes["changes"]), changes
            assert (
                changes["changes"][1]["source_model_id"] == changes["changes"][2]["source_model_id"]
            ), changes
            preview = batch["result"]["preview_file"]
            assert preview and (ROOT / preview).resolve().is_file(), preview
            note("single execute_plan job inserted three components; preview.jpg reused")

            # 7. Readback: transforms, constraint symbols, snapshot aliases.
            listed = await call("creo_list_components", {"model_id": batch["model_id"]})
            assert len(listed["components"]) == 3, listed
            for component in listed["components"]:
                constraint = component["constraints"][0]
                assert constraint["type_name"] == "fix", component
                assert type(constraint["type"]) is int, component
            alias = listed["aliases"]["plate_a"]
            assert alias["source_snapshot"] is True and alias["source_revision"] == 1, alias
            copy_before = {c["feature_id"]: c["model_name"] for c in listed["components"]}
            note("readback verified: 3 components, numeric+symbolic constraint names")

            # 8. Source edit does NOT update the inserted snapshot.
            edited = await job(
                "creo_execute_plan",
                {
                    **identity(source_a),
                    "operations": block("rib", [10, 10], 2),
                },
            )
            assert edited["revision"] == source_a["revision"] + 1
            unchanged = await call("creo_list_components", {"model_id": batch["model_id"]})
            assert unchanged["revision"] == batch["revision"]
            copy_after_edit = {c["feature_id"]: c["model_name"] for c in unchanged["components"]}
            assert copy_before == copy_after_edit, "source edit moved the snapshot copy"
            note("source edit left the inserted snapshot unchanged")

            # 9. Regenerate: remove + re-assemble picks up the current revision.
            regenerated = await job(
                "creo_execute_plan",
                {
                    **identity(unchanged),
                    "operations": [
                        {"op": "remove_component", "component": "plate_a"},
                        {
                            "op": "assemble_component",
                            "label": "plate_a",
                            "source_model_id": adopted_ids[part_file_a],
                            "translation": [0, 0, 0],
                            "placement": "fixed",
                        },
                    ],
                },
            )
            regen_changes = regenerated["component_changes"]
            assert [c["op"] for c in regen_changes["changes"]] == ["removed", "added"], (
                regen_changes
            )
            assert regen_changes["changes"][1]["source_revision"] == edited["revision"], (
                regen_changes
            )
            final = await call("creo_list_components", {"model_id": batch["model_id"]})
            final_copies = {c["feature_id"]: c["model_name"] for c in final["components"]}
            assert len(final_copies) == 3
            assert set(final_copies.values()) != set(copy_before.values()), (
                "regeneration kept the stale copy"
            )
            note("remove + re-assemble regenerated the snapshot at the current revision")

            report["success"] = True
            report["untested"] = [
                "unknown outcome and its protection (never injected)",
                "concurrent clients and channel busy interleaving",
                "non-millimeter / dependent / unhealthy source admission beyond per-item refusal",
                "nested subassemblies (not supported)",
                "all Creo versions other than the live session",
                "WorkBuddy pure-MCP acceptance",
            ]
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-health-verified", action="store_true", required=True)
    parser.parse_args()
    asyncio.run(run())
