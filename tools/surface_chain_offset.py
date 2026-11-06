"""S09 surface_offset distance applicability (FEAT-039/R01).

The offset wall volume divided by the source area is the offset distance only
when the part had no solid before the offset and the source is exactly one
planar face. This case pins that gate and then exercises it:

* offline: schema, compact projection and native gate contract, plus the
  normalize/annotate helper on synthetic receipts;
* ``--live --confirm-session-usable``: a 40x20 fill offset 5 mm on both sides
  of two empty models (distance published), a fill offset in a part that
  already holds a solid (``pre_existing_volume``), and a cylindrical quilt
  (``source_quilt_not_a_single_plane``). Both refused cases must keep the
  distance null instead of publishing a plausible number.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

try:  # the driver runs as a script and as a package module
    from surface_chain_chains import make_checks, section, submit_plan
except ImportError:  # pragma: no cover - the package import path
    from tools.surface_chain_chains import make_checks, section, submit_plan

ROOT = Path(__file__).resolve().parents[1]

OFFSET_DISTANCE = 5.0
RECT_WIDTH = 40.0
RECT_HEIGHT = 20.0
PATCH_AREA = RECT_WIDTH * RECT_HEIGHT
SOLID_DEPTH = 10.0
SOLID_VOLUME = PATCH_AREA * SOLID_DEPTH
CYLINDER_RADIUS = 20.0
CYLINDER_DEPTH = 12.0
DISTANCE_TOLERANCE = 1e-6
VOLUME_TOLERANCE = 1e-3


def patch_plan() -> list[dict[str, Any]]:
    """One 40x20 planar fill: the source the offset gate accepts."""
    return [
        {
            "op": "sketch",
            "label": "offset_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "rect",
                    "min": [0.0, 0.0],
                    "max": [RECT_WIDTH, RECT_HEIGHT],
                }
            ],
        },
        {"op": "surface_fill", "label": "offset_patch", "sketch": "offset_profile"},
    ]


def solid_plus_patch_plan() -> list[dict[str, Any]]:
    """A solid block plus a planar fill: the volume before the offset is not 0."""
    return [
        {
            "op": "sketch",
            "label": "block_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "block",
                    "min": [0.0, 0.0],
                    "max": [RECT_WIDTH, RECT_HEIGHT],
                }
            ],
        },
        {
            "op": "extrude",
            "label": "offset_block",
            "sketch": "block_profile",
            "depth": SOLID_DEPTH,
        },
        {
            "op": "sketch",
            "label": "solid_patch_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "patch",
                    "min": [0.0, 0.0],
                    "max": [RECT_WIDTH, RECT_HEIGHT],
                }
            ],
        },
        {
            "op": "surface_fill",
            "label": "solid_patch",
            "sketch": "solid_patch_profile",
        },
    ]


def cylinder_surface_plan() -> list[dict[str, Any]]:
    """One cylindrical quilt: a single face that is not planar."""
    return [
        {
            "op": "sketch",
            "label": "cylinder_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "circle",
                    "name": "circle",
                    "center": [0.0, 0.0],
                    "radius": CYLINDER_RADIUS,
                }
            ],
        },
        {
            "op": "extrude",
            "label": "cylinder_quilt",
            "sketch": "cylinder_profile",
            "mode": "surface",
            "depth": CYLINDER_DEPTH,
        },
    ]


def offset_operation(quilt_id: int, side: str) -> dict[str, Any]:
    return {
        "op": "surface_offset",
        "label": f"offset_wall_{side}",
        "reference": {"kind": "quilt", "id": quilt_id},
        "distance": OFFSET_DISTANCE,
        "side": side,
    }


def case_offset_offline() -> dict:
    """The gate contract before any geometry is built."""
    from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS
    from creo_mechdog.operation_results import annotate_offset_distance_status
    from creo_mechdog.schema import validate_operations

    checks, check = make_checks()

    try:
        validate_operations([dict(operation) for operation in patch_plan()])
        validated = validate_operations([offset_operation(12, "positive")])
        check(
            "schema_accepts_a_quilt_offset",
            validated[0]["side"] == "positive"
            and float(validated[0]["distance"]) == OFFSET_DISTANCE,
        )
    except ValueError as error:
        check("schema_accepts_a_quilt_offset", False, {"error": str(error)})

    for name, patch in (
        ("body_reference", {"reference": {"kind": "body", "id": 1}}),
        ("datum_plane_reference", {"reference": {"kind": "datum_plane", "label": "TOP"}}),
        ("zero_distance", {"distance": 0}),
        ("unknown_side", {"side": "both"}),
    ):
        try:
            validate_operations([{**offset_operation(12, "positive"), **patch}])
        except ValueError:
            check(f"schema_refuses_{name}", True)
        else:
            check(f"schema_refuses_{name}", False)

    check("registered", "surface_offset" in REGISTERED_OPERATIONS)
    check("published", "surface_offset" not in UNAVAILABLE_OPERATIONS)

    native = (ROOT / "native" / "surfaces.cpp").read_text(encoding="utf-8")
    check(
        "native_gate_requires_an_empty_part_and_one_planar_face",
        "const bool single_planar_source" in native
        and "const bool empty_before" in native
        and "area_known && single_planar_source && empty_before && result_volume_known" in native,
    )
    check(
        "native_names_each_refusal_reason",
        all(
            reason in native
            for reason in (
                "source_area_unavailable",
                "source_surface_visit_failed",
                "source_quilt_not_a_single_plane",
                "pre_offset_volume_unavailable",
                "pre_existing_volume",
                "result_volume_unavailable",
            )
        ),
    )
    check(
        "native_distance_is_the_volume_over_area_ratio",
        "(volume_after - volume_before) / source_area" in native,
    )

    projection = (ROOT / "src" / "creo_mechdog" / "job_projection.py").read_text(encoding="utf-8")
    check("compact_projection_keeps_the_distance_status", '"offset_distance_status"' in projection)

    annotated = annotate_offset_distance_status(
        {
            "operations": [
                {"op": "surface_offset", "measured_offset_distance_mm": 5.0},
                {
                    "op": "surface_offset",
                    "measured_offset_distance_mm": 6.25,
                    "offset_distance_status": {
                        "available": False,
                        "reason": "pre_existing_volume",
                    },
                },
                {
                    "op": "surface_offset",
                    "measured_offset_distance_mm": 6.25,
                    "offset_distance_status": "not-a-block",
                },
            ]
        }
    )
    legacy, refused, malformed = annotated["operations"]
    check(
        "legacy_record_without_status_is_untouched",
        "offset_distance_status" not in legacy and legacy.get("measured_offset_distance_mm") == 5.0,
        {"operation": legacy},
    )
    check(
        "unavailable_status_nulls_the_measurement",
        refused["offset_distance_status"]["reason"] == "pre_existing_volume"
        and refused["offset_distance_status"]["available"] is False
        and refused["measured_offset_distance_mm"] is None,
        {"operation": refused},
    )
    check(
        "malformed_status_is_named_not_read_as_available",
        malformed["offset_distance_status"]["reason"] == "offset_distance_status_missing"
        and malformed["measured_offset_distance_mm"] is None,
        {"operation": malformed},
    )

    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_offset_distance": "not_verified",
        "checks": checks,
    }


def _status_of(state: dict) -> dict:
    operation = state.get("operation") or {}
    return operation.get("offset_distance_status") or {}


def _measured(state: dict) -> float | None:
    value = (state.get("operation") or {}).get("measured_offset_distance_mm")
    return None if value is None else float(value)


def _quilts_with_area(quilts: list, area: float) -> list:
    return [record for record in quilts if abs(float(record.get("area_mm2") or 0.0) - area) <= 0.5]


async def case_offset_live(wait_ready) -> dict:
    """Distance applicability on an empty, an occupied and a curved part."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks, check = make_checks()
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
            return {
                "mode": "live",
                "passed": False,
                "native_offset_distance": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
            }

        capabilities = (await client.call_tool("creo_capabilities", {})).structured_content
        published = "surface_offset" in (capabilities.get("operations") or [])
        check("surface_offset_published", published)
        if not published:
            return {
                "mode": "live",
                "passed": False,
                "native_offset_distance": "not_verified",
                "note": "surface_offset is not published; nothing was submitted",
                "checks": checks,
            }

        # A. Empty part, one 40x20 planar fill, offset 5 mm on each side. Each
        # side gets its own empty model: the first wall would otherwise make the
        # second model not empty and the gate would refuse the second number.
        for side in ("positive", "negative"):
            built = await submit_plan(client, patch_plan(), jobs)
            check(
                f"empty_patch_built_{side}",
                built.get("status") == "succeeded",
                {"status": built.get("status"), "message": str(built.get("message"))[:200]},
            )
            if built.get("status") != "succeeded":
                continue
            quilts = await section(client, built["model_id"], "quilts")
            patches = _quilts_with_area(quilts, PATCH_AREA)
            check(f"empty_patch_is_800_{side}", len(patches) == 1, {"quilts": quilts})
            if len(patches) != 1:
                continue
            offset = await submit_plan(
                client,
                [offset_operation(int(patches[0]["quilt_id"]), side)],
                jobs,
                built["model_id"],
                built.get("revision"),
            )
            operation = offset.get("operation") or {}
            status = _status_of(offset)
            measured = _measured(offset)
            check(
                f"offset_succeeded_{side}",
                offset.get("status") == "succeeded",
                {"status": offset.get("status"), "message": str(offset.get("message"))[:200]},
            )
            check(
                f"empty_planar_publishes_distance_{side}",
                status.get("available") is True
                and status.get("source") == "volume_over_source_area"
                and measured is not None
                and abs(measured - OFFSET_DISTANCE) <= DISTANCE_TOLERANCE,
                {"status": status, "measured": measured},
            )
            wall_volume = (operation.get("volume_after_mm3") or 0.0) - (
                operation.get("volume_before_mm3") or 0.0
            )
            check(
                f"offset_wall_volume_is_area_times_distance_{side}",
                abs(wall_volume - PATCH_AREA * OFFSET_DISTANCE) <= VOLUME_TOLERANCE,
                {
                    "wall_volume_mm3": wall_volume,
                    "volume_before_mm3": operation.get("volume_before_mm3"),
                    "volume_after_mm3": operation.get("volume_after_mm3"),
                },
            )
            check(
                f"offset_direction_is_reported_{side}",
                operation.get("direction") == side,
                {"direction": operation.get("direction")},
            )
            check(
                f"offset_saved_and_reloaded_{side}",
                offset.get("saved_verified") is True,
                {"saved_file_reloaded_and_verified": offset.get("saved_verified")},
            )

        # B. A part that already holds a solid: the numerator carries the old
        # volume, so the ratio is not a distance.
        occupied = await submit_plan(client, solid_plus_patch_plan(), jobs)
        check(
            "occupied_part_built",
            occupied.get("status") == "succeeded",
            {"status": occupied.get("status"), "message": str(occupied.get("message"))[:200]},
        )
        if occupied.get("status") == "succeeded":
            quilts = await section(client, occupied["model_id"], "quilts")
            patches = _quilts_with_area(quilts, PATCH_AREA)
            check("occupied_patch_found", len(patches) == 1, {"quilts": quilts})
            if len(patches) == 1:
                offset = await submit_plan(
                    client,
                    [offset_operation(int(patches[0]["quilt_id"]), "positive")],
                    jobs,
                    occupied["model_id"],
                    occupied.get("revision"),
                )
                operation = offset.get("operation") or {}
                status = _status_of(offset)
                check(
                    "occupied_part_offset_succeeded",
                    offset.get("status") == "succeeded",
                    {"status": offset.get("status"), "message": str(offset.get("message"))[:200]},
                )
                check(
                    "pre_existing_volume_keeps_the_distance_null",
                    status.get("available") is False
                    and status.get("reason") == "pre_existing_volume"
                    and _measured(offset) is None,
                    {"status": status, "measured": _measured(offset)},
                )
                check(
                    "pre_existing_volume_is_reported_not_guessed",
                    abs(float(operation.get("volume_before_mm3") or 0.0) - SOLID_VOLUME)
                    <= VOLUME_TOLERANCE,
                    {"volume_before_mm3": operation.get("volume_before_mm3")},
                )
                check(
                    "occupied_part_offset_saved_and_reloaded",
                    offset.get("saved_verified") is True,
                    {"saved_file_reloaded_and_verified": offset.get("saved_verified")},
                )

        # C. A cylindrical quilt is one face, but not a plane: a constant-normal
        # offset is not an area sweep, so no measured distance is published.
        curved = await submit_plan(client, cylinder_surface_plan(), jobs)
        check(
            "curved_quilt_built",
            curved.get("status") == "succeeded",
            {"status": curved.get("status"), "message": str(curved.get("message"))[:200]},
        )
        if curved.get("status") == "succeeded":
            quilts = await section(client, curved["model_id"], "quilts")
            check("curved_quilt_found", len(quilts) >= 1, {"quilts": quilts})
            if quilts:
                offset = await submit_plan(
                    client,
                    [offset_operation(int(quilts[0]["quilt_id"]), "positive")],
                    jobs,
                    curved["model_id"],
                    curved.get("revision"),
                )
                status = _status_of(offset)
                check(
                    "curved_quilt_offset_succeeded",
                    offset.get("status") == "succeeded",
                    {"status": offset.get("status"), "message": str(offset.get("message"))[:200]},
                )
                check(
                    "curved_source_keeps_the_distance_null",
                    status.get("available") is False
                    and status.get("reason") == "source_quilt_not_a_single_plane"
                    and _measured(offset) is None,
                    {"status": status, "measured": _measured(offset)},
                )
                area = (offset.get("operation") or {}).get("source_area_mm2")
                check(
                    "curved_source_area_is_still_reported",
                    area is not None
                    and math.isfinite(float(area))
                    and abs(float(area) - 2 * math.pi * CYLINDER_RADIUS * CYLINDER_DEPTH) <= 0.5,
                    {"source_area_mm2": area},
                )

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_offset_distance": "verified" if passed else "failed",
        "jobs": jobs,
        "checks": checks,
    }
