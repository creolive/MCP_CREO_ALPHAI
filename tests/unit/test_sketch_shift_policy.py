"""Public contract for the rigid-translation policy (BUG-108 / R13)."""

import unittest

from creo_mechdog.geometry_deviation import (
    RIGID_TRANSLATION_LIMIT_MM,
    normalize_geometry_deviation,
    normalize_sketch_shifted,
)


def shift_block(**overrides):
    block = {
        "detected": True,
        "rigid": True,
        "translation_mm": {"u": 0.000016, "v": 0.0},
        "max_point_mm": 0.000016,
        "residual_mm": 0.0,
        "shape_deviation_mm": 0.0,
        "accepted_rigid": True,
        "point_count": 4,
        "tolerance_source": "default_coordinates",
        "accepted_by_request": False,
        "measurement_scope": "named_section_entities",
        "sample": [],
        "truncated": False,
    }
    block.update(overrides)
    return block


class RigidTranslationLimit(unittest.TestCase):
    def test_limit_is_one_hundredth_of_a_millimeter(self):
        self.assertEqual(RIGID_TRANSLATION_LIMIT_MM, 1e-2)


class SketchShiftAcceptedRigid(unittest.TestCase):
    def test_accepts_a_rigid_translation_inside_the_limit(self):
        report = normalize_sketch_shifted(shift_block())
        self.assertTrue(report["rigid"])
        self.assertTrue(report["accepted_rigid"])
        self.assertEqual(report["translation_mm"], {"u": 0.000016, "v": 0.0})
        self.assertEqual(report["residual_mm"], 0.0)

    def test_rejects_a_rigid_translation_beyond_the_limit(self):
        report = normalize_sketch_shifted(
            shift_block(translation_mm={"u": 0.02, "v": 0.0}, max_point_mm=0.02)
        )
        self.assertTrue(report["rigid"])
        self.assertFalse(report["accepted_rigid"])

    def test_a_deformed_profile_is_never_accepted_as_rigid(self):
        report = normalize_sketch_shifted(
            shift_block(rigid=False, translation_mm=None, residual_mm=0.004, accepted_rigid=False)
        )
        self.assertFalse(report["accepted_rigid"])
        self.assertEqual(report["residual_mm"], 0.004)

    def test_acceptance_is_not_inferred_from_a_missing_flag(self):
        block = shift_block()
        block.pop("accepted_rigid")
        self.assertFalse(normalize_sketch_shifted(block)["accepted_rigid"])

    def test_reported_acceptance_without_a_usable_translation_is_refused(self):
        report = normalize_sketch_shifted(
            shift_block(translation_mm={"u": None, "v": 0.0}, accepted_rigid=True)
        )
        self.assertFalse(report["accepted_rigid"])

    def test_no_shift_keeps_the_new_fields_empty(self):
        report = normalize_sketch_shifted(shift_block(detected=False, max_point_mm=0.0))
        self.assertFalse(report["detected"])
        self.assertFalse(report["accepted_rigid"])
        self.assertIsNone(report["residual_mm"])


class GeometryDeviationShapeFields(unittest.TestCase):
    def test_rigid_fields_are_echoed_next_to_the_deviation(self):
        report = normalize_geometry_deviation(
            {
                "available": True,
                "warning_threshold_mm": 1e-5,
                "max_deviation_mm": 0.000016,
                "enforced": True,
                "tolerance_source": "default_coordinates",
                "total": 4,
                "sample": [],
                "truncated": False,
                "shape_deviation_mm": 0.0,
                "residual_mm": 0.0,
                "rigid": True,
                "translation_mm": {"u": 0.000016, "v": 0.0},
                "accepted_rigid": True,
                "stages": {},
            }
        )
        self.assertEqual(report["shape_deviation_mm"], 0.0)
        self.assertEqual(report["residual_mm"], 0.0)
        self.assertTrue(report["rigid"])
        self.assertTrue(report["accepted_rigid"])
        self.assertEqual(report["translation_mm"], {"u": 0.000016, "v": 0.0})
        self.assertTrue(report["exceeds_warning"])

    def test_acceptance_is_never_trusted_over_the_numbers(self):
        report = normalize_geometry_deviation(
            {
                "available": True,
                "max_deviation_mm": 0.000016,
                "warning_threshold_mm": 1e-5,
                "rigid": False,
                "accepted_rigid": True,
                "stages": {},
            }
        )
        self.assertFalse(report["accepted_rigid"])

    def test_old_records_keep_the_fields_absent(self):
        report = normalize_geometry_deviation(
            {
                "available": True,
                "max_deviation_mm": 0.0004,
                "warning_threshold_mm": 1e-3,
                "total": 1,
                "sample": [],
                "stages": {},
            }
        )
        self.assertIsNone(report["shape_deviation_mm"])
        self.assertIsNone(report["rigid"])
        self.assertIsNone(report["accepted_rigid"])

    def test_unavailable_record_declares_the_new_fields_as_null(self):
        report = normalize_geometry_deviation(None)
        for key in (
            "shape_deviation_mm",
            "residual_mm",
            "rigid",
            "translation_mm",
            "accepted_rigid",
        ):
            self.assertIsNone(report[key], key)


if __name__ == "__main__":
    unittest.main()
