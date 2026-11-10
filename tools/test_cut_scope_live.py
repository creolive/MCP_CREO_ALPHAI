"""B4/F08 live acceptance: a cut scoped to one body in a two-body part.

Builds a part with two separate bodies, then cuts only the first one:

* the operation result carries ``scope_applied`` with the requested and applied
  body ids read from the feature tree, ``source=feature_tree`` and
  ``non_target_bodies_unchanged=true``;
* the second body keeps its surface count and bounding box while the first
  loses material, and the total volume drops by the analytic amount;
* an unknown body id fails the job with ``F08_SCOPE_RESOLVE_FAILED`` and rolls
  back, leaving the revision unchanged;
* a scope on an add operation is refused before any job is created.

Live runs need a usable Creo session, so ``--live`` and
``--confirm-session-usable`` are both required.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
RUN_TAG = time.strftime("%H%M%S")
PLATE_MM = 60 * 40 * 10
BLOCK_MM = 40 * 40 * 10
CUT_RADIUS_MM = 5.0
CUT_DEPTH_MM = 10.0
REMOVED_MM3 = math.pi * CUT_RADIUS_MM**2 * CUT_DEPTH_MM
TOL = 1e-3
REPORT: dict = {"run_tag": RUN_TAG, "checks": {}, "failures": []}


def check(condition, message):
    REPORT["checks"][message] = bool(condition)
    if not condition:
        REPORT["failures"].append(message)
        print(f"  FAILURE: {message}", flush=True)
    return condition


def close(actual, expected, tolerance=TOL):
    return actual is not None and abs(actual - expected) <= tolerance


def two_body_plan():
    return [
        {
            "op": "sketch",
            "label": "sk_plate",
            "plane": "XY",
            "entities": [
                {"type": "rectangle", "name": "plate", "min": [-30, -20], "max": [30, 20]}
            ],
        },
        {
            "op": "extrude",
            "label": "plate",
            "sketch": "sk_plate",
            "depth": 10,
            "mode": "add",
        },
        {
            "op": "sketch",
            "label": "sk_block",
            "plane": "XY",
            "entities": [
                {"type": "rectangle", "name": "block", "min": [100, -20], "max": [140, 20]}
            ],
        },
        {
            "op": "extrude",
            "label": "block",
            "sketch": "sk_block",
            "depth": 10,
            "mode": "add",
            "new_body": True,
        },
    ]


def scoped_cut_plan(body_id, tag=""):
    # Each case needs its own labels: the server refuses a plan whose labels
    # already exist, so a rejected case must not reuse the accepted cut's names.
    sketch_label, cut_label = f"sk_hole{tag}", f"scoped_cut{tag}"
    return [
        {
            "op": "sketch",
            "label": sketch_label,
            "plane": "XY",
            "entities": [
                {"type": "circle", "name": "hole", "center": [0, 0], "radius": CUT_RADIUS_MM}
            ],
        },
        {
            "op": "extrude",
            "label": cut_label,
            "sketch": sketch_label,
            "mode": "cut",
            "direction": "positive",
            "depth": CUT_DEPTH_MM,
            "scope": {"kind": "bodies", "body_ids": [body_id]},
        },
    ]


async def call(client, name, args):
    result = await client.call_tool(name, args)
    if result.is_error:
        raise RuntimeError(f"{name}: {result.content}")
    return result.structured_content


async def wait_job(client, job_id):
    for _ in range(600):
        state = await call(client, "creo_get_job", {"job_id": job_id, "detail": "compact"})
        if state["status"] not in ("queued", "running"):
            return state
        await asyncio.sleep(1)
    raise RuntimeError("job did not finish")


async def submit_plan(client, model_id, revision, operations):
    submitted = await call(
        client,
        "creo_execute_plan",
        {"model_id": model_id, "expected_revision": revision, "operations": operations},
    )
    return submitted["job_id"], await wait_job(client, submitted["job_id"])


async def ready(client):
    for _ in range(120):
        status = await call(client, "creo_startup_status", {})
        if status.get("state") == "ready" and status.get("connected"):
            return True
        await asyncio.sleep(3)
    return False


async def bodies_of(client, model_id):
    """Per-body records live in the paginated ``bodies`` section.

    ``detail="compact"`` is a summary: it carries ``counts.bodies`` and
    ``body_counts`` but no per-body records, so a material comparison has to
    page ``detail="full"`` with ``section="bodies"`` instead.
    """
    records: list = []
    page = await call(
        client, "creo_inspect_model", {"model_id": model_id, "detail": "full", "section": "bodies"}
    )
    while True:
        records.extend((page.get("data") or {}).get("bodies") or [])
        cursor = page.get("next_cursor")
        if not cursor:
            return records
        page = await call(
            client,
            "creo_inspect_model",
            {"model_id": model_id, "detail": "full", "section": "bodies", "cursor": cursor},
        )


def body_view(records):
    bodies = {}
    for body in records:
        bodies[body.get("id")] = {
            "surface_count": body.get("surface_count"),
            "bbox": body.get("bbox"),
            "material": body.get("material"),
            "state": body.get("state"),
        }
    return bodies


async def volume_of(client, model_id):
    """Volume from the saved-model summary; the job result is only a fallback."""
    summary = await call(client, "creo_inspect_model", {"model_id": model_id, "detail": "compact"})
    return (summary.get("inspection") or {}).get("volume_mm3")


def scope_of(job):
    for operation in (job.get("result") or {}).get("operations") or []:
        if str(operation.get("label") or "").startswith("scoped_cut"):
            return operation.get("scope_applied")
    return None


async def main_async(args):
    if not (args.live and args.confirm_session_usable):
        print("refused: pass --live --confirm-session-usable to touch the session")
        return 2
    params = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT)
    )
    async with Client(params) as client:
        if not await ready(client):
            print("refused: session never became ready; see creo_startup_status")
            return 2
        created = await call(client, "creo_new_part", {"model_name": f"b4_scope_{RUN_TAG}"})
        created = await wait_job(client, created["job_id"])
        model_id, revision = created["model_id"], created["revision"]
        REPORT["model_id"], REPORT["model_name"] = model_id, f"b4_scope_{RUN_TAG}"
        check(created["status"] == "succeeded", "part created")

        job_id, built = await submit_plan(client, model_id, revision, two_body_plan())
        REPORT["build_job"] = job_id
        check(built["status"] == "succeeded", "two-body plan succeeded")
        revision = built["revision"]
        before = body_view(await bodies_of(client, model_id))
        active = [bid for bid, body in before.items() if body["material"]]
        REPORT["bodies_before"] = before
        check(len(active) == 2, "two bodies carry material before the cut")
        if len(active) != 2:
            REPORT["success"] = False
            Path(args.output).write_text(json.dumps(REPORT, indent=2), encoding="utf-8")
            return 1
        target, other = sorted(active)[0], sorted(active)[1]
        REPORT["target_body_id"], REPORT["other_body_id"] = target, other

        job_id, cut = await submit_plan(client, model_id, revision, scoped_cut_plan(target))
        REPORT["cut_job"] = job_id
        check(cut["status"] == "succeeded", "scoped cut succeeded")
        check(
            (cut.get("result") or {}).get("saved_file_reloaded_and_verified") is True,
            "scoped cut saved and reloaded verified",
        )
        applied = scope_of(cut)
        REPORT["scope_applied"] = applied
        check(isinstance(applied, dict), "scoped cut reports scope_applied")
        if isinstance(applied, dict):
            check(applied.get("requested_body_ids") == [target], "requested ids echo the scope")
            check(applied.get("applied_body_ids") == [target], "applied ids come from the tree")
            check(applied.get("source") == "feature_tree", "applied source is the feature tree")
            check(applied.get("query_code") == 0, "element readback succeeded")
            check(
                applied.get("non_target_bodies_unchanged") is True,
                "non-target body comparison is true",
            )
        after = body_view(await bodies_of(client, model_id))
        REPORT["bodies_after"] = after
        check(
            after.get(other, {}).get("surface_count") == before[other]["surface_count"],
            "non-target body keeps its surface count",
        )
        check(
            after.get(other, {}).get("bbox") == before[other]["bbox"],
            "non-target body keeps its bbox",
        )
        target_surfaces = after.get(target, {}).get("surface_count")
        check(
            isinstance(target_surfaces, int) and target_surfaces != before[target]["surface_count"],
            "target body changed",
        )
        measured = await volume_of(client, model_id)
        if measured is None:
            # Job results may carry a reference instead of the inline inspection.
            measured = ((cut.get("result") or {}).get("inspection") or {}).get("volume_mm3")
        REPORT["volume_mm3"] = measured
        check(
            close(measured, PLATE_MM + BLOCK_MM - REMOVED_MM3),
            "total volume matches the analytic value",
        )

        revision = cut["revision"]
        bad_id = 100000
        job_id, wrong = await submit_plan(
            client, model_id, revision, scoped_cut_plan(bad_id, "_bad")
        )
        REPORT["wrong_scope_job"] = job_id
        message = str(wrong.get("message") or "")
        check(wrong["status"] == "failed", "unknown body id fails the job")
        check("F08_SCOPE_RESOLVE_FAILED" in message, "unknown body id names the contract code")
        check(
            (wrong.get("result") or {}).get("rollback_succeeded") is True,
            "unknown body id rolled back",
        )
        # The failed job's own record may omit the revision, so the model summary
        # is the authority here: an unknown value must not pass this check.
        settled = await call(
            client, "creo_inspect_model", {"model_id": model_id, "detail": "compact"}
        )
        check(settled.get("revision") == revision, "failed scope left the revision alone")

        # An invalid scope is refused by plan validation, before a job exists, so
        # the call itself may come back as a tool error instead of a job record.
        refused = await client.call_tool(
            "creo_execute_plan",
            {
                "model_id": model_id,
                "expected_revision": revision,
                "operations": [
                    {
                        "op": "sketch",
                        "label": "sk_scope_add",
                        "plane": "XY",
                        "entities": [
                            {"type": "circle", "name": "c", "center": [0, 0], "radius": 3}
                        ],
                    },
                    {
                        "op": "extrude",
                        "label": "scope_add",
                        "sketch": "sk_scope_add",
                        "depth": 5,
                        "mode": "add",
                        "scope": {"kind": "bodies", "body_ids": [target]},
                    },
                ],
            },
        )
        refused_text = json.dumps(
            {
                "is_error": refused.is_error,
                "content": [str(item.text) for item in refused.content if hasattr(item, "text")],
                "structured": refused.structured_content,
            },
            ensure_ascii=False,
        )
        REPORT["add_scope_refusal"] = refused_text[:400]
        # Any tool error would pass a bare is_error check, so the refusal has to
        # name the contract rule; a pre-empted later call must not look like this.
        check("only to extrude cuts" in refused_text, "scope on an add operation is refused")

    REPORT["success"] = not REPORT["failures"]
    Path(args.output).write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"failures={REPORT['failures']}", flush=True)
    return 0 if not REPORT["failures"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="required: touch the session")
    parser.add_argument(
        "--confirm-session-usable",
        action="store_true",
        help="required: the caller confirmed this session may be used",
    )
    parser.add_argument("--output", default="build/cut_scope_live.json")
    args = parser.parse_args()
    try:
        return asyncio.run(main_async(args))
    except Exception as error:  # keep the partial evidence when a call blows up
        REPORT["success"] = False
        REPORT["error"] = f"{type(error).__name__}: {error}"
        REPORT["failures"].append(REPORT["error"])
        Path(args.output).write_text(
            json.dumps(REPORT, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"error={REPORT['error']}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
