"""BUG-097 Q06 L2 fixture: archived smoke_3pt case converted to the FEAT-053 contract."""

import math
import unittest

from tools.test_tilted_sketch_3pt import (
    DEPTH_MM,
    TRIANGLE_UV,
    expected_normal,
    expected_volume_mm3,
    offline_checks,
    triangle_area_mm2,
)


class TiltedSketch3ptTest(unittest.TestCase):
    def test_area_is_the_independent_triangle_oracle(self):
        # Shoelace on the archived UV triangle; no feedback reference value.
        expected = (
            abs(
                (TRIANGLE_UV[1][0] - TRIANGLE_UV[0][0]) * (TRIANGLE_UV[2][1] - TRIANGLE_UV[0][1])
                - (TRIANGLE_UV[2][0] - TRIANGLE_UV[0][0]) * (TRIANGLE_UV[1][1] - TRIANGLE_UV[0][1])
            )
            / 2.0
        )
        self.assertAlmostEqual(triangle_area_mm2(TRIANGLE_UV), expected, places=12)
        self.assertAlmostEqual(expected, 999.6264427740043, places=9)

    def test_volume_matches_area_times_symmetric_depth(self):
        self.assertAlmostEqual(
            expected_volume_mm3(), triangle_area_mm2(TRIANGLE_UV) * DEPTH_MM, places=9
        )
        self.assertEqual(DEPTH_MM, 9.87008714331235)

    def test_normal_is_unit_length_and_matches_archived_geometry(self):
        normal = expected_normal()
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in normal)), 1.0, places=12)
        # The archived external report normal has three decimals; compare direction only.
        reported = (-0.678, -0.093, 0.730)
        dot = sum(normal[i] * reported[i] for i in range(3))
        self.assertGreater(abs(dot), 0.999)

    def test_converted_plan_is_accepted_and_keeps_original_precision(self):
        summary = offline_checks()
        self.assertEqual(
            summary["operation_kinds"],
            ["datum_points", "datum_points", "datum_points", "datum_plane", "sketch", "extrude"],
        )
        self.assertEqual(summary["depth_mm"], 9.87008714331235)
        self.assertGreater(summary["triangle_area_mm2"], 900.0)
        self.assertLess(summary["triangle_area_mm2"], 1100.0)


if __name__ == "__main__":
    unittest.main()
