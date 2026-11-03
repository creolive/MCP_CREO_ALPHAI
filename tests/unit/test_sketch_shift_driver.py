"""Offline regressions for the BUG-108 sketch-shift driver (no Creo, no MCP).

The driver's candidate table, its independent rigid fit and its judgement are
pure, so they can be checked without a session. A ``pass`` here never means the
absolute-free-branch was exercised: only a recorded live witness can do that.
"""

import unittest

import tools.test_sketch_shift_batch as driver


def witness(*, magnitude=0.000016, residual=0.0, tolerance_source="default_coordinates"):
    """A complete, self-consistent candidate that satisfies the target branch."""
    translation = {"u": magnitude, "v": 0.0}
    return {
        "case_id": "S01",
        "scope": "rigid_translation",
        "model_id": "model-1",
        "request": {
            "points": driver.TRIANGLE,
            "depth": driver.DEPTH_MM,
            "geometry_tolerance_mm": None,
            "expected_volume_mm3": driver.expected_volume_mm3(driver.TRIANGLE),
        },
        "stages": {
            "sketch": {
                "status": "succeeded",
                "sketch_shifted": {
                    "detected": True,
                    "rigid": True,
                    "translation_mm": translation,
                    "shape_deviation_mm": residual,
                    "residual_mm": residual,
                    "accepted_rigid": True,
                    "accepted_by_request": tolerance_source == "request",
                    "tolerance_source": tolerance_source,
                    "point_count": 3,
                },
                "geometry_deviation": {
                    "available": True,
                    "accepted_rigid": True,
                    "translation_mm": translation,
                },
            },
            "solid": {"status": "succeeded"},
        },
        "measurement": {
            "native": {"translation_mm": translation},
            "independent": {
                "translation_mm": translation,
                "magnitude_mm": magnitude,
                "residual_mm": residual,
                "point_count": 3,
            },
            "volume_mm3": driver.expected_volume_mm3(driver.TRIANGLE),
        },
        "saved_file_reloaded_and_verified": True,
        "followup": {"status": "succeeded"},
        "verification_level": "live",
    }


class RigidFit(unittest.TestCase):
    def test_translation_and_residual_are_recomputed_from_points(self):
        source = [[0.0, 0.0], [10.0, 0.0], [0.0, 5.0]]
        solved = [[x + 0.004, y - 0.002] for x, y in source]
        fit = driver.rigid_fit(source, solved)
        self.assertAlmostEqual(fit["translation_mm"]["u"], 0.004, places=12)
        self.assertAlmostEqual(fit["translation_mm"]["v"], -0.002, places=12)
        self.assertAlmostEqual(fit["residual_mm"], 0.0, places=12)
        self.assertEqual(fit["point_count"], 3)

    def test_deformed_profile_has_a_residual(self):
        source = [[0.0, 0.0], [10.0, 0.0], [0.0, 5.0]]
        solved = [[0.0, 0.0], [10.5, 0.0], [0.0, 5.0]]
        fit = driver.rigid_fit(source, solved)
        self.assertGreater(fit["residual_mm"], 1e-5)

    def test_mismatched_point_counts_are_not_fitted(self):
        self.assertIsNone(driver.rigid_fit([[0, 0], [1, 0], [0, 1]], [[0, 0], [1, 0]]))


class Candidates(unittest.TestCase):
    def test_candidate_models_are_independent_and_in_range(self):
        candidates = driver.shift_candidates()
        self.assertEqual(len(candidates), 9)
        names = [item["model_name"] for item in candidates]
        self.assertEqual(len(names), len(set(names)))
        offsets = [item["offset_mm"] for item in candidates]
        self.assertEqual(offsets.count(0.0), 3)
        self.assertEqual(offsets.count(40.0), 3)
        self.assertEqual(offsets.count(-260.0), 3)
        for item in candidates:
            self.assertIsNone(item["geometry_tolerance_mm"], "default gate only")
            self.assertGreater(item["expected_volume_mm3"], 0)

    def test_volume_oracle_is_the_prism(self):
        # 260 x 20.9 / 2 * 5 mm
        self.assertAlmostEqual(driver.expected_volume_mm3(driver.TRIANGLE), 13585.0, places=6)


class Judgment(unittest.TestCase):
    def test_no_shift_does_not_cover_acceptance(self):
        case = witness()
        case["stages"]["sketch"]["sketch_shifted"]["detected"] = False
        judged = driver.judge_shift_case(case)
        self.assertEqual(judged["verdict"], "unverified", judged)
        self.assertIn("control", judged["reason"])

    def test_explicit_tolerance_does_not_cover_default_gate(self):
        case = witness(tolerance_source="request")
        judged = driver.judge_shift_case(case)
        self.assertEqual(judged["verdict"], "unverified", judged)
        failed = {item["check"]: item["result"] for item in judged["checks"]}
        self.assertEqual(failed["default_coordinate_gate"], "unverified")

    def test_acceptance_requires_numeric_and_geometry_evidence(self):
        incomplete = witness()
        incomplete["measurement"]["independent"] = None
        incomplete["measurement"]["native"] = {}
        incomplete["stages"]["sketch"]["geometry_deviation"] = {}
        judged = driver.judge_shift_case(incomplete)
        self.assertEqual(judged["verdict"], "unverified", judged)

        contradictory = witness(magnitude=0.02)
        judged = driver.judge_shift_case(contradictory)
        self.assertEqual(judged["verdict"], "fail", judged)
        failed = [item["check"] for item in judged["checks"] if item["result"] == "fail"]
        self.assertIn("translation_within_limit", failed)

    def test_missing_stage_measurement_is_unverified(self):
        case = witness()
        case["stages"]["solid"] = {"status": None}
        judged = driver.judge_shift_case(case)
        self.assertEqual(judged["verdict"], "unverified", judged)

    def test_complete_witness_passes(self):
        judged = driver.judge_shift_case(witness())
        self.assertEqual(judged["verdict"], "pass", judged)
        self.assertEqual(judged["checks"][-1]["actual"], "succeeded")


if __name__ == "__main__":
    unittest.main()
