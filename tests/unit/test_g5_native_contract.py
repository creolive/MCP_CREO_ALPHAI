"""Q07 G5 native contract freeze: offline guards for the frozen surface.

FEAT-009 / FEAT-039. The contract in docs/development/G5-NATIVE-CONTRACT.md is
the only interface basis Q08-Q10 may implement against. These regressions lock
the parts of it that must not drift silently: the frozen document markers, the
three independent geometry oracles, the element-symbol resolution rule, and
the rule that one failed native probe blocks only its own dependent task.

No Creo connection, no Toolkit call and no native build happens here.
"""

import unittest

from tools import test_g5_native_probe as probe


class ContractDocumentTests(unittest.TestCase):
    def test_contract_document_keeps_every_frozen_marker(self):
        report = probe.check_contract_document()
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["required_markers"], len(probe.REQUIRED_CONTRACT_MARKERS))
        self.assertGreaterEqual(report["required_markers"], 39)

    def test_contract_records_the_rejected_proposal_symbols(self):
        # The 0.10.0 proposal names that this machine's SDK does not have must
        # stay recorded as rejected, so nobody re-introduces them.
        text = probe.CONTRACT.read_text(encoding="utf-8")
        for symbol in probe.REJECTED_PROPOSAL_SYMBOLS:
            with self.subTest(symbol=symbol):
                self.assertIn(symbol, text)


class OracleTests(unittest.TestCase):
    def test_every_oracle_recomputes_to_its_closed_form(self):
        report = probe.check_oracles()
        self.assertEqual(report["count"], 3)
        by_id = {oracle["id"]: oracle for oracle in report["oracles"]}
        self.assertEqual(set(by_id), {"O1", "O2", "O3"})

        loft = by_id["O1"]
        self.assertAlmostEqual(
            loft["expected_area_mm2"],
            loft["sections_mm"]["length"] * loft["sections_mm"]["separation"],
            places=9,
        )

        project = by_id["O2"]
        self.assertAlmostEqual(
            project["expected_curve_length_mm"], project["source_line_mm"]["length"], places=9
        )
        self.assertAlmostEqual(
            project["expected_endpoint_radius_mm"],
            project["cylinder"]["radius_mm"],
            places=9,
        )
        # The source line must sit off the cylinder, otherwise the oracle
        # could not tell a real projection from an echoed input curve.
        self.assertNotAlmostEqual(
            project["source_line_mm"]["radial_offset_mm"],
            project["cylinder"]["radius_mm"],
            places=6,
        )

        trim = by_id["O3"]
        self.assertAlmostEqual(
            trim["expected_area_before_mm2"],
            trim["rectangle_mm"]["width"] * trim["rectangle_mm"]["height"],
            places=9,
        )
        self.assertAlmostEqual(
            2 * trim["expected_area_after_mm2"],
            trim["expected_area_before_mm2"],
            places=9,
        )

    def test_oracles_are_measurable_without_any_native_result(self):
        # An oracle that only makes sense against a native reading would not be
        # independently parseable; every expected value here is closed form.
        for oracle in probe.ORACLES:
            with self.subTest(oracle=oracle["id"]):
                self.assertIn("expected_", " ".join(oracle.keys()) + " ".join(oracle))


class ProbePlanTests(unittest.TestCase):
    def test_three_probes_exist_and_each_blocks_only_its_own_task(self):
        report = probe.check_probe_plan()
        self.assertEqual([p["id"] for p in report["probes"]], ["P1", "P2", "P3"])
        self.assertEqual(
            [p["blocks_on_failure"] for p in report["probes"]],
            [["Q08 surface_loft"], ["Q09 project_curve"], ["Q10 surface_trim"]],
        )

    def test_each_probe_states_what_to_create_extract_and_compare(self):
        for probe_row in probe.PROBES:
            with self.subTest(probe=probe_row["id"]):
                self.assertTrue(probe_row["goal"])
                self.assertGreaterEqual(len(probe_row["create"]), 2)
                self.assertGreaterEqual(len(probe_row["extract"]), 2)
                self.assertGreaterEqual(len(probe_row["compare"]), 2)
                self.assertEqual(
                    probe_row["verdicts"], ["feasible", "route not established", "unverified"]
                )

    def test_probe_create_steps_never_use_a_hardcoded_element_number(self):
        for probe_row in probe.PROBES:
            for step in probe_row["create"]:
                with self.subTest(probe=probe_row["id"], step=step):
                    self.assertNotRegex(step, r"\bPRO_[A-Z0-9_]+\s*=\s*\d+")
                    self.assertNotRegex(step, r"\b\d{3,}\b")


class SymbolResolutionTests(unittest.TestCase):
    def test_required_symbols_are_named_never_numbered(self):
        for op, symbols in probe.REQUIRED_SDK_SYMBOLS.items():
            with self.subTest(op=op):
                self.assertTrue(symbols)
                for symbol in symbols:
                    self.assertRegex(symbol, r"^PRO_[A-Z0-9_]+$")

    def test_missing_header_sources_are_named_for_every_known_gap(self):
        # The offline report must be able to say which SDK header has to be
        # added to tools/generate_constants.py HEADERS for each gap.
        for symbol, header in probe.MISSING_HEADER_SOURCES.items():
            with self.subTest(symbol=symbol):
                self.assertRegex(header, r"^Pro[A-Za-z]+\.h$")

    def test_measurement_apis_are_the_real_sdk_entry_points(self):
        report = probe.check_measurement_apis()
        names = {row["api"] for row in report["apis"]}
        self.assertIn("ProSurfaceAreaEval", names)
        self.assertIn("ProContourAreaEval", names)
        self.assertIn("ProCurveLengthEval", names)
        self.assertIn("ProCurveXyzdataEval", names)


class ReferenceRuleTests(unittest.TestCase):
    def test_reference_kinds_and_uniqueness_rule_are_frozen(self):
        report = probe.check_reference_rules()
        self.assertEqual(
            report["allowed_reference_kinds"],
            ["curve", "datum_axis_feature", "datum_plane", "edge", "quilt_feature"],
        )
        self.assertIn("exactly one geometry item", report["uniqueness_rule"])
        # A body boolean must never stand in for a quilt.
        self.assertTrue(report["body_boolean_not_allowed"])


if __name__ == "__main__":
    unittest.main()
