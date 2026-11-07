"""DEV-051 T05 offline driver: four-wall flange failure localisation (FEAT-014/BUG-047).

Offline half of the 0.7.0 R1 S3 case: 185 x 232 x 1 mm base wall plus four flanges
(h80 / R2.54 / Y0.5) whose edges were captured in one inspection (reported as
104-107). The third flange returned ProFeatureWithoptionsCreate=-1 and the fourth
never ran.

Nothing here reproduces Creo. The driver does three things that can be done
without a session:

1. builds the fixture from the confirmed thin plate and selects the four edges
   from geometry (endpoints, span, boundary plane) with an explicit top/bottom
   face -- the report's ids are evidence only and never selected from;
2. compares the reported single plan (four ids captured once) with the
   per-flange refresh procedure (re-inspect, validate, submit one flange per
   job), and records the expectation and judgement fields for every flange;
3. audits the flange element tree statically: what the public parameters reach
   (section side = bend direction, radius, Y factor), what is fixed (trajectory
   normal, thickness flip, relief none) and what is implicit (parent body).

It does not decide the root cause. The hypotheses are falsifiable, each one maps
to a judgement field, and the decision table states which observation would
support or refute it. The stage result is "not reproduced offline / root cause
undetermined" until a live session fills those fields.

Default is strictly offline: no MCP client, no Toolkit connection, no job. --live
needs --confirm-session-usable and is still refused here; T05's live diagnosis
belongs to the single shared dev service integration step.
"""

from __future__ import annotations

import argparse
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
from tests.unit import test_sheetmetal_flange as fx  # noqa: E402

ROOT = SOURCE_PATHS.resource_root


# --- checks ---------------------------------------------------------------


def check_edge_selection() -> dict:
    inspection = fx.box_inspection()
    sides = {}
    for side in fx.SIDE_AXES:
        top = fx.select_wall_edge(inspection, fx.PLATE_BOUNDS, side, face="top")
        bottom = fx.select_wall_edge(inspection, fx.PLATE_BOUNDS, side, face="bottom")
        sides[side] = {
            "top": top["geometry"],
            "bottom": bottom["geometry"],
            "top_and_bottom_are_parallel": abs(
                top["geometry"]["start"][2] - bottom["geometry"]["start"][2]
            )
            == fx.PLATE_THICKNESS_MM,
        }
    try:
        fx.select_wall_edge(inspection, fx.PLATE_BOUNDS, "+x")
    except fx.EdgeSelectionError as error:
        ambiguous = str(error)
    else:
        raise AssertionError("an unqualified side was accepted")
    shuffled = fx.box_inspection()
    for index, edge in enumerate(shuffled["edges"]):
        edge["id"] = 900 + index * 11
    permuted = {
        side: fx.select_wall_edge(shuffled, fx.PLATE_BOUNDS, side, face="top")["geometry"]
        for side in fx.SIDE_AXES
    }
    for side, geometry in sides.items():
        assert permuted[side]["start"] == geometry["top"]["start"], side
        assert permuted[side]["end"] == geometry["top"]["end"], side
    return {
        "selection_input": (
            "inspection edges (id, start, end, adjacent_surfaces) + active body bbox; "
            "no id from the report is read"
        ),
        "report_edge_ids_used": [],
        "report_edge_ids_present_in_catalog": sorted(
            set(fx.REPORT_EDGE_IDS) & {edge["id"] for edge in inspection["edges"]}
        ),
        "sides": sides,
        "unqualified_side_refused": ambiguous,
        "permuted_ids_keep_the_same_geometry": True,
        "face_is_required_because": (
            "a 1 mm wall has two parallel boundary edges 1 mm apart; the reported run never "
            "recorded which one each id named"
        ),
    }


def check_plan_contract() -> dict:
    from creo_mechdog.schema import validate_operations

    inspection = fx.box_inspection()
    operations, references = fx.four_wall_plan(inspection)
    validated = validate_operations(operations)
    rows = []
    previous: list[str] = []
    for position, (side, label) in enumerate(fx.FLANGE_SEQUENCE):
        reference = references[position]
        span = reference["geometry"]["span_mm"]
        corners = fx.shared_corners(previous, side)
        previous.append(side)
        rows.append(
            {
                "label": label,
                "index": position + 2,
                "side": side,
                "edge": reference["geometry"],
                "request": {
                    "height": fx.FLANGE_HEIGHT_MM,
                    "angle": fx.FLANGE_ANGLE_DEG,
                    "radius": fx.FLANGE_RADIUS_MM,
                    "y_factor": fx.FLANGE_Y_FACTOR,
                    "flip": False,
                },
                "expected": {
                    "added_volume_mm3": fx.wall_volume_mm3(span),
                    "volume_basis": "span x height x thickness (constant-thickness wall)",
                    "shared_corners_with_previous_walls": corners,
                    "corner_overlap_lower_bound_mm3": fx.corner_overlap_volume_mm3(corners),
                    "bbox_if_material_inside": list(fx.predicted_bbox(side, "inside")),
                    "bbox_if_material_outside": list(fx.predicted_bbox(side, "outside")),
                    "direction_if_bent": (
                        "up if the plate sits above the sketch plane; T03 still lists the "
                        "bbox sign as a live item"
                    ),
                },
                "judgement": fx.judgement_template(label, position + 2, side),
            }
        )
    return {
        "operations_validated": len(validated),
        "operation_order": [operation["op"] for operation in validated],
        "labels": [operation["label"] for operation in validated],
        "reported_indices": {row["label"]: row["index"] for row in fx.ORIGINAL_OPERATION_RESULTS},
        "flanges": rows,
        "volume_note": (
            "the flange volume is t x developed length x span and does not depend on the bend "
            "radius or Y factor; the corner overlap is a lower bound because the bend arc "
            "removes (h - R) from the straight run"
        ),
    }


def check_sequence_comparison() -> dict:
    inspection = fx.box_inspection()
    _, references = fx.four_wall_plan(inspection)
    steps = fx.sequential_steps(inspection)
    table = []
    for position, (side, label) in enumerate(fx.FLANGE_SEQUENCE):
        single = references[position]["geometry"]
        sequential = steps[position]["reference"]["geometry"]
        table.append(
            {
                "label": label,
                "side": side,
                "single_plan": {
                    "edge_id": single["id"],
                    "span_mm": single["span_mm"],
                    "start": single["start"],
                    "end": single["end"],
                    "source": "captured once, before any flange existed",
                },
                "sequential": {
                    "edge_id": sequential["id"],
                    "span_mm": sequential["span_mm"],
                    "shortfall_mm": sequential["shortfall_mm"],
                    "start": sequential["start"],
                    "end": sequential["end"],
                    "source": "re-inspected after the previous flange",
                    "allow_shortened": position >= 2,
                },
                "same_geometry": single["start"] == sequential["start"]
                and single["end"] == sequential["end"],
            }
        )
    return {
        "table": table,
        "single_plan_ids": len({row["single_plan"]["edge_id"] for row in table}),
        "conclusion": (
            "both procedures agree on flanges 1-2; from flange 3 the refreshed boundary is "
            "shorter by one thickness at each shared corner, so a reference captured before "
            "the first flange no longer describes the intended full-length edge"
        ),
        "not_a_live_result": True,
    }


def _function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    end = source.find("\nstatic ", start + len(signature))
    return source[start : end if end > 0 else len(source)]


def check_native_source() -> dict:
    """Static audit of the flange element tree; not native verification."""
    advanced = (ROOT / "native" / "advanced.cpp").read_text(encoding="utf-8", errors="replace")
    geometry = (ROOT / "native" / "geometry.cpp").read_text(encoding="utf-8", errors="replace")
    body = _function_body(advanced, "static void generic_sheetmetal_flange")
    # T11 moved relief into its own helper, so the relief facts are asserted on
    # that body. The default is still NONE on both ends; rectangular is opt-in.
    relief_body = _function_body(advanced, "static void flange_relief_side")
    checks = {
        "feature_type_wall": "PRO_E_FEATURE_TYPE, PRO_FEAT_WALL" in body,
        "wall_type_flange": "PRO_E_SMT_WALL_TYPE, PRO_SMT_WALL_TYPE_FLANGE" in body,
        "flange_type_2d_swept": "PRO_FLANGE_WALL_TYPE_2D_SWEPT" in body,
        # 2026-10-29 DEV-051 A / BUG-047: `flip` used to write the trajectory normal, which
        # produced identical geometry for both values. The measured direction switch is the
        # section side element; the trajectory normal now stays at the stock NO_FLIP.
        "section_side_flip_exposed": "PRO_E_SMT_FLANGE_SEC_FLIP, sec_flip" in body
        and 'op.value("flip", false) ? PRO_B_FALSE : PRO_B_TRUE' in body,
        "trajectory_normal_fixed_no_flip": "PRO_E_SMT_FLANGE_TRAJ_CRV_NORM, PRO_FLANGE_TRAJ_NORM_NO_FLIP"
        in body,
        "wall_thickness_flip_fixed_false": "PRO_E_SMT_WALL_THICKNESS_FLIP, PRO_B_FALSE" in body,
        "bend_relief_compound_both_ends": "PRO_E_SMT_BEND_RELIEF" in body
        and "PRO_E_SMT_BEND_RELIEF_SIDE1" in body
        and "PRO_E_SMT_BEND_RELIEF_SIDE2" in body,
        "bend_relief_default_none_both_ends": "PRO_BEND_RLF_NONE" in relief_body
        and "enabled ? PRO_BEND_RLF_RECTANGULAR : PRO_BEND_RLF_NONE" in relief_body,
        "bend_relief_rectangular_opt_in": "PRO_BEND_RLF_RECTANGULAR" in relief_body
        and "PRO_E_BEND_RELIEF_WIDTH" in relief_body
        and "PRO_BEND_RLF_DEPTH_BLIND" in relief_body
        and "PRO_E_BEND_RELIEF_DEPTH" in relief_body,
        "bend_relief_other_shapes_absent": "PRO_BEND_RLF_RIP" not in relief_body
        and "PRO_BEND_RLF_OBROUND" not in relief_body
        and "PRO_BEND_RLF_STRETCH" not in relief_body
        and "PRO_BEND_RLF_PARAM" not in relief_body,
        "corner_miter_rip_absent": "PRO_E_SMT_CORNER_RELIEF" not in body
        and "PRO_E_SMT_MTR_CUTS" not in body
        and "PRO_E_SMT_EDGE_RIP" not in body,
        "relief_validated_before_create": body.index("flange_relief_request(op)")
        < body.index("PRO_E_FEATURE_TREE"),
        "sharp_corners_to_bends": "PRO_E_SMT_WALL_SHARPS_TO_BENDS, PRO_B_TRUE" in body,
        "radius_inside_fillet": "PRO_E_SMT_FILLETS_USE_RAD" in body
        and "PRO_BEND_RAD_INSIDE" in body
        and 'op["radius"]' in body,
        "y_factor_exposed": 'op.value("y_factor", 0.5)' in body
        and "PRO_DVL_SRC_FEAT_YF_ONLY" in body,
        # DEV-051 T05/T11 (2026-10-29): the section's horizontal centerline is the
        # alignment with the attachment wall and its coordinate system is the attachment
        # point, so the leg angle is measured from that alignment. The pre-fix
        # (90 - angle) form made every 90 degree request collinear with the centerline
        # (native.log LINE_wall 0,0 -> 80,0): a zero-bend profile.
        "angle_in_section_frame": 'op["angle"].get<double>() * acos(-1.0) / 180' in body,
        "regenerate_after_create": "ProSolidRegenerate" in body,
        "parent_is_the_model_not_a_body_element": "PRO_E_BODY" not in body,
        "attachment_edge_checked_on_a_wall_face": "ProSmtedgeContourGet" in body
        and "PRO_TK_BAD_CONTEXT" in body,
        "create_uses_model_selection": "ProMdlToModelitem(board, &mi)" in geometry
        and "PRO_FEAT_CR_NO_OPTS" in geometry,
        "section_path_recorded": 'extra["section_path"]' in body,
    }
    missing = [name for name, present in checks.items() if not present]
    assert not missing, f"native source guard missing: {missing}"
    return {
        "static_source_assertions": checks,
        "element_tree": {
            "feature": "PRO_FEAT_WALL / PRO_SMT_WALL_TYPE_FLANGE / PRO_FLANGE_WALL_TYPE_2D_SWEPT",
            "trajectory": "PRO_E_STD_CURVE_COLLECTION_APPL with one edge reference",
            "material_side": (
                "PRO_E_SMT_FLANGE_SEC_FLIP = flip ? FALSE : TRUE (default out of the "
                "attachment face); PRO_E_SMT_FLANGE_TRAJ_CRV_NORM stays NO_FLIP"
            ),
            "fixed_not_exposed": [
                "PRO_E_SMT_WALL_THICKNESS_FLIP = FALSE",
                "PRO_E_SMT_CORNER_RELIEF, PRO_E_SMT_MTR_CUTS, PRO_E_SMT_EDGE_RIP",
            ],
            "bend_relief": (
                "T11: side1/side2 default PRO_BEND_RLF_NONE (unchanged for old calls) and "
                "opt-in PRO_BEND_RLF_RECTANGULAR with width plus blind depth; other relief "
                "shapes are absent"
            ),
            "bend": "radius at PRO_E_SMT_FILLETS_VALUE, side = PRO_BEND_RAD_INSIDE",
            "development": "PRO_E_SMT_DEV_LEN_Y_FACTOR from y_factor (Y factor only)",
            "parent": "ProFeatureWithoptionsCreate(model selection, tree, PRO_FEAT_CR_NO_OPTS)",
            "body": "no PRO_E_BODY element: the wall attaches to the model's active body",
        },
        "conclusion": (
            "one public control (flip) reaches the bend side through the section side element; "
            "the trajectory normal, thickness side, relief (none by default, rectangular only "
            "when requested) and the target body plus every corner rule stay fixed. A live "
            "third-flange failure therefore cannot be attributed to a public parameter from "
            "the source alone, and T11 relief is not proof that the corner itself is resolved."
        ),
        "production_change_this_stage": (
            "generic_sheetmetal_flange: the direction switch moved from "
            "PRO_E_SMT_FLANGE_TRAJ_CRV_NORM to PRO_E_SMT_FLANGE_SEC_FLIP"
        ),
        "production_change_since": (
            "DEV-051 T11 added the opt-in rectangular relief; DEV-051 A made the section side "
            "the direction switch after the 2026-10-29 live matrix"
        ),
    }


def check_hypotheses() -> dict:
    return {
        "hypotheses": [
            {
                "id": hypothesis["id"],
                "statement": hypothesis["statement"],
                "probe": hypothesis["probe"],
                "expected_if_true": hypothesis["expected_if_true"],
                "refutation": hypothesis["refutation"],
                "judgement_fields": list(hypothesis["judgement_fields"]),
                "status": hypothesis["status"],
            }
            for hypothesis in fx.HYPOTHESES
        ],
        "decision_table": [dict(row) for row in fx.DECISION_TABLE],
        "statement": "no hypothesis is resolved offline; none is reported as a root cause",
    }


def check_original_evidence() -> dict:
    tokens = (
        fx.ORIGINAL_JOB,
        fx.ORIGINAL_MODEL,
        fx.ORIGINAL_MODEL_NAME,
        fx.ORIGINAL_ERROR,
    )
    hits = {token: fx.archived_reports_containing(token) for token in tokens}
    for token, files in hits.items():
        assert files, f"evidence token missing from archives: {token}"
    return {
        "source_report": (
            "docs/validation/feedback-0.7.0-2026-10-28/"
            "2026-10-27_CREO_0.7.0_钣金增料与四壁折边仍未修复验收报告.md"
        ),
        "job": fx.ORIGINAL_JOB,
        "model": fx.ORIGINAL_MODEL,
        "model_name": fx.ORIGINAL_MODEL_NAME,
        "raw_error": fx.ORIGINAL_ERROR,
        "reported_edge_ids": list(fx.REPORT_EDGE_IDS),
        "reported_operation_results": [dict(row) for row in fx.ORIGINAL_OPERATION_RESULTS],
        "operation_index_matches_fixture": {
            row["label"]: row["index"] for row in fx.ORIGINAL_OPERATION_RESULTS
        },
        "archive_cross_check": hits,
        "replayed_here": False,
        "rebuild_note": (
            "the report lists the successful flanges as effect_status=rolled_back, so a retry "
            "must rebuild the plate and every flange; resuming at flange 3 is invalid"
        ),
    }


def check_thick_plate_branch() -> dict:
    return {
        "branch": dict(fx.THICK_PLATE_BRANCH),
        "conclusion": "no geometry conclusion: waiting for the T03 live bbox/axis contract",
    }


def t11_design_input() -> dict:
    return {
        "trigger": (
            "live evidence shows the third flange fails on a full-length edge and succeeds on "
            "an edge trimmed short of the corners, or the predicted corner overlap is measured"
        ),
        "capability": "bend relief at the wall ends plus a corner rule for perpendicular walls",
        "open_parameters": [
            "relief type: none / rectangular / tear / circular",
            "relief width and depth relative to the wall thickness",
            "one end or both ends, and whether the user can select them",
            "corner rule: relief only, miter, or explicit overlap policy",
            "schema surface: a sheetmetal_flange field or a model-level rule",
            "compatibility default must stay none for existing plans",
        ],
        "must_not": (
            "do not add an undocumented relief default inside this investigation task, and do "
            "not claim four-wall capability before unbend/bend-back, edit, reload and rollback"
        ),
        "implemented_here": False,
        "t11_status": (
            "implemented offline: relief type none (default) or rectangular with explicit width, "
            "blind depth and end selection; rip/stretch/obround/param and every corner rule stay "
            "unsupported. Native acceptance is pending, so four-wall capability is still open."
        ),
    }


def live_checklist() -> list[str]:
    return [
        "confirm the session is usable and BUG-001 conditions hold; one dev service only",
        "fresh model with a unique name; record job/model/revision and the base wall bbox/volume",
        "inspect and store the full edge catalog (both faces of all four sides), not four ids",
        "for each flange: re-inspect, select by geometry with an explicit face, validate the "
        "reference, submit one job, poll, then fill every judgement field",
        "after each flange record bbox (material side and direction), bodies, feature status, "
        "whether the flanged edge was consumed and whether the neighbours shortened",
        "run the untouched single plan on a second fresh model for the same fingerprint",
        "at flange 3 also submit the captured-before-flange-1 reference to compare failure modes",
        "on failure record the raw code and element errors, the real rollback and the revision, "
        "then rebuild from the plate; never resume at the next flange",
        "probe the trimmed edge (20 mm short of both corners) to separate corner overlap from "
        "reference drift",
        "toggle flip on one edge only: the section side must move the bend, so the two bbox "
        "sides differ by the flange height",
        "run the thick-base first flange only after the T03 live contract fixes the bbox",
    ]


def run_unit_module() -> dict:
    from tests.unit import test_sheetmetal_flange

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_sheetmetal_flange)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    return {
        "module": "tests.unit.test_sheetmetal_flange",
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
        else ROOT / "build" / "sheetmetal_flange" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
    """Collect source evidence even when running from an extracted release."""
    from creo_mechdog.source_provenance import local_provenance as collect

    return collect(
        ROOT, ("tools/test_sheetmetal_flange.py", "tests/unit/test_sheetmetal_flange.py")
    )


def write_offline_report(output: Path, run_id: str, results: dict) -> dict:
    report = {
        "task": "FEAT-014 / BUG-047 / DEV-051 T05",
        "scope": (
            "four-wall flange failure localisation: geometric edge selection, per-flange "
            "refresh versus one captured plan, element-tree audit and falsifiable probes"
        ),
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "status": {
            "reproduction": "not_reproduced_offline",
            "root_cause": "undetermined",
            "production_change": "none",
            "statement": (
                "Offline only: fixture, selection, expectations and probes are ready. No Toolkit "
                "connection, no native geometry, no failure reproduced and no root cause claimed."
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
            "labels": [label for _, label in fx.FLANGE_SEQUENCE],
            "oracle_independent_of_production": True,
        },
        "checks": results,
        "t11_design_input": t11_design_input(),
        "live_checklist": live_checklist(),
        "not_verified": [
            "no flange was created; the third-flange failure is not reproduced",
            "material side, direction, parent body and feature health are unmeasured",
            "the corner-overlap prediction is geometry, not an observed native failure",
            "the thick-base branch has no live contract yet",
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
        print(fx.LIVE_REFUSAL, file=sys.stderr)
        return 2

    run_id = new_run_id()
    output = resolve_output(args.output, run_id)
    results = {
        "edge_selection": check_edge_selection(),
        "plan_contract": check_plan_contract(),
        "sequence_comparison": check_sequence_comparison(),
        "native_source": check_native_source(),
        "hypotheses": check_hypotheses(),
        "original_evidence": check_original_evidence(),
        "thick_plate_branch": check_thick_plate_branch(),
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
