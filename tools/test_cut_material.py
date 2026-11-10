"""DEV-033/BUG-054 focused acceptance: cut material-change contract, T01-T08.

Real MCP + Creo run against isolated models. Each scenario records tool input,
job_id/model_id, terminal status, volumes, revision, operation details and the
saved-reload flag into build/cut_material_test.json.
"""

import asyncio
import json
import math
import sys
import time
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.mcp_readiness import wait_for_startup  # noqa: E402
from version import VERSION  # noqa: E402

REPORT = {"version": VERSION, "started_at": time.time(), "cases": {}, "failures": []}
RUN_TAG = time.strftime("%H%M%S")
TOL = 0.01

PLATE = [
    {
        "op": "sketch",
        "label": "sk_base",
        "plane": "XY",
        "entities": [{"type": "rectangle", "name": "base", "min": [-30, -20], "max": [30, 20]}],
    },
    {
        "op": "extrude",
        "label": "plate",
        "sketch": "sk_base",
        "depth": 10,
        "mode": "add",
        "direction": "positive",
    },
]
HOLE8 = [
    {
        "op": "sketch",
        "label": "sk_hole8",
        "plane": "XY",
        "entities": [{"type": "circle", "name": "d8", "center": [-10, 0], "radius": 4}],
    },
    {
        "op": "extrude",
        "label": "cut_hole8",
        "sketch": "sk_hole8",
        "mode": "cut",
        "direction": "positive",
        "depth_type": "through_all",
    },
]


def close(a, b, tol=TOL):
    return a is not None and abs(a - b) <= tol


async def call(client, name, args):
    result = await client.call_tool(name, args)
    if result.is_error:
        raise RuntimeError(f"{name}: {result.content}")
    return result.structured_content


async def job(client, name, args):
    created = await call(client, name, args)
    job_id, model_id = created["job_id"], created.get("model_id")
    for _ in range(330):
        result = await call(client, "creo_get_job", {"job_id": job_id, "detail": "compact"})
        if result["status"] not in ("queued", "running"):
            break
        await asyncio.sleep(1)
    result["model_id"] = model_id
    return result


async def new_model(client, name, operations):
    created = await job(client, "creo_new_part", {"model_name": name})
    model_id = created["model_id"]
    assert created["status"] == "succeeded", str(created.get("message"))
    result = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model_id,
            "expected_revision": created.get("revision"),
            "operations": operations,
        },
    )
    assert result["status"] == "succeeded", str(result.get("message"))
    return model_id, result["revision"]


def case(name, data):
    REPORT["cases"][name] = data
    print(f"[{name}] {json.dumps(data, ensure_ascii=False, default=str)[:400]}", flush=True)


def check(condition, message):
    if not condition:
        REPORT["failures"].append(message)
        print(f"  FAILURE: {message}", flush=True)
    return condition


def removed_of(result, label):
    for op in (result.get("result") or {}).get("operations") or []:
        if op.get("label") == label:
            return op.get("material_removed_mm3")
    return None


def cut_context_of(result, label):
    """B2/F11: the structured zero-material-cut receipt on one operation."""
    for op in (result.get("result") or {}).get("operations") or []:
        if op.get("label") == label:
            return op.get("cut_geometry_context")
    return None


def recomputable(context):
    """Recompute the interval from the receipt's own frame and effective depth."""
    if not isinstance(context, dict) or not context.get("available"):
        return False
    frame = context.get("sketch_frame") or {}
    interval = context.get("depth_interval_mm") or {}
    if not frame.get("available") or not interval.get("available"):
        return False
    origin, normal, axis = (
        frame.get("origin_mm"),
        frame.get("normal"),
        interval.get("axis"),
    )
    sign = interval.get("direction_sign")
    start = interval.get("start_offset_mm")
    end = interval.get("end_offset_mm")
    depth = interval.get("effective_depth_mm")
    if not all(isinstance(value, list) and len(value) == 3 for value in (origin, normal, axis)):
        return False
    if sign not in (1, -1) or any(value is None for value in (start, end, depth)):
        return False
    if abs((end - start) - depth) > 1e-6:
        return False
    if any(abs(axis[i] - normal[i] * sign) > 1e-6 for i in range(3)):
        return False
    for offset, key in ((start, "start_point_mm"), (end, "end_point_mm")):
        point = interval.get(key)
        if not isinstance(point, list) or len(point) != 3:
            return False
        if any(abs(point[i] - (origin[i] + axis[i] * offset)) > 1e-6 for i in range(3)):
            return False
    return True


async def model_state(client, model_id):
    state = await call(client, "creo_inspect_model", {"model_id": model_id, "detail": "compact"})
    aliases = await call(
        client, "creo_inspect_model", {"model_id": model_id, "detail": "full", "section": "aliases"}
    )
    names = {rec.get("name") for rec in ((aliases.get("data") or {}).get("aliases") or [])}
    return {
        "revision": state.get("revision"),
        "volume": (state.get("inspection") or {}).get("volume_mm3"),
        "aliases": names,
    }


async def volume_of(client, model_id):
    """Current volume from creo_inspect_model.

    Plan job results carry no ``inspection`` block (verified in jobs/*/job.json),
    so a volume assertion has to read the model, which is also the post-save
    state this driver means to assert.
    """
    state = await call(client, "creo_inspect_model", {"model_id": model_id, "detail": "compact"})
    return (state.get("inspection") or {}).get("volume_mm3")


async def t01_valid_cut(client):
    model_id, revision = await new_model(client, "bug054_t01_" + RUN_TAG, PLATE + HOLE8)
    result = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model_id,
            "expected_revision": revision,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk_c4",
                    "plane": "XY",
                    "entities": [{"type": "circle", "name": "c4", "center": [15, 0], "radius": 2}],
                },
                {
                    "op": "extrude",
                    "label": "cut_c4",
                    "sketch": "sk_c4",
                    "depth": 10,
                    "mode": "cut",
                    "direction": "positive",
                },
            ],
        },
    )
    volume = await volume_of(client, model_id)
    data = {
        "job_status": result["status"],
        "revision": result.get("revision"),
        "volume_mm3": volume,
        "material_removed_mm3": removed_of(result, "cut_c4"),
        "saved_reloaded": (result.get("result") or {}).get("saved_file_reloaded_and_verified"),
        "cut_geometry_context": cut_context_of(result, "cut_c4"),
    }
    case("T01", data)
    check(result["status"] == "succeeded", "T01 job must succeed")
    check(close(data["material_removed_mm3"], 40 * math.pi), "T01 removed ~40*pi")
    check(close(volume, 24000 - 200 * math.pi), "T01 volume 24000-200*pi")
    check(data["saved_reloaded"] is True, "T01 saved and reloaded")
    check(result.get("revision") == revision + 1, "T01 revision advances once")
    check(data["cut_geometry_context"] is None, "T01 successful cut has no failure context")


async def t02_disjoint_cut_rolls_back(client):
    model_id, revision = await new_model(client, "bug054_t02_" + RUN_TAG, PLATE + HOLE8)
    before = await model_state(client, model_id)
    result = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model_id,
            "expected_revision": revision,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk_out",
                    "plane": "XY",
                    "entities": [
                        {"type": "circle", "name": "c1", "center": [100, 100], "radius": 5}
                    ],
                },
                {
                    "op": "extrude",
                    "label": "cut_out",
                    "sketch": "sk_out",
                    "depth": 10,
                    "mode": "cut",
                    "direction": "positive",
                },
            ],
        },
    )
    after = await model_state(client, model_id)
    data = {
        "job_status": result["status"],
        "message": result.get("message"),
        "rollback_succeeded": (result.get("result") or {}).get("rollback_succeeded"),
        "before_volume": before["volume"],
        "after_volume": after["volume"],
        "before_revision": before["revision"],
        "after_revision": after["revision"],
        "aliases_absent": all(k not in after["aliases"] for k in ("sk_out", "cut_out")),
        "cut_geometry_context": cut_context_of(result, "cut_out"),
    }
    case("T02", data)
    check(result["status"] == "failed", "T02 must fail")
    check("removes no material" in (result.get("message") or ""), "T02 identifiable message")
    check("cut_geometry_context" in (result.get("message") or ""), "T02 message names receipt")
    check(data["rollback_succeeded"] is True, "T02 rolled back to checkpoint")
    check(data["after_volume"] == data["before_volume"], "T02 volume unchanged")
    check(data["after_revision"] == data["before_revision"], "T02 revision unchanged")
    check(data["aliases_absent"], "T02 no leftover aliases")
    context = data["cut_geometry_context"] or {}
    check(context.get("status") == "no_material_removed", "T02 structured status")
    check(recomputable(context), "T02 origin/normal/depth interval recomputable")
    check((context.get("sketch_frame") or {}).get("source") == "sketch_alias", "T02 frame source")
    interval = context.get("depth_interval_mm") or {}
    check(interval.get("source") == "feature_tree_and_sketch_alias", "T02 interval source is tree")
    check(close(interval.get("effective_depth_mm"), 10), "T02 effective depth is the 10 mm cut")
    volume = context.get("volume_mm3") or {}
    check(
        close(volume.get("before"), before["volume"])
        and close(volume.get("after"), before["volume"]),
        "T02 measured volumes match the unchanged model",
    )

    resume = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model_id,
            "expected_revision": revision,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk_ok",
                    "plane": "XY",
                    "entities": [{"type": "circle", "name": "ok", "center": [15, 0], "radius": 2}],
                },
                {
                    "op": "extrude",
                    "label": "cut_ok",
                    "sketch": "sk_ok",
                    "depth": 10,
                    "mode": "cut",
                    "direction": "positive",
                },
            ],
        },
    )
    check(resume["status"] == "succeeded", "T02 model still editable after failure")


async def t03_repeat_cut(client):
    model_id, revision = await new_model(client, "bug054_t03_" + RUN_TAG, PLATE + HOLE8)
    result = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model_id,
            "expected_revision": revision,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk_dup",
                    "plane": "XY",
                    "entities": [
                        {"type": "circle", "name": "dup", "center": [-10, 0], "radius": 2}
                    ],
                },
                {
                    "op": "extrude",
                    "label": "cut_dup",
                    "sketch": "sk_dup",
                    "depth": 10,
                    "mode": "cut",
                    "direction": "positive",
                },
            ],
        },
    )
    after = await model_state(client, model_id)
    data = {
        "job_status": result["status"],
        "message": result.get("message"),
        "after_revision": after.get("revision"),
        "cut_geometry_context": cut_context_of(result, "cut_dup"),
    }
    case("T03", data)
    check(result["status"] == "failed", "T03 repeated cut must fail")
    check("removes no material" in (result.get("message") or ""), "T03 same contract as T02")
    check(after.get("revision") == revision, "T03 revision unchanged")
    check(recomputable(data["cut_geometry_context"]), "T03 context recomputable too")


async def t04_boundary_and_small_cut(client):
    model_tan, rev_tan = await new_model(client, "bug054_t04a_" + RUN_TAG, PLATE)
    tangent = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model_tan,
            "expected_revision": rev_tan,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk_tan",
                    "plane": "XY",
                    "entities": [{"type": "circle", "name": "tan", "center": [35, 0], "radius": 5}],
                },
                {
                    "op": "extrude",
                    "label": "cut_tan",
                    "sketch": "sk_tan",
                    "depth": 10,
                    "mode": "cut",
                    "direction": "positive",
                },
            ],
        },
    )
    check(tangent["status"] == "failed", "T04 tangent-only cut has zero material")
    check("removes no material" in (tangent.get("message") or ""), "T04 tangent message")

    model_id, rev = await new_model(client, "bug054_t04b_" + RUN_TAG, PLATE)
    small = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model_id,
            "expected_revision": rev,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk_small",
                    "plane": "XY",
                    "entities": [
                        {"type": "circle", "name": "small", "center": [34, 0], "radius": 5}
                    ],
                },
                {
                    "op": "extrude",
                    "label": "cut_small",
                    "sketch": "sk_small",
                    "depth": 10,
                    "mode": "cut",
                    "direction": "positive",
                },
            ],
        },
    )
    expected = 10 * (25 * math.acos(0.8) - 12)
    volume = await volume_of(client, model_id)
    data = {
        "job_status": small["status"],
        "material_removed_mm3": removed_of(small, "cut_small"),
        "expected_removed": expected,
        "volume_mm3": volume,
    }
    case("T04", data)
    check(small["status"] == "succeeded", "T04 small real cut must not be rejected")
    check(close(data["material_removed_mm3"], expected), "T04 small removal matches analysis")
    check(close(volume, 24000 - expected), "T04 final volume matches analysis")


async def t05_multi_operation_plan(client):
    model_id, revision = await new_model(client, "bug054_t05_" + RUN_TAG, PLATE)
    result = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model_id,
            "expected_revision": revision,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk_good",
                    "plane": "XY",
                    "entities": [
                        {"type": "circle", "name": "good", "center": [10, 0], "radius": 2}
                    ],
                },
                {
                    "op": "extrude",
                    "label": "cut_good",
                    "sketch": "sk_good",
                    "depth": 10,
                    "mode": "cut",
                    "direction": "positive",
                },
                {
                    "op": "sketch",
                    "label": "sk_bad",
                    "plane": "XY",
                    "entities": [
                        {"type": "circle", "name": "bad", "center": [100, 100], "radius": 5}
                    ],
                },
                {
                    "op": "extrude",
                    "label": "cut_bad",
                    "sketch": "sk_bad",
                    "depth": 10,
                    "mode": "cut",
                    "direction": "positive",
                },
            ],
        },
    )
    after = await model_state(client, model_id)
    data = {
        "job_status": result["status"],
        "message": result.get("message"),
        "failed_operation_index": (result.get("result") or {}).get("failed_operation_index"),
        "rollback_succeeded": (result.get("result") or {}).get("rollback_succeeded"),
        "after_revision": after["revision"],
        "after_volume": after["volume"],
        "aliases_absent": all(
            k not in after["aliases"] for k in ("sk_good", "cut_good", "sk_bad", "cut_bad")
        ),
    }
    case("T05", data)
    check(result["status"] == "failed", "T05 plan must fail at the bad cut")
    check(data["failed_operation_index"] == 3, "T05 failure at operation index 3")
    check(data["rollback_succeeded"] is True, "T05 whole plan rolled back")
    check(data["after_revision"] == revision, "T05 revision restored")
    check(close(data["after_volume"], 24000), "T05 volume back to plate")
    check(data["aliases_absent"], "T05 no half-done aliases")

    resume = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model_id,
            "expected_revision": revision,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk_r",
                    "plane": "XY",
                    "entities": [{"type": "circle", "name": "r", "center": [10, 0], "radius": 2}],
                },
                {
                    "op": "extrude",
                    "label": "cut_r",
                    "sketch": "sk_r",
                    "depth": 10,
                    "mode": "cut",
                    "direction": "positive",
                },
            ],
        },
    )
    check(resume["status"] == "succeeded", "T05 model editable after rollback")


async def t07_legacy_regression(client):
    model_id, rev = await new_model(client, "bug054_t07a_" + RUN_TAG, PLATE)
    hole = await job(
        client,
        "creo_hole",
        {
            "model_id": model_id,
            "expected_revision": rev,
            "label": "hole_ok",
            "diameter": 8,
            "placement": {"kind": "plane", "axis": "z", "offset": 10},
            "reference1": {"kind": "datum_plane", "axis": "x"},
            "reference2": {"kind": "datum_plane", "axis": "y"},
            "offset1": 10,
            "offset2": 0,
        },
    )
    hole_removed = removed_of(hole, "hole_ok")
    check(hole["status"] == "succeeded", "T07 valid hole still succeeds")
    check(close(hole_removed, 160 * math.pi), "T07 hole removal 160*pi")

    bad_hole = await job(
        client,
        "creo_hole",
        {
            "model_id": model_id,
            "expected_revision": rev + 1,
            "label": "hole_out",
            "diameter": 8,
            "placement": {"kind": "plane", "axis": "z", "offset": 10},
            "reference1": {"kind": "datum_plane", "axis": "x"},
            "reference2": {"kind": "datum_plane", "axis": "y"},
            "offset1": 100,
            "offset2": 100,
        },
    )
    check(bad_hole["status"] == "failed", "T07 disjoint hole still rejected")

    model2, rev2 = await new_model(client, "bug054_t07b_" + RUN_TAG, PLATE)
    add = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model2,
            "expected_revision": rev2,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk_boss",
                    "plane": "XY",
                    "entities": [
                        {"type": "rectangle", "name": "boss", "min": [0, 0], "max": [5, 5]}
                    ],
                },
                {
                    "op": "extrude",
                    "label": "boss",
                    "sketch": "sk_boss",
                    "depth": 15,
                    "mode": "add",
                    "direction": "positive",
                },
            ],
        },
    )
    volume = await volume_of(client, model2)
    check(add["status"] == "succeeded", "T07 add still succeeds")
    check(removed_of(add, "boss") is None, "T07 add has no material_removed field")
    check(close(volume, 24000 + 125), "T07 add volume")

    model3, rev3 = await new_model(client, "bug054_t07c_" + RUN_TAG, PLATE)
    surface = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model3,
            "expected_revision": rev3,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk_srf",
                    "plane": "XY",
                    "entities": [{"type": "circle", "name": "srf", "center": [0, 0], "radius": 5}],
                },
                {
                    "op": "extrude",
                    "label": "srf",
                    "sketch": "sk_srf",
                    "depth": 10,
                    "mode": "surface",
                    "direction": "positive",
                },
            ],
        },
    )
    svolume = await volume_of(client, model3)
    check(surface["status"] == "succeeded", "T07 surface still succeeds")
    check(close(svolume, 24000), "T07 surface does not change volume")
    case(
        "T07",
        {
            "hole": hole["status"],
            "bad_hole": bad_hole["status"],
            "add": add["status"],
            "surface": surface["status"],
        },
    )


async def t08_revolve_cut(client):
    model_id, rev = await new_model(client, "bug054_t08a_" + RUN_TAG, PLATE)
    revolve = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model_id,
            "expected_revision": rev,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk_rev",
                    "plane": "XZ",
                    "entities": [
                        {"type": "centerline", "name": "cl", "start": [20, 0], "end": [25, 0]},
                        {"type": "rectangle", "name": "ring", "min": [20, 2], "max": [25, 4]},
                    ],
                },
                {
                    "op": "revolve",
                    "label": "cut_ring",
                    "sketch": "sk_rev",
                    "mode": "cut",
                    "angle": 360,
                    "direction": "positive",
                },
            ],
        },
    )
    volume = await volume_of(client, model_id)
    data = {
        "job_status": revolve["status"],
        "message": revolve.get("message"),
        "material_removed_mm3": removed_of(revolve, "cut_ring"),
        "volume_mm3": volume,
    }
    case("T08a", data)
    check(revolve["status"] == "succeeded", "T08a valid revolve cut succeeds")
    check(close(data["material_removed_mm3"], 30 * math.pi), "T08a removal is the half-ring 30*pi")
    check(close(volume, 24000 - 30 * math.pi), "T08a volume")

    model2, rev2 = await new_model(client, "bug054_t08b_" + RUN_TAG, PLATE)
    disjoint = await job(
        client,
        "creo_execute_plan",
        {
            "model_id": model2,
            "expected_revision": rev2,
            "operations": [
                {
                    "op": "sketch",
                    "label": "sk_rev2",
                    "plane": "XZ",
                    "entities": [
                        {"type": "centerline", "name": "cl", "start": [100, 0], "end": [105, 0]},
                        {"type": "rectangle", "name": "ring", "min": [100, 2], "max": [105, 4]},
                    ],
                },
                {
                    "op": "revolve",
                    "label": "cut_ring2",
                    "sketch": "sk_rev2",
                    "mode": "cut",
                    "angle": 360,
                    "direction": "positive",
                },
            ],
        },
    )
    context = cut_context_of(disjoint, "cut_ring2") or {}
    case(
        "T08b",
        {
            "job_status": disjoint["status"],
            "message": disjoint.get("message"),
            "cut_geometry_context": context,
        },
    )
    check(disjoint["status"] == "failed", "T08b disjoint revolve cut fails")
    check("removes no material" in (disjoint.get("message") or ""), "T08b same contract")
    check(context.get("status") == "no_material_removed", "T08b structured revolve context")
    frame = context.get("sketch_frame") or {}
    normal = frame.get("normal") or []
    check(
        len(normal) == 3 and close(normal[1], -1.0),
        "T08b XZ normal stays negative Y (A-batch three-plane contract)",
    )
    check(
        (context.get("depth_interval_mm") or {}).get("reason") == "revolve_cut_has_no_linear_depth",
        "T08b revolve never gains a fabricated linear depth interval",
    )


async def main():
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=60,
    ) as client:
        await wait_for_startup(client, REPORT, ROOT / "build/cut_material_test.json")
        status = await call(client, "creo_session_status", {})
        assert status["connected"], status
        for scenario in (
            t01_valid_cut,
            t02_disjoint_cut_rolls_back,
            t03_repeat_cut,
            t04_boundary_and_small_cut,
            t05_multi_operation_plan,
            t07_legacy_regression,
            t08_revolve_cut,
        ):
            print(f"== {scenario.__name__} ==", flush=True)
            await scenario(client)
    REPORT["T06"] = (
        "offline: measurement failure, rollback, revision and protection are "
        "covered by tests/unit/test_cut_material.py"
    )
    REPORT["failures"] = sorted(set(REPORT["failures"]))
    REPORT["finished_at"] = time.time()
    (ROOT / "build/cut_material_test.json").write_text(
        json.dumps(REPORT, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"failures={REPORT['failures']}", flush=True)
    sys.exit(1 if REPORT["failures"] else 0)


asyncio.run(main())
