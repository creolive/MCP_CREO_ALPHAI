"""DEV-050: unit-stage timeout budget of dev_check must stay configurable and honest.

The stubs below replace the real unit run, so the 300 vs 347 seconds conflict of
DEV-050 is reproduced without waiting for a full suite.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools import dev_check

FIXTURE_STYLES = {
    "schema_version": 1,
    "tool_versions": {"ruff": "fixture"},
    "configuration": {"pyproject.toml": "fixture"},
    "lint": [],
    "unformatted": {},
    "python_files_checked": 1,
    "cpp_files_checked": 0,
    "source_sha256": "fixture",
}


def accept(command, **kwargs):
    """Stand-in unit stage that completes successfully."""
    return subprocess.CompletedProcess(command, 0, "", "")


def fail_with_exit_code(command, **kwargs):
    return subprocess.CompletedProcess(command, 3, "", "unit failures")


def time_out(command, **kwargs):
    raise subprocess.TimeoutExpired(command, kwargs["timeout"])


def suite_of_347_seconds(command, **kwargs):
    """Stand-in for the 1017-test suite that needs about 347 seconds.

    Any budget below 347 seconds kills a run that would have passed, which is
    exactly the hardcoded 300-second conflict recorded in DEV-050.
    """
    budget = kwargs["timeout"]
    if budget < 347:
        raise subprocess.TimeoutExpired(command, budget)
    return subprocess.CompletedProcess(command, 0, "", "")


def never_run(command, **kwargs):
    raise AssertionError(f"subprocess.run must not be called: {command!r} {kwargs}")


class DevCheckTimeout(unittest.TestCase):
    def run_dev_check(self, argv, unit_stage=accept):
        """Run dev_check.main against an isolated root and a stubbed unit stage."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "version.py").write_text('VERSION = "fixture"\n', encoding="utf-8")
            dev_check.save_json(root / dev_check.BASELINE, dict(FIXTURE_STYLES))
            collect = MagicMock(return_value=dict(FIXTURE_STYLES))
            run = MagicMock(side_effect=unit_stage)
            out, err = io.StringIO(), io.StringIO()
            with (
                patch.object(dev_check, "ROOT", root),
                patch.object(dev_check, "git_state", return_value={}),
                patch.object(dev_check, "collect_styles", collect),
                patch.object(dev_check.subprocess, "run", run),
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(err),
            ):
                try:
                    code = dev_check.main(argv)
                except SystemExit as exited:
                    code = exited.code
            report_path = root / "build/development_check.json"
            report = (
                json.loads(report_path.read_text(encoding="utf-8"))
                if report_path.exists()
                else None
            )
            return code, report, run, collect, err.getvalue()

    def test_default_budget_is_900_seconds_and_reaches_the_unit_stage(self):
        code, report, run, _collect, _err = self.run_dev_check([])
        self.assertEqual(code, 0)
        self.assertEqual(report["unit_test_timeout_seconds"], 900)
        self.assertEqual(report["unit_tests"], "passed")
        self.assertEqual(run.call_args.kwargs["timeout"], 900)

    def test_explicit_budget_overrides_the_default(self):
        code, report, run, _collect, _err = self.run_dev_check(["--unit-timeout-seconds", "1200"])
        self.assertEqual(code, 0)
        self.assertEqual(report["unit_test_timeout_seconds"], 1200)
        self.assertEqual(report["unit_tests"], "passed")
        self.assertEqual(run.call_args.kwargs["timeout"], 1200)

    def test_invalid_budgets_are_rejected_during_argument_parsing(self):
        for value in ("0", "-3", "abc", "12.5", ""):
            with self.subTest(value=value):
                code, report, run, collect, err = self.run_dev_check(
                    ["--unit-timeout-seconds", value], unit_stage=never_run
                )
                self.assertNotEqual(code, 0)
                self.assertIsNone(report)
                run.assert_not_called()
                collect.assert_not_called()
                self.assertIn("--unit-timeout-seconds", err)

    def test_skip_unit_skips_the_run_but_keeps_the_budget(self):
        code, report, run, _collect, _err = self.run_dev_check(
            ["--skip-unit", "--unit-timeout-seconds", "45"], unit_stage=never_run
        )
        self.assertEqual(code, 0)
        self.assertTrue(report["success"])
        self.assertEqual(report["unit_tests"], "not_run")
        self.assertEqual(report["unit_test_timeout_seconds"], 45)
        run.assert_not_called()
        code, report, run, _collect, err = self.run_dev_check(
            ["--skip-unit", "--unit-timeout-seconds", "0"], unit_stage=never_run
        )
        self.assertNotEqual(code, 0)
        self.assertIsNone(report)
        run.assert_not_called()
        self.assertIn("--unit-timeout-seconds", err)

    def test_nonzero_unit_exit_is_reported_failed(self):
        code, report, run, _collect, _err = self.run_dev_check([], unit_stage=fail_with_exit_code)
        self.assertEqual(code, 1)
        self.assertFalse(report["success"])
        self.assertEqual(report["unit_tests"], "failed")
        self.assertEqual(report["unit_test_timeout_seconds"], 900)
        self.assertEqual(run.call_args.kwargs["timeout"], 900)

    def test_timeout_is_reported_timed_out_and_never_success(self):
        code, report, run, _collect, _err = self.run_dev_check(
            ["--unit-timeout-seconds", "300"], unit_stage=time_out
        )
        self.assertEqual(code, 1)
        self.assertFalse(report["success"])
        self.assertEqual(report["unit_tests"], "timed_out")
        self.assertNotEqual(report["unit_tests"], "passed")
        self.assertNotEqual(report["unit_tests"], "failed")
        self.assertEqual(run.call_args.kwargs["timeout"], 300)

    def test_normal_completion_is_reported_passed_and_success(self):
        code, report, run, _collect, _err = self.run_dev_check(
            ["--unit-timeout-seconds", "600"], unit_stage=accept
        )
        self.assertEqual(code, 0)
        self.assertTrue(report["success"])
        self.assertEqual(report["unit_tests"], "passed")
        self.assertEqual(report["unit_test_timeout_seconds"], 600)
        self.assertEqual(run.call_args.kwargs["timeout"], 600)

    def test_stub_reproduces_hardcoded_300_second_budget_conflict(self):
        legacy, legacy_report, _run, _collect, _err = self.run_dev_check(
            ["--unit-timeout-seconds", "300"], unit_stage=suite_of_347_seconds
        )
        self.assertEqual(legacy, 1)
        self.assertEqual(legacy_report["unit_tests"], "timed_out")
        self.assertFalse(legacy_report["success"])
        fixed, fixed_report, run, _collect, _err = self.run_dev_check(
            [], unit_stage=suite_of_347_seconds
        )
        self.assertEqual(fixed, 0)
        self.assertEqual(fixed_report["unit_tests"], "passed")
        self.assertTrue(fixed_report["success"])
        self.assertEqual(fixed_report["unit_test_timeout_seconds"], 900)
        self.assertEqual(run.call_args.kwargs["timeout"], 900)


if __name__ == "__main__":
    unittest.main()
