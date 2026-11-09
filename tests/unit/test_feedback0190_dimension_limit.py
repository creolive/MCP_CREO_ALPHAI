"""DEV-081 / F03: radius and sketch dimension API limit is explicit and usable."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from creo_mechdog.schema import Arc, Ellipse, SketchDimension, validate_operations


def _arc(radius):
    return {
        "type": "arc",
        "name": "a",
        "center": [0, 0],
        "radius": radius,
        "start_angle": 0,
        "end_angle": 90,
    }


class DimensionLimitTests(unittest.TestCase):
    def test_arc_radius_105000_accepted(self):
        self.assertEqual(Arc(**_arc(105000)).radius, 105000)

    def test_ellipse_and_sketch_dimension_105000_accepted(self):
        ellipse = Ellipse(
            type="ellipse", name="e1", center=[0, 0], x_radius=105000, y_radius=105000
        )
        dimension = SketchDimension(name="d1", type="radius", refs=[{"entity": "a"}], value=105000)
        self.assertEqual(ellipse.x_radius, 105000)
        self.assertEqual(dimension.value, 105000)

    def test_dimension_over_1e6_rejected_with_api_limit_text(self):
        with self.assertRaises(ValidationError) as caught:
            Arc(**_arc(1000001))
        text = str(caught.exception)
        self.assertIn("1000000", text)
        self.assertIn("API limit", text)

    def test_boolean_zero_negative_nan_inf_rejected(self):
        for value in (True, 0, -1, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    Arc(**_arc(value))

    def test_translation_100001_still_rejected(self):
        with self.assertRaises(ValueError):
            validate_operations(
                [
                    {
                        "op": "geometry_transform",
                        "label": "pose",
                        "references": [{"kind": "body"}],
                        "translation": [100001, 0, 0],
                        "rotation": [0, 0, 45],
                        "keep_original": True,
                    }
                ]
            )


if __name__ == "__main__":
    unittest.main()
