"""FEAT-039/S05: the surface sweep contract and its analytic oracles."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SurfaceSweepContractTests(unittest.TestCase):
    def test_the_oracles_are_consistent(self):
        from tools import surface_chain_sweep as sweep

        self.assertEqual(sweep.OPEN_AREA, 2400.0)
        self.assertEqual(sweep.CAPPED_AREA, 4000.0)
        self.assertEqual(sweep.BOX_VOLUME, 16000.0)
        self.assertEqual(sweep.CAPPED_AREA, sweep.OPEN_AREA + 2.0 * sweep.WIDTH * sweep.HEIGHT)

    def test_the_case_offline_passes(self):
        from tools import test_surface_chain as driver

        report = driver.case_sweep_offline()
        self.assertTrue(report["passed"], report.get("checks"))
        self.assertEqual(report["blocked_steps"], ["loft_surface"])

    def test_the_plan_uses_only_delivered_operators(self):
        from tools import surface_chain_sweep as sweep

        for capped in (False, True):
            kinds = {operation["op"] for operation in sweep.sweep_plan(capped)}
            self.assertTrue(kinds <= {"sketch", "sweep"}, kinds)

    def test_the_surface_mode_is_documented_in_the_capabilities(self):
        from creo_mechdog.capabilities import families

        entry = families()["sweep"]
        self.assertIn("2400.000 mm2", entry["native_test"])
        self.assertIn("constant section", entry["limits"])

    def test_the_loft_surface_mode_stays_refused(self):
        from creo_mechdog.capabilities import require_available

        with self.assertRaises(ValueError) as caught:
            require_available(
                [
                    {
                        "op": "loft",
                        "label": "loft_surface",
                        "sections": ["sweep_path"],
                        "mode": "surface",
                    }
                ]
            )
        self.assertIn("surface", str(caught.exception))

    def test_the_driver_declares_the_case(self):
        driver = (ROOT / "tools" / "test_surface_chain.py").read_text(encoding="utf-8")
        self.assertRegex(driver, r"(?s)CASES = \([^)]*\"sweep_surface\"")


if __name__ == "__main__":
    unittest.main()
