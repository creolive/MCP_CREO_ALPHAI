"""FEAT-039: the shipped surface examples stay runnable."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
DRIVER = ROOT / "tools" / "test_surface_chain.py"
EXAMPLE_FILES = ("p12_surface_blade.json", "surface_trim_merge.json")


class SurfaceExampleTests(unittest.TestCase):
    def test_the_plan_examples_exist(self):
        for name in EXAMPLE_FILES:
            self.assertTrue((EXAMPLES / name).exists(), name)

    def test_the_examples_use_phases_and_only_known_placeholders(self):
        for name in EXAMPLE_FILES:
            payload = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
            self.assertTrue(payload["phases"], name)
            for phase in payload["phases"]:
                self.assertTrue(phase["operations"], name)
            blob = json.dumps(payload)
            for kind in ("$curve:", "$quilt:", "$body:"):
                if kind in blob:
                    self.assertIn(kind[1:].rstrip(":"), ("curve", "quilt", "body"))

    def test_the_examples_pass_the_offline_check(self):
        from tools import test_surface_chain as driver

        for name in EXAMPLE_FILES:
            report = driver.case_example_offline(EXAMPLES / name)
            self.assertTrue(report["passed"], (name, report.get("checks")))

    def test_the_driver_takes_an_example_file(self):
        driver = DRIVER.read_text(encoding="utf-8")
        self.assertIn('"--example"', driver)
        self.assertIn("case_example_live", driver)


if __name__ == "__main__":
    unittest.main()
