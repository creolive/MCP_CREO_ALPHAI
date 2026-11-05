"""S05 surface case: the documented surface sweep, judged by analytic oracles.

The local SDK documents the surface sweep (ProSweep.h line 162: the feature type
is PRO_SWEEP_FEAT_TYPE_SURFACE, and PRO_E_END_SRF_ATTR decides whether the ends
stay open or get capped). A 40x20 rectangle swept along a 20 mm line is a
rectangular tube, so every expectation is a closed form:

* open tube: the four lateral faces, 2 * (40 + 20) * 20 = 2400 mm2;
* capped tube: the same walls plus two 40x20 end caps = 4000 mm2, and a closed
  quilt, which solidifies into a 40 x 20 x 20 box of 16000 mm3.

The multi-section loft (boundary blend) stays unavailable: ProSweep.h documents a
constant section only and this machine ships no ProBlend.h.
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

WIDTH = 40.0
HEIGHT = 20.0
LENGTH = 20.0
PERIMETER = 2.0 * (WIDTH + HEIGHT)
OPEN_AREA = PERIMETER * LENGTH
CAP_AREA = 2.0 * WIDTH * HEIGHT
CAPPED_AREA = OPEN_AREA + CAP_AREA
BOX_VOLUME = WIDTH * HEIGHT * LENGTH

PROFILE = [{"type": "rectangle", "name": "rect", "min": [0.0, 0.0], "max": [WIDTH, HEIGHT]}]
PATH_LINE = [{"type": "line", "name": "path", "start": [0.0, 0.0], "end": [LENGTH, 0.0]}]


def sweep_plan(capped: bool) -> list[dict[str, Any]]:
    """A 40x20 profile swept 20 mm along a straight path."""
    return [
        {"op": "sketch", "label": "sweep_path", "plane": "XZ", "entities": PATH_LINE},
        {
            "op": "sweep",
            "label": "sweep_surface",
            "trajectory": "sweep_path",
            "profile": PROFILE,
            "mode": "surface",
            "capped": capped,
        },
    ]


def case_sweep_offline() -> dict:
    """S05 surface sweep: the contract before any geometry is built."""
    from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS
    from creo_mechdog.schema import validate_operations

    checks, check = make_checks()
    for capped in (False, True):
        try:
            validate_operations([dict(operation) for operation in sweep_plan(capped)])
            check(f"schema_accepts_surface_sweep_capped_{capped}", True)
        except ValueError as error:
            check(f"schema_accepts_surface_sweep_capped_{capped}", False, {"error": str(error)})
    try:
        rejected = False
        validate_operations(
            [
                {
                    "op": "sweep",
                    "label": "bad",
                    "trajectory": "sweep_path",
                    "profile": PROFILE,
                    "mode": "not-a-mode",
                }
            ]
        )
    except ValueError:
        rejected = True
    check("unknown_mode_is_refused", rejected)
    check("sweep_published", "sweep" not in UNAVAILABLE_OPERATIONS)
    check("solidify_published", "solidify" not in UNAVAILABLE_OPERATIONS)
    check("revolve_registered", "revolve" in REGISTERED_OPERATIONS)
    # The multi-section loft stays refused: the loft operator is published, but
    # its surface mode is rejected before a job exists (no documented tree, and
    # the delivered blend is dashboard driven with solid output only).
    from creo_mechdog.capabilities import require_available

    refused = False
    try:
        require_available(
            [
                {
                    "op": "loft",
                    "label": "loft_surface",
                    "sections": ["sweep_path"],
                    "mode": "surface",
                }
            ]
        )
    except ValueError as error:
        refused = "surface" in str(error)
    check("loft_surface_still_refused", refused)
    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_sweep_surface": "not_verified",
        "blocked_steps": ["loft_surface"],
        "expected": {
            "open_area_mm2": OPEN_AREA,
            "capped_area_mm2": CAPPED_AREA,
            "box_volume_mm3": BOX_VOLUME,
        },
        "checks": checks,
    }


async def case_sweep_live(wait_ready) -> dict:
    """S05 surface sweep: open 2400 mm2, capped 4000 mm2, box 16000 mm3."""
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
                "native_sweep_surface": "not_verified",
                "blocked_steps": ["loft_surface"],
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
            }

        # 1) the open surface: four lateral faces, no end caps.
        open_built = await submit_plan(client, sweep_plan(False), jobs)
        check(
            "open_sweep_built",
            open_built.get("status") == "succeeded",
            {"status": open_built.get("status"), "message": open_built.get("message")},
        )
        check("open_sweep_saved_and_reloaded", bool(open_built.get("saved_verified")))
        open_quilts = await section(client, open_built["model_id"], "quilts")
        check(
            "open_sweep_area_is_2400",
            len(open_quilts) == 1
            and abs(float(open_quilts[0].get("area_mm2") or 0.0) - OPEN_AREA) <= 0.5,
            {
                "areas": [quilt.get("area_mm2") for quilt in open_quilts],
                "expected_mm2": OPEN_AREA,
            },
        )
        check(
            "open_sweep_is_open",
            bool(open_quilts) and open_quilts[0].get("closed") is False,
            {"closed": [quilt.get("closed") for quilt in open_quilts]},
        )

        # 2) the capped surface: walls plus two 40x20 caps, and it is closed.
        capped_built = await submit_plan(client, sweep_plan(True), jobs)
        check(
            "capped_sweep_built",
            capped_built.get("status") == "succeeded",
            {"status": capped_built.get("status"), "message": capped_built.get("message")},
        )
        check("capped_sweep_saved_and_reloaded", bool(capped_built.get("saved_verified")))
        capped_quilts = await section(client, capped_built["model_id"], "quilts")
        check(
            "capped_sweep_area_is_4000",
            len(capped_quilts) == 1
            and abs(float(capped_quilts[0].get("area_mm2") or 0.0) - CAPPED_AREA) <= 0.5,
            {
                "areas": [quilt.get("area_mm2") for quilt in capped_quilts],
                "expected_mm2": CAPPED_AREA,
            },
        )
        check(
            "capped_sweep_is_closed",
            bool(capped_quilts) and capped_quilts[0].get("closed") is True,
            {"closed": [quilt.get("closed") for quilt in capped_quilts]},
        )
        if not capped_quilts:
            return {
                "mode": "live",
                "passed": False,
                "native_sweep_surface": "failed",
                "blocked_steps": ["loft_surface"],
                "checks": checks,
            }

        # 3) the closed surface is a real solid: 40 x 20 x 20 = 16000 mm3.
        solidified = await submit_plan(
            client,
            [
                {
                    "op": "solidify",
                    "label": "sweep_solid",
                    "reference": {"kind": "quilt", "id": capped_quilts[0].get("quilt_id")},
                    "side": "positive",
                }
            ],
            jobs,
            capped_built["model_id"],
            capped_built.get("revision"),
        )
        operation = solidified.get("operation") or {}
        volume = float(operation.get("volume_after_mm3") or 0.0)
        check(
            "solidify_volume_is_16000",
            solidified.get("status") == "succeeded" and abs(volume - BOX_VOLUME) <= 1.0,
            {
                "status": solidified.get("status"),
                "volume_after_mm3": volume,
                "expected_mm3": BOX_VOLUME,
                "message": solidified.get("message"),
            },
        )
        check("solidify_saved_and_reloaded", bool(solidified.get("saved_verified")))

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_sweep_surface": "verified" if passed else "failed",
        "blocked_steps": ["loft_surface"],
        "expected": {
            "open_area_mm2": OPEN_AREA,
            "capped_area_mm2": CAPPED_AREA,
            "box_volume_mm3": BOX_VOLUME,
        },
        "jobs": jobs,
        "checks": checks,
    }
