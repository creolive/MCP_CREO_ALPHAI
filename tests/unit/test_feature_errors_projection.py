"""BUG-097 L2: bounded CompleteFeature error receipt projection and wiring.

Offline only. The projection tests feed synthetic native blocks; the native
assertions read native/generic.cpp, native/geometry.cpp and
native/sketch_solver.cpp to lock the wiring. Nothing connects to Creo, no
Toolkit call is made and no geometry result is claimed here.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from creo_mechdog import operation_results

NATIVE = Path(__file__).resolve().parents[2] / "native"
PYTHON_ROOT = Path(__file__).resolve().parents[2]

SAMPLE_LIMIT = 20


def native_source(name: str) -> str:
    return (NATIVE / name).read_text(encoding="utf-8")


def region(source: str, start: str, stop: str) -> str:
    begin = source.index(start)
    return source[begin : source.index(stop, begin)]


def native_block(**overrides) -> dict:
    block = {
        "api": "ProFeatureWithoptionsRedefine",
        "code": -1,
        "failed_stage": "CompleteFeature",
        "element_errors": {
            "total": 2,
            "truncated": False,
            "sample": [
                {"element": 2889, "type": 12590, "error": -1},
                {"element": 2890, "type": 12591, "error": 5},
            ],
        },
        "section_errors": {
            "available": True,
            "total": 0,
            "truncated": False,
            "sample": [],
        },
    }
    block.update(overrides)
    return block


class NormalizeFeatureErrorsTests(unittest.TestCase):
    def test_wellformed_block_passes_through_with_types_coerced(self):
        normalized = operation_results.normalize_feature_errors(native_block())
        self.assertEqual(normalized["api"], "ProFeatureWithoptionsRedefine")
        self.assertEqual(normalized["code"], -1)
        self.assertEqual(normalized["failed_stage"], "CompleteFeature")
        self.assertEqual(normalized["element_errors"]["total"], 2)
        self.assertFalse(normalized["element_errors"]["truncated"])
        self.assertEqual(len(normalized["element_errors"]["sample"]), 2)
        self.assertTrue(normalized["section_errors"]["available"])
        self.assertEqual(normalized["section_errors"]["sample"], [])

    def test_sample_is_capped_at_twenty_with_totals_kept(self):
        block = native_block(
            element_errors={
                "total": 25,
                "truncated": True,
                "sample": [
                    {"element": index, "type": 100 + index, "error": index - 30}
                    for index in range(25)
                ],
            }
        )
        normalized = operation_results.normalize_feature_errors(block)
        self.assertEqual(len(normalized["element_errors"]["sample"]), SAMPLE_LIMIT)
        self.assertEqual(normalized["element_errors"]["total"], 25)
        self.assertTrue(normalized["element_errors"]["truncated"])

    def test_oversized_sample_is_truncated_by_the_projection_itself(self):
        block = native_block(
            element_errors={
                "total": 25,
                "truncated": False,
                "sample": [{"element": index, "type": 1, "error": 2} for index in range(25)],
            }
        )
        normalized = operation_results.normalize_feature_errors(block)
        self.assertEqual(len(normalized["element_errors"]["sample"]), SAMPLE_LIMIT)
        self.assertTrue(normalized["element_errors"]["truncated"])

    def test_missing_section_capture_stays_explicitly_unavailable(self):
        block = native_block(
            section_errors={"available": False, "total": None, "truncated": None, "sample": []}
        )
        normalized = operation_results.normalize_feature_errors(block)
        self.assertFalse(normalized["section_errors"]["available"])
        self.assertIsNone(normalized["section_errors"]["total"])
        self.assertIn("unavailable_reason", normalized["section_errors"])
        self.assertTrue(normalized["section_errors"]["unavailable_reason"])

    def test_absent_section_block_gains_an_explicit_unavailable_reason(self):
        block = native_block()
        del block["section_errors"]
        normalized = operation_results.normalize_feature_errors(block)
        self.assertFalse(normalized["section_errors"]["available"])
        self.assertEqual(normalized["section_errors"]["sample"], [])
        self.assertTrue(normalized["section_errors"]["unavailable_reason"])

    def test_uninterpretable_block_degrades_to_explicit_unavailable(self):
        for raw in (None, "CompleteFeature=-1", 42, ["element=1"]):
            with self.subTest(raw=raw):
                normalized = operation_results.normalize_feature_errors(raw)
                self.assertIsNone(normalized["api"])
                self.assertIsNone(normalized["code"])
                self.assertEqual(normalized["element_errors"]["sample"], [])
                self.assertFalse(normalized["section_errors"]["available"])
                self.assertTrue(normalized["section_errors"]["unavailable_reason"])

    def test_non_integer_fields_are_nulled_not_invented(self):
        block = native_block(
            code="-1",
            element_errors={
                "total": "2",
                "truncated": "no",
                "sample": [{"element": "2889", "type": None, "error": -1}],
            },
        )
        normalized = operation_results.normalize_feature_errors(block)
        self.assertIsNone(normalized["code"])
        self.assertIsNone(normalized["element_errors"]["total"])
        self.assertIsNone(normalized["element_errors"]["truncated"])
        entry = normalized["element_errors"]["sample"][0]
        self.assertIsNone(entry["element"])
        self.assertIsNone(entry["type"])
        self.assertEqual(entry["error"], -1)


class AnnotateWiringTests(unittest.TestCase):
    def test_failed_result_keeps_normalized_report_and_operation_blocks(self):
        result = {
            "success": False,
            "message": "Toolkit call CompleteFeature failed with code -1 during execute_sketch",
            "feature_errors": native_block(),
            "operations": [
                {
                    "op": "sketch",
                    "index": 0,
                    "label": "smk",
                    "succeeded": False,
                    "execution_status": "failed",
                    "feature_errors": native_block(),
                }
            ],
        }
        annotated = operation_results.annotate_native_result(result, readonly=False)
        self.assertEqual(annotated["feature_errors"]["failed_stage"], "CompleteFeature")
        operation = annotated["operations"][0]
        self.assertEqual(operation["execution_status"], "failed")
        self.assertEqual(operation["feature_errors"]["api"], "ProFeatureWithoptionsRedefine")
        self.assertEqual(len(operation["feature_errors"]["element_errors"]["sample"]), 2)

    def test_operations_block_is_normalized_even_without_an_operation_list(self):
        result = {"success": False, "feature_errors": native_block()}
        annotated = operation_results.annotate_native_result(result, readonly=False)
        self.assertEqual(annotated["feature_errors"]["code"], -1)

    def test_results_without_a_block_stay_untouched(self):
        result = {"success": False, "operations": [{"op": "sketch", "index": 0}]}
        annotated = operation_results.annotate_native_result(result, readonly=False)
        self.assertNotIn("feature_errors", annotated)
        self.assertNotIn("feature_errors", annotated["operations"][0])

    def test_successful_results_are_not_given_synthetic_errors(self):
        result = {"success": True, "operations": [{"op": "sketch", "index": 0}]}
        annotated = operation_results.annotate_native_result(result, readonly=False)
        self.assertNotIn("feature_errors", annotated)
        self.assertEqual(annotated["operations"][0]["execution_status"], "succeeded")


class NativeWiringTests(unittest.TestCase):
    """Source-marker locks: the receipt must be produced and consumed."""

    def test_redefine_captures_the_report_before_checking_the_code(self):
        generic = native_source("generic.cpp")
        body = region(generic, "static void redefine(ProFeature *f, ProElement root)", "#include")
        self.assertIn("ProFeatureWithoptionsRedefine", body)
        self.assertIn("errors(es);", body)
        self.assertIn(
            'last_feature_error_report = feature_error_report(',
            body,
        )
        self.assertIn('"ProFeatureWithoptionsRedefine"', body)
        self.assertIn('check(e, "CompleteFeature");', body)
        self.assertLess(
            body.index("feature_error_report("), body.index('check(e, "CompleteFeature")')
        )

    def test_report_carries_api_code_stage_and_bounded_sections(self):
        generic = native_source("generic.cpp")
        body = region(generic, "static J feature_error_report(", "static void redefine(")
        for expected in (
            '"api", api',
            '"code", code',
            '"failed_stage", failed_stage',
            '"element_errors"',
            '"section_errors"',
            '"unavailable_reason"',
        ):
            self.assertIn(expected, body)

    def test_geometry_caps_the_element_sample_and_keeps_the_total(self):
        geometry = native_source("geometry.cpp")
        body = region(geometry, "static void errors(const ProErrorlist &es)",
                      "static ProFeature create")
        self.assertIn("FEATURE_ERROR_SAMPLE_LIMIT", body)
        self.assertIn("feature_error_total = es.error_number;", body)
        limit = region(geometry, "static const int FEATURE_ERROR_SAMPLE_LIMIT",
                       "static void reset_section_error_capture")
        self.assertIn("= 20;", limit)
        # The historical log line and unbounded string stay (log dig remains).
        self.assertIn('log("feature_error element=%d type=%d error=%d\\n"', body)
        self.assertIn("last_feature_errors +=", body)

    def test_section_errors_are_captured_bounded_and_reset_per_solve(self):
        solver = native_source("sketch_solver.cpp")
        self.assertIn("capture_section_error(phase, utf8);", solver)
        self.assertIn("reset_section_error_capture();", solver)
        self.assertLess(
            solver.index("reset_section_error_capture();"), solver.index("ProSectionSolve")
        )
        geometry = native_source("geometry.cpp")
        self.assertIn("SECTION_ERROR_SAMPLE_LIMIT = 20", geometry)

    def test_execute_operation_clears_and_attaches_the_receipt(self):
        generic = native_source("generic.cpp")
        body = region(generic, "static void execute_operation(const J &op)",
                      "static void finalize_operation_results")
        self.assertLess(
            body.index("last_feature_error_report = nullptr;"), body.index("try {")
        )
        self.assertIn('failure["feature_errors"] = last_feature_error_report;', body)
        self.assertLess(
            body.index('failure["feature_errors"]'), body.index("append_operation_result")
        )

    def test_job_level_failure_publishes_the_receipt_and_bounded_text(self):
        generic = native_source("generic.cpp")
        body = region(
            generic, 'log("BUILD_SUCCESS=1\\n");', '} catch (const std::exception &error) {'
        )
        self.assertIn("} catch (ProError error) {", body)
        self.assertIn('report["feature_errors"] = last_feature_error_report;', body)
        self.assertIn('" Element errors: "', body)
        self.assertIn("sample capped", body)

    def test_run_generic_resets_the_receipt_per_job(self):
        generic = native_source("generic.cpp")
        body = region(generic, "static int run_generic(const std::wstring &job)", "J report = ")
        self.assertIn("last_feature_error_report = nullptr;", body)

    def test_python_projection_keeps_the_same_bound(self):
        source = (PYTHON_ROOT / "src" / "creo_mechdog" / "operation_results.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("FEATURE_ERROR_SAMPLE_LIMIT = 20", source)
        self.assertIn("SECTION_ERROR_SAMPLE_LIMIT = 20", source)
        self.assertIn("annotate_feature_errors(result)", source)


class Bug097L1NativeWiringTests(unittest.TestCase):
    """L1 locks: the fallback is gated, diagnosed and consistently inverted."""

    def test_identity_detection_covers_the_full_4x4_matrix(self):
        generic = native_source("generic.cpp")
        body = region(generic, "const bool loc_is_identity = [&]() {",
                      "const bool identity_plausible")
        self.assertIn("row == col ? 1.0 : 0.0", body)
        self.assertIn("for (int row = 0; row < 4; row++)", body)
        self.assertIn("for (int col = 0; col < 4; col++)", body)
        self.assertIn("1e-12", body)

    def test_fallback_requires_an_impossible_identity_not_a_bare_one(self):
        generic = native_source("generic.cpp")
        self.assertIn(
            "const bool use_frame_basis = loc_is_identity && !identity_plausible;",
            generic,
        )
        body = region(generic, "const bool identity_plausible", "const bool use_frame_basis")
        # The plausibility guard pins normal to +Z and the origin to the world
        # origin: only there can the identity be the true placement.
        for expected in ("frame.n[0]", "frame.n[1]", "frame.n[2] - 1",
                         "frame.origin[0]", "frame.origin[1]", "frame.origin[2]"):
            self.assertIn(expected, body)

    def test_diagnostic_log_marker_and_structured_block_exist(self):
        generic = native_source("generic.cpp")
        self.assertIn('SECTION_LOCATION_IDENTITY=%d using_%s identity_plausible=%d', generic)
        self.assertIn('"matrix_identity", loc_is_identity', generic)
        self.assertIn('"identity_plausible", identity_plausible', generic)
        self.assertIn('use_frame_basis ? "frame_basis" : "location_matrix"', generic)
        self.assertIn('solver_info["section_location"] = section_location;', generic)
        self.assertIn('{"section_location", section_location},', generic)

    def test_projection_and_inverse_use_the_same_mapping(self):
        generic = native_source("generic.cpp")
        body = region(generic, "auto project = [&](const J &p, double *out) {",
                      "CK(ProSectionIntentManagerModeSet(section, PRO_B_FALSE));")
        self.assertIn("if (use_frame_basis) {", body)
        self.assertIn("out[0] = dot(d, frame.u);", body)
        self.assertIn("out[1] = dot(d, frame.v);", body)
        # The inverse (arc/round-trip report) must use the effective matrix,
        # never the placeholder identity: both call sites report against it.
        self.assertEqual(generic.count("frame.v, effective_loc,"), 2)
        self.assertIn("memcpy(effective_loc, loc, sizeof(effective_loc));", generic)

    def test_bug087_nonparallel_anchor_fix_is_untouched(self):
        generic = native_source("generic.cpp")
        self.assertIn("SKETCH_ANCHOR_SKIPPED=%d parallel_to_orientation=%.9f", generic)
        self.assertIn("if (p.id == frame.orientation || fabs(dot(n, frame.n)) >= 0.95)", generic)


if __name__ == "__main__":
    unittest.main()
