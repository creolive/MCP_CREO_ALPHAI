"""Publish sanitized summaries of fresh MCP/native multisection Blend checks.

Requires the five-section smooth report. Includes the three-section straight
report when present; neither failed nor older evidence is silently relabeled.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bridge
from tools.test_multisection_blend import verify_native
from version import VERSION


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    unit = read(ROOT / "build/unit_test_report.json")
    protocol = read(ROOT / "build/mcp_protocol_test.json")
    assert unit["version"] == protocol["server"]["version"] == VERSION
    assert unit["success"] and protocol["session"]["connected"]
    assert len(protocol["tools"]) == 68
    assert protocol["loft_section_count_schema_verified"]
    assert protocol["loft_interpolation_schema_verified"]
    native_sources = sorted(
        p for p in (ROOT / "native").rglob("*") if p.suffix in (".cpp", ".h", ".hpp", ".inc")
    )
    digest = hashlib.sha256()
    for path in native_sources:
        digest.update(path.read_bytes())
    digest.update(json.dumps(bridge.config(), sort_keys=True).encode())
    fingerprint = digest.hexdigest()
    worker_sha = sha(ROOT / "build/creo_worker.exe")
    assert fingerprint == (ROOT / "build/source.sha256").read_text().strip()
    reports = [ROOT / "build/multisection_5_smooth_integration.json"]
    three = ROOT / "build/multisection_3_straight_integration.json"
    if three.exists():
        reports.insert(0, three)
    suites = []
    for path in reports:
        report = read(path)
        count, mode = report["section_count"], report["interpolation"]
        assert report["version"] == VERSION and report["success"], path.name
        assert report["source_file_unchanged"]
        assert report["count_mismatch_rejected"] and report["mode_mismatch_rejected"]
        assert report["native_build"] == {
            "source_fingerprint": fingerprint,
            "worker_sha256": worker_sha,
        }
        cases, succeeded, failed, mutations, rollbacks = {}, 0, 0, 0, 0
        for entry in report["jobs"]:
            job = read(ROOT / "jobs" / entry["job_id"] / "job.json")
            assert job["status"] == ("failed" if entry["expected_failure"] else "succeeded")
            if entry["expected_failure"]:
                failed += 1
                if entry["stage"] == "failed_edit_rollback":
                    assert job["result"]["rollback_succeeded"]
                    setting = job["result"]["loft_checks"]["rollback"]["blend"]
                    assert setting["section_count"] == count and setting["interpolation"] == mode
                    rollbacks += 1
            else:
                succeeded += 1
                if entry["stage"] in (
                    "rect_create",
                    "rect_edit_middle",
                    "foil_create",
                    "foil_edit_middle_plane",
                ):
                    verify_native(job, count, mode)
                    mutations += 1
        assert (succeeded, failed, mutations, rollbacks) == (
            (8, 3, 4, 1) if count == 5 else (4, 3, 2, 1)
        )
        for name, case in report["cases"].items():
            assert case["success"] and case["all_section_geometry"]["success"]
            initial, edited = case["initial"], case["edited"]
            assert initial["blend_feature_id"] == edited["blend_feature_id"]
            assert initial["section_sketch_ids"] == edited["section_sketch_ids"]
            for model in (initial, edited):
                assert model["saved_file_reloaded_and_verified"]
                for phase in ("before_save", "after_reload"):
                    setting = model["native_checks"][phase]["blend"]
                    assert setting["section_count"] == count and setting["interpolation"] == mode
            geometry = case["all_section_geometry"]
            assert len(geometry["sections"]) == count
            for section in geometry["sections"]:
                if name == "airfoil":
                    assert section["max_nearest_profile_distance_mm"] < geometry["tolerance_mm"]
                else:
                    for axis in ("width", "height"):
                        assert (
                            abs(section[axis + "_mm"] - section["requested_size_mm"])
                            < geometry["tolerance_mm"]
                        )
            cases[name] = {
                "success": True,
                "initial_volume_mm3": initial["volume_mm3"],
                "edited_volume_mm3": edited["volume_mm3"],
                "native_blend_feature_preserved": True,
                "all_parameter_sketches_preserved": True,
                "parameter_edit_changes_solid": True,
                "saved_file_reloaded_with_count_and_mode_preserved": True,
                "actual_stl_sections": geometry,
            }
            for key in ("middle_size_mm", "middle_plane_edit", "profile", "rollback_verified"):
                if key in case:
                    cases[name][key] = case[key]
        suites.append(
            {
                "section_count": count,
                "interpolation": mode,
                "successful_native_jobs": succeeded,
                "expected_failure_jobs": failed,
                "saved_file_verified_mutation_jobs": mutations,
                "rollback_verified_jobs": rollbacks,
                "seed_count_mismatch_rejected": True,
                "seed_mode_mismatch_rejected": True,
                "source_seed_file_unchanged": True,
                "cases": cases,
                "private_report_sha256": sha(path),
            }
        )
    public = {
        "name": "MCP_CREO_MechDog",
        "version": VERSION,
        "scope": "new parts from matching-count and matching-mode native solid Blend seeds",
        "tool": "creo_new_loft_part",
        "tool_count": 68,
        "enabled_tool_count": 67,
        "section_count_input_range": [2, 20],
        "input_range_is_not_all_counts_tested": True,
        "direct_loft_creation_enabled": False,
        "complete_creo_coverage": False,
        "native_modeling_validation_version": VERSION,
        "input_validation_version": unit["version"],
        "input_validation_tests": unit["tests_run"],
        "mcp_validation_version": protocol["server"]["version"],
        "mcp_stdio_connected": True,
        "suites": suites,
        "native_source_sha256": {
            p.relative_to(ROOT).as_posix(): sha(p) for p in native_sources if p.suffix != ".inc"
        },
        "native_worker_sha256": worker_sha,
        "tested_environment": {"os": "Windows x64", "creo": "10.0.0.0", "python": "3.12 x64"},
        "limits": [
            "Requires a dedicated saved mm solid Blend seed with the requested section count and interpolation",
            "2 to 20 independent closed XY sketches; offsets strictly increase, seed sketches created and selected low Z first",
            "No seed section insertion/removal, interpolation conversion, existing-target insertion or direct no-seed Blend creation",
            "No nonparallel sections, surface/cut mode or endpoint tangency/curvature controls",
            "Only listed count/mode/profile combinations were tested; other inputs need individual validation",
            "STL section tolerance is a tessellation check, not a guarantee of analytical or aerodynamic accuracy",
        ],
        "evidence_type": "Development-machine MCP/native tests; not verification of another installation",
    }
    (ROOT / "docs/validation_multisection.json").write_text(
        json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "version": VERSION,
                "verified_suites": [
                    {"section_count": s["section_count"], "interpolation": s["interpolation"]}
                    for s in suites
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
