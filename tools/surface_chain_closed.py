"""S08 closed chain case: closed surface -> solidify -> revise -> rollback.

The merge step of the plan's closed chain is still gated, so the closed surface
comes from a 360 degree revolve instead of a merge. Every expectation is an
analytic oracle derived from the measured bounding box, and every job must
report saved_file_reloaded_and_verified.
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


def case_chain_closed_offline(plan: list[dict[str, Any]]) -> dict:
    """S08 closed chain: the contract before any geometry is built."""
    from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS
    from creo_mechdog.schema import validate_operations

    checks, check = make_checks()
    try:
        validate_operations([dict(operation) for operation in plan])
        check("schema_accepts_the_closed_plan", True)
    except ValueError as error:
        check("schema_accepts_the_closed_plan", False, {"error": str(error)})
    try:
        validate_operations(
            [
                {
                    "op": "update_sketch_geometry",
                    "sketch": "chain_profile",
                    "entities": [
                        {"type": "rectangle", "name": "rp", "min": [0, 0], "max": [5, 30]}
                    ],
                }
            ]
        )
        check("schema_accepts_a_revise", True)
    except ValueError as error:
        check("schema_accepts_a_revise", False, {"error": str(error)})
    check("solidify_published", "solidify" not in UNAVAILABLE_OPERATIONS)
    check("revolve_registered", "revolve" in REGISTERED_OPERATIONS)
    check("quilt_merge_still_gated", "quilt_merge" in UNAVAILABLE_OPERATIONS)
    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_chain_closed": "not_verified",
        "blocked_steps": ["quilt_merge"],
        "checks": checks,
    }


async def case_chain_closed_live(
    wait_ready, plan: list[dict[str, Any]], profile_label: str
) -> dict:
    """S08 closed chain: closed surface -> solidify -> revise -> rollback."""
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
                "native_chain_closed": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
            }

        built = await submit_plan(client, plan, jobs)
        check(
            "closed_surface_built",
            built["status"] == "succeeded" and bool(built.get("saved_verified")),
            {"status": built.get("status"), "message": built.get("message")},
        )
        if built["status"] != "succeeded":
            return {
                "mode": "live",
                "passed": False,
                "native_chain_closed": "failed",
                "checks": checks,
            }
        model_id = built["model_id"]
        revision = built.get("revision")
        quilts = await section(client, model_id, "quilts")
        closed = [record for record in quilts if record.get("closed") is True]
        check("closed_quilt_measured", bool(closed), {"areas": [r.get("area_mm2") for r in quilts]})
        if not closed:
            return {
                "mode": "live",
                "passed": False,
                "native_chain_closed": "failed",
                "checks": checks,
            }
        quilt = closed[0]
        bbox = quilt.get("bbox_mm") or []
        radius = (bbox[1][1] - bbox[0][1]) / 2.0 if len(bbox) == 2 else 0.0
        height = (bbox[1][0] - bbox[0][0]) if len(bbox) == 2 else 0.0
        expected_volume = math.pi * radius * radius * height
        expected_area = 2 * math.pi * radius * height + 2 * math.pi * radius * radius
        check(
            "closed_area_matches_oracle",
            abs(float(quilt.get("area_mm2") or 0.0) - expected_area) <= 0.5,
            {"area_mm2": quilt.get("area_mm2"), "expected_mm2": expected_area},
        )

        solidified = await submit_plan(
            client,
            [
                {
                    "op": "solidify",
                    "label": "chain_solid",
                    "reference": {"kind": "quilt", "id": quilt.get("quilt_id")},
                    "side": "positive",
                }
            ],
            jobs,
            model_id,
            revision,
        )
        solid = solidified.get("operation") or {}
        check(
            "solidify_measured",
            solidified["status"] == "succeeded"
            and abs(float(solid.get("volume_after_mm3") or 0.0) - expected_volume) <= 1.0,
            {
                "status": solidified.get("status"),
                "volume_after_mm3": solid.get("volume_after_mm3"),
                "expected_mm3": expected_volume,
                "message": solidified.get("message"),
            },
        )
        check("solidify_saved_and_reloaded", bool(solidified.get("saved_verified")))
        revision = solidified.get("revision")

        revised = await submit_plan(
            client,
            [
                {
                    "op": "update_sketch_geometry",
                    "sketch": profile_label,
                    "entities": [
                        {"type": "rectangle", "name": "rp", "min": [0.0, 0.0], "max": [5.0, 30.0]}
                    ],
                }
            ],
            jobs,
            model_id,
            revision,
        )
        check(
            "revise_succeeded",
            revised["status"] == "succeeded",
            {"status": revised.get("status"), "message": revised.get("message")},
        )
        after = await section(client, model_id, "quilts")
        changed = [
            record
            for record in after
            if abs(float(record.get("area_mm2") or 0.0) - float(quilt.get("area_mm2") or 0.0)) > 0.5
        ]
        check(
            "revise_changed_the_surface",
            bool(changed),
            {"areas": [record.get("area_mm2") for record in after]},
        )
        check("revise_saved_and_reloaded", bool(revised.get("saved_verified")))
        revision = revised.get("revision")
        rolled = await submit_plan(
            client,
            [
                {"op": "surface_fill", "label": "chain_ok", "sketch": profile_label},
                {
                    "op": "surface_trim",
                    "label": "chain_bad",
                    "target": {"kind": "quilt", "id": 999999},
                    "tool": {"kind": "quilt", "id": 999998},
                    "keep_side": "one",
                },
            ],
            jobs,
            model_id,
            revision,
        )
        check(
            "failing_plan_rolled_back",
            rolled.get("status") == "failed",
            {"status": rolled.get("status"), "message": rolled.get("message")},
        )
        final = await section(client, model_id, "quilts")
        check(
            "rollback_kept_the_geometry",
            bool(changed)
            and abs(
                float(final[0].get("area_mm2") or 0.0) - float(changed[0].get("area_mm2") or 0.0)
            )
            <= 0.5,
            {"areas": [record.get("area_mm2") for record in final]},
        )

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_chain_closed": "verified" if passed else "failed",
        "blocked_steps": ["quilt_merge"],
        "jobs": jobs,
        "checks": checks,
    }
