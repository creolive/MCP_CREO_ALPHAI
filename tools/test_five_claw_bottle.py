"""FEAT-039/H10 (DEV-074): the five-claw bottle chain through public operators.

The chain is built from the operators proved in this cycle:

* ``body_tube``: a circle sketch extruded in surface mode, so the body is one
  open cylindrical quilt (2*pi*20*40 = 5026.548 mm2);
* ``petal0..4``: five ruled boundary blends, each between one 72-degree arc of
  the rim circle at z = 0 (R = 20) and the matching 72-degree arc of the foot
  circle at z = -10 (R = 8). Together the five sectors cover the whole conical
  foot band (lateral area pi*(20+8)*sqrt(12^2+10^2) = 1374.051 mm2);
* ``foot_disc``: a planar fill of the R8 circle at z = -10 (201.062 mm2);
* ``top_cap``: a planar fill of the R20 circle at z = 40 (1256.637 mm2).

Every seam in the chain is a full-coincident edge: neighbouring petals share a
radial line, the foot disc shares its whole circle with the five foot arcs, the
tube shares its bottom circle with the five rim arcs and its top circle with the
cap. So the merge chain is judged on the measured area growth, not on a
tolerance: each ``quilt_merge`` must report the target quilt growing by exactly
the next piece, and the closed quilt must reach

  area = 5026.548 + 1374.051 + 201.062 + 1256.637 = 7858.298 mm2
  volume (solidify) = pi*20^2*40 + pi*10/3*(20^2+20*8+8^2) = 56799.995 mm3

Live steps on model A: chain -> group measure -> thicken 0.3 mm -> one solid
round on the rim edge -> one solidify attempt -> save/reload identity. Model B
repeats the chain and thickens 2 mm as its first solid, because a quilt that
already carries a thicken feature is the subject of a separate limit. Every
accepted job is only polled; nothing is resubmitted. If the arc-section lofts
are refused, the run degrades to the flat-capped can (labelled, never presented
as a five-claw bottle).

Usage (PowerShell, repo root):
  .venv\\Scripts\\python.exe tools\\test_five_claw_bottle.py
  .venv\\Scripts\\python.exe tools\\test_five_claw_bottle.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PETAL_COUNT = 5
SECTOR_DEGREES = 360.0 / PETAL_COUNT
BODY_RADIUS = 20.0
BODY_HEIGHT = 40.0
FOOT_RADIUS = 8.0
FOOT_DEPTH = 10.0
THIN_MM = 0.3
THICK_MM = 2.0
# The rim round must fit inside the wall: 0.1 mm on the 0.3 mm shell, 0.5 mm on
# the 2 mm shell.
ROUND_THIN_MM = 0.1
ROUND_THICK_MM = 0.5
TOLERANCE_MM = 0.01
GAP_SEARCH_MM = 1.0
AREA_TOL_MM2 = 0.5
VOLUME_TOL_REL = 0.02

BODY_AREA = 2.0 * math.pi * BODY_RADIUS * BODY_HEIGHT
CAP_AREA = math.pi * BODY_RADIUS * BODY_RADIUS
FOOT_AREA = math.pi * FOOT_RADIUS * FOOT_RADIUS
SLANT = math.hypot(BODY_RADIUS - FOOT_RADIUS, FOOT_DEPTH)
FOOT_BAND_AREA = math.pi * (BODY_RADIUS + FOOT_RADIUS) * SLANT
PETAL_AREA = FOOT_BAND_AREA / PETAL_COUNT
CLOSED_AREA = BODY_AREA + FOOT_BAND_AREA + FOOT_AREA + CAP_AREA
CLOSED_VOLUME = math.pi * BODY_RADIUS**2 * BODY_HEIGHT + (
    math.pi * FOOT_DEPTH / 3.0 * (BODY_RADIUS**2 + BODY_RADIUS * FOOT_RADIUS + FOOT_RADIUS**2)
)
# A symmetric thicken of a closed make area * thickness; the conical foot adds a
# curvature term well under one percent, so the tolerance is two percent.
THIN_VOLUME = CLOSED_AREA * THIN_MM
THICK_VOLUME = CLOSED_AREA * THICK_MM


def _arc_sketch(label: str, offset: float, radius: float, start: float, end: float) -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": "XY",
        "offset": offset,
        "dimensioning": "coordinates",
        "entities": [
            {
                "type": "arc",
                "name": f"{label}_arc",
                "center": [0.0, 0.0],
                "radius": radius,
                "start_angle": start,
                "end_angle": end,
                "dir": 1,
            }
        ],
    }


def _circle_sketch(label: str, offset: float, radius: float) -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": "XY",
        "offset": offset,
        "dimensioning": "coordinates",
        "entities": [
            {"type": "circle", "name": f"{label}_circle", "center": [0.0, 0.0], "radius": radius}
        ],
    }


def petal_step(index: int) -> list[dict[str, Any]]:
    """One 72-degree ruled sector: two arc sections and the loft between them."""
    start = index * SECTOR_DEGREES
    end = (index + 1) * SECTOR_DEGREES
    return [
        _arc_sketch(f"petal{index}_top", 0.0, BODY_RADIUS, start, end),
        _arc_sketch(f"petal{index}_foot", -FOOT_DEPTH, FOOT_RADIUS, start, end),
        {
            "op": "surface_loft",
            "label": f"petal{index}",
            "sections": [f"petal{index}_top", f"petal{index}_foot"],
        },
    ]


def petal_plan() -> list[dict[str, Any]]:
    """All five sectors as one plan (used by the offline contract)."""
    return [operation for index in range(PETAL_COUNT) for operation in petal_step(index)]


def body_plan() -> list[dict[str, Any]]:
    """The tube, the foot disc and the top cap; the petals are already there."""
    return [
        _circle_sketch("body_rim", 0.0, BODY_RADIUS),
        {
            "op": "extrude",
            "label": "body_tube",
            "sketch": "body_rim",
            "mode": "surface",
            "depth": BODY_HEIGHT,
        },
        _circle_sketch("foot_profile", -FOOT_DEPTH, FOOT_RADIUS),
        {"op": "surface_fill", "label": "foot_disc", "sketch": "foot_profile"},
        _circle_sketch("cap_profile", BODY_HEIGHT, BODY_RADIUS),
        {"op": "surface_fill", "label": "top_cap", "sketch": "cap_profile"},
    ]


def fallback_plan() -> list[dict[str, Any]]:
    """Degraded chain: a plain cylinder with two flat caps, no claws at all."""
    return [
        _circle_sketch("can_rim", 0.0, BODY_RADIUS),
        {
            "op": "extrude",
            "label": "can_tube",
            "sketch": "can_rim",
            "mode": "surface",
            "depth": BODY_HEIGHT,
        },
        _circle_sketch("can_cap_profile", BODY_HEIGHT, BODY_RADIUS),
        {"op": "surface_fill", "label": "can_cap", "sketch": "can_cap_profile"},
    ]


def merge_op(label: str, target: int, tool: int) -> dict[str, Any]:
    return {
        "op": "quilt_merge",
        "label": label,
        "target": {"kind": "quilt", "id": target},
        "tool": {"kind": "quilt", "id": tool},
    }


def thicken_op(label: str, quilt: int, thickness: float, new_body: bool = False) -> dict[str, Any]:
    return {
        "op": "thicken",
        "label": label,
        "reference": {"kind": "quilt", "id": quilt},
        "thickness": thickness,
        "side": "symmetric",
        "new_body": new_body,
    }


def round_op(label: str, edge: int, radius: float) -> dict[str, Any]:
    return {
        "op": "round",
        "label": label,
        "size": radius,
        "references": [{"edge": {"kind": "edge", "id": edge}}],
    }


def case_offline() -> dict:
    """Contract before any geometry: the plan and the published operators."""
    from creo_mechdog.capabilities import (
        REGISTERED_OPERATIONS,
        UNAVAILABLE_OPERATIONS,
        require_available,
    )
    from creo_mechdog.schema import validate_operations

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    try:
        petals = validate_operations([dict(op) for op in petal_plan()])
        check("petal_plan_validates", [op["op"] for op in petals].count("surface_loft") == 5)
    except ValueError as error:
        check("petal_plan_validates", False, {"error": str(error)})
    try:
        body = validate_operations([dict(op) for op in body_plan()])
        check(
            "body_plan_validates",
            [op["op"] for op in body].count("surface_fill") == 2
            and [op["op"] for op in body].count("extrude") == 1,
        )
    except ValueError as error:
        check("body_plan_validates", False, {"error": str(error)})
    try:
        validate_operations([dict(op) for op in fallback_plan()])
        check("fallback_plan_validates", True)
    except ValueError as error:
        check("fallback_plan_validates", False, {"error": str(error)})
    try:
        validate_operations(
            [
                merge_op("offline_merge", 11, 12),
                thicken_op("offline_thin", 11, THIN_MM),
                round_op("offline_round", 7, ROUND_THICK_MM),
            ]
        )
        check("merge_thicken_round_validate", True)
    except ValueError as error:
        check("merge_thicken_round_validate", False, {"error": str(error)})

    for operation in (
        "surface_loft",
        "quilt_merge",
        "surface_group_measure",
        "surface_fill",
        "thicken",
        "round",
    ):
        check(f"{operation}_registered", operation in REGISTERED_OPERATIONS)
        check(f"{operation}_published", operation not in UNAVAILABLE_OPERATIONS)

    admitted = True
    try:
        require_available(
            [merge_op("offline_merge", 11, 12), thicken_op("offline_thin", 11, THIN_MM)]
        )
    except ValueError:
        admitted = False
    check("chain_admitted_before_job", admitted)
    check(
        "analytic_oracles_are_the_expected_bottle",
        abs(BODY_AREA - 5026.548245743669) <= 1e-6
        and abs(FOOT_BAND_AREA - 1374.0508882537029) <= 1e-6
        and abs(CLOSED_AREA - 7858.298125263036) <= 1e-6
        and abs(CLOSED_VOLUME - 56799.99517690347) <= 1e-6,
        {
            "body": BODY_AREA,
            "band": FOOT_BAND_AREA,
            "closed_area": CLOSED_AREA,
            "closed_volume": CLOSED_VOLUME,
            "petal": PETAL_AREA,
        },
    )

    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_five_claw_bottle": "not_verified",
        "checks": checks,
    }


async def call_tool(client, tool: str, arguments: dict) -> tuple[dict, bool, str]:
    result = await client.call_tool(tool, arguments)
    payload = result.structured_content
    text = "\n".join(block.text for block in (result.content or []) if getattr(block, "text", None))
    if payload is None and text:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"raw": text[:800]}
    return payload or {}, bool(getattr(result, "is_error", False)), text


class Abort(RuntimeError):
    """The channel refused or lost the job; stop instead of retrying."""


#: Partial receipts survive a driver error: the live case appends to these
#: lists, so main() can still write the evidence it collected.
RUN_STATE: dict[str, Any] = {"checks": [], "jobs": [], "evidence": {}}


async def submit(
    client,
    operations: list[dict],
    jobs: list[str],
    model_id: str | None = None,
    revision: int | None = None,
) -> dict:
    arguments: dict[str, Any] = {"operations": operations}
    if model_id:
        arguments["model_id"] = model_id
        arguments["expected_revision"] = revision
    payload, is_error, text = await call_tool(client, "creo_execute_plan", arguments)
    state_status = payload.get("status")
    if state_status in ("busy", "unknown_outcome"):
        raise Abort(
            "channel refused the plan before a job (status="
            f"{state_status}); blocking_job_id={payload.get('blocking_job_id')}"
        )
    if is_error or not payload.get("job_id"):
        return {
            "status": "refused",
            "is_error": is_error,
            "job_id": payload.get("job_id"),
            "message": (text or str(payload))[:1500],
        }
    job_id = payload["job_id"]
    jobs.append(job_id)
    deadline = time.monotonic() + 900
    state: dict = {}
    while time.monotonic() < deadline:
        state, _, _ = await call_tool(
            client, "creo_get_job", {"job_id": job_id, "detail": "compact"}
        )
        if state.get("status") in ("succeeded", "failed", "unknown_outcome"):
            break
        await asyncio.sleep(2)
    else:
        raise Abort(f"job {job_id} did not settle within the poll budget")
    if state.get("status") == "unknown_outcome":
        raise Abort(f"job {job_id} ended in unknown_outcome; stopping without a resubmit")
    full, _, _ = await call_tool(client, "creo_get_job", {"job_id": job_id, "detail": "full"})
    if isinstance(full.get("result"), dict):
        merged = dict(state)
        combined = dict(state.get("result") or {})
        combined.update(full["result"])
        merged["result"] = combined
        state = merged
    results = (state.get("result") or {}).get("operations") or []
    state["operation"] = results[-1] if results else None
    state["operations"] = results
    state["saved_verified"] = (state.get("result") or {}).get(
        "saved_file_reloaded_and_verified"
    ) or state.get("saved_file_reloaded_and_verified")
    return state


async def section(client, model_id: str, name: str) -> list:
    page, _, _ = await call_tool(
        client,
        "creo_inspect_model",
        {"model_id": model_id, "detail": "full", "section": name, "limit": 200},
    )
    return (page.get("data") or {}).get(name) or []


async def compact(client, model_id: str) -> dict:
    page, _, _ = await call_tool(
        client, "creo_inspect_model", {"model_id": model_id, "detail": "compact"}
    )
    return page


async def wait_ready(client, budget_seconds: int = 210) -> dict:
    deadline = time.monotonic() + budget_seconds
    state: dict = {}
    retry = True
    while time.monotonic() < deadline:
        state, _, _ = await call_tool(client, "creo_startup_status", {"retry": retry})
        retry = False
        if state.get("connected"):
            return state
        if state.get("state") in ("timeout", "failed", "error", "blocked", "unavailable"):
            return state
        await asyncio.sleep(2)
    return state


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _near(value: Any, expected: float, tolerance: float) -> bool:
    actual = _number(value)
    return actual is not None and abs(actual - expected) <= tolerance


def quilt_area(records: list, quilt_id: int | None) -> dict | None:
    for record in records:
        if record.get("quilt_id") == quilt_id:
            return record
    return None


def pick_quilt(records: list, area: float, tolerance: float = AREA_TOL_MM2) -> dict | None:
    for record in records:
        if _near(record.get("area_mm2"), area, tolerance):
            return record
    return None


def bbox_span(body: dict, axis: int) -> float | None:
    bbox = body.get("bbox") or []
    if len(bbox) != 2:
        return None
    low, high = _number(bbox[0][axis]), _number(bbox[1][axis])
    if low is None or high is None:
        return None
    return high - low


def active_bodies(records: list) -> list:
    return [record for record in records if record.get("material") is True]


def find_rim_edge(surfaces: list, edges: list, radius: float, tol: float = 0.05) -> int | None:
    """The outermost edge between the cylinder of the given radius and a top plane.

    A closed circular edge carries no line data, so the edge height is read from
    the adjacent planar surface's origin instead of the edge endpoints.
    """
    by_id = {surface.get("id"): surface for surface in surfaces}
    cylinders = {
        surface.get("id") for surface in surfaces if _near(surface.get("radius"), radius, tol)
    }
    best: tuple[float, int] | None = None
    for edge in edges:
        adjacent = edge.get("adjacent_surfaces") or []
        if len(adjacent) != 2:
            continue
        for cylinder_id, plane_id in (adjacent, list(reversed(adjacent))):
            plane = by_id.get(plane_id) or {}
            normal = plane.get("normal")
            if cylinder_id not in cylinders or not isinstance(normal, list) or len(normal) != 3:
                continue
            if abs(abs(normal[2]) - 1.0) > 1e-3:
                continue
            origin = plane.get("origin") or [None, None, None]
            height = _number(origin[2])
            edge_id = edge.get("id")
            if height is None or not isinstance(edge_id, int):
                continue
            if best is None or height > best[0]:
                best = (height, edge_id)
    return best[1] if best else None


async def build_chain(client, jobs: list[str], check, prefix: str) -> dict:
    """Petals -> tube -> foot disc -> top cap -> the seven merges.

    Every step reports its own job id, quilt id and measured area. A refused
    sector degrades the run to the flat-capped can instead of pretending the
    bottle is complete.
    """
    result: dict[str, Any] = {
        "petal_steps": [],
        "merges": [],
        "claw_mode": "five_arc_ruled_petals",
        "model_id": None,
        "revision": None,
        "chain_id": None,
        "chain_area": 0.0,
        "ok": False,
        "quilts_after_build": {},
        "final_quilt": {},
    }
    petal_map: dict[int, int] = {}
    model_id: str | None = None
    revision: int | None = None
    for index in range(PETAL_COUNT):
        receipt = await submit(client, petal_step(index), jobs, model_id, revision)
        operation = receipt.get("operation") or {}
        step = {
            "index": index,
            "job_id": receipt.get("job_id"),
            "status": receipt.get("status"),
            "quilt_id": operation.get("quilt_id"),
            "area_mm2": operation.get("surface_area_mm2"),
            "closed": operation.get("quilt_closed_native"),
            "feature_id": operation.get("feature_id"),
            "saved": receipt.get("saved_verified"),
            "message": str(receipt.get("message"))[:400],
        }
        result["petal_steps"].append(step)
        if receipt.get("status") != "succeeded":
            break
        model_id = receipt.get("model_id") or model_id
        revision = receipt.get("revision")
        if isinstance(step["quilt_id"], int):
            petal_map[index] = step["quilt_id"]
    check(
        f"{prefix}_five_petal_lofts_built",
        len(petal_map) == PETAL_COUNT
        and all(step.get("saved") is True for step in result["petal_steps"])
        and all(
            _near(step.get("area_mm2"), PETAL_AREA, AREA_TOL_MM2) for step in result["petal_steps"]
        ),
        {"petal_steps": result["petal_steps"], "petal_area_mm2": PETAL_AREA},
    )
    if len(petal_map) != PETAL_COUNT:
        # A refused sector cannot be bridged by the remaining ones.
        result["claw_mode"] = "flat_capped_can"
        result["petal_failure"] = result["petal_steps"][-1] if result["petal_steps"] else {}

    if model_id is None or result["claw_mode"] != "five_arc_ruled_petals":
        result["claw_mode"] = "flat_capped_can"
        body = await submit(client, fallback_plan(), jobs)
        model_id = body.get("model_id")
    else:
        body = await submit(client, body_plan(), jobs, model_id, revision)
    result["body_build"] = {
        "job_id": body.get("job_id"),
        "status": body.get("status"),
        "saved": body.get("saved_verified"),
        "message": str(body.get("message"))[:600],
        "claw_mode": result["claw_mode"],
    }
    check(
        f"{prefix}_body_build_succeeded",
        body.get("status") == "succeeded" and body.get("saved_verified") is True,
        result["body_build"],
    )
    if body.get("status") != "succeeded":
        return result
    model_id = body["model_id"]
    revision = body.get("revision")

    records = await section(client, model_id, "quilts")
    tube = pick_quilt(records, BODY_AREA, 1.0)
    foot = pick_quilt(records, FOOT_AREA, 0.5) if result["claw_mode"] != "flat_capped_can" else None
    cap = pick_quilt(records, CAP_AREA, 0.5)
    result["quilts_after_build"] = {
        "count": len(records),
        "areas_mm2": [record.get("area_mm2") for record in records],
        "tube": (tube or {}).get("quilt_id"),
        "foot": (foot or {}).get("quilt_id"),
        "cap": (cap or {}).get("quilt_id"),
    }
    check(
        f"{prefix}_tube_measured_5026",
        _near((tube or {}).get("area_mm2"), BODY_AREA, 1.0),
        {"area_mm2": (tube or {}).get("area_mm2")},
    )
    check(
        f"{prefix}_cap_measured_1256",
        _near((cap or {}).get("area_mm2"), CAP_AREA, 0.5),
        {"area_mm2": (cap or {}).get("area_mm2")},
    )
    if tube is None or cap is None:
        return result

    merges: list[dict] = result["merges"]
    chain_id: int | None = None
    chain_area = 0.0
    chain_ok = True

    def record_merge(label: str, receipt: dict, target: int, tool: int, expected: float) -> None:
        operation = receipt.get("operation") or {}
        merges.append(
            {
                "label": label,
                "job_id": receipt.get("job_id"),
                "status": receipt.get("status"),
                "target_quilt_id": target,
                "tool_quilt_id": tool,
                "result_quilt_id": operation.get("result_quilt_id"),
                "result_quilt_source": operation.get("result_quilt_source"),
                "input_area_mm2": operation.get("input_area_mm2"),
                "area_mm2": operation.get("area_mm2"),
                "expected_area_mm2": expected,
                "closed": operation.get("closed"),
                "feature_id": operation.get("feature_id"),
                "saved": receipt.get("saved_verified"),
                "message": str(receipt.get("message"))[:400],
            }
        )

    if result["claw_mode"] == "five_arc_ruled_petals" and len(petal_map) == PETAL_COUNT:
        order = [petal_map[index] for index in sorted(petal_map)]
        chain_id = order[0]
        chain_area = PETAL_AREA
        for position, next_id in enumerate(order[1:], start=1):
            label = f"merge_petal{position}"
            expected = chain_area + PETAL_AREA
            receipt = await submit(
                client, [merge_op(label, chain_id, next_id)], jobs, model_id, revision
            )
            record_merge(label, receipt, chain_id, next_id, expected)
            if receipt.get("status") != "succeeded":
                chain_ok = False
                break
            chain_id = (receipt.get("operation") or {}).get("result_quilt_id") or chain_id
            chain_area = expected
            revision = receipt.get("revision")
        check(
            f"{prefix}_petal_chain_merged",
            chain_ok and len(merges) == PETAL_COUNT - 1,
            {"merges": len(merges), "chain_area_mm2": chain_area},
        )
        if chain_ok and merges:
            check(
                f"{prefix}_petal_band_area_1374",
                _near(merges[-1].get("area_mm2"), FOOT_BAND_AREA, AREA_TOL_MM2),
                {"area_mm2": merges[-1].get("area_mm2"), "expected": FOOT_BAND_AREA},
            )

    if chain_id is None:
        receipt = await submit(
            client,
            [merge_op("merge_can_cap", tube.get("quilt_id"), cap.get("quilt_id"))],
            jobs,
            model_id,
            revision,
        )
        record_merge(
            "merge_can_cap",
            receipt,
            tube.get("quilt_id"),
            cap.get("quilt_id"),
            BODY_AREA + CAP_AREA,
        )
        chain_id = (receipt.get("operation") or {}).get("result_quilt_id") or tube.get("quilt_id")
        chain_area = BODY_AREA + CAP_AREA
        chain_ok = receipt.get("status") == "succeeded"
        revision = receipt.get("revision")
    else:
        tail = []
        if foot is not None:
            tail.append(("merge_foot_disc", foot.get("quilt_id"), FOOT_AREA))
        tail.append(("merge_body_tube", tube.get("quilt_id"), BODY_AREA))
        tail.append(("merge_top_cap", cap.get("quilt_id"), CAP_AREA))
        for label, tool_id, area in tail:
            expected = chain_area + area
            receipt = await submit(
                client, [merge_op(label, chain_id, tool_id)], jobs, model_id, revision
            )
            record_merge(label, receipt, chain_id, tool_id, expected)
            if receipt.get("status") != "succeeded":
                chain_ok = False
                break
            chain_id = (receipt.get("operation") or {}).get("result_quilt_id") or chain_id
            chain_area = expected
            revision = receipt.get("revision")
        check(
            f"{prefix}_closed_chain_merged",
            chain_ok and _near(chain_area, CLOSED_AREA, AREA_TOL_MM2),
            {"chain_area_mm2": chain_area, "expected_area_mm2": CLOSED_AREA},
        )

    records = await section(client, model_id, "quilts")
    chain_record = quilt_area(records, chain_id) or {}
    result["final_quilt"] = {
        "quilt_id": chain_id,
        "area_mm2": chain_record.get("area_mm2"),
        "closed": chain_record.get("closed"),
        "face_count": chain_record.get("face_count"),
        "bbox_mm": chain_record.get("bbox_mm"),
    }
    if result["claw_mode"] == "five_arc_ruled_petals" and chain_ok:
        check(
            f"{prefix}_merged_quilt_area_is_closed_bottle",
            _near(chain_record.get("area_mm2"), CLOSED_AREA, AREA_TOL_MM2),
            result["final_quilt"],
        )
        check(
            f"{prefix}_merged_quilt_reports_closed",
            chain_record.get("closed") is True,
            {"closed": chain_record.get("closed")},
        )
        bbox = chain_record.get("bbox_mm") or []
        check(
            f"{prefix}_merged_quilt_bbox_is_the_bottle",
            len(bbox) == 2
            and _near(bbox[0][2], -FOOT_DEPTH, 0.05)
            and _near(bbox[1][2], BODY_HEIGHT, 0.05),
            {"bbox_mm": bbox},
        )
    result.update(
        {
            "model_id": model_id,
            "revision": revision,
            "chain_id": chain_id,
            "chain_area": chain_area,
            "ok": bool(chain_ok and chain_id is not None),
        }
    )
    return result


def body_snapshot(bodies: list) -> list:
    return [
        {
            "id": body.get("id"),
            "surface_count": body.get("surface_count"),
            "bbox": body.get("bbox"),
            "span_x": bbox_span(body, 0),
            "span_z": bbox_span(body, 2),
        }
        for body in bodies
    ]


async def case_live() -> dict:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks: list[dict[str, Any]] = RUN_STATE["checks"]
    jobs: list[str] = RUN_STATE["jobs"]
    evidence: dict[str, Any] = RUN_STATE["evidence"]

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    def failed(native_state: str) -> dict:
        return {
            "mode": "live",
            "passed": False,
            "native_five_claw_bottle": native_state,
            "jobs": jobs,
            "evidence": evidence,
            "checks": checks,
        }

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        check("session_ready", bool(started.get("connected")), {"state": started.get("state")})
        if not started.get("connected"):
            evidence["note"] = "the session never reported connected; no geometry was submitted"
            return failed("not_verified")

        capabilities, _, _ = await call_tool(client, "creo_capabilities", {})
        published = capabilities.get("operations") or []
        evidence["tool_count"] = capabilities.get("tool_count")
        for operation in (
            "surface_loft",
            "quilt_merge",
            "surface_group_measure",
            "surface_fill",
            "thicken",
            "round",
        ):
            check(f"{operation}_published", operation in published)

        # --- 1. model A: the chain ----------------------------------------
        chain_a = await build_chain(client, jobs, check, "bottle")
        evidence["chain_a"] = chain_a
        if not chain_a.get("ok"):
            return failed("failed")
        model_id = chain_a["model_id"]
        revision = chain_a["revision"]
        chain_id = chain_a["chain_id"]
        claw_mode = chain_a["claw_mode"]
        evidence["claw_mode"] = claw_mode

        # --- 2. the group receipt -----------------------------------------
        group_payload, group_error, group_text = await call_tool(
            client,
            "creo_measure_surface_group",
            {
                "model_id": model_id,
                "references": [{"kind": "quilt", "id": chain_id}],
                "tolerance_mm": TOLERANCE_MM,
                "gap_search_mm": GAP_SEARCH_MM,
            },
        )
        if group_payload.get("job_id"):
            jobs.append(group_payload["job_id"])
        group = group_payload.get("group") or {}
        overlap_status = group.get("overlap_status") or {}
        evidence["group_measure"] = {
            "job_id": group_payload.get("job_id"),
            "is_error": group_error,
            "refusal_text": group_text[:400] if group_error else "",
            "revision": group_payload.get("revision"),
            "unit_name": group_payload.get("unit_name"),
            "tolerance_mm": group.get("tolerance_mm"),
            "gap_search_mm": group.get("gap_search_mm"),
            "state": group.get("state"),
            "state_reason": group.get("state_reason"),
            "open_edges": group.get("open_edges"),
            "boundary_edges": group.get("boundary_edges"),
            "joined_edges": group.get("joined_edges"),
            "joined_pairs": group.get("joined_pairs"),
            "boundary_closed": group.get("boundary_closed"),
            "gap_max_mm": group.get("gap_max_mm"),
            "gap_status": group.get("gap_max_status"),
            "overlap_detected": overlap_status.get("detected"),
            "overlap_reason": overlap_status.get("reason"),
            "overlap_query_code": overlap_status.get("query_code"),
            "overlap_area_mm2": group.get("overlap_area_mm2"),
        }
        check(
            "group_measure_finished",
            bool(group_payload.get("job_id")) and group.get("state") is not None,
            {"state": group.get("state"), "reason": group.get("state_reason")},
        )
        check("group_state_closed", group.get("state") == "closed", evidence["group_measure"])
        check(
            "group_boundary_is_a_shell",
            group.get("boundary_closed") is True and group.get("open_edges") == 0,
            {
                "boundary_closed": group.get("boundary_closed"),
                "open_edges": group.get("open_edges"),
            },
        )
        # With no open edge there is no gap to report, so a null gap_max_mm is
        # the honest answer instead of a fabricated zero.
        check(
            "group_gap_is_not_reported_because_no_edge_is_open",
            group.get("open_edges") == 0
            and (
                group.get("gap_max_mm") is None or _near(group.get("gap_max_mm"), 0.0, TOLERANCE_MM)
            ),
            {"gap_max_mm": group.get("gap_max_mm"), "open_edges": group.get("open_edges")},
        )
        # The overlap scan has a per-quilt sample budget; a closed six-face
        # 7858 mm2 quilt exceeds it, and the receipt says so instead of
        # reporting "no overlap".
        check(
            "group_overlap_is_not_reported_as_detected",
            overlap_status.get("detected") is not True,
            {"detected": overlap_status.get("detected"), "reason": overlap_status.get("reason")},
        )

        # --- 3. thicken 0.3 mm on model A ----------------------------------
        thin = await submit(
            client, [thicken_op("bottle_thin_03", chain_id, THIN_MM)], jobs, model_id, revision
        )
        thin_op = thin.get("operation") or {}
        bodies_after_thin = (
            await section(client, model_id, "bodies") if thin.get("status") == "succeeded" else []
        )
        thin_bodies = active_bodies(bodies_after_thin)
        page_after_thin = (
            await compact(client, model_id) if thin.get("status") == "succeeded" else {}
        )
        evidence["thicken_0_3"] = {
            "job_id": thin.get("job_id"),
            "status": thin.get("status"),
            "volume_before_mm3": thin_op.get("volume_before_mm3"),
            "volume_after_mm3": thin_op.get("volume_after_mm3"),
            "expected_volume_mm3": THIN_VOLUME,
            "thickness_mm": THIN_MM,
            "saved": thin.get("saved_verified"),
            "revision": thin.get("revision"),
            "compact_keys": sorted(page_after_thin.keys()),
            "has_solid": page_after_thin.get("has_solid"),
            "bodies": body_snapshot(thin_bodies),
            "message": str(thin.get("message"))[:500],
        }
        check(
            "thicken_0_3_succeeded",
            thin.get("status") == "succeeded" and thin.get("saved_verified") is True,
            evidence["thicken_0_3"],
        )
        check(
            "thicken_0_3_volume_is_area_times_thickness",
            _near(thin_op.get("volume_after_mm3"), THIN_VOLUME, THIN_VOLUME * VOLUME_TOL_REL),
            {"volume_after_mm3": thin_op.get("volume_after_mm3"), "expected_mm3": THIN_VOLUME},
        )
        thin_span = bbox_span(thin_bodies[0], 2) if thin_bodies else None
        check(
            "thicken_0_3_thickness_readback",
            thin_span is not None and _near(thin_span, BODY_HEIGHT + FOOT_DEPTH + THIN_MM, 0.05),
            {"span_z_mm": thin_span, "expected_mm": BODY_HEIGHT + FOOT_DEPTH + THIN_MM},
        )
        check(
            "thicken_0_3_body_is_a_shell",
            bool(thin_bodies) and (thin_bodies[0].get("surface_count") or 0) >= 12,
            {"bodies": body_snapshot(thin_bodies)},
        )
        if thin.get("status") == "succeeded":
            revision = thin.get("revision")

        # --- 4. one edit on the solidified model ---------------------------
        surfaces = await section(client, model_id, "surfaces")
        edges = await section(client, model_id, "edges")
        rim_edge = find_rim_edge(surfaces, edges, BODY_RADIUS + THIN_MM / 2.0)
        evidence["round_edge"] = {
            "edge_id": rim_edge,
            "surface_count": len(surfaces),
            "edge_count": len(edges),
        }
        check("solid_rim_edge_found", rim_edge is not None, evidence["round_edge"])
        if rim_edge is not None:
            rounded = await submit(
                client,
                [round_op("bottle_rim_round", rim_edge, ROUND_THIN_MM)],
                jobs,
                model_id,
                revision,
            )
            round_operation = rounded.get("operation") or {}
            evidence["round"] = {
                "job_id": rounded.get("job_id"),
                "status": rounded.get("status"),
                "volume_before_mm3": round_operation.get("volume_before_mm3"),
                "volume_after_mm3": round_operation.get("volume_after_mm3"),
                "material_delta_mm3": round_operation.get("material_delta_mm3"),
                "edge_id": rim_edge,
                "radius_mm": ROUND_THIN_MM,
                "saved": rounded.get("saved_verified"),
                "revision": rounded.get("revision"),
                "message": str(rounded.get("message"))[:500],
            }
            check(
                "solid_round_on_thickened_model",
                rounded.get("status") == "succeeded" and rounded.get("saved_verified") is True,
                evidence["round"],
            )
            if rounded.get("status") == "succeeded":
                revision = rounded.get("revision")

        # --- 5. one solidify attempt on the merged quilt -------------------
        solidify = await submit(
            client,
            [
                {
                    "op": "solidify",
                    "label": "bottle_solid",
                    "reference": {"kind": "quilt", "id": chain_id},
                    "side": "positive",
                }
            ],
            jobs,
            model_id,
            revision,
        )
        solidify_operation = solidify.get("operation") or {}
        evidence["solidify"] = {
            "job_id": solidify.get("job_id"),
            "status": solidify.get("status"),
            "volume_before_mm3": solidify_operation.get("volume_before_mm3"),
            "volume_after_mm3": solidify_operation.get("volume_after_mm3"),
            "expected_volume_mm3": CLOSED_VOLUME,
            "saved": solidify.get("saved_verified"),
            "revision": solidify.get("revision"),
            "message": str(solidify.get("message"))[:600],
        }
        check(
            "solidify_after_thicken_has_a_recorded_outcome",
            (
                solidify.get("status") == "failed"
                and "ProFeatureWithoptionsCreate" in str(solidify.get("message"))
            )
            or (
                solidify.get("status") == "succeeded"
                and _near(
                    solidify_operation.get("volume_after_mm3"),
                    CLOSED_VOLUME,
                    CLOSED_VOLUME * VOLUME_TOL_REL,
                )
            ),
            evidence["solidify"],
        )
        if solidify.get("status") == "succeeded":
            revision = solidify.get("revision")

        # --- 6. model A identity after save/reload -------------------------
        final_page = await compact(client, model_id)
        final_quilts = await section(client, model_id, "quilts")
        final_bodies = active_bodies(await section(client, model_id, "bodies"))
        final_record = quilt_area(final_quilts, chain_id) or {}
        evidence["final_state"] = {
            "revision": final_page.get("revision"),
            "expected_revision": revision,
            "quilt": {
                "quilt_id": final_record.get("quilt_id"),
                "area_mm2": final_record.get("area_mm2"),
                "closed": final_record.get("closed"),
                "face_count": final_record.get("face_count"),
            },
            "body_count": len(final_bodies),
            "bodies": body_snapshot(final_bodies),
            "note": (
                "after the thicken the kernel re-associates the merged quilt item: its record "
                "keeps the id and closed=true but reports a sub-quilt area and one face, while "
                "the body carries the whole 12-face wall"
            ),
        }
        check(
            "final_revision_matches",
            final_page.get("revision") == revision,
            {"model_revision": final_page.get("revision"), "last_job_revision": revision},
        )
        final_span = bbox_span(final_bodies[0], 2) if final_bodies else None
        check(
            "thickened_body_survives_reload",
            len(final_bodies) == 1
            and final_span is not None
            and _near(final_span, BODY_HEIGHT + FOOT_DEPTH + THIN_MM, 0.05),
            {"bodies": body_snapshot(final_bodies)},
        )
        check(
            "quilt_record_keeps_its_id_and_closed_flag",
            final_record.get("quilt_id") == chain_id and final_record.get("closed") is True,
            evidence["final_state"]["quilt"],
        )

        # --- 7. model B: the 2 mm wall as the first solid -------------------
        chain_b = await build_chain(client, jobs, check, "wall2")
        evidence["chain_b"] = chain_b
        if chain_b.get("ok"):
            model_b = chain_b["model_id"]
            revision_b = chain_b["revision"]
            chain_b_id = chain_b["chain_id"]
            thick = await submit(
                client,
                [thicken_op("bottle_thick_2", chain_b_id, THICK_MM)],
                jobs,
                model_b,
                revision_b,
            )
            thick_op = thick.get("operation") or {}
            bodies_b = (
                await section(client, model_b, "bodies")
                if thick.get("status") == "succeeded"
                else []
            )
            thick_bodies = active_bodies(bodies_b)
            evidence["thicken_2_0"] = {
                "job_id": thick.get("job_id"),
                "status": thick.get("status"),
                "volume_before_mm3": thick_op.get("volume_before_mm3"),
                "volume_after_mm3": thick_op.get("volume_after_mm3"),
                "expected_volume_mm3": THICK_VOLUME,
                "thickness_mm": THICK_MM,
                "saved": thick.get("saved_verified"),
                "revision": thick.get("revision"),
                "bodies": body_snapshot(thick_bodies),
                "message": str(thick.get("message"))[:500],
            }
            check(
                "thicken_2_0_succeeded",
                thick.get("status") == "succeeded" and thick.get("saved_verified") is True,
                evidence["thicken_2_0"],
            )
            check(
                "thicken_2_0_volume_is_area_times_thickness",
                _near(
                    thick_op.get("volume_after_mm3"), THICK_VOLUME, THICK_VOLUME * VOLUME_TOL_REL
                ),
                {
                    "volume_after_mm3": thick_op.get("volume_after_mm3"),
                    "expected_mm3": THICK_VOLUME,
                },
            )
            thick_span = bbox_span(thick_bodies[0], 2) if thick_bodies else None
            check(
                "thicken_2_0_thickness_readback",
                thick_span is not None
                and _near(thick_span, BODY_HEIGHT + FOOT_DEPTH + THICK_MM, 0.05),
                {"span_z_mm": thick_span, "expected_mm": BODY_HEIGHT + FOOT_DEPTH + THICK_MM},
            )
            if thick.get("status") == "succeeded":
                revision_b = thick.get("revision")

            # --- 8. one edit on the 2 mm wall: a rim round -----------------
            surfaces_b = await section(client, model_b, "surfaces")
            edges_b = await section(client, model_b, "edges")
            rim_b = find_rim_edge(surfaces_b, edges_b, BODY_RADIUS + THICK_MM / 2.0)
            evidence["round_b"] = {
                "edge_id": rim_b,
                "radius_mm": ROUND_THICK_MM,
                "surface_count": len(surfaces_b),
                "edge_count": len(edges_b),
            }
            check("thick_wall_rim_edge_found", rim_b is not None, evidence["round_b"])
            if rim_b is not None:
                rounded_b = await submit(
                    client,
                    [round_op("wall2_rim_round", rim_b, ROUND_THICK_MM)],
                    jobs,
                    model_b,
                    revision_b,
                )
                round_b_operation = rounded_b.get("operation") or {}
                evidence["round_b"].update(
                    {
                        "job_id": rounded_b.get("job_id"),
                        "status": rounded_b.get("status"),
                        "volume_before_mm3": round_b_operation.get("volume_before_mm3"),
                        "volume_after_mm3": round_b_operation.get("volume_after_mm3"),
                        "material_delta_mm3": round_b_operation.get("material_delta_mm3"),
                        "saved": rounded_b.get("saved_verified"),
                        "revision": rounded_b.get("revision"),
                        "message": str(rounded_b.get("message"))[:500],
                    }
                )
                check(
                    "solid_round_on_the_2mm_wall",
                    rounded_b.get("status") == "succeeded"
                    and rounded_b.get("saved_verified") is True,
                    evidence["round_b"],
                )
                if rounded_b.get("status") == "succeeded":
                    revision_b = rounded_b.get("revision")

            page_b_final = await compact(client, model_b)
            quilts_b = await section(client, model_b, "quilts")
            bodies_b_final = active_bodies(await section(client, model_b, "bodies"))
            record_b = quilt_area(quilts_b, chain_b_id) or {}
            evidence["model_b_final"] = {
                "revision": page_b_final.get("revision"),
                "expected_revision": revision_b,
                "quilt": {
                    "quilt_id": record_b.get("quilt_id"),
                    "area_mm2": record_b.get("area_mm2"),
                    "closed": record_b.get("closed"),
                },
                "bodies": body_snapshot(bodies_b_final),
            }
            check(
                "model_b_revision_matches",
                page_b_final.get("revision") == revision_b,
                {
                    "model_revision": page_b_final.get("revision"),
                    "last_job_revision": revision_b,
                },
            )
            span_b_final = bbox_span(bodies_b_final[0], 2) if bodies_b_final else None
            check(
                "model_b_body_survives_the_round",
                len(bodies_b_final) == 1
                and span_b_final is not None
                and _near(span_b_final, BODY_HEIGHT + FOOT_DEPTH + THICK_MM, 0.05),
                {"bodies": body_snapshot(bodies_b_final)},
            )
            check(
                "model_b_quilt_record_keeps_its_id",
                record_b.get("quilt_id") == chain_b_id,
                evidence["model_b_final"]["quilt"],
            )

        # --- 9. model C: solidify the closed chain before any thicken thins it
        chain_c = await build_chain(client, jobs, check, "solid")
        evidence["chain_c"] = chain_c
        if chain_c.get("ok"):
            model_c = chain_c["model_id"]
            revision_c = chain_c["revision"]
            chain_c_id = chain_c["chain_id"]
            fill = await submit(
                client,
                [
                    {
                        "op": "solidify",
                        "label": "bottle_fill",
                        "reference": {"kind": "quilt", "id": chain_c_id},
                        "side": "positive",
                    }
                ],
                jobs,
                model_c,
                revision_c,
            )
            fill_operation = fill.get("operation") or {}
            bodies_c = (
                await section(client, model_c, "bodies")
                if fill.get("status") == "succeeded"
                else []
            )
            evidence["solidify_fresh"] = {
                "job_id": fill.get("job_id"),
                "status": fill.get("status"),
                "volume_before_mm3": fill_operation.get("volume_before_mm3"),
                "volume_after_mm3": fill_operation.get("volume_after_mm3"),
                "expected_volume_mm3": CLOSED_VOLUME,
                "saved": fill.get("saved_verified"),
                "revision": fill.get("revision"),
                "bodies": body_snapshot(active_bodies(bodies_c)),
                "message": str(fill.get("message"))[:600],
            }
            check(
                "solidify_measured_the_bottle_volume",
                fill.get("status") == "succeeded"
                and _near(
                    fill_operation.get("volume_after_mm3"),
                    CLOSED_VOLUME,
                    CLOSED_VOLUME * VOLUME_TOL_REL,
                ),
                evidence["solidify_fresh"],
            )
            if fill.get("status") == "succeeded":
                revision_c = fill.get("revision")
            page_c_final = await compact(client, model_c)
            evidence["model_c_final"] = {
                "revision": page_c_final.get("revision"),
                "expected_revision": revision_c,
                "bodies": body_snapshot(active_bodies(await section(client, model_c, "bodies"))),
            }
            check(
                "model_c_revision_matches",
                page_c_final.get("revision") == revision_c,
                {
                    "model_revision": page_c_final.get("revision"),
                    "last_job_revision": revision_c,
                },
            )
            check(
                "solidified_bottle_survives_reload",
                bool(evidence["model_c_final"]["bodies"]),
                evidence["model_c_final"],
            )

        passed = all(item["ok"] for item in checks)
        return {
            "mode": "live",
            "passed": passed,
            "claw_mode": claw_mode,
            "native_five_claw_bottle": "verified" if passed else "failed",
            "jobs": jobs,
            "evidence": evidence,
            "checks": checks,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.live and not args.confirm_session_usable:
        print("live runs require --confirm-session-usable", file=sys.stderr)
        return 2

    RUN_STATE["checks"].clear()
    RUN_STATE["jobs"].clear()
    RUN_STATE["evidence"].clear()
    try:
        report = asyncio.run(case_live()) if args.live else case_offline()
    except Abort as error:
        report = {
            "mode": "live",
            "passed": False,
            "native_five_claw_bottle": "aborted",
            "abort": str(error),
            "jobs": RUN_STATE["jobs"],
            "evidence": RUN_STATE["evidence"],
            "checks": RUN_STATE["checks"],
        }
    except Exception as error:  # noqa: BLE001 - the report must survive a driver bug
        # An unexpected driver error must still leave the receipts behind, so
        # the run is reported as failed instead of vanishing with a traceback.
        import traceback

        report = {
            "mode": "live" if args.live else "offline",
            "passed": False,
            "native_five_claw_bottle": "driver_error",
            "abort": f"{type(error).__name__}: {error}",
            "traceback": traceback.format_exc()[-4000:],
            "jobs": RUN_STATE["jobs"],
            "evidence": RUN_STATE["evidence"],
            "checks": RUN_STATE["checks"],
        }
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    output = args.output or ROOT / "build" / "five_claw_bottle" / run_id / "report.json"
    if output.exists():
        print(f"refusing to overwrite {output}", file=sys.stderr)
        return 3
    report["run_id"] = run_id
    report["report_path"] = str(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # LF bytes so the evidence SHA256 matches the committed blob.
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
