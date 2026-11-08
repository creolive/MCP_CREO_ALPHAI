"""FEAT-039/H04: group-level boundary measurement (open edges, gap, overlap).

The group is two 40x20 planar fills whose second patch is shifted along X:

* ``coincident`` (offset 40.000): the seam edges coincide -> closed, gap ~0;
* ``micro_gap`` (offset 40.005): the seam is inside the 0.01 mm tolerance ->
  micro_gap with gap_max ~0.005 mm;
* ``gap`` (offset 40.500): the seam is outside tolerance but inside the 1 mm
  search window -> open with gap_max ~0.5 mm;
* ``overlap`` (offset 39.500): the patches overlap 0.5 x 20 = 10 mm2 -> overlap.

Each case is built and saved by its own job (``saved_file_reloaded_and_verified``)
and then measured with the read-only ``creo_measure_surface_group`` tool, so the
measurement runs on the reloaded model and the revision does not advance.

Usage:
  python tools/test_surface_chain.py --case group
  python tools/test_surface_chain.py --case group --live --confirm-session-usable
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:  # the driver runs as a script and as a package module
    from surface_chain_chains import call_tool, make_checks, section, submit_plan
except ImportError:  # pragma: no cover - the package import path
    from tools.surface_chain_chains import call_tool, make_checks, section, submit_plan

ROOT = Path(__file__).resolve().parents[1]

PATCH_WIDTH = 40.0
PATCH_HEIGHT = 20.0
PATCH_AREA = PATCH_WIDTH * PATCH_HEIGHT
TOLERANCE_MM = 0.01
GAP_SEARCH_MM = 1.0

# name, second-patch x offset, expected state, expected gap (mm), expected open edges
CASES: tuple[tuple[str, float, str, float, int], ...] = (
    ("coincident", 40.0, "closed", 0.0, 6),
    ("micro_gap", 40.005, "micro_gap", 0.005, 6),
    ("gap", 40.5, "open", 0.5, 8),
    ("overlap", 39.5, "overlap", 0.5, 8),
)
GAP_TOLERANCE_MM = 1e-4


def patches_plan(offset: float) -> list[dict[str, Any]]:
    """Two 40x20 coplanar fills; the second one shifted by ``offset`` mm in X."""
    return [
        {
            "op": "sketch",
            "label": "group_profile_a",
            "plane": "XY",
            # Coordinates dimensioning keeps the requested coordinates exactly;
            # autodim rounds the profile to 0.01 mm on this session (measured
            # 2026-11-07), which would move a 0.005 mm seam onto the tolerance.
            "dimensioning": "coordinates",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "rect_a",
                    "min": [0.0, 0.0],
                    "max": [PATCH_WIDTH, PATCH_HEIGHT],
                }
            ],
        },
        {"op": "surface_fill", "label": "group_patch_a", "sketch": "group_profile_a"},
        {
            "op": "sketch",
            "label": "group_profile_b",
            "plane": "XY",
            "dimensioning": "coordinates",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "rect_b",
                    "min": [offset, 0.0],
                    "max": [offset + PATCH_WIDTH, PATCH_HEIGHT],
                }
            ],
        },
        {"op": "surface_fill", "label": "group_patch_b", "sketch": "group_profile_b"},
    ]


def case_group_offline() -> dict:
    """Contract before any geometry exists."""
    from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS
    from creo_mechdog.job_projection import compact_operation
    from creo_mechdog.operation_results import SURFACE_GROUP_STATES, normalize_surface_group
    from creo_mechdog.schema import validate_operations

    checks, check = make_checks()

    try:
        validated = validate_operations(
            [
                {
                    "op": "surface_group_measure",
                    "references": [{"kind": "quilt", "id": 21}, {"kind": "quilt", "id": 22}],
                }
            ]
        )[0]
        check(
            "schema_defaults",
            validated["tolerance_mm"] == TOLERANCE_MM
            and validated["gap_search_mm"] == GAP_SEARCH_MM,
            {"operation": validated},
        )
    except ValueError as error:
        check("schema_defaults", False, {"error": str(error)})

    for name, references in {
        "duplicate": [{"kind": "quilt", "id": 21}, {"kind": "quilt", "id": 21}],
        "datum_plane": [{"kind": "datum_plane", "label": "TOP"}],
        "empty": [],
    }.items():
        try:
            validate_operations([{"op": "surface_group_measure", "references": references}])
        except ValueError:
            check(f"schema_refuses_{name}", True)
        else:
            check(f"schema_refuses_{name}", False)

    check("registered", "surface_group_measure" in REGISTERED_OPERATIONS)
    check("published", "surface_group_measure" not in UNAVAILABLE_OPERATIONS)
    check("four_states_frozen", SURFACE_GROUP_STATES == ("closed", "open", "micro_gap", "overlap"))

    compact = compact_operation(
        {
            "op": "surface_group_measure",
            "group": {"state": "closed", "open_edges": 6},
        }
    )
    check("compact_keeps_group", compact.get("group", {}).get("open_edges") == 6, compact)

    cleaned = normalize_surface_group(
        {
            "open_edges": 6,
            "open_edges_status": {"available": False, "reason": "boundary_edge_visit_failed"},
            "state": "closed",
            "state_reason": None,
        }
    )
    check(
        "unavailable_status_nulls_the_count",
        cleaned["open_edges"] is None and cleaned["state"] == "closed",
        cleaned,
    )

    native = (ROOT / "native" / "surface_group.cpp").read_text(encoding="utf-8")
    check(
        "native_uses_real_boundary_queries",
        all(
            api in native
            for api in (
                "ProContourEdgeVisit",
                "ProEdgeTessellationGet",
                "ProSurfaceUvpntVerify",
                "ProSurfaceParamEval",
            )
        ),
    )
    check(
        "native_does_not_derive_the_answer_from_area_or_volume",
        "ProQuiltVolumeEval(" not in native and "quilt_area_native" not in native,
    )
    check(
        "loft_chain_receipt_carries_the_group_block",
        'details["surface_group"]'
        in (ROOT / "native" / "surface_loft.cpp").read_text(encoding="utf-8"),
    )
    tools = (ROOT / "server.py").read_text(encoding="utf-8")
    check(
        "readonly_tool_and_source_identity",
        "creo_measure_surface_group" in tools and '"native/surface_group.cpp"' in tools,
    )

    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_surface_group": "not_verified",
        "checks": checks,
    }


def _quilts_of(records: list) -> list[int]:
    patches = [
        int(record["quilt_id"])
        for record in records
        if abs(float(record.get("area_mm2") or 0.0) - PATCH_AREA) <= 0.5
    ]
    return patches


async def case_group_live(wait_ready) -> dict:
    """Four seam conditions on the connected session."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks, check = make_checks()
    jobs: list[str] = []
    measurements: dict[str, Any] = {}

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
                "native_surface_group": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
            }

        for name, offset, state, gap, open_edges in CASES:
            built = await submit_plan(client, patches_plan(offset), jobs)
            check(
                f"{name}_group_built",
                built.get("status") == "succeeded" and built.get("saved_verified") is True,
                {
                    "status": built.get("status"),
                    "saved_file_reloaded_and_verified": built.get("saved_verified"),
                    "message": str(built.get("message"))[:240],
                },
            )
            if built.get("status") != "succeeded":
                continue
            built_revision = built.get("revision")
            quilts = _quilts_of(await section(client, built["model_id"], "quilts"))
            check(f"{name}_two_800_patches", len(quilts) == 2, {"quilt_ids": quilts})
            if len(quilts) != 2:
                continue

            measured = await call_tool(
                client,
                "creo_measure_surface_group",
                {
                    "model_id": built["model_id"],
                    "references": [{"kind": "quilt", "id": quilt} for quilt in quilts],
                    "tolerance_mm": TOLERANCE_MM,
                    "gap_search_mm": GAP_SEARCH_MM,
                },
            )
            group = measured.get("group") or {}
            record = {
                "job_id": measured.get("job_id"),
                "model_id": built["model_id"],
                "build_job_id": built.get("job_id"),
                "built_revision": built_revision,
                "measured_revision": measured.get("revision"),
                "quilt_ids": quilts,
                "unit_name": measured.get("unit_name"),
                "state": group.get("state"),
                "state_reason": group.get("state_reason"),
                "open_edges": group.get("open_edges"),
                "boundary_edges": group.get("boundary_edges"),
                "joined_edges": group.get("joined_edges"),
                "boundary_closed": group.get("boundary_closed"),
                "gap_max_mm": group.get("gap_max_mm"),
                "gap_status": group.get("gap_max_status"),
                "overlap_area_mm2": group.get("overlap_area_mm2"),
                "overlap_status": group.get("overlap_status"),
                "open_edges_status": group.get("open_edges_status"),
            }
            measurements[name] = record
            if record["job_id"]:
                jobs.append(record["job_id"])

            check(
                f"{name}_measurement_finished",
                bool(record["job_id"]) and group.get("state") is not None,
                {"state": group.get("state"), "state_reason": group.get("state_reason")},
            )
            check(
                f"{name}_state_is_{state}",
                group.get("state") == state,
                {"state": group.get("state"), "reason": group.get("state_reason")},
            )
            check(
                f"{name}_open_edges_{open_edges}",
                group.get("open_edges") == open_edges,
                {"open_edges": group.get("open_edges")},
            )
            gap_value = group.get("gap_max_mm")
            check(
                f"{name}_gap_max_{gap}",
                isinstance(gap_value, (int, float))
                and not isinstance(gap_value, bool)
                and abs(float(gap_value) - gap) <= GAP_TOLERANCE_MM,
                {"gap_max_mm": gap_value},
            )
            overlap_status = group.get("overlap_status") or {}
            expected_overlap = state == "overlap"
            check(
                f"{name}_overlap_detected_{str(expected_overlap).lower()}",
                overlap_status.get("detected") is expected_overlap,
                {
                    "detected": overlap_status.get("detected"),
                    "area": group.get("overlap_area_mm2"),
                    "buried": overlap_status.get("buried_boundary_edges"),
                },
            )
            check(
                f"{name}_overlap_budget_diagnostics",
                overlap_status.get("sample_budget") == 20000
                and isinstance(overlap_status.get("faces_total"), int)
                and isinstance(overlap_status.get("sample_tests_required"), int)
                and isinstance(overlap_status.get("sample_tests_attempted"), int)
                and overlap_status.get("budget_exceeded") is False
                and overlap_status.get("partial") is False
                and isinstance(overlap_status.get("sample_test_coverage"), (int, float))
                and abs(float(overlap_status["sample_test_coverage"]) - 1.0) <= 1e-9,
                {
                    "sample_budget": overlap_status.get("sample_budget"),
                    "faces": [
                        overlap_status.get("faces_sampled"),
                        overlap_status.get("faces_total"),
                    ],
                    "tests": [
                        overlap_status.get("sample_tests_attempted"),
                        overlap_status.get("sample_tests_required"),
                    ],
                    "coverage": overlap_status.get("sample_test_coverage"),
                },
            )
            if expected_overlap:
                area = group.get("overlap_area_mm2")
                check(
                    f"{name}_overlap_area_is_small_but_present",
                    overlap_status.get("buried_boundary_edges", 0) >= 1
                    or (
                        isinstance(area, (int, float))
                        and not isinstance(area, bool)
                        and 0.0 < float(area) <= 20.0
                    ),
                    {"area_mm2": area, "status": overlap_status},
                )
            check(
                f"{name}_revision_unchanged_by_the_read_only_query",
                measured.get("revision") == built_revision,
                {"built": built_revision, "measured": measured.get("revision")},
            )
            check(
                f"{name}_units_are_mm",
                measured.get("unit_name") == "mm" and measured.get("length_scale_to_mm") == 1.0,
                {"unit": measured.get("unit_name"), "scale": measured.get("length_scale_to_mm")},
            )
            check(
                f"{name}_boundary_is_an_open_sheet",
                group.get("boundary_closed") is False,
                {"boundary_closed": group.get("boundary_closed")},
            )

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_surface_group": "verified" if passed else "failed",
        "jobs": jobs,
        "measurements": measurements,
        "checks": checks,
    }
