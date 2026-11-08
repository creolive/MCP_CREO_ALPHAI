import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from tools import test_unit


class UnitReportTests(unittest.TestCase):
    def test_runner_records_skips_duration_and_explicit_source(self):
        class Cases(unittest.TestCase):
            def test_pass(self):
                self.assertTrue(True)

            @unittest.skip("fixture has no SDK")
            def test_skip(self):
                pass

        source = {
            "commit": None,
            "branch": None,
            "dirty": None,
            "git_status": "unavailable",
            "source_fingerprint": "a" * 64,
            "source_scope": "distributed_source",
            "source_status": "complete",
            "source_errors": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(test_unit, "ROOT", root),
                patch.object(
                    test_unit.unittest.defaultTestLoader,
                    "discover",
                    return_value=unittest.defaultTestLoader.loadTestsFromTestCase(Cases),
                ),
                patch.object(test_unit, "local_provenance", return_value=source),
                redirect_stderr(io.StringIO()),
            ):
                code = test_unit.main()
            report = json.loads((root / "build/unit_test_report.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(report["tests_run"], 2)
        self.assertEqual(report["skipped"], 1)
        self.assertIn("fixture has no SDK", report["skipped_tests"][0]["reason"])
        self.assertGreaterEqual(report["duration_seconds"], 0)
        self.assertEqual(report["source"]["git_status"], "unavailable")
        self.assertIsNone(report["source"]["commit"])
        self.assertEqual(report["source"]["source_fingerprint"], "a" * 64)

    def test_failed_run_keeps_nonzero_exit_and_report(self):
        class Failure(unittest.TestCase):
            def runTest(self):
                self.fail("expected fixture failure")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(test_unit, "ROOT", root),
                patch.object(
                    test_unit.unittest.defaultTestLoader,
                    "discover",
                    return_value=unittest.TestSuite([Failure()]),
                ),
                patch.object(
                    test_unit, "local_provenance", return_value={"git_status": "unavailable"}
                ),
                redirect_stderr(io.StringIO()),
            ):
                code = test_unit.main()
            report = json.loads((root / "build/unit_test_report.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertFalse(report["success"])
        self.assertEqual(report["failures"], 1)
        self.assertEqual(report["errors"], 0)
