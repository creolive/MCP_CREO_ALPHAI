"""Summarize actual version-matched reports; never re-label historical tests."""

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creo_mechdog.capabilities import UNAVAILABLE_OPERATIONS, families
from version import VERSION


def load(name, protocol=False):
    value = json.loads((ROOT / "build" / name).read_text(encoding="utf-8"))
    version = value.get("server", {}).get("version") if protocol else value.get("version")
    if version != VERSION:
        raise ValueError(f"{name} is for {version}, expected {VERSION}; run its tests first")
    return value


def main():
    if VERSION != "0.21":
        from summarize_development import main as summarize_current

        return summarize_current()
    core = load("general_integration_test.json")
    extended = load("extended_integration_test.json")
    guards = load("guards_integration_test.json")
    advanced = load("v021_integration_test.json")
    protocol = load("mcp_protocol_test.json", True)
    unit = load("unit_test_report.json")
    for name, value in [("core", core), ("extended", extended), ("guards", guards), ("unit", unit)]:
        if not value.get("success"):
            raise ValueError(f"{name} tests did not all pass")
    required = {
        "mirror",
        "draft",
        "sweep",
        "sheetmetal_wall",
        "sheetmetal",
        "assembly",
        "disabled_tools",
    }
    if any(not advanced["cases"].get(n, {}).get("success") for n in required):
        raise ValueError("A required 0.21 test case has not passed")
    if not protocol["session"]["connected"] or len(protocol["tools"]) != 47:
        raise ValueError("MCP protocol/session check did not pass")
    expected_extended = {
        "shell",
        "outward_shell",
        "edges",
        "pattern",
        "curves",
        "spline",
        "thin",
        "cut",
        "pocket",
        "relations",
        "datum",
        "constraints",
        "oblique",
        "partial",
        "dimensions",
        "directions",
        "revolve_modes",
        "export",
    }
    if any(not extended.get("case_results", {}).get(n) for n in expected_extended):
        raise ValueError("Extended report is incomplete; run all extended cases")
    jobs = [c["job"] for report in (core, extended) for c in report["cases"]]
    jobs += [j for n in required for j in advanced["cases"][n].get("jobs", [])]
    jobs += [guards["refresh_job"]]
    unique = {j["job_id"]: j for j in jobs if j["status"] == "succeeded"}
    operations = {}
    mutation_count = 0
    for job in unique.values():
        request = json.loads(
            (Path(job["job_directory"]) / "request.json").read_text(encoding="utf-8")
        )
        if not request.get("readonly", False):
            if not job["result"].get("saved_file_reloaded_and_verified"):
                raise ValueError(f"Mutation {job['job_id']} lacks saved-file verification")
            mutation_count += 1
        for op in job.get("operations", []):
            operations.setdefault(op["op"], []).append(job["job_id"])
    incomplete = [
        "loft",
        "variable/helical sweep",
        "feature/subtree mirror",
        "rib",
        "standard threaded/counterbore/countersink holes",
        "advanced sheetmetal forms and bend tables",
        "nested assembly copying and source-linked updates",
        "drawing/MBD",
        "manufacturing, mold, simulation and cabling modules",
    ]
    branches = [
        "native metric sketches and dependent features, explicit dimensions and horizontal/vertical constraints",
        "line, centerline, rectangle, closed polyline, circle, arc, ellipse and spline entities",
        "principal and oblique sketch supports; offset/angled datum plane; two-plane datum axis",
        "add/cut/surface/thin extrusion, through cut, blind pocket, symmetric depth, negative direction, new bodies",
        "full/partial/symmetric revolve, external-axis revolve, revolved groove, surface and thin revolve",
        "straight through and blind holes; constant edge rounds, equal chamfers, inward/outward shell",
        "one-direction dimension pattern; feature and named sketch dimensions; parameters and arithmetic relations",
        "whole-solid mirror with retained original; straight-trajectory circular constant sweep and diameter 4 to 6 edit",
        "constant 3 degree unsplit planar draft",
        "native sheetmetal conversion from a 40 x 30 x 1 first wall, 90 degree flange with R2/R3 bend",
        "flange named height 15 to 20 edit, unbend, bend-back and flat pattern with saved-file reload at each step",
        "assembly part snapshots, rigid placement, removal, datum-plane constraints, named component references, 20 mm offset",
        "source file unaffected by insertion, source depth edit changes source volume but preserves assembly snapshot volume",
        "symbolic feature tree and XML dump; STEP/STL/IGES/JPEG export from a part",
        "stale edit rejection; partial failed mutation restores file hash, revision, live geometry and parameters",
    ]
    evidence = {
        "name": "MCP_CREO_MechDog",
        "version": VERSION,
        "generated_at": time.time(),
        "all_selected_test_suites_passed": True,
        "complete_creo_coverage": False,
        "all_requested_families_verified": False,
        "protocol": protocol["protocol_version"],
        "tool_count": 47,
        "enabled_tool_count": 47 - len(UNAVAILABLE_OPERATIONS),
        "successful_native_jobs": len(unique),
        "saved_file_verified_mutation_jobs": mutation_count,
        "input_validation_tests": unit["tests_run"],
        "verified_operations": {k: list(dict.fromkeys(v)) for k, v in sorted(operations.items())},
        "verified_branches": branches,
        "families": families(),
        "unavailable_operations": UNAVAILABLE_OPERATIONS,
        "not_high_level_implemented": incomplete,
        "not_individually_verified": [
            "all geometry/reference combinations",
            "all dimension/constraint combinations",
            "every sweep mode and trajectory",
            "sheetmetal angles/flip/partial bend references/multiple flanges",
            "mate/insert/csys/default assembly constraints",
            "assembly export format combinations",
        ],
        "expected_failure_checks": {
            "disabled_loft_rejected_before_queue": True,
            "stale_revision_rejected": guards["stale_revision_rejected"],
            "partial_mutation_rollback_verified": guards["rollback_succeeded"],
        },
        "test_reports": [
            "general_integration_test.json",
            "extended_integration_test.json",
            "guards_integration_test.json",
            "v021_integration_test.json",
            "mcp_protocol_test.json",
            "unit_test_report.json",
        ],
        "native_worker_sha256": hashlib.sha256(
            (ROOT / "build/creo_worker.exe").read_bytes()
        ).hexdigest(),
    }
    correction = ROOT / "build" / f"version_correction_{VERSION}.json"
    if correction.is_file():
        checked = load("mcp_version_validation.json")
        if not checked.get("success"):
            raise ValueError("Corrected MCP version has not been verified")
        evidence["version_label_correction_only"] = True
        evidence["validation_note"] = (
            "Only the release label was corrected. Native modeling evidence is retained from the same modeling implementation; input validation and MCP version checks were rerun."
        )
    (ROOT / "build/capability_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    public = {
        k: v for k, v in evidence.items() if k not in ("native_worker_sha256", "test_reports")
    }
    public["verified_operations"] = list(evidence["verified_operations"])
    public["evidence_type"] = (
        "Development-machine validation for this source version; not verification of another installation"
    )
    public["tested_environment"] = {
        "os": "Windows x64",
        "creo": "10.0.0.0",
        "python": "3.12 x64",
        "compiler": "Visual Studio 2022 C++ Build Tools",
    }
    public["historical_evidence"] = "validation_0.2.0.json; excluded from 0.21 counts"
    (ROOT / "docs/validation.json").write_text(
        json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"Version {VERSION}: {len(unique)} native jobs, {mutation_count} saved-file mutations, {unit['tests_run']} input tests; full coverage=False"
    )


if __name__ == "__main__":
    main()
