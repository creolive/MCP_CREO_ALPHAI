"""Real stdio/native checks. Supply a local Blend seed matching --interpolation."""

import argparse
import asyncio
import hashlib
import json
import math
import sys
import time
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.mcp_readiness import wait_for_startup
from version import VERSION


def sections(shape):
    result = []
    for label, z, side in [("bottom", 0, 20), ("top", 30, 10)]:
        if shape == "rectangle":
            entities = [
                {
                    "type": "rectangle",
                    "name": "profile",
                    "min": [-side / 2, -side / 2],
                    "max": [side / 2, side / 2],
                }
            ]
            dims = [
                {
                    "name": name,
                    "type": "length",
                    "refs": [{"entity": "profile_" + str(i)}],
                    "value": side,
                    "position": [side, side],
                }
                for i, name in enumerate(["width", "height"])
            ]
        elif shape == "circle":
            entities = [{"type": "circle", "name": "profile", "center": [0, 0], "radius": side / 2}]
            dims = []
        else:
            entities = [
                {
                    "type": "polyline",
                    "name": "profile",
                    "points": [[0, 0], [side, 0], [0, side]],
                    "closed": True,
                }
            ]
            dims = []
        result.append(
            {"op": "sketch", "label": label, "offset": z, "entities": entities, "dimensions": dims}
        )
    return result


async def main(seed_file, feature_id, interpolation="straight"):
    source = Path(seed_file).resolve()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    report = {
        "version": VERSION,
        "success": False,
        "interpolation": interpolation,
        "construction": "native_two_section_blend_seed_rebinding",
        "jobs": [],
        "cases": {},
    }
    output = ROOT / (
        "build/loft_smooth_integration.json"
        if interpolation == "smooth"
        else "build/loft_seed_integration.json"
    )
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        await wait_for_startup(client, report, output)

        async def job(tool, args, fail=False, rollback=False):
            response = await client.call_tool(tool, args)
            if response.is_error:
                raise RuntimeError(str(response))
            jid = response.structured_content["job_id"]
            print(json.dumps({"tool": tool, "job_id": jid}), flush=True)
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                r = (await client.call_tool("creo_get_job", {"job_id": jid})).structured_content
                if r["status"] in ("succeeded", "failed", "unknown_outcome"):
                    break
                await asyncio.sleep(0.5)
            else:
                raise TimeoutError("Inspect pending job; do not resubmit")
            native_build = {
                "source_fingerprint": (ROOT / "build/source.sha256").read_text().strip(),
                "worker_sha256": hashlib.sha256(
                    (ROOT / "build/creo_worker.exe").read_bytes()
                ).hexdigest(),
            }
            assert report.get("native_build", native_build) == native_build, (
                "Native build changed during integration test"
            )
            report["native_build"] = native_build
            report["jobs"].append({"job_id": jid, "status": r["status"], "expected_failure": fail})
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            if fail:
                assert r["status"] == "failed", r.get("message")
                if rollback:
                    assert r["result"]["rollback_succeeded"], r.get("message")
                if rollback:
                    assert (
                        r["result"]["loft_checks"]["rollback"]["blend"]["interpolation"]
                        == interpolation
                    )
            else:
                assert (
                    r["status"] == "succeeded" and r["result"]["saved_file_reloaded_and_verified"]
                ), r.get("message")
                for phase in ["before_save", "after_reload"]:
                    setting = r["result"]["loft_checks"][phase]["blend"]
                    assert (
                        setting["interpolation"] == interpolation and setting["section_count"] == 2
                    )
                assert r["result"]["aliases"]["blend"]["interpolation"] == interpolation
            return r

        for shape, expected in [
            ("rectangle", 7000),
            ("circle", 1750 * math.pi),
            ("triangle", 3500),
        ]:
            p = await job(
                "creo_new_loft_part",
                {
                    "seed_file": str(source),
                    "seed_feature_id": feature_id,
                    "sections": sections(shape),
                    "label": "blend",
                    "interpolation": interpolation,
                    "assertions": {"volume_mm3": expected, "require_solid": True},
                },
            )
            alias = p["result"]["aliases"]["blend"]
            native = next(
                f for f in p["result"]["inspection"]["features"] if f["id"] == alias["feature_id"]
            )
            assert native["status"] == 0 and not native["incomplete"]
            assert not any(
                f["name"] in ("LOFT_BOTTOM", "LOFT_TOP")
                for f in p["result"]["inspection"]["features"]
            )
            report["cases"][shape] = {
                "success": True,
                "model_id": p["model_id"],
                "part_file": p["result"]["part_file"],
                "native_blend_id": alias["feature_id"],
                "volume_mm3": p["result"]["inspection"]["volume_mm3"],
                "interpolation_verified": interpolation,
            }
            if shape == "rectangle":
                p = await job(
                    "creo_execute_plan",
                    {
                        "model_id": p["model_id"],
                        "expected_revision": p["revision"],
                        "operations": [
                            {
                                "op": "set_sketch_dimensions",
                                "sketch": "top",
                                "values": {"width": 12, "height": 12},
                            }
                        ],
                        "assertions": {"volume_mm3": 7840},
                    },
                )
                report["cases"][shape]["edited_volume_mm3"] = p["result"]["inspection"][
                    "volume_mm3"
                ]
                await job(
                    "creo_execute_plan",
                    {
                        "model_id": p["model_id"],
                        "expected_revision": p["revision"],
                        "operations": [
                            {
                                "op": "set_sketch_dimensions",
                                "sketch": "top",
                                "values": {"width": 15},
                            }
                        ],
                        "assertions": {"volume_mm3": 1},
                    },
                    fail=True,
                    rollback=True,
                )
                p = await job(
                    "creo_execute_plan",
                    {
                        "model_id": p["model_id"],
                        "expected_revision": p["revision"],
                        "operations": [
                            {
                                "op": "sketch",
                                "label": "hole_profile",
                                "entities": [
                                    {
                                        "type": "circle",
                                        "name": "circle",
                                        "center": [0, 0],
                                        "radius": 1,
                                    }
                                ],
                            },
                            {
                                "op": "extrude",
                                "label": "through_cut",
                                "sketch": "hole_profile",
                                "depth": 30,
                                "mode": "cut",
                            },
                        ],
                        "assertions": {"volume_mm3": 7840 - 30 * math.pi},
                    },
                )
                report["cases"][shape]["edited_and_cut_part"] = p["result"]["part_file"]
                report["cases"][shape]["edited_and_cut_volume_mm3"] = p["result"]["inspection"][
                    "volume_mm3"
                ]

        async def rejected(args, expected):
            """B1: an incompatible explicit seed is refused before any job is queued."""
            response = await client.call_tool("creo_new_loft_part", args)
            assert response.is_error, response.structured_content
            message = " ".join(
                item.text for item in response.content if getattr(item, "text", None)
            )
            assert "Seed preflight rejected before any job was submitted" in message, message
            assert expected in message, message
            assert "job_id" not in (response.structured_content or {}), response.structured_content
            report.setdefault("preflight_rejections", []).append(
                {"input": args, "is_error": True, "message": message}
            )
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            return message

        await rejected(
            {
                "seed_file": str(source),
                "seed_feature_id": 2147483647,
                "sections": sections("rectangle"),
                "interpolation": interpolation,
            },
            "seed_feature_id 2147483647 does not match the manifest id",
        )
        await rejected(
            {
                "seed_file": str(source),
                "seed_feature_id": feature_id,
                "sections": sections("rectangle"),
                "interpolation": "straight" if interpolation == "smooth" else "smooth",
            },
            "Seed interpolation is",
        )
        report["mismatched_seed_rejected"] = True
        report["source_file_unchanged"] = hashlib.sha256(source.read_bytes()).hexdigest() == digest
        assert report["source_file_unchanged"]
        report["success"] = True
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps({"success": True, "cases": report["cases"]}, ensure_ascii=False), flush=True
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed-file", required=True)
    p.add_argument("--feature-id", required=True, type=int)
    p.add_argument("--interpolation", choices=["straight", "smooth"], default="straight")
    a = p.parse_args()
    asyncio.run(main(a.seed_file, a.feature_id, a.interpolation))
