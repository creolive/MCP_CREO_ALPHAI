"""FEAT-039/S03: the join contract in the surface chain driver."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "tools" / "test_surface_chain.py"


class SurfaceJoinContractTests(unittest.TestCase):
    def test_driver_declares_the_join_case(self):
        driver = DRIVER.read_text(encoding="utf-8")
        self.assertIn('"join"', driver)
        self.assertRegex(driver, r"(?s)CASES = \([^)]*\"join\"")

    def test_join_case_offline_passes(self):
        from tools import test_surface_chain as driver

        report = driver.case_join_offline()
        self.assertTrue(report["passed"], report.get("checks"))
        self.assertEqual(report["blocked_steps"], [])

    def test_the_merge_operator_is_published(self):
        from creo_mechdog.capabilities import UNAVAILABLE_OPERATIONS

        self.assertNotIn("quilt_merge", UNAVAILABLE_OPERATIONS)

    def test_the_analytic_oracle_is_consistent(self):
        from tools import surface_chain_join as join

        self.assertEqual(
            join.JOIN_UNION_AREA, join.JOIN_AREA_A + join.JOIN_AREA_B - join.JOIN_SHARED
        )
        self.assertEqual(join.JOIN_UNION_AREA, 1400.0)
        self.assertEqual(join.JOIN_SHARED + join.JOIN_OUTSIDE, join.JOIN_AREA_B)

    def test_the_join_plan_uses_delivered_operators_only(self):
        from tools import surface_chain_join as join

        kinds = {operation["op"] for operation in join.JOIN_PLAN}
        self.assertTrue(kinds <= {"sketch", "surface_fill", "datum_plane"}, kinds)
        self.assertNotIn("quilt_merge", kinds)


if __name__ == "__main__":
    unittest.main()
