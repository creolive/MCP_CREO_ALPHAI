"""Machine-readable evidence for a unittest run (DEV-066)."""

from __future__ import annotations

import unittest
from typing import Any

from version import VERSION


def build_unit_report(
    result: unittest.TestResult,
    *,
    timestamp: float,
    duration_seconds: float,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Keep legacy totals and distinguish skipped cases and source identity."""
    return {
        "version": VERSION,
        "timestamp": timestamp,
        "tests_run": result.testsRun,
        "success": result.wasSuccessful(),
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "skipped_tests": [{"test": str(test), "reason": reason} for test, reason in result.skipped],
        "duration_seconds": duration_seconds,
        "source": {
            key: provenance.get(key)
            for key in (
                "commit",
                "branch",
                "dirty",
                "git_status",
                "source_fingerprint",
                "source_scope",
                "source_status",
                "source_file_count",
                "source_errors",
            )
        },
    }
