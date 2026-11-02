"""Summarize development evidence without relabeling the published 0.21 results."""

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS, families
from version import VERSION


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    reports = {
        name: read(ROOT / "build" / name)
        for name in [
            "development_integration.json",
            "surface_integration.json",
            "udf_integration.json",
            "unit_test_report.json",
            "mcp_protocol_test.json",
        ]
    }
    correction_file = ROOT / "build" / f"version_label_correction_{VERSION}.json"
    correction = read(correction_file) if correction_file.is_file() else None
    modeling_reports = {
        "development_integration.json",
        "surface_integration.json",
        "udf_integration.json",
    }
    inherited_evidence = False
    for name, value in reports.items():
        actual_version = value.get("server", value).get("version")
        if actual_version != VERSION:
            assert (
                name in modeling_reports
                and correction
                and correction["to_version"] == VERSION
                and correction["from_version"] == actual_version
            ), (name, "version mismatch")
            assert (
                hashlib.sha256((ROOT / "build" / name).read_bytes()).hexdigest()
                == correction["modeling_report_sha256"][name]
            ), (name, "modeling report changed")
            for filename, digest in correction["runtime_sha256"].items():
                assert hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == digest, (
                    filename,
                    "runtime changed; rerun native tests",
                )
            inherited_evidence = True
    drawing = reports["development_integration.json"]
    surface = reports["surface_integration.json"]
    udf = reports["udf_integration.json"]
    unit = reports["unit_test_report.json"]
    protocol = reports["mcp_protocol_test.json"]
    assert drawing["success"] and udf["success"] and unit["success"]
    required = {"datums", "thicken", "union", "subtract", "intersect", "solidify", "rib"}
    assert all(surface["cases"].get(c, {}).get("success") for c in required)
    assert protocol["session"]["connected"] and len(protocol["tools"]) == 68
    entries = [*drawing["jobs"], *udf["jobs"]]
    for c in required:
        entries.extend(
            {"job_id": j, "expected_failure": False} for j in surface["cases"][c]["jobs"]
        )
    unique = {}
    expected_failures = []
    operations = set()
    mutations = 0
    for entry in entries:
        jid = entry["job_id"]
        job = read(ROOT / "jobs" / jid / "job.json")
        if entry.get("expected_failure"):
            assert job["status"] == "failed" and job["result"]["rollback_succeeded"], jid
            expected_failures.append(jid)
            continue
        assert job["status"] == "succeeded", jid
        unique[jid] = job
    for job in unique.values():
        if not job["readonly"]:
            assert job["result"]["saved_file_reloaded_and_verified"], job["job_id"]
            mutations += 1
        operations.update(op["op"] for op in job["operations"])
    result = {
        "name": "MCP_CREO_MechDog",
        "version": VERSION,
        "generated_at": time.time(),
        "complete_creo_coverage": False,
        "all_selected_development_suites_passed": True,
        "tool_count": len(protocol["tools"]),
        "enabled_tool_count": len(protocol["tools"]) - len(UNAVAILABLE_OPERATIONS),
        "registered_operation_count": len(REGISTERED_OPERATIONS),
        "enabled_operation_count": len(REGISTERED_OPERATIONS) - len(UNAVAILABLE_OPERATIONS),
        "successful_native_jobs": len(unique),
        "saved_file_verified_mutation_jobs": mutations,
        "input_validation_tests": unit["tests_run"],
        "verified_operations": sorted(operations),
        "expected_rollback_failures_verified": len(expected_failures),
        "families": families(),
        "unavailable_operations": UNAVAILABLE_OPERATIONS,
        "historical_evidence": "validation_0.21.json; old release tests excluded from development counts",
        "baseline_regression_scope": "Development tests also exercise sketch, extrusion, dimensions, regeneration and checkpoint rollback. Full 0.21 integration suites were not rerun for this development build.",
        "tested_environment": {
            "os": "Windows x64",
            "creo": "10.0.0.0",
            "python": "3.12 x64",
            "compiler": "Visual Studio 2022 C++ Build Tools",
        },
        "pdf_visual_review": drawing.get("pdf_visual_review", {"rendered_and_reviewed": False}),
        "udf_test": {
            "variable_diameter_mm": [10, 20],
            "remaining_volumes_mm3": [udf["volume_before"], udf["volume_after"]],
        },
        "evidence_type": "Development-machine native tests; not verification of another installation",
    }
    if inherited_evidence:
        result["version_label_correction_only"] = True
        result["modeling_validation_version"] = correction["from_version"]
        result["validation_note"] = (
            f"The release label is {VERSION}. Native modeling evidence retains its original development version and applies to byte-identical modeling runtime. Input validation and MCP version/connection checks were rerun for {VERSION}."
        )
    (ROOT / "docs/validation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "docs/validation_development.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    result["jobs"] = list(unique)
    result["expected_failure_jobs"] = expected_failures
    result["native_worker_sha256"] = hashlib.sha256(
        (ROOT / "build/creo_worker.exe").read_bytes()
    ).hexdigest()
    (ROOT / "build/capability_evidence.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "version",
                    "tool_count",
                    "successful_native_jobs",
                    "saved_file_verified_mutation_jobs",
                    "input_validation_tests",
                    "expected_rollback_failures_verified",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
