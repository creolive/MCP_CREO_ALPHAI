"""FEAT-012/BUG-045 live MCP assembly matrix acceptance scenarios.

Run only after independently verifying session health and authorization under
AGENTS.md. This task adds these scenarios without running them. Does not erase
the session, recover unknown outcomes, or retry rejected submissions.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from datetime import datetime, timezone

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from creo_mechdog.paths import SOURCE_PATHS
from tools.dev_check import git_state, source_hash
from tools.mcp_readiness import wait_for_startup

ROOT = SOURCE_PATHS.resource_root
IDENTITY = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
POSES = [
    ([0, 0, 0], IDENTITY, [2, 3, 5]),
    ([90, 0, 0], [[1, 0, 0], [0, 0, 1], [0, -1, 0]], [2, -5, 3]),
    ([-90, 0, 0], [[1, 0, 0], [0, 0, -1], [0, 1, 0]], [2, 5, -3]),
    ([0, 90, 0], [[0, 0, -1], [0, 1, 0], [1, 0, 0]], [5, 3, -2]),
    ([0, -90, 0], [[0, 0, 1], [0, 1, 0], [-1, 0, 0]], [-5, 3, 2]),
    ([0, 0, 90], [[0, 1, 0], [-1, 0, 0], [0, 0, 1]], [-3, 2, 5]),
    ([0, 0, -90], [[0, -1, 0], [1, 0, 0], [0, 0, 1]], [3, -2, 5]),
    ([90, 0, 90], [[0, 1, 0], [0, 0, 1], [1, 0, 0]], [5, 2, 3]),
    ([90, 90, 90], [[0, 0, -1], [0, 1, 0], [1, 0, 0]], [5, 3, -2]),
    ([90, -90, 90], [[0, 0, 1], [0, -1, 0], [1, 0, 0]], [5, -3, 2]),
    (
        [30, 90, 60],
        [[0, 0, -1], [-0.5, math.sqrt(3) / 2, 0], [math.sqrt(3) / 2, 0.5, 0]],
        [-1.5 + 5 * math.sqrt(3) / 2, 3 * math.sqrt(3) / 2 + 2.5, -2],
    ),
]


async def run() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = ROOT / f"build/assembly_matrix_live_{stamp}/report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "work_items": ["FEAT-012", "BUG-045"],
        "source": git_state(ROOT),
        "source_fingerprints": {
            name: source_hash(ROOT / name)
            for name in (
                "server.py",
                "generic_bridge.py",
                "src/creo_mechdog/schema.py",
                "native/advanced.cpp",
                "native/assembly_pose.h",
                "tools/test_assembly_matrix.py",
            )
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
        "calls": [],
        "jobs": [],
        "success": False,
        "session_health": "operator attested before invocation",
        "workbuddy": "not performed by this developer integration script",
    }

    def save():
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

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

            async def terminal_job(name, arguments):
                # Poll to a terminal status without assuming success.
                created = await call(name, arguments)
                deadline = asyncio.get_running_loop().time() + 330
                result = created
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
                return result

            def identity(result):
                return {"model_id": result["model_id"], "expected_revision": result["revision"]}

            async def check(result, label, rotation, mapped):
                listed = await call("creo_list_components", {"model_id": result["model_id"]})
                component_id = listed["aliases"][label]["feature_id"]
                component = next(c for c in listed["components"] if c["feature_id"] == component_id)
                actual = component["transform"]
                # Fixed placement reports the numeric SDK code plus the shared
                # readable symbol; both stay available (FEAT-008 batch 2).
                assert component["constraints"][0]["type_name"] == "fix", component
                assert type(component["constraints"][0]["type"]) is int, component
                expected = [row + [0] for row in rotation] + [[7, -8, 9, 1]]
                assert all(
                    abs(a - b) < 1e-6 for ar, er in zip(actual, expected) for a, b in zip(ar, er)
                ), actual
                # Basis directions and known point using the actual native query matrix.
                for i in range(3):
                    assert all(abs(actual[i][j] - rotation[i][j]) < 1e-6 for j in range(3))
                point = [
                    sum(v * actual[k][j] for k, v in enumerate([2, 3, 5])) + actual[3][j]
                    for j in range(3)
                ]
                assert all(abs(point[j] - mapped[j] - [7, -8, 9][j]) < 1e-6 for j in range(3)), (
                    point
                )
                return listed

            await wait_for_startup(client, report, destination)
            report["environment"] = await call("creo_check_environment", {})
            source = await job(
                "creo_execute_plan",
                {
                    "operations": [
                        {
                            "op": "sketch",
                            "label": "profile",
                            "plane": "XY",
                            "entities": [
                                {"type": "rectangle", "name": "box", "min": [0, 0], "max": [2, 3]}
                            ],
                        },
                        {"op": "extrude", "label": "solid", "sketch": "profile", "depth": 5},
                    ]
                },
            )
            assembly = await job("creo_new_assembly", {})
            for index, (euler, rotation, mapped) in enumerate(POSES):
                label = f"matrix_{index}"
                create = {
                    "op": "assemble_component",
                    "label": label,
                    "source_model_id": source["model_id"],
                    "translation": [7, -8, 9],
                    "rotation_matrix": rotation,
                }
                if index % 2:
                    assembly = await job(
                        "creo_execute_plan", {**identity(assembly), "operations": [create]}
                    )
                else:
                    assembly = await job(
                        "creo_assemble_component",
                        {**identity(assembly), **{k: v for k, v in create.items() if k != "op"}},
                    )
                await check(assembly, label, rotation, mapped)
                assembly = await job(
                    "creo_component_placement",
                    {
                        **identity(assembly),
                        "component": label,
                        "translation": [7, -8, 9],
                        "rotation": euler,
                    },
                )
                await check(assembly, label, rotation, mapped)
                update = {
                    "op": "component_placement",
                    "component": label,
                    "translation": [7, -8, 9],
                    "rotation_matrix": rotation,
                }
                if index % 2:
                    assembly = await job(
                        "creo_component_placement",
                        {**identity(assembly), **{k: v for k, v in update.items() if k != "op"}},
                    )
                else:
                    assembly = await job(
                        "creo_execute_plan", {**identity(assembly), "operations": [update]}
                    )
                before = await check(assembly, label, rotation, mapped)
                await call(
                    "creo_component_placement",
                    {
                        **identity(assembly),
                        "component": label,
                        "translation": [0, 0, 0],
                        "rotation": [0, 0, 0],
                        "rotation_matrix": rotation,
                    },
                    error=True,
                )
                after = await call("creo_list_components", {"model_id": assembly["model_id"]})
                assert (
                    before == after
                )  # invalid request leaves revision/placement/constraints intact
            # One genuine ordinary failure: an unknown component reference is
            # accepted, fails natively, and rolls back; nothing is reported as
            # an effective change and the verified snapshot is untouched.
            before = await call("creo_list_components", {"model_id": assembly["model_id"]})
            failed = await terminal_job(
                "creo_execute_plan",
                {
                    **identity(assembly),
                    "operations": [{"op": "remove_component", "component": "no_such_label"}],
                },
            )
            assert failed["status"] == "failed", failed
            assert failed["revision"] == assembly["revision"], failed
            assert failed["component_changes"]["status"] == "rolled_back", failed
            after = await call("creo_list_components", {"model_id": assembly["model_id"]})
            assert before == after
            report["success"] = True
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
