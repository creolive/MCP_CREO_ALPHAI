"""0.3.7 remaining native regressions via stdio MCP; no process or failure injection."""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from creo_mechdog import inspection_refs
from creo_mechdog.paths import SOURCE_PATHS
from tools.dev_check import git_state, source_hash
from tools.mcp_readiness import wait_for_startup
from tools.test_direct_loft import Probe, circle_sections
from tools.test_p1_modeling import box, identity

ROOT = SOURCE_PATHS.resource_root


def close_matrix(actual: list, expected: list) -> None:
    assert len(actual) == len(expected) == 4
    assert all(len(row) == 4 for row in actual + expected)
    assert all(abs(a - b) < 1e-7 for ar, er in zip(actual, expected) for a, b in zip(ar, er)), (
        actual
    )


async def components(probe: Probe) -> None:
    source = await probe.job("creo_execute_plan", {"operations": box()}, "component_source")
    assembly = await probe.job("creo_new_assembly", {}, "assembly")
    placed = await probe.job(
        "creo_assemble_component",
        {
            **identity(assembly),
            "label": "member",
            "source_model_id": source["model_id"],
            "translation": [-30, 20, 0],
            "rotation": [0, 0, 30],
        },
        "initial_placement",
    )
    before = placed["result"]["inspection"]["components"][0]["transform"]
    assert abs(before[3][0] + 30) < 1e-7 and abs(before[3][1] - 20) < 1e-7
    constraints = [
        {
            "type": "align",
            "assembly_reference": {"kind": "datum_plane", "axis": axis},
            "component_reference": {"kind": "datum_plane", "axis": axis},
        }
        for axis in "xyz"
    ]
    solved = await probe.job(
        "creo_component_constraints",
        {
            **identity(placed),
            "component": "member",
            "constraints": constraints,
        },
        "constraints_replace_fixed_pose",
    )
    expected = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    component = solved["result"]["inspection"]["components"][0]
    close_matrix(component["transform"], expected)
    assert component["transform_source"] == "component_to_assembly"
    assert not component["underconstrained"] and not component["packaged"]
    refreshed = await probe.job(
        "creo_refresh_model", {"model_id": solved["model_id"]}, "assembly_reload"
    )
    close_matrix(refreshed["result"]["inspection"]["components"][0]["transform"], expected)
    assert refreshed["revision"] == placed["revision"] + 1


async def seeds(probe: Probe) -> None:
    for interpolation in ("straight", "smooth"):
        result = await probe.job(
            "creo_new_loft_part",
            {
                "sections": circle_sections(),
                "interpolation": interpolation,
                "label": "seed_blend",
            },
            "seed_" + interpolation,
        )
        evidence = result["result"]["seed_load_evidence"]
        assert evidence["status"] == "loaded" and evidence["evidence_persisted"]
        assert evidence["creo_release_numeric"] > 0
        value = await probe.call("creo_validate_seed", {"seed_name": "two_" + interpolation})
        assert value["available"]
        assert any(
            row["job_id"] == result["job_id"]
            for row in value["native_compatibility"]["observations"]
        )
        assert value["native_compatibility"]["status"] == "not_verified_for_current_session"
        if interpolation == "straight":
            summary = inspection_refs.summary_of(result["result"])
            assert abs(summary["volume_mm3"] - 4900 * math.pi / 3) < 0.01


async def rounds(probe: Probe) -> None:
    for kind, field, value in (("round", "radius", 2), ("chamfer", "distance", 1)):
        for mode in ("tool", "plan_size", "plan_alias"):
            base = await probe.job(
                "creo_execute_plan", {"operations": box()}, f"{kind}_{mode}_base"
            )
            edge = base["result"]["inspection"]["edges"][0]["id"]
            inputs = {
                "label": "finish",
                "references": [{"edge": {"kind": "edge", "id": edge}}],
            }
            size_field = "size" if mode == "plan_size" else field
            if mode != "tool":
                result = await probe.job(
                    "creo_execute_plan",
                    {
                        **identity(base),
                        "operations": [{"op": kind, **inputs, size_field: value}],
                    },
                    f"{kind}_{mode}",
                )
            else:
                result = await probe.job(
                    "creo_" + kind, {**identity(base), **inputs, field: value}, kind + "_tool"
                )
            operation = result["result"]["operations"][-1]
            assert operation["size"] == value
            compact = await probe.call(
                "creo_get_job", {"job_id": result["job_id"], "detail": "compact"}
            )
            assert compact["result"]["operations"][-1]["size"] == value
            fid = result["result"]["aliases"]["finish"]["feature_id"]
            feature = next(f for f in result["result"]["inspection"]["features"] if f["id"] == fid)
            assert any(abs(d["value"] - value) < 1e-7 for d in feature["dimensions"])
            other_alias = "distance" if kind == "round" else "radius"
            for invalid, message in (
                ({"size": value, field: value}, "not both"),
                ({other_alias: value}, "does not accept"),
            ):
                await probe.call(
                    "creo_execute_plan",
                    {
                        **identity(result),
                        "operations": [
                            {"op": kind, **inputs, "label": "invalid_finish", **invalid}
                        ],
                    },
                    expect_error=True,
                )
                error_text = " ".join(
                    item.get("text", "") for item in probe.report["calls"][-1]["raw_error"]
                )
                assert message in error_text, error_text
            unchanged = await probe.job(
                "creo_refresh_model", {"model_id": result["model_id"]}, kind + "_after_conflict"
            )
            assert unchanged["revision"] == result["revision"]
            assert (
                abs(
                    unchanged["result"]["inspection"]["volume_mm3"]
                    - result["result"]["inspection"]["volume_mm3"]
                )
                < 0.01
            )


async def run(args: argparse.Namespace) -> bool:
    fingerprint_files = (
        "bridge.py",
        "generic_bridge.py",
        "server.py",
        "src/creo_mechdog/schema.py",
        "src/creo_mechdog/seed_compatibility.py",
        "native/advanced.cpp",
        "native/generic.cpp",
        "native/loft_seed.cpp",
        "native/component_transform.h",
        "native/assembly_pose.h",
        "tools/test_feedback037_modeling.py",
    )
    report = {
        "work_items": ["BUG-036", "FEAT-030", "BUG-019"],
        "source": git_state(ROOT),
        "source_fingerprints": {name: source_hash(ROOT / name) for name in fingerprint_files},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "calls": [],
        "jobs": [],
        "success": False,
    }
    probe = None
    try:
        async with Client(
            StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
            read_timeout_seconds=130,
        ) as client:
            probe = Probe(client, report, args.output, 180)
            if args.retry:
                await probe.call("creo_startup_status", {"retry": True})
            await wait_for_startup(client, report, args.output)
            for case in args.cases.split(","):
                await {"components": components, "seeds": seeds, "rounds": rounds}[case](probe)
            report["success"] = True
    except Exception as error:
        report["error"] = repr(error)
    finally:
        if probe:
            probe.save()
    return report["success"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="components,seeds,rounds")
    parser.add_argument("--retry", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/feedback037-modeling.json")
    raise SystemExit(0 if asyncio.run(run(parser.parse_args())) else 1)
