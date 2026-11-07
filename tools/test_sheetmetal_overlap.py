"""DEV-051 T04 offline driver for BUG-046: overlapping solid add on sheetmetal.

Three-way comparison on the confirmed thin base plate 185 x 232 x 1 mm: a
solid-part add, a sheetmetal add and a sheetmetal cut share one rectangle, one
spatial position and one overlap volume (100 mm3), so only the base model kind
and the extrude mode vary. The fixture, the negative contracts and the
original bare -1 evidence come from tests.unit.test_sheetmetal_overlap (one
source for driver and unit tests).

The native source guard only audits the static facts of the single protrusion
path (target body, parent reference, feature type/elements) and proves the
committed contracts are present in the working tree. It is not native
verification and it does not determine the root cause: the add/cut asymmetries
can only be isolated against a live Creo session.

Default is strictly offline: no MCP client is instantiated and no Toolkit
connection is made. --live --confirm-session-usable runs the three routes on the
manually opened session: each route builds its base in one job, records the
measured volume, submits the same overlap prism in a second job and records the
measured delta and the native feature types; the negative case then proves a
rejected plan leaves volume and revision untouched. It never launches, restarts
or closes Creo, never injects a fault, never clears a protection and never
resubmits a job. A route blocked by a failed base is recorded as blocked and the
routes that depend on the same base are not submitted again.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
import unittest
import uuid
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402
from creo_mechdog.sheetmetal import SOLID_ADD_UNSUPPORTED  # noqa: E402
from tests.unit import test_sheetmetal_overlap as fx  # noqa: E402

ROOT = SOURCE_PATHS.resource_root

from tools.sheetmetal_live import (  # noqa: E402
    LiveRunner,
    LiveStop,
    failure_text,
    require_manual_start,
    unique_name,
)
from tools.sheetmetal_live import (
    new_run_id as live_run_id,
)
from tools.sheetmetal_live import (
    resolve_output as live_output,
)

# --- checks ---------------------------------------------------------------


def check_three_way_contract() -> list[dict]:
    from creo_mechdog.schema import validate_operations

    routes = (
        ("solid_add", "part", fx.route_solid_add(), fx.ROUTE_ADD_VOLUME_MM3),
        ("sheetmetal_add", "sheetmetal", fx.route_sheetmetal_add(), fx.ROUTE_ADD_VOLUME_MM3),
        ("sheetmetal_cut", "sheetmetal", fx.route_sheetmetal_cut(), fx.ROUTE_CUT_VOLUME_MM3),
    )
    rows = []
    for name, model_kind, ops, expected_volume in routes:
        validated = validate_operations(ops)
        prism = validated[-1]
        assert prism["sketch"] == ops[-1]["sketch"], prism
        assert prism["depth"] == fx.PRISM_HALF_DEPTH_MM, prism
        assert prism["direction"] == "symmetric", prism
        assert prism["mode"] == ops[-1]["mode"], prism
        footprint = ops[-2]["entities"][0]
        rows.append(
            {
                "route": name,
                "base_model_kind": model_kind,
                "mode": prism["mode"],
                "validated_operations": validated,
                "shared_input": {
                    "rectangle_min": footprint["min"],
                    "rectangle_max": footprint["max"],
                    "prism_plane": "XY",
                    "prism_depth_mm": fx.PRISM_HALF_DEPTH_MM,
                    "prism_direction": "symmetric",
                    "note": (
                        "same 10 x 10 x 5 block and the same 100 mm3 overlap; the sheetmetal "
                        "routes move the footprint into the XZ wall base band y=-232..0"
                    ),
                },
                "oracle": {
                    "base_volume_mm3": fx.BASE_VOLUME_MM3,
                    "prism_volume_mm3": fx.prism_volume_mm3(),
                    "overlap_volume_mm3": fx.overlap_volume_mm3(),
                    "expected_result_volume_mm3": expected_volume,
                },
                "native_result": "not_measured_offline",
            }
        )
    return rows


def check_shared_geometry() -> dict:
    placements = []
    block = (-fx.PRISM_HALF_DEPTH_MM, fx.PRISM_HALF_DEPTH_MM)
    for low in (-1.0, -0.5, 0.0, 0.7):
        plate = (low, low + fx.BASE_THICKNESS_MM)
        crossed = max(0.0, min(plate[1], block[1]) - max(plate[0], block[0]))
        assert abs(crossed - fx.BASE_THICKNESS_MM) < 1e-9, (plate, crossed)
        placements.append(
            {
                "plate_z_interval_mm": list(plate),
                "crossed_thickness_mm": crossed,
                "overlap_volume_mm3": fx.PRISM_SIDE_MM * fx.PRISM_SIDE_MM * crossed,
            }
        )
    for lo in fx.OVERLAP_MIN:
        assert lo >= 0.0
    assert fx.OVERLAP_MAX[0] <= fx.BASE_LENGTH_MM
    assert fx.OVERLAP_MAX[1] <= fx.BASE_WIDTH_MM
    return {
        "footprint_inside_plate": True,
        "overlap_invariant_across_plate_z_placements": placements,
        "note": (
            "The straddling block spans any 1 mm plate placement near the sketch plane, "
            "so the overlap stays 100 mm3 while the first-wall Z sign is still an "
            "unverified live item (DEV-051 T03 card)."
        ),
    }


def check_negative_contracts() -> dict:
    from creo_mechdog.schema import validate_operations

    cases = []

    def rejected(name, operations, reason):
        try:
            validate_operations(operations)
        except ValueError as error:
            message = str(error)
            assert reason in message, (name, message)
            cases.append({"case": name, "rejected": True, "message": message})
        else:
            raise AssertionError(f"{name} was accepted")

    broken = fx.overlap_sketch()
    broken["entities"][0]["max"] = list(fx.OVERLAP_MIN)
    rejected(
        "through_all_add",
        [fx.overlap_sketch(), fx.prism_op("add", "boss_add", depth_type="through_all")],
        "through_all is supported for cuts",
    )
    rejected(
        "through_all_surface",
        [fx.overlap_sketch(), fx.prism_op("surface", "surf_extrude", depth_type="through_all")],
        "through_all is supported for cuts",
    )
    rejected(
        "degenerate_overlap_rectangle",
        [broken, fx.prism_op("add", "boss_add")],
        "Rectangle max must exceed min",
    )
    rejected(
        "nonpositive_prism_depth",
        [fx.overlap_sketch(), fx.prism_op("add", "boss_add", depth=0.0)],
        "greater than 0",
    )
    for name, operations in (
        ("unknown_mode", [fx.overlap_sketch(), fx.prism_op("weld", "boss_add")]),
        (
            "unknown_direction",
            [fx.overlap_sketch(), fx.prism_op("add", "boss_add", direction="up")],
        ),
    ):
        try:
            validate_operations(operations)
        except ValueError as error:
            cases.append({"case": name, "rejected": True, "message": str(error)})
        else:
            raise AssertionError(f"{name} was accepted")
    return {
        "rejected_before_modelling": cases,
        "model_untouched": "rejected_before_native_modelling",
        "not_a_rejection_rule": (
            "solid add on a sheetmetal model is deliberately NOT pre-rejected here: its "
            "support status is unconfirmed and a rejection would prejudge the live result"
        ),
    }


def check_regression_guards() -> dict:
    from creo_mechdog.schema import validate_operations

    try:
        validate_operations([fx.solid_plate_sketch(), fx.wall_base_op("plate_sketch")])
    except ValueError as error:
        message = str(error)
        assert "exactly one open straight line" in message, message
        closed_rejected = message
    else:
        raise AssertionError("closed rectangle first wall was accepted (T03 contract regressed)")
    validated = validate_operations([fx.wall_sketch(), fx.wall_base_op()])
    assert validated[1]["op"] == "sheetmetal_wall"
    return {
        "t03_first_wall_closed_still_rejected": closed_rejected,
        "t03_first_wall_open_line_still_accepted": True,
        "t02_arc_dir_fields_untouched_by_this_task": True,
    }


def check_original_evidence() -> dict:
    hits = {
        token: fx.archived_reports_containing(token)
        for token in (
            *fx.ORIGINAL_ADD_JOBS,
            fx.ORIGINAL_CUT_JOB,
            fx.ORIGINAL_ADD_MODEL,
            fx.ORIGINAL_REPRO_MODEL,
        )
    }
    for token, files in hits.items():
        assert files, f"evidence token missing from archives: {token}"
    return {
        "source_reports": [
            "docs/validation/feedback-2026-10-16 (0.3.1 S1, sheetmetal toolchain report)",
            "docs/validation/FEEDBACK-0.3.2.md (A S1 regression)",
        ],
        "add_failures": {
            "jobs": list(fx.ORIGINAL_ADD_JOBS),
            "model": fx.ORIGINAL_ADD_MODEL,
            "shape": "10x10x5 block overlapping the base, plus a 155x1x76.46 end wall add",
            "raw_error": fx.ORIGINAL_ADD_ERROR,
            "toolkit_code": fx.ORIGINAL_TOOLKIT_CODE,
        },
        "cut_control": {
            "job": fx.ORIGINAL_CUT_JOB,
            "model": fx.ORIGINAL_REPRO_MODEL,
            "shape": "10x10 sketch extrude(mode='add', depth=5) failed on the same model where cut works",
        },
        "archive_cross_check": hits,
        "replayed_here": False,
        "note": "original inputs are evidence only; the three-way fixture is the fixed overlap case",
    }


def check_native_source() -> dict:
    """Static audit of the single protrusion path; not native verification."""
    generic = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8", errors="replace")
    geometry = (ROOT / "native" / "geometry.cpp").read_text(encoding="utf-8", errors="replace")
    advanced = (ROOT / "native" / "advanced.cpp").read_text(encoding="utf-8", errors="replace")
    schema = (ROOT / "src" / "creo_mechdog" / "schema.py").read_text(
        encoding="utf-8", errors="replace"
    )
    checks = {
        "single_protrusion_path": generic.count("extrude_or_revolve") == 2,
        "dispatch_shared_by_all_models": 'details = extrude_or_revolve(op, kind == "revolve");'
        in generic,
        "feature_type_add_vs_cut": "PRO_FEAT_PROTRUSION" in generic and "PRO_FEAT_CUT" in generic,
        "material_add_vs_remove": "PRO_EXT_MATERIAL_ADD" in generic
        and "PRO_EXT_MATERIAL_REMOVE" in generic,
        "body_all_for_cut": "PRO_BODY_USE_ALL" in generic,
        "body_selected_default_for_add": "PRO_BODY_USE_SELECTED" in generic
        and "ProSolidDefaultBodyGet" in generic,
        "parent_reference_is_model": "ProMdlToModelitem(board, &mi)" in geometry,
        "create_options_no_opts": "PRO_FEAT_CR_NO_OPTS" in geometry,
        "raw_minus_one_preserved": "ProFeatureWithoptionsCreate=" in generic,
        "element_errors_preserved": "last_feature_errors" in generic,
        "first_wall_native_gate_present": "first_wall_line_length" in advanced,
        "first_wall_conversion_is_wall_not_protrusion": "PRO_DTM_SRF_AS_WALL" in advanced,
        "t03_plan_admission_present": "first_wall_section_problem" in schema,
    }
    missing = [name for name, present in checks.items() if not present]
    assert not missing, f"native source guard missing: {missing}"
    return {
        "static_source_assertions": checks,
        "protrusion_paths_found": 1,
        "element_tree": {
            "creation_call": "ProFeatureWithoptionsCreate(model selection, tree, PRO_FEAT_CR_NO_OPTS)",
            "common": [
                "PRO_E_FEATURE_FORM=PRO_EXTRUDE",
                "PRO_E_EXT_SURF_CUT_SOLID_TYPE=PRO_EXT_FEAT_TYPE_SOLID",
                "PRO_E_STD_FEATURE_NAME=<label>",
                "PRO_E_STD_SECTION/PRO_E_SEC_USE_SKETCH=<sketch feature>",
                "PRO_E_STD_DIRECTION=+1/-1 (section normal sign x direction)",
                "PRO_E_STD_EXT_DEPTH: FROM_NONE, TO_BLIND + value",
            ],
            "add_only": [
                "PRO_E_FEATURE_TYPE=PRO_FEAT_PROTRUSION",
                "PRO_E_REMOVE_MATERIAL=PRO_EXT_MATERIAL_ADD",
                "PRO_E_BODY: PRO_BODY_USE_NEW (no solid / new_body) or "
                "PRO_BODY_USE_SELECTED + default body (ProSolidDefaultBodyGet)",
            ],
            "cut_only": [
                "PRO_E_FEATURE_TYPE=PRO_FEAT_CUT",
                "PRO_E_REMOVE_MATERIAL=PRO_EXT_MATERIAL_REMOVE",
                "PRO_E_BODY: PRO_BODY_USE_ALL",
            ],
        },
        "asymmetries_add_vs_cut": [
            "PRO_E_FEATURE_TYPE: PRO_FEAT_PROTRUSION vs PRO_FEAT_CUT",
            "PRO_E_REMOVE_MATERIAL: PRO_EXT_MATERIAL_ADD vs PRO_EXT_MATERIAL_REMOVE",
            "PRO_E_BODY: PRO_BODY_USE_SELECTED + default-body ref vs PRO_BODY_USE_ALL",
        ],
        "root_cause": "not_determined_statically",
        "why": (
            "each asymmetry, and any sheetmetal material-model restriction behind "
            "ProFeatureWithoptionsCreate -1, can only be isolated against a live session"
        ),
        "production_change_this_stage": "none",
        "note": "Source presence only; native geometry is unverified until the live stage.",
    }


# --- live acceptance ------------------------------------------------------

LIVE_ROUTES = (
    ("solid_add", "t04_solid_add", "part", fx.ROUTE_ADD_VOLUME_MM3),
    ("sheetmetal_add", "t04_sm_add", "sheetmetal", fx.ROUTE_ADD_VOLUME_MM3),
    ("sheetmetal_cut", "t04_sm_cut", "sheetmetal", fx.ROUTE_CUT_VOLUME_MM3),
    # BUG-046 isolation. Both keep the same 10 x 10 x 5 block and the same overlap
    # with the 1 mm sheet, so the only difference from sheetmetal_add is the
    # position (off the processed area) or the target body (PRO_BODY_USE_NEW).
    ("sheetmetal_add_offgroup", "t04_sm_add_off", "sheetmetal", fx.ROUTE_ADD_VOLUME_MM3),
    ("sheetmetal_add_new_body", "t04_sm_add_newbody", "sheetmetal", fx.BASE_VOLUME_MM3 + 500.0),
)
EXPECTED_DELTA_MM3 = {
    "solid_add": 400.0,
    "sheetmetal_add": 400.0,
    "sheetmetal_cut": -100.0,
    "sheetmetal_add_offgroup": 400.0,
    "sheetmetal_add_new_body": 500.0,
}
# The measured boundary (2026-10-29 live isolation) is the contract this driver now
# checks: adding solid material into the sheetmetal body is refused at admission
# with an identifiable code, the same add as a new body is a separate 10x10x5 solid
# (+500 mm3, no merge), and the cut still removes the 100 mm3 overlap.
EXPECTED_OUTCOME = {
    "solid_add": {"kind": "success", "delta_mm3": 400.0},
    "sheetmetal_add": {"kind": "rejected", "code": SOLID_ADD_UNSUPPORTED},
    "sheetmetal_cut": {"kind": "success", "delta_mm3": -100.0},
    "sheetmetal_add_offgroup": {"kind": "rejected", "code": SOLID_ADD_UNSUPPORTED},
    "sheetmetal_add_new_body": {"kind": "success", "delta_mm3": 500.0},
}
# Isolation geometry: 10 x 10 at x 60..70 / y -70..-60, clear of the plate edges and
# of every other feature on the XZ wall base (x 0..185, y -232..0, z -0.5..0.5).
OFFSET_MIN = [60.0, -70.0]
OFFSET_MAX = [70.0, -60.0]
ROUTE_PURPOSE = {
    "sheetmetal_add_offgroup": (
        "BUG-046 H3 probe: a non-overlapping-in-plane position must fail exactly like "
        "sheetmetal_add if the trigger is the solid add itself, not the overlap"
    ),
    "sheetmetal_add_new_body": (
        "BUG-046 H1 probe: PRO_BODY_USE_NEW instead of PRO_BODY_USE_SELECTED + default "
        "body isolates whether the target body is what Creo rejects"
    ),
}
# The XZ wall base puts the 1 mm sheet across the sketch plane (z -0.5..0.5), so a
# one-sided prism only shares 0.5 mm with it. "symmetric" halves the requested depth
# per side (2026-10-29 live: depth 2.5 gave a 2.5 mm tall block), so depth 5
# symmetric is a 10x10x5 block spanning the whole thickness on both base kinds
# while the requested value stays the T04 depth of 5 mm.
LIVE_PRISM_DEPTH_MM = 5.0
LIVE_PRISM_DIRECTION = "symmetric"
# One job that has not reached a terminal state within this budget counts as a hang:
# the driver stops, records the job id and never resubmits (DEV-051 hand-off rule).
HANG_BUDGET_SECONDS = 180.0


def live_base_plan(route: str) -> list[dict]:
    if route == "solid_add":
        return [fx.solid_plate_sketch(), fx.solid_base_op()]
    return [fx.wall_sketch(), fx.wall_base_op()]


def shifted_sketch(label: str) -> dict:
    sketch = fx.sheetmetal_overlap_sketch()
    sketch["label"] = label
    sketch["entities"][0]["min"] = list(OFFSET_MIN)
    sketch["entities"][0]["max"] = list(OFFSET_MAX)
    return sketch


def live_prism_plan(route: str) -> list[dict]:
    depth, direction = LIVE_PRISM_DEPTH_MM, LIVE_PRISM_DIRECTION
    if route == "sheetmetal_cut":
        return [
            fx.sheetmetal_overlap_sketch(),
            fx.prism_op(
                "cut",
                "pocket_cut",
                depth=depth,
                direction=direction,
                sketch="sheetmetal_overlap_sketch",
            ),
        ]
    if route == "sheetmetal_add_offgroup":
        return [
            shifted_sketch("offset_sketch"),
            fx.prism_op(
                "add", "boss_add_offset", depth=depth, direction=direction, sketch="offset_sketch"
            ),
        ]
    if route == "sheetmetal_add_new_body":
        return [
            fx.sheetmetal_overlap_sketch(),
            fx.prism_op(
                "add",
                "boss_add_new_body",
                depth=depth,
                direction=direction,
                new_body=True,
                sketch="sheetmetal_overlap_sketch",
            ),
        ]
    return [fx.overlap_sketch(), fx.prism_op("add", "boss_add", depth=depth, direction=direction)]


def element_errors(terminal: dict) -> dict:
    """Element-level errors, reported as present only when the native layer gave them."""
    result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
    pieces = [str(terminal.get("message") or "")]
    for operation in result.get("operations") or []:
        if isinstance(operation, dict):
            pieces.extend(str(operation.get(key) or "") for key in ("error", "message"))
    blob = " ".join(pieces)
    marker = "Element errors:"
    detail = blob.split(marker, 1)[1].split(".", 1)[0].strip() if marker in blob else None
    return {
        "present": detail is not None,
        "detail": detail,
        "log_has_feature_error": "feature_error element="
        in (terminal.get("native_log_tail") or ""),
        "searched": "job message, operation errors/messages and native log tail",
    }


def volume_check(measured: float | None, expected: float) -> dict:
    tolerance = max(0.01, abs(expected) * 1e-3)
    if measured is None:
        return {"expected_mm3": expected, "tolerance_mm3": tolerance, "abs_error_mm3": None}
    error = abs(float(measured) - expected)
    return {"expected_mm3": expected, "tolerance_mm3": tolerance, "abs_error_mm3": error}


async def run_route(
    runner: LiveRunner, route: str, tag: str, model_type: str, expected: float
) -> dict:
    """Base job, then the shared overlap prism in a second job on the same model."""
    name = unique_name(tag)
    created = await runner.submit(
        f"{route}:base",
        "creo_execute_plan",
        {"model_name": name, "model_type": model_type, "operations": live_base_plan(route)},
    )
    job_id, model_id = created["job_id"], created["model_id"]
    terminal = await runner.wait_job(job_id, budget=HANG_BUDGET_SECONDS)
    entry: dict = {
        "route": route,
        "purpose": ROUTE_PURPOSE.get(route, "baseline route of the three-way comparison"),
        "base_model_kind": model_type,
        "model_name": name,
        "model_id": model_id,
        "base_job_id": job_id,
        "base_status": terminal.get("status"),
        "expected_base_volume_mm3": fx.BASE_VOLUME_MM3,
        "expected_result_volume_mm3": expected,
        "expected_delta_mm3": EXPECTED_DELTA_MM3[route],
        "overlap_volume_mm3": fx.overlap_volume_mm3(),
        "prism_volume_mm3": fx.PRISM_SIDE_MM * fx.PRISM_SIDE_MM * LIVE_PRISM_DEPTH_MM,
        "prism_spec": {
            "depth_mm": LIVE_PRISM_DEPTH_MM,
            "direction": LIVE_PRISM_DIRECTION,
            "rectangle_min": live_prism_plan(route)[0]["entities"][0]["min"],
            "rectangle_max": live_prism_plan(route)[0]["entities"][0]["max"],
        },
    }
    if terminal.get("status") != "succeeded":
        entry.update(
            failure=failure_text(terminal),
            element_errors=element_errors(terminal),
            passed=False,
            note="the base was not created, so this route measured no volume or feature",
        )
        return runner.case(entry)

    base = await runner.snapshot(model_id)
    base_volume = runner.volume(base)
    base_features = runner.feature_types(base)
    entry.update(
        base_revision=base.get("revision"),
        base_measured_volume_mm3=base_volume,
        base_feature_types=base_features,
    )

    prism_arguments = {
        "model_id": model_id,
        "expected_revision": base.get("revision"),
        "operations": live_prism_plan(route),
    }
    answer = await runner.probe("creo_execute_plan", prism_arguments)
    body = answer["structured"] or {}
    if answer["is_error"]:
        if body.get("status") == "busy":
            raise LiveStop(f"toolkit channel busy: {json.dumps(body)[:400]}")
        message = str(body.get("error") or body.get("message") or answer["text"])
        rejected = {
            "case": route,
            "route": route,
            "prism_status": "rejected_before_modelling",
            "job_id": body.get("job_id"),
            "message": message[:1200],
            "code_present": SOLID_ADD_UNSUPPORTED in message if route != "sheetmetal_cut" else None,
        }
        after_rejection = await runner.snapshot(model_id)
        rejected.update(
            revision_after_rejection=after_rejection.get("revision"),
            volume_after_rejection_mm3=runner.volume(after_rejection),
            model_unchanged=bool(
                after_rejection.get("revision") == base.get("revision")
                and runner.volume(after_rejection) == base_volume
            ),
            expected=EXPECTED_OUTCOME[route],
            passed=bool(
                EXPECTED_OUTCOME[route]["kind"] == "rejected"
                and SOLID_ADD_UNSUPPORTED in message
                and not body.get("job_id")
                and after_rejection.get("revision") == base.get("revision")
            ),
        )
        entry.update(rejected)
        return runner.case(entry)

    prism = body
    terminal = await runner.wait_job(prism["job_id"], budget=HANG_BUDGET_SECONDS)
    entry.update(prism_job_id=prism["job_id"], prism_status=terminal.get("status"))
    if terminal.get("status") != "succeeded":
        failure = failure_text(terminal)
        after_failure = await runner.snapshot(model_id)
        failure_volume = runner.volume(after_failure)
        entry.update(
            failure=failure,
            element_errors=element_errors(terminal),
            revision_after_failure=after_failure.get("revision"),
            volume_after_failure_mm3=failure_volume,
            rollback_matches_base=bool(
                after_failure.get("revision") == base.get("revision")
                and base_volume is not None
                and failure_volume is not None
                and abs(failure_volume - base_volume) <= 0.01
            ),
            passed=False,
            note="the prism failed; the raw failure is kept and expectations are unchanged",
        )
        return runner.case(entry)

    after = await runner.snapshot(model_id)
    volume = runner.volume(after)
    delta = None if volume is None or base_volume is None else volume - base_volume
    check = volume_check(volume, expected)
    after_features = runner.feature_types(after)
    entry.update(
        revision=after.get("revision"),
        measured_volume_mm3=volume,
        volume_delta_mm3=delta,
        abs_error_mm3=check["abs_error_mm3"],
        tolerance_mm3=check["tolerance_mm3"],
        feature_types=after_features,
        feature_delta={
            key: after_features.get(key, 0) - base_features.get(key, 0)
            for key in set(after_features) | set(base_features)
        },
        saved_file_reloaded_and_verified=(terminal.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ),
    )
    entry["passed"] = bool(
        volume is not None
        and check["abs_error_mm3"] is not None
        and check["abs_error_mm3"] <= check["tolerance_mm3"]
        and delta is not None
        and abs(delta - EXPECTED_DELTA_MM3[route]) <= 0.01
        and entry["saved_file_reloaded_and_verified"] is True
    )
    return runner.case(entry)


async def run_negative_case(runner: LiveRunner, anchor: dict) -> dict:
    """Illegal plans must be refused before modelling and change nothing."""
    model_id = anchor["model_id"]
    before = await runner.snapshot(model_id)
    revision = before.get("revision")
    volume = runner.volume(before)
    degenerate = fx.overlap_sketch()
    degenerate["entities"][0]["max"] = list(fx.OVERLAP_MIN)
    attempts = []
    for name, operations in (
        (
            "through_all_add",
            [fx.overlap_sketch(), fx.prism_op("add", "boss_add", depth_type="through_all")],
        ),
        ("degenerate_overlap_rectangle", [degenerate, fx.prism_op("add", "boss_add")]),
    ):
        answer = await runner.probe(
            "creo_execute_plan",
            {"model_id": model_id, "expected_revision": revision, "operations": operations},
        )
        body = answer["structured"] or {}
        attempts.append(
            {
                "case": name,
                "rejected": bool(answer["is_error"]),
                "job_id": body.get("job_id"),
                "message": str(body.get("error") or body.get("message") or answer["text"])[:500],
            }
        )
    after = await runner.snapshot(model_id)
    unchanged = (
        after.get("revision") == revision
        and runner.volume(after) == volume
        and not any(attempt["job_id"] for attempt in attempts)
    )
    return runner.case(
        {
            "case": "negative_before_modelling",
            "model_id": model_id,
            "revision_before": revision,
            "revision_after": after.get("revision"),
            "volume_before_mm3": volume,
            "volume_after_mm3": runner.volume(after),
            "attempts": attempts,
            "model_and_revision_unchanged": unchanged,
            "passed": bool(unchanged and all(attempt["rejected"] for attempt in attempts)),
        }
    )


async def live(output: Path, run_id: str) -> int:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=180) as client:
        runner = LiveRunner(
            client,
            output,
            "BUG-046 / DEV-051 T04",
            "three-way overlap comparison: solid add, sheetmetal add, sheetmetal cut",
            run_id,
        )
        try:
            await runner.start()
            runner.report["hang_budget_seconds"] = HANG_BUDGET_SECONDS
            anchor = None
            wall_blocked = None
            for route, tag, model_type, expected in LIVE_ROUTES:
                if wall_blocked:
                    runner.case(
                        {
                            "route": route,
                            "base_model_kind": model_type,
                            "base_status": "not_executed",
                            "passed": False,
                            "not_executed": wall_blocked,
                        }
                    )
                    continue
                entry = await run_route(runner, route, tag, model_type, expected)
                if entry["passed"] and anchor is None:
                    anchor = entry
                if route == "sheetmetal_add" and entry["base_status"] != "succeeded":
                    message = (entry.get("failure") or {}).get("message") or "base failed"
                    wall_blocked = (
                        "sheetmetal base wall did not succeed, so this route was not submitted: "
                        + str(message)[:300]
                    )
                    runner.report["blocked_route"] = {
                        "route": "sheetmetal_cut",
                        "reason": wall_blocked,
                        "evidence": "DEV-051 T03 live card: the first wall is rejected before modelling",
                    }
            if anchor is None:
                runner.report["negative_check"] = {"skipped": "no successful route to anchor on"}
            else:
                await run_negative_case(runner, anchor)
        except BaseException as error:
            runner.report["stopped"] = f"{type(error).__name__}: {error}"
            runner.finish()
            raise
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    rows = [
        {
            key: case.get(key)
            for key in ("route", "base_status", "prism_status", "volume_delta_mm3", "passed")
        }
        for case in runner.report["cases"]
    ]
    print(json.dumps({"passed": runner.report["passed"], "cases": rows}, ensure_ascii=False))
    return 0 if runner.report["passed"] else 1


def run_unit_module() -> dict:
    from tests.unit import test_sheetmetal_overlap

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_sheetmetal_overlap)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    return {
        "module": "tests.unit.test_sheetmetal_overlap",
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
    """Refuse to overwrite an existing report before anything else runs."""
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "sheetmetal_overlap" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
    """Collect source evidence even when running from an extracted release."""
    from creo_mechdog.source_provenance import local_provenance as collect

    return collect(
        ROOT, ("tools/test_sheetmetal_overlap.py", "tests/unit/test_sheetmetal_overlap.py")
    )


def write_offline_report(output: Path, run_id: str, results: dict) -> dict:
    report = {
        "task": "BUG-046 / DEV-051 T04",
        "scope": (
            "three-way overlap comparison (solid add / sheetmetal add / sheetmetal cut) "
            "on the confirmed thin base plate; static audit of the protrusion path"
        ),
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: input contracts, negative contracts, regression guards "
            "and the static path audit are validated. No Toolkit connection, no native "
            "geometry, no root cause claimed."
        ),
        "oracle": {
            "base_plate_mm": [fx.BASE_LENGTH_MM, fx.BASE_WIDTH_MM, fx.BASE_THICKNESS_MM],
            "base_volume_mm3": fx.BASE_VOLUME_MM3,
            "prism": "10x10x5 mm block centred on the sketch plane (symmetric, 2.5 each side)",
            "overlap_volume_mm3": fx.overlap_volume_mm3(),
            "route_add_volume_mm3": fx.ROUTE_ADD_VOLUME_MM3,
            "route_cut_volume_mm3": fx.ROUTE_CUT_VOLUME_MM3,
            "independent_of_production_normalization": True,
        },
        "checks": results,
        "support_boundary": {
            "solid_add_on_sheetmetal": "unconfirmed_offline",
            "disclosure": (
                "no pre-modeling rejection and no identifiable error code are added in this "
                "stage: declaring the combination unsupported would prejudge the live result. "
                "If live confirms it is unsupported, BUG-046 requires a clear boundary plus "
                "viable-tool guidance (sheetmetal_wall / sheetmetal_flange) instead of a bare "
                "-1; that change is intentionally not made here."
            ),
            "forbidden_shortcut": (
                "converting the sheetmetal part to a solid part must never be reported as a "
                "successful sheetmetal add"
            ),
        },
        "thick_wall_branch": {
            "status": "pending_t03_live_contract",
            "note": (
                "the thick base branch is listed for verification only; this stage sets no "
                "geometry conclusion for it"
            ),
        },
        "live_checklist": [
            "run the three routes on fresh models with unique names; record job/model/revision",
            "route A (solid add) must succeed with volume 43 320 mm3 and one merged body",
            "route B (sheetmetal add) records the raw failure code and element errors, or the "
            "real added volume 43 320 mm3 if supported",
            "route C (sheetmetal cut) must remove 100 mm3 and keep sheetmetal identity",
            "probe B2: non-overlapping sheetmetal add (discriminates overlap from add)",
            "probe B3: exact original replay (depth 5 positive, as in the 0.3.2 repro)",
            "isolate the three add/cut asymmetries (body element, feature type, remove flag)",
            "negative case: a failing add must leave volume/aliases/revision unchanged and a "
            "later legal cut must still work",
            "unbend/bend_back after each successful add or cut; saved_file_reloaded_and_verified",
            "thick-wall base branch after T03 fixes the real geometry contract",
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
        print("live runs require --confirm-session-usable", file=sys.stderr)
        return 2
    if args.live:
        run_id = live_run_id()
        return asyncio.run(live(live_output("sheetmetal_overlap", run_id, args.output), run_id))

    run_id = new_run_id()
    output = resolve_output(args.output, run_id)
    results = {
        "three_way_contract": check_three_way_contract(),
        "shared_geometry": check_shared_geometry(),
        "negative_contracts": check_negative_contracts(),
        "regression_guards": check_regression_guards(),
        "original_evidence": check_original_evidence(),
        "native_source": check_native_source(),
    }
    report = write_offline_report(output, run_id, results)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name("report.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"report_sha256: {digest}")
    print(f"unit_module: {report['unit_module']}")
    return 0 if report["unit_module"]["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
