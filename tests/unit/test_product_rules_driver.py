"""Offline driver report preservation and provenance."""

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import test_adoption_product_rules as driver


class ProductRulesDriverTests(unittest.TestCase):
    def test_refuses_existing_report_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            original = b"existing evidence\n"
            path.write_bytes(original)
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(FileExistsError):
                driver.main(["--output", directory])
            self.assertEqual(path.read_bytes(), original)

    def test_pure_checks_have_provenance_without_processes(self):
        with patch.object(subprocess, "run", side_effect=AssertionError("process")):
            report = driver.run_checks()
        self.assertTrue(report["passed"])
        for name in ("timestamp_utc", "version", "platform", "source_sha256"):
            self.assertTrue(report[name])
        self.assertEqual(report["native"], "not_run")
        self.assertEqual(report["saved_reload"], "not_run")

    def test_cli_report_identity_and_rejects_live(self):
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(driver.main(["--output", directory]), 0)
            report = json.loads((Path(directory) / "report.json").read_text(encoding="utf-8"))
            if report["git"]["commit"] is None:
                self.assertIsNone(report["git"]["dirty"])
                self.assertTrue(report["git"]["error"])
            else:
                self.assertEqual(len(report["git"]["commit"]), 40)
                self.assertIsInstance(report["git"]["dirty"], bool)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            driver.main(["--live"])
        self.assertEqual(error.exception.code, 2)

    def test_git_identity_known_and_unavailable(self):
        with patch.object(
            subprocess,
            "run",
            side_effect=[
                subprocess.CompletedProcess([], 0, "a" * 40 + "\n"),
                subprocess.CompletedProcess([], 0, " M server.py\n"),
            ],
        ):
            self.assertEqual(driver.git_identity(), {"commit": "a" * 40, "dirty": True})
        with patch.object(subprocess, "run", side_effect=FileNotFoundError("git unavailable")):
            identity = driver.git_identity()
        self.assertIsNone(identity["commit"])
        self.assertIsNone(identity["dirty"])
        self.assertIn("git unavailable", identity["error"])
