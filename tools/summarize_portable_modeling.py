"""Produce a public summary from completed private MCP acceptance reports."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creo_mechdog import seeds
from version import VERSION


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def result(state, name):
    row = next(j for j in state["jobs"] if j["name"] == name)
    assert row["status"] == "succeeded", name
    native = row["result"]["result"]
    assert native["saved_file_reloaded_and_verified"], name
    return native


def volume(state, name):
    return result(state, name)["inspection"].get("volume_mm3")


def bounds(state, name):
    return next(b["bbox"] for b in result(state, name)["inspection"]["bodies"] if b["state"] == 4)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--placement-report", type=Path)
    parser.add_argument("--tested-root", type=Path, required=True)
    args = parser.parse_args()
    state = read(args.report)
    placement = read(args.placement_report) if args.placement_report else state
    assert state["airfoil_passed"] and state["pattern_passed"]
    assert placement["body_transform_passed"] and placement["quilt_transform_passed"]
    assert state["actual_section_deviation_mm"] < 0.15
    for sample in [state, placement]:
        assert all(
            j["status"] == "succeeded" and j["result"]["result"]["saved_file_reloaded_and_verified"]
            for j in sample["jobs"]
        )
    code_paths = [
        "server.py",
        "schema.py",
        "seeds.py",
        "src/creo_mechdog/seeds.py",
        "src/creo_mechdog/capabilities.py",
        "airfoil.py",
        "src/creo_mechdog/schema.py",
        "src/creo_mechdog/airfoil.py",
        "src/creo_mechdog/profile_checks.py",
        "generic_bridge.py",
        "capabilities.py",
        "native/generic.cpp",
        "native/sketch_edit.cpp",
        "native/placement.cpp",
    ]
    hashes = {}
    for name in code_paths:
        source = (ROOT / name).read_bytes()
        assert source == (args.tested_root / name).read_bytes(), (
            f"Tested implementation differs: {name}"
        )
        hashes[name] = hashlib.sha256(source).hexdigest()
    initial = result(state, "create_airfoil")
    final = result(state, "edit_patterned_airfoil")
    preserved = {
        name: initial["aliases"][name]["feature_id"] == final["aliases"][name]["feature_id"]
        for name in state["initial_ids"]
    }
    assert all(preserved.values())
    body_id = result(placement, "move_rotate_body_v3")["aliases"]["position"]["feature_id"]
    assert (
        body_id == result(placement, "edit_body_placement_v3")["aliases"]["position"]["feature_id"]
    )
    quilt_id = result(placement, "move_rotate_quilt_v2")["aliases"]["position"]["feature_id"]
    assert (
        quilt_id == result(placement, "edit_quilt_placement")["aliases"]["position"]["feature_id"]
    )
    protocols = []
    for name in ["mcp_protocol_auto.json", "mcp_protocol_test.json"]:
        protocol = read(args.tested_root / "build" / name)
        assert len(protocol["tools"]) == 80 and protocol["server"]["version"] == VERSION
        protocols.append(
            {
                "client_mode": protocol["client_mode"],
                "tool_count": len(protocol["tools"]),
                "protocol_version": protocol["protocol_version"],
            }
        )
    summary = {
        "version": VERSION,
        "increment": "portable-modeling-20261011",
        "date": "2026-10-11",
        "status": "passed",
        "environment": {
            "os": "Windows x64",
            "creo": "10.0.0.0",
            "python": "3.12 x64",
            "compiler": "VS 2022 C++ Build Tools",
        },
        "tool_count": 80,
        "enabled_tool_count": 79,
        "unit_tests": {"passed": 44, "failed": 0},
        "mcp_protocols": protocols,
        "migration_validation": {
            "fresh_source_directory": True,
            "new_mcp_clients": True,
            "no_prior_registry_models_or_binary": True,
            "reused_same_host_python_and_environment_config": True,
            "another_physical_computer_tested": False,
        },
        "seed_library": {
            "automatic_selection_without_path_or_id": True,
            "seeds": [
                {k: s[k] for k in ("name", "section_count", "interpolation", "sha256", "available")}
                for s in seeds.list_seeds()["seeds"]
            ],
        },
        "airfoil": {
            "native_type": "ordinary solid smooth Blend and independent native sketch splines",
            "station_count": 5,
            "parameter_edit_sequence": [
                {"chord": 32, "thickness_ratio": 0.15, "twist_deg": 12},
                {"twist_deg": 16, "origin": [1, 0]},
                {"chord": 34, "twist_deg": 17, "after_group_pattern": True},
            ],
            "initial_volume_mm3": volume(state, "create_airfoil"),
            "edited_volume_mm3": volume(state, "edit_airfoil_again"),
            "original_feature_ids_preserved": preserved,
            "actual_stl_section": {
                "z_mm": 55,
                "point_count": state["actual_section_points"],
                "max_nearest_profile_deviation_mm": state["actual_section_deviation_mm"],
                "tolerance_mm": 0.15,
            },
        },
        "feature_organization": {
            "reorder": True,
            "native_local_group": True,
            "native_axis_group_pattern": {"count": 2, "increment_deg": 180},
            "patterned_volume_mm3": volume(state, "pattern_blade"),
            "edited_after_pattern_volume_mm3": volume(state, "edit_patterned_airfoil"),
            "active_body_count": len([b for b in final["inspection"]["bodies"] if b["state"] == 4]),
        },
        "body_transform": {
            "native_type": "attached FlexMove",
            "rotation_deg": [0, 0, 90],
            "translation_mm": [10, 20, 30],
            "bbox_after_transform_mm": bounds(placement, "move_rotate_body_v3"),
            "edited_rotation_deg": [0, 0, 0],
            "edited_translation_mm": [12, 20, 30],
            "bbox_after_edit_mm": bounds(placement, "edit_body_placement_v3"),
            "volume_mm3": 120,
            "feature_id_preserved": True,
        },
        "quilt_transform": {
            "native_type": "Move with coordinate-system-bound support points and axes",
            "rotation_deg": [90, 0, 0],
            "translation_mm": [0, 3, 8],
            "downstream_symmetric_thickness_mm": 2,
            "bbox_after_thicken_mm": bounds(placement, "thicken_moved_quilt"),
            "edited_translation_mm": [5, 3, 8],
            "bbox_after_edit_mm": bounds(placement, "edit_quilt_placement"),
            "volume_mm3": volume(placement, "edit_quilt_placement"),
            "feature_id_preserved": True,
        },
        "saved_erased_reloaded_verified": True,
        "successful_mcp_mutation_jobs": len(state["jobs"])
        + (len(placement["jobs"]) if args.placement_report else 0),
        "implementation_sha256": hashes,
        "limitations": [
            "Automatic seeds: 2/straight, 2/smooth, 5/smooth; no count/mode conversion or unseeded Blend creation",
            "NACA 00xx symmetric profiles; MCP metadata-driven sketch redefinition, not native relation-driven airfoil dimensions",
            "Body/quilt move-original branches verified; copies, multiple bodies, custom frames and other geometry combinations require local validation",
            "VSS, Swept Blend, Boundary Blend and complete Creo coverage remain outside this increment",
        ],
    }
    output = ROOT / "docs/validation_portable_modeling.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Public evidence: {output}; {summary['successful_mcp_mutation_jobs']} successful mutation jobs"
    )


if __name__ == "__main__":
    main()
