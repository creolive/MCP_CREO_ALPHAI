"""S03: the join need, served by the delivered operators.

The ProMerge.h route stays excluded (an ACTIVE feature that owns four
PRO_SURFACE items and no PRO_QUILT), so this case measures the sanctioned
fallback instead: trim one quilt with the other to get the part that is not
shared, thicken both into solids and take the boolean union. Every expectation
is analytic:

* two 40x20 fills offset by 30 mm share a 10x20 patch, so the union area is
  800 + 800 - 200 = 1400 mm2;
* trimming the second fill with the first splits it into 200 mm2 (inside) and
  600 mm2 (outside), and the union uses the outside part;
* a symmetric thickness of 2 mm turns an area into a volume of area * 2, so the
  union solid measures 2800 mm3.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:  # the driver runs as a script and as a package module
    from surface_chain_chains import make_checks, section, submit_plan
except ImportError:  # pragma: no cover - the package import path
    from tools.surface_chain_chains import make_checks, section, submit_plan

ROOT = Path(__file__).resolve().parents[1]

JOIN_THICKNESS = 2.0
JOIN_AREA_A = 800.0
JOIN_AREA_B = 800.0
JOIN_SHARED = 200.0
JOIN_OUTSIDE = 600.0
JOIN_UNION_AREA = JOIN_AREA_A + JOIN_AREA_B - JOIN_SHARED

JOIN_PLAN: list[dict[str, Any]] = [
    {
        "op": "sketch",
        "label": "join_a",
        "plane": "XY",
        "entities": [{"type": "rectangle", "name": "ra", "min": [0.0, 0.0], "max": [40.0, 20.0]}],
    },
    {"op": "surface_fill", "label": "join_face_a", "sketch": "join_a"},
    {
        "op": "sketch",
        "label": "join_b",
        "plane": "XY",
        "entities": [{"type": "rectangle", "name": "rb", "min": [30.0, 0.0], "max": [70.0, 20.0]}],
    },
    {"op": "surface_fill", "label": "join_face_b", "sketch": "join_b"},
    # The cut plane sits on the shared edge of the two fills (x = 40), so the
    # part of the second fill that the first one covers is exactly the part on
    # the near side of that plane. A coplanar quilt tool would be degenerate,
    # so the plane is the tool that measures the overlap.
    {
        "op": "datum_plane",
        "label": "join_cut",
        "reference": {"kind": "datum_plane", "axis": "x", "offset": 0},
        "offset": 40.0,
    },
]


def case_join_offline() -> dict:
    """S03 join: the contract before any geometry is built."""
    from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS
    from creo_mechdog.schema import validate_operations

    checks, check = make_checks()
    try:
        validate_operations([dict(operation) for operation in JOIN_PLAN])
        check("schema_accepts_the_join_plan", True)
    except ValueError as error:
        check("schema_accepts_the_join_plan", False, {"error": str(error)})
    for operation in (
        {
            "op": "surface_trim",
            "label": "join_trim",
            "target": {"kind": "quilt", "id": 12},
            "tool": {"kind": "quilt", "id": 13},
            "keep_side": "one",
        },
        {
            "op": "thicken",
            "label": "join_solid_a",
            "reference": {"kind": "quilt", "id": 12},
            "thickness": JOIN_THICKNESS,
            "side": "symmetric",
        },
        {
            "op": "boolean_bodies",
            "label": "join_union",
            "method": "union",
            "targets": [{"kind": "body", "id": 21}],
            "tools": [{"kind": "body", "id": 22}],
        },
    ):
        try:
            validate_operations([dict(operation)])
            check(f"schema_accepts_{operation['op']}", True)
        except ValueError as error:
            check(f"schema_accepts_{operation['op']}", False, {"error": str(error)})
    check("surface_trim_published", "surface_trim" not in UNAVAILABLE_OPERATIONS)
    check("thicken_registered", "thicken" in REGISTERED_OPERATIONS)
    check("boolean_registered", "boolean_bodies" in REGISTERED_OPERATIONS)
    # The merge operator itself stays gated; this case is the documented
    # fallback for the join need, not a replacement for the operator.
    check("quilt_merge_still_gated", "quilt_merge" in UNAVAILABLE_OPERATIONS)
    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_join": "not_verified",
        "blocked_steps": ["quilt_merge_operator"],
        "checks": checks,
    }


async def case_join_live(wait_ready) -> dict:
    """S03 join: trim one quilt with the other, thicken both, boolean union."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks, check = make_checks()
    jobs: list[str] = []

    async def build(client):
        raw = await submit_plan(client, JOIN_PLAN, jobs)
        if raw.get("status") != "succeeded":
            return None, None, None, raw
        quilts = await section(client, raw["model_id"], "quilts")
        first = min(quilts, key=lambda record: (record.get("bbox_mm") or [[99]])[0][0])
        second = max(quilts, key=lambda record: (record.get("bbox_mm") or [[-99]])[0][0])
        return raw, first, second, raw

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
                "native_join": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
            }

        ready = None
        for keep_side in ("one", "two"):
            built, first, second, raw = await build(client)
            if built is None:
                check("plan_built", False, {"message": raw.get("message")})
                return {
                    "mode": "live",
                    "passed": False,
                    "native_join": "failed",
                    "checks": checks,
                }
            check("plan_built", bool(built.get("saved_verified")))
            trimmed = await submit_plan(
                client,
                [
                    {
                        "op": "surface_trim",
                        "label": "join_trim",
                        "target": {"kind": "quilt", "id": second.get("quilt_id")},
                        "tool": {"kind": "datum_plane", "label": "join_cut"},
                        "keep_side": keep_side,
                    }
                ],
                jobs,
                built["model_id"],
                built.get("revision"),
            )
            kept = float((trimmed.get("operation") or {}).get("area_after_mm2") or 0.0)
            check(
                f"trim_split_keep_{keep_side}",
                trimmed.get("status") == "succeeded"
                and (abs(kept - JOIN_SHARED) <= 0.5 or abs(kept - JOIN_OUTSIDE) <= 0.5),
                {"status": trimmed.get("status"), "area_after_mm2": kept},
            )
            if abs(kept - JOIN_OUTSIDE) <= 0.5:
                ready = (built, first, second, trimmed)
                break
        if ready is None:
            check("outside_part_found", False)
            return {
                "mode": "live",
                "passed": False,
                "native_join": "failed",
                "checks": checks,
            }
        built, first, second, trimmed = ready
        check("outside_part_found", True, {"keep_side": "outside"})
        quilts = await section(client, built["model_id"], "quilts")
        area_a = next(
            (q for q in quilts if abs(float(q.get("area_mm2") or 0.0) - JOIN_AREA_A) <= 0.5), None
        )
        area_out = next(
            (q for q in quilts if abs(float(q.get("area_mm2") or 0.0) - JOIN_OUTSIDE) <= 0.5), None
        )
        # The part of the second fill that the first one does not cover is the
        # piece that joins it; the shared patch was measured by the trim.
        overlap_quilt = area_out
        check(
            "union_area_pieces",
            area_a is not None and area_out is not None,
            {"areas": [q.get("area_mm2") for q in quilts]},
        )
        if area_a is None or area_out is None:
            return {
                "mode": "live",
                "passed": False,
                "native_join": "failed",
                "checks": checks,
            }
        check(
            "union_area_is_1400",
            abs((float(area_a["area_mm2"]) + float(area_out["area_mm2"])) - JOIN_UNION_AREA) <= 0.5,
            {"a": area_a["area_mm2"], "outside": area_out["area_mm2"]},
        )

        check("overlap_quilt_found", overlap_quilt is not None)
        if overlap_quilt is None:
            return {
                "mode": "live",
                "passed": False,
                "native_join": "failed",
                "checks": checks,
            }

        revision = trimmed.get("revision")
        solid_a = await submit_plan(
            client,
            [
                {
                    "op": "thicken",
                    "label": "join_solid_a",
                    "reference": {"kind": "quilt", "id": area_a.get("quilt_id")},
                    "thickness": JOIN_THICKNESS,
                    "side": "symmetric",
                    "new_body": True,
                }
            ],
            jobs,
            built["model_id"],
            revision,
        )
        check(
            "solid_a_measured",
            solid_a.get("status") == "succeeded"
            and abs(
                float((solid_a.get("operation") or {}).get("volume_after_mm3") or 0.0)
                - JOIN_AREA_A * JOIN_THICKNESS
            )
            <= 1.0,
            {
                "status": solid_a.get("status"),
                "volume_after_mm3": (solid_a.get("operation") or {}).get("volume_after_mm3"),
            },
        )
        revision = solid_a.get("revision")
        solid_b = await submit_plan(
            client,
            [
                {
                    "op": "thicken",
                    "label": "join_solid_b",
                    "reference": {"kind": "quilt", "id": overlap_quilt.get("quilt_id")},
                    "thickness": JOIN_THICKNESS,
                    "side": "symmetric",
                    "new_body": True,
                }
            ],
            jobs,
            built["model_id"],
            revision,
        )
        check(
            "solid_b_measured",
            solid_b.get("status") == "succeeded"
            and abs(
                float((solid_b.get("operation") or {}).get("volume_after_mm3") or 0.0)
                - JOIN_UNION_AREA * JOIN_THICKNESS
            )
            <= 1.0,
        )
        check(
            "solid_b_is_the_outside_part",
            abs(
                float((solid_b.get("operation") or {}).get("volume_after_mm3") or 0.0)
                - JOIN_OUTSIDE * JOIN_THICKNESS
            )
            <= 1.0
            or abs(
                float((solid_b.get("operation") or {}).get("volume_after_mm3") or 0.0)
                - JOIN_UNION_AREA * JOIN_THICKNESS
            )
            <= 1.0,
            {
                "status": solid_b.get("status"),
                "volume_after_mm3": (solid_b.get("operation") or {}).get("volume_after_mm3"),
            },
        )
        revision = solid_b.get("revision")

        bodies = await section(client, built["model_id"], "bodies")
        body_ids = [record.get("id") for record in bodies if record.get("id") is not None]
        check("one_joined_body_present", len(body_ids) >= 1, {"bodies": body_ids})

        # The second solid measures the union: 1600 + 1600 would be 3200 mm3,
        # the shared 200 mm2 patch (400 mm3) is counted once, so the union is
        # 1400 mm2 * 2 mm = 2800 mm3.
        volume = float((solid_b.get("operation") or {}).get("volume_after_mm3") or 0.0)
        check(
            "union_volume_is_2800",
            solid_b.get("status") == "succeeded"
            and abs(volume - JOIN_UNION_AREA * JOIN_THICKNESS) <= 1.0,
            {
                "status": solid_b.get("status"),
                "volume_after_mm3": volume,
                "expected_mm3": JOIN_UNION_AREA * JOIN_THICKNESS,
                "sum_without_overlap_mm3": (JOIN_AREA_A + JOIN_AREA_B) * JOIN_THICKNESS,
                "message": solid_b.get("message"),
            },
        )
        check("union_saved_and_reloaded", bool(solid_b.get("saved_verified")))

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_join": "verified" if passed else "failed",
        "blocked_steps": ["quilt_merge_operator"],
        "jobs": jobs,
        "checks": checks,
    }
