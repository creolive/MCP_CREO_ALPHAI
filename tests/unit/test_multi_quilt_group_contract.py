"""FEAT-039/H10 driver contract: the offline half of the multi-quilt probe."""

from __future__ import annotations

import unittest

from tools import test_multi_quilt_group as driver


class MultiQuiltGroupContractTests(unittest.TestCase):
    def test_offline_contract_passes(self) -> None:
        report = driver.case_offline()

        self.assertTrue(report["passed"], report["checks"])
        self.assertEqual(report["native_multi_quilt_group"], "not_verified")

    def test_group_plan_has_two_lofts_and_one_fill(self) -> None:
        plan = driver.group_plan()

        self.assertEqual(sum(op["op"] == "surface_loft" for op in plan), 2)
        self.assertEqual(sum(op["op"] == "surface_fill" for op in plan), 1)
        sections = [op["sections"] for op in plan if op["op"] == "surface_loft"]
        self.assertEqual(sections, [["loft_a_low", "loft_a_high"], ["loft_b_low", "loft_b_high"]])

    def test_group_area_oracle(self) -> None:
        self.assertEqual(driver.LOFT_AREA, 800.0)
        self.assertEqual(driver.FLOOR_AREA, 1600.0)
        self.assertEqual(driver.GROUP_AREA, 3200.0)


if __name__ == "__main__":
    unittest.main()
