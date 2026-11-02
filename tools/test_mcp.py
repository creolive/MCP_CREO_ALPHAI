"""Exercise the real stdio transport. --create also creates a fresh native test part."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from version import VERSION


async def main(create: bool, simple: bool, classic: bool):
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    report = {"transport": "stdio", "client_mode": "legacy" if classic else "auto"}
    async with Client(
        params, mode="legacy" if classic else "auto", read_timeout_seconds=60
    ) as client:
        report["protocol_version"] = client.protocol_version
        tools = await client.list_tools()
        report["tools"] = [t.name for t in tools.tools]
        from capabilities import UNAVAILABLE_OPERATIONS

        assert not {f"creo_{name}" for name in UNAVAILABLE_OPERATIONS} & set(report["tools"])
        assert {
            "creo_execute_plan",
            "creo_create_sketch",
            "creo_extrude",
            "creo_revolve",
            "creo_hole",
            "creo_dimension_pattern",
            "creo_new_drawing",
            "creo_create_udf",
            "creo_rib",
            "creo_boolean_bodies",
            "creo_new_loft_part",
        } <= set(report["tools"]), report
        assert {
            "creo_list_seeds",
            "creo_install_seed_library",
            "creo_validate_seed",
            "creo_new_airfoil_blade",
            "creo_create_airfoil_section",
            "creo_set_airfoil_parameters",
            "creo_update_sketch_geometry",
            "creo_transform_geometry",
            "creo_set_geometry_transform",
            "creo_group_features",
            "creo_reorder_features",
            "creo_axis_pattern",
        } <= set(report["tools"])
        loft_tool = next(t for t in tools.tools if t.name == "creo_new_loft_part")
        interpolation = loft_tool.input_schema["properties"]["interpolation"]
        assert set(interpolation["enum"]) == {"straight", "smooth"}, interpolation
        assert interpolation["default"] == "straight", interpolation
        assert not {"seed_file", "seed_feature_id"} & set(
            loft_tool.input_schema.get("required", [])
        )
        sections = loft_tool.input_schema["properties"]["sections"]
        assert sections["minItems"] == 2 and sections["maxItems"] == 20, sections
        report["loft_section_count_schema_verified"] = True
        report["loft_interpolation_schema_verified"] = True
        capabilities = await client.call_tool("creo_capabilities", {})
        assert not capabilities.is_error, capabilities
        assert capabilities.structured_content["enabled_tool_count"] == len(report["tools"])
        assert capabilities.structured_content["disabled_tools_hidden"] is True
        assert capabilities.structured_content["families"]["loft_seed"]["interpolation"] == [
            "straight",
            "smooth",
        ]
        assert capabilities.structured_content["families"]["loft_seed"][
            "section_count_input_range"
        ] == [2, 20]
        assert (
            capabilities.structured_content["families"]["loft_seed"][
                "seed_section_count_must_match"
            ]
            is True
        )
        report["server"] = {
            key: capabilities.structured_content[key] for key in ("name", "version")
        }
        assert report["server"] == {"name": "MCP_CREO_MechDog", "version": VERSION}, report[
            "server"
        ]
        environment = await client.call_tool("creo_check_environment", {})
        assert not environment.is_error, environment
        report["environment"] = environment.structured_content
        assert report["environment"]["ready_to_build"], report["environment"]
        status = await client.call_tool("creo_session_status", {})
        assert not status.is_error, status
        report["session"] = status.structured_content
        assert report["session"]["connected"], report["session"]
        print(
            json.dumps(
                {
                    "tool_count": len(report["tools"]),
                    "session_connected": report["session"]["connected"],
                }
            ),
            flush=True,
        )
        invalid = await client.call_tool(
            "creo_create_plate",
            {
                "length": 80,
                "width": 60,
                "thickness": 20,
                "holes": [{"x": 40, "y": 0, "diameter": 8}],
            },
        )
        assert invalid.is_error, "Invalid geometry must be rejected before submitting a native job"
        report["invalid_geometry_rejected"] = True
        if create:
            assert report["session"]["connected"], report["session"]
            spec = (
                {"length": 42, "width": 30, "thickness": 6, "corner_radius": 0, "holes": []}
                if simple
                else {
                    "length": 100,
                    "width": 70,
                    "thickness": 12,
                    "corner_radius": 4,
                    "holes": [
                        {"x": x, "y": y, "diameter": 6}
                        for x, y in [(-35, -20), (35, -20), (35, 20), (-35, 20)]
                    ]
                    + [{"x": 0, "y": 0, "diameter": 10}],
                }
            )
            created = await client.call_tool("creo_create_plate", spec)
            assert not created.is_error, created
            job_id = created.structured_content["job_id"]
            print(f"job_id={job_id}", flush=True)
            stage = None
            for _ in range(150):
                result = await client.call_tool("creo_get_job", {"job_id": job_id})
                assert not result.is_error, result
                job = result.structured_content
                state = (job["status"], job.get("stage"))
                if state != stage:
                    print(f"progress={state}", flush=True)
                    stage = state
                if job["status"] in ("succeeded", "failed", "unknown_outcome"):
                    report["job"] = job
                    break
                await asyncio.sleep(2)
            else:
                raise TimeoutError(f"Job is still running: {job_id}; do not submit a duplicate")
            (
                ROOT / "build" / ("mcp_simple_test.json" if simple else "mcp_integration_test.json")
            ).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            assert job["status"] == "succeeded", json.dumps(job, ensure_ascii=False, indent=2)
            assert job["result"]["saved_file_reloaded_and_verified"]
            print(json.dumps(job, ensure_ascii=False, indent=2), flush=True)
        else:
            (ROOT / "build/mcp_protocol_test.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--simple", action="store_true")
    parser.add_argument("--classic", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.create, args.simple, args.classic))
