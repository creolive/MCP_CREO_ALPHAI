"""R10: in-plan edge selection by geometry, verified across edge-id renumbering.

The plan-level selector is ``{kind:'edge_geometry', endpoints_mm:[[x,y,z],[x,y,z]],
tolerance_mm:...}``: the native resolver re-queries the current model for every
operation and requires exactly one undirected straight-edge match. This driver
answers the plan question that the Python-side per-job inspection cannot:

* two non-interfering flanges (+x and -x of a 185 x 232 x 1 mm plate) are
  submitted in separate jobs; the -x reference keeps the endpoints captured
  **before** the +x flange existed, so only a re-query against the current
  (renumbered) geometry can still find that edge;
* the observed edge ids before and after the first flange are recorded, so
  "the id changed" or "the id happened to stay" is evidence rather than an
  assumption;
* the explicit miter request is combined with the same selector on the -y
  wall, whose attachment edge is shortened by the two existing bends;
* one geometry that is absent from the model must be refused by the native
  resolver, leave the revision and volume untouched, and report how many
  straight edges were scanned.

Default is strictly offline: no MCP client, no Toolkit connection, no job.
``--live --confirm-session-usable`` starts the formal live run on the single
shared dev service; the report is written under
build/flange_edge_geometry/<run_id>/ and never overwritten.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
import uuid
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))
if str(_SOURCE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT / "src"))

from creo_mechdog.schema import validate_operations  # noqa: E402
from tests.unit import test_sheetmetal_flange as fx  # noqa: E402
from tools.sheetmetal_live import (  # noqa: E402
    LiveRunner,
    failure_text,
    require_manual_start,
    unique_name,
)
from tools.test_sheetmetal_box_live import bbox_of, local_provenance  # noqa: E402
from tools.test_sheetmetal_planar_box import (  # noqa: E402
    top_horizontal_faces,
    wall_top_faces,
)

ROOT = _SOURCE_ROOT

LENGTH_MM = fx.PLATE_LENGTH_MM
WIDTH_MM = fx.PLATE_WIDTH_MM
THICKNESS_MM = fx.PLATE_THICKNESS_MM
HEIGHT_MM = fx.FLANGE_HEIGHT_MM
RADIUS_MM = fx.FLANGE_RADIUS_MM
Y_FACTOR = fx.FLANGE_Y_FACTOR
ANGLE_DEG = fx.FLANGE_ANGLE_DEG
MITER = {"width": THICKNESS_MM, "offset": THICKNESS_MM}
TOL_MM = 1e-6
BUDGET_SECONDS = 420.0
ABSENT_GEOMETRY_MM = [[900.0, 900.0, 900.0], [900.0, 901.0, 900.0]]

#: Opposite ends of the plate: the bend zones do not meet, so the first flange
#: cannot consume or move the second reference.
NON_INTERFERING = ("+x", "-x")


def geometry_of(reference: dict, tolerance_mm: float = TOL_MM) -> dict:
    """The plan selector built from a driver-selected edge's current endpoints."""
    geometry = reference["geometry"]
    return {
        "kind": "edge_geometry",
        "endpoints_mm": [list(geometry["start"]), list(geometry["end"])],
        "tolerance_mm": tolerance_mm,
    }


def flange_operation(edge: dict, label: str, *, miter: dict | None = None) -> dict:
    operation = {
        "op": "sheetmetal_flange",
        "label": label,
        "edge": edge,
        "height": HEIGHT_MM,
        "angle": ANGLE_DEG,
        "radius": RADIUS_MM,
        "flip": False,
        "y_factor": Y_FACTOR,
    }
    if miter is not None:
        operation["miter_cuts"] = dict(miter)
    return operation


def plate_plan() -> list[dict]:
    return [
        {
            "op": "sheetmetal_planar_wall",
            "label": "wall_pw",
            "plane": "XY",
            "length": LENGTH_MM,
            "width": WIDTH_MM,
            "thickness": THICKNESS_MM,
            "direction": "positive",
        }
    ]


def endpoints_match(left: dict, right: dict, tolerance: float = 1e-6) -> bool:
    """Undirected comparison of two endpoint pairs."""
    first = [list(left["start"]), list(left["end"])]
    second = [list(right["start"]), list(right["end"])]

    def close(a: list, b: list) -> bool:
        return all(abs(float(x) - float(y)) <= tolerance for x, y in zip(a, b))

    return (close(first[0], second[0]) and close(first[1], second[1])) or (
        close(first[0], second[1]) and close(first[1], second[0])
    )


# --- offline ---------------------------------------------------------------


def offline_checks() -> dict:
    inspection = fx.box_inspection()
    bounds = fx.PLATE_BOUNDS
    references = {
        side: fx.select_wall_edge(inspection, bounds, side, face="top") for side in NON_INTERFERING
    }
    operations = [
        flange_operation(geometry_of(references[side]), f"f_{side[1]}") for side in NON_INTERFERING
    ]
    validated = [validate_operations([operation])[0] for operation in operations]

    # The plan is built from geometry, so renumbering the fixture ids must not
    # change what the payload says: the endpoints are the reference.
    renumbered = fx.refresh_after_flange(
        inspection, bounds, references["+x"], "+x", thickness_inside=True
    )
    stale = geometry_of(references["-x"])
    stale_validated = validate_operations([flange_operation(stale, "f_nx_stale")])[0]["edge"]

    return {
        "plate_plan_valid": validate_operations(plate_plan())[0]["op"] == "sheetmetal_planar_wall",
        "sides_are_opposite": {tuple(sorted(NON_INTERFERING))} == {("+x", "-x")},
        "edge_payloads": [operation["edge"] for operation in validated],
        "both_payloads_are_geometry": [op["edge"]["kind"] for op in validated]
        == ["edge_geometry", "edge_geometry"],
        "payload_keeps_endpoints_after_fixture_renumbering": stale_validated["endpoints_mm"]
        == [
            [float(value) for value in references["-x"]["geometry"]["start"]],
            [float(value) for value in references["-x"]["geometry"]["end"]],
        ],
        "fixture_ids_actually_changed": sorted(edge["id"] for edge in renumbered["edges"])
        != sorted(edge["id"] for edge in inspection["edges"]),
        "note": (
            "offline only proves the payload shape and determinism; whether Creo keeps or "
            "changes ids and whether one native match exists is a live result"
        ),
    }


# --- live ------------------------------------------------------------------


def operation_detail(job: dict, op: str) -> dict:
    for item in (job.get("result") or {}).get("operations") or []:
        if isinstance(item, dict) and item.get("op") == op:
            return item
    return {}


async def create_plate(runner: LiveRunner) -> tuple[dict, dict | None]:
    model_name = unique_name("r10_geom")
    created = await runner.submit(
        "new",
        "creo_new_sheetmetal",
        {"model_name": model_name, "template": "native_planar"},
    )
    entry = {
        "group": "edge_geometry",
        "model_name": model_name,
        "model_id": created.get("model_id"),
        "new_job_id": created["job_id"],
        "passed": False,
    }
    terminal = await runner.wait_job(created["job_id"], budget=BUDGET_SECONDS)
    entry["new_status"] = terminal.get("status")
    if terminal.get("status") != "succeeded":
        entry.update(failure=failure_text(terminal))
        return runner.case(entry), None

    snapshot = await runner.snapshot(entry["model_id"])
    plan = plate_plan()
    validate_operations(plan)
    job = await runner.submit(
        "wall",
        "creo_execute_plan",
        {
            "model_id": entry["model_id"],
            "expected_revision": snapshot.get("revision"),
            "operations": plan,
        },
    )
    terminal = await runner.wait_job(job["job_id"], budget=BUDGET_SECONDS)
    result = terminal.get("result") or {}
    entry["wall"] = {
        "job_id": job["job_id"],
        "status": terminal.get("status"),
        "message": terminal.get("message"),
        "revision": terminal.get("revision"),
        "saved_file_reloaded_and_verified": result.get("saved_file_reloaded_and_verified"),
    }
    if terminal.get("status") != "succeeded":
        entry.update(failure=failure_text(terminal))
        return runner.case(entry), None
    after = await runner.snapshot(entry["model_id"])
    entry["plate_bbox_mm"] = bbox_of(after)
    entry["plate_volume_mm3"] = LiveRunner.volume(after)
    return entry, after


async def submit_flange(
    runner: LiveRunner,
    case_key: str,
    model_id: str,
    revision: int | None,
    operation: dict,
) -> tuple[dict, dict]:
    submitted = await runner.submit(
        case_key,
        "creo_sheetmetal_flange",
        {
            "model_id": model_id,
            "expected_revision": revision,
            **{key: value for key, value in operation.items() if key != "op"},
        },
    )
    terminal = await runner.wait_job(submitted["job_id"], budget=BUDGET_SECONDS)
    after = await runner.snapshot(model_id)
    result = terminal.get("result") or {}
    record = {
        "job_id": submitted["job_id"],
        "status": terminal.get("status"),
        "message": terminal.get("message"),
        "revision_before": revision,
        "revision_after": after.get("revision"),
        "volume_after_mm3": LiveRunner.volume(after),
        "saved_file_reloaded_and_verified": result.get("saved_file_reloaded_and_verified"),
        "rollback_status": result.get("rollback_status"),
    }
    detail = operation_detail(terminal, "sheetmetal_flange")
    record["operation_result"] = {
        key: detail.get(key)
        for key in ("label", "execution_status", "effect_status", "error", "message")
        if detail.get(key) is not None
    }
    if terminal.get("status") != "succeeded":
        record["failure"] = failure_text(terminal)
    return record, after


async def run_geometry(runner: LiveRunner) -> dict:
    entry, snapshot = await create_plate(runner)
    if snapshot is None:
        return entry
    model_id = entry["model_id"]
    plate_bounds = fx.active_bbox(LiveRunner.inspection(snapshot))
    inspection = LiveRunner.inspection(snapshot)
    initial = {
        side: fx.select_wall_edge(inspection, plate_bounds, side, face="top")
        for side in NON_INTERFERING
    }
    entry["initial_edges"] = {
        side: {"id": reference["geometry"]["id"], **reference["geometry"]}
        for side, reference in initial.items()
    }
    entry["initial_edge_ids"] = sorted(edge["id"] for edge in inspection.get("edges") or [])
    try:
        initial_miter_edge = fx.select_wall_edge(inspection, plate_bounds, "-y", face="top")
    except fx.EdgeSelectionError as error:
        initial_miter_edge = None
        entry["initial_miter_edge"] = f"EdgeSelectionError: {error}"

    steps = []
    revision = snapshot.get("revision")
    for side, label in (("+x", "f_px"), ("-x", "f_nx")):
        operation = flange_operation(geometry_of(initial[side]), label)
        validate_operations([operation])
        record, after = await submit_flange(
            runner, f"flange_{label}", model_id, revision, operation
        )
        record["label"] = label
        record["side"] = side
        record["edge_geometry"] = operation["edge"]
        record["edge_span_mm"] = initial[side]["geometry"]["span_mm"]
        record["endpoints_captured_before_any_flange"] = True
        steps.append(record)
        if record["status"] != "succeeded":
            entry.update(steps=steps, failure=record.get("failure"))
            return runner.case(entry)
        revision = record["revision_after"]
        current = LiveRunner.inspection(after)
        if side == "+x":
            # The -x boundary still exists; only its id is allowed to differ.
            try:
                seen = fx.select_wall_edge(current, plate_bounds, "-x", face="top")
            except fx.EdgeSelectionError as error:
                record["renumbering_observation"] = f"EdgeSelectionError: {error}"
            else:
                record["renumbering_observation"] = {
                    "id_before": initial["-x"]["geometry"]["id"],
                    "id_after": seen["geometry"]["id"],
                    "renumbered": seen["geometry"]["id"] != initial["-x"]["geometry"]["id"],
                    "endpoints_unchanged": endpoints_match(
                        seen["geometry"], initial["-x"]["geometry"]
                    ),
                    "edge_ids_after": sorted(edge["id"] for edge in current.get("edges") or []),
                }

    final = await runner.snapshot(model_id)
    final_inspection = LiveRunner.inspection(final)
    bounds = bbox_of(final)
    top_z = bounds[1][2] if bounds else THICKNESS_MM + HEIGHT_MM
    faces = top_horizontal_faces(final_inspection, top_z)
    for step in steps:
        step["top_faces"] = wall_top_faces(
            faces, plate_bounds, step["side"], step.get("edge_span_mm")
        )
        step["wall_verified"] = (step.get("top_faces") or {}).get("relation") == "matches"

    # The explicit miter request combined with the same geometry selector.
    try:
        miter_reference = fx.select_wall_edge(
            final_inspection, plate_bounds, "-y", face="top", allow_shortened=True
        )
    except fx.EdgeSelectionError as error:
        entry.update(steps=steps, miter={"error": f"EdgeSelectionError: {error}"})
        return runner.case(entry)
    if initial_miter_edge is not None:
        entry["miter_edge_renumbering"] = {
            "id_before": initial_miter_edge["geometry"]["id"],
            "id_after": miter_reference["geometry"]["id"],
            "renumbered": miter_reference["geometry"]["id"] != initial_miter_edge["geometry"]["id"],
            "span_before_mm": initial_miter_edge["geometry"]["span_mm"],
            "span_after_mm": miter_reference["geometry"]["span_mm"],
            "shortened": miter_reference["geometry"]["shortfall_mm"] > 0,
            "edge_ids_after": sorted(edge["id"] for edge in final_inspection.get("edges") or []),
        }
    miter_operation = flange_operation(geometry_of(miter_reference), "f_ny", miter=MITER)
    validate_operations([miter_operation])
    before_volume = LiveRunner.volume(final)
    miter_record, after_miter = await submit_flange(
        runner, "flange_miter", model_id, final.get("revision"), miter_operation
    )
    miter_record.update(
        label="f_ny",
        edge_geometry=miter_operation["edge"],
        attachment_span_mm=miter_reference["geometry"]["span_mm"],
        attachment_shortfall_mm=miter_reference["geometry"]["shortfall_mm"],
        miter_cuts=MITER,
        volume_before_mm3=before_volume,
    )
    after_inspection = LiveRunner.inspection(after_miter)
    after_bounds = bbox_of(after_miter)
    after_faces = top_horizontal_faces(after_inspection, after_bounds[1][2]) if after_bounds else []
    miter_record["top_faces"] = wall_top_faces(
        after_faces, plate_bounds, "-y", miter_reference["geometry"]["span_mm"]
    )
    miter_record["wall_verified"] = miter_record["top_faces"] is not None
    entry["miter"] = miter_record
    if miter_record["status"] == "succeeded":
        revision = miter_record["revision_after"]

    # A geometry that is not in the model must be refused by the native scan.
    absent = flange_operation(
        {"kind": "edge_geometry", "endpoints_mm": ABSENT_GEOMETRY_MM, "tolerance_mm": TOL_MM},
        "f_absent",
    )
    validate_operations([absent])
    before_refusal = await runner.snapshot(model_id)
    refusal, after_refusal = await submit_flange(
        runner, "flange_absent", model_id, before_refusal.get("revision"), absent
    )
    refusal.update(
        label="f_absent",
        edge_geometry=absent["edge"],
        volume_before_mm3=LiveRunner.volume(before_refusal),
    )
    entry["absent_geometry"] = refusal
    entry["steps"] = steps
    entry["final_bbox_mm"] = bbox_of(after_refusal)
    entry["final_volume_mm3"] = LiveRunner.volume(after_refusal)

    renumbering = steps[0].get("renumbering_observation")
    entry["assertions"] = {
        "plate_is_185x232x1": _bbox_spans(entry.get("plate_bbox_mm"))
        == (LENGTH_MM, WIDTH_MM, THICKNESS_MM),
        "two_geometry_flanges_succeeded": all(step["status"] == "succeeded" for step in steps)
        and len(steps) == 2,
        "two_geometry_flanges_saved_and_reloaded": all(
            step["saved_file_reloaded_and_verified"] is True for step in steps
        ),
        "geometry_payloads_were_used": all(
            step["edge_geometry"]["kind"] == "edge_geometry" for step in steps
        ),
        "edge_id_renumbering_observation_recorded": isinstance(renumbering, dict)
        and isinstance(renumbering.get("renumbered"), bool),
        "second_reference_endpoints_survived": isinstance(renumbering, dict)
        and renumbering.get("endpoints_unchanged") is True,
        "two_walls_measured_on_their_sides": all(
            step.get("wall_verified") is True for step in steps
        ),
        "miter_geometry_flange_succeeded": miter_record["status"] == "succeeded",
        "miter_geometry_flange_saved_and_reloaded": miter_record["saved_file_reloaded_and_verified"]
        is True,
        "miter_attachment_was_shortened": (miter_record.get("attachment_shortfall_mm") or 0) > 0,
        "miter_edge_renumbering_observation_recorded": isinstance(
            entry.get("miter_edge_renumbering"), dict
        ),
        "miter_old_edge_id_is_gone": isinstance(entry.get("miter_edge_renumbering"), dict)
        and entry["miter_edge_renumbering"]["id_before"]
        not in entry["miter_edge_renumbering"]["edge_ids_after"],
        "miter_wall_measured": miter_record.get("wall_verified") is True,
        "absent_geometry_refused": refusal["status"] == "failed",
        "absent_geometry_names_the_scan": "matched none of the"
        in json.dumps(refusal.get("operation_result") or {})
        or "matched none of the" in (refusal.get("message") or ""),
        "absent_geometry_revision_unchanged": refusal["revision_after"]
        == refusal["revision_before"],
        "absent_geometry_volume_unchanged": _close(
            refusal.get("volume_after_mm3"), refusal.get("volume_before_mm3")
        ),
    }
    entry["passed"] = all(entry["assertions"].values())
    return runner.case(entry)


def _bbox_spans(bounds: list | None) -> tuple | None:
    if not bounds:
        return None
    low, high = bounds
    return tuple(round(float(high[i]) - float(low[i]), 6) for i in range(3))


def _close(left: float | None, right: float | None, tolerance: float = 1e-6) -> bool:
    if left is None or right is None:
        return False
    return abs(float(left) - float(right)) <= tolerance


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "flange_edge_geometry" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


async def live(output: Path, run_id: str) -> int:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    runner: LiveRunner | None = None
    teardown = None
    try:
        async with Client(params, read_timeout_seconds=300) as client:
            runner = LiveRunner(
                client,
                output,
                "R10 / FEAT-014 edge_geometry",
                (
                    "185x232x1 planar wall; +x and -x flanges selected by endpoints captured "
                    "before any flange (stale ids, current geometry); -y flange with an "
                    "explicit miter request; one absent geometry refused"
                ),
                run_id,
            )
            runner.report["source"] = local_provenance()
            runner.report["driver_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            await runner.start()
            try:
                await run_geometry(runner)
            except BaseException as error:
                runner.report["stopped"] = f"{type(error).__name__}: {error}"
    except BaseException as error:  # teardown failures must not orphan the server
        teardown = f"{type(error).__name__}: {error}"
    if runner is None:
        raise RuntimeError(f"MCP client never started: {teardown}")
    if teardown:
        runner.report["client_teardown"] = teardown[:600]
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if runner.report["passed"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.live and not args.confirm_session_usable:
        print(
            "live runs require --confirm-session-usable after human session checks", file=sys.stderr
        )
        return 2
    try:
        run_id = new_run_id()
        output = resolve_output(args.output, run_id)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    if args.live:
        try:
            require_manual_start(ROOT / "config.json")
        except (ValueError, OSError) as error:
            print(f"LIVE_REFUSED: {error}", file=sys.stderr)
            return 2
        return asyncio.run(live(output, run_id))

    report = {
        "task": "R10 / FEAT-014 edge_geometry",
        "run_id": run_id,
        "mode": "offline",
        "native_acceptance": "not_run",
        "source": local_provenance(),
        "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "checks": offline_checks(),
        "not_verified": [
            "no model was created and no flange was built offline",
            "Creo 9/10 and WorkBuddy were not exercised",
            "the native 0-candidate refusal and the id renumbering are live results only",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name("report.sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"report_sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
