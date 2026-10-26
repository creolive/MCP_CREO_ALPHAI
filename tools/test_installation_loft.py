"""Real MCP regression for seed loading, window activation and optional dimensions.

Run with --seed-library pointing to the extracted official v0.2.4 seed library.
Creates isolated new models. Never resubmit a pending/unknown job.
"""

import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creo_mechdog import inspection_refs, model_registry
from tools.test_loft_seed import sections
from tools.test_multisection_blend import profiles
from version import VERSION


def native_result_details(job: dict) -> tuple[dict, dict]:
    result = job["result"]
    inspection = inspection_refs.full_inspection(result)
    if inspection is None:
        raise AssertionError("Native result has no full inspection evidence")
    return inspection, model_registry.aliases_of(result)


EXTRA_CASES = (
    ("rectangle_empty_A", "two_straight", False, False),
    ("rectangle_explicit_B", "two_straight", True, False),
    ("rectangle_empty_C", "two_straight", False, False),
    ("rectangle_smooth_empty", "two_smooth", False, False),
    ("five_rectangle_empty", "five_smooth", False, False),
    ("five_airfoil_empty", "five_smooth", False, True),
)


def seed_cases(manifest: dict) -> list[tuple[str, str, bool, bool]]:
    baseline = [
        ("matrix_" + seed["name"], seed["name"], False, False)
        for seed in sorted(manifest["seeds"], key=lambda row: row["name"])
    ]
    return baseline + list(EXTRA_CASES)


async def main(library: Path):
    manifest = json.loads((library / "seed_manifest.json").read_text(encoding="utf-8-sig"))
    seeds = {s["name"]: s for s in manifest["seeds"]}
    source_files = {name: library / s["relative_path"] for name, s in seeds.items()}
    hashes = {name: hashlib.sha256(p.read_bytes()).hexdigest() for name, p in source_files.items()}
    assert all(hashes[name] == s["sha256"] for name, s in seeds.items())
    report = {
        "version": VERSION,
        "success": False,
        "cases": {},
        "jobs": [],
        "source_hashes": hashes,
    }
    output = ROOT / "build/installation_loft_validation.json"

    def persist():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:

        async def job(tool, args, expected_failure=False):
            response = await client.call_tool(tool, args)
            if response.is_error:
                raise RuntimeError(str(response))
            jid = response.structured_content["job_id"]
            print(json.dumps({"tool": tool, "job_id": jid}), flush=True)
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                state = (await client.call_tool("creo_get_job", {"job_id": jid})).structured_content
                if state["status"] not in ("queued", "running"):
                    break
                await asyncio.sleep(0.5)
            else:
                raise TimeoutError("Inspect pending job before retrying")
            report["jobs"].append(
                {"job_id": jid, "status": state["status"], "expected_failure": expected_failure}
            )
            persist()
            assert state["status"] == ("failed" if expected_failure else "succeeded"), state.get(
                "message"
            )
            if not expected_failure:
                assert state["result"]["saved_file_reloaded_and_verified"]
            return state

        def check(state, seed, fid=None):
            result = state["result"]
            inspection, aliases = native_result_details(state)
            setting = result["loft_checks"]["after_reload"]["blend"]
            assert setting["interpolation"] == seed["interpolation"]
            assert setting["section_count"] == seed["section_count"]
            actual = aliases["blend"]["feature_id"]
            assert fid is None or actual == fid
            feature = next(f for f in inspection["features"] if f["id"] == actual)
            assert feature["type"] == 917 and feature["status"] == 0 and not feature["incomplete"]
            assert (
                inspection["healthy"]
                and len([b for b in inspection["bodies"] if b["state"] == 4]) == 1
            )
            return actual, feature, inspection["volume_mm3"]

        try:
            for case, name, dimensions, foil in seed_cases(manifest):
                seed = seeds[name]
                count = seed["section_count"]
                ops = sections("rectangle") if count == 2 else profiles(count, foil)[0]
                if not dimensions:
                    for op in ops:
                        op["dimensions"] = []
                args = {
                    "seed_file": str(source_files[name]),
                    "seed_feature_id": seed["seed_feature_id"],
                    "sections": ops,
                    "label": "blend",
                    "interpolation": seed["interpolation"],
                    "assertions": {"require_solid": True},
                }
                if count == 2:
                    args["assertions"]["volume_mm3"] = 7000
                state = await job("creo_new_loft_part", args)
                fid, feature, initial_volume = check(state, seed)
                if dimensions:
                    edit = {
                        "op": "set_sketch_dimensions",
                        "sketch": "top",
                        "values": {"width": 12, "height": 12},
                    }
                    assertions = {"volume_mm3": 7840}
                else:
                    label = "TOP_PLANE" if count == 2 else "SECTION_2_PLANE"
                    inspection, _ = native_result_details(state)
                    plane = next(f for f in inspection["features"] if f["name"] == label)
                    offset = ops[1 if count == 2 else 2]["offset"]
                    dim = next(d for d in plane["dimensions"] if abs(d["value"] - offset) < 1e-7)
                    edit = {
                        "op": "set_dimensions",
                        "values": [{"id": dim["id"], "value": offset + 5}],
                    }
                    assertions = {"require_solid": True}
                    if count == 2:
                        assertions["volume_mm3"] = 7000 * 35 / 30
                edited = await job(
                    "creo_execute_plan",
                    {
                        "model_id": state["model_id"],
                        "expected_revision": state["revision"],
                        "operations": [edit],
                        "assertions": assertions,
                    },
                )
                _, _, edited_volume = check(edited, seed, fid)
                assert abs(edited_volume - initial_volume) > 0.01
                report["cases"][case] = {
                    "success": True,
                    "seed_name": name,
                    "seed_sha256": hashes[name],
                    "job_id": state["job_id"],
                    "edit_job_id": edited["job_id"],
                    "model_id": state["model_id"],
                    "create_revision": state["revision"],
                    "edit_revision": edited["revision"],
                    "native_blend_id": fid,
                    "blend_feature": {
                        "id": feature["id"],
                        "type": feature["type"],
                        "status": feature["status"],
                        "incomplete": feature["incomplete"],
                    },
                    "section_count": count,
                    "interpolation": seed["interpolation"],
                    "initial_volume_mm3": initial_volume,
                    "edited_volume_mm3": edited_volume,
                    "volume_changed_by_edit": True,
                    "parameter_edit": edit,
                    "create_saved_reloaded_verified": state["result"][
                        "saved_file_reloaded_and_verified"
                    ],
                    "edit_saved_reloaded_verified": edited["result"][
                        "saved_file_reloaded_and_verified"
                    ],
                }
                persist()
            invalid = {**args, "seed_feature_id": 2147483647}
            await job("creo_new_loft_part", invalid, expected_failure=True)
            mismatch = {
                **args,
                "interpolation": "smooth" if args["interpolation"] == "straight" else "straight",
            }
            state = await job("creo_new_loft_part", mismatch, expected_failure=True)
            assert "does not match requested interpolation" in state.get("message", "")
            report["source_files_unchanged"] = all(
                hashlib.sha256(p.read_bytes()).hexdigest() == hashes[name]
                for name, p in source_files.items()
            )
            assert report["source_files_unchanged"]
            report["success"] = True
        except Exception as error:
            report["error"] = str(error)
            raise
        finally:
            persist()
    print(
        json.dumps({"success": True, "case_count": len(report["cases"]), "report": str(output)}),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-library", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.seed_library.resolve()))
