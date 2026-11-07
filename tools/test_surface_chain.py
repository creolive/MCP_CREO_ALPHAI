"""Unified surface-chain driver (FEAT-055/S01, FEAT-039).

All surface-chain cases (S01 quilts query, S02 surface_trim, S03 quilt_merge
closure, S04 project_curve) run from this entry. Acceptance uses public MCP
tools only (creo_execute_plan / creo_get_job / creo_inspect_model); no internal
Python API ever decides a case's outcome.

Modes:
* default (offline): pure query-side checks against synthetic snapshots in
  this repo's own query layer. The report records
  ``native_quilt_query=not_verified`` — offline results are never native
  evidence.
* ``--live --confirm-session-usable`` (both flags required): runs the same
  case against the connected Creo session and asserts real geometry.

Discipline:
* unknown cases are refused before any connection is attempted;
* the report is written under build/surface_chain/<run_id>/ where run_id is a
  millisecond timestamp; an existing directory is never overwritten.

Example (PowerShell, from the repo root):
.venv\\Scripts\\python.exe tools\\test_surface_chain.py --case quilts
.venv\\Scripts\\python.exe tools\\test_surface_chain.py --case quilts --live --confirm-session-usable
.venv\\Scripts\\python.exe tools\\test_surface_chain.py --case trim
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

try:  # the driver runs as a script and as a package module
    from surface_chain_chains import (
        case_chain_open_live,
        case_chain_open_offline,
        section,
        submit_plan,
    )
    from surface_chain_closed import case_chain_closed_live, case_chain_closed_offline
    from surface_chain_example import case_example_live, case_example_offline
    from surface_chain_group import case_group_live, case_group_offline
    from surface_chain_join import case_join_live, case_join_offline
    from surface_chain_offset import case_offset_live, case_offset_offline
    from surface_chain_sweep import case_sweep_live, case_sweep_offline
except ImportError:  # pragma: no cover - the package import path
    from tools.surface_chain_chains import (
        case_chain_open_live,
        case_chain_open_offline,
        section,
        submit_plan,
    )
    from tools.surface_chain_closed import case_chain_closed_live, case_chain_closed_offline
    from tools.surface_chain_example import case_example_live, case_example_offline
    from tools.surface_chain_group import case_group_live, case_group_offline
    from tools.surface_chain_join import case_join_live, case_join_offline
    from tools.surface_chain_offset import case_offset_live, case_offset_offline
    from tools.surface_chain_sweep import case_sweep_live, case_sweep_offline
sys.path.insert(0, str(ROOT))

from version import VERSION  # noqa: E402

CASES = (
    "quilts",
    "trim",
    "merge",
    "project",
    "solidify",
    "chain_open",
    "chain_closed",
    "join",
    "sweep_surface",
    "offset",
    "group",
)
BUSY_EXIT = 2
OVERWRITE_EXIT = 3


def surface_chain_plan(width: float, height: float) -> list[dict]:
    """One surface_fill rectangle: the shared S01+ geometry fixture."""
    return [
        {
            "op": "sketch",
            "label": "patch_profile",
            "entities": [
                {"type": "rectangle", "name": "rect", "min": [0, 0], "max": [width, height]}
            ],
        },
        {"op": "surface_fill", "label": "patch", "sketch": "patch_profile"},
    ]


def case_quilts_offline() -> dict:
    """Query-side contract against synthetic snapshots (no Creo involved)."""
    from creo_mechdog.model_queries import (
        COUNT_KEYS,
        SECTIONS,
        inspect_page,
        inspection_summary,
        section_records,
    )

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    record = {
        "quilt_id": 7,
        "feature_ids": [3],
        "face_count": 2,
        "surface_ids": [11, 12],
        "area_mm2": None,
        "area_status": {
            "available": False,
            "reason": "unit_scale_unknown",
            "query_code": 0,
            "scale_to_mm_known": False,
            "unit_name": None,
        },
        "closed": None,
        "closed_status": {
            "available": False,
            "reason": "quilt_volume_eval_failed",
            "query_code": 3,
            "scale_to_mm_known": False,
            "unit_name": None,
        },
        "bbox_mm": None,
        "bbox_status": {
            "available": False,
            "reason": "surface_data_get_failed",
            "query_code": 2,
            "scale_to_mm_known": False,
            "unit_name": None,
        },
    }
    with_quilts = {
        "model_id": "m1",
        "model_name": "m1.prt",
        "model_type": "part",
        "revision": 1,
        "part_file": "m1.prt",
        "status": "ready",
        "inspection": {
            "healthy": True,
            "has_solid": True,
            "model_type": "part",
            "features": [],
            "surfaces": [{"id": 11}, {"id": 12}],
            "edges": [],
            "bodies": [],
            "counts": {"surfaces": 2, "edges": 0},
            "quilts": [record],
        },
    }
    legacy = {
        **with_quilts,
        "inspection": {k: v for k, v in with_quilts["inspection"].items() if k != "quilts"},
    }

    check("quilts_section_registered", "quilts" in SECTIONS and "quilts" in COUNT_KEYS)
    check(
        "quilts_section_available",
        section_records(with_quilts, "quilts") == [record]
        and inspect_page(with_quilts, "full", section="quilts")["data"]["quilts"] == [record],
    )
    check(
        "counts_quilts_counted",
        inspection_summary(with_quilts["inspection"])["counts"]["quilts"] == 1,
    )
    check(
        "legacy_snapshot_quilts_unavailable",
        section_records(legacy, "quilts") is None
        and inspection_summary(legacy["inspection"])["counts"]["quilts"] is None,
    )
    check(
        "quilt_and_surface_ids_apart",
        record["quilt_id"] not in record["surface_ids"],
    )
    check(
        "unknown_unit_keeps_measurements_null",
        record["area_mm2"] is None
        and record["area_status"]["available"] is False
        and record["area_status"]["scale_to_mm_known"] is False,
    )
    grown = json.loads(json.dumps(with_quilts))
    grown["inspection"]["quilts"].append({**record, "quilt_id": 8})
    page = inspect_page(grown, "full", section="quilts", limit=1)
    try:
        inspect_page(
            {**grown, "revision": grown["revision"] + 1},
            "full",
            section="quilts",
            limit=1,
            cursor=page["next_cursor"],
        )
        check("cursor_bound_to_snapshot", False, {"error": "stale cursor accepted"})
    except ValueError:
        check("cursor_bound_to_snapshot", True)

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "offline",
        "passed": passed,
        "native_quilt_query": "not_verified",
        "checks": checks,
    }


async def wait_ready(client, budget_seconds: int = 210, retry_once: bool = True) -> dict:
    """Poll the startup coordinator inside this session until it is connected.

    The coordinator runs on a thread of the serving process: a client that
    submits first, or that disconnects while the build phase is running, only
    ever sees the persisted `building_worker` snapshot. Polling here keeps the
    session alive until the Toolkit verification actually settles.

    `retry_once` asks the coordinator for one attempt when the persisted state
    is stale (a previous client exited mid-build). Only the first call carries
    it: every retry starts another attempt, and a state file left in an active
    phase cannot be replaced otherwise.
    """
    deadline = time.monotonic() + budget_seconds
    state: dict = {}
    while time.monotonic() < deadline:
        state = (
            await client.call_tool("creo_startup_status", {"retry": retry_once})
        ).structured_content
        retry_once = False
        if state.get("connected"):
            return state
        if state.get("state") in ("timeout", "failed", "error", "blocked", "unavailable"):
            return state
        await asyncio.sleep(2)
    return state


def job_runner(client, jobs: list[str]):
    """Submit through the public tool and poll only the accepted job."""

    async def run_job(tool: str, args: dict) -> dict:
        result = await client.call_tool(tool, args)
        if result.is_error:
            raise RuntimeError(str(result))
        state = result.structured_content
        job_id = state["job_id"]
        jobs.append(job_id)
        print(json.dumps({"tool": tool, "job_id": job_id}), flush=True)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            state = (await client.call_tool("creo_get_job", {"job_id": job_id})).structured_content
            if state["status"] in ("succeeded", "failed", "unknown_outcome"):
                break
            await asyncio.sleep(0.5)
        else:
            raise TimeoutError("job did not settle; inspect it, never blindly resubmit")
        if state["status"] != "succeeded":
            raise RuntimeError(
                json.dumps(
                    {
                        "job_id": job_id,
                        "status": state["status"],
                        "message": state.get("message"),
                    }
                )
            )
        assert state["result"]["saved_file_reloaded_and_verified"]
        return state

    return run_job


async def case_quilts_live() -> dict:
    """Real geometry through the MCP surface: query the quilts section."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    width, height = 40.0, 20.0
    jobs: list[str] = []
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        check(
            "session_ready",
            bool(started.get("connected")),
            {"state": started.get("state"), "message": str(started.get("message"))[:200]},
        )
        if not started.get("connected"):
            return {"mode": "live", "passed": False, "checks": checks}
        run_job = job_runner(client, jobs)
        build = await run_job(
            "creo_execute_plan", {"operations": surface_chain_plan(width, height)}
        )
        model_id = build["model_id"]
        page = (
            await client.call_tool(
                "creo_inspect_model", {"model_id": model_id, "detail": "full", "section": "quilts"}
            )
        ).structured_content

    records = page.get("data", {}).get("quilts")
    summary = page.get("inspection", {})
    check("quilts_in_sections_available", "quilts" in page.get("sections_available", []))
    check(
        "quilts_section_served",
        isinstance(records, list) and len(records) >= 1,
        {"records": records},
    )
    if isinstance(records, list) and records:
        record = records[0]
        expected_area = width * height
        area = record.get("area_mm2")
        check(
            "quilt_record_shape",
            isinstance(record.get("quilt_id"), int)
            and isinstance(record.get("surface_ids"), list)
            and isinstance(record.get("feature_ids"), list)
            and record["quilt_id"] not in record["surface_ids"],
            {"record": record},
        )
        check("face_count_positive", record.get("face_count") == len(record.get("surface_ids", [])))
        check(
            "area_matches_fixture",
            isinstance(area, (int, float)) and abs(area - expected_area) <= 0.5,
            {"area_mm2": area, "expected": expected_area},
        )
        check("open_quilt_reports_closed_false", record.get("closed") is False)
        check(
            "bbox_present_and_in_domain",
            isinstance(record.get("bbox_mm"), list)
            and len(record["bbox_mm"]) == 2
            and abs(record["bbox_mm"][0][0] - 0.0) < 1e-6
            and abs(record["bbox_mm"][1][0] - width) < 1e-6
            and abs(record["bbox_mm"][0][2]) < 1e-6
            and abs(record["bbox_mm"][1][2]) < 1e-6,
            {"bbox_mm": record.get("bbox_mm")},
        )
        check(
            "counts_quilts_match_records",
            summary.get("counts", {}).get("quilts") == len(records),
            {"counts": summary.get("counts")},
        )
    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_quilt_query": "verified" if passed else "failed",
        "jobs": jobs,
        "model_id": page.get("model_id") if isinstance(page, dict) else None,
        "checks": checks,
    }


TRIM_WIDTH, TRIM_HEIGHT, TRIM_X = 40.0, 20.0, 5.0
# Live 2026-11-04: keep_side one keeps the +X side of the tool plane normal
# (700 mm2), two keeps the -X side (100 mm2). The cut is asymmetric on purpose -
# a cut at x=20 leaves 400 mm2 on both sides, so the area cannot name the
# retained side. DEV-074/H06 adds measured centroids/bboxes/normals so the side
# is proven by geometry, not by the area alone.
TRIM_EXPECTED_AREA = {
    "one": (TRIM_WIDTH - TRIM_X) * TRIM_HEIGHT,
    "two": TRIM_X * TRIM_HEIGHT,
}
TRIM_TARGET_CENTROID_X = TRIM_WIDTH / 2.0
# The quilt tool is a 60x60 fill on the YZ plane at x=TRIM_X, so it cuts at the
# same place as the datum plane and must yield the same retained regions.
TRIM_TOOL_QUILT_SIZE = 60.0


def trim_expected_kept_centroid_x(keep_side: str) -> float:
    return (TRIM_X + TRIM_WIDTH) / 2.0 if keep_side == "one" else TRIM_X / 2.0


def trim_plan(keep_side: str, tool: str = "plane") -> list[dict]:
    """One 40x20 fill trimmed at x=5 (plan S02 step 4, H06 matrix).

    ``tool="plane"`` uses a datum plane; ``tool="quilt"`` uses a perpendicular
    60x60 fill on the YZ plane at the same x. The retained region is judged by
    measured area, position and centroid, never by comparing quilt ids across
    two independent models (contract §4.5 / R5).
    """
    operations = [
        {
            "op": "sketch",
            "label": "trim_profile",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "rect",
                    "min": [0, 0],
                    "max": [TRIM_WIDTH, TRIM_HEIGHT],
                }
            ],
        },
        {"op": "surface_fill", "label": "trim_target", "sketch": "trim_profile"},
    ]
    if tool == "quilt":
        half = TRIM_TOOL_QUILT_SIZE / 2.0
        operations.extend(
            [
                {
                    "op": "sketch",
                    "label": "trim_cut_profile",
                    "plane": "YZ",
                    "offset": TRIM_X,
                    "entities": [
                        {
                            "type": "rectangle",
                            "name": "cut_rect",
                            "min": [-half, -half],
                            "max": [half, half],
                        }
                    ],
                },
                {
                    "op": "surface_fill",
                    "label": "trim_cut_quilt",
                    "sketch": "trim_cut_profile",
                },
            ]
        )
        tool_reference = {"kind": "quilt_feature", "label": "trim_cut_quilt"}
    else:
        operations.append(
            {
                "op": "datum_plane",
                "label": "trim_cut_plane",
                # Geometric plane references resolve by axis/normal; a label here
                # is refused (live 2026-11-04: it silently resolved to TOP).
                "reference": {"kind": "datum_plane", "axis": "x", "offset": 0},
                "offset": TRIM_X,
            }
        )
        tool_reference = {"kind": "datum_plane", "label": "trim_cut_plane"}
    operations.append(
        {
            "op": "surface_trim",
            "label": "trim_result",
            "target": {"kind": "quilt_feature", "label": "trim_target"},
            "tool": tool_reference,
            "keep_side": keep_side,
        }
    )
    return operations


def trim_failure_base_plan() -> list[dict]:
    """A 40x20 fill plus a plane at x=100 that cannot cut it."""
    return [
        {
            "op": "sketch",
            "label": "trim_profile",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "rect",
                    "min": [0, 0],
                    "max": [TRIM_WIDTH, TRIM_HEIGHT],
                }
            ],
        },
        {"op": "surface_fill", "label": "trim_target", "sketch": "trim_profile"},
        {
            "op": "datum_plane",
            "label": "trim_far_plane",
            "reference": {"kind": "datum_plane", "axis": "x", "offset": 0},
            "offset": TRIM_WIDTH * 2.5,
        },
    ]


TRIM_FAILURE_PLAN = [
    {
        "op": "surface_trim",
        "label": "trim_impossible",
        "target": {"kind": "quilt_feature", "label": "trim_target"},
        "tool": {"kind": "datum_plane", "label": "trim_far_plane"},
        "keep_side": "one",
    }
]


def case_trim_offline() -> dict:
    """S02 contract, gate and native wiring. No Creo session is involved."""
    from creo_mechdog.capabilities import UNAVAILABLE_OPERATIONS, require_available
    from creo_mechdog.schema import validate_operations

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    operation = trim_plan("one")[3]
    validated = validate_operations([operation])
    check(
        "trim_plan_validates",
        validated[0]["op"] == "surface_trim" and validated[0]["keep_side"] == "one",
    )
    # The quilt-tool branch and the rollback case are real plans too; a schema
    # regression there must not wait for the live window to surface.
    quilt_plan = validate_operations(trim_plan("two", "quilt"))
    check(
        "quilt_tool_plan_validates",
        quilt_plan[-1]["keep_side"] == "two"
        and quilt_plan[-1]["tool"] == {"kind": "quilt_feature", "label": "trim_cut_quilt"},
    )
    check(
        "failure_plan_validates",
        validate_operations(trim_failure_base_plan() + TRIM_FAILURE_PLAN)[-1]["op"]
        == "surface_trim",
    )

    def rejects(candidate: dict, pattern: str) -> bool:
        try:
            validate_operations([candidate])
        except ValueError as error:
            return pattern in str(error)
        return False

    def accepts(candidate: dict) -> bool:
        try:
            validate_operations([candidate])
        except ValueError:
            return False
        return True

    check(
        "body_target_rejected",
        rejects({**operation, "target": {"kind": "body", "id": 3}}, "target"),
    )
    # The use-curve variant is published (2026-11-04 live matrix), so a curve
    # tool is accepted; only a curve without a real id is refused.
    check(
        "curve_tool_accepted",
        accepts({**operation, "tool": {"kind": "curve", "id": 41}}),
    )
    check(
        "curve_tool_without_id_rejected",
        rejects({**operation, "tool": {"kind": "curve", "label": "cut"}}, "tool"),
    )
    check(
        "multi_tool_rejected",
        rejects(
            {**operation, "tool": [{"kind": "quilt", "id": 1}, {"kind": "quilt", "id": 2}]},
            "tool",
        ),
    )
    check(
        "keep_side_both_rejected",
        rejects({**operation, "keep_side": "both"}, "keep_side"),
    )
    check(
        "self_trim_rejected",
        rejects({**operation, "tool": dict(operation["target"])}, "distinct"),
    )

    # Live 2026-11-04: both keep_side values built, measured (700 / 100 mm2) and
    # saved/reloaded with the retained bbox on the measured side, so the
    # operation is published and the gate no longer refuses it.
    check("surface_trim_published", "surface_trim" not in UNAVAILABLE_OPERATIONS)
    allowed = True
    try:
        require_available([operation])
    except ValueError:
        allowed = False
    check("no_gate_refusal", allowed)

    generic = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8")
    native = (ROOT / "native" / "surface_trim.cpp").read_text(encoding="utf-8")
    check(
        "native_included_and_dispatched",
        '#include "surface_trim.cpp"' in generic and generic.count("generic_surface_trim(op)") == 1,
    )
    check(
        "native_reuses_shared_helpers",
        "resolve_quilt_reference" in native and "quilt_area_native" in native,
    )
    check(
        "native_result_fields_frozen",
        all(
            field in native
            for field in (
                "area_before_mm2",
                "area_after_mm2",
                "kept_side_basis",
                "kept_quilt_id",
            )
        ),
    )
    # DEV-074/H06: the retained side is now proven by measured region geometry;
    # the old "quilt_centroid_not_measured" null block must be gone.
    check(
        "native_kept_side_geometry_wired",
        "quilt_region_geometry" in native
        and "quilt_centroid_not_measured" not in native
        and all(
            field in native
            for field in (
                "target_centroid_status",
                "kept_centroid_status",
                "target_bbox_mm",
                "kept_bbox_mm",
                "target_bbox_status",
                "kept_bbox_status",
                "target_direction",
                "kept_direction",
                "target_direction_status",
                "kept_direction_status",
            )
        ),
    )

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "offline",
        "passed": passed,
        "native_surface_trim": "not_verified",
        "gate": UNAVAILABLE_OPERATIONS.get("surface_trim"),
        "checks": checks,
    }


def _near(value: Any, expected: float, tolerance: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and abs(float(value) - expected) <= tolerance
    )


def _near_point(value: Any, expected: tuple[float, float, float], tolerance: float) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(_near(item, want, tolerance) for item, want in zip(value, expected, strict=True))
    )


async def case_trim_live() -> dict:
    """H06 matrix: keep_side one/two x plane/quilt tool plus a clean rollback.

    Every successful case must prove the retained side by measured geometry:
    the target and retained centroids, their difference, the retained bounds and
    the region normal. A failing trim must roll back and leave the 800 mm2 fill
    intact. Each successful job is also required to report
    ``saved_file_reloaded_and_verified``.
    """
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    jobs: list[str] = []
    evidence: list[dict] = []
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        # A rebuilt worker makes the coordinator report building_worker; a job
        # submitted before it settles is refused with "Creo is not ready".
        started = await wait_ready(client)
        check(
            "session_ready",
            bool(started.get("connected")),
            {"state": started.get("state"), "message": str(started.get("message"))[:200]},
        )
        if not started.get("connected"):
            return {
                "mode": "live",
                "passed": False,
                "native_surface_trim": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
            }
        capabilities = (await client.call_tool("creo_capabilities", {})).structured_content
        published = "surface_trim" in (capabilities.get("operations") or [])
        check("surface_trim_published", published)
        if not published:
            return {
                "mode": "live",
                "passed": False,
                "native_surface_trim": "gated",
                "note": (
                    "surface_trim is refused before any job until the live retained-side "
                    "measurement (plan S02 step 3) is on record; no geometry was submitted"
                ),
                "checks": checks,
            }
        for tool in ("plane", "quilt"):
            for side in ("one", "two"):
                name = f"{tool}_{side}"
                state = await submit_plan(client, trim_plan(side, tool), jobs)
                check(
                    f"trim_{name}_succeeded",
                    state.get("status") == "succeeded",
                    {"job_id": state.get("job_id"), "message": state.get("message")},
                )
                if state.get("status") != "succeeded":
                    evidence.append(
                        {
                            "tool": tool,
                            "keep_side": side,
                            "job_id": state.get("job_id"),
                            "status": state.get("status"),
                            "message": state.get("message"),
                        }
                    )
                    continue
                check(f"trim_{name}_saved_and_reloaded", state.get("saved_verified") is True)
                operation = state.get("operation") or {}
                basis = operation.get("kept_side_basis") or {}
                expected_area = TRIM_EXPECTED_AREA[side]
                expected_centroid_x = trim_expected_kept_centroid_x(side)
                delta_x = expected_centroid_x - TRIM_TARGET_CENTROID_X
                records = await section(client, state["model_id"], "quilts")
                measured = [
                    record
                    for record in records
                    if _near(record.get("area_mm2"), expected_area, 0.5)
                ]
                check(
                    f"trim_{name}_area",
                    bool(measured),
                    {
                        "expected_mm2": expected_area,
                        "records": [record.get("area_mm2") for record in records],
                    },
                )
                bbox = measured[0].get("bbox_mm") if measured else None
                low, high = (bbox[0][0], bbox[1][0]) if bbox else (None, None)
                expected_bounds = (TRIM_X, TRIM_WIDTH) if side == "one" else (0.0, TRIM_X)
                check(
                    f"trim_{name}_position",
                    _near(low, expected_bounds[0], 0.5) and _near(high, expected_bounds[1], 0.5),
                    {"bbox_mm": bbox},
                )
                target_centroid = basis.get("target_centroid")
                kept_centroid = basis.get("kept_centroid")
                check(
                    f"trim_{name}_centroid",
                    _near_point(
                        target_centroid, (TRIM_TARGET_CENTROID_X, TRIM_HEIGHT / 2.0, 0.0), 0.05
                    )
                    and _near_point(
                        kept_centroid, (expected_centroid_x, TRIM_HEIGHT / 2.0, 0.0), 0.05
                    )
                    and _near_point(basis.get("centroid_delta_mm"), (delta_x, 0.0, 0.0), 0.05),
                    {
                        "target_centroid": target_centroid,
                        "kept_centroid": kept_centroid,
                        "centroid_delta_mm": basis.get("centroid_delta_mm"),
                        "centroid_status": basis.get("centroid_status"),
                    },
                )
                kept_bbox = basis.get("kept_bbox_mm") or {}
                bbox_min = kept_bbox.get("min") or []
                bbox_max = kept_bbox.get("max") or []
                check(
                    f"trim_{name}_bbox",
                    _near_point(bbox_min, (expected_bounds[0], 0.0, 0.0), 1e-3)
                    and _near_point(bbox_max, (expected_bounds[1], TRIM_HEIGHT, 0.0), 1e-3)
                    and _near_point(
                        kept_bbox.get("size"),
                        (expected_bounds[1] - expected_bounds[0], TRIM_HEIGHT, 0.0),
                        1e-3,
                    ),
                    {"kept_bbox_mm": kept_bbox, "kept_bbox_status": basis.get("kept_bbox_status")},
                )
                direction = basis.get("kept_direction")
                direction_status = basis.get("kept_direction_status") or {}
                check(
                    f"trim_{name}_direction",
                    isinstance(direction, list)
                    and len(direction) == 3
                    and abs(abs(direction[2]) - 1.0) <= 1e-6
                    and abs(direction[0]) <= 1e-6
                    and abs(direction[1]) <= 1e-6
                    and direction_status.get("available") is True
                    and direction_status.get("planar") is True,
                    {
                        "kept_direction": direction,
                        "target_direction": basis.get("target_direction"),
                        "kept_direction_status": direction_status,
                    },
                )
                tool_normal = basis.get("tool_normal")
                if tool == "plane":
                    normal_source = basis.get("tool_normal_source")
                    signed = basis.get("signed_offset_mm")
                    expected_sign = 1.0 if side == "one" else -1.0
                    check(
                        f"trim_{name}_tool_normal",
                        normal_source == "datum_plane_axis"
                        and _near_point(tool_normal, (1.0, 0.0, 0.0), 1e-6)
                        and isinstance(signed, (int, float))
                        and signed * expected_sign > 0
                        and _near(abs(signed), abs(delta_x), 0.05),
                        {
                            "tool_normal": tool_normal,
                            "tool_normal_source": normal_source,
                            "signed_offset_mm": signed,
                            "signed_offset_status": basis.get("signed_offset_status"),
                        },
                    )
                else:
                    # A quilt tool's face orientation is measured, not anchored,
                    # so signed_offset stays null with its reason.
                    check(
                        f"trim_{name}_tool_normal",
                        isinstance(tool_normal, list)
                        and len(tool_normal) == 3
                        and abs(abs(tool_normal[0]) - 1.0) <= 1e-6
                        and abs(tool_normal[1]) <= 1e-6
                        and abs(tool_normal[2]) <= 1e-6
                        and basis.get("tool_normal_source") == "tool_quilt_face_normal"
                        and basis.get("signed_offset_mm") is None
                        and (basis.get("signed_offset_status") or {}).get("reason")
                        == "tool_normal_unavailable",
                        {
                            "tool_normal": tool_normal,
                            "tool_normal_source": basis.get("tool_normal_source"),
                            "signed_offset_mm": basis.get("signed_offset_mm"),
                            "signed_offset_status": basis.get("signed_offset_status"),
                        },
                    )
                evidence.append(
                    {
                        "tool": tool,
                        "keep_side": side,
                        "job_id": state.get("job_id"),
                        "model_id": state.get("model_id"),
                        "revision": state.get("revision"),
                        "status": state.get("status"),
                        "area_after_mm2": operation.get("area_after_mm2"),
                        "target_centroid": target_centroid,
                        "kept_centroid": kept_centroid,
                        "centroid_delta_mm": basis.get("centroid_delta_mm"),
                        "kept_bbox_mm": kept_bbox,
                        "kept_direction": direction,
                        "tool_normal": tool_normal,
                        "tool_normal_source": basis.get("tool_normal_source"),
                        "signed_offset_mm": basis.get("signed_offset_mm"),
                        "saved_file_reloaded_and_verified": state.get("saved_verified"),
                    }
                )
        # The two retained regions must sit on opposite sides of the same tool
        # plane at x=TRIM_X; the coordinates and their difference are the proof.
        for tool in ("plane", "quilt"):
            pages = [
                item
                for item in evidence
                if item.get("tool") == tool and isinstance(item.get("kept_centroid"), list)
            ]
            if len(pages) == 2:
                sides = {item["keep_side"]: item["kept_centroid"][0] - TRIM_X for item in pages}
                check(
                    f"trim_{tool}_sides_are_opposite",
                    sides.get("one", 0.0) * sides.get("two", 0.0) < 0,
                    {
                        "tool_plane_x": TRIM_X,
                        "kept_centroid_offset_mm": sides,
                    },
                )
        # A trim that cannot cut anything must fail cleanly: the job rolls back,
        # the revision does not advance and the 800 mm2 fill stays untrimmed.
        built = await submit_plan(client, trim_failure_base_plan(), jobs)
        check(
            "rollback_case_built",
            built.get("status") == "succeeded" and built.get("saved_verified") is True,
            {"job_id": built.get("job_id"), "message": built.get("message")},
        )
        if built.get("status") == "succeeded":
            model_id = built["model_id"]
            revision = built.get("revision")
            failed = await submit_plan(client, TRIM_FAILURE_PLAN, jobs, model_id, revision)
            result = failed.get("result") or {}
            check(
                "impossible_trim_failed",
                failed.get("status") == "failed",
                {"job_id": failed.get("job_id"), "message": failed.get("message")},
            )
            check(
                "impossible_trim_rolled_back",
                result.get("rollback_succeeded") is True,
                {
                    "rollback_succeeded": result.get("rollback_succeeded"),
                    "message": failed.get("message"),
                },
            )
            records = await section(client, model_id, "quilts")
            areas = [record.get("area_mm2") for record in records]
            check(
                "rollback_kept_the_fill",
                any(_near(area, TRIM_WIDTH * TRIM_HEIGHT, 0.5) for area in areas),
                {"areas_mm2": areas},
            )
            page = (
                await client.call_tool(
                    "creo_inspect_model", {"model_id": model_id, "detail": "compact"}
                )
            ).structured_content
            check(
                "rollback_kept_the_revision",
                page.get("revision") == revision,
                {"revision_before": revision, "revision_after": page.get("revision")},
            )
    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_surface_trim": "verified" if passed else "failed",
        "jobs": jobs,
        "evidence": evidence,
        "checks": checks,
    }


MERGE_FACE = 20.0


def merge_plan(gap: float = 0.0) -> list[dict]:
    """Two coplanar 20x20 fills joined into one 800 mm2 quilt.

    ``gap`` separates the second face along +X: 0 gives two faces sharing an
    edge (a join that must succeed), a positive value gives a pair that cannot
    be joined (the negative case that must not report a false closure).
    The result is judged by the measured area and the reported closure only;
    no tolerance is claimed and no gap is measured (plan S03 step 4).
    """
    second_min = MERGE_FACE + gap
    return [
        {
            "op": "sketch",
            "label": "merge_profile_a",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "rect_a",
                    "min": [0, 0],
                    "max": [MERGE_FACE, MERGE_FACE],
                }
            ],
        },
        {
            "op": "sketch",
            "label": "merge_profile_b",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "rect_b",
                    "min": [second_min, 0],
                    "max": [second_min + MERGE_FACE, MERGE_FACE],
                }
            ],
        },
        {"op": "surface_fill", "label": "merge_face_a", "sketch": "merge_profile_a"},
        {"op": "surface_fill", "label": "merge_face_b", "sketch": "merge_profile_b"},
        {
            "op": "quilt_merge",
            "label": "merge_result",
            "target": {"kind": "quilt_feature", "label": "merge_face_a"},
            "tool": {"kind": "quilt_feature", "label": "merge_face_b"},
        },
    ]


# Closed case: a cylinder tube plus two circular caps, joined in two steps, then
# solidified. A cylinder is chosen over a six-faced box because it needs two
# merges instead of five, and every expected value stays analytic.
MERGE_RADIUS = 5.0
MERGE_HEIGHT = 10.0
MERGE_TUBE_AREA = 2 * math.pi * MERGE_RADIUS * MERGE_HEIGHT
MERGE_CAP_AREA = math.pi * MERGE_RADIUS * MERGE_RADIUS
MERGE_CLOSED_AREA = MERGE_TUBE_AREA + 2 * MERGE_CAP_AREA
MERGE_CLOSED_VOLUME = MERGE_CAP_AREA * MERGE_HEIGHT


def merged_closed_plan() -> list[dict]:
    """Tube + two caps joined twice into a closed quilt, then solidified.

    The quilt counts as closed only if the reported closure is true and the
    solidified volume matches pi*r^2*h; an open result must not reach the
    solid step.
    """
    return [
        {
            "op": "sketch",
            "label": "merge_circle_lower",
            "entities": [
                {"type": "circle", "name": "c_low", "center": [0, 0], "radius": MERGE_RADIUS}
            ],
        },
        {
            "op": "sketch",
            "label": "merge_circle_upper",
            "offset": MERGE_HEIGHT,
            "entities": [
                {"type": "circle", "name": "c_up", "center": [0, 0], "radius": MERGE_RADIUS}
            ],
        },
        {
            "op": "extrude",
            "label": "merge_tube",
            "sketch": "merge_circle_lower",
            "mode": "surface",
            "depth": MERGE_HEIGHT,
        },
        {"op": "surface_fill", "label": "merge_cap_lower", "sketch": "merge_circle_lower"},
        {"op": "surface_fill", "label": "merge_cap_upper", "sketch": "merge_circle_upper"},
        {
            "op": "quilt_merge",
            "label": "merge_half",
            "target": {"kind": "quilt_feature", "label": "merge_tube"},
            "tool": {"kind": "quilt_feature", "label": "merge_cap_lower"},
        },
        {
            "op": "quilt_merge",
            "label": "merge_closed_result",
            "target": {"kind": "quilt_feature", "label": "merge_half"},
            "tool": {"kind": "quilt_feature", "label": "merge_cap_upper"},
        },
        {
            "op": "solidify",
            "label": "merge_solid",
            "reference": {"kind": "quilt_feature", "label": "merge_closed_result"},
        },
    ]


def case_merge_offline() -> dict:
    """S03 contract, gate and native wiring. No Creo session is involved."""
    from creo_mechdog.capabilities import UNAVAILABLE_OPERATIONS, require_available
    from creo_mechdog.schema import validate_operations

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    operation = merge_plan()[-1]
    validated = validate_operations([operation])
    check("merge_plan_validates", validated[0]["op"] == "quilt_merge")
    closed_ops = validate_operations(merged_closed_plan())
    check(
        "closed_plan_validates",
        closed_ops[-1]["op"] == "solidify" and closed_ops[5]["op"] == "quilt_merge",
    )

    def rejects(candidate: dict, pattern: str) -> bool:
        try:
            validate_operations([candidate])
        except ValueError as error:
            return pattern in str(error)
        return False

    check(
        "self_merge_rejected",
        rejects({**operation, "tool": dict(operation["target"])}, "distinct"),
    )
    check("body_rejected", rejects({**operation, "tool": {"kind": "body", "id": 3}}, "tool"))
    check(
        "datum_plane_tool_rejected",
        rejects({**operation, "tool": {"kind": "datum_plane", "label": "FRONT"}}, "tool"),
    )
    check(
        "tolerance_rejected",
        rejects({**operation, "tolerance_mm": 0.01}, "tolerance"),
    )

    check("quilt_merge_gated", "quilt_merge" in UNAVAILABLE_OPERATIONS)
    refused = False
    try:
        require_available([operation])
    except ValueError as error:
        refused = "no native job was queued" in str(error)
    check("gate_refuses_before_job", refused)

    generic = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8")
    native = (ROOT / "native" / "quilt_merge.cpp").read_text(encoding="utf-8")
    check(
        "native_included_and_dispatched",
        '#include "quilt_merge.cpp"' in generic and generic.count("generic_quilt_merge(op)") == 1,
    )
    check(
        "native_uses_join_not_default_intersect",
        "PRO_SRF_MRG_JOIN" in native and "PRO_SRF_MRG_INTSCT" not in native,
    )
    check(
        "native_closure_from_shared_probe",
        "quilt_closed_native" in native and "quilt_area_native" in native,
    )
    check(
        "native_no_unproved_tolerance_or_gap",
        "gap_mm" not in native and "tolerance_mm" not in native,
    )

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "offline",
        "passed": passed,
        "native_quilt_merge": "not_verified",
        "gate": UNAVAILABLE_OPERATIONS.get("quilt_merge"),
        "checks": checks,
    }


async def case_merge_live() -> dict:
    """Three models: open join, closed cylinder (with solidify), gap negative."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    jobs: list[str] = []
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        check("session_ready", bool(started.get("connected")), {"state": started.get("state")})
        if not started.get("connected"):
            return {
                "mode": "live",
                "passed": False,
                "native_quilt_merge": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
            }
        capabilities = (await client.call_tool("creo_capabilities", {})).structured_content
        published = "quilt_merge" in (capabilities.get("operations") or [])
        check("quilt_merge_published", published)
        if not published:
            return {
                "mode": "live",
                "passed": False,
                "native_quilt_merge": "gated",
                "note": (
                    "quilt_merge is refused before any job until the live join acceptance "
                    "(plan S03) is on record; no geometry was submitted"
                ),
                "checks": checks,
            }
        run_job = job_runner(client, jobs)

        # 1. Two faces sharing an edge join into one 800 mm2 open quilt.
        state = await run_job("creo_execute_plan", {"operations": merge_plan()})
        detail = state["result"]["operations"][-1]
        expected_open = MERGE_FACE * MERGE_FACE * 2
        area = detail.get("area_mm2")
        check(
            "open_merge_area",
            area is not None and abs(area - expected_open) <= 0.5,
            {
                "expected_mm2": expected_open,
                "area_mm2": area,
                "area_status": detail.get("area_status"),
            },
        )
        check(
            "open_merge_result_quilt_reported",
            detail.get("result_quilt_id") is not None,
            {"result_quilt_id": detail.get("result_quilt_id")},
        )
        check(
            "open_merge_reports_open",
            detail.get("closed") is False,
            {"closed": detail.get("closed"), "closed_status": detail.get("closed_status")},
        )
        check(
            "open_merge_saved_and_reloaded",
            state["result"].get("saved_file_reloaded_and_verified") is True,
            {"saved": state["result"].get("saved_file_reloaded_and_verified")},
        )
        if state.get("model_id"):
            page = (
                await client.call_tool(
                    "creo_inspect_model",
                    {"model_id": state["model_id"], "detail": "full", "section": "quilts"},
                )
            ).structured_content
            records = (page.get("data") or {}).get("quilts") or []
            check(
                "open_merge_reference_readable_after_reload",
                any(
                    record.get("area_mm2") is not None
                    and abs(record["area_mm2"] - expected_open) <= 0.5
                    for record in records
                ),
                {"records": [record.get("area_mm2") for record in records]},
            )

        # 2. Tube plus two caps joins into a closed quilt that solidifies.
        closed_state = await run_job("creo_execute_plan", {"operations": merged_closed_plan()})
        closed_ops = closed_state["result"]["operations"]
        closed_detail = closed_ops[-2] if len(closed_ops) > 1 else closed_ops[-1]
        solid_detail = closed_ops[-1]
        closed_area = closed_detail.get("area_mm2")
        check(
            "closed_merge_area",
            closed_area is not None and abs(closed_area - MERGE_CLOSED_AREA) <= 1.0,
            {
                "expected_mm2": MERGE_CLOSED_AREA,
                "area_mm2": closed_area,
                "area_status": closed_detail.get("area_status"),
            },
        )
        check(
            "closed_merge_reports_closed",
            closed_detail.get("closed") is True,
            {
                "closed": closed_detail.get("closed"),
                "closed_status": closed_detail.get("closed_status"),
            },
        )
        volume = solid_detail.get("volume_mm3")
        check(
            "solidified_volume",
            volume is not None and abs(volume - MERGE_CLOSED_VOLUME) <= 1.0,
            {
                "expected_mm3": MERGE_CLOSED_VOLUME,
                "volume_mm3": volume,
                "keys": sorted(solid_detail),
            },
        )

        # 3. Two faces with a gap must not join into a false closure.
        gap_state = await run_job("creo_execute_plan", {"operations": merge_plan(gap=2.0)})
        gap_detail = (gap_state["result"].get("operations") or [{}])[-1]
        gap_failed = gap_state.get("status") == "failed"
        gap_honest = gap_failed or (
            gap_detail.get("closed") is not True
            and gap_detail.get("area_mm2") is not None
            and abs(gap_detail["area_mm2"] - expected_open) > 0.5
        )
        check(
            "gap_join_does_not_claim_success",
            gap_honest,
            {
                "job_status": gap_state.get("status"),
                "closed": gap_detail.get("closed"),
                "area_mm2": gap_detail.get("area_mm2"),
                "message": str(gap_state.get("message"))[:200],
            },
        )
    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_quilt_merge": "verified" if passed else "failed",
        "jobs": jobs,
        "checks": checks,
    }


PROJECT_WIDTH = 40.0
PROJECT_HEIGHT = 20.0
PROJECT_SOURCE_Z = 10.0
PROJECT_LINE_LENGTH = 30.0
PROJECT_ARC_RADIUS = 8.0

PROJECT_ENTITIES = {
    "line": [{"type": "line", "name": "src", "start": [5.0, 10.0], "end": [35.0, 10.0]}],
    "arc": [
        {
            "type": "arc",
            "name": "src",
            "center": [20.0, 10.0],
            "radius": PROJECT_ARC_RADIUS,
            "start_angle": 0.0,
            "end_angle": 180.0,
        }
    ],
}

PROJECT_EXPECTED = {
    "line": {
        "length_mm": PROJECT_LINE_LENGTH,
        "endpoints_mm": [[5.0, 10.0, 0.0], [35.0, 10.0, 0.0]],
    },
    "arc": {
        "length_mm": math.pi * PROJECT_ARC_RADIUS,
        "endpoints_mm": [
            [20.0 - PROJECT_ARC_RADIUS, 10.0, 0.0],
            [20.0 + PROJECT_ARC_RADIUS, 10.0, 0.0],
        ],
    },
}


def project_plan(source: str) -> list[dict]:
    """A 40x20 fill at z=0, a source sketch at z=10 and a +Z direction plane.

    The source sits 10 mm above the target, so a curve that merely echoes the
    source (z=10) fails every position check below.
    """
    return [
        {
            "op": "sketch",
            "label": "project_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "rect",
                    "min": [0.0, 0.0],
                    "max": [PROJECT_WIDTH, PROJECT_HEIGHT],
                }
            ],
        },
        {"op": "surface_fill", "label": "project_target", "sketch": "project_profile"},
        {
            "op": "sketch",
            "label": "project_src",
            "plane": "XY",
            "offset": PROJECT_SOURCE_Z,
            "entities": PROJECT_ENTITIES[source],
        },
        {
            "op": "datum_plane",
            "label": "project_dir_plane",
            "reference": {"kind": "datum_plane", "axis": "z", "offset": 0.0},
            "offset": PROJECT_SOURCE_Z + 20.0,
        },
    ]


def project_operation(curve_id: int, side: str) -> dict:
    return {
        "op": "project_curve",
        "label": "project_result",
        "target": {"kind": "quilt_feature", "label": "project_target"},
        "source": {"kind": "curve", "id": curve_id},
        "direction_ref": {"kind": "datum_feature", "label": "project_dir_plane"},
        "side": side,
    }


def case_project_offline() -> dict:
    """S04 schema, publication and native route. No Creo session is involved."""
    from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS
    from creo_mechdog.schema import validate_operations

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    valid = {
        "op": "project_curve",
        "label": "project_main",
        "target": {"kind": "quilt", "id": 12},
        "source": {"kind": "curve", "id": 7},
        "direction_ref": {"kind": "datum_feature", "label": "top"},
    }
    try:
        validated = validate_operations([dict(valid)])
        check("schema_accepts_one_quilt_one_curve", validated[0]["side"] == "positive")
    except ValueError as error:
        check("schema_accepts_one_quilt_one_curve", False, {"error": str(error)})

    for name, patch in (
        ("body_target", {"target": {"kind": "body", "id": 1}}),
        ("non_curve_source", {"source": {"kind": "quilt", "id": 12}}),
        ("raw_vector", {"direction": [0.0, 0.0, -1.0]}),
        ("datum_plane_direction", {"direction_ref": {"kind": "datum_plane", "label": "TOP"}}),
    ):
        try:
            validate_operations([{**valid, **patch}])
        except ValueError:
            check(f"schema_refuses_{name}", True)
        else:
            check(f"schema_refuses_{name}", False)

    check("registered", "project_curve" in REGISTERED_OPERATIONS)
    check("published", "project_curve" not in UNAVAILABLE_OPERATIONS)
    native = (ROOT / "native" / "project_curve.cpp").read_text(encoding="utf-8")
    check(
        "native_uses_the_documented_intersect_tree",
        "PRO_CURVE_TYPE_INTSRF" in native and "PRO_E_CRV_IP_COMP_REF1" in native,
    )
    check(
        "native_does_not_guess_undocumented_trees",
        '"PRO_E_COPYTRIM' not in native and '"PRO_E_PROJ_CRV' not in native,
    )
    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_project_curve": "not_verified",
        "checks": checks,
    }


async def case_project_live() -> dict:
    """Measured projections: one line, one arc, and one refused side."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    jobs: list[str] = []

    async def submit(client, operations: list[dict], model_id=None, revision=None) -> dict:
        arguments: dict = {"operations": operations}
        if model_id:
            arguments["model_id"] = model_id
            arguments["expected_revision"] = revision
        state = (await client.call_tool("creo_execute_plan", arguments)).structured_content
        job_id = state.get("job_id")
        if not job_id:
            raise RuntimeError(json.dumps(state)[:500])
        jobs.append(job_id)
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            state = (await client.call_tool("creo_get_job", {"job_id": job_id})).structured_content
            if state["status"] in ("succeeded", "failed", "unknown_outcome"):
                break
            await asyncio.sleep(1)
        else:
            raise TimeoutError("job did not settle; inspect it, never blindly resubmit")
        return state

    async def section(client, model_id: str, name: str) -> dict:
        page = (
            await client.call_tool(
                "creo_inspect_model",
                {"model_id": model_id, "detail": "full", "section": name},
            )
        ).structured_content
        return page.get("data", {}).get(name) or []

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        check(
            "session_ready",
            bool(started.get("connected")),
            {"state": started.get("state"), "message": str(started.get("message"))[:200]},
        )
        if not started.get("connected"):
            return {
                "mode": "live",
                "passed": False,
                "native_project_curve": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
            }
        capabilities = (await client.call_tool("creo_capabilities", {})).structured_content
        published = "project_curve" in (capabilities.get("operations") or [])
        check("project_curve_published", published)
        if not published:
            return {
                "mode": "live",
                "passed": False,
                "native_project_curve": "gated",
                "note": "project_curve is refused before any job; no geometry was submitted",
                "checks": checks,
            }

        for source in ("line", "arc"):
            build = await submit(client, project_plan(source))
            check(
                f"build_{source}",
                build["status"] == "succeeded"
                and build["result"]["saved_file_reloaded_and_verified"],
                {"status": build["status"], "message": build.get("message")},
            )
            if build["status"] != "succeeded":
                continue
            model_id = build["model_id"]
            features = await section(client, model_id, "features")
            source_feature = next(
                (
                    feature
                    for feature in features
                    if str(feature.get("name", "")).lower() == "project_src"
                ),
                None,
            )
            geometry = await section(client, model_id, "feature_geometry")
            curve_ids = [
                item["id"]
                for item in geometry
                if item.get("feature_id") == (source_feature or {}).get("id")
                and item.get("type") == 62
            ]
            check(f"source_curve_{source}", bool(curve_ids), {"curve_ids": curve_ids})
            if not curve_ids:
                continue
            # The build job already reported the revision it left the model at;
            # a second read-only job would hold the model's pending_job and make
            # the next submit busy for no benefit.
            state = await submit(
                client,
                [project_operation(curve_ids[0], "negative")],
                model_id,
                build.get("revision"),
            )
            result = (state.get("result") or {}).get("operations", [{}])[-1]
            expected = PROJECT_EXPECTED[source]
            length = result.get("curve_length_mm")
            endpoints = result.get("endpoints_mm") or []
            check(
                f"project_{source}_succeeded",
                state["status"] == "succeeded" and bool(result.get("curve_id")),
                {"status": state["status"], "message": state.get("message"), "result": result},
            )
            check(
                f"project_{source}_length",
                isinstance(length, (int, float)) and abs(length - expected["length_mm"]) <= 1e-6,
                {"length_mm": length, "expected_mm": expected["length_mm"]},
            )
            check(
                f"project_{source}_endpoints",
                len(endpoints) == 2
                and all(
                    min(math.dist(point, target) for target in expected["endpoints_mm"]) <= 1e-6
                    for point in endpoints
                ),
                {"endpoints_mm": endpoints, "expected_mm": expected["endpoints_mm"]},
            )
            check(
                f"project_{source}_saved_and_reloaded",
                bool((state.get("result") or {}).get("saved_file_reloaded_and_verified")),
            )
            check(
                f"project_{source}_reports_construction",
                result.get("route") == "swept_surface_intersect"
                and isinstance(result.get("helper_feature_id"), int)
                and result.get("direction_basis") == "datum_plane_normal",
                {
                    "route": result.get("route"),
                    "helper_feature_id": result.get("helper_feature_id"),
                    "direction_basis": result.get("direction_basis"),
                },
            )

        # A +Z projection points away from the z=0 target: it must be refused
        # with the measured reason instead of returning a curve on the wrong side.
        build = await submit(client, project_plan("line"))
        if build["status"] == "succeeded":
            model_id = build["model_id"]
            features = await section(client, model_id, "features")
            source_feature = next(
                (
                    feature
                    for feature in features
                    if str(feature.get("name", "")).lower() == "project_src"
                ),
                None,
            )
            geometry = await section(client, model_id, "feature_geometry")
            curve_ids = [
                item["id"]
                for item in geometry
                if item.get("feature_id") == (source_feature or {}).get("id")
                and item.get("type") == 62
            ]
            refused = await submit(
                client,
                [project_operation(curve_ids[0], "positive")],
                model_id,
                build.get("revision"),
            )
            check(
                "wrong_side_refused",
                refused["status"] == "failed"
                and "behind the source curve" in str(refused.get("message")),
                {"status": refused["status"], "message": refused.get("message")},
            )

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_project_curve": "verified" if passed else "failed",
        "jobs": jobs,
        "checks": checks,
    }


SOLIDIFY_CYLINDER_PLAN = [
    {
        "op": "datum_axis",
        "label": "solid_axis",
        "references": [
            {"kind": "datum_plane", "axis": "y"},
            {"kind": "datum_plane", "axis": "z"},
        ],
    },
    {
        "op": "sketch",
        "label": "solid_profile",
        "plane": "XZ",
        "entities": [{"type": "rectangle", "name": "rp", "min": [0.0, 0.0], "max": [5.0, 20.0]}],
    },
    {
        "op": "revolve",
        "label": "solid_wall",
        "sketch": "solid_profile",
        "angle": 360.0,
        "mode": "surface",
        "axis": {"kind": "datum_axis_feature", "label": "solid_axis"},
    },
]

SOLIDIFY_OPEN_PLAN = [
    {
        "op": "sketch",
        "label": "solid_open_profile",
        "plane": "XY",
        "entities": [{"type": "rectangle", "name": "ro", "min": [0.0, 0.0], "max": [40.0, 20.0]}],
    },
    {"op": "surface_fill", "label": "solid_open_face", "sketch": "solid_open_profile"},
]


def case_solidify_offline() -> dict:
    """S06 schema, publication and native criteria. No Creo session is involved."""
    from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS
    from creo_mechdog.schema import validate_operations

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    operation = {
        "op": "solidify",
        "label": "solid_body",
        "reference": {"kind": "quilt", "id": 12},
        "side": "positive",
    }
    try:
        validate_operations([dict(operation)])
        check("schema_accepts_one_quilt", True)
    except ValueError as error:
        check("schema_accepts_one_quilt", False, {"error": str(error)})
    try:
        validate_operations([{**operation, "reference": {"kind": "body", "id": 3}}])
        check("schema_refuses_a_body_reference", False)
    except ValueError:
        check("schema_refuses_a_body_reference", True)

    check("registered", "solidify" in REGISTERED_OPERATIONS)
    check("published", "solidify" not in UNAVAILABLE_OPERATIONS)
    native = (ROOT / "native" / "surfaces.cpp").read_text(encoding="utf-8")
    check("native_measures_the_closure", "quilt_closed_native" in native)
    check("native_refuses_an_open_quilt", "solidify requires a closed quilt" in native)
    check("native_reports_the_volume", "volume_after_mm3" in native)
    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_solidify": "not_verified",
        "checks": checks,
    }


async def case_solidify_live() -> dict:
    """S06 measured criteria: a closed quilt becomes a solid of the right volume."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    jobs: list[str] = []

    async def submit(client, operations, model_id=None, revision=None) -> dict:
        arguments: dict = {"operations": operations}
        if model_id:
            arguments["model_id"] = model_id
            arguments["expected_revision"] = revision
        submitted = (await client.call_tool("creo_execute_plan", arguments)).structured_content
        job_id = (submitted or {}).get("job_id")
        if not job_id:
            raise RuntimeError(json.dumps(submitted)[:400])
        jobs.append(job_id)
        deadline = time.monotonic() + 300
        state: dict = {}
        while time.monotonic() < deadline:
            state = (await client.call_tool("creo_get_job", {"job_id": job_id})).structured_content
            if state.get("status") in ("succeeded", "failed", "unknown_outcome"):
                break
            await asyncio.sleep(2)
        else:
            raise TimeoutError("job did not settle; inspect it, never blindly resubmit")
        results = (state.get("result") or {}).get("operations") or []
        state["operation"] = results[-1] if results else None
        state["saved_verified"] = (state.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        )
        return state

    async def section(client, model_id: str, name: str) -> list:
        page = (
            await client.call_tool(
                "creo_inspect_model",
                {"model_id": model_id, "detail": "full", "section": name},
            )
        ).structured_content
        return (page.get("data") or {}).get(name) or []

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        check(
            "session_ready",
            bool(started.get("connected")),
            {"state": started.get("state"), "message": str(started.get("message"))[:200]},
        )
        if not started.get("connected"):
            return {
                "mode": "live",
                "passed": False,
                "native_solidify": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
            }

        built = await submit(client, SOLIDIFY_CYLINDER_PLAN)
        check(
            "closed_quilt_built",
            built["status"] == "succeeded",
            {"status": built.get("status"), "message": built.get("message")},
        )
        if built["status"] != "succeeded":
            return {
                "mode": "live",
                "passed": False,
                "native_solidify": "failed",
                "checks": checks,
            }
        model_id = built["model_id"]
        quilts = await section(client, model_id, "quilts")
        check(
            "quilt_is_closed", bool(quilts) and quilts[0].get("closed") is True, {"quilts": quilts}
        )
        if not quilts:
            return {
                "mode": "live",
                "passed": False,
                "native_solidify": "failed",
                "checks": checks,
            }
        quilt = quilts[0]
        bbox = quilt.get("bbox_mm") or []
        radius = (bbox[1][1] - bbox[0][1]) / 2.0 if len(bbox) == 2 else 0.0
        height = (bbox[1][0] - bbox[0][0]) if len(bbox) == 2 else 0.0
        expected_volume = math.pi * radius * radius * height
        expected_area = 2 * math.pi * radius * height + 2 * math.pi * radius * radius
        check(
            "closed_quilt_area_matches_oracle",
            abs(float(quilt.get("area_mm2") or 0.0) - expected_area) <= 0.5,
            {"area_mm2": quilt.get("area_mm2"), "expected_mm2": expected_area},
        )

        solidified = await submit(
            client,
            [
                {
                    "op": "solidify",
                    "label": "solid_body",
                    "reference": {"kind": "quilt", "id": quilt.get("quilt_id")},
                    "side": "positive",
                }
            ],
            model_id,
            built.get("revision"),
        )
        operation = solidified.get("operation") or {}
        volume = operation.get("volume_after_mm3")
        check(
            "solidify_succeeded",
            solidified["status"] == "succeeded" and solidified.get("saved_verified") is True,
            {"status": solidified.get("status"), "message": solidified.get("message")},
        )
        check(
            "volume_matches_oracle",
            isinstance(volume, (int, float)) and abs(volume - expected_volume) <= 0.5,
            {"volume_after_mm3": volume, "expected_mm3": expected_volume},
        )
        check(
            "closure_is_reported",
            (operation.get("closure") or {}).get("available") is True,
            {"closure": operation.get("closure")},
        )

        open_build = await submit(client, SOLIDIFY_OPEN_PLAN)
        if open_build["status"] == "succeeded":
            open_model = open_build["model_id"]
            open_quilts = await section(client, open_model, "quilts")
            open_quilt = open_quilts[0] if open_quilts else {}
            refused = await submit(
                client,
                [
                    {
                        "op": "solidify",
                        "label": "solid_open",
                        "reference": {"kind": "quilt", "id": open_quilt.get("quilt_id")},
                        "side": "positive",
                    }
                ],
                open_model,
                open_build.get("revision"),
            )
            check(
                "open_quilt_refused",
                refused["status"] == "failed" and "closed quilt" in str(refused.get("message")),
                {"status": refused.get("status"), "message": refused.get("message")},
            )
            after = await section(client, open_model, "quilts")
            check(
                "open_quilt_untouched_after_refusal",
                bool(after) and abs(float(after[0].get("area_mm2") or 0.0) - 800.0) <= 0.5,
                {"quilts_after": after},
            )

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_solidify": "verified" if passed else "failed",
        "jobs": jobs,
        "checks": checks,
    }


def run_case(case: str, live: bool) -> dict:
    if case == "quilts":
        return asyncio.run(case_quilts_live()) if live else case_quilts_offline()
    if case == "trim":
        return asyncio.run(case_trim_live()) if live else case_trim_offline()
    if case == "sweep_surface":
        return asyncio.run(case_sweep_live(wait_ready)) if live else case_sweep_offline()
    if case == "join":
        return asyncio.run(case_join_live(wait_ready)) if live else case_join_offline()
    if case == "offset":
        return asyncio.run(case_offset_live(wait_ready)) if live else case_offset_offline()
    if case == "group":
        return asyncio.run(case_group_live(wait_ready)) if live else case_group_offline()
    if case == "chain_open":
        return asyncio.run(case_chain_open_live(wait_ready)) if live else case_chain_open_offline()
    if case == "chain_closed":
        return (
            asyncio.run(case_chain_closed_live(wait_ready, SOLIDIFY_CYLINDER_PLAN, "solid_profile"))
            if live
            else case_chain_closed_offline(SOLIDIFY_CYLINDER_PLAN)
        )
    if case == "merge":
        return asyncio.run(case_merge_live()) if live else case_merge_offline()
    if case == "project":
        return asyncio.run(case_project_live()) if live else case_project_offline()
    if case == "solidify":
        return asyncio.run(case_solidify_live()) if live else case_solidify_offline()
    raise SystemExit(BUSY_EXIT, f"unknown case: {case}; available: {', '.join(CASES)}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="quilts", help=f"case to run, one of: {', '.join(CASES)}")
    parser.add_argument(
        "--example",
        default="",
        help="run an example plan file (examples/*.json) instead of a case",
    )
    parser.add_argument(
        "--live", action="store_true", help="run against the connected Creo session"
    )
    parser.add_argument(
        "--confirm-session-usable",
        action="store_true",
        help="second required key that the session was verified usable",
    )
    args = parser.parse_args()
    if args.example:
        example_path = Path(args.example)
        if not example_path.is_absolute():
            example_path = ROOT / example_path
        if not example_path.exists():
            parser.exit(BUSY_EXIT, f"example file not found: {args.example}\n")
        args.case = f"example:{example_path.name}"
    elif args.case not in CASES:
        parser.exit(BUSY_EXIT, f"unknown case: {args.case}; available: {', '.join(CASES)}\n")
    if args.live != args.confirm_session_usable:
        parser.exit(
            BUSY_EXIT,
            "--live and --confirm-session-usable must be given together\n",
        )

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + f"{time.time_ns() % 1_000_000:06d}"
    )
    run_dir = ROOT / "build" / "surface_chain" / run_id
    if run_dir.exists():
        parser.exit(OVERWRITE_EXIT, f"run directory already exists: {run_dir}\n")
    run_dir.mkdir(parents=True)

    report = {
        "run_id": run_id,
        "case": args.case,
        "mode": "live" if args.live else "offline",
        "version": VERSION,
        "command": "tools/test_surface_chain.py " + " ".join(sys.argv[1:]),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    if args.example:
        outcome = (
            asyncio.run(case_example_live(wait_ready, example_path))
            if args.live
            else case_example_offline(example_path)
        )
    else:
        outcome = run_case(args.case, args.live)
    report.update(outcome)
    path = run_dir / "report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "report": str(path), "passed": report["passed"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
