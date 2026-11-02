"""BUG-108: post-solve sketch translation must be visible without digging into samples.

The 0.11.1 feedback (Creo 10) hit ``maximum deviation mm=0.004004`` where the
solver translated the whole profile by 0.004 mm in u instead of deforming it.
The rejection message was the only signal, and an explicit
``geometry_tolerance_mm`` let it through without any top-level indication that
the sketch had moved. These tests pin the ``sketch_shifted`` contract:

- a rigid translation reports its common-mode vector;
- a deformation reports ``rigid=False`` and no translation vector;
- a request-tolerance release is marked ``accepted_by_request`` (never implied);
- malformed records degrade to an explicit unavailable state, never to zeros.
"""

import math
import unittest
from pathlib import Path

from creo_mechdog.geometry_deviation import normalize_sketch_shifted
from creo_mechdog.operation_results import annotate_sketch_shifted

ROOT = Path(__file__).resolve().parents[2]


def native_shift(**overrides):
    block = {
        "detected": True,
        "rigid": True,
        "translation_mm": {"u": 0.004003728342, "v": 0.0},
        "max_point_mm": 0.004003728342,
        "point_count": 6,
        "total": 6,
        "sample": [
            {
                "entity": "tri_0",
                "point": "start",
                "axis": 0,
                "moved_mm": 0.004003728342,
            }
        ],
        "truncated": False,
        "tolerance_source": "default_coordinates",
        "accepted_by_request": False,
        "measurement_scope": "named_section_entities",
        "note": "the solved profile translated as a rigid body",
    }
    block.update(overrides)
    return block


class RigidShiftTests(unittest.TestCase):
    def test_rigid_translation_keeps_the_measured_vector(self):
        report = normalize_sketch_shifted(native_shift())
        self.assertTrue(report["detected"])
        self.assertTrue(report["rigid"])
        self.assertAlmostEqual(report["translation_mm"]["u"], 0.004003728342)
        self.assertEqual(report["translation_mm"]["v"], 0.0)
        self.assertAlmostEqual(report["max_point_mm"], 0.004003728342)
        self.assertEqual(report["point_count"], 6)

    def test_deformation_reports_no_translation_vector(self):
        report = normalize_sketch_shifted(
            native_shift(rigid=False, translation_mm={"u": 0.002, "v": 0.0})
        )
        self.assertTrue(report["detected"])
        self.assertFalse(report["rigid"])
        self.assertIsNone(report["translation_mm"])

    def test_zero_shift_is_not_detected(self):
        report = normalize_sketch_shifted(
            native_shift(
                detected=False,
                rigid=None,
                translation_mm=None,
                max_point_mm=0.0,
                accepted_by_request=False,
            )
        )
        self.assertFalse(report["detected"])
        self.assertIsNone(report["translation_mm"])
        self.assertFalse(report["accepted_by_request"])

    def test_request_tolerance_is_marked_as_accepted_not_exact(self):
        report = normalize_sketch_shifted(
            native_shift(tolerance_source="request", accepted_by_request=True)
        )
        self.assertEqual(report["tolerance_source"], "request")
        self.assertTrue(report["accepted_by_request"])
        self.assertIn("not an exact solve", report["note"])

    def test_accepted_by_request_is_never_invented(self):
        # A request-tolerance run with no detected shift is not "accepted".
        report = normalize_sketch_shifted(
            native_shift(
                detected=False,
                rigid=None,
                translation_mm=None,
                max_point_mm=0.0,
                tolerance_source="request",
                accepted_by_request=False,
            )
        )
        self.assertFalse(report["accepted_by_request"])
        # Nor is a default-threshold shift accepted by request.
        report = normalize_sketch_shifted(native_shift(accepted_by_request=True))
        self.assertFalse(report["accepted_by_request"])

    def test_sample_is_capped_and_truncation_is_reported(self):
        sample = [
            {"entity": f"e{index}", "point": "start", "axis": 0, "moved_mm": 0.001}
            for index in range(30)
        ]
        report = normalize_sketch_shifted(native_shift(sample=sample, total=30))
        self.assertEqual(len(report["sample"]), 20)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["total"], 30)

    def test_malformed_records_degrade_to_explicit_unavailable(self):
        for block in (
            "not a dict",
            {"detected": "yes"},
            {"detected": True, "rigid": True, "translation_mm": {"u": float("nan"), "v": 0.0}},
        ):
            with self.subTest(block=block):
                report = normalize_sketch_shifted(block)
                self.assertIsNone(report["detected"])
                self.assertIsNone(report["max_point_mm"])
                self.assertEqual(report["sample"], [])
                self.assertIsInstance(report["note"], str)

    def test_detected_without_any_measurement_is_contradictory(self):
        report = normalize_sketch_shifted(
            native_shift(max_point_mm=None, translation_mm=None, rigid=None, point_count=0)
        )
        self.assertIsNone(report["detected"])
        self.assertIn("contradict", report["note"])

    def test_unknown_tolerance_source_is_dropped(self):
        report = normalize_sketch_shifted(native_shift(tolerance_source="guess"))
        self.assertIsNone(report["tolerance_source"])
        self.assertFalse(report["accepted_by_request"])


class OperationProjectionTests(unittest.TestCase):
    def test_annotate_projects_sketch_and_edit_records(self):
        result = {
            "operations": [
                {"op": "sketch", "sketch_shifted": native_shift()},
                {"op": "update_sketch_geometry", "sketch_shifted": native_shift(rigid=False)},
                {"op": "extrude"},
            ]
        }
        annotate_sketch_shifted(result)
        self.assertTrue(result["operations"][0]["sketch_shifted"]["rigid"])
        self.assertFalse(result["operations"][1]["sketch_shifted"]["rigid"])
        self.assertNotIn("sketch_shifted", result["operations"][2])

    def test_absent_block_stays_absent(self):
        result = {"operations": [{"op": "sketch", "geometry_deviation": {"available": False}}]}
        annotate_sketch_shifted(result)
        self.assertNotIn("sketch_shifted", result["operations"][0])

    def test_malformed_block_on_a_record_degrades_in_place(self):
        result = {"operations": [{"op": "sketch", "sketch_shifted": {"detected": 1}}]}
        annotate_sketch_shifted(result)
        self.assertIsNone(result["operations"][0]["sketch_shifted"]["detected"])


class NativeContractTests(unittest.TestCase):
    """The executor must publish the block; the contract is source-verifiable."""

    def _native_source(self, name):
        return (ROOT / "native" / name).read_text(encoding="utf-8")

    def test_native_shift_detection_and_mount_points_exist(self):
        coordinates = self._native_source("sketch_coordinates.cpp")
        for token in (
            "rigid",
            "translation_mm",
            "SKETCH_SHIFT_RIGID",
            "SKETCH_ORIGIN_PIN_UNAVAILABLE",
            "sketch_shift_block",
        ):
            self.assertIn(token, coordinates)
        generic = self._native_source("generic.cpp")
        self.assertIn('"sketch_shifted"', generic)
        edit = self._native_source("sketch_edit.cpp")
        self.assertIn('"sketch_shifted"', edit)

    def test_native_shift_keeps_the_existing_rejection_gate(self):
        coordinates = self._native_source("sketch_coordinates.cpp")
        self.assertIn("maximum deviation mm=", coordinates)
        self.assertIn("tolerance_mm", coordinates)
        # No silent acceptance: the rigid report never raises tolerance itself.
        self.assertNotIn("rigid ? 0", coordinates)


class TranslationMathTests(unittest.TestCase):
    def test_mean_of_identical_offsets_is_the_offset(self):
        offsets = [(0.004, 0.0), (0.004, 0.0), (0.004, 0.0)]
        u = sum(item[0] for item in offsets) / len(offsets)
        self.assertAlmostEqual(u, 0.004)
        residual = max(math.hypot(item[0] - u, item[1]) for item in offsets)
        self.assertLessEqual(residual, 1e-9)
