"""FEAT-008 batch-2 stage-3 live official assembly rebuild pipeline scenario.

Exercises the documented pipeline end to end through real MCP calls with
fixtures prepared for THIS RUN ONLY:
create two fixture parts -> copy their verified bytes to a unique, unmanaged
external directory (recorded SHA256, then read-only) -> adopt the external
files by path -> build an original assembly with a repeated occurrence and an
asymmetric combined rotation -> freeze its verified snapshot -> rebuild a new
assembly from the normalized millimeter transforms read by
creo_inspect_session_assembly -> prove source_snapshot semantics by editing the
ADOPTED source (a real protruding tab that changes volume), regenerating the
assembly (revision+1, geometry still the old snapshot) and finally replacing
the component via remove + re-assemble (fresh native geometry reflects the new
source).

The earlier revision of this driver passed MCP-managed output files (which
adoption must refuse as managed_output) to creo_adopt_file and edited the
original fixture instead of the adopted copy; both defects are corrected here.
Managed fixture originals and their registry records are never modified after
preparation; the external sources are prepared BEFORE any acceptance and stay
read-only afterwards.

Run only after independently verifying session health and authorization under
AGENTS.md (same conditions as tools/test_assembly_matrix.py). The script never
erases the session, recovers unknown outcomes, retries rejected submissions, or
injects failures. For md050 runs, wrap with tools/guarded_live_run.py so the
main worktree service cannot touch the same Creo concurrently. WorkBuddy
acceptance is a separate pure-MCP activity.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from creo_mechdog.paths import SOURCE_PATHS
from tools.dev_check import git_state, source_hash
from tools.mcp_readiness import wait_for_startup

ROOT = SOURCE_PATHS.resource_root
ROT_Z90 = [[0, 1, 0], [-1, 0, 0], [0, 0, 1]]
# Asymmetric combined rotation (row vectors, local to parent, det +1).
ROT_COMBINED = [[0, 1, 0], [0, 0, 1], [1, 0, 0]]
# Protruding tab: extends x beyond the 40x30x6 body envelope (x in -20..20),
# so both volume (+600 mm3) and bounding box really change.
TAB_MIN = [20, -5]
TAB_MAX = [30, 5]
TAB_DEPTH = 6
TAB_VOLUME = (TAB_MAX[0] - TAB_MIN[0]) * (TAB_MAX[1] - TAB_MIN[1]) * TAB_DEPTH


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


def tab_operations() -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "tab_profile",
            "plane": "XY",
            "entities": [
                {"type": "rectangle", "name": "tab_outline", "min": TAB_MIN, "max": TAB_MAX}
            ],
        },
        {"op": "extrude", "label": "tab", "sketch": "tab_profile", "depth": TAB_DEPTH},
    ]


def matrix_close(actual, expected, tolerance=1e-6) -> bool:
    return all(abs(a - b) <= tolerance for ar, er in zip(actual, expected) for a, b in zip(ar, er))


async def run() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = stamp + uuid.uuid4().hex[:8]
    destination = ROOT / f"build/assembly_pipeline_live_{tag}/report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    external_dir = ROOT / f"build/assembly_pipeline_external_{tag}"
    external_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "work_items": ["FEAT-008", "FEAT-012", "FEAT-048", "DEV-046"],
        "stage": "batch-2 stage-3 review closeout",
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
                "native/constraint_compare.h",
                "native/assembly_pose.h",
                "tools/test_assembly_pipeline.py",
            )
        },
        "fixture_tag": tag,
        "external_fixture_dir": str(external_dir),
        "tab_volume_mm3": TAB_VOLUME,
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

            def identity_of(result):
                return {"model_id": result["model_id"], "expected_revision": result["revision"]}

            def volume_of(model_id):
                return call("creo_inspect_model", {"model_id": model_id})

            await wait_for_startup(client, report, destination)
            report["environment"] = await call("creo_check_environment", {})

            # 1-2. Fixture parts (unique names per run), verified saved+reloaded.
            source_a = await job(
                "creo_execute_plan",
                {"model_name": f"pipe_src_a_{tag}", "operations": block("body", [40, 30], 6)},
            )
            source_b = await job(
                "creo_execute_plan",
                {"model_name": f"pipe_src_b_{tag}", "operations": block("cap", [12, 12], 18)},
            )
            note("fixture parts created and saved on disk with verified reload")

            # 3. Prepare EXTERNAL, unmanaged, uniquely named adoption sources:
            # byte copies of the verified fixture outputs, hashed and read-only.
            external = {}
            for key, created in (("a", source_a), ("b", source_b)):
                part = created["result"]["part_file"]
                target = external_dir / f"pipe_ext_{key}_{tag}.prt.1"
                target.write_bytes((ROOT / part).resolve().read_bytes())
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                assert digest == created["result"]["sha256"], (
                    "external fixture copy diverged from the verified managed output"
                )
                os.chmod(target, 0o444)
                external[key] = {"path": str(target), "sha256": digest}
            report["external_sources"] = external
            save()
            note("external fixture sources prepared before acceptance; read-only; SHA256 recorded")

            # 4. Adopt the EXTERNAL files by path (inspect -> apply).
            paths = [external["a"]["path"], external["b"]["path"]]
            evidence = await call("creo_adopt_file", {"file_path": paths, "mode": "inspect"})
            assert evidence["available"] and evidence["item_count"] == 2, evidence
            for item in evidence["items"]:
                key = "a" if "pipe_ext_a_" in item["file"]["path"] else "b"
                assert item["file"]["sha256"] == external[key]["sha256"], item
            adopted = await call(
                "creo_adopt_file",
                {
                    "file_path": paths,
                    "mode": "apply",
                    "evidence_token": evidence["evidence_token"],
                    "idempotency_key": f"pipe-{tag}",
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
            assert set(adopted_ids.values()).isdisjoint(
                {source_a["model_id"], source_b["model_id"]}
            ), "adoption must create independent managed models"
            note("external sources adopted by path with independent durable commits")

            # 5. Original assembly: repeated occurrence + asymmetric rotation.
            original_name = f"pipe_orig_asm_{tag}"
            original = await job("creo_new_assembly", {"model_name": original_name})
            original = await job(
                "creo_execute_plan",
                {
                    **identity_of(original),
                    "operations": [
                        {
                            "op": "assemble_component",
                            "label": "plate_a",
                            "source_model_id": adopted_ids[external["a"]["path"]],
                            "translation": [0, 0, 0],
                            "placement": "fixed",
                        },
                        {
                            "op": "assemble_component",
                            "label": "plate_b",
                            "source_model_id": adopted_ids[external["b"]["path"]],
                            "translation": [50, 0, 0],
                            "rotation_matrix": ROT_Z90,
                            "placement": "fixed",
                        },
                        {
                            "op": "assemble_component",
                            "label": "plate_b_second",
                            "source_model_id": adopted_ids[external["b"]["path"]],
                            "translation": [50, 40, 10],
                            "rotation_matrix": ROT_COMBINED,
                            "placement": "fixed",
                        },
                    ],
                },
            )
            changes = original["component_changes"]
            assert changes["status"] == "committed" and len(changes["changes"]) == 3, changes
            assert all(change["op"] == "added" for change in changes["changes"]), changes
            assert (
                changes["changes"][1]["source_model_id"] == changes["changes"][2]["source_model_id"]
            ), changes
            preview = original["result"]["preview_file"]
            assert preview and (ROOT / preview).resolve().is_file(), preview
            note("original assembly built: repeated occurrence + asymmetric combined rotation")

            # 6. Freeze the verified snapshot (fresh from the saved/reload job).
            listed = await call("creo_list_components", {"model_id": original["model_id"]})
            assert len(listed["components"]) == 3, listed
            for component in listed["components"]:
                constraint = component["constraints"][0]
                assert constraint["type_name"] == "fix", component
                assert type(constraint["type"]) is int, component
            frozen = {}
            for label, alias in listed["aliases"].items():
                component = next(
                    c for c in listed["components"] if c["feature_id"] == alias["feature_id"]
                )
                assert alias["source_snapshot"] is True, alias
                frozen[label] = {
                    "feature_id": alias["feature_id"],
                    "copy_name": component["model_name"],
                    "transform": component["transform"],
                    "source_model_id": alias["source_model_id"],
                    "source_revision": alias["source_revision"],
                }
            assert len(frozen) == 3
            origin_inspect = await volume_of(original["model_id"])
            origin_volume = origin_inspect["volume_mm3"]
            assert origin_volume, "assembly volume must be measurable"
            note("frozen verified snapshot recorded (poses, copy names, aliases, volume)")

            # 7. Rebuild from the inspected normalized millimeter transforms.
            inspected = await call(
                "creo_inspect_session_assembly", {"name": original_name, "limit": 50}
            )
            assert inspected["total"] == 3, inspected
            by_name = {item["name"]: item for item in inspected["components"]}
            assert len(by_name) == 3, "occurrence names must resolve uniquely"
            operations = []
            for label, snap in frozen.items():
                occurrence = by_name.get(snap["copy_name"])
                assert occurrence is not None, f"occurrence {snap['copy_name']} missing"
                assert occurrence["transform_mm_known"], occurrence
                transform = occurrence["transform_to_parent"]
                operations.append(
                    {
                        "op": "assemble_component",
                        "label": label,
                        "source_model_id": snap["source_model_id"],
                        "translation": transform[3][:3],
                        "rotation_matrix": [row[:3] for row in transform[:3]],
                        "placement": "fixed",
                    }
                )
            rebuilt = await job("creo_new_assembly", {"model_name": f"pipe_rebuilt_asm_{tag}"})
            rebuilt = await job(
                "creo_execute_plan", {**identity_of(rebuilt), "operations": operations}
            )
            assert rebuilt["component_changes"]["status"] == "committed"
            note("rebuilt assembly created from inspected normalized mm transforms")

            # 8. Readback: every occurrence pose matches the frozen snapshot.
            readback = await call("creo_list_components", {"model_id": rebuilt["model_id"]})
            assert len(readback["components"]) == 3, readback
            aliases = readback["aliases"]
            assert (
                aliases["plate_b"]["source_model_id"]
                == aliases["plate_b_second"]["source_model_id"]
            ), aliases
            probe_local = [2.0, 3.0, 5.0]
            for label, snap in frozen.items():
                feature_id = aliases[label]["feature_id"]
                component = next(c for c in readback["components"] if c["feature_id"] == feature_id)
                assert matrix_close(component["transform"], snap["transform"]), (
                    label,
                    component["transform"],
                    snap["transform"],
                )
                assert component["constraints"][0]["type_name"] == "fix", component
                mapped = [
                    sum(v * component["transform"][k][j] for k, v in enumerate(probe_local))
                    + component["transform"][3][j]
                    for j in range(3)
                ]
                expected = [
                    sum(v * snap["transform"][k][j] for k, v in enumerate(probe_local))
                    + snap["transform"][3][j]
                    for j in range(3)
                ]
                assert all(abs(a - b) <= 1e-6 for a, b in zip(mapped, expected))
            rebuilt_inspect = await volume_of(rebuilt["model_id"])
            assert abs(rebuilt_inspect["volume_mm3"] - origin_volume) <= 0.01, (
                rebuilt_inspect["volume_mm3"],
                origin_volume,
            )
            note("rebuilt assembly readback matches the frozen snapshot (poses + volume)")

            # 9. source_snapshot semantics on the ADOPTED source.
            adopted_a = adopted_ids[external["a"]["path"]]
            adopted_a_inspect = await volume_of(adopted_a)
            volume_a_before = adopted_a_inspect["volume_mm3"]
            assert volume_a_before, "adopted source volume must be measurable"

            # 9a. Edit the ADOPTED source with a real protruding tab.
            edited = await job(
                "creo_execute_plan",
                {
                    "model_id": adopted_a,
                    "expected_revision": adopted_a_inspect["revision"],
                    "operations": tab_operations(),
                },
            )
            edited_inspect = await volume_of(adopted_a)
            assert edited_inspect["revision"] == edited["revision"]
            assert abs(edited_inspect["volume_mm3"] - (volume_a_before + TAB_VOLUME)) <= 0.01, (
                edited_inspect["volume_mm3"],
                volume_a_before + TAB_VOLUME,
            )
            note("adopted source edited: protruding tab really changed volume")

            # 9b. The managed fixture original must be untouched (independent
            # identity proof for the adoption itself).
            fixture_a = await volume_of(source_a["model_id"])
            assert fixture_a["revision"] == source_a["revision"], fixture_a
            assert abs(fixture_a["volume_mm3"] - 40 * 30 * 6) <= 0.01, fixture_a

            # 9c. Cached readback stays stale (this is a cache, not proof).
            cached = await call("creo_list_components", {"model_id": rebuilt["model_id"]})
            assert cached["revision"] == rebuilt["revision"]
            note("list_components cache unchanged after source edit (cache only, not proof)")

            # 9d. Explicit native regenerate of the assembly: revision advances
            # (+1 contract) but the fresh saved/reload geometry must still be
            # the OLD snapshot (volume unchanged by the source edit).
            regenerated = await job(
                "creo_execute_plan",
                {**identity_of(rebuilt), "operations": [{"op": "regenerate"}]},
            )
            fresh = await volume_of(rebuilt["model_id"])
            assert fresh["revision"] == regenerated["revision"]
            assert abs(fresh["volume_mm3"] - origin_volume) <= 0.01, (
                fresh["volume_mm3"],
                origin_volume,
            )
            note("assembly regenerate: revision+1 with fresh native data; still old snapshot")

            # 9e. remove + re-assemble picks up the current source revision.
            plate_a_pose = next(op for op in operations if op["label"] == "plate_a")
            replaced = await job(
                "creo_execute_plan",
                {
                    **identity_of(regenerated),
                    "operations": [
                        {"op": "remove_component", "component": "plate_a"},
                        {k: v for k, v in plate_a_pose.items() if k != "op"},
                    ],
                },
            )
            regen_changes = replaced["component_changes"]
            assert [c["op"] for c in regen_changes["changes"]] == ["removed", "added"], (
                regen_changes
            )
            assert regen_changes["changes"][1]["source_revision"] == edited["revision"], (
                regen_changes
            )
            final_inspect = await volume_of(rebuilt["model_id"])
            assert abs(final_inspect["volume_mm3"] - (origin_volume + TAB_VOLUME)) <= 0.01, (
                final_inspect["volume_mm3"],
                origin_volume + TAB_VOLUME,
            )
            final_list = await call("creo_list_components", {"model_id": rebuilt["model_id"]})
            assert len(final_list["components"]) == 3
            new_alias = final_list["aliases"]["plate_a"]
            assert new_alias["source_revision"] == edited["revision"], new_alias
            new_component = next(
                c for c in final_list["components"] if c["feature_id"] == new_alias["feature_id"]
            )
            assert matrix_close(new_component["transform"], frozen["plate_a"]["transform"]), (
                new_component["transform"],
                frozen["plate_a"]["transform"],
            )
            assert new_component["model_name"] != frozen["plate_a"]["copy_name"], (
                "re-inserted snapshot must be a fresh native copy"
            )
            note("remove + re-assemble regenerated the snapshot at the current source revision")

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
