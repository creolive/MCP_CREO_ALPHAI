"""Development gates must reject new debt, tool failures and incomplete source packages."""

import contextlib
import copy
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import dev_check, package


class DevelopmentWorkflow(unittest.TestCase):
    def snapshot(self):
        return {
            "schema_version": 1,
            "tool_versions": {"ruff": "fixture"},
            "configuration": {"pyproject.toml": "fixture"},
            "lint": [
                {
                    "path": "legacy.py",
                    "code": "F401",
                    "message": "unused import",
                    "source": "import old",
                    "count": 1,
                }
            ],
            "unformatted": {"legacy.py": "known-content"},
        }

    def test_new_problem_cannot_replace_old_problem_with_same_total_count(self):
        baseline = self.snapshot()
        current = copy.deepcopy(baseline)
        current["lint"][0]["source"] = "import different"
        self.assertTrue(dev_check.regressions(current, baseline))

    def test_additional_identical_problem_is_a_regression(self):
        baseline = self.snapshot()
        current = copy.deepcopy(baseline)
        current["lint"][0]["count"] = 2
        self.assertTrue(dev_check.regressions(current, baseline))

    def test_cleaning_debt_is_allowed_but_changed_unformatted_file_is_not(self):
        baseline = self.snapshot()
        current = copy.deepcopy(baseline)
        current["lint"] = []
        current["unformatted"] = {}
        self.assertEqual(dev_check.regressions(current, baseline), [])
        current["unformatted"] = {"legacy.py": "changed-content"}
        self.assertTrue(dev_check.regressions(current, baseline))

    def test_configuration_and_tool_changes_require_review(self):
        for key in ("schema_version", "tool_versions", "configuration"):
            with self.subTest(key=key):
                baseline = self.snapshot()
                current = copy.deepcopy(baseline)
                current[key] = "changed"
                self.assertTrue(dev_check.regressions(current, baseline))

    def test_checkout_line_endings_do_not_change_content_fingerprint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = root / "lf.py", root / "crlf.py"
            first.write_bytes(b"value = 1\n")
            second.write_bytes(b"value = 1\r\n")
            self.assertEqual(dev_check.source_hash(first), dev_check.source_hash(second))

    def test_line_movement_keeps_known_diagnostic_and_syntax_is_never_debt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "fixture.py"
            diagnostic = {
                "filename": str(source),
                "code": "F401",
                "message": "unused import",
                "location": {"row": 1},
            }
            source.write_text("import old\n", encoding="utf-8")
            before = dev_check.lint_entries([diagnostic], root)
            source.write_text("# inserted line\nimport old\n", encoding="utf-8")
            diagnostic["location"]["row"] = 2
            self.assertEqual(before, dev_check.lint_entries([diagnostic], root))
            diagnostic["code"] = "invalid-syntax"
            with self.assertRaises(RuntimeError):
                dev_check.lint_entries([diagnostic], root)

    def test_baseline_cannot_be_updated_without_a_reason(self):
        with (
            patch.object(dev_check, "collect_styles") as collect,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as raised:
                dev_check.main(["--write-baseline"])
            self.assertEqual(raised.exception.code, 2)
            collect.assert_not_called()

    def test_tool_failure_returns_failure_and_does_not_create_a_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "version.py").write_text('VERSION = "fixture"\n', encoding="utf-8")
            with (
                patch.object(dev_check, "ROOT", root),
                patch.object(dev_check, "git_state", return_value={}),
                patch.object(dev_check, "collect_styles", side_effect=RuntimeError("bad config")),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = dev_check.main(
                    ["--write-baseline", "--reason", "DEV-fixture: review", "--skip-unit"]
                )
            self.assertEqual(result, 1)
            self.assertFalse((root / dev_check.BASELINE).exists())
            report = json.loads((root / "build/development_check.json").read_text(encoding="utf-8"))
            self.assertFalse(report["success"])
            self.assertEqual(report["native_validation"], "not_run")

    def test_tool_configuration_exit_is_not_an_accepted_lint_result(self):
        with patch.object(
            dev_check.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(["fixture"], 2, "", "invalid configuration"),
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid configuration"):
                dev_check.command(["fixture"], cwd=Path.cwd(), accepted=(0, 1))

    def test_extracted_snapshot_does_not_inherit_parent_git_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(dev_check, "command", return_value=str(root)):
                self.assertEqual(
                    dev_check.git_state(root / "extracted"),
                    {"commit": None, "dirty": None, "git_status": "unavailable"},
                )

    def test_unit_failure_and_timeout_cannot_pass_the_combined_check(self):
        scenarios = (
            (subprocess.CompletedProcess(["fixture"], 1), None, "failed"),
            (None, subprocess.TimeoutExpired(["fixture"], 300), "timed_out"),
        )
        for result, error, expected in scenarios:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "version.py").write_text('VERSION = "fixture"\n', encoding="utf-8")
                current = {
                    **self.snapshot(),
                    "python_files_checked": 1,
                    "cpp_files_checked": 0,
                    "source_sha256": "fixture",
                }
                dev_check.save_json(root / dev_check.BASELINE, current)
                with (
                    patch.object(dev_check, "ROOT", root),
                    patch.object(dev_check, "git_state", return_value={}),
                    patch.object(dev_check, "collect_styles", return_value=current),
                    patch.object(
                        dev_check.subprocess, "run", return_value=result, side_effect=error
                    ),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(dev_check.main([]), 1)
                report = json.loads(
                    (root / "build/development_check.json").read_text(encoding="utf-8")
                )
                self.assertFalse(report["success"])
                self.assertEqual(report["unit_tests"], expected)

    def test_source_distribution_contains_governance_and_excludes_local_artifacts(self):
        root = package.ROOT
        files = {path.relative_to(root).as_posix() for path in package.source_files()}
        required = {
            "src/creo_mechdog/__init__.py",
            "src/creo_mechdog/paths.py",
            "src/creo_mechdog/update_check.py",
            "tests/unit/test_update_check.py",
            "AGENTS.md",
            "pyproject.toml",
            ".clang-format",
            ".editorconfig",
            ".gitattributes",
            "requirements-dev.txt",
            "tools/dev_check.py",
            "tools/test_result_delivery.cpp",
            "native/result_delivery.h",
            "docs/BACKLOG.md",
            "docs/development/style-baseline.json",
            ".github/workflows/checks.yml",
            ".github/pull_request_template.md",
        }
        self.assertTrue(required <= files, required - files)
        self.assertTrue(
            {"config.json", "client-config.json", "native/constants.inc"}.isdisjoint(files)
        )
        self.assertFalse(
            any(path.startswith(("build/", "jobs/", "models/", ".venv/")) for path in files)
        )


if __name__ == "__main__":
    unittest.main()
