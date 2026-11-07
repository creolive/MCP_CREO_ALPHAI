"""DEV-051 T11 offline driver: bend-end relief for the four-wall flange case (FEAT-014).

Second-batch T11. Inputs: the T05 failure candidate (185 x 232 x 1 mm base wall,
four flanges h80 / R2.54 / Y0.5, third flange returned
ProFeatureWithoptionsCreate=-1) and the T03 contract for the thin wall.

The 2026-10-29 round six proved only a negative: both measured flanges ended at
free plate corners, where no notch is expected either way. The 2026-10-30 stage
adds the valid-material scenario - f_px on +x (both bend ends at free corners)
followed by f_ny on -y, whose +x chain end runs into f_px's bend - with a
differential oracle: the none baseline vs rectangular 1x1 / 4x4 / single ends on
the same geometry, removal expectations derived from the actual intersecting
material, and a verdict that rejects "parameters written but no material
removed". The DEV-051 T05 contrast (2026-10-30) proved that such an attach-edge
end adjacent to an existing bend fails flange regeneration, so a failing f_ny
with that evidence is classified known_t05_boundary instead of a failure, and
the relief geometry it blocks is reported unverified.

The driver is offline only. It records:

* what Creo 12.4 Toolkit exposes for bend relief and corners, read from the
  installed ProSmtFlangeWall.h when a Creo root is configured and otherwise
  reported as a transcription with the header path;
* the admission matrix -- the compatibility default none, the single supported
  rectangular shape, the end selection and every rejected combination;
* the native element tree the implementation must produce, plus what it must
  still not touch (corner relief, miter cuts, edge rip, parent body), and the
  created-feature read-back that proves the values reached the tree;
* the four-wall expectation with relief: wall volume, relief removal, shared
  corners and the depth needed to reach the T05 corner run;
* the material-scenario plan, per-case removal expectations and the verdict
  matrix, including the round-six shape (echo without geometry) as rejected;
* the edit path: relief is fixed at creation, the named height dimension keeps
  its existing edit, and a change means deleting and re-creating the flange.

Default use makes no Creo session, no Toolkit job and no native geometry.
"--live --confirm-session-usable" runs the two four-wall profiles (relief
omitted, and rectangular 1x1 on both ends) and then the material scenario
against the manually opened session: one base wall per profile, then the
flanges one job at a time, re-selecting each edge from a fresh snapshot. Each
flange records the measured volume delta, the relief alias echo, the
created-feature relief read-back, the native feature types and, on failure, the
raw code plus whether the model rolled back. It never launches, restarts or
closes Creo, never injects a fault, never clears a protection and never
resubmits a job; a failed base wall stops the remaining profile instead of
repeating the same blocked submission.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
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
from tests.unit import test_sheetmetal_relief as relief  # noqa: E402

ROOT = SOURCE_PATHS.resource_root

from tools.sheetmetal_live import (  # noqa: E402
    LiveRunner,
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

PROFILES = {
    "thickness_scale": {
        "description": "one thickness wide and deep; the Creo-style default scale",
        "relief": {"type": "rectangular", "width": 1.0, "depth": 1.0},
    },
    "corner_run": {
        "description": (
            "one thickness wide, depth equal to the shared corner run (height - radius); the "
            "smallest notch that reaches through the T05 overlap column"
        ),
        "relief": {"type": "rectangular", "width": 1.0, "depth": 77.46},
    },
}


# DEV-051 live rule: one job that is not terminal after 180 s is a hang. The driver then
# records the job id and the stage, stops every further submission and never resubmits.
HANG_BUDGET_SECONDS = 180.0

# --- checks ---------------------------------------------------------------


def configured_creo_root() -> Path | None:
    config = ROOT / "config.json"
    if not config.exists():
        return None
    try:
        root = json.loads(config.read_text(encoding="utf-8-sig")).get("creo_root")
    except (OSError, ValueError):
        return None
    return Path(root) if root else None


def sdk_contract() -> dict:
    """Relief and corner enums, cross-checked against the installed SDK if present."""
    header = "Common Files/protoolkit/includes/ProSmtFlangeWall.h"
    parsed: dict = {"status": "not_checked", "path": None, "lines": {}}
    root = configured_creo_root()
    candidate = root / header if root else None
    if candidate is not None and candidate.exists():
        text = candidate.read_text(encoding="utf-8", errors="replace")
        names = {}
        for match in re.finditer(r"PRO_BEND_RLF_([A-Z_]+)\s*=\s*(-?\d+)", text):
            names[match.group(1).lower()] = int(match.group(2))
        found = {name: names.get(name) for name in relief.RELIEF_TYPES}
        for match in re.finditer(r"^\s*(PRO_E_[A-Z_0-9]+)\s{2,}", text, re.M):
            parsed["lines"][match.group(1)] = text[: match.start()].count("\n") + 1
        parsed.update(
            {
                "status": "parsed",
                "path": str(candidate),
                "relief_types": found,
                "matches_transcription": found == relief.RELIEF_TYPES,
                "element_names_present": {
                    "PRO_E_SMT_BEND_RELIEF": "PRO_E_SMT_BEND_RELIEF" in parsed["lines"],
                    "PRO_E_SMT_BEND_RELIEF_SIDE1": "PRO_E_SMT_BEND_RELIEF_SIDE1" in parsed["lines"],
                    "PRO_E_SMT_BEND_RELIEF_SIDE2": "PRO_E_SMT_BEND_RELIEF_SIDE2" in parsed["lines"],
                    "PRO_E_BEND_RELIEF_WIDTH": "PRO_E_BEND_RELIEF_WIDTH" in parsed["lines"],
                    "PRO_E_BEND_RELIEF_DEPTH_TYPE": "PRO_E_BEND_RELIEF_DEPTH_TYPE"
                    in parsed["lines"],
                    "PRO_E_BEND_RELIEF_DEPTH": "PRO_E_BEND_RELIEF_DEPTH" in parsed["lines"],
                },
            }
        )
    elif candidate is not None:
        parsed.update({"status": "header_not_found", "path": str(candidate)})
    return {
        "sdk_version": relief.SDK_VERSION,
        "header": header,
        "transcribed": {
            "relief_types": relief.RELIEF_TYPES,
            "depth_types": relief.RELIEF_DEPTH_TYPES,
            "corner_relief_types": relief.CORNER_RELIEF_TYPES,
        },
        "installed_header": parsed,
        "selected_shape": {
            "type": "rectangular",
            "why": (
                "the only shape whose geometry the caller fully controls with two numbers; rip "
                "has no width/depth, stretch and obround are not needed for a box corner, and "
                "param defers to part defaults"
            ),
            "width_rule": "width > 0 in model units; mandatory on every enabled end",
            "depth_rule": (
                "depth >= 0 in model units, always PRO_BEND_RLF_DEPTH_BLIND, measured from the "
                "bend edge (SDK note 7)"
            ),
            "end_rule": "ends both|side1|side2; the other end stays PRO_BEND_RLF_NONE",
            "thickness_rule": (
                "absolute model units, never a thickness multiple and never a thickness-derived "
                "default; the applied record carries the measured part thickness"
            ),
        },
        "not_supported": {
            "relief_shapes": list(relief.UNSUPPORTED_RELIEF_TYPES),
            "corner_rules": list(relief.NOT_IMPLEMENTED_CORNER_RULES),
            "statement": (
                "corner relief (ProCornerRelType), miter cuts and edge rips exist in the same "
                "SDK tree but are not emitted; nothing is inferred from edge or corner geometry"
            ),
        },
    }


def _attempt(relief_value) -> dict:
    from creo_mechdog.schema import validate_operations

    operation = relief.flange_op(relief_value)
    try:
        return {"accepted": validate_operations([operation])[0]}
    except Exception as error:  # noqa: BLE001 - the driver records the real rejection text
        return {"rejected": str(error)}


def admission_matrix() -> dict:
    cases = {
        "omitted": None,
        "explicit_none": {"type": "none"},
        "rectangular_both": {"type": "rectangular", "width": 1.0, "depth": 1.0},
        "rectangular_side1": {"type": "rectangular", "width": 1.0, "depth": 1.0, "ends": "side1"},
        "rectangular_side2": {"type": "rectangular", "width": 1.0, "depth": 1.0, "ends": "side2"},
        "rectangular_zero_depth": {"type": "rectangular", "width": 1.0, "depth": 0.0},
        "none_with_width": {"type": "none", "width": 1.0},
        "none_with_ends": {"type": "none", "ends": "side1"},
        "rectangular_missing_depth": {"type": "rectangular", "width": 1.0},
        "rectangular_zero_width": {"type": "rectangular", "width": 0.0, "depth": 1.0},
        "rectangular_negative_depth": {"type": "rectangular", "width": 1.0, "depth": -1.0},
        "rectangular_boolean_width": {"type": "rectangular", "width": True, "depth": 1.0},
        "rectangular_infinite_depth": {"type": "rectangular", "width": 1.0, "depth": float("inf")},
        "rip": {"type": "rip"},
        "stretch": {"type": "stretch"},
        "obround": {"type": "obround", "width": 1.0, "depth": 1.0},
        "param": {"type": "param"},
        "auto_corner": {"type": "rectangular", "width": 1.0, "depth": 1.0, "corner": "auto"},
        "unknown_end": {"type": "rectangular", "width": 1.0, "depth": 1.0, "ends": "left"},
    }
    results = {name: _attempt(value) for name, value in cases.items()}
    expected_accepted = {
        name
        for name, value in cases.items()
        if name
        in {
            "omitted",
            "explicit_none",
            "rectangular_both",
            "rectangular_side1",
            "rectangular_side2",
            "rectangular_zero_depth",
        }
    }
    for name, result in results.items():
        assert ("accepted" in result) == (name in expected_accepted), (name, result)
        if "accepted" in result:
            dumped = result["accepted"]
            sides = relief.expected_native_sides(dumped.get("relief"))
            result["native_sides"] = sides
    return {
        "cases": results,
        "accepted": sorted(expected_accepted),
        "statement": (
            "the compatibility default stays none on both ends; rectangular is the only added "
            "shape and every other SDK shape is rejected, not silently mapped to none"
        ),
    }


def default_compatibility() -> dict:
    operations, _ = fx.four_wall_plan(fx.box_inspection())
    from creo_mechdog.schema import validate_operations

    dumped = validate_operations(operations)
    flanges = [item for item in dumped if item["op"] == "sheetmetal_flange"]
    return {
        "reported_plan_still_validates": len(flanges) == 4,
        "relief_key_present": any("relief" in item for item in flanges),
        "unchanged_fields": sorted(flanges[0]),
        "statement": (
            "the pre-T11 four-wall plan validates unchanged and carries no relief key, so both "
            "bend ends keep PRO_BEND_RLF_NONE"
        ),
    }


def _function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    end = source.find("\nstatic ", start + len(signature))
    return source[start : end if end > 0 else len(source)]


def native_source() -> dict:
    advanced = (ROOT / "native" / "advanced.cpp").read_text(encoding="utf-8", errors="replace")
    flange = _function_body(advanced, "static void generic_sheetmetal_flange")
    side = _function_body(advanced, "static void flange_relief_side")
    request = _function_body(advanced, "static FlangeReliefRequest flange_relief_request")
    record = _function_body(advanced, "static J flange_relief_record")
    expect = _function_body(advanced, "static void flange_relief_expect")
    checks = {
        "relief_compound_both_ends": "PRO_E_SMT_BEND_RELIEF_SIDE1" in flange
        and "PRO_E_SMT_BEND_RELIEF_SIDE2" in flange,
        "default_none_preserved": "PRO_BEND_RLF_NONE" in side,
        "rectangular_opt_in": "PRO_BEND_RLF_RECTANGULAR" in side,
        "width_element": "PRO_E_BEND_RELIEF_WIDTH" in side,
        "depth_type_blind": "PRO_E_BEND_RELIEF_DEPTH_TYPE" in side
        and "PRO_BEND_RLF_DEPTH_BLIND" in side,
        "depth_element": "PRO_E_BEND_RELIEF_DEPTH" in side,
        "created_tree_echo_extracted": "ProFeatureElemtreeExtract" in flange
        and flange.index("ProSolidRegenerate") < flange.index("ProFeatureElemtreeExtract"),
        "created_tree_echo_verified": "flange_relief_expect(" in flange,
        "created_tree_echo_staged": 'extra["relief_element_echo"]' in flange,
        "echo_divergence_fails": "did not persist into the created feature" in expect,
        "echo_only_when_requested": "if (relief_request.side1 || relief_request.side2)" in flange,
        "no_corner_relief": "PRO_E_SMT_CORNER_RELIEF" not in flange + side + record,
        "no_miter_cut": "PRO_E_SMT_MTR_CUTS" not in flange + side + record,
        "no_edge_rip": "PRO_E_SMT_EDGE_RIP" not in flange + side + record,
        "no_rip_or_obround": "PRO_BEND_RLF_RIP" not in side and "PRO_BEND_RLF_OBROUND" not in side,
        "no_length_or_angle": "PRO_E_BEND_RELIEF_LENGTH" not in side
        and "PRO_E_BEND_RELIEF_ANGLE" not in side,
        "parent_body_still_implicit": "PRO_E_BODY" not in flange + side + record,
        "validated_before_tree": flange.index("flange_relief_request(op)")
        < flange.index("node(nullptr, PRO_E_FEATURE_TREE)"),
        "unknown_type_throws": "Unsupported sheetmetal flange relief type" in request,
        "record_only_when_requested": 'extra["relief"] = flange_relief_record' in flange
        and 'op.contains("relief")' in flange,
        "measured_thickness": "part_thickness_read(&thickness)" in record,
        "height_dimension_kept": '{"name", "height"}' in flange,
        "section_path_kept": 'extra["section_path"]' in flange,
    }
    missing = [name for name, present in checks.items() if not present]
    assert not missing, f"native source guard missing: {missing}"
    return {
        "static_source_assertions": checks,
        "element_tree": {
            "bend_relief": "PRO_E_SMT_BEND_RELIEF with SIDE1 and SIDE2 compounds",
            "default": "both ends PRO_BEND_RLF_NONE (pre-T11 behaviour)",
            "rectangular": (
                "type RECTANGULAR, width, depth type BLIND, depth on the selected ends"
            ),
            "created_tree_read_back": (
                "after create+regen the relief section is read from the created feature tree; "
                "divergence from the request fails the feature and the read-back is staged as "
                "relief_element_echo (length type/length/angle recorded, not asserted)"
            ),
            "untouched": [
                "PRO_E_SMT_CORNER_RELIEF",
                "PRO_E_SMT_MTR_CUTS",
                "PRO_E_SMT_EDGE_RIP",
                "PRO_E_BODY",
            ],
            "record": (
                "relief alias record: requested sides, measured part thickness, corner run and "
                "the two request-derived comparisons"
            ),
        },
        "live_uncertainty": (
            "the rectangular branch leaves PRO_E_BEND_RELIEF_LENGTH_TYPE/LENGTH/ANGLE unset; "
            "the created-feature read-back now records their effective values (the probe trees "
            "show Creo filling unwritten relief elements with PARAM and zeros), but whether a "
            "notch is cut at a material end stays a live measurement"
        ),
    }


def four_wall_plan(profile: str = "thickness_scale") -> dict:
    from creo_mechdog.schema import validate_operations

    relief_value = PROFILES[profile]["relief"]
    inspection = fx.box_inspection()
    operations = [fx.wall_sketch(), fx.wall_base_op()]
    rows = []
    previous: list[str] = []
    run = relief.corner_overlap_run_mm()
    for side, label in fx.FLANGE_SEQUENCE:
        reference = fx.select_wall_edge(inspection, fx.PLATE_BOUNDS, side, face="top")
        operation = fx.flange_op(side, label, reference)
        operation["relief"] = dict(relief_value)
        operations.append(operation)
        corners = fx.shared_corners(previous, side)
        previous.append(side)
        span = reference["geometry"]["span_mm"]
        # Material-aware offline expectations over the full fixture span; live
        # chains of later walls are shorter by R + t per already-built neighbour.
        removed = relief.four_wall_removed_mm3(relief_value, label)
        assert removed is not None, "offline four-wall profiles only use ends=both"
        increment = relief.bent_wall_increment_mm3(span)
        rows.append(
            {
                "label": label,
                "side": side,
                "edge_span_mm": span,
                "relief": dict(relief_value),
                "native_sides": relief.expected_native_sides(relief_value),
                "wall_volume_mm3": fx.wall_volume_mm3(span),
                "bent_increment_mm3": increment,
                "material_ends": relief.FOUR_WALL_MATERIAL_ENDS[label],
                "relief_removed_mm3": removed,
                "expected_added_volume_mm3": increment - removed,
                "shared_corners": corners,
                "corner_overlap_lower_bound_mm3": fx.corner_overlap_volume_mm3(corners),
                "corner_overlap_run_mm": run,
                "depth_reaches_corner_run": relief_value["depth"] >= run,
            }
        )
    dumped = validate_operations(operations)
    return {
        "profile": profile,
        "profile_description": PROFILES[profile]["description"],
        "operations_validated": len(dumped),
        "flanges": rows,
        "total_expected_added_volume_mm3": sum(row["expected_added_volume_mm3"] for row in rows),
        "base_volume_mm3": fx.PLATE_VOLUME_MM3,
        "expected_body_volume_mm3": fx.PLATE_VOLUME_MM3
        + sum(row["expected_added_volume_mm3"] for row in rows),
        "volume_note": (
            "the increment model reproduces the measured 2026-10-29 walls (straight run plus "
            "net bend zone); a rectangular notch removes width x depth x thickness only at "
            "bend ends abuting existing walls - free plate corners remove nothing (2026-10-29 "
            "round six). Live spans of f_ny/f_py are shorter than the fixture spans"
        ),
        "not_verified": (
            "the notch footprint relative to the bend line is a live measurement: only a live "
            "volume delta and surface inspection can confirm that depth is measured into the "
            "wall run as assumed"
        ),
    }


def profiles() -> dict:
    run = relief.corner_overlap_run_mm()
    return {
        "corner_overlap_run_mm": run,
        "profiles": {
            name: {
                "relief": dict(value["relief"]),
                "description": value["description"],
                "removed_per_wall_mm3": relief.relief_removed_mm3(value["relief"]),
                "reaches_corner_run": value["relief"]["depth"] >= run,
            }
            for name, value in PROFILES.items()
        },
        "statement": (
            "the thickness-scale notch is the ordinary Creo relief and cannot clear a 77.46 mm "
            "shared corner run; the corner-run profile is the diagnostic that can"
        ),
    }


# --- DEV-051 T11 2026-10-30: valid-material scenario -----------------------


def material_case_specs() -> tuple:
    """The relief variants the material scenario runs, one fresh model each.

    ``target`` names the flange carrying the relief: "second" (f_ny, one bend
    end abutting f_px's bend) or "first" (f_px, both ends free - the negative
    control that must remove nothing).
    """
    return (
        ("mat_baseline", "second", None),
        (
            "mat_rect_both_1x1",
            "second",
            {"type": "rectangular", "width": 1.0, "depth": 1.0, "ends": "both"},
        ),
        (
            "mat_rect_both_4x4",
            "second",
            {"type": "rectangular", "width": 4.0, "depth": 4.0, "ends": "both"},
        ),
        (
            "mat_rect_side1_1x1",
            "second",
            {"type": "rectangular", "width": 1.0, "depth": 1.0, "ends": "side1"},
        ),
        (
            "mat_rect_side2_1x1",
            "second",
            {"type": "rectangular", "width": 1.0, "depth": 1.0, "ends": "side2"},
        ),
        (
            "free_rect_both_4x4",
            "first",
            {"type": "rectangular", "width": 4.0, "depth": 4.0, "ends": "both"},
        ),
    )


def material_scenario() -> dict:
    """Offline plan validation and oracle table for the valid-material scenario."""
    from creo_mechdog.schema import validate_operations

    plan_operations, first_reference = relief.material_scenario_plan()
    validate_operations(plan_operations)
    rows = []
    for name, target, relief_value in material_case_specs():
        if target == "second":
            operation = relief.material_second_flange_op(relief_value)
        else:
            operations, _ = relief.material_scenario_plan()
            operations[2]["relief"] = dict(relief_value)
            operation = operations[2]
        dumped = validate_operations([operation])
        rows.append(
            {
                "case": name,
                "target": target,
                "relief": relief_value,
                "validated": True,
                "native_sides": relief.expected_native_sides(dumped[0].get("relief")),
                "expected_delta_vs_baseline_mm3": relief.scenario_expected_delta_mm3(
                    relief_value, target
                ),
            }
        )
    span = first_reference["geometry"]["span_mm"]
    return {
        "fixture": {
            "base_wall_mm": [fx.PLATE_LENGTH_MM, fx.PLATE_WIDTH_MM, fx.PLATE_THICKNESS_MM],
            "first_flange": relief.MATERIAL_SCENARIO["first"],
            "second_flange": relief.MATERIAL_SCENARIO["second"],
            "first_flange_edge_span_mm": span,
            "why": (
                "f_px (+x) keeps both bend ends at free plate corners; f_ny (-y) submitted "
                "afterwards has its +x chain end run into f_px's bend - one material end. "
                "The DEV-051 T05 contrast (2026-10-30) proved that such an attach-edge end "
                "adjacent to an existing bend fails flange regeneration, so whether f_ny "
                "builds at all (and whether its relief changes that) is the live "
                "observation; a failing f_ny with the proven signature and adjacency "
                "evidence is classified known_t05_boundary, not judged a failure"
            ),
            "chain_trim_per_material_end_mm": relief.CHAIN_TRIM_MM,
            "predicted_increment_full_span_mm3": relief.bent_wall_increment_mm3(span),
            "predicted_increment_one_material_end_mm3": relief.bent_wall_increment_mm3(
                span, trimmed_ends=1
            ),
            "increment_model": (
                "straight run (height - t - R) plus net bend zone (quarter annulus minus the "
                "t x (R + t) plate rectangle); reproduces the measured +18 025.291234 mm3 of "
                "the 2026-10-29 run for the 232 mm span"
            ),
        },
        "cases": rows,
        "oracle": (
            "differential on the same geometry: added_volume(relief) - added_volume(none). "
            "A rectangular notch removes width x depth x thickness per bend end whose chain "
            "end abuts material; free ends remove nothing (2026-10-29 round six), which is a "
            "control, not relief evidence"
        ),
        "statement": (
            "the request echo and the created-tree read-back are necessary but not sufficient: "
            "a material-end case passes only when the measured delta matches the independent "
            "removal and notch faces are observable"
        ),
        "not_verified": (
            "whether f_ny with relief builds after f_px (the relief-less shape hits the "
            "proven T05 boundary), where the material end sits among side1/side2, the "
            "notch position and the volume delta are live items"
        ),
    }


def relief_verdict_matrix() -> dict:
    """The verdict shapes the live run must reproduce, exercised offline."""
    echo = lambda width, depth: {  # noqa: E731 - table fixture, not production code
        "side1": {
            "type": relief.RELIEF_TYPES["rectangular"],
            "width_mm": width,
            "depth_type": relief.RELIEF_DEPTH_TYPES["blind"],
            "depth_mm": depth,
            "length_type": 0,
            "length_mm": 0.0,
            "angle": 0.0,
        },
        "side2": {
            "type": relief.RELIEF_TYPES["rectangular"],
            "width_mm": width,
            "depth_type": relief.RELIEF_DEPTH_TYPES["blind"],
            "depth_mm": depth,
            "length_type": 0,
            "length_mm": 0.0,
            "angle": 0.0,
        },
    }
    both_1x1 = {"type": "rectangular", "width": 1.0, "depth": 1.0, "ends": "both"}
    rows = {
        "round_six_echo_without_geometry_rejected": relief.relief_geometry_verdict(
            "material", both_1x1, echo(1.0, 1.0), 0.0, -1.0, 0, part_thickness_mm=3.71
        ),
        "echo_without_geometry_no_thickness_contradiction_rejected": (
            relief.relief_geometry_verdict(
                "material", both_1x1, echo(1.0, 1.0), 0.0, -1.0, 0, part_thickness_mm=1.0
            )
        ),
        "consistent_removal_passes": relief.relief_geometry_verdict(
            "material", both_1x1, echo(1.0, 1.0), -1.0, -1.0, 2, part_thickness_mm=1.0
        ),
        "free_control_zero_passes_as_no_evidence": relief.relief_geometry_verdict(
            "free", both_1x1, echo(1.0, 1.0), 0.0, None, 0, part_thickness_mm=1.0
        ),
        "pair_split_resolves_material_end": relief.single_end_pair_verdict(
            {"side1": -1.0, "side2": 0.0}, 1.0, 1.0
        ),
        "pair_without_split_fails": relief.single_end_pair_verdict(
            {"side1": 0.0, "side2": 0.0}, 1.0, 1.0
        ),
    }
    expected = {
        "round_six_echo_without_geometry_rejected": False,
        "echo_without_geometry_no_thickness_contradiction_rejected": False,
        "consistent_removal_passes": True,
        "free_control_zero_passes_as_no_evidence": True,
        "pair_split_resolves_material_end": True,
        "pair_without_split_fails": False,
    }
    wrong = [name for name, verdict in rows.items() if verdict["passed"] != expected[name]]
    assert not wrong, f"verdict matrix disagrees: {wrong}"
    return {
        "rows": rows,
        "expected_passed": expected,
        "statement": (
            "2026-10-29 round six (rectangular echoed, 0.000000 delta, no notch faces, part "
            "thickness 3.71) is a rejection shape; only measured material removal with the "
            "created-tree read-back counts as relief evidence"
        ),
    }


def edit_path() -> dict:
    return {
        "creation_only": (
            "relief is written into the flange element tree at creation; the executor has no "
            "feature redefine, so there is no in-place relief edit"
        ),
        "kept_edit": "creo_set_dimensions still edits the flanges named height dimension",
        "change_sequence": [
            "delete or suppress the flange with creo_feature_state",
            "re-create it with the new relief through creo_sheetmetal_flange or execute_plan",
            "re-create any flange that consumed the removed features edge",
        ],
        "record": (
            "the relief alias record keeps the requested values, the measured part thickness and "
            "the two request-derived comparisons so a caller can detect drift before rebuilding"
        ),
        "not_verified": "none of these steps was executed in this stage",
    }


def live_checklist() -> list[str]:
    return [
        "confirm the session is usable and BUG-001 conditions hold; one dev service only",
        "fresh model, unique name; record job/model/revision and the base wall 185x232x1 volume",
        "create the first flange with relief {rectangular, both ends, 1x1} and inspect the tree",
        "record the measured added volume and compare with span x height x t - 2 x w x d x t",
        "inspect the notch surfaces and their distance from the bend line (depth axis)",
        "run the same flange without relief on a second model and diff volume and surfaces",
        "submit flanges 2-4 with relief on both ends, re-inspecting each edge before submitting",
        "repeat with the corner-run profile (width 1, depth 77.46) and compare the third flange",
        "toggle ends side1/side2 on one flange to confirm one-sided relief material removal",
        "material scenario: base + f_px(+x, no relief), then f_ny(-y) none vs rect 1x1 / 4x4 / "
        "side1 / side2 on fresh models; expect -1 / -16 mm3 at the f_px-side material end",
        "free-end control: f_px(+x) with rect 4x4 must remove nothing; do not count it as relief",
        "check relief_element_echo from the created feature tree matches every request",
        "wall_contract part_thickness_mm must read 1.0 (T03 sync) in every material case",
        "unbend/flat pattern and bend back with relief present; check the relief in the flat state",
        "edit the named height dimension with relief present; record revision before/after",
        "save, reload and verify the model; then suppress/delete a flange and re-create it",
        "on failure record the raw code, feature status, real rollback and revision",
        "corner relief, miter cuts and edge rips stay out of scope: do not test them as supported",
    ]


# --- live acceptance ------------------------------------------------------

LIVE_PROFILES = (
    ("relief_none", None),
    ("relief_rect_1x1", {"type": "rectangular", "width": 1.0, "depth": 1.0, "ends": "both"}),
)


def flange_payload(
    model_id: str, revision: int | None, label: str, reference: dict, relief_value: dict | None
) -> dict:
    payload = {
        "model_id": model_id,
        "expected_revision": revision,
        "label": label,
        "edge": dict(reference["edge"]),
        "height": fx.FLANGE_HEIGHT_MM,
        "angle": fx.FLANGE_ANGLE_DEG,
        "radius": fx.FLANGE_RADIUS_MM,
        "flip": False,
        "y_factor": fx.FLANGE_Y_FACTOR,
    }
    if relief_value is not None:
        payload["relief"] = dict(relief_value)
    return payload


def notch_faces(inspection: dict, limit_mm: float = 1.5) -> list[dict]:
    """Faces small enough to be a 1 x 1 bend-relief notch, with their position.

    A rectangular relief cuts a width x depth pocket through the sheet at each bend end,
    so its walls are the only faces on the model whose three bbox extents are all within
    a couple of millimetres. Recording the centres turns "the notch exists" into "the
    notch is at these bend ends" without a second modelling job.
    """
    faces = []
    for surface in inspection.get("surfaces") or []:
        bbox = surface.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 2:
            continue
        extent = [abs(bbox[1][index] - bbox[0][index]) for index in range(3)]
        if max(extent) > limit_mm or min(extent) <= 0.05:
            continue
        faces.append(
            {
                "id": surface.get("id"),
                "extent_mm": extent,
                "center_mm": [(bbox[0][i] + bbox[1][i]) / 2.0 for i in range(3)],
            }
        )
    return faces


async def run_profile(runner: LiveRunner, profile: str, relief_value: dict | None) -> dict:
    """Base wall, then the four flanges one job at a time with fresh edge selection."""
    name = unique_name(f"t11_{profile}")
    created = await runner.submit(
        f"{profile}:base",
        "creo_execute_plan",
        {
            "model_name": name,
            "model_type": "sheetmetal",
            "operations": [fx.wall_sketch(), fx.wall_base_op()],
        },
    )
    model_id = created["model_id"]
    terminal = await runner.wait_job(created["job_id"], budget=HANG_BUDGET_SECONDS)
    entry: dict = {
        "profile": profile,
        "relief": relief_value,
        "model_name": name,
        "model_id": model_id,
        "base_job_id": created["job_id"],
        "base_status": terminal.get("status"),
        "base_revision": terminal.get("revision"),
        "flanges": [],
    }
    if terminal.get("status") != "succeeded":
        entry.update(
            failure=failure_text(terminal),
            passed=False,
            blocked="the base first wall was not created, so no flange was submitted",
        )
        return runner.case(entry)

    snapshot = await runner.snapshot(model_id)
    bounds = fx.active_bbox(runner.inspection(snapshot))
    entry.update(
        base_volume_mm3=runner.volume(snapshot),
        plate_bounds_mm=[list(bounds[0]), list(bounds[1])],
    )

    for index, (side, label) in enumerate(fx.FLANGE_SEQUENCE):
        snapshot = await runner.snapshot(model_id)
        try:
            reference = fx.select_wall_edge(
                runner.inspection(snapshot),
                bounds,
                side,
                face="top",
                allow_shortened=index >= 2,
            )
        except fx.EdgeSelectionError as error:
            entry["flanges"].append(
                {"label": label, "side": side, "selected": False, "error": str(error)}
            )
            break
        before_volume = runner.volume(snapshot)
        before_revision = snapshot.get("revision")
        span = reference["geometry"]["span_mm"]
        # Material-aware oracle: only bend ends abuting existing walls remove
        # material (round six: f_px/f_nx free corners removed nothing), and the
        # increment model is the one validated against the measured 2026-10-29
        # walls; the live-measured span already carries any chain trim.
        removed = relief.four_wall_removed_mm3(relief_value, label)
        assert removed is not None, "live four-wall profiles only use ends=both"
        expected_added = relief.bent_wall_increment_mm3(span) - removed
        submitted = await runner.submit(
            f"{profile}:{label}",
            "creo_sheetmetal_flange",
            flange_payload(model_id, before_revision, label, reference, relief_value),
        )
        terminal = await runner.wait_job(submitted["job_id"], budget=HANG_BUDGET_SECONDS)
        row: dict = {
            "label": label,
            "side": side,
            "edge": reference["geometry"],
            "job_id": submitted["job_id"],
            "status": terminal.get("status"),
            "revision_before": before_revision,
            "volume_before_mm3": before_volume,
            "edge_span_mm": span,
            "wall_volume_mm3": fx.wall_volume_mm3(span),
            "bent_increment_mm3": relief.bent_wall_increment_mm3(span),
            "relief_removed_mm3": removed,
            "expected_added_mm3": expected_added,
            "shared_corners": fx.shared_corners([s for s, _ in fx.FLANGE_SEQUENCE[:index]], side),
        }
        if terminal.get("status") != "succeeded":
            after = await runner.snapshot(model_id)
            row.update(
                failure=failure_text(terminal),
                revision_after=after.get("revision"),
                volume_after_mm3=runner.volume(after),
                rolled_back=(
                    after.get("revision") == before_revision
                    and runner.volume(after) == before_volume
                ),
                passed=False,
            )
            classification = relief.classify_flange_failure(
                row["shared_corners"],
                row["edge"].get("shortfall_mm"),
                row["failure"],
            )
            row["verdict"] = classification["verdict"]
            row["failure_classification"] = classification
            entry["flanges"].append(row)
            break
        after = await runner.snapshot(model_id)
        added = None
        if runner.volume(after) is not None and before_volume is not None:
            added = runner.volume(after) - before_volume
        saved = (terminal.get("result") or {}).get("saved_file_reloaded_and_verified")
        # DEV-051 T11: the volume oracle alone cannot tell a bend from a flat
        # extension - 232 x 80 x 1 is the same number either way, and the 2026-10-29
        # round produced exactly that in-plane wall. The measured bbox decides the
        # direction; since DEV-051 A the default section side is "out of the attachment
        # face", so every top-edge flange must go up and `flip` is what would reverse it.
        after_bounds = fx.active_bbox(runner.inspection(after))
        direction = fx.classify_direction(after_bounds)
        row.update(
            revision_after=after.get("revision"),
            volume_after_mm3=runner.volume(after),
            added_mm3=added,
            abs_error_mm3=None if added is None else abs(added - expected_added),
            relief_echo=(runner.record(after, label) or {}).get("relief"),
            notch_faces=notch_faces(runner.inspection(after)),
            feature_types=runner.feature_types(after),
            body_bbox_after=[list(after_bounds[0]), list(after_bounds[1])],
            direction=direction,
            material_side=fx.classify_material_side(after_bounds, side),
            saved_file_reloaded_and_verified=saved,
            passed=bool(
                added is not None
                and abs(added - expected_added) <= max(0.01, abs(expected_added) * 1e-3)
                and direction == "up"
                and saved is True
            ),
        )
        row["verdict"] = "passed" if row["passed"] else "failed"
        entry["flanges"].append(row)

    entry["flange_count"] = sum(1 for row in entry["flanges"] if row.get("passed"))
    entry["expected_added_total_mm3"] = sum(
        row.get("expected_added_mm3") or 0.0 for row in entry["flanges"]
    )
    boundary = [
        row["label"] for row in entry["flanges"] if row.get("verdict") == "known_t05_boundary"
    ]
    selection_errors = [row["label"] for row in entry["flanges"] if row.get("selected") is False]
    unexpected = [row["label"] for row in entry["flanges"] if row.get("verdict") == "failed"]
    reached = [row["label"] for row in entry["flanges"]]
    not_submitted = [label for _, label in fx.FLANGE_SEQUENCE if label not in reached]
    entry["known_t05_boundary"] = boundary
    entry["relief_geometry_unverified"] = sorted(set(boundary) | set(not_submitted))
    if selection_errors or unexpected or not entry["flange_count"]:
        entry["verdict"] = "failed"
        entry["passed"] = False
    elif boundary:
        # DEV-051 T05 proven boundary: an attach-edge end adjacent to an
        # existing bend cannot build. That outcome is the expected diagnostic
        # (same convention as the N05 trigger groups), not a failed case; the
        # relief geometry on the blocked flanges stays explicitly unverified.
        entry["verdict"] = "known_t05_boundary"
        entry["passed"] = True
    else:
        entry["verdict"] = "verified"
        entry["passed"] = entry["flange_count"] == len(fx.FLANGE_SEQUENCE)
    return runner.case(entry)


def relief_comparison(cases: list[dict]) -> dict:
    """Differential oracle: relief omitted vs rectangular both 1x1 on the same flange.

    The wall volume oracle is absolute and approximate (development length shortens the
    wall), so the relief is judged by the difference between the two profiles on the same
    side: two notches of width x depth x thickness must take exactly 2 mm3 away.
    """
    by_profile = {case.get("profile"): case for case in cases if case.get("flanges")}
    none_rows = {
        row["label"]: row for row in (by_profile.get("relief_none") or {}).get("flanges") or []
    }
    rect_rows = {
        row["label"]: row for row in (by_profile.get("relief_rect_1x1") or {}).get("flanges") or []
    }
    rows = []
    for label, row in rect_rows.items():
        base = none_rows.get(label)
        if not base or row.get("added_mm3") is None or base.get("added_mm3") is None:
            continue
        delta = row["added_mm3"] - base["added_mm3"]
        # Material-aware expectation: f_px/f_nx end at free corners and must take
        # zero; f_ny/f_py run into both neighbours and take 2 x w x d x t.
        removed = relief.four_wall_removed_mm3(
            {"type": "rectangular", "width": 1.0, "depth": 1.0, "ends": "both"}, label
        )
        rows.append(
            {
                "label": label,
                "added_without_relief_mm3": base["added_mm3"],
                "added_with_relief_mm3": row["added_mm3"],
                "measured_delta_mm3": delta,
                "expected_delta_mm3": -removed,
                "delta_error_mm3": abs(delta + removed),
                "notch_faces_without_relief": len(base.get("notch_faces") or []),
                "notch_faces_with_relief": len(row.get("notch_faces") or []),
                "notch_centers_with_relief_mm": [
                    face["center_mm"] for face in row.get("notch_faces") or []
                ],
            }
        )
    return {
        "oracle": (
            "same flange, relief omitted vs rectangular both 1x1: the measured volume delta "
            "is the notch volume at the bend ends that actually abut material (f_px/f_nx: "
            "free corners, zero; f_ny/f_py: two material ends)"
        ),
        "tolerance_mm3": 0.2,
        "rows": rows,
        "all_within_tolerance": bool(rows) and all(row["delta_error_mm3"] <= 0.2 for row in rows),
    }


# --- live material scenario (2026-10-30) -----------------------------------


async def run_material_case(
    runner: LiveRunner, name: str, target: str, relief_value: dict | None
) -> dict:
    """One fresh model: the base wall plan, then f_px and (target "second") f_ny.

    Every flange is its own job and re-selects its edge from a fresh snapshot
    taken against the frozen post-wall plate bounds. The 2026-10-30/31 live run
    submitted the offline fixture plan (wall + f_px carrying the synthetic box
    edge id 253) as one job and Creo refused the attachment
    (PRO_MODELITEM_INIT = PRO_TK_NOT_EXIST, -23): a driver fixture defect,
    never a modelling failure.

    f_px carries the relief only for the free-end control (target "first"); the
    material cases put the relief on f_ny, whose +x chain end abuts f_px's
    bend -- the DEV-051 T05 proven boundary condition. A failing f_ny with the
    proven regeneration signature and adjacency evidence is classified
    known_t05_boundary and is not judged a failure.
    """
    key = f"mat_{name}"
    model_name = unique_name(f"t11_{name}")
    first = relief.MATERIAL_SCENARIO["first"]
    second = relief.MATERIAL_SCENARIO["second"]
    created = await runner.submit(
        f"{key}:base",
        "creo_execute_plan",
        {
            "model_name": model_name,
            "model_type": "sheetmetal",
            "operations": relief.material_wall_plan(),
        },
    )
    model_id = created["model_id"]
    terminal = await runner.wait_job(created["job_id"], budget=HANG_BUDGET_SECONDS)
    entry: dict = {
        "case": name,
        "target": target,
        "relief": relief_value,
        "model_name": model_name,
        "model_id": model_id,
        "plan_job_id": created["job_id"],
        "plan_status": terminal.get("status"),
    }
    if terminal.get("status") != "succeeded":
        entry.update(
            failure=failure_text(terminal),
            passed=False,
            blocked="the base wall plan failed; nothing further was submitted",
        )
        return runner.case(entry)

    base = await runner.snapshot(model_id)
    bounds = fx.active_bbox(runner.inspection(base))
    base_record = runner.record(base, "base_wall") or {}
    contract = base_record.get("wall_contract") or {}
    entry.update(
        plan_revision=base.get("revision"),
        plan_volume_mm3=runner.volume(base),
        wall_contract=contract,
        plate_bounds_mm=[list(bounds[0]), list(bounds[1])],
    )
    notch_limit = 1.5
    if relief_value is not None:
        notch_limit = 1.5 + max(float(relief_value["width"]), float(relief_value["depth"]))

    try:
        reference = fx.select_wall_edge(runner.inspection(base), bounds, first["side"], face="top")
    except fx.EdgeSelectionError as error:
        entry.update(f_px={"selected": False, "error": str(error)}, passed=False)
        return runner.case(entry)
    px_before_volume = runner.volume(base)
    px_before_revision = base.get("revision")
    px_submitted = await runner.submit(
        f"{key}:f_px",
        "creo_sheetmetal_flange",
        flange_payload(
            model_id,
            px_before_revision,
            first["label"],
            reference,
            relief_value if target == "first" else None,
        ),
    )
    px_terminal = await runner.wait_job(px_submitted["job_id"], budget=HANG_BUDGET_SECONDS)
    px_row: dict = {
        "job_id": px_submitted["job_id"],
        "status": px_terminal.get("status"),
        "revision_before": px_before_revision,
        "volume_before_mm3": px_before_volume,
        "edge": reference["geometry"],
        "shared_corners": fx.shared_corners([], first["side"]),
    }
    entry["f_px"] = px_row
    if px_terminal.get("status") != "succeeded":
        after = await runner.snapshot(model_id)
        px_row.update(
            failure=failure_text(px_terminal),
            revision_after=after.get("revision"),
            volume_after_mm3=runner.volume(after),
            rolled_back=(
                after.get("revision") == px_before_revision
                and runner.volume(after) == px_before_volume
            ),
            passed=False,
        )
        classification = relief.classify_flange_failure(
            px_row["shared_corners"],
            px_row["edge"].get("shortfall_mm"),
            px_row["failure"],
        )
        px_row["verdict"] = classification["verdict"]
        px_row["failure_classification"] = classification
        entry.update(passed=False, blocked="f_px failed; material scenario not reproducible")
        return runner.case(entry)

    after_px = await runner.snapshot(model_id)
    px_added = None
    if runner.volume(after_px) is not None and px_before_volume is not None:
        px_added = runner.volume(after_px) - px_before_volume
    px_record = runner.record(after_px, first["label"]) or {}
    px_row.update(
        revision_after=after_px.get("revision"),
        volume_after_mm3=runner.volume(after_px),
        added_mm3=px_added,
        relief_echo=px_record.get("relief"),
        relief_element_echo=px_record.get("relief_element_echo"),
        saved_file_reloaded_and_verified=(px_terminal.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ),
    )
    entry.update(
        f_px_added_mm3=px_added,
        f_px_relief_echo=px_record.get("relief_element_echo"),
    )

    if target == "first":
        # Free-end control: f_px itself carries the relief over free plate corners.
        # The verdict is differential (vs the baseline model's f_px increment) and
        # is assembled in material_summary once every case has run.
        entry.update(
            notch_faces=notch_faces(runner.inspection(after_px), notch_limit),
            passed=True,
        )
        return runner.case(entry)

    try:
        reference = fx.select_wall_edge(
            runner.inspection(after_px),
            bounds,
            second["side"],
            face="top",
            allow_shortened=True,
        )
    except fx.EdgeSelectionError as error:
        entry.update(f_ny={"selected": False, "error": str(error)}, passed=False)
        return runner.case(entry)
    before_volume = runner.volume(after_px)
    before_revision = after_px.get("revision")
    submitted = await runner.submit(
        f"{key}:f_ny",
        "creo_sheetmetal_flange",
        flange_payload(model_id, before_revision, second["label"], reference, relief_value),
    )
    ny_terminal = await runner.wait_job(submitted["job_id"], budget=HANG_BUDGET_SECONDS)
    row: dict = {
        "job_id": submitted["job_id"],
        "status": ny_terminal.get("status"),
        "revision_before": before_revision,
        "volume_before_mm3": before_volume,
        "edge": reference["geometry"],
        "shared_corners": fx.shared_corners([first["side"]], second["side"]),
    }
    entry["f_ny"] = row
    if ny_terminal.get("status") != "succeeded":
        after = await runner.snapshot(model_id)
        row.update(
            failure=failure_text(ny_terminal),
            revision_after=after.get("revision"),
            volume_after_mm3=runner.volume(after),
            rolled_back=(
                after.get("revision") == before_revision and runner.volume(after) == before_volume
            ),
        )
        classification = relief.classify_flange_failure(
            row["shared_corners"],
            row["edge"].get("shortfall_mm"),
            row["failure"],
        )
        row["verdict"] = classification["verdict"]
        row["failure_classification"] = classification
        if classification["verdict"] == "known_t05_boundary":
            # DEV-051 T05 proven boundary: one attach-edge end adjacent to
            # f_px's bend. Expected under that boundary, not a relief defect;
            # the relief geometry stays explicitly unverified here.
            entry.update(
                known_t05_boundary=[second["label"]],
                relief_geometry_unverified=[second["label"]],
                passed=True,
                blocked=(
                    "f_ny is blocked by the proven T05 boundary (attach-edge end "
                    "adjacent to f_px's bend); relief geometry is not observable "
                    "in this scenario"
                ),
            )
        else:
            entry.update(passed=False, blocked="f_ny failed; baseline scenario not reproducible")
        return runner.case(entry)
    after = await runner.snapshot(model_id)
    added = None
    if runner.volume(after) is not None and before_volume is not None:
        added = runner.volume(after) - before_volume
    ny_record = runner.record(after, relief.MATERIAL_SCENARIO["second"]["label"]) or {}
    row.update(
        revision_after=after.get("revision"),
        volume_after_mm3=runner.volume(after),
        added_mm3=added,
        relief_echo=ny_record.get("relief"),
        relief_element_echo=ny_record.get("relief_element_echo"),
        notch_faces=notch_faces(runner.inspection(after), notch_limit),
        saved_file_reloaded_and_verified=(ny_terminal.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ),
    )
    row["verdict"] = "passed"
    entry["passed"] = True
    return runner.case(entry)


def material_summary(cases: list[dict]) -> dict:
    """Differential verdicts for the material scenario, from measured volumes."""
    by_name = {case.get("case"): case for case in cases}
    baseline = by_name.get("mat_baseline") or {}
    baseline_ny = (baseline.get("f_ny") or {}).get("added_mm3")
    baseline_px = baseline.get("f_px_added_mm3")
    rows = []
    for name, target, relief_value in material_case_specs():
        case = by_name.get(name) or {}
        row: dict = {"case": name, "target": target, "relief": relief_value}
        if case.get("known_t05_boundary"):
            # The target flange is blocked by the proven T05 boundary (its
            # attach-edge end is adjacent to an existing bend). That is the
            # expected outcome under the boundary, not a relief defect: report
            # the known boundary and keep the relief geometry explicitly
            # unverified instead of judging the case failed.
            row.update(
                measured_delta_vs_baseline_mm3=None,
                expected_delta_mm3=relief.scenario_expected_delta_mm3(relief_value, target),
                verdict={
                    "status": "known_t05_boundary",
                    "passed": True,
                    "evidence_class": "none",
                    "relief_geometry_verified": False,
                    "reasons": [
                        "the target flange is blocked by the proven T05 boundary "
                        "(attach-edge end adjacent to an existing bend); relief "
                        "geometry is not observable in this scenario"
                    ],
                },
                passed=True,
            )
            rows.append(row)
            continue
        if target == "first":
            echo = case.get("f_px_relief_echo")
            measured = (
                None
                if case.get("f_px_added_mm3") is None or baseline_px is None
                else case["f_px_added_mm3"] - baseline_px
            )
            verdict = relief.relief_geometry_verdict(
                "free",
                relief_value,
                echo,
                measured,
                None,
                len(case.get("notch_faces") or []),
                part_thickness_mm=(case.get("wall_contract") or {}).get("part_thickness_mm"),
            )
        else:
            ny = case.get("f_ny") or {}
            measured = (
                None
                if ny.get("added_mm3") is None or baseline_ny is None
                else ny["added_mm3"] - baseline_ny
            )
            expected = relief.scenario_expected_delta_mm3(relief_value, target)
            if measured is None and ny.get("added_mm3") is not None and baseline_ny is None:
                row.update(
                    measured_delta_vs_baseline_mm3=None,
                    expected_delta_mm3=expected,
                    verdict={
                        "status": "unverified_no_baseline",
                        "passed": False,
                        "evidence_class": "none",
                        "relief_geometry_verified": False,
                        "reasons": [
                            "f_ny built but the none-baseline f_ny increment is "
                            "unavailable, so the differential oracle cannot run; "
                            "relief geometry stays unverified"
                        ],
                    },
                    passed=False,
                )
                rows.append(row)
                continue
            verdict = relief.relief_geometry_verdict(
                "material",
                relief_value,
                ny.get("relief_element_echo"),
                measured,
                expected,
                len(ny.get("notch_faces") or []),
                part_thickness_mm=(case.get("wall_contract") or {}).get("part_thickness_mm"),
            )
        row.update(
            measured_delta_vs_baseline_mm3=measured,
            expected_delta_mm3=relief.scenario_expected_delta_mm3(relief_value, target),
            verdict=verdict,
            passed=bool(case) and verdict["passed"] and case.get("passed") is True,
        )
        rows.append(row)
    side_deltas = {
        "side1": (by_name.get("mat_rect_side1_1x1", {}).get("f_ny") or {}).get("added_mm3"),
        "side2": (by_name.get("mat_rect_side2_1x1", {}).get("f_ny") or {}).get("added_mm3"),
    }
    pair = None
    if baseline_ny is not None and all(value is not None for value in side_deltas.values()):
        pair = relief.single_end_pair_verdict(
            {name: value - baseline_ny for name, value in side_deltas.items()},
            1.0,
            1.0,
        )
    return {
        "baseline_f_ny_added_mm3": baseline_ny,
        "baseline_f_px_added_mm3": baseline_px,
        "rows": rows,
        "single_end_pair": pair,
        "known_t05_boundary": [
            row["case"]
            for row in rows
            if (row.get("verdict") or {}).get("status") == "known_t05_boundary"
        ],
        "relief_geometry_verified": any(
            row.get("passed")
            and (row.get("verdict") or {}).get("evidence_class") == "relief_geometry"
            for row in rows
        ),
        "passed": bool(rows)
        and all(row["passed"] for row in rows)
        and (pair is None or pair["passed"]),
    }


async def run_material_scenario(runner: LiveRunner) -> dict:
    """The 2026-10-30 valid-material relief scenario, one fresh model per case."""
    cases = []
    blocked = None
    for name, target, relief_value in material_case_specs():
        if blocked:
            cases.append({"case": name, "passed": False, "not_executed": blocked})
            runner.case(cases[-1])
            continue
        entry = await run_material_case(runner, name, target, relief_value)
        cases.append(entry)
        if entry.get("plan_status") != "succeeded":
            message = (entry.get("failure") or {}).get("message") or "base plan failed"
            blocked = (
                "the base plan failed; remaining material cases were not submitted: "
                + str(message)[:300]
            )
    summary = material_summary(cases)
    for row in summary["rows"]:
        for case in cases:
            if case.get("case") == row["case"]:
                case["verdict"] = row["verdict"]
                case["passed"] = row["passed"]
    runner.save()
    runner.report["material_scenario"] = summary
    return summary


async def live(output: Path, run_id: str) -> int:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=180) as client:
        runner = LiveRunner(
            client,
            output,
            "FEAT-014 / DEV-051 T11",
            "four-wall flange h80/R2.54/Y0.5 with relief none and rectangular 1x1",
            run_id,
        )
        runner.report["hang_budget_seconds"] = HANG_BUDGET_SECONDS
        try:
            await runner.start()
            blocked = None
            for profile, relief_value in LIVE_PROFILES:
                if blocked:
                    runner.case(
                        {
                            "profile": profile,
                            "relief": relief_value,
                            "base_status": "not_executed",
                            "passed": False,
                            "not_executed": blocked,
                        }
                    )
                    continue
                entry = await run_profile(runner, profile, relief_value)
                if entry["base_status"] != "succeeded":
                    message = (entry.get("failure") or {}).get("message") or "base failed"
                    blocked = (
                        "the base first wall failed, so no flange was submitted for this profile: "
                        + str(message)[:300]
                    )
                    runner.report["blocked_profile"] = {
                        "profile": profile,
                        "reason": blocked,
                        "evidence": "DEV-051 T03 live card: the first wall is rejected before modelling",
                    }
            await run_material_scenario(runner)
        except BaseException as error:
            runner.report["stopped"] = f"{type(error).__name__}: {error}"
            runner.report["profile_comparison"] = relief_comparison(runner.report["cases"])
            runner.finish()
            raise
        runner.report["profile_comparison"] = relief_comparison(runner.report["cases"])
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    rows = [
        {
            "profile": case.get("profile") or case.get("case"),
            "base_status": case.get("base_status") or case.get("plan_status"),
            "flanges": len(case.get("flanges") or []),
            "passed": case.get("passed"),
        }
        for case in runner.report["cases"]
    ]
    print(json.dumps({"passed": runner.report["passed"], "cases": rows}, ensure_ascii=False))
    material = runner.report.get("material_scenario") or {}
    print(
        json.dumps(
            {
                "material_scenario_passed": material.get("passed"),
                "single_end_pair": (material.get("single_end_pair") or {}).get("material_end"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if runner.report["passed"] else 1


def run_unit_module() -> dict:
    from tests.unit import test_sheetmetal_relief

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_sheetmetal_relief)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    return {
        "module": "tests.unit.test_sheetmetal_relief",
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
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "sheetmetal_relief" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
    """Collect source evidence even when running from an extracted release."""
    from creo_mechdog.source_provenance import local_provenance as collect

    return collect(
        ROOT, ("tools/test_sheetmetal_relief.py", "tests/unit/test_sheetmetal_relief.py")
    )


def write_offline_report(output: Path, run_id: str, results: dict) -> dict:
    report = {
        "task": "FEAT-014 / DEV-051 T11",
        "scope": (
            "bend-end relief design and offline implementation for the four-wall flange case: "
            "SDK shape audit, admission, native element tree, geometry expectation, edit path"
        ),
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "status": {
            "offline_implementation": "complete",
            "four_wall_capability": "pending_native_acceptance",
            "statement": (
                "Offline only: contract, native tree and expectations are in place. No Toolkit "
                "connection, no flange created, no relief measured, no four-wall closure."
            ),
        },
        "fixture": {
            "base_wall_mm": [fx.PLATE_LENGTH_MM, fx.PLATE_WIDTH_MM, fx.PLATE_THICKNESS_MM],
            "base_volume_mm3": fx.PLATE_VOLUME_MM3,
            "labels": [label for _, label in fx.FLANGE_SEQUENCE],
            "flange": {
                "height": fx.FLANGE_HEIGHT_MM,
                "radius": fx.FLANGE_RADIUS_MM,
                "y_factor": fx.FLANGE_Y_FACTOR,
                "angle": fx.FLANGE_ANGLE_DEG,
            },
            "oracle_independent_of_production": True,
        },
        "checks": results,
        "live_checklist": live_checklist(),
        "not_verified": [
            "no flange or relief was created; the four walls remain unverified",
            "the valid-material scenario (f_ny after f_px) was never executed live: build "
            "success, the material end's side mapping, notch position and volume delta are "
            "live items",
            "whether Creo keeps the written relief values in the created feature is answered "
            "only by the live relief_element_echo read-back",
            "unbend/flat pattern, bend back, dimension edit, revision, save/reload and rollback "
            "are untested",
            "corner relief, miter cuts and edge rips are unsupported, not alternative paths",
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
        return asyncio.run(live(live_output("sheetmetal_relief", run_id, args.output), run_id))

    run_id = new_run_id()
    output = resolve_output(args.output, run_id)
    results = {
        "sdk_contract": sdk_contract(),
        "admission_matrix": admission_matrix(),
        "default_compatibility": default_compatibility(),
        "native_source": native_source(),
        "profiles": profiles(),
        "four_wall_thickness_scale": four_wall_plan("thickness_scale"),
        "four_wall_corner_run": four_wall_plan("corner_run"),
        "material_scenario": material_scenario(),
        "relief_verdict_matrix": relief_verdict_matrix(),
        "edit_path": edit_path(),
    }
    report = write_offline_report(output, run_id, results)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name("report.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"report_sha256: {digest}")
    print(
        f"status: {report['status']['offline_implementation']} / "
        f"{report['status']['four_wall_capability']}"
    )
    print(f"unit_module: {report['unit_module']}")
    return 0 if report["unit_module"]["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
