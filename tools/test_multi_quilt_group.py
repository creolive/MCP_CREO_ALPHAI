"""FEAT-039/H10: a multi-quilt group through measure, thicken, reload and edit.

The group is built from public operators only:

* ``loft_a``: a 40 x 20 ruled surface on the plane y = 0 (z from 0 to 20);
* ``loft_b``: the perpendicular 40 x 20 ruled surface on x = 40, so the two
  lofts share the vertical edge (40, 0, z);
* ``floor``: a 40 x 40 planar fill at z = 0 whose two edges coincide with the
  bottom edges of both lofts.

So the group has three seam pairs (12 boundary edges, 6 left open) and its
member seams are closed while the outer boundary is still an open sheet.

What the live case measures:

1. per-quilt readings (id, area, ``closed``, bbox) and the group-level
   ``creo_measure_surface_group`` four-state receipt;
2. ``thicken`` of one quilt at 0.3 mm and, on a second model, at 2 mm, with the
   volume taken from the receipt and the wall thickness read back from the
   active body's bounding box;
3. the multi-quilt solidify/thicken entries: schema-level refusal of a
   reference list, the ``quilt_merge`` gate, and the native refusal of an open
   single quilt;
4. save/reload identity plus one further ``thicken`` on the same model.

The merge operator stays gated: this driver never claims a single closed quilt
or a watertight bottle bottom.

Usage (PowerShell, repo root):
  .venv\\Scripts\\python.exe tools\\test_multi_quilt_group.py
  .venv\\Scripts\\python.exe tools\\test_multi_quilt_group.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOFT_WIDTH = 40.0
LOFT_HEIGHT = 20.0
FLOOR_SIZE = 40.0
LOFT_AREA = LOFT_WIDTH * LOFT_HEIGHT
FLOOR_AREA = FLOOR_SIZE * FLOOR_SIZE
GROUP_AREA = 2 * LOFT_AREA + FLOOR_AREA
THIN_MM = 0.3
THICK_MM = 2.0
TOLERANCE_MM = 0.01
GAP_SEARCH_MM = 1.0
AREA_TOLERANCE_MM2 = 0.5
VOLUME_TOLERANCE_MM3 = 0.5
# The two thickened lofts meet in a 1 x 0.15 x 20 mm corner when both are
# symmetric. If the kernel unions them into one body, the second feature adds
# 1600 mm3 minus that 3 mm3 overlap.
SECOND_OVERLAP_MM3 = 1.0 * (THIN_MM / 2.0) * LOFT_HEIGHT


def _line_sketch(label: str, offset: float, start: list[float], end: list[float]) -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": "XY",
        "offset": offset,
        "entities": [{"type": "line", "name": f"{label}_line", "start": start, "end": end}],
    }


def group_plan() -> list[dict[str, Any]]:
    """Two perpendicular lofts plus a planar floor, all independent quilts."""
    return [
        _line_sketch("loft_a_low", 0.0, [0.0, 0.0], [LOFT_WIDTH, 0.0]),
        _line_sketch("loft_a_high", LOFT_HEIGHT, [0.0, 0.0], [LOFT_WIDTH, 0.0]),
        {
            "op": "surface_loft",
            "label": "loft_a",
            "sections": ["loft_a_low", "loft_a_high"],
        },
        _line_sketch("loft_b_low", 0.0, [LOFT_WIDTH, 0.0], [LOFT_WIDTH, FLOOR_SIZE]),
        _line_sketch("loft_b_high", LOFT_HEIGHT, [LOFT_WIDTH, 0.0], [LOFT_WIDTH, FLOOR_SIZE]),
        {
            "op": "surface_loft",
            "label": "loft_b",
            "sections": ["loft_b_low", "loft_b_high"],
        },
        {
            "op": "sketch",
            "label": "floor_profile",
            "plane": "XY",
            "dimensioning": "coordinates",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "floor_rect",
                    "min": [0.0, 0.0],
                    "max": [FLOOR_SIZE, FLOOR_SIZE],
                }
            ],
        },
        {"op": "surface_fill", "label": "floor", "sketch": "floor_profile"},
    ]


def case_offline() -> dict:
    """Contract before any geometry exists: plans, gates and refusal shapes."""
    from creo_mechdog.capabilities import (
        REGISTERED_OPERATIONS,
        UNAVAILABLE_OPERATIONS,
        require_available,
    )
    from creo_mechdog.schema import validate_operations

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    plan = group_plan()
    try:
        validated = validate_operations(plan)
        check("group_plan_validates", [op["op"] for op in validated].count("surface_loft") == 2)
        check(
            "group_plan_has_one_fill",
            sum(op["op"] == "surface_fill" for op in validated) == 1,
        )
    except ValueError as error:
        check("group_plan_validates", False, {"error": str(error)})

    references = [{"kind": "quilt", "id": 21}, {"kind": "quilt", "id": 22}]
    for name, operation in {
        "solidify": {"op": "solidify", "label": "g_solid", "reference": references},
        "thicken": {
            "op": "thicken",
            "label": "g_thick",
            "reference": references,
            "thickness": THIN_MM,
        },
    }.items():
        try:
            validate_operations([operation])
            check(f"{name}_refuses_a_reference_list", False, {"reason": "accepted"})
        except ValueError:
            check(f"{name}_refuses_a_reference_list", True)

    try:
        validate_operations([{"op": "solidify", "label": "one", "reference": references[0]}])
        check("solidify_accepts_one_quilt", True)
    except ValueError as error:
        check("solidify_accepts_one_quilt", False, {"error": str(error)})

    for name, refs in {
        "three": references + [{"kind": "quilt", "id": 23}],
        "duplicate": [references[0], references[0]],
    }.items():
        try:
            validate_operations(
                [
                    {
                        "op": "surface_group_measure",
                        "references": refs,
                        "tolerance_mm": TOLERANCE_MM,
                        "gap_search_mm": GAP_SEARCH_MM,
                    }
                ]
            )
            check(f"group_measure_refuses_{name}", name != "duplicate")
        except ValueError:
            check(f"group_measure_refuses_{name}", name == "duplicate")

    check("group_measure_registered", "surface_group_measure" in REGISTERED_OPERATIONS)
    check("quilt_merge_gated", "quilt_merge" in UNAVAILABLE_OPERATIONS)
    refused = False
    try:
        require_available(
            [
                {
                    "op": "quilt_merge",
                    "label": "g_merge",
                    "target": references[0],
                    "tool": references[1],
                }
            ]
        )
    except ValueError as error:
        refused = "no native job was queued" in str(error)
    check("merge_gate_refuses_before_job", refused)
    check("surface_loft_published", "surface_loft" not in UNAVAILABLE_OPERATIONS)
    check("thicken_registered", "thicken" in REGISTERED_OPERATIONS)

    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_multi_quilt_group": "not_verified",
        "checks": checks,
    }


async def call_tool(client, tool: str, arguments: dict) -> tuple[dict, bool, str]:
    """Call a tool and keep the refusal text as well as the payload."""
    result = await client.call_tool(tool, arguments)
    payload = result.structured_content
    text = "\n".join(block.text for block in (result.content or []) if getattr(block, "text", None))
    if payload is None and text:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"raw": text[:800]}
    return payload or {}, bool(getattr(result, "is_error", False)), text


async def submit(
    client,
    operations: list[dict],
    jobs: list[str],
    model_id: str | None = None,
    revision: int | None = None,
) -> dict:
    """Submit a plan, poll the accepted job and return its full receipt."""
    arguments: dict[str, Any] = {"operations": operations}
    if model_id:
        arguments["model_id"] = model_id
        arguments["expected_revision"] = revision
    payload, is_error, text = await call_tool(client, "creo_execute_plan", arguments)
    if is_error or not payload.get("job_id"):
        return {
            "status": "refused",
            "is_error": is_error,
            "job_id": payload.get("job_id"),
            "message": (text or str(payload))[:1200],
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
        return {"status": "unsettled", "job_id": job_id, "message": "job did not settle"}
    # A large plan receipt is paged on the full view (no ``result`` block), so
    # the compact view stays authoritative unless the full view actually carries
    # one. Replacing a compact result with a page fragment loses the save/reload
    # evidence and the operation criteria.
    full, _, _ = await call_tool(client, "creo_get_job", {"job_id": job_id, "detail": "full"})
    if isinstance(full.get("result"), dict):
        merged = dict(state)
        combined = dict(state.get("result") or {})
        combined.update(full["result"])
        merged["result"] = combined
        state = merged
    results = (state.get("result") or {}).get("operations") or []
    state["operation"] = results[-1] if results else None
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


async def measure_group(client, model_id: str, references: list[dict], jobs: list[str]) -> dict:
    payload, is_error, text = await call_tool(
        client,
        "creo_measure_surface_group",
        {
            "model_id": model_id,
            "references": references,
            "tolerance_mm": TOLERANCE_MM,
            "gap_search_mm": GAP_SEARCH_MM,
        },
    )
    if payload.get("job_id"):
        jobs.append(payload["job_id"])
    payload["is_error"] = is_error
    payload["refusal_text"] = text[:600] if is_error else ""
    return payload


def _area(record: dict) -> float:
    value = record.get("area_mm2")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else -1.0


def classify_quilts(records: list) -> dict[str, dict]:
    """Name the three fixture quilts by area and bounding box, not by id."""
    lofts = [record for record in records if abs(_area(record) - LOFT_AREA) <= AREA_TOLERANCE_MM2]
    floor = [record for record in records if abs(_area(record) - FLOOR_AREA) <= AREA_TOLERANCE_MM2]
    named: dict[str, dict] = {"floor": floor[0] if floor else {}}
    for record in lofts:
        bbox = record.get("bbox_mm") or []
        if len(bbox) != 2:
            continue
        if abs(bbox[0][1]) <= 0.5 and abs(bbox[1][1]) <= 0.5:
            named["loft_a"] = record
        elif abs(bbox[0][0] - LOFT_WIDTH) <= 0.5 and abs(bbox[1][0] - LOFT_WIDTH) <= 0.5:
            named["loft_b"] = record
    return named


def quilt_record(record: dict) -> dict:
    bbox = record.get("bbox_mm") or []
    return {
        "quilt_id": record.get("quilt_id"),
        "area_mm2": record.get("area_mm2"),
        "closed": record.get("closed"),
        "face_count": record.get("face_count"),
        "bbox_mm": bbox,
    }


def group_record(payload: dict) -> dict:
    group = payload.get("group") or {}
    return {
        "job_id": payload.get("job_id"),
        "revision": payload.get("revision"),
        "unit_name": payload.get("unit_name"),
        "tolerance_mm": group.get("tolerance_mm", TOLERANCE_MM),
        "gap_search_mm": group.get("gap_search_mm", GAP_SEARCH_MM),
        "state": group.get("state"),
        "state_reason": group.get("state_reason"),
        "open_edges": group.get("open_edges"),
        "boundary_edges": group.get("boundary_edges"),
        "joined_edges": group.get("joined_edges"),
        "joined_pairs": group.get("joined_pairs"),
        "boundary_closed": group.get("boundary_closed"),
        "gap_max_mm": group.get("gap_max_mm"),
        "overlap_detected": (group.get("overlap_status") or {}).get("detected"),
        "overlap_area_mm2": group.get("overlap_area_mm2"),
    }


def active_body(records: list) -> dict:
    for record in records:
        if record.get("material") is True:
            return record
    return {}


def bbox_span(body: dict, axis: int) -> float | None:
    bbox = body.get("bbox") or []
    if len(bbox) != 2:
        return None
    return float(bbox[1][axis]) - float(bbox[0][axis])


def _near(value: Any, expected: float, tolerance: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and abs(float(value) - expected) <= tolerance
    )


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


async def case_live() -> dict:
    """Build the group, measure it, thicken members, attempt the group route."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks: list[dict[str, Any]] = []
    jobs: list[str] = []
    evidence: dict[str, Any] = {}

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        check("session_ready", bool(started.get("connected")), {"state": started.get("state")})
        if not started.get("connected"):
            return {
                "mode": "live",
                "passed": False,
                "native_multi_quilt_group": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
            }

        capabilities, _, _ = await call_tool(client, "creo_capabilities", {})
        published = capabilities.get("operations") or []
        for operation in ("surface_loft", "surface_trim", "thicken", "solidify"):
            check(f"{operation}_published", operation in published)
        check("surface_group_measure_published", "surface_group_measure" in published)
        check("quilt_merge_gated", "quilt_merge" not in published)

        # --- Model A: build the three-quilt group -------------------------
        build = await submit(client, group_plan(), jobs)
        check(
            "group_built",
            build.get("status") == "succeeded" and build.get("saved_verified") is True,
            {"job_id": build.get("job_id"), "message": str(build.get("message"))[:300]},
        )
        if build.get("status") != "succeeded":
            return {
                "mode": "live",
                "passed": False,
                "native_multi_quilt_group": "failed",
                "jobs": jobs,
                "checks": checks,
                "build": build,
            }
        model_a = build["model_id"]
        revision = build.get("revision")
        records = await section(client, model_a, "quilts")
        named = classify_quilts(records)
        evidence["per_quilt"] = {name: quilt_record(record) for name, record in named.items()}
        check(
            "three_quilts_present",
            all(name in named for name in ("loft_a", "loft_b", "floor")),
            {"areas_mm2": [record.get("area_mm2") for record in records]},
        )
        check(
            "areas_800_800_1600",
            _near(_area(named.get("loft_a") or {}), LOFT_AREA, AREA_TOLERANCE_MM2)
            and _near(_area(named.get("loft_b") or {}), LOFT_AREA, AREA_TOLERANCE_MM2)
            and _near(_area(named.get("floor") or {}), FLOOR_AREA, AREA_TOLERANCE_MM2),
            evidence["per_quilt"],
        )
        check(
            "every_member_quilt_is_open",
            all(
                (named.get(name) or {}).get("closed") is False
                for name in ("loft_a", "loft_b", "floor")
            ),
            {name: (named.get(name) or {}).get("closed") for name in ("loft_a", "loft_b")},
        )
        check("sum_area_is_3200", _near(sum(_area(r) for r in records), GROUP_AREA, 1.0))

        references = [
            {"kind": "quilt", "id": named[name].get("quilt_id")}
            for name in ("loft_a", "loft_b", "floor")
            if name in named
        ]
        if len(references) != 3:
            return {
                "mode": "live",
                "passed": False,
                "native_multi_quilt_group": "failed",
                "jobs": jobs,
                "checks": checks,
                "evidence": evidence,
            }
        group = group_record(await measure_group(client, model_a, references, jobs))
        evidence["group_measure"] = group
        check(
            "group_measure_finished",
            bool(group["job_id"]) and group["state"] is not None,
            {"state": group["state"], "reason": group["state_reason"]},
        )
        check("group_state_is_closed", group["state"] == "closed", group)
        check("group_open_edges_6", group["open_edges"] == 6, {"open_edges": group["open_edges"]})
        check(
            "group_gap_within_tolerance",
            _near(group["gap_max_mm"], 0.0, TOLERANCE_MM),
            {"gap_max_mm": group["gap_max_mm"]},
        )
        check("group_has_no_overlap", group["overlap_detected"] is False, group)
        check("group_boundary_is_open_sheet", group["boundary_closed"] is False)
        check("group_measure_is_mm", group["unit_name"] == "mm")
        check("group_measure_kept_revision", group["revision"] == revision)

        # --- The whole-group routes are refused before a job --------------
        attempts: dict[str, Any] = {}
        for name, operation in {
            "solidify_reference_list": {
                "op": "solidify",
                "label": "group_solid",
                "reference": references,
                "side": "positive",
            },
            "thicken_reference_list": {
                "op": "thicken",
                "label": "group_thicken",
                "reference": references,
                "thickness": THIN_MM,
                "side": "symmetric",
            },
            "quilt_merge": {
                "op": "quilt_merge",
                "label": "group_merge",
                "target": references[0],
                "tool": references[1],
            },
        }.items():
            payload, is_error, text = await call_tool(
                client,
                "creo_execute_plan",
                {"operations": [operation], "model_id": model_a, "expected_revision": revision},
            )
            attempts[name] = {
                "is_error": is_error,
                "job_id": payload.get("job_id"),
                "message": (text or str(payload))[:800],
            }
            check(
                f"{name}_refused_before_job",
                is_error and not payload.get("job_id"),
                attempts[name],
            )
        evidence["group_routes"] = attempts
        page, _, _ = await call_tool(
            client, "creo_inspect_model", {"model_id": model_a, "detail": "compact"}
        )
        check(
            "refusals_kept_revision",
            page.get("revision") == revision,
            {"before": revision, "after": page.get("revision")},
        )

        # --- 0.3 mm thicken of the loft --------------------------------
        thin = await submit(
            client,
            [
                {
                    "op": "thicken",
                    "label": "thicken_loft_a_03",
                    "reference": references[0],
                    "thickness": THIN_MM,
                    "side": "symmetric",
                }
            ],
            jobs,
            model_a,
            revision,
        )
        thin_op = thin.get("operation") or {}
        evidence["thicken_0_3"] = {
            "job_id": thin.get("job_id"),
            "status": thin.get("status"),
            "volume_before_mm3": thin_op.get("volume_before_mm3"),
            "volume_after_mm3": thin_op.get("volume_after_mm3"),
            "saved": thin.get("saved_verified"),
            "message": str(thin.get("message"))[:300],
        }
        check(
            "thicken_0_3_succeeded",
            thin.get("status") == "succeeded" and thin.get("saved_verified") is True,
            evidence["thicken_0_3"],
        )
        check(
            "thicken_0_3_volume_240",
            _near(thin_op.get("volume_after_mm3"), LOFT_AREA * THIN_MM, VOLUME_TOLERANCE_MM3),
            {"volume_after_mm3": thin_op.get("volume_after_mm3"), "expected": LOFT_AREA * THIN_MM},
        )
        revision = thin.get("revision")
        bodies = await section(client, model_a, "bodies")
        body = active_body(bodies)
        thin_span = bbox_span(body, 1)
        evidence["thicken_0_3"]["body"] = {
            "bbox": body.get("bbox"),
            "surface_count": body.get("surface_count"),
            "thickness_span_y_mm": thin_span,
        }
        check("thicken_0_3_one_body", bool(body), {"bodies": bodies})
        check(
            "thicken_0_3_thickness_readback",
            thin_span is not None and abs(thin_span - THIN_MM) <= 0.02,
            {"thickness_span_y_mm": thin_span, "bbox": body.get("bbox")},
        )
        check(
            "thicken_0_3_is_a_closed_slab",
            body.get("surface_count") == 6,
            {"surface_count": body.get("surface_count")},
        )

        after_first = classify_quilts(await section(client, model_a, "quilts"))
        evidence["after_first_thicken"] = {
            name: quilt_record(record) for name, record in after_first.items()
        }
        # Live 2026-11-08: the thicken does not consume the quilt; all three
        # ids and areas survive, while the thickened member starts reporting
        # closed=true (its quilt volume is now measurable).
        check(
            "thicken_keeps_every_quilt_id_and_area",
            all(name in after_first for name in ("loft_a", "loft_b", "floor"))
            and all(
                after_first[name].get("quilt_id") == named[name].get("quilt_id")
                for name in ("loft_a", "loft_b", "floor")
            )
            and _near(_area(after_first.get("loft_a") or {}), LOFT_AREA, AREA_TOLERANCE_MM2)
            and _near(_area(after_first.get("floor") or {}), FLOOR_AREA, AREA_TOLERANCE_MM2),
            {"remaining": list(after_first)},
        )
        check(
            "thickened_member_reports_closed",
            (after_first.get("loft_a") or {}).get("closed") is True
            and (after_first.get("loft_b") or {}).get("closed") is False,
            {
                "loft_a_closed": (after_first.get("loft_a") or {}).get("closed"),
                "loft_b_closed": (after_first.get("loft_b") or {}).get("closed"),
            },
        )
        # A group that still names the thickened member cannot be measured: the
        # quilt now belongs to a solid, so the boundary visit is refused. The
        # receipt is kept as evidence instead of silently dropping the member.
        combined = await measure_group(client, model_a, references, jobs)
        evidence["group_with_thickened_member"] = {
            "is_error": combined.get("is_error"),
            "job_id": combined.get("job_id"),
            "message": str(combined.get("refusal_text") or "")[:600],
        }
        check(
            "group_with_thickened_member_is_refused",
            combined.get("is_error") is True and not combined.get("job_id"),
            evidence["group_with_thickened_member"],
        )

        remaining_refs = [
            {"kind": "quilt", "id": after_first[name].get("quilt_id")}
            for name in ("loft_b", "floor")
            if name in after_first
        ]
        reloaded_group = group_record(await measure_group(client, model_a, remaining_refs, jobs))
        evidence["group_after_first_thicken"] = reloaded_group
        check(
            "reloaded_open_members_keep_their_seams",
            reloaded_group["state"] == "closed"
            and reloaded_group["open_edges"] == 6
            and reloaded_group["boundary_edges"] == 8
            and reloaded_group["joined_edges"] == 2
            and _near(reloaded_group["gap_max_mm"], 0.0, TOLERANCE_MM)
            and reloaded_group["revision"] == revision,
            reloaded_group,
        )

        # --- An open member cannot solidify on its own -----------------
        open_solid = await submit(
            client,
            [
                {
                    "op": "solidify",
                    "label": "solidify_open_loft_b",
                    "reference": {"kind": "quilt", "id": after_first["loft_b"].get("quilt_id")},
                    "side": "positive",
                }
            ],
            jobs,
            model_a,
            revision,
        )
        open_result = open_solid.get("result") or {}
        evidence["single_open_solidify"] = {
            "job_id": open_solid.get("job_id"),
            "status": open_solid.get("status"),
            "rollback_succeeded": open_result.get("rollback_succeeded"),
            "message": str(open_solid.get("message"))[:600],
        }
        check(
            "open_member_solidify_refused_by_native",
            open_solid.get("status") == "failed"
            and "closed quilt" in str(open_solid.get("message")),
            evidence["single_open_solidify"],
        )
        check(
            "open_member_solidify_rolled_back",
            open_result.get("rollback_succeeded") is True,
            {"rollback_succeeded": open_result.get("rollback_succeeded")},
        )
        page, _, _ = await call_tool(
            client, "creo_inspect_model", {"model_id": model_a, "detail": "compact"}
        )
        check(
            "open_member_solidify_kept_revision",
            page.get("revision") == revision,
            {"before": revision, "after": page.get("revision")},
        )

        # --- Second thicken on the same model after reload --------------
        subsequent = await submit(
            client,
            [
                {
                    "op": "thicken",
                    "label": "thicken_loft_b_2",
                    "reference": {"kind": "quilt", "id": after_first["loft_b"].get("quilt_id")},
                    "thickness": THICK_MM,
                    "side": "symmetric",
                }
            ],
            jobs,
            model_a,
            revision,
        )
        subsequent_op = subsequent.get("operation") or {}
        expected_volume = LOFT_AREA * THIN_MM + LOFT_AREA * THICK_MM - SECOND_OVERLAP_MM3
        evidence["subsequent_thicken"] = {
            "job_id": subsequent.get("job_id"),
            "status": subsequent.get("status"),
            "volume_before_mm3": subsequent_op.get("volume_before_mm3"),
            "volume_after_mm3": subsequent_op.get("volume_after_mm3"),
            "naive_sum_mm3": LOFT_AREA * THIN_MM + LOFT_AREA * THICK_MM,
            "expected_with_corner_overlap_mm3": expected_volume,
            "saved": subsequent.get("saved_verified"),
            "message": str(subsequent.get("message"))[:300],
        }
        check(
            "subsequent_thicken_succeeded",
            subsequent.get("status") == "succeeded" and subsequent.get("saved_verified") is True,
            evidence["subsequent_thicken"],
        )
        check(
            "subsequent_thicken_volume_is_the_union",
            _near(subsequent_op.get("volume_after_mm3"), expected_volume, 5.0),
            {
                "volume_after_mm3": subsequent_op.get("volume_after_mm3"),
                "expected_with_corner_overlap_mm3": expected_volume,
                "naive_sum_mm3": LOFT_AREA * THIN_MM + LOFT_AREA * THICK_MM,
            },
        )
        revision = subsequent.get("revision")
        final_quilts = classify_quilts(await section(client, model_a, "quilts"))
        final_bodies = await section(client, model_a, "bodies")
        final_body = active_body(final_bodies)
        evidence["final_state"] = {
            "revision": revision,
            "quilts": {name: quilt_record(record) for name, record in final_quilts.items()},
            "body": {
                "bbox": final_body.get("bbox"),
                "surface_count": final_body.get("surface_count"),
            },
        }
        check(
            "quilt_identity_survives_both_thickens",
            all(
                name in final_quilts
                and final_quilts[name].get("quilt_id") == named[name].get("quilt_id")
                and _near(_area(final_quilts[name]), _area(named[name]), AREA_TOLERANCE_MM2)
                for name in ("loft_a", "loft_b", "floor")
            ),
            {"remaining": list(final_quilts)},
        )
        check(
            "both_thickened_members_report_closed",
            final_quilts.get("loft_a", {}).get("closed") is True
            and final_quilts.get("loft_b", {}).get("closed") is True
            and final_quilts.get("floor", {}).get("closed") is False,
            {
                name: (final_quilts.get(name) or {}).get("closed")
                for name in ("loft_a", "loft_b", "floor")
            },
        )
        check(
            "both_sheets_share_one_body",
            len([b for b in final_bodies if b.get("material") is True]) == 1,
            {"bodies": final_bodies},
        )

        # --- Model B: the same loft at 2 mm ----------------------------
        build_b = await submit(client, group_plan(), jobs)
        check(
            "group_built_2",
            build_b.get("status") == "succeeded" and build_b.get("saved_verified") is True,
            {"job_id": build_b.get("job_id"), "message": str(build_b.get("message"))[:300]},
        )
        if build_b.get("status") == "succeeded":
            model_b = build_b["model_id"]
            named_b = classify_quilts(await section(client, model_b, "quilts"))
            if "loft_a" in named_b:
                thick = await submit(
                    client,
                    [
                        {
                            "op": "thicken",
                            "label": "thicken_loft_a_2",
                            "reference": {
                                "kind": "quilt",
                                "id": named_b["loft_a"].get("quilt_id"),
                            },
                            "thickness": THICK_MM,
                            "side": "symmetric",
                        }
                    ],
                    jobs,
                    model_b,
                    build_b.get("revision"),
                )
                thick_op = thick.get("operation") or {}
                bodies_b = await section(client, model_b, "bodies")
                body_b = active_body(bodies_b)
                span_b = bbox_span(body_b, 1)
                evidence["thicken_2_0"] = {
                    "job_id": thick.get("job_id"),
                    "status": thick.get("status"),
                    "volume_after_mm3": thick_op.get("volume_after_mm3"),
                    "saved": thick.get("saved_verified"),
                    "thickness_span_y_mm": span_b,
                    "surface_count": body_b.get("surface_count"),
                }
                check(
                    "thicken_2_0_succeeded",
                    thick.get("status") == "succeeded" and thick.get("saved_verified") is True,
                    evidence["thicken_2_0"],
                )
                check(
                    "thicken_2_0_volume_1600",
                    _near(
                        thick_op.get("volume_after_mm3"),
                        LOFT_AREA * THICK_MM,
                        VOLUME_TOLERANCE_MM3,
                    ),
                    evidence["thicken_2_0"],
                )
                check(
                    "thicken_2_0_thickness_readback",
                    span_b is not None and abs(span_b - THICK_MM) <= 0.02,
                    {"thickness_span_y_mm": span_b, "bbox": body_b.get("bbox")},
                )
                check(
                    "thicken_2_0_is_a_closed_slab",
                    body_b.get("surface_count") == 6,
                    {"surface_count": body_b.get("surface_count")},
                )
            else:
                check("model_b_loft_found", False, {"quilts": list(named_b)})
        passed = all(item["ok"] for item in checks)
        return {
            "mode": "live",
            "passed": passed,
            "native_multi_quilt_group": "verified" if passed else "failed",
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

    report = asyncio.run(case_live()) if args.live else case_offline()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    output = args.output or ROOT / "build" / "multi_quilt_group" / run_id / "report.json"
    if output.exists():
        print(f"refusing to overwrite {output}", file=sys.stderr)
        return 3
    report["run_id"] = run_id
    report["report_path"] = str(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
