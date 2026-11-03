"""FEAT-035 standard threaded holes: frozen table, guards and prepared payload.

The native branch is verified live for the ISO metric coarse rows (FEAT-035
2026-11-03). These tests keep the offline contract: only frozen rows, the thread
depth inside the real tip depth, and the chart-bound values injected by
``hole_standards.prepare`` rather than derived by native.
"""

import unittest

from pydantic import ValidationError

from creo_mechdog.hole_standards import (
    TABLE_ID,
    prepare,
    resolve_standard_hole,
    table_digest,
    tip_cone_height_mm,
)
from creo_mechdog.schema import HoleOp, StandardHoleSpec


def hole(**overrides):
    payload = {
        "op": "hole",
        "label": "h001_m6",
        "placement": {"type": "point", "x": 10, "y": 10, "z": 0},
        "reference1": {"type": "plane", "id": 3},
        "reference2": {"type": "plane", "id": 4},
        "diameter": 6.0,
        "depth": 20.0,
    }
    payload.update(overrides)
    return payload


class FrozenTable(unittest.TestCase):
    def test_resolves_known_sizes(self):
        row = resolve_standard_hole("ISO", "M6")
        self.assertEqual(row["table_id"], TABLE_ID)
        self.assertAlmostEqual(row["nominal_diameter_mm"], 6.0)
        self.assertAlmostEqual(row["tap_drill_diameter_mm"], 5.0)
        self.assertAlmostEqual(row["pitch_mm"], 1.0)
        self.assertEqual(len(row["table_sha256"]), 64)
        self.assertEqual(row["table_sha256"], table_digest("ISO"))

    def test_sizes_are_mostly_ordered_by_nominal_diameter(self):
        sizes = ["M3", "M4", "M5", "M6", "M8", "M10", "M12"]
        rows = [resolve_standard_hole("ISO", size) for size in sizes]
        nomina = [row["nominal_diameter_mm"] for row in rows]
        drills = [row["tap_drill_diameter_mm"] for row in rows]
        self.assertEqual(nomina, sorted(nomina))
        self.assertEqual(drills, sorted(drills))
        self.assertTrue(all(drill < nominal for drill, nominal in zip(drills, nomina, strict=True)))

    def test_unknown_series_and_size_are_refused(self):
        with self.assertRaises(ValueError) as error:
            resolve_standard_hole("ANSI", "M6")
        self.assertIn("unknown standard hole series", str(error.exception))
        with self.assertRaises(ValueError) as error:
            resolve_standard_hole("ISO", "M7")
        self.assertIn("is not in ISO", str(error.exception))

    def test_paths_and_empty_names_are_refused(self):
        for series, size in (
            ("ISO", "../M6"),
            ("ISO", "a\\b"),
            ("ISO", "C:M6"),
            ("ISO", ".."),
            ("", "M6"),
            ("ISO", "  "),
        ):
            with self.assertRaises(ValueError):
                resolve_standard_hole(series, size)


class SchemaContract(unittest.TestCase):
    def test_old_payload_keeps_working(self):
        op = HoleOp.model_validate(hole())
        self.assertIsNone(op.standard)

    def test_standard_spec_shape_is_frozen(self):
        spec = StandardHoleSpec.model_validate({"series": "ISO", "size": "M6", "thread_depth": 10})
        self.assertEqual(spec.series, "ISO")
        self.assertEqual(spec.thread_depth, 10.0)

    def test_mutual_exclusion_with_counterbore(self):
        payload = hole(
            standard={"series": "ISO", "size": "M6", "thread_depth": 10},
            counterbore={"diameter": 11, "depth": 3},
        )
        with self.assertRaises(ValidationError) as error:
            HoleOp.model_validate(payload)
        self.assertIn("cannot be combined with counterbore", str(error.exception))

    def test_diameter_must_match_the_table(self):
        payload = hole(diameter=5.0, standard={"series": "ISO", "size": "M6", "thread_depth": 10})
        with self.assertRaises(ValidationError) as error:
            HoleOp.model_validate(payload)
        self.assertIn("nominal diameter", str(error.exception))

    def test_thread_depth_is_bounded_by_the_table(self):
        payload = hole(standard={"series": "ISO", "size": "M6", "thread_depth": 13})
        with self.assertRaises(ValidationError) as error:
            HoleOp.model_validate(payload)
        self.assertIn("table limit", str(error.exception))

    def test_thread_depth_must_be_positive_finite_and_not_boolean(self):
        for depth in (0, -1, True, float("inf")):
            payload = hole(standard={"series": "ISO", "size": "M6", "thread_depth": depth})
            with self.assertRaises(ValidationError):
                HoleOp.model_validate(payload)

    def test_diameter_is_optional_for_standard_holes(self):
        payload = hole(
            diameter=None,
            standard={"series": "ISO", "size": "M6", "thread_depth": 10},
        )
        payload.pop("diameter")
        op = HoleOp.model_validate(payload)
        self.assertIsNone(op.diameter)
        self.assertEqual(op.standard.thread_depth, 10.0)

    def test_diameter_is_still_required_without_standard(self):
        payload = hole()
        payload.pop("diameter")
        with self.assertRaises(ValidationError) as error:
            HoleOp.model_validate(payload)
        self.assertIn("requires diameter", str(error.exception))

    def test_standard_hole_requires_a_blind_depth(self):
        payload = hole(standard={"series": "ISO", "size": "M6", "thread_depth": 10})
        payload.pop("depth")
        with self.assertRaises(ValidationError) as error:
            HoleOp.model_validate(payload)
        self.assertIn("requires an explicit depth", str(error.exception))

    def test_thread_depth_must_be_strictly_inside_tip_depth(self):
        # M12 has a 24 mm table limit, so the tip rule is what decides here.
        cone = tip_cone_height_mm(10.2)
        payload = hole(
            diameter=12.0,
            depth=20.0,
            standard={"series": "ISO", "size": "M12", "thread_depth": 20.0 + cone},
        )
        with self.assertRaises(ValidationError) as error:
            HoleOp.model_validate(payload)
        self.assertIn("strictly inside", str(error.exception))
        inside = hole(
            diameter=12.0,
            depth=20.0,
            standard={"series": "ISO", "size": "M12", "thread_depth": 20.0 + cone - 0.01},
        )
        self.assertAlmostEqual(
            HoleOp.model_validate(inside).standard.thread_depth, 20.0 + cone - 0.01
        )

    def test_prepare_injects_the_frozen_row(self):
        operations = prepare([hole(standard={"series": "ISO", "size": "M6", "thread_depth": 6.0})])
        standard = operations[0]["standard"]
        self.assertEqual(standard["fastener_id"], "M6x1")
        self.assertAlmostEqual(standard["tap_drill_mm"], 5.0)
        self.assertAlmostEqual(standard["nominal_diameter_mm"], 6.0)
        self.assertAlmostEqual(standard["thread_depth_limit_mm"], 12.0)
        # The prepared payload still satisfies the public schema.
        HoleOp.model_validate(operations[0])

    def test_prepared_values_must_match_the_table(self):
        row = resolve_standard_hole("ISO", "M6")
        payload = hole(
            standard={
                "series": "ISO",
                "size": "M6",
                "thread_depth": 6,
                "tap_drill_mm": 6.0,
            }
        )
        with self.assertRaises(ValidationError) as error:
            HoleOp.model_validate(payload)
        self.assertIn(f"{row['tap_drill_diameter_mm']} mm", str(error.exception))

    def test_valid_standard_hole_is_accepted(self):
        op = HoleOp.model_validate(
            hole(standard={"series": "ISO", "size": "M6", "thread_depth": 10})
        )
        self.assertEqual(op.standard.series, "ISO")
        self.assertEqual(op.standard.size, "M6")


if __name__ == "__main__":
    unittest.main()
