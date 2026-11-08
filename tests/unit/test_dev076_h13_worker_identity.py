"""DEV-076 / H13—H16: worker build identity, overlap diagnostics, trim handles.

Offline only. These tests pin the admission and receipt contracts; they do not
claim a Creo 10 worker, a live overlap budget or a consecutive trim was run.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import bridge
from creo_mechdog import capability_pages
from creo_mechdog.capabilities import (
    KNOWN_LIMITATIONS,
    PLAN_EXAMPLES,
    families,
    project_worker_availability,
    require_worker_availability,
)
from creo_mechdog.operation_results import normalize_surface_group
from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
NATIVE_GROUP = ROOT / "native" / "surface_group.cpp"
NATIVE_TRIM = ROOT / "native" / "surface_trim.cpp"
GENERIC_BRIDGE = ROOT / "generic_bridge.py"

DIGEST = "a" * 64


def identity(available: bool, *, status: str = "verified") -> dict:
    return {
        "identity_status": status,
        "identity_schema": 1,
        "source_digest": DIGEST,
        "worker_sha256": "b" * 64,
        "identity_source": "worker_self_report",
        "features": {
            "surface_loft": {
                "available": available,
                "state": "compiled" if available else "sdk_header_missing",
                "sdk_requirements": ["Probbl.h"],
                "missing_sdk_requirements": [] if available else ["Probbl.h"],
            }
        },
    }


class WorkerBuildInfoParseTests(unittest.TestCase):
    def test_accepts_a_complete_self_report(self):
        parsed = bridge._parse_worker_build_info(
            {
                "identity_schema": 1,
                "source_digest": DIGEST,
                "features": {
                    "surface_loft": {
                        "available": False,
                        "state": "sdk_header_missing",
                        "sdk_requirements": ["Probbl.h"],
                        "missing_sdk_requirements": ["Probbl.h"],
                    }
                },
            },
            "b" * 64,
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["identity_status"], "verified")
        self.assertEqual(parsed["source_digest"], DIGEST)
        self.assertFalse(parsed["features"]["surface_loft"]["available"])

    def test_rejects_missing_digest_or_feature_flag(self):
        base = {
            "identity_schema": 1,
            "source_digest": DIGEST,
            "features": {"surface_loft": {"available": True}},
        }
        self.assertIsNone(bridge._parse_worker_build_info({**base, "source_digest": None}, "x"))
        self.assertIsNone(
            bridge._parse_worker_build_info(
                {**base, "features": {"surface_loft": {"state": "compiled"}}}, "x"
            )
        )
        self.assertIsNone(bridge._parse_worker_build_info({**base, "identity_schema": 2}, "x"))


class WorkerAdmissionTests(unittest.TestCase):
    def test_rejects_surface_loft_before_a_job_when_the_worker_lacks_the_header(self):
        with self.assertRaisesRegex(ValueError, "compiled out of the current worker"):
            require_worker_availability([{"op": "surface_loft"}], identity(available=False))

    def test_accepts_surface_loft_when_the_worker_reports_the_route(self):
        require_worker_availability([{"op": "surface_loft"}], identity(available=True))

    def test_unknown_identity_never_replaces_the_runtime_error(self):
        for unknown in (
            None,
            {},
            {"identity_status": "worker_missing"},
            identity(available=False, status="invalid_build_info"),
        ):
            with self.subTest(unknown=unknown):
                require_worker_availability([{"op": "surface_loft"}], unknown)

    def test_other_operations_are_not_gated_by_worker_identity(self):
        require_worker_availability([{"op": "sketch"}], identity(available=False))

    def test_submit_checks_the_worker_before_taking_the_channel(self):
        source = GENERIC_BRIDGE.read_text(encoding="utf-8")
        self.assertIn("require_worker_availability", source)
        self.assertLess(
            source.index("require_worker_availability(operations"),
            source.index('with bridge.toolkit_lock(operation="submit"'),
        )


class WorkerCapabilityProjectionTests(unittest.TestCase):
    def test_unavailable_worker_turns_the_family_off(self):
        projected = project_worker_availability(families(), identity(available=False))
        entry = projected["surface_loft"]
        self.assertEqual(entry["availability"], "unavailable")
        self.assertFalse(entry["available"])
        self.assertFalse(entry["enabled"])
        self.assertIn("Probbl.h", entry["unavailable_reason"])
        self.assertEqual(entry["worker_build_identity"]["source_digest"], DIGEST)

    def test_available_worker_keeps_the_projectable_route(self):
        projected = project_worker_availability(families(), identity(available=True))
        entry = projected["surface_loft"]
        self.assertEqual(entry["availability"], "available")
        self.assertTrue(entry["available"])
        self.assertTrue(entry["enabled"])

    def test_unknown_identity_keeps_the_conditional_metadata(self):
        for unknown in (None, {"identity_status": "worker_missing"}):
            with self.subTest(unknown=unknown):
                entry = project_worker_availability(families(), unknown)["surface_loft"]
                self.assertEqual(entry["availability"], "sdk_conditional")
                self.assertNotIn("available", entry)


class OverlapBudgetDiagnosticsTests(unittest.TestCase):
    def test_native_status_reports_budget_and_coverage_without_an_area(self):
        source = NATIVE_GROUP.read_text(encoding="utf-8")
        for marker in (
            '"sample_budget"',
            '"sample_tests_required"',
            '"sample_tests_attempted"',
            '"sample_test_coverage"',
            '"budget_exceeded"',
            '"containment_errors_observed"',
        ):
            self.assertIn(marker, source)
        self.assertIn("J overlap_area_mm2 = overlap_outcome.available", source)

    def test_unavailable_overlap_stays_null_but_keeps_partial_diagnostics(self):
        group = normalize_surface_group(
            {
                "quilt_ids": [1, 2],
                "overlap_area_mm2": 0.0,
                "overlap_status": {
                    "available": False,
                    "reason": "overlap_sample_budget_exceeded",
                    "sample_budget": 20000,
                    "sample_tests_required": 24000,
                    "sample_tests_attempted": 18000,
                    "sample_test_coverage": 0.75,
                    "budget_exceeded": True,
                    "partial": True,
                    "containment_errors_observed": 2,
                    "detected": True,
                },
            }
        )
        self.assertIsNone(group["overlap_area_mm2"])
        self.assertIsNone(group["overlap_status"]["detected"])
        self.assertEqual(group["overlap_status"]["sample_budget"], 20000)
        self.assertTrue(group["overlap_status"]["budget_exceeded"])
        self.assertAlmostEqual(group["overlap_status"]["sample_test_coverage"], 0.75)


class TrimResultHandleTests(unittest.TestCase):
    def test_trim_receipt_publishes_a_verified_result_handle(self):
        source = NATIVE_TRIM.read_text(encoding="utf-8")
        for marker in (
            '"result_quilt_id"',
            '"result_quilt_handle"',
            "kept_handle_available",
            '"retrimmed_target_quilt"',
        ):
            self.assertIn(marker, source)
        self.assertLess(
            source.index("kept_handle_available = true"),
            source.index('details["result_quilt_id"]'),
        )


class KnownLimitationsTests(unittest.TestCase):
    def test_entries_carry_the_structured_contract(self):
        self.assertGreaterEqual(len(KNOWN_LIMITATIONS), 10)
        for entry in KNOWN_LIMITATIONS:
            with self.subTest(entry=entry["id"]):
                for key in ("id", "condition", "release", "evidence", "configurable", "effect"):
                    self.assertIn(key, entry)
                self.assertIsInstance(entry["configurable"], bool)

    def test_compact_counts_and_full_section_paginate(self):
        payload = {"families": {}, "known_limitations": list(KNOWN_LIMITATIONS)}
        capability_pages.reset_snapshot()
        compact = capability_pages.capabilities_response(lambda: payload, detail="compact")
        self.assertEqual(compact["known_limitations"]["count"], len(KNOWN_LIMITATIONS))
        full = capability_pages.capabilities_response(
            lambda: payload, detail="full", section="known_limitations", limit=50
        )
        self.assertEqual(full["total"], len(KNOWN_LIMITATIONS))
        self.assertTrue(full["complete"])
        self.assertLessEqual(
            len(str(full).encode("utf-8", errors="replace")), capability_pages.PAGE_BYTES
        )


class PlanExamplesTests(unittest.TestCase):
    def test_every_example_passes_schema_admission(self):
        self.assertGreaterEqual(len(PLAN_EXAMPLES), 6)
        for example in PLAN_EXAMPLES:
            with self.subTest(example=example["name"]):
                self.assertIn("goal", example)
                validate_operations(example["operations"])

    def test_compact_counts_and_full_section_paginate(self):
        payload = {"families": {}, "plan_examples": list(PLAN_EXAMPLES)}
        capability_pages.reset_snapshot()
        compact = capability_pages.capabilities_response(lambda: payload, detail="compact")
        self.assertEqual(compact["plan_examples"]["count"], len(PLAN_EXAMPLES))
        full = capability_pages.capabilities_response(
            lambda: payload, detail="full", section="plan_examples", limit=50
        )
        self.assertEqual(full["total"], len(PLAN_EXAMPLES))
        self.assertTrue(full["complete"])


if __name__ == "__main__":
    unittest.main()
