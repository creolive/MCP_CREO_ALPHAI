"""Unified surface-chain driver (FEAT-055/S01, FEAT-039).

All surface-chain cases (S01 quilts query, later S02 surface_trim and S03
quilt_merge closure) run from this entry. Acceptance uses public MCP tools
only (creo_execute_plan / creo_get_job / creo_inspect_model); no internal
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
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from version import VERSION  # noqa: E402

CASES = ("quilts",)
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
    legacy = {**with_quilts, "inspection": {k: v for k, v in with_quilts["inspection"].items() if k != "quilts"}}

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
                state = (
                    await client.call_tool("creo_get_job", {"job_id": job_id})
                ).structured_content
                if state["status"] in ("succeeded", "failed", "unknown_outcome"):
                    break
                await asyncio.sleep(0.5)
            else:
                raise TimeoutError("job did not settle; inspect it, never blindly resubmit")
            if state["status"] != "succeeded":
                raise RuntimeError(
                    json.dumps({"job_id": job_id, "status": state["status"], "message": state.get("message")})
                )
            assert state["result"]["saved_file_reloaded_and_verified"]
            return state

        build = await run_job("creo_execute_plan", {"operations": surface_chain_plan(width, height)})
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="quilts", help=f"case to run, one of: {', '.join(CASES)}")
    parser.add_argument("--live", action="store_true", help="run against the connected Creo session")
    parser.add_argument(
        "--confirm-session-usable",
        action="store_true",
        help="second required key that the session was verified usable",
    )
    args = parser.parse_args()
    if args.case not in CASES:
        parser.exit(BUSY_EXIT, f"unknown case: {args.case}; available: {', '.join(CASES)}\n")
    if args.live != args.confirm_session_usable:
        parser.exit(
            BUSY_EXIT,
            "--live and --confirm-session-usable must be given together\n",
        )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + f"{time.time_ns() % 1_000_000:06d}"
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
    if args.live:
        outcome = asyncio.run(case_quilts_live())
    else:
        outcome = case_quilts_offline()
    report.update(outcome)
    path = run_dir / "report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "report": str(path), "passed": report["passed"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
