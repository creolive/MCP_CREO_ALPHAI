"""BUG-095 / DEV-053 P07: sketch origin rejection carries measured diagnostics.

Offline contract tests. The native executor owns the measurement; these tests
fix the frozen output contract (``sketch_origin_diagnostics`` on the failed
sketch operation record), the unchanged 1e-6 mm admission threshold, and the
Python-side projection of the block onto persisted job results.
"""

import math
import unittest

from creo_mechdog.operation_results import (
    annotate_native_result,
    annotate_sketch_origin_diagnostics,
    normalize_sketch_origin_diagnostics,
)

ORIGIN_TOLERANCE_MM = 1e-6


def dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


# The oracle plane mirrors the executor's computation: a normalized support
# normal (oriented as the sketch frame normal) and a plane constant.
ORACLE_PLANE = {"normal": [0.0, 0.0, 1.0], "constant_mm": 0.0}
# An oblique plane proves the math never assumes a principal orientation.
ORACLE_OBLIQUE_PLANE = {
    "normal": [1.0 / math.sqrt(3), -1.0 / math.sqrt(3), 1.0 / math.sqrt(3)],
    "constant_mm": 5.0,
}


def signed_distance(plane, point):
    return dot(plane["normal"], point) - plane["constant_mm"]


def diagnostics_block(plane, requested_origin):
    """Mirror of the native sketch_frame rejection payload (BUG-095)."""
    signed = signed_distance(plane, requested_origin)
    return {
        "status": "origin_outside_support_plane",
        "distance_to_plane_mm": abs(signed),
        "signed_distance_to_plane_mm": signed,
        "origin_tolerance_mm": ORIGIN_TOLERANCE_MM,
        "support_plane": dict(plane),
        "requested_origin": list(requested_origin),
        "suggested_origin": [
            requested_origin[i] - signed * plane["normal"][i] for i in range(3)
        ],
    }


def on_plane_point(plane, offset_along_normal=0.0):
    """A point on the plane (or offset along its normal), plus a fixed tangential shift."""
    normal = plane["normal"]
    tangent = [normal[1] - normal[2], normal[2] - normal[0], normal[0] - normal[1]]
    tangent_length = math.sqrt(dot(tangent, tangent))
    tangent = [item / tangent_length for item in tangent]
    return [
        normal[i] * plane["constant_mm"] + tangent[i] * 2.0 + normal[i] * offset_along_normal
        for i in range(3)
    ]


def deviations(plane):
    """Points off the plane at the frozen coverage deviations, both signs."""
    return [
        (deviation, sign, on_plane_point(plane, sign * deviation))
        for deviation in (0.0, 0.5e-6, 2e-6, 1.07e-4)
        for sign in (1, -1)
    ]


class SketchOriginOracleTest(unittest.TestCase):
    """The frozen admission rule and payload math, on both plane shapes."""

    def test_on_plane_origin_is_within_tolerance_from_both_sides(self):
        for plane in (ORACLE_PLANE, ORACLE_OBLIQUE_PLANE):
            with self.subTest(plane=plane["normal"]):
                self.assertAlmostEqual(
                    signed_distance(plane, on_plane_point(plane)), 0.0, delta=1e-12
                )

    def test_boundary_deviations_split_at_the_frozen_threshold(self):
        for plane in (ORACLE_PLANE, ORACLE_OBLIQUE_PLANE):
            for deviation, sign, point in deviations(plane):
                with self.subTest(plane=plane["normal"], deviation=deviation, sign=sign):
                    signed = signed_distance(plane, point)
                    if deviation <= ORIGIN_TOLERANCE_MM:
                        self.assertLessEqual(abs(signed), ORIGIN_TOLERANCE_MM)
                    else:
                        self.assertGreater(abs(signed), ORIGIN_TOLERANCE_MM)

    def test_reported_deviation_matches_the_feedback_case(self):
        # The external report: a ~1.07e-4 mm origin deviation must produce a
        # rejection whose distance equals the deviation, whatever the sign.
        for sign in (1, -1):
            with self.subTest(sign=sign):
                block = diagnostics_block(ORACLE_PLANE, [0.0, 0.0, sign * 1.07e-4])
                self.assertAlmostEqual(block["distance_to_plane_mm"], 1.07e-4, places=15)
                self.assertAlmostEqual(
                    abs(block["signed_distance_to_plane_mm"]), 1.07e-4, places=15
                )
                self.assertEqual(
                    math.copysign(1, block["signed_distance_to_plane_mm"]), float(sign)
                )

    def test_suggested_origin_is_an_exact_projection_onto_the_plane(self):
        for plane in (ORACLE_PLANE, ORACLE_OBLIQUE_PLANE):
            for _, _, point in deviations(plane):
                with self.subTest(plane=plane["normal"], point=point):
                    block = diagnostics_block(plane, point)
                    residual = signed_distance(plane, block["suggested_origin"])
                    self.assertAlmostEqual(residual, 0.0, delta=1e-12)

    def test_support_plane_normal_is_normalized_and_constant_matches_origin(self):
        block = diagnostics_block(ORACLE_OBLIQUE_PLANE, [0.0, 0.0, 4.0])
        normal = block["support_plane"]["normal"]
        self.assertAlmostEqual(dot(normal, normal), 1.0, delta=1e-12)
        on_plane = [normal[i] * block["support_plane"]["constant_mm"] for i in range(3)]
        self.assertAlmostEqual(signed_distance(ORACLE_OBLIQUE_PLANE, on_plane), 0.0, delta=1e-12)


class SketchOriginProjectionTest(unittest.TestCase):
    """The Python-side projection of the executor's diagnostics block."""

    def test_well_formed_block_passes_through_with_frozen_fields(self):
        block = diagnostics_block(ORACLE_OBLIQUE_PLANE, [0.0, 0.0, 4.0])
        normalized = normalize_sketch_origin_diagnostics(block)
        self.assertEqual(sorted(normalized), sorted(block))
        self.assertEqual(normalized["status"], "origin_outside_support_plane")
        self.assertAlmostEqual(
            normalized["distance_to_plane_mm"], block["distance_to_plane_mm"], delta=1e-15
        )
        self.assertAlmostEqual(
            normalized["signed_distance_to_plane_mm"],
            block["signed_distance_to_plane_mm"],
            delta=1e-15,
        )
        self.assertEqual(normalized["origin_tolerance_mm"], ORIGIN_TOLERANCE_MM)
        self.assertEqual(normalized["requested_origin"], [0.0, 0.0, 4.0])

    def test_non_unit_support_normal_degrades_to_unknown_plane(self):
        block = diagnostics_block(ORACLE_PLANE, [0.0, 0.0, 1.07e-4])
        block["support_plane"]["normal"] = [0.0, 0.0, 2.0]
        normalized = normalize_sketch_origin_diagnostics(block)
        self.assertIsNone(normalized["support_plane"])
        self.assertAlmostEqual(normalized["distance_to_plane_mm"], 1.07e-4)

    def test_distance_signed_mismatch_degrades_both_distances(self):
        block = diagnostics_block(ORACLE_PLANE, [0.0, 0.0, 2e-6])
        block["distance_to_plane_mm"] = 3e-6
        normalized = normalize_sketch_origin_diagnostics(block)
        self.assertIsNone(normalized["distance_to_plane_mm"])
        self.assertIsNone(normalized["signed_distance_to_plane_mm"])
        self.assertEqual(normalized["status"], "origin_outside_support_plane")

    def test_malformed_numbers_degrade_to_null_fields(self):
        block = diagnostics_block(ORACLE_PLANE, [0.0, 0.0, 2e-6])
        block["distance_to_plane_mm"] = "big"
        block["requested_origin"] = [0, 0]
        block["origin_tolerance_mm"] = float("nan")
        normalized = normalize_sketch_origin_diagnostics(block)
        self.assertIsNone(normalized["distance_to_plane_mm"])
        self.assertIsNone(normalized["requested_origin"])
        self.assertIsNone(normalized["origin_tolerance_mm"])
        self.assertIsNotNone(normalized["suggested_origin"])

    def test_non_dict_block_degrades_to_explicit_unknown(self):
        normalized = normalize_sketch_origin_diagnostics("nope")
        self.assertEqual(
            sorted(normalized),
            sorted(
                [
                    "status",
                    "distance_to_plane_mm",
                    "signed_distance_to_plane_mm",
                    "origin_tolerance_mm",
                    "support_plane",
                    "requested_origin",
                    "suggested_origin",
                ]
            ),
        )
        self.assertEqual(normalized["status"], "unknown")
        self.assertTrue(all(normalized[key] is None for key in normalized if key != "status"))

    def test_missing_block_stays_missing_and_non_sketch_ops_are_untouched(self):
        result = {
            "success": False,
            "operations": [
                {"op": "sketch", "label": "kept", "succeeded": False},
                {"op": "extrude", "sketch_origin_diagnostics": "junk"},
            ],
        }
        annotate_sketch_origin_diagnostics(result)
        self.assertNotIn("sketch_origin_diagnostics", result["operations"][0])
        self.assertEqual(result["operations"][1]["sketch_origin_diagnostics"], "junk")

    def test_annotate_native_result_normalizes_failed_sketch_records(self):
        block = diagnostics_block(ORACLE_PLANE, [0.0, 0.0, 1.07e-4])
        result = {
            "success": False,
            "failed_operation_index": 1,
            "operations": [
                {"op": "sketch", "label": "base", "succeeded": True, "index": 0},
                {"op": "airfoil_sketch", "succeeded": False, "index": 1,
                 "sketch_origin_diagnostics": dict(block)},
            ],
        }
        annotated = annotate_native_result(result, readonly=False)
        failure = annotated["operations"][1]
        self.assertEqual(failure["execution_status"], "failed")
        normalized = failure["sketch_origin_diagnostics"]
        self.assertEqual(normalized["status"], "origin_outside_support_plane")
        self.assertAlmostEqual(normalized["distance_to_plane_mm"], 1.07e-4)
        self.assertEqual(normalized["support_plane"]["constant_mm"], 0.0)

    def test_projection_never_echoes_the_request_as_support_evidence(self):
        # A fabricated block whose support plane contradicts any request value
        # still passes through verbatim: the projection validates shape and
        # consistency, it never recomputes evidence from the input plane.
        block = {
            "status": "origin_outside_support_plane",
            "distance_to_plane_mm": 0.25,
            "signed_distance_to_plane_mm": -0.25,
            "origin_tolerance_mm": ORIGIN_TOLERANCE_MM,
            "support_plane": {"normal": [0.6, 0.8, 0.0], "constant_mm": 12.0},
            "requested_origin": [7.0, -2.0, 1.0],
            "suggested_origin": [8.2, -1.4, 1.0],
        }
        normalized = normalize_sketch_origin_diagnostics(block)
        self.assertEqual(normalized, block)


if __name__ == "__main__":
    unittest.main()
