"""Regression for isolated tools namespace imports, independent of test order."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ToolPackageImports(unittest.TestCase):
    def test_reported_modules_import_in_fresh_isolated_processes(self):
        for module in ("test_tilted_sketch_lifecycle", "test_guards", "summarize_multisection"):
            with self.subTest(module=module), tempfile.TemporaryDirectory() as cwd:
                code = "import sys, importlib; sys.path.insert(0, sys.argv[1]); importlib.import_module(sys.argv[2])"
                result = subprocess.run(
                    [sys.executable, "-I", "-c", code, str(ROOT), "tools." + module],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
