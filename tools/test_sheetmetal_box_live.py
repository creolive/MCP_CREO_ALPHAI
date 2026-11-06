"""DEV-052 N05 box driver: formal third-wall probes, trim measurement and guards.

The 2026-10-30 live contrast (a one-off build probe that never entered the repo)
settled the trigger condition: a wall whose attachment edge ends adjacent to an
existing bend fails even when only one end touches, while the full free edge
builds as a real 90-degree bend. The internal mechanism - section out of the
bendable area vs neighbouring material overlap - is still unproven.

This driver turns that one-off probe capability into the formal N05 entry:

1. the frozen offline half of the T05 contrast (full-length / trimmed-20 / order
   gradient designs, the end_trim_mm contract, the failing-wall stage record and
   the corner decision table) is unchanged;
2. the formal live probe plan: -y as the first wall on the full free edge, +x
   then -y (one adjacent bend end), +x then -x then -y (the round-six shape),
   plus the end_trim_mm measurement (no trim vs a positive trim on free first
   walls, two fresh models, classified from the measured volume);
3. native failure forensics guards: the failing paths record bounded edge,
   adjacent-face/edge, feature-status and element-tree evidence with unknowns
   null, so N06 receives mechanism facts instead of bare error codes;
4. the regression locks: one missing live switch means no connection, the
   output path never overwrites, unknown measurements never pass, a failing
   third wall is never counted as a built wall and four_walls_complete stays
   False in every verdict branch;
5. the edge-selection fix from the 2026-10-30 live first run: every wall is
   selected against the plate bounds frozen from its base snapshot (never the
   post-flange body bbox, whose top is the wall top), thickness-scale rim
   edges are never candidates, and a selection that is ambiguous or
   unqualified is recorded as driver_edge_selection_error -- a driver failure,
   never a Creo failure and never a trigger reproduction;
6. the N06 adjacent-bend-ends boundary: the native pre-check now refuses a
   wall whose attachment-edge end abuts an existing bend before any feature
   exists (failure_reason=adjacent_bend_ends). Since the trigger condition is
   proven (2026-10-30/31), that rejection is the expected known boundary and
   the group verdict records adjacent_bend_ends_rejected; the
   trigger_reproduced label is reserved for the unexpected shape -- a
   regeneration failure without the adjacency marker.

Default is strictly offline: no MCP client, no Toolkit connection, no job.
--live --confirm-session-usable together start the formal live probes on the
single shared dev service, only after the human session checks; the run is a
diagnostic, never a capability claim.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402
from tests.unit import test_sheetmetal_box_live as box  # noqa: E402
from tests.unit import test_sheetmetal_flange as fx  # noqa: E402
from tests.unit import test_sheetmetal_relief as relief  # noqa: E402
from tools.sheetmetal_live import (  # noqa: E402
    LiveRunner,
    LiveStop,
    failure_text,
    require_manual_start,
    unique_name,
)

ROOT = SOURCE_PATHS.resource_root


# --- checks ---------------------------------------------------------------


def check_contrast_design() -> dict:
    groups = box.contrast_groups()
    return {
        "trim_mm": box.TRIM_MM,
        "groups": {
            name: {
                "order": group["order"],
                "trim_third": group["trim_third"],
                "why": group["why"],
                "walls": group["walls"],
                "f_ny_material_corners": group["f_ny_material_corners"],
            }
            for name, group in groups.items()
        },
        "corner_gradient": {
            name: groups[name]["f_ny_material_corners"]
            for name in ("order_ny_first", "order_ny_second", "full_length", "trimmed_20")
        },
        "rules": [
            "one fresh model per group; one job per wall",
            "every wall's edge is re-selected from a fresh inspection with an explicit face",
            "the trimmed group only runs after the free-wall probe confirms the setback "
            "reading of the blind offset",
        ],
        "statement": (
            "the contrast design is frozen offline; no group has run, so no outcome is "
            "recorded and corner interference stays a candidate"
        ),
    }


def check_oracle_rows() -> dict:
    rows = {name: box.offline_plan_rows(name) for name in box.contrast_groups()}
    trimmed = rows["trimmed_20"][-1]
    assert trimmed["label"] == "f_ny" and trimmed["end_trim_mm"] == box.TRIM_MM
    assert abs(trimmed["effective_span_mm"] - (trimmed["fixture_span_mm"] - 2 * box.TRIM_MM)) < 1e-9
    assert (
        abs(
            trimmed["expected_added_mm3"]
            - relief.bent_wall_increment_mm3(trimmed["effective_span_mm"])
        )
        < 1e-6
    )
    return {
        "rows": rows,
        "oracle_basis": (
            "bent-wall increment (span x height x thickness with the bend-arc correction) "
            "validated against the measured 2026-10-29 walls"
        ),
        "trim_rows_are_setback_reading_only": True,
        "statement": (
            "offline expectations assume full fixture spans and the setback trim reading; "
            "the live driver recomputes every expectation from the measured span"
        ),
    }


def check_trim_probe() -> dict:
    operations, reference = box.trim_probe_plan()
    interpretations = {
        span: box.trim_interpretations(span) for span in (fx.PLATE_LENGTH_MM, fx.PLATE_WIDTH_MM)
    }
    self_check = {
        name: box.classify_trim_semantics(expected, fx.PLATE_WIDTH_MM)["semantics"]
        for name, expected in interpretations[fx.PLATE_WIDTH_MM].items()
    }
    assert all(got == name for name, got in self_check.items()), self_check
    return {
        "probe_wall": "f_px on +x as the first wall (both bend ends at free plate corners)",
        "probe_operations": len(operations),
        "probe_reference": reference["geometry"],
        "interpretations": interpretations,
        "classifier_self_check": self_check,
        "gating": (
            "the trimmed third wall is submitted only when the probe classifies the "
            "semantics as setback_from_ends; any other reading keeps the trim contrast "
            "inconclusive about corner clearance"
        ),
    }


def check_miter_plan() -> dict:
    """FEAT-014 offline: the miter request validates and the plan order is fixed."""
    reference = fx.select_wall_edge(fx.box_inspection(), fx.PLATE_BOUNDS, "+x", face="top")
    miter = {"width": MITER_GAP_MM, "offset": MITER_GAP_MM}
    first = fx.flange_op("+x", "f_px", reference)
    mitered = fx.flange_op("+x", "f_px", reference)
    mitered["miter_cuts"] = miter
    plain = fx.validate_operations([first])[0]
    validated = fx.validate_operations([mitered])[0]
    assert "miter_cuts" not in plain
    assert validated["miter_cuts"] == miter
    assert [label for _, label, _ in MITER_BOX_SEQUENCE] == [
        "f_px",
        "f_nx",
        "f_ny",
        "f_py",
    ]
    assert [use for _, _, use in MITER_BOX_SEQUENCE] == [False, False, True, True]
    return {
        "miter_gap_mm": MITER_GAP_MM,
        "request": miter,
        "box_sequence": [
            {"side": side, "label": label, "miter_cuts": miter if use else None}
            for side, label, use in MITER_BOX_SEQUENCE
        ],
        "validated": validated["miter_cuts"],
        "validated_without_miter": "miter_cuts" not in plain,
        "gating": (
            "run_miter_probe classifies the literal width/offset semantics from two "
            "measured free walls before run_miter_box is judged; four_walls_complete needs "
            "all four walls to succeed with saved_file_reloaded_and_verified=true"
        ),
    }


def check_admission() -> dict:
    plans = box.group_plans_validate()
    probe, _ = box.trim_probe_plan()
    return {
        "groups": plans,
        "probe_plan_last_operation": probe[-1],
        "statement": (
            "every group's base plan and per-wall request, plus the trimmed probe plan, "
            "pass validate_operations with the shared contract"
        ),
    }


def check_native_trim_branch() -> dict:
    guard = box.native_source()
    return {
        **guard,
        "statement": (
            "end_trim_mm switches both flange depth sides from TO_END to blind with the "
            "requested offset and nothing else; calls without the field keep the stock "
            "TO_END tree byte-for-byte; the failing paths record bounded forensics"
        ),
    }


def check_live_probe_plan() -> dict:
    groups = box.LIVE_PROBE_GROUPS
    gradient = {
        "ny_first": "zero adjacent bend ends on the full free -y edge",
        "px_then_ny": "exactly one -y edge end adjacent to the f_px bend",
        "px_nx_then_ny": "both -y edge ends adjacent to the f_px/f_nx bends",
    }
    for group in ("ny_first", "px_then_ny", "px_nx_then_ny"):
        assert group in groups, group
    assert groups["trim_probe"]["verdict"] == "volume_classification"
    return {
        "groups": groups,
        "trigger_gradient": gradient,
        "proven_trigger": (
            "2026-10-30 live contrast: a wall whose attachment edge ends adjacent to an "
            "existing bend fails even when only one end touches; the full free edge builds"
        ),
        "rules": [
            "one fresh model per group (two for the trim probe), unique lowercase name",
            "one job per wall; the edge is re-selected from a fresh inspection with an "
            "explicit face against the plate bounds frozen from the base snapshot "
            "(never the post-flange body bbox) before every submission",
            "assert the measured edge span before submitting; never resubmit an accepted "
            "job; a job that is not terminal within 180 s stops everything",
            "the trim probe runs first; the trimmed third wall of the offline trimmed_20 "
            "design is only runnable after the probe confirms setback_from_ends",
        ],
        "capability_claim": {
            "four_walls_complete": False,
            "statement": (
                "this live entry is a diagnostic; the proven trigger condition is enforced "
                "by the N06 native pre-check, which rejects a wall whose edge end abuts an "
                "existing bend before create (failure_reason=adjacent_bend_ends) unless the "
                "request carries miter_cuts. That rejection is still the expected boundary "
                "outcome without miter (adjacent_bend_ends_rejected); trigger_reproduced is "
                "reserved for an unmarked regeneration failure. The FEAT-014 miter route is "
                "implemented and only reported complete by a passing miter_box group"
            ),
        },
    }


def check_failure_forensics_contract() -> dict:
    guard = box.native_source()["failure_forensics_assertions"]
    synthetic = box.wall_outcome(
        {
            "terminal_status": "failed",
            "edge_span_mm": 177.92,
            "revision_after": 3,
            "volume_after_mm3": 80_040.0,
        }
    )
    assert synthetic == "failed", synthetic
    unknown = box.wall_outcome({"terminal_status": "succeeded", "volume_after_mm3": None})
    assert unknown == "unknown", unknown
    return {
        "native_forensics_assertions": guard,
        "driver_fields": {
            "flange_failure_evidence": (
                "staged into the failed operation record by the native forensics under "
                "operations[].flange_failure_evidence (N06 propagation fix: the block is "
                "nested, never flattened): stage (before_create for pre-check rejections "
                "or after_regenerate for unhealthy features), failure_reason "
                "(adjacent_bend_ends on pre-check rejections), feature_status(_name), "
                "feature_id, geometry_visit_code, geometry_item_count, edge_forensics "
                "{id, length_mm, end0_mm, end1_mm, neighbors_code, "
                "adjacent_faces[{id,smt_type,type_code}], adjacent_edges[{id,id_code}]}, "
                "adjacency ends[{end, point_mm, neighbor_edge_id, neighbor_arc, "
                "neighbor_radius_mm, radius_bound_mm, bend_face_ids, "
                "adjacent_bend_end}], section_leg_sketch; every query failure is null, "
                "never guessed"
            ),
            "stage_feature_state": (
                "the failing wall's status/geometry from the native log's "
                "UNHEALTHY_FEATURES dump (third_wall_stage_record); the log tail now "
                "covers the full dump (10841-char row in the 2026-10-31 rerun)"
            ),
            "rollback": "revision and volume before/after from the post-failure snapshot",
            "trim_classification": (
                "trim_probe_verdict names the semantics from the measured increments; "
                "unconfirmed classifications never feed a corner attribution"
            ),
        },
        "semantics_for_n06": (
            "edge_forensics.end0_mm/end1_mm are the attachment edge's measured end "
            "points; adjacent_faces carries Creo's sheetmetal typing of the two faces "
            "sharing the edge; feature_status 6 = PRO_FEAT_UNREGENERATED (created but "
            "not regenerated); geometry_item_count 0 with status 6 is the round-six "
            "shape. A pre-check rejection (failure_reason=adjacent_bend_ends, "
            "stage=before_create) carries the per-end adjacency evidence instead: no "
            "feature exists, so there is no feature status. All of it is evidence, "
            "not a corner rule."
        ),
        "synthetic_check": {"failed_wall": synthetic, "unknown_measurement": unknown},
    }


def check_contract() -> dict:
    return box.contract_source()


def check_stage_record_contract() -> dict:
    """Exercise the stage-record helpers on the round-six synthetic line.

    This is a fixture self-check, not a live result: it proves the live driver
    can recognise the round-six failure shape and will record deviations as new
    evidence instead of forcing them into the old shape.
    """
    unhealthy_line = (
        'UNHEALTHY_FEATURES=[{"id":9,"type":17,"type_name":"WALL","status":6,'
        '"incomplete":false,"name":"f_ny","dimensions":[],"geometry_items":[],'
        '"parent_ids":[],"child_ids":[]}]'
    )
    snapshot = {"revision": 3, "inspection": {"volume_mm3": 80_040.0}}
    stage = box.third_wall_stage_record(
        "f_ny",
        "job-synthetic",
        {
            "status": "failed",
            "message": "Regeneration produced a failed, suppressed or incomplete feature",
        },
        unhealthy_line,
        3,
        80_040.0,
        snapshot,
    )
    verdict = box.failed_wall_verdict(stage, "f_ny")
    assert verdict["matches_round_six_shape"], verdict
    deviation = box.failed_wall_verdict(
        box.third_wall_stage_record(
            "f_ny",
            "job-synthetic",
            {"status": "failed", "message": "other"},
            None,
            3,
            80_040.0,
            snapshot,
        ),
        "f_ny",
    )
    assert not deviation["matches_round_six_shape"]
    return {
        "stages": [
            "stage_submission",
            "stage_terminal",
            "stage_feature_state (from the native log's UNHEALTHY_FEATURES dump)",
            "stage_health_check",
            "stage_rollback (revision and volume restored)",
        ],
        "round_six_shape_recognised": True,
        "deviation_recorded_not_forced": True,
        "statement": (
            "the live run fills each stage from observation; a failing wall that does not "
            "match the round-six shape is recorded as a new observation"
        ),
        "synthetic_only": True,
    }


def check_corner_decision_table() -> dict:
    reachable = {
        "incomplete_run": box.corner_decision({"full_length": "third_failed"})["conclusion"],
        "not_reproduced": box.corner_decision(
            {
                "full_length": "third_succeeded",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            }
        )["conclusion"],
        "zero_corner_failure_refutes_corners": box.corner_decision(
            {
                "full_length": "third_failed",
                "order_ny_first": "third_failed",
                "order_ny_second": "third_succeeded",
            }
        )["conclusion"],
        "trim_builds_but_semantics_unconfirmed": box.corner_decision(
            {
                "full_length": "third_failed",
                "trimmed_20": "third_succeeded",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            },
            trim_semantics="unresolved",
        )["conclusion"],
        "corner_interference_supported": box.corner_decision(
            {
                "full_length": "third_failed",
                "trimmed_20": "third_succeeded",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            },
            trim_semantics="setback_from_ends",
        )["conclusion"],
        "trimmed_wall_also_fails_refutes_corners": box.corner_decision(
            {
                "full_length": "third_failed",
                "trimmed_20": "third_failed",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            },
            trim_semantics="setback_from_ends",
        )["conclusion"],
    }
    return {
        "reachable_conclusions": reachable,
        "corner_interference_now": "candidate_only_no_contrast_run",
        "statement": (
            "offline, no observation exists, so the standing conclusion is "
            "undetermined_incomplete; corner interference becomes supported only when the "
            "trim contrast and the order gradient agree with the setback semantics confirmed"
        ),
    }


def check_round_six_evidence() -> dict:
    report = ROOT / "build" / "sheetmetal_relief" / "20261029T222754_44e6ab6a" / "report.json"
    return {
        **box.ROUND_SIX,
        "report_present": report.exists(),
        "statement": (
            "round six is the starting observation (status=6, empty geometry, rollback); it "
            "is a candidate shape, not a cause, and this run does not resubmit anything"
        ),
    }


# --- formal live probes (DEV-052 N05) ----------------------------------------


def native_failure_evidence(terminal: dict) -> dict | None:
    """The native forensics block from the failed operation record, if any."""
    result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
    for operation in result.get("operations") or []:
        if isinstance(operation, dict) and operation.get("flange_failure_evidence"):
            return operation["flange_failure_evidence"]
    return None


def read_native_log(job_id: str | None, limit: int = 65_536) -> str | None:
    """A bounded tail of the job's native log, for the UNHEALTHY_FEATURES dump.

    The 2026-10-31 rerun: the failing job's UNHEALTHY_FEATURES line is one
    10841-char JSON row starting about 16.6k chars before EOF, so the old
    6000-char tail cut the line prefix off and stage_feature_state reported
    line_found=false even though the dump was there. 64 KiB keeps the whole
    dump and the staged evidence reachable while staying bounded.
    """
    if not job_id:
        return None
    path = ROOT / "jobs" / job_id / "native.log"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError:
        return None


def bbox_of(snapshot: dict) -> list | None:
    inspection = LiveRunner.inspection(snapshot)
    if not inspection:
        return None
    try:
        low, high = fx.active_bbox(inspection)
        return [list(low), list(high)]
    except (ValueError, KeyError, IndexError):
        return None


async def build_base(runner: LiveRunner, case_name: str) -> tuple[dict, dict | None]:
    """One fresh base wall per case; nothing else runs when the base fails."""
    model_name = unique_name(f"n05_{case_name[:24]}")
    created = await runner.submit(
        f"{case_name}:base",
        "creo_execute_plan",
        {
            "model_name": model_name,
            "model_type": "sheetmetal",
            "operations": [fx.wall_sketch(), fx.wall_base_op()],
        },
    )
    model_id = created["model_id"]
    terminal = await runner.wait_job(created["job_id"], budget=box.HANG_BUDGET_SECONDS)
    entry = {
        "model_name": model_name,
        "model_id": model_id,
        "base_job_id": created["job_id"],
        "base_status": terminal.get("status"),
        "base_revision": terminal.get("revision"),
    }
    if terminal.get("status") != "succeeded":
        entry.update(failure=failure_text(terminal), passed=False)
        return runner.case(entry), None
    snapshot = await runner.snapshot(model_id)
    entry.update(
        base_revision_after=snapshot.get("revision"),
        base_volume_mm3=LiveRunner.volume(snapshot),
        base_inspection_present=bool(LiveRunner.inspection(snapshot)),
    )
    return entry, snapshot


async def submit_wall(
    runner: LiveRunner,
    case_name: str,
    model_id: str,
    side: str,
    label: str,
    plate_bounds: tuple,
    end_trim_mm: float | None = None,
    miter_cuts: dict | None = None,
) -> tuple[dict, dict, dict]:
    """One wall, one job: fresh inspection for the edge, submit, wait, snapshot.

    plate_bounds is the plate slab frozen from the base snapshot before any
    flange; the fresh inspection only supplies the candidate edges and the
    revision. The 2026-10-30 live run classified "top" against the post-flange
    body bbox instead, submitted the 1 mm wall-end rim edge for f_ny
    (PRO_TK_BAD_CONTEXT) and found no -x top edge at all -- both driver
    defects this signature rules out.
    """
    snapshot = await runner.snapshot(model_id)
    inspection = LiveRunner.inspection(snapshot)
    reference = fx.select_wall_edge(
        inspection, plate_bounds, side, face="top", allow_shortened=True
    )
    request = {
        "model_id": model_id,
        "expected_revision": snapshot.get("revision"),
        "label": label,
        "edge": dict(reference["edge"]),
        "height": fx.FLANGE_HEIGHT_MM,
        "angle": fx.FLANGE_ANGLE_DEG,
        "radius": fx.FLANGE_RADIUS_MM,
        "flip": False,
        "y_factor": fx.FLANGE_Y_FACTOR,
    }
    if end_trim_mm is not None:
        request["end_trim_mm"] = end_trim_mm
    if miter_cuts is not None:
        request["miter_cuts"] = miter_cuts
    submitted = await runner.submit(f"{case_name}:{label}", "creo_sheetmetal_flange", request)
    terminal = await runner.wait_job(submitted["job_id"], budget=box.HANG_BUDGET_SECONDS)
    after = await runner.snapshot(model_id)
    return reference, terminal, after


def wall_record(
    label: str,
    side: str,
    reference: dict,
    terminal: dict,
    after: dict,
    revision_before: int | None,
    volume_before: float | None,
    log_text: str | None,
) -> dict:
    """Everything the verdict needs for one wall, measured before judged."""
    result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
    job_id = terminal.get("job_id", terminal.get("id"))
    record = {
        "label": label,
        "side": side,
        "edge": reference["geometry"],
        "edge_span_mm": reference["geometry"].get("span_mm"),
        "terminal_status": terminal.get("status"),
        "job_id": job_id,
        "revision_before": revision_before,
        "revision_after": after.get("revision"),
        "volume_before_mm3": volume_before,
        "volume_after_mm3": LiveRunner.volume(after),
        "bbox_after_mm": bbox_of(after),
        "saved_file_reloaded_and_verified": result.get("saved_file_reloaded_and_verified"),
        "native_failure_evidence": native_failure_evidence(terminal),
        "flange_echo": LiveRunner.record(after, label) or None,
    }
    if terminal.get("status") == "failed":
        record.update(
            failure=failure_text(terminal),
            stage_record=box.third_wall_stage_record(
                label,
                job_id,
                terminal,
                log_text,
                revision_before,
                volume_before,
                {
                    "revision": after.get("revision"),
                    "inspection": {"volume_mm3": LiveRunner.volume(after)},
                },
            ),
        )
    return record


async def run_trim_probe(runner: LiveRunner) -> dict:
    """No trim vs a positive trim on free first walls; classify the semantics."""
    full_case = await build_base(runner, "trim_full")
    verdict = {"group": "trim_probe", "passed": False, "four_walls_complete": False}
    if full_case[1] is None:
        verdict.update(full={"not_executed": "the full base wall did not succeed"})
        return runner.case(verdict)
    full_base = full_case[0]
    full_bounds = fx.active_bbox(LiveRunner.inspection(full_case[1]))
    full_ref, full_terminal, full_after = await submit_wall(
        runner, "trim_full", full_base["model_id"], "+x", "f_px", full_bounds
    )
    full_added = (
        LiveRunner.volume(full_after) - full_base["base_volume_mm3"]
        if LiveRunner.volume(full_after) is not None
        and full_base.get("base_volume_mm3") is not None
        else None
    )
    full_entry = {
        "wall": "f_px_full",
        **wall_record(
            "f_px",
            "+x",
            full_ref,
            full_terminal,
            full_after,
            full_base.get("base_revision_after"),
            full_base.get("base_volume_mm3"),
            None,
        ),
        "added_mm3": full_added,
    }
    trimmed_case = await build_base(runner, "trim_trimmed")
    if trimmed_case[1] is None:
        verdict.update(full=full_entry, trimmed={"not_executed": "the trimmed base failed"})
        return runner.case(verdict)
    trimmed_base = trimmed_case[0]
    trimmed_bounds = fx.active_bbox(LiveRunner.inspection(trimmed_case[1]))
    trimmed_ref, trimmed_terminal, trimmed_after = await submit_wall(
        runner,
        "trim_trimmed",
        trimmed_base["model_id"],
        "+x",
        "f_px",
        trimmed_bounds,
        end_trim_mm=box.TRIM_MM,
    )
    trimmed_added = (
        LiveRunner.volume(trimmed_after) - trimmed_base["base_volume_mm3"]
        if LiveRunner.volume(trimmed_after) is not None
        and trimmed_base.get("base_volume_mm3") is not None
        else None
    )
    trimmed_entry = {
        "wall": "f_px_trimmed",
        "end_trim_mm": box.TRIM_MM,
        **wall_record(
            "f_px",
            "+x",
            trimmed_ref,
            trimmed_terminal,
            trimmed_after,
            trimmed_base.get("base_revision_after"),
            trimmed_base.get("base_volume_mm3"),
            None,
        ),
        "added_mm3": trimmed_added,
    }
    verdict.update(
        full=full_entry,
        trimmed=trimmed_entry,
        **box.trim_probe_verdict(
            {"added_mm3": full_added, "edge_span_mm": full_entry["edge_span_mm"]},
            {"added_mm3": trimmed_added, "edge_span_mm": trimmed_entry["edge_span_mm"]},
        ),
    )
    return runner.case(verdict)


WALL_SEQUENCES = {
    "ny_first": [("-y", "f_ny")],
    "px_then_ny": [("+x", "f_px"), ("-y", "f_ny")],
    "px_nx_then_ny": [("+x", "f_px"), ("-x", "f_nx"), ("-y", "f_ny")],
}


async def run_wall_group(runner: LiveRunner, group: str) -> dict:
    """One probe group: fresh model, one job per wall, fresh edge per wall."""
    base_entry, snapshot = await build_base(runner, group)
    verdict = {"group": group, "four_walls_complete": False}
    if snapshot is None:
        verdict.update(walls=[], group_verdict=box.probe_group_verdict(group, {}))
        return runner.case(verdict)
    revision = snapshot.get("revision")
    volume = LiveRunner.volume(snapshot)
    plate_bounds = fx.active_bbox(LiveRunner.inspection(snapshot))
    records = []
    for side, label in WALL_SEQUENCES[group]:
        try:
            reference, terminal, after = await submit_wall(
                runner, group, base_entry["model_id"], side, label, plate_bounds
            )
        except fx.EdgeSelectionError as error:
            # The 2026-10-30 run died on this unhandled error. An ambiguous or
            # unqualified selection is a driver defect: record it, keep it out
            # of the Creo verdicts and stop this group.
            records.append(
                {
                    "label": label,
                    "side": side,
                    "outcome": "driver_edge_selection_error",
                    "terminal_status": None,
                    "error": f"EdgeSelectionError: {error}",
                    "note": (
                        "probe selection defect, recorded as a driver failure; never "
                        "a Creo failure and never a trigger reproduction"
                    ),
                }
            )
            break
        log_text = read_native_log(terminal.get("job_id", terminal.get("id")))
        record = wall_record(label, side, reference, terminal, after, revision, volume, log_text)
        record["outcome"] = box.wall_outcome(record)
        if record["outcome"] == "failed" and box.driver_selection_error(record):
            # A failed wall on a thickness-scale rim edge is the selector's
            # defect (2026-10-30), never a trigger reproduction.
            record["outcome"] = "driver_edge_selection_error"
        elif record["outcome"] == "failed" and box.adjacency_rejection(record):
            # DEV-052 N06: the native adjacent-bend-ends pre-check refused the
            # wall before any feature was created. The trigger condition is
            # proven (2026-10-30/31), so this explicit rejection is the known
            # boundary working as designed -- not a trigger reproduction.
            record["outcome"] = "adjacent_bend_ends_rejected"
        records.append(record)
        if terminal.get("status") == "succeeded":
            revision = record["revision_after"]
            volume = record["volume_after_mm3"]
    outcomes = {record["label"]: record["outcome"] for record in records}
    group_verdict = box.probe_group_verdict(group, outcomes)
    verdict.update(
        base=base_entry,
        walls=records,
        group_verdict=group_verdict,
        outcome=group_verdict["outcome"],
        passed=group_verdict["passed"],
        failed_walls=group_verdict["failed_walls"],
    )
    return runner.case(verdict)


MITER_GAP_MM = fx.PLATE_THICKNESS_MM

#: FEAT-014: the four-wall order the 2026-11-06 evidence left blocked. The first
#: two walls attach to free edges; the third and fourth abut existing bends, so
#: they carry the explicit miter request. One job per wall, fresh edge each time.
MITER_BOX_SEQUENCE = (
    ("+x", "f_px", False),
    ("-x", "f_nx", False),
    ("-y", "f_ny", True),
    ("+y", "f_py", True),
)


async def run_miter_probe(runner: LiveRunner) -> dict:
    """GAP semantics probe first: the same free wall with and without miter_cuts.

    The end_trim_mm lesson (a requested value the kernel ignored) is why the
    miter section is never trusted from the request echo: two fresh models, one
    free +x wall each, and the added-volume difference classifies whether the
    gap changes the built geometry at all.
    """
    verdict = {
        "group": "miter_probe",
        "miter_gap_mm": MITER_GAP_MM,
        "passed": False,
        "four_walls_complete": False,
    }
    plain_case = await build_base(runner, "miter_plain")
    if plain_case[1] is None:
        verdict.update(plain={"not_executed": "the plain base wall did not succeed"})
        return runner.case(verdict)
    plain_base = plain_case[0]
    plain_bounds = fx.active_bbox(LiveRunner.inspection(plain_case[1]))
    plain_ref, plain_terminal, plain_after = await submit_wall(
        runner, "miter_plain", plain_base["model_id"], "+x", "f_px", plain_bounds
    )
    plain_added = (
        LiveRunner.volume(plain_after) - plain_base["base_volume_mm3"]
        if LiveRunner.volume(plain_after) is not None
        and plain_base.get("base_volume_mm3") is not None
        else None
    )
    plain_entry = {
        "wall": "f_px_plain",
        **wall_record(
            "f_px",
            "+x",
            plain_ref,
            plain_terminal,
            plain_after,
            plain_base.get("base_revision_after"),
            plain_base.get("base_volume_mm3"),
            None,
        ),
        "added_mm3": plain_added,
    }
    gap_case = await build_base(runner, "miter_gap")
    if gap_case[1] is None:
        verdict.update(plain=plain_entry, gap={"not_executed": "the miter base failed"})
        return runner.case(verdict)
    gap_base = gap_case[0]
    gap_bounds = fx.active_bbox(LiveRunner.inspection(gap_case[1]))
    miter = {"width": MITER_GAP_MM, "offset": MITER_GAP_MM}
    gap_ref, gap_terminal, gap_after = await submit_wall(
        runner,
        "miter_gap",
        gap_base["model_id"],
        "+x",
        "f_px",
        gap_bounds,
        miter_cuts=miter,
    )
    gap_added = (
        LiveRunner.volume(gap_after) - gap_base["base_volume_mm3"]
        if LiveRunner.volume(gap_after) is not None and gap_base.get("base_volume_mm3") is not None
        else None
    )
    gap_entry = {
        "wall": "f_px_miter",
        "miter_cuts": miter,
        **wall_record(
            "f_px",
            "+x",
            gap_ref,
            gap_terminal,
            gap_after,
            gap_base.get("base_revision_after"),
            gap_base.get("base_volume_mm3"),
            None,
        ),
        "added_mm3": gap_added,
    }
    delta = gap_added - plain_added if gap_added is not None and plain_added is not None else None
    if delta is None:
        classification = "unmeasured"
    elif abs(delta) <= 0.5:
        classification = "no_measurable_cut"
    else:
        classification = "gap_measured"
    verdict.update(
        plain=plain_entry,
        gap=gap_entry,
        gap_minus_plain_mm3=delta,
        classification=classification,
        statement=(
            "the request echo only proves the element tree accepted the literal BLIND "
            "section; whether width/offset cut the built wall is classified from the "
            "measured added-volume difference, never assumed. The 2026-11-06 live probe "
            "measured no change on a free wall, where there is no overlap to cut"
        ),
        passed=(
            plain_terminal.get("status") == "succeeded"
            and gap_terminal.get("status") == "succeeded"
            and delta is not None
        ),
    )
    return runner.case(verdict)


async def run_miter_box(runner: LiveRunner) -> dict:
    """The four-wall box through the FEAT-014 miter route (one job per wall).

    Unlike the earlier groups, this one can report four_walls_complete=true, but
    only when every wall succeeded, every required measurement is present and
    every wall reports saved_file_reloaded_and_verified=true.
    """
    base_entry, snapshot = await build_base(runner, "miter_box")
    verdict = {"group": "miter_box", "four_walls_complete": False, "passed": False}
    if snapshot is None:
        verdict.update(walls=[], statement="the base wall did not succeed")
        return runner.case(verdict)
    revision = snapshot.get("revision")
    volume = LiveRunner.volume(snapshot)
    plate_bounds = fx.active_bbox(LiveRunner.inspection(snapshot))
    miter = {"width": MITER_GAP_MM, "offset": MITER_GAP_MM}
    records = []
    for side, label, use_miter in MITER_BOX_SEQUENCE:
        try:
            reference, terminal, after = await submit_wall(
                runner,
                "miter_box",
                base_entry["model_id"],
                side,
                label,
                plate_bounds,
                miter_cuts=miter if use_miter else None,
            )
        except fx.EdgeSelectionError as error:
            records.append(
                {
                    "label": label,
                    "side": side,
                    "outcome": "driver_edge_selection_error",
                    "terminal_status": None,
                    "error": f"EdgeSelectionError: {error}",
                    "note": "probe selection defect, recorded as a driver failure",
                }
            )
            break
        record = wall_record(
            label,
            side,
            reference,
            terminal,
            after,
            revision,
            volume,
            read_native_log(terminal.get("job_id", terminal.get("id"))),
        )
        record["outcome"] = box.wall_outcome(record)
        if record["outcome"] == "failed" and box.driver_selection_error(record):
            record["outcome"] = "driver_edge_selection_error"
        elif record["outcome"] == "failed" and box.adjacency_rejection(record):
            record["outcome"] = "adjacent_bend_ends_rejected"
        record["miter_requested"] = use_miter
        records.append(record)
        if terminal.get("status") == "succeeded":
            revision = record["revision_after"]
            volume = record["volume_after_mm3"]
    complete = len(records) == len(MITER_BOX_SEQUENCE) and all(
        record["outcome"] == "succeeded" and record.get("saved_file_reloaded_and_verified") is True
        for record in records
    )
    verdict.update(
        base=base_entry,
        miter_cuts=miter,
        walls=records,
        four_walls_complete=complete,
        passed=complete,
        statement=(
            "four walls count only when all four succeeded with measurements and "
            "saved_file_reloaded_and_verified=true on every wall"
        ),
    )
    return runner.case(verdict)


async def live_box(output: Path, run_id: str) -> int:
    """The formal live entry: dual-switch gated, serial, diagnostic only."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=240) as client:
        runner = LiveRunner(
            client,
            output,
            "FEAT-014 / BUG-047 / DEV-052 N05/N06",
            (
                "formal third-wall probes: the proven trigger gradient (ny_first / "
                "px_then_ny / px_nx_then_ny) plus the end_trim_mm measurement; every "
                "wall keeps its real status and four_walls_complete stays false; since "
                "N06 a wall whose edge end abuts an existing bend is explicitly rejected "
                "before create (failure_reason=adjacent_bend_ends) and that rejection is "
                "the expected boundary outcome"
            ),
            run_id,
        )
        runner.report["hang_budget_seconds"] = box.HANG_BUDGET_SECONDS
        runner.report["capability_claim"] = {
            "four_walls_complete": False,
            "statement": (
                "a diagnostic run: the earlier groups keep their known boundary (a wall "
                "whose edge end is adjacent to an existing bend is rejected before create "
                "unless miter_cuts is supplied); the miter_probe classifies the literal "
                "width/offset semantics from measured volumes and the miter_box is the only "
                "case that may report four_walls_complete=true, and only when every wall "
                "saved, reloaded and verified"
            ),
        }
        try:
            await runner.start()
            await run_trim_probe(runner)
            for group in ("ny_first", "px_then_ny", "px_nx_then_ny"):
                await run_wall_group(runner, group)
            await run_miter_probe(runner)
            await run_miter_box(runner)
        except (LiveStop, BaseException) as error:
            runner.report["stopped"] = f"{type(error).__name__}: {error}"
            runner.finish()
            raise
    miter_box = next(
        (case for case in runner.report["cases"] if case.get("group") == "miter_box"),
        None,
    )
    runner.report["capability_claim"]["four_walls_complete"] = bool(
        miter_box and miter_box.get("four_walls_complete")
    )
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if runner.report["passed"] else 1


def run_live(output: Path, run_id: str) -> int:
    """Entry guard before any MCP client exists; then the formal live probes."""
    try:
        require_manual_start(ROOT / "config.json")
    except (ValueError, OSError) as error:
        print(f"LIVE_REFUSED: {error}", file=sys.stderr)
        return 2
    print(box.LIVE_GATE, file=sys.stderr)
    return asyncio.run(live_box(output, run_id))


def live_checklist() -> list[str]:
    return [
        "confirm the session is usable and BUG-001 conditions hold; one dev service only "
        "(MCP_CREO_MechDog_dev); config.json auto_start_creo must be false",
        "run the formal entry with a unique --output: "
        "tools\\test_sheetmetal_box_live.py --live --confirm-session-usable --output "
        "build/post090_n05_live_<run_id>/report.json",
        "the driver runs the trim probe first (two fresh free first walls, one with "
        "end_trim_mm=20) and then the three groups ny_first / px_then_ny / px_nx_then_ny; "
        "one fresh model per group, one job per wall, edge re-selected from a fresh "
        "inspection with an explicit face against the plate bounds frozen from the "
        "base snapshot; thickness-scale rim edges are never candidates",
        "a selection that is ambiguous, unqualified or rim-scale is recorded as "
        "driver_edge_selection_error (passed=false) and never submitted, never judged "
        "as a Creo failure and never as trigger_reproduced",
        "record per wall: edge span, terminal status, revision and volume before/after, "
        "bbox, saved_file_reloaded_and_verified and the native flange_failure_evidence "
        "block; a failing wall also gets third_wall_stage_record from the UNHEALTHY_FEATURES "
        "dump; never resubmit a failed or accepted job",
        "judge with the driver's verdicts: trim_probe_verdict names the semantics only "
        "from measured increments; probe_group_verdict keeps failed walls listed as "
        "failed and never sets four_walls_complete",
        "a third wall the native pre-check refused (failure_reason=adjacent_bend_ends) "
        "verdicts as adjacent_bend_ends_rejected with passed=true -- the expected known "
        "boundary since 2026-10-31; an unmarked regeneration failure verdicts as "
        "trigger_reproduced with passed=false and needs the native evidence investigated",
        "the trim classification is evidence only: without setback_from_ends confirmed, "
        "the trimmed third wall of the offline design stays unrunnable and nothing feeds "
        "a corner attribution",
        "stop on first unknown/hang (180 s budget per job), keep the scene and hand over",
    ]


def run_unit_module() -> dict:
    from tests.unit import test_sheetmetal_box_live

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_sheetmetal_box_live)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    return {
        "module": "tests.unit.test_sheetmetal_box_live",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "successful": result.wasSuccessful(),
    }


# --- provenance and report ------------------------------------------------


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    """Refuse to overwrite an existing report before anything else runs.

    The formal N05 entry writes under build/post090_n05/<run_id>/ so its reports
    never collide with the historical build/sheetmetal_box/ layout.
    """
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "post090_n05" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
    from version import VERSION

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout.strip()

    names = set(
        git("ls-files", "--", "*.py", "native/*.h", "native/*.hpp", "native/*.cpp").splitlines()
    )
    names.update(
        (
            "tools/test_sheetmetal_box_live.py",
            "tests/unit/test_sheetmetal_box_live.py",
            "tools/test_sheetmetal_flange.py",
            "tests/unit/test_sheetmetal_flange.py",
            "tests/unit/test_sheetmetal_relief.py",
            "tools/sheetmetal_live.py",
        )
    )
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in sorted(names)
    }
    return {
        "version": VERSION,
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "dirty": bool(git("status", "--porcelain")),
        "source_sha256": hashes,
        "source_fingerprint": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "auto_start_creo": False,
        "human_session_confirmation": True,
    }


def write_offline_report(output: Path, run_id: str, results: dict) -> dict:
    report = {
        "task": "FEAT-014 / BUG-047 / DEV-052 N05",
        "scope": (
            "formal third-wall probes: the frozen T05 contrast design, the end_trim_mm "
            "contract, the formal live entry (proven trigger gradient plus the trim "
            "measurement), the failing-wall stage record, the native failure forensics "
            "guards and the regression locks"
        ),
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "status": {
            "reproduction": "not_run_offline",
            "root_cause": "undetermined",
            "corner_interference": "candidate_only_no_contrast_run",
            "trigger_condition": (
                "proven 2026-10-30: an attachment-edge end adjacent to an existing bend "
                "fails the wall even when only one end touches; the full free edge builds"
            ),
            "production_change": (
                "end_trim_mm: opt-in blind depth on both flange sides (advanced.cpp, "
                "schema.py, server.py); the stock tree is unchanged without the field; "
                "N05 adds bounded native failure forensics on the failing paths only; "
                "N06 adds the adjacent-bend-ends pre-check, which explicitly rejects a "
                "wall whose attachment-edge end abuts an existing bend before create "
                "(failure_reason=adjacent_bend_ends); FEAT-014 adds the opt-in "
                "miter_cuts request (PRO_E_SMT_MTR_CUTS GAP) as the only release of that "
                "guard; free-edge behaviour is unchanged"
            ),
            "statement": (
                "Offline only: the designs, contracts, verdict locks and forensics guards "
                "are frozen and the executor builds. No Toolkit connection, no wall "
                "created, no failure reproduced here; the formal live entry is gated on "
                "--live --confirm-session-usable and never run by this task."
            ),
        },
        "fixture": {
            "base_wall_mm": [fx.PLATE_LENGTH_MM, fx.PLATE_WIDTH_MM, fx.PLATE_THICKNESS_MM],
            "base_volume_mm3": fx.PLATE_VOLUME_MM3,
            "flange": {
                "height": fx.FLANGE_HEIGHT_MM,
                "radius": fx.FLANGE_RADIUS_MM,
                "y_factor": fx.FLANGE_Y_FACTOR,
                "angle": fx.FLANGE_ANGLE_DEG,
                "flip": False,
            },
            "trim_mm": box.TRIM_MM,
            "hang_budget_seconds": box.HANG_BUDGET_SECONDS,
        },
        "checks": results,
        "live_checklist": live_checklist(),
        "not_verified": [
            "no wall was created in this run; the trim measurement and the three probe "
            "groups are unrun here",
            "the trimmed third wall of the offline design stays gated on the measured "
            "setback classification",
            "the miter_probe and miter_box live cases are unrun here; the GAP width/"
            "offset semantics stay unmeasured, so no cut amount is claimed",
            "four-wall capability remains open until the miter_box run reports every wall "
            "succeeded with saved_file_reloaded_and_verified=true",
            "the native forensics fields are compile-verified only; their live values "
            "are unmeasured until the assigned live run",
        ],
        "unit_module": run_unit_module(),
        "provenance": local_provenance(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


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
        return run_live(output, run_id)

    results = {
        "contrast_design": check_contrast_design(),
        "oracle_rows": check_oracle_rows(),
        "trim_probe": check_trim_probe(),
        "miter_plan": check_miter_plan(),
        "admission": check_admission(),
        "native_trim_branch": check_native_trim_branch(),
        "contract": check_contract(),
        "stage_record_contract": check_stage_record_contract(),
        "corner_decision_table": check_corner_decision_table(),
        "round_six_evidence": check_round_six_evidence(),
        "live_probe_plan": check_live_probe_plan(),
        "failure_forensics_contract": check_failure_forensics_contract(),
    }
    report = write_offline_report(output, run_id, results)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name("report.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"report_sha256: {digest}")
    print(f"status: {report['status']['reproduction']} / {report['status']['root_cause']}")
    print(f"unit_module: {report['unit_module']}")
    return 0 if report["unit_module"]["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
