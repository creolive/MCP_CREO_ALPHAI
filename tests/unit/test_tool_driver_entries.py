"""Regression: live drivers run both as `python tools/<driver>.py` and `-m tools.<driver>`.

Without these entry points, running a driver by path from the repository root
failed at import time (`ModuleNotFoundError: No module named 'tools'` /
`'bridge'`) because the repository root was not on sys.path. Only `--help` is
exercised, so no Creo session is required.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRIVERS = [
    "test_assembly_matrix",
    "test_assembly_pipeline",
    "test_file_adoption",
]


def entry_env() -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


class ToolDriverEntryTest(unittest.TestCase):
    def run_entry(self, args: list[str]) -> None:
        result = subprocess.run(
            args,
            cwd=ROOT,
            env=entry_env(),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"{args!r} failed:\n{result.stderr}",
        )
        self.assertIn("usage:", result.stdout)

    def test_direct_script_entry_help(self) -> None:
        for driver in DRIVERS:
            with self.subTest(driver=driver):
                self.run_entry([sys.executable, str(ROOT / "tools" / f"{driver}.py"), "--help"])

    def test_module_entry_help(self) -> None:
        for driver in DRIVERS:
            with self.subTest(driver=driver):
                self.run_entry([sys.executable, "-m", f"tools.{driver}", "--help"])


if __name__ == "__main__":
    unittest.main()
