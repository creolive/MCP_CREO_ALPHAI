"""DEV-049 T05: offline coverage for the substitute multi-contour replay driver."""

import io
import json
import math
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from creo_mechdog.schema import validate_operations
from tools import test_dev049_profile_replay as driver


def cases():
    return driver.build_cases("abc12345")


class FixtureTests(unittest.TestCase):
    def test_every_contour_is_closed(self):
        for case in cases():
            for contour in case["contours"]:
                with self.subTest(case=case["case"], contour=contour["name"]):
                    self.assertLessEqual(driver.closure_gap(contour), 1e-9)

    def test_contours_never_overlap(self):
        for case in cases():
            contours = case["contours"]
            for index, left in enumerate(contours):
                for right in contours[index + 1 :]:
                    with self.subTest(case=case["case"], left=left["name"], right=right["name"]):
                        self.assertGreater(driver.pairwise_gap(left, right), 0.0)

    def test_the_reported_counts_and_entities_are_explicit(self):
        by_case = {case["case"]: case for case in cases()}
        self.assertEqual(by_case["control_two_circles_r2"]["expected_contour_count"], 2)
        self.assertEqual(by_case["control_two_circles_r2"]["expected_entity_count"], 2)
        self.assertEqual(by_case["five_arc_rings_cut"]["expected_contour_count"], 5)
        self.assertEqual(by_case["five_arc_rings_cut"]["expected_entity_count"], 20)
        self.assertEqual(by_case["ten_arc_rings_cut"]["expected_contour_count"], 10)
        self.assertEqual(by_case["ten_arc_rings_cut"]["expected_entity_count"], 40)

    def test_the_reported_case_is_labelled_as_substitute_verification(self):
        by_case = {case["case"]: case for case in cases()}
        self.assertEqual(by_case["control_two_circles_r2"]["role"], "control_reference")
        self.assertEqual(by_case["control_two_circles_r2"]["expectation_source"], "reported_value")
        for name in ("five_arc_rings_cut", "ten_arc_rings_cut"):
            self.assertEqual(by_case[name]["role"], "uncovered_difference")
            self.assertEqual(by_case[name]["expectation_source"], "substitute")

    def test_model_names_are_unique_and_legal(self):
        names = [case["model_name"] for case in cases()]
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            with self.subTest(name=name):
                self.assertLessEqual(len(name), 31)
                self.assertTrue(name[0].isalnum())
                self.assertEqual(name, name.lower())

    def test_validate_case_inputs_rejects_an_illegal_model_name(self):
        for bad in ("", "x" * 32, "Bad_Name", "_leading"):
            case_list = cases()
            case_list[0]["model_name"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                driver.validate_case_inputs(case_list)

    def test_operations_pass_schema_validation(self):
        validate_operations(driver.plate_operations())
        for case in cases():
            validate_operations(driver.cut_operations(case))

    def test_the_cut_plan_is_through_all_on_the_reported_plate(self):
        case = cases()[1]
        operations = driver.cut_operations(case)
        self.assertEqual(operations[1]["mode"], "cut")
        self.assertEqual(operations[1]["depth_type"], "through_all")
        self.assertEqual(operations[1]["depth"], driver.PLATE_DEPTH_MM)
        self.assertEqual(len(operations[0]["entities"]), case["expected_entity_count"])


class AreaOracleTests(unittest.TestCase):
    def test_analytic_areas_are_pi_r_squared_per_contour(self):
        for case in cases():
            circular = [driver._circular_contour(contour) for contour in case["contours"]]
            expected = sum(math.pi * radius**2 for _, radius in circular)
            with self.subTest(case=case["case"]):
                self.assertAlmostEqual(case["expected_area_mm2"], expected, places=12)

    def test_numeric_area_matches_the_closed_form(self):
        for case in cases():
            numeric = sum(driver.extrapolated_area(contour) for contour in case["contours"])
            with self.subTest(case=case["case"]):
                self.assertLessEqual(
                    abs(numeric - case["expected_area_mm2"]),
                    driver.AREA_TOLERANCE_MM2 * case["expected_contour_count"],
                )

    def test_inscribed_polygon_alone_is_not_precise_enough(self):
        contour = cases()[0]["contours"][0]
        raw = driver.sampled_area(contour)
        self.assertGreater(abs(raw - driver.analytic_area(contour)), driver.AREA_TOLERANCE_MM2)

    def test_volume_is_area_times_plate_depth(self):
        for case in cases():
            with self.subTest(case=case["case"]):
                self.assertAlmostEqual(
                    case["expected_removed_mm3"],
                    case["expected_area_mm2"] * driver.PLATE_DEPTH_MM,
                    places=9,
                )
                driver.validate_expectation(case)

    def test_the_reported_two_circle_control_reproduces_125_663706(self):
        control = driver.reported_control()
        self.assertTrue(control["agrees_at_six_decimals"])
        self.assertLess(control["abs_difference_mm3"], 1e-6)

    def test_a_stale_area_table_is_rejected(self):
        case = dict(cases()[1])
        case["expected_area_mm2"] = case["expected_area_mm2"] * 1.01
        case["expected_removed_mm3"] = case["expected_area_mm2"] * case["depth"]
        with self.assertRaises(AssertionError):
            driver.validate_expectation(case)


class VolumeVerdictTests(unittest.TestCase):
    def test_the_independent_value_passes(self):
        for case in cases():
            with self.subTest(case=case["case"]):
                verdict = driver.judge_volume(case, case["expected_removed_mm3"])
                self.assertTrue(verdict["passed"])
                self.assertLessEqual(verdict["abs_error_mm3"], driver.VOLUME_TOLERANCE_MM3)

    def test_zero_double_and_wrong_depth_are_rejected(self):
        for case in cases():
            expected = case["expected_removed_mm3"]
            for bad in (0.0, expected * 2.0, case["expected_area_mm2"] * 8.0):
                with self.subTest(case=case["case"], bad=bad):
                    self.assertFalse(driver.judge_volume(case, bad)["passed"])

    def test_non_numeric_measurements_are_refused(self):
        for bad in ("120", None, float("nan"), float("inf")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                driver.judge_volume(cases()[0], bad)


class OriginalInputTests(unittest.TestCase):
    def test_missing_attachments_are_recorded_as_missing(self):
        inputs = driver.original_inputs()
        for name in driver.ORIGINAL_INPUTS:
            self.assertEqual(inputs[name], "missing")
        self.assertEqual(inputs["original_case_replay"], "not_possible_missing_attachments")
        self.assertEqual(inputs["original_part_model"], "missing")
        self.assertEqual(inputs["original_preview_images"], "missing")

    def test_no_contour_limit_is_claimed(self):
        table = driver.coverage_table()
        joined = json.dumps(table, ensure_ascii=False).lower()
        self.assertNotIn("supported 2", joined)
        self.assertNotIn("supported=2", joined)
        basis = driver.geometry_basis()
        self.assertIn("direction_note", basis)


class OfflineEntryTests(unittest.TestCase):
    def run_main(self, argv):
        output = io.StringIO()
        with redirect_stdout(output):
            code = driver.main(argv)
        return code, output.getvalue()

    def test_default_run_is_offline_and_never_builds_a_client(self):
        client = Mock(side_effect=AssertionError("MCP client must not be created"))
        with patch.dict("sys.modules", {"mcp": Mock(Client=client)}):
            with patch.object(driver, "live", new=AsyncMock()) as live:
                code, text = self.run_main([])
        self.assertEqual(code, 0)
        self.assertIn("OFFLINE ONLY", text)
        self.assertIn("offline_cases=3 validated", text)
        self.assertIn("original_case_replay=not_possible", text)
        self.assertIn("replacement_verification=true", text)
        self.assertIn("LIVE NOT RUN", text)
        live.assert_not_awaited()
        client.assert_not_called()

    def test_a_single_live_flag_cannot_connect(self):
        for argv in (["--live"], ["--confirm-session-usable"]):
            with self.subTest(argv=argv):
                client = Mock(side_effect=AssertionError("MCP client must not be created"))
                with patch.dict("sys.modules", {"mcp": Mock(Client=client)}):
                    with patch.object(driver, "live", new=AsyncMock()) as live:
                        code, text = self.run_main(argv)
                self.assertEqual(code, 0)
                self.assertIn("OFFLINE ONLY", text)
                self.assertIn("both --live and --confirm-session-usable are required", text)
                live.assert_not_awaited()
                client.assert_not_called()

    def test_both_flags_reach_the_live_entry_point_only(self):
        with patch.object(driver, "live", new=AsyncMock()) as live:
            code, text = self.run_main(["--live", "--confirm-session-usable"])
        self.assertEqual(code, 0)
        self.assertEqual(text, "")
        live.assert_awaited_once()

    def test_an_existing_report_is_refused_before_any_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            stale = Path(directory) / "report.json"
            stale.write_text("{}", encoding="utf-8")
            client = Mock(side_effect=AssertionError("MCP client must not be created"))
            for argv in ([], ["--live", "--confirm-session-usable"]):
                with self.subTest(argv=argv):
                    with patch.dict("sys.modules", {"mcp": Mock(Client=client)}):
                        with patch.object(driver, "live", new=AsyncMock()) as live:
                            code, text = self.run_main([*argv, "--output", str(stale)])
                    self.assertEqual(code, 2)
                    self.assertIn("REFUSED BEFORE CONNECTION", text)
                    self.assertIn("Refusing to overwrite", text)
                    live.assert_not_awaited()
                    client.assert_not_called()

    def test_offline_run_writes_a_fresh_report_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            code, text = self.run_main(["--output", str(target)])
            self.assertEqual(code, 0)
            self.assertTrue(target.exists())
            self.assertIn(f"report={target}", text)
            code, text = self.run_main(["--output", str(target)])
            self.assertEqual(code, 2)
            self.assertIn("REFUSED BEFORE CONNECTION", text)


class NoResubmissionTests(unittest.IsolatedAsyncioTestCase):
    def runner(self):
        with patch.object(driver, "local_provenance", return_value={}):
            directory = tempfile.TemporaryDirectory()
            self.addCleanup(directory.cleanup)
            return driver.ProfileReplayAcceptance(
                None, Path(directory.name) / "report.json", "testrun"
            )

    async def test_submit_once_refuses_a_repeat_submission(self):
        runner = self.runner()
        runner.call = AsyncMock(return_value={"job_id": "j1"})
        await runner.submit_once("case", {"operations": []})
        with self.assertRaisesRegex(RuntimeError, "never resubmit"):
            await runner.submit_once("case", {"operations": []})
        runner.call.assert_awaited_once()

    async def test_budget_exhaustion_raises_and_does_not_resubmit(self):
        runner = self.runner()
        runner.call = AsyncMock(return_value={"status": "running"})
        with patch.object(driver.asyncio, "sleep", new=AsyncMock()):
            with self.assertRaisesRegex(TimeoutError, "do not resubmit"):
                await runner.wait_job("j1", budget=0)
        self.assertEqual(runner.submitted, set())
        for call in runner.call.await_args_list:
            self.assertEqual(call.args[0], "creo_get_job")

    async def test_unknown_terminal_status_is_recorded_and_not_resubmitted(self):
        runner = self.runner()
        runner.call = AsyncMock(return_value={"status": "corrupted"})
        with self.assertRaisesRegex(RuntimeError, "do not resubmit"):
            await runner.wait_job("j1")
        self.assertEqual(runner.submitted, set())
        runner.call.assert_awaited_once_with("creo_get_job", {"job_id": "j1"})


class ReportTests(unittest.TestCase):
    def test_offline_report_states_that_live_was_not_run(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            driver.main(["--output", str(target)])
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "offline")
            self.assertFalse(report["live_run"])
            self.assertEqual(report["native_acceptance"], "not_run")
            self.assertTrue(report["replacement_verification"])
            self.assertEqual(report["contour_limit_claim"], "not_asserted")
            self.assertEqual(len(report["cases"]), 3)
            self.assertEqual(
                report["original_inputs"]["original_case_replay"],
                "not_possible_missing_attachments",
            )
            self.assertTrue(report["oracle"]["reported_control"]["agrees_at_six_decimals"])

    def test_resolve_output_rejects_an_existing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            stale = Path(directory) / "report.json"
            stale.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                driver.resolve_output(stale, "run")
            fresh = Path(directory) / "fresh.json"
            self.assertEqual(driver.resolve_output(fresh, "run"), fresh)


if __name__ == "__main__":
    unittest.main()
