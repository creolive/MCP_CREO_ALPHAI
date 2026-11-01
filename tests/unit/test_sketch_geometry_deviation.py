"""Q02 geometry fidelity: post-solve sketch deviation contract (FEAT-010/BUG-049).

Offline regressions for the unified ``geometry_deviation`` result block on
sketch creation and in-place edits, plus the ``geometry_tolerance_mm`` request
parameter. The feedback's approximate reference values (for example the
"correct area 136486.4") are never used as assertions; every oracle here is
computed independently from exact geometry.
"""

import math
import re
import unittest
from pathlib import Path

from creo_mechdog.geometry_deviation import (
    AUTODIM_WARNING_THRESHOLD_MM,
    COORDINATES_DEFAULT_TOLERANCE_MM,
    SAMPLE_LIMIT,
    normalize_geometry_deviation,
    unavailable_geometry_deviation,
    validate_tolerance_mm,
)
from creo_mechdog.profile_diagnostics import analyze_profile
from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Independent analytic fixture: rounded equilateral triangle (3 lines + 3 arcs)
# ---------------------------------------------------------------------------

TRIANGLE_CIRCUMRADIUS_MM = 30.0
FILLET_RADIUS_MM = 8.0
INTERIOR_ANGLE_DEG = 60.0
CORNER_ANGLES_DEG = (90.0, 210.0, 330.0)


def _xy(distance: float, angle_deg: float) -> list[float]:
    a = math.radians(angle_deg)
    return [distance * math.cos(a), distance * math.sin(a)]


def fillet_center(corner_deg: float) -> list[float]:
    """Fillet circle center: interior angle bisector, r/sin(30 deg) from corner."""
    offset = FILLET_RADIUS_MM / math.sin(math.radians(INTERIOR_ANGLE_DEG / 2))
    radius = TRIANGLE_CIRCUMRADIUS_MM - offset
    return _xy(radius, corner_deg)


def tangent_point(corner_deg: float, side_offset_deg: float) -> list[float]:
    """Tangent point shared by the fillet at corner_deg and the adjacent side.

    The side between corners phi and phi+120 has its outward normal at
    phi+60; the foot of the perpendicular from the fillet center is the
    tangent point. side_offset_deg is +60 (next side) or -60 (previous side).
    """
    center = fillet_center(corner_deg)
    foot = _xy(FILLET_RADIUS_MM, corner_deg + side_offset_deg)
    return [center[0] + foot[0], center[1] + foot[1]]


def rounded_triangle_entities() -> list[dict]:
    """Closed 6-entity contour: exact shared endpoints, CCW, mixed lines+arcs."""
    entities = []
    for index, corner in enumerate(CORNER_ANGLES_DEG):
        nxt = CORNER_ANGLES_DEG[(index + 1) % len(CORNER_ANGLES_DEG)]
        entities.append(
            {
                "type": "line",
                "name": f"side_{index}",
                "start": tangent_point(corner, 60.0),
                "end": tangent_point(nxt, -60.0),
            }
        )
        entities.append(
            {
                "type": "arc",
                "name": f"fillet_{index}",
                "center": fillet_center(corner),
                "radius": FILLET_RADIUS_MM,
                "start_angle": corner - 60.0,
                "end_angle": (corner + 60.0) % 360.0,
                "dir": 1,
            }
        )
    return entities


def oracle_area_hexagon_plus_segments() -> float:
    """Shoelace over the tangent-point hexagon plus three circular segments."""
    hexagon = []
    for corner in CORNER_ANGLES_DEG:
        hexagon.append(tangent_point(corner, -60.0))
        hexagon.append(tangent_point(corner, 60.0))
    shoelace = abs(
        sum(
            hexagon[i][0] * hexagon[(i + 1) % len(hexagon)][1]
            - hexagon[(i + 1) % len(hexagon)][0] * hexagon[i][1]
            for i in range(len(hexagon))
        )
    ) / 2
    sweep = math.radians(180.0 - INTERIOR_ANGLE_DEG)
    segment = 0.5 * FILLET_RADIUS_MM**2 * (sweep - math.sin(sweep))
    return shoelace + 3 * segment


def oracle_area_corner_cut() -> float:
    """Triangle area minus three corner pieces (independent closed form)."""
    triangle = (
        3 * TRIANGLE_CIRCUMRADIUS_MM**2 * math.sin(math.radians(120.0)) / 2
    )
    t = FILLET_RADIUS_MM / math.tan(math.radians(INTERIOR_ANGLE_DEG / 2))
    corner_polygon = 0.5 * t * t * math.sin(math.radians(INTERIOR_ANGLE_DEG))
    sweep = math.radians(180.0 - INTERIOR_ANGLE_DEG)
    segment = 0.5 * FILLET_RADIUS_MM**2 * (sweep - math.sin(sweep))
    return triangle - 3 * (corner_polygon - segment)


def oracle_arcs() -> dict[str, dict]:
    arcs = {}
    for index, corner in enumerate(CORNER_ANGLES_DEG):
        arcs[f"fillet_{index}"] = {
            "center": fillet_center(corner),
            "radius": FILLET_RADIUS_MM,
        }
    return arcs


# ---------------------------------------------------------------------------
# Tolerance parameter validation
# ---------------------------------------------------------------------------


class GeometryToleranceValidation(unittest.TestCase):
    def test_defaults_match_current_source_semantics(self):
        # coordinates keeps the current source rejection threshold (1e-5 mm),
        # not the feedback-reported 1e-4; autodim warns at 1e-3 mm.
        self.assertEqual(COORDINATES_DEFAULT_TOLERANCE_MM, 1e-5)
        self.assertEqual(AUTODIM_WARNING_THRESHOLD_MM, 1e-3)
        self.assertEqual(SAMPLE_LIMIT, 20)

    def test_native_coordinates_threshold_stays_synced(self):
        source = (ROOT / "native" / "sketch_coordinates.cpp").read_text(encoding="utf-8")
        match = re.search(r"tolerance_mm = ([0-9.eE-]+)\)", source)
        self.assertIsNotNone(match, "coordinates rejection threshold not found in native source")
        self.assertAlmostEqual(float(match.group(1)), COORDINATES_DEFAULT_TOLERANCE_MM)

    def test_accepts_finite_positive_numbers(self):
        for value in (1e-5, 0.001, 1.0, 25.0):
            with self.subTest(value=value):
                self.assertEqual(validate_tolerance_mm(value), float(value))

    def test_omitted_tolerance_maps_to_none(self):
        self.assertIsNone(validate_tolerance_mm(None))

    def test_rejects_bool_nan_inf_zero_negative_and_non_numbers(self):
        for value in (
            True,
            False,
            float("nan"),
            float("inf"),
            float("-inf"),
            0,
            0.0,
            -1.0,
            -1e-9,
            "0.001",
            [0.001],
        ):
            with self.subTest(value=value):
                with self.assertRaises((ValueError, TypeError)):
                    validate_tolerance_mm(value)


# ---------------------------------------------------------------------------
# Schema plumbing for geometry_tolerance_mm
# ---------------------------------------------------------------------------


class SketchToleranceSchema(unittest.TestCase):
    def sketch(self, **extra):
        return {
            "op": "sketch",
            "label": "profile",
            "plane": "XY",
            "entities": rounded_triangle_entities(),
            "dimensioning": "coordinates",
            **extra,
        }

    def test_sketch_accepts_explicit_tolerance(self):
        dumped = validate_operations([self.sketch(geometry_tolerance_mm=0.002)])[0]
        self.assertEqual(dumped["geometry_tolerance_mm"], 0.002)

    def test_sketch_tolerance_defaults_to_none(self):
        dumped = validate_operations([self.sketch()])
        self.assertNotIn("geometry_tolerance_mm", dumped[0])

    def test_sketch_rejects_bool_nan_inf_zero_negative(self):
        for value in (True, 0, 0.0, -0.001):
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    validate_operations([self.sketch(geometry_tolerance_mm=value)])

    def test_sketch_rejects_non_finite_floats(self):
        # allow_inf_nan=False on StrictModel must hold for the tolerance too.
        for value in (float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    validate_operations([self.sketch(geometry_tolerance_mm=value)])

    def test_edit_op_accepts_and_rejects_tolerance(self):
        edit = {
            "op": "update_sketch_geometry",
            "sketch": "profile",
            "dimensioning": "coordinates",
            "entities": rounded_triangle_entities(),
        }
        dumped = validate_operations([{**edit, "geometry_tolerance_mm": 0.0005}])[0]
        self.assertEqual(dumped["geometry_tolerance_mm"], 0.0005)
        with self.assertRaises(Exception):
            validate_operations([{**edit, "geometry_tolerance_mm": False}])

    def test_coordinates_lenient_mode_is_not_added(self):
        with self.assertRaises(Exception):
            validate_operations([self.sketch(dimensioning="coordinates_lenient")])


# ---------------------------------------------------------------------------
# geometry_deviation result normalization
# ---------------------------------------------------------------------------


def native_report(**overrides):
    """A well-formed native two-stage report for the rounded triangle."""
    sample = [
        {"entity": "fillet_0", "kind": "arc", "measurement": "radius",
         "deviation_mm": 0.0, "reason": None},
        {"entity": "fillet_1", "kind": "arc", "measurement": "center",
         "deviation_mm": 1.7e-6, "reason": None},
    ]
    stages = {
        "section_regenerate": {
            "available": True,
            "max_deviation_mm": 1.7e-6,
            "total": 26,
            "sample": sample,
            "truncated": False,
            "unavailable_reason": None,
        },
        "complete_feature": {
            "available": True,
            "max_deviation_mm": 4.2e-6,
            "total": 26,
            "sample": sample,
            "truncated": False,
            "unavailable_reason": None,
        },
    }
    block = {
        "available": True,
        "unavailable_reason": None,
        "measurement_scope": "named_section_entities",
        "warning_threshold_mm": 1e-5,
        "max_deviation_mm": 4.2e-6,
        "exceeds_warning": False,
        "total": 26,
        "sample": sample,
        "truncated": False,
        "enforced": True,
        "tolerance_source": "default_coordinates",
        "stages": stages,
    }
    block.update(overrides)
    return block


class GeometryDeviationNormalization(unittest.TestCase):
    def test_well_formed_report_passes_through(self):
        report = normalize_geometry_deviation(native_report())
        self.assertTrue(report["available"])
        self.assertEqual(report["max_deviation_mm"], 4.2e-6)
        self.assertEqual(report["warning_threshold_mm"], 1e-5)
        self.assertFalse(report["exceeds_warning"])
        self.assertEqual(report["measurement_scope"], "named_section_entities")
        self.assertEqual(report["total"], 26)
        self.assertFalse(report["truncated"])
        self.assertEqual(
            set(report["stages"]), {"section_regenerate", "complete_feature"}
        )

    def test_exceeds_warning_is_recomputed_not_trusted(self):
        report = normalize_geometry_deviation(
            native_report(max_deviation_mm=2e-3, warning_threshold_mm=1e-3,
                          exceeds_warning=False)
        )
        self.assertTrue(report["exceeds_warning"])

    def test_measurement_failure_is_unavailable_with_reason_not_zero(self):
        report = normalize_geometry_deviation(
            native_report(
                available=False,
                unavailable_reason="ProSectionEntityGet failed (code -2)",
                max_deviation_mm=None,
                exceeds_warning=None,
                total=0,
                sample=[],
                stages={
                    "section_regenerate": {
                        "available": False,
                        "max_deviation_mm": None,
                        "total": 0,
                        "sample": [],
                        "truncated": False,
                        "unavailable_reason": "ProSectionEntityGet failed (code -2)",
                    }
                },
            )
        )
        self.assertFalse(report["available"])
        self.assertIsNone(report["max_deviation_mm"])
        self.assertIn("failed", report["unavailable_reason"])
        # A query failure must never degrade to an all-zero success report.
        self.assertNotEqual(report["max_deviation_mm"], 0.0)

    def test_malformed_block_degrades_to_unavailable(self):
        for bad in (None, "deviation", 17, [], {"available": "yes"}):
            with self.subTest(bad=bad):
                report = normalize_geometry_deviation(bad)
                self.assertFalse(report["available"])
                self.assertIsNone(report["max_deviation_mm"])
                self.assertTrue(report["unavailable_reason"])

    def test_sample_is_capped_and_truncation_is_reported(self):
        flood = [
            {"entity": f"e{i}", "kind": "line", "measurement": "end",
             "deviation_mm": 0.0, "reason": None}
            for i in range(SAMPLE_LIMIT + 5)
        ]
        report = normalize_geometry_deviation(
            native_report(sample=flood, total=SAMPLE_LIMIT + 5, truncated=True)
        )
        self.assertEqual(len(report["sample"]), SAMPLE_LIMIT)
        self.assertTrue(report["truncated"])

    def test_sample_entries_reject_non_finite_deviations(self):
        flooded = [
            {"entity": "fillet_0", "kind": "arc", "measurement": "radius",
             "deviation_mm": float("nan"), "reason": None},
        ]
        report = normalize_geometry_deviation(native_report(sample=flooded))
        self.assertEqual(report["sample"][0]["deviation_mm"], None)

    def test_unavailable_helper_documents_reason(self):
        report = unavailable_geometry_deviation("no snapshot was taken for this mode")
        self.assertFalse(report["available"])
        self.assertIsNone(report["max_deviation_mm"])
        self.assertEqual(report["unavailable_reason"], "no snapshot was taken for this mode")

    def test_identity_names_survive_normalization(self):
        report = normalize_geometry_deviation(native_report())
        self.assertEqual(
            [entry["entity"] for entry in report["sample"]],
            ["fillet_0", "fillet_1"],
        )

    def test_native_sources_wire_the_two_stage_contract(self):
        coordinates = (ROOT / "native" / "sketch_coordinates.cpp").read_text(encoding="utf-8")
        self.assertIn("geometry_deviation_report", coordinates)
        for marker in ("section_regenerate", "complete_feature"):
            with self.subTest(marker=marker):
                joined = coordinates + (ROOT / "native" / "generic.cpp").read_text(
                    encoding="utf-8"
                ) + (ROOT / "native" / "sketch_edit.cpp").read_text(encoding="utf-8")
                self.assertIn(marker, joined)
        self.assertNotIn("coordinates_lenient", coordinates)


# ---------------------------------------------------------------------------
# Fixture validation against the independent oracle
# ---------------------------------------------------------------------------


class RoundedTriangleOracle(unittest.TestCase):
    def test_two_independent_oracles_agree(self):
        a = oracle_area_hexagon_plus_segments()
        b = oracle_area_corner_cut()
        self.assertAlmostEqual(a, b, delta=1e-6)
        self.assertGreater(a, 0.0)

    def test_input_analyzer_matches_independent_oracle(self):
        # Validates the fixture itself: exact shared endpoints, closed contour,
        # and the analytic input report agrees with the independent oracle.
        report = analyze_profile(rounded_triangle_entities())
        self.assertEqual(report["closed_contour_count"], 1)
        self.assertEqual(report["open_contour_count"], 0)
        self.assertEqual(report["entity_count"], 6)
        self.assertLess(report["max_endpoint_gap_mm"] if "max_endpoint_gap_mm" in report
                        else max(c["max_join_gap_mm"] for c in report["contours"]),
                        1e-12)
        self.assertAlmostEqual(
            report["material_area_mm2"], oracle_area_hexagon_plus_segments(), delta=1e-6
        )

    def test_arc_oracle_values_are_exact(self):
        arcs = oracle_arcs()
        self.assertEqual(len(arcs), 3)
        for name, arc in arcs.items():
            self.assertEqual(arc["radius"], FILLET_RADIUS_MM, name)
            self.assertAlmostEqual(math.hypot(*arc["center"]), 14.0, delta=1e-12, msg=name)

    def test_oracle_volume_for_prism_extrusion(self):
        depth = 10.0
        self.assertAlmostEqual(
            oracle_area_hexagon_plus_segments() * depth,
            10376.4,
            delta=1.0,
        )


# ---------------------------------------------------------------------------
# Plan-level admission keeps the contract on both entries
# ---------------------------------------------------------------------------


class PlanParity(unittest.TestCase):
    def test_plan_sketch_and_edit_share_the_same_tolerance_contract(self):
        plan = [
            {
                "op": "sketch",
                "label": "profile",
                "plane": "XY",
                "entities": rounded_triangle_entities(),
                "dimensioning": "autodim",
                "geometry_tolerance_mm": 0.002,
            },
            {
                "op": "extrude",
                "label": "solid",
                "sketch": "profile",
                "depth": 10,
            },
            {
                "op": "update_sketch_geometry",
                "sketch": "profile",
                "entities": rounded_triangle_entities(),
                "dimensioning": "coordinates",
                "geometry_tolerance_mm": 0.0005,
            },
        ]
        dumped = validate_operations(plan)
        self.assertEqual(dumped[0]["geometry_tolerance_mm"], 0.002)
        self.assertEqual(dumped[2]["geometry_tolerance_mm"], 0.0005)
        self.assertEqual(dumped[2]["dimensioning"], "coordinates")


if __name__ == "__main__":
    unittest.main()
