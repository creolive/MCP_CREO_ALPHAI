"""FEAT-052 live assembly family-recolor integration scenario.

Covers the live acceptance items of
docs/superpowers/plans/2026-10-31-assembly-recolor-plan.md ("验收"):
build an 80-component / 12-family fixture with the proposal's family table
and RGB values, recolor it once through automatic source grouping and once
through an explicit family table, verify the saved/erase/reloaded colors
(readback abs err <= 1e-6), the unchanged source part file SHA256s and the
unchanged component identity/pose/constraints/geometry, recolor again with a
third palette, change one component placement + save and prove the colors
survive, and roll two deliberately failing plans back to the captured
appearance baseline (once onto components with NO component-level appearance,
once onto previously painted colors).

The 12 family RGB values and the 12 expected counts are taken verbatim from
the external proposal package (recolor_worker.cpp g_families and its 80-entry
component schedule); they are fixture truth data only. The executor NEVER
receives them: every recolor goes through explicit label assignments (the
native side refuses visit-order or name-prefix family guessing).

Tool surface used (Python side of FEAT-052): ``creo_recolor_assembly``
(model_id, expected_revision, palette, families, ...) per the plan's MCP
interface, plus the ``recolor_assembly`` plan operation for ``creo_execute_plan``
(same families/palette form; the Python adapter translates it into the native
``assignments`` payload). Component appearance is read through the public
component check (``creo_list_components``), where every component entry carries
the three-state ``appearance`` record {state, rgb, query_code}. The recolor
evidence block is read from the job result (``result.recolor`` or the owning
entry of ``result.operations``).

Run only after independently verifying session health and authorization under
AGENTS.md (same conditions as tools/test_assembly_pipeline.py). The script
never erases the session, recovers unknown outcomes, retries rejected
submissions, or injects failures beyond the two in-plan rollback scenarios
(whose failing operation is a plain double remove_component). WorkBuddy
acceptance is a separate pure-MCP activity.

THIS PHASE: written offline only. It must NOT be executed until the FEAT-052
Python side lands and the BUG-001/BUG-091 session admission rules are met.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bridge
from creo_mechdog.paths import SOURCE_PATHS
from creo_mechdog.schema import validate_operations
from tools.mcp_readiness import wait_for_startup
from tools.test_assembly_matrix import compact_inspection

ROOT = SOURCE_PATHS.resource_root
SUFFIX_LENGTH = 8
READBACK_TOLERANCE = 1e-6

# Family truth data from the external proposal package (family_table.json and
# g_families): one RGB per family and the 80-component family schedule of the
# fixture assembly. Family labels here are fixture bookkeeping only; the
# automatic round groups by source_model_id and the explicit round uses the
# exp_* names below.
FAMILIES = [
    {"key": "crank_orange", "rgb": [0.85, 0.32, 0.10]},
    {"key": "frame_blue", "rgb": [0.30, 0.32, 0.90]},
    {"key": "shaft_green", "rgb": [0.10, 0.62, 0.30]},
    {"key": "pin3_yellow", "rgb": [0.95, 0.80, 0.10]},
    {"key": "pin4_purple", "rgb": [0.55, 0.10, 0.75]},
    {"key": "rod_c_red", "rgb": [0.90, 0.15, 0.20]},
    {"key": "rod_f_orange", "rgb": [0.95, 0.45, 0.10]},
    {"key": "rod_j_sky", "rgb": [0.15, 0.55, 0.85]},
    {"key": "rod_k_khaki", "rgb": [0.85, 0.75, 0.20]},
    {"key": "tri_ebd_green", "rgb": [0.20, 0.75, 0.45]},
    {"key": "tri_igh_mauve", "rgb": [0.60, 0.25, 0.60]},
    {"key": "fan_grey", "rgb": [0.45, 0.47, 0.52]},
]
EXPECTED_COUNTS = [1, 4, 2, 18, 6, 6, 6, 6, 6, 12, 12, 1]
# 80-component family schedule from the proposal's family_table.json: the n-th
# assembled component c01..c80 belongs to family g_comp_family[n-1].
COMPONENT_FAMILY = [
    9,
    10,
    10,
    3,
    9,
    6,
    5,
    4,
    3,
    3,
    11,
    10,
    3,
    10,
    3,
    3,
    4,
    7,
    8,
    3,
    9,
    3,
    10,
    3,
    7,
    4,
    6,
    3,
    9,
    10,
    4,
    3,
    3,
    7,
    8,
    3,
    3,
    8,
    10,
    3,
    9,
    6,
    5,
    9,
    5,
    9,
    7,
    10,
    10,
    9,
    9,
    6,
    10,
    3,
    8,
    5,
    10,
    3,
    9,
    4,
    9,
    6,
    7,
    5,
    8,
    3,
    1,
    0,
    1,
    4,
    9,
    1,
    5,
    2,
    6,
    10,
    7,
    2,
    1,
    8,
]
assert len(COMPONENT_FAMILY) == 80
assert [COMPONENT_FAMILY.count(i) for i in range(12)] == EXPECTED_COUNTS

# Explicit round: crank (family 0) and fan (family 11) share one family, every
# other source keeps its own family ("显式合族" coverage).
MERGED_FAMILY = "exp_crank_fan"
MERGED_MEMBERS = (0, 11)


def short_suffix(tag: str) -> str:
    return hashlib.sha256(tag.encode("utf-8")).hexdigest()[:SUFFIX_LENGTH]


def source_model_name(tag: str, family: int) -> str:
    return bridge.normalize_model_name(f"recolor_src_{family:02d}_{short_suffix(tag)}")


def assembly_name(tag: str) -> str:
    return bridge.normalize_model_name(f"recolor_asm_{short_suffix(tag)}")


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


def component_labels() -> list[str]:
    return [f"c{index + 1:02d}" for index in range(80)]


def labels_by_family() -> dict[int, list[str]]:
    grouped: dict[int, list[str]] = {}
    for index, family in enumerate(COMPONENT_FAMILY):
        grouped.setdefault(family, []).append(f"c{index + 1:02d}")
    return grouped


def assemble_operations(source_ids: list[str]) -> list[dict]:
    """One fixed-placement component per schedule entry, laid out on a grid."""
    operations = []
    for index, family in enumerate(COMPONENT_FAMILY):
        operations.append(
            {
                "op": "assemble_component",
                "label": f"c{index + 1:02d}",
                "source_model_id": source_ids[family],
                "translation": [40.0 * (index % 10), 40.0 * (index // 10), 0],
                "placement": "fixed",
            }
        )
    return operations


def explicit_families() -> dict[str, list[str]]:
    grouped = labels_by_family()
    families: dict[str, list[str]] = {}
    for family, members in grouped.items():
        name = MERGED_FAMILY if family in MERGED_MEMBERS else f"exp_fam_{family:02d}"
        families.setdefault(name, []).extend(members)
    return families


def explicit_palette(shift: bool) -> dict[str, list[float]]:
    palette: dict[str, list[float]] = {}
    for family, spec in enumerate(FAMILIES):
        rgb = spec["rgb"]
        if shift:
            rgb = [rgb[1], rgb[2], rgb[0]]
        name = MERGED_FAMILY if family in MERGED_MEMBERS else f"exp_fam_{family:02d}"
        palette.setdefault(name, rgb)
    return palette


def expected_explicit_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for family, count in enumerate(EXPECTED_COUNTS):
        name = MERGED_FAMILY if family in MERGED_MEMBERS else f"exp_fam_{family:02d}"
        counts[name] = counts.get(name, 0) + count
    return counts


def rgb_close(actual, expected, tolerance=READBACK_TOLERANCE) -> bool:
    if not isinstance(actual, list) or len(actual) != 3:
        return False
    return all(abs(a - b) <= tolerance for a, b in zip(actual, expected))


def appearance_matches(record, rgb) -> bool:
    return (
        isinstance(record, dict)
        and record.get("state") == "present"
        and rgb_close(record.get("rgb"), rgb)
    )


async def run() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = stamp + uuid.uuid4().hex[:8]
    destination = ROOT / f"build/assembly_appearance_live_{tag}/report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "work_items": ["FEAT-052"],
        "source_fingerprints": {},
        "fixture_tag": tag,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "calls": [],
        "jobs": [],
        "checks": [],
        "success": False,
        "session_health": "operator attested before invocation",
        "workbuddy": "not performed by this developer integration script",
        "untested": [
            "busy / concurrent channel interleaving",
            "dry_run preview, pagination and cursor invalidation (offline unit scope)",
            "invalid input rejection (Python-side admission, offline unit scope)",
            "readback error / mismatch fault injection (offline controlled cases)",
            "on-screen visual appearance (operator eyes, WorkBuddy acceptance)",
            "all Creo versions other than the live session",
        ],
    }

    def save():
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    checks: list[dict] = report["checks"]

    def check(name: str, ok: bool, detail="") -> bool:
        entry = {"name": name, "ok": bool(ok), "detail": detail}
        checks.append(entry)
        save()
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail and not ok else ""))
        return bool(ok)

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        mode="legacy",
        read_timeout_seconds=120,
    ) as client:

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
            deadline = asyncio.get_running_loop().time() + 900
            while asyncio.get_running_loop().time() < deadline:
                result = await call("creo_get_job", {"job_id": created["job_id"], "detail": "full"})
                if result["status"] not in ("queued", "running"):
                    break
                await asyncio.sleep(1)
            else:
                raise TimeoutError("Poll existing job only; do not resubmit")
            report["jobs"].append(result)
            save()
            return result

        async def succeeded_job(name, arguments):
            result = await job(name, arguments)
            assert result["status"] == "succeeded", result
            payload = result["result"]
            assert payload["saved_file_reloaded_and_verified"] is True, result
            if "expected_revision" in arguments:
                assert result["revision"] == arguments["expected_revision"] + 1, result
            return result

        def recolor_block(payload) -> dict:
            block_json = payload.get("recolor")
            if isinstance(block_json, dict):
                return block_json
            for entry in payload.get("operations", []):
                if entry.get("op") == "recolor_assembly" and isinstance(entry.get("recolor"), dict):
                    return entry["recolor"]
            raise AssertionError(f"no recolor block in job result: {json.dumps(payload)[:2000]}")

        def identity_snapshot(listed: dict) -> dict:
            aliases = listed["aliases"]
            by_feature = {c["feature_id"]: c for c in listed["components"]}
            snapshot = {}
            for label, alias in aliases.items():
                component = by_feature[alias["feature_id"]]
                snapshot[label] = {
                    "feature_id": alias["feature_id"],
                    "model_name": component["model_name"],
                    "model_type": component["model_type"],
                    "transform": component["transform"],
                    "constraints": component["constraints"],
                }
            return snapshot

        def identity_matches(snapshot: dict, listed: dict, moved: set[str] = ()) -> bool:
            current = identity_snapshot(listed)
            if set(current) != set(snapshot):
                return False
            for label, before in snapshot.items():
                after = current[label]
                same = (
                    after["feature_id"] == before["feature_id"]
                    and after["model_name"] == before["model_name"]
                    and after["model_type"] == before["model_type"]
                    and after["constraints"] == before["constraints"]
                )
                if not same:
                    return False
                if label in moved:
                    continue
                if not all(
                    abs(a - b) <= 1e-6
                    for row_a, row_b in zip(before["transform"], after["transform"])
                    for a, b in zip(row_a, row_b)
                ):
                    return False
            return True

        def appearance_map(listed: dict) -> dict[str, dict]:
            aliases = listed["aliases"]
            by_feature = {c["feature_id"]: c for c in listed["components"]}
            return {
                label: by_feature[alias["feature_id"]].get("appearance")
                for label, alias in aliases.items()
            }

        async def volumes_and_appearances(model_id: str):
            listed = await call("creo_list_components", {"model_id": model_id})
            inspected = await call(
                "creo_inspect_model", {"model_id": model_id, "detail": "compact"}
            )
            return listed, compact_inspection(inspected)

        await wait_for_startup(client, report, destination)
        report["environment"] = await call("creo_check_environment", {})

        # ---- fixture: 12 source parts -------------------------------------
        # Distinct block sizes per family so every family is one source model.
        sources = {}
        sizes = [[40 + 2 * family, 30 + family, 6 + family % 5] for family in range(12)]
        for family in range(12):
            created = await succeeded_job(
                "creo_execute_plan",
                {
                    "model_name": source_model_name(tag, family),
                    "operations": block(f"src_{family:02d}", sizes[family], 8),
                },
            )
            part_file = created["result"]["part_file"]
            sources[family] = {
                "model_id": created["model_id"],
                "part_file": part_file,
                "sha256": created["result"]["sha256"],
            }
        check("12 source parts created with verified save/reload", len(sources) == 12)

        def verify_source_hashes(stage: str):
            unchanged = True
            for family, source in sources.items():
                digest = hashlib.sha256(
                    (ROOT / source["part_file"]).resolve().read_bytes()
                ).hexdigest()
                unchanged = unchanged and digest == source["sha256"]
            return check(f"source part SHA256 unchanged ({stage})", unchanged)

        # ---- fixture: 80-component assembly -------------------------------
        source_ids = [sources[family]["model_id"] for family in range(12)]
        assembly = await succeeded_job("creo_new_assembly", {"model_name": assembly_name(tag)})
        assembly = await succeeded_job(
            "creo_execute_plan",
            {
                "model_id": assembly["model_id"],
                "expected_revision": assembly["revision"],
                "operations": assemble_operations(source_ids),
            },
        )
        assembly_id = assembly["model_id"]
        listed, inspected = await volumes_and_appearances(assembly_id)
        check("assembly has 80 components", len(listed["components"]) == 80)
        baseline_identity = identity_snapshot(listed)
        baseline_volume = inspected["volume_mm3"]
        baseline_revision = assembly["revision"]
        appearances = appearance_map(listed)
        check(
            "fresh assembly components report absent appearance",
            all(
                isinstance(record, dict) and record.get("state") == "absent"
                for record in appearances.values()
            ),
        )

        # ---- failing plan 1: rollback onto NO component appearance --------
        # The recolor paints three components, then remove_component(c02) runs
        # and the second remove_component(c02) hits its tombstone natively,
        # failing the plan mid-execution after the paint.
        probe_labels = ["c01", "c02", "c03"]
        failing_recolor = {
            "op": "recolor_assembly",
            "families": {"fail_probe": probe_labels},
            "palette": {"fail_probe": [0.9, 0.1, 0.1]},
        }
        validate_operations([failing_recolor, {"op": "remove_component", "component": "c02"}])
        failed = await job(
            "creo_execute_plan",
            {
                "model_id": assembly_id,
                "expected_revision": baseline_revision,
                "operations": [
                    failing_recolor,
                    {"op": "remove_component", "component": "c02"},
                    {"op": "remove_component", "component": "c02"},
                ],
            },
        )
        ok = check("failing plan 1 terminal status is failed", failed["status"] == "failed")
        payload = failed.get("result", {})
        ok = ok and check(
            "failing plan 1 rolled back to the saved checkpoint",
            payload.get("rollback_succeeded") is True,
        )
        recolor_ops = [
            entry
            for entry in payload.get("operations", [])
            if entry.get("op") == "recolor_assembly"
        ]
        ok = ok and check(
            "failing plan 1 recolor effect_status is rolled_back",
            bool(recolor_ops) and recolor_ops[0].get("effect_status") == "rolled_back",
        )
        probe_block = recolor_block(payload)
        ok = ok and check(
            "failing plan 1 recolor block captured a three-entry absent baseline",
            probe_block.get("painted") == 3
            and len(probe_block.get("component_appearance_baseline", [])) == 3
            and all(
                entry["appearance"]["state"] == "absent"
                for entry in probe_block["component_appearance_baseline"]
            ),
        )
        listed, inspected = await volumes_and_appearances(assembly_id)
        appearances = appearance_map(listed)
        ok = ok and check(
            "after failing plan 1 all components are back to no component appearance",
            all(
                isinstance(record, dict) and record.get("state") == "absent"
                for record in appearances.values()
            ),
        )
        ok = ok and check(
            "after failing plan 1 all 80 components and identity are restored",
            len(listed["components"]) == 80 and identity_matches(baseline_identity, listed),
        )

        # ---- round A: automatic families by source model -------------------
        auto_palette = {
            sources[family]["model_id"]: FAMILIES[family]["rgb"] for family in range(12)
        }
        round_a = await succeeded_job(
            "creo_recolor_assembly",
            {
                "model_id": assembly_id,
                "expected_revision": baseline_revision,
                "palette": auto_palette,
            },
        )
        block_a = recolor_block(round_a["result"])
        expected_auto_counts = {sources[f]["model_id"]: EXPECTED_COUNTS[f] for f in range(12)}
        check(
            "round A painted all 80 components with no unmatched entries",
            block_a.get("painted") == 80 and block_a.get("unmatched") == [],
        )
        check(
            "round A family_counts match the proposal's 12 counts per source",
            block_a.get("family_counts") == expected_auto_counts,
            json.dumps(block_a.get("family_counts")),
        )
        check(
            "round A readback before and after reload within 1e-6",
            block_a.get("readback_all_within_tolerance") is True
            and len(block_a.get("readback_before_save", [])) == 80
            and len(block_a.get("readback_after_reload", [])) == 80,
        )
        check(
            "round A saved_file_reloaded_and_verified and revision advanced once",
            round_a["result"]["saved_file_reloaded_and_verified"] is True
            and round_a["revision"] == baseline_revision + 1,
        )
        verify_source_hashes("after round A")
        listed, inspected = await volumes_and_appearances(assembly_id)
        appearances = appearance_map(listed)
        check(
            "round A colors readable through the component check",
            all(
                appearance_matches(
                    appearances[label],
                    auto_palette[sources[COMPONENT_FAMILY[int(label[1:]) - 1]]["model_id"]],
                )
                for label in component_labels()
            ),
        )
        check(
            "round A kept identity, pose, constraints and volume",
            identity_matches(baseline_identity, listed)
            and abs(inspected["volume_mm3"] - baseline_volume) <= 0.01,
        )

        # ---- failing plan 2: rollback onto previously painted colors -------
        shifted = {
            family: [spec["rgb"][1], spec["rgb"][2], spec["rgb"][0]]
            for family, spec in enumerate(FAMILIES)
        }
        failing_recolor_full = {
            "op": "recolor_assembly",
            "families": {f"fail_{family:02d}": labels_by_family()[family] for family in range(12)},
            "palette": {f"fail_{family:02d}": shifted[family] for family in range(12)},
        }
        failed = await job(
            "creo_execute_plan",
            {
                "model_id": assembly_id,
                "expected_revision": round_a["revision"],
                "operations": [
                    failing_recolor_full,
                    {"op": "remove_component", "component": "c02"},
                    {"op": "remove_component", "component": "c02"},
                ],
            },
        )
        ok = check("failing plan 2 terminal status is failed", failed["status"] == "failed")
        payload = failed.get("result", {})
        ok = ok and check(
            "failing plan 2 rolled back with a verified appearance restore",
            payload.get("rollback_succeeded") is True
            and recolor_block(payload).get("rollback_appearance_verified") is True,
        )
        listed, inspected = await volumes_and_appearances(assembly_id)
        appearances = appearance_map(listed)
        ok = ok and check(
            "after failing plan 2 every component is back to its round A color",
            all(
                appearance_matches(
                    appearances[label],
                    auto_palette[sources[COMPONENT_FAMILY[int(label[1:]) - 1]]["model_id"]],
                )
                for label in component_labels()
            ),
        )

        # ---- round B: explicit family table (with a merged family) --------
        exp_families = explicit_families()
        palette_plain = explicit_palette(shift=False)
        palette_shifted = explicit_palette(shift=True)
        family_of_label = {
            label: name for name, members in exp_families.items() for label in members
        }
        round_b = await succeeded_job(
            "creo_recolor_assembly",
            {
                "model_id": assembly_id,
                "expected_revision": round_a["revision"],
                "families": exp_families,
                "palette": palette_plain,
            },
        )
        block_b = recolor_block(round_b["result"])
        check(
            "round B family_counts match the explicit table including the merged family",
            block_b.get("family_counts") == expected_explicit_counts(),
            json.dumps(block_b.get("family_counts")),
        )
        check(
            "round B readback within 1e-6 after save/reload",
            block_b.get("readback_all_within_tolerance") is True,
        )
        listed, _ = await volumes_and_appearances(assembly_id)
        appearances = appearance_map(listed)
        check(
            "round B colors readable through the component check",
            all(
                appearance_matches(appearances[label], palette_plain[family_of_label[label]])
                for label in component_labels()
            ),
        )

        # ---- round C: recolor again with a third palette -------------------
        round_c = await succeeded_job(
            "creo_recolor_assembly",
            {
                "model_id": assembly_id,
                "expected_revision": round_b["revision"],
                "families": exp_families,
                "palette": palette_shifted,
            },
        )
        block_c = recolor_block(round_c["result"])
        check(
            "round C (re-recolor) readback within 1e-6 and counts unchanged",
            block_c.get("readback_all_within_tolerance") is True
            and block_c.get("family_counts") == expected_explicit_counts(),
        )
        verify_source_hashes("after rounds B and C")

        # ---- placement change + save keeps the colors ----------------------
        placed = await succeeded_job(
            "creo_execute_plan",
            {
                "model_id": assembly_id,
                "expected_revision": round_c["revision"],
                "operations": [
                    {
                        "op": "component_placement",
                        "component": "c01",
                        "translation": [5, 5, 0],
                        "placement": "fixed",
                    }
                ],
            },
        )
        listed, inspected = await volumes_and_appearances(assembly_id)
        appearances = appearance_map(listed)
        check(
            "after placement + save every component keeps its round C color",
            all(
                appearance_matches(appearances[label], palette_shifted[family_of_label[label]])
                for label in component_labels()
            ),
        )
        check(
            "placement moved only c01 and kept geometry (volume unchanged)",
            identity_matches(baseline_identity, listed, moved={"c01"})
            and abs(inspected["volume_mm3"] - baseline_volume) <= 0.01,
        )
        check(
            "final saved_file_reloaded_and_verified is true for the placement job",
            placed["result"]["saved_file_reloaded_and_verified"] is True,
        )

        verify_source_hashes("final")
        report["success"] = all(entry["ok"] for entry in checks)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        passed = sum(1 for entry in checks if entry["ok"])
        print(f"\n==== assembly appearance summary: {passed}/{len(checks)} checks passed ====")
        if not report["success"]:
            failed_names = [entry["name"] for entry in checks if not entry["ok"]]
            print("FAILED checks: " + "; ".join(failed_names))
    if not report["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-health-verified", action="store_true", required=True)
    parser.parse_args()
    asyncio.run(run())
