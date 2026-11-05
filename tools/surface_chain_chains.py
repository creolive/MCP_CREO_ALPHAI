"""S08 chain cases for the surface chain driver.

The open chain runs fill -> project -> curve trim -> query -> symmetric
thicken through the delivered operators; the loft step stays blocked and is
reported as blocked instead of being faked with a body boolean. The closed
chain runs a 360 degree revolve -> solidify -> revise -> rollback; the merge
step stays blocked and the closed surface comes from the revolve instead.

Every expectation is an analytic oracle derived from the measured geometry, and
every job must report saved_file_reloaded_and_verified.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CHAIN_OPEN_PLAN: list[dict[str, Any]] = [
    {
        "op": "sketch",
        "label": "chain_profile",
        "plane": "XY",
        "entities": [{"type": "rectangle", "name": "rect", "min": [0.0, 0.0], "max": [40.0, 20.0]}],
    },
    {"op": "surface_fill", "label": "chain_target", "sketch": "chain_profile"},
    {
        "op": "sketch",
        "label": "chain_source",
        "plane": "XY",
        "offset": 10.0,
        "entities": [{"type": "line", "name": "src", "start": [-5.0, 5.0], "end": [45.0, 5.0]}],
    },
    {
        "op": "sketch",
        "label": "chain_cut",
        "plane": "XY",
        "entities": [{"type": "line", "name": "cut", "start": [-5.0, 5.0], "end": [45.0, 5.0]}],
    },
    {
        "op": "datum_plane",
        "label": "chain_dir",
        "reference": {"kind": "datum_plane", "axis": "z", "offset": 0},
        "offset": 30.0,
    },
]
CHAIN_THICKNESS = 2.0
# The source line is 50 mm long, but the projection is restricted to the
# target face, so the measured curve is the 40 mm inside the 40 mm wide fill.
CHAIN_SOURCE_LENGTH = 40.0
CHAIN_TRIM_AREA = 600.0


async def call_tool(client, tool: str, arguments: dict) -> dict:
    """Call a tool and return its structured payload, tolerating refusals."""
    result = await client.call_tool(tool, arguments)
    if result.structured_content is not None:
        return result.structured_content
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text[:600]}
    return {}


async def submit_plan(client, operations, jobs, model_id=None, revision=None) -> dict:
    """Submit a plan and wait for its terminal state without asserting success."""
    arguments: dict = {"operations": operations}
    if model_id:
        arguments["model_id"] = model_id
        arguments["expected_revision"] = revision
    submitted = await call_tool(client, "creo_execute_plan", arguments)
    job_id = submitted.get("job_id")
    if not job_id:
        return {"status": "refused", "message": str(submitted)[:400]}
    jobs.append(job_id)
    # A queued job waits for the native worker to be rebuilt after an
    # interrupted run, so the deadline is generous: the job does finish.
    deadline = time.monotonic() + 900
    state: dict = {}
    while time.monotonic() < deadline:
        # The compact page keeps the polling cheap; a job whose metadata fills
        # the response budget is refused by the full page ("Query metadata
        # exceeds response budget"), so the compact view is the one to poll.
        state = await call_tool(client, "creo_get_job", {"job_id": job_id, "detail": "compact"})
        if state.get("status") in ("succeeded", "failed", "unknown_outcome"):
            break
        await asyncio.sleep(2)
    else:
        raise TimeoutError("job did not settle; inspect it, never blindly resubmit")
    # The compact page carries the status but drops the measurements, so the
    # full page is asked once for the numbers. A job whose metadata fills the
    # response budget is refused there, and the compact page stays in place.
    full = await call_tool(client, "creo_get_job", {"job_id": job_id, "detail": "full"})
    if full.get("status"):
        state = full
    results = (state.get("result") or {}).get("operations") or []
    state["operation"] = results[-1] if results else None
    state["saved_verified"] = (state.get("result") or {}).get("saved_file_reloaded_and_verified")
    return state


async def section(client, model_id: str, name: str) -> list:
    # The paged sections default to 50 entries; a chain model carries more, so
    # the page is widened instead of reading a truncated list.
    page = await call_tool(
        client,
        "creo_inspect_model",
        {"model_id": model_id, "detail": "full", "section": name, "limit": 200},
    )
    return (page.get("data") or {}).get(name) or []


def curve_id_of(geometry: list, feature: dict) -> int | None:
    for item in geometry:
        if item.get("feature_id") == feature.get("id") and item.get("type") == 62:
            return item["id"]
    return None


def feature_named(features: list, name: str) -> dict:
    return next(
        (feature for feature in features if str(feature.get("name", "")).lower() == name), {}
    )


def make_checks() -> tuple[list, Any]:
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    return checks, check


def case_chain_open_offline() -> dict:
    """S08 open chain: the contract before any geometry is built."""
    from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS
    from creo_mechdog.schema import validate_operations

    checks, check = make_checks()
    for operation in (
        {"op": "surface_fill", "label": "chain_target", "sketch": "chain_profile"},
        {
            "op": "project_curve",
            "label": "chain_proj",
            "target": {"kind": "quilt_feature", "label": "chain_target"},
            "source": {"kind": "curve", "id": 7},
            "direction_ref": {"kind": "datum_feature", "label": "chain_dir"},
            "side": "negative",
        },
        {
            "op": "surface_trim",
            "label": "chain_trim",
            "target": {"kind": "quilt_feature", "label": "chain_target"},
            "tool": {"kind": "curve", "id": 9},
            "keep_side": "one",
        },
        {
            "op": "thicken",
            "label": "chain_solid",
            "reference": {"kind": "quilt", "id": 12},
            "thickness": CHAIN_THICKNESS,
            "side": "symmetric",
        },
    ):
        try:
            validate_operations([dict(operation)])
            check(f"schema_accepts_{operation['op']}", True)
        except ValueError as error:
            check(f"schema_accepts_{operation['op']}", False, {"error": str(error)})

    check("project_curve_published", "project_curve" not in UNAVAILABLE_OPERATIONS)
    check("surface_trim_published", "surface_trim" not in UNAVAILABLE_OPERATIONS)
    check("thicken_registered", "thicken" in REGISTERED_OPERATIONS)
    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_chain_open": "not_verified",
        "blocked_steps": ["surface_loft"],
        "checks": checks,
    }


async def case_chain_open_live(wait_ready) -> dict:
    """S08 open chain: fill -> project -> curve trim -> query -> symmetric thicken."""
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
                "native_chain_open": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
            }

        built = await submit_plan(client, CHAIN_OPEN_PLAN, jobs)
        check(
            "plan_built",
            built["status"] == "succeeded" and bool(built.get("saved_verified")),
            {"status": built.get("status"), "message": built.get("message")},
        )
        if built["status"] != "succeeded":
            return {
                "mode": "live",
                "passed": False,
                "native_chain_open": "failed",
                "checks": checks,
            }
        model_id = built["model_id"]
        revision = built.get("revision")

        features = await section(client, model_id, "features")
        geometry = await section(client, model_id, "feature_geometry")
        source_curve = curve_id_of(geometry, feature_named(features, "chain_source"))
        cut_curve = curve_id_of(geometry, feature_named(features, "chain_cut"))
        check("source_curve_found", source_curve is not None, {"source": source_curve})
        check("cut_curve_found", cut_curve is not None, {"cut": cut_curve})

        projected = await submit_plan(
            client,
            [
                {
                    "op": "project_curve",
                    "label": "chain_proj",
                    "target": {"kind": "quilt_feature", "label": "chain_target"},
                    "source": {"kind": "curve", "id": source_curve},
                    "direction_ref": {"kind": "datum_feature", "label": "chain_dir"},
                    "side": "negative",
                }
            ],
            jobs,
            model_id,
            revision,
        )
        projection = projected.get("operation") or {}
        check(
            "projection_measured",
            projected["status"] == "succeeded"
            and abs(float(projection.get("curve_length_mm") or 0.0) - CHAIN_SOURCE_LENGTH) <= 0.5,
            {
                "status": projected.get("status"),
                "length_mm": projection.get("curve_length_mm"),
                "message": projected.get("message"),
            },
        )
        check("projection_saved_and_reloaded", bool(projected.get("saved_verified")))
        revision = projected.get("revision")

        trimmed = await submit_plan(
            client,
            [
                {
                    "op": "surface_trim",
                    "label": "chain_trim",
                    "target": {"kind": "quilt_feature", "label": "chain_target"},
                    "tool": {"kind": "curve", "id": cut_curve},
                    "keep_side": "one",
                }
            ],
            jobs,
            model_id,
            revision,
        )
        trim = trimmed.get("operation") or {}
        check(
            "trim_measured",
            trimmed["status"] == "succeeded"
            and abs(float(trim.get("area_after_mm2") or 0.0) - CHAIN_TRIM_AREA) <= 0.5,
            {
                "status": trimmed.get("status"),
                "area_after_mm2": trim.get("area_after_mm2"),
                "message": trimmed.get("message"),
            },
        )
        check("trim_saved_and_reloaded", bool(trimmed.get("saved_verified")))
        revision = trimmed.get("revision")

        quilts = await section(client, model_id, "quilts")
        kept = [
            record
            for record in quilts
            if abs(float(record.get("area_mm2") or 0.0) - CHAIN_TRIM_AREA) <= 0.5
        ]
        check(
            "query_finds_the_kept_quilt", bool(kept), {"areas": [r.get("area_mm2") for r in quilts]}
        )
        check(
            "kept_quilt_is_open",
            bool(kept) and kept[0].get("closed") is False,
            {"closed": kept[0].get("closed") if kept else None},
        )
        if not kept:
            return {
                "mode": "live",
                "passed": False,
                "native_chain_open": "failed",
                "checks": checks,
            }

        thickened = await submit_plan(
            client,
            [
                {
                    "op": "thicken",
                    "label": "chain_solid",
                    "reference": {"kind": "quilt", "id": kept[0].get("quilt_id")},
                    "thickness": CHAIN_THICKNESS,
                    "side": "symmetric",
                }
            ],
            jobs,
            model_id,
            revision,
        )
        solid = thickened.get("operation") or {}
        expected_volume = CHAIN_TRIM_AREA * CHAIN_THICKNESS
        check(
            "symmetric_thicken_measured",
            thickened["status"] == "succeeded"
            and abs(float(solid.get("volume_after_mm3") or 0.0) - expected_volume) <= 1.0,
            {
                "status": thickened.get("status"),
                "volume_after_mm3": solid.get("volume_after_mm3"),
                "expected_mm3": expected_volume,
                "message": thickened.get("message"),
            },
        )
        check("thicken_saved_and_reloaded", bool(thickened.get("saved_verified")))

        stale = await submit_plan(
            client,
            [{"op": "surface_fill", "label": "chain_stale", "sketch": "chain_profile"}],
            jobs,
            model_id,
            (revision or 1) - 1,
        )
        check(
            "stale_revision_refused",
            stale.get("status") in ("failed", "refused"),
            {"status": stale.get("status"), "message": stale.get("message")},
        )

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_chain_open": "verified" if passed else "failed",
        "blocked_steps": ["surface_loft"],
        "jobs": jobs,
        "checks": checks,
    }
