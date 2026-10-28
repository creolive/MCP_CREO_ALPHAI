"""DEV-049 T04: offline coverage for the six tilted-cut inputs and the oracle."""

import copy
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from creo_mechdog.schema import validate_operations
from tools import test_dev049_tilted_cut as driver


def good_frame(normal=None):
    normal = driver.tilted_normal() if normal is None else normal
    return {
        "origin": [0.0, 0.0, 0.0],
        "normal": list(normal),
        "u_axis": driver.u_axis_normalized(),
        "v_axis": driver.cross(driver.unit(normal), driver.u_axis_normalized()),
    }


class GeometryBasisTests(unittest.TestCase):
    def test_effective_height_inside_the_disc_is_three(self):
        self.assertAlmostEqual(driver.effective_height(), 3.0, places=12)

    def test_v_axis_is_n_cross_u_and_equals_minus_z(self):
        v = driver.v_axis()
        self.assertAlmostEqual(v[0], 0.0, places=6)
        self.assertAlmostEqual(v[1], 0.0, places=6)
        self.assertAlmostEqual(v[2], -1.0, places=6)

    def test_raw_u_axis_input_is_the_report_value(self):
        self.assertEqual(driver.U_AXIS_INPUT, [0.809017, -0.587785, 0.0])


class OracleTests(unittest.TestCase):
    def test_analytic_matches_the_dispatch_value(self):
        self.assertAlmostEqual(driver.expected_volume("positive"), 238.390260127791, places=9)
        self.assertAlmostEqual(driver.expected_volume("negative"), 238.390260127791, places=9)
        self.assertAlmostEqual(driver.expected_volume("symmetric"), 476.780520255582, places=9)

    def test_analytic_and_numeric_integration_agree(self):
        cross = driver.oracle_cross_check()
        self.assertTrue(cross["agrees"])
        self.assertLessEqual(cross["abs_difference_mm3"], driver.ORACLE_CROSS_TOLERANCE)

    def test_numeric_integration_is_independent_of_the_closed_form(self):
        analytic = driver.analytic_integral()
        numeric = driver.numeric_integral(4000)
        self.assertGreater(abs(analytic - numeric), 0.0)
        self.assertLess(abs(analytic - numeric), driver.ORACLE_CROSS_TOLERANCE)

    def test_expected_volume_rejects_an_unknown_direction(self):
        with self.assertRaises(ValueError):
            driver.expected_volume("sideways")

    def test_oracle_rejects_the_old_120_and_0_anomaly_pair(self):
        for direction in driver.DIRECTIONS:
            for measured in (120.0, 0.0):
                with self.subTest(direction=direction, measured=measured):
                    self.assertFalse(driver.judge_volume(direction, measured)["passed"])

    def test_oracle_rejects_478_as_a_single_direction_expectation(self):
        for direction in ("positive", "negative"):
            with self.subTest(direction=direction):
                self.assertFalse(driver.judge_volume(direction, 478.0)["passed"])
                with self.assertRaises(ValueError):
                    driver.validate_expectation(direction, 478.0)

    def test_oracle_accepts_the_independent_values(self):
        for direction in driver.DIRECTIONS:
            with self.subTest(direction=direction):
                expected = driver.expected_volume(direction)
                self.assertTrue(driver.judge_volume(direction, expected)["passed"])
                driver.validate_expectation(direction, expected)
                self.assertTrue(driver.judge_volume(direction, expected + 0.005)["passed"])

    def test_oracle_rejects_a_bidirectional_value_in_a_single_slot(self):
        symmetric = driver.expected_volume("symmetric")
        self.assertFalse(driver.judge_volume("positive", symmetric)["passed"])
        with self.assertRaises(ValueError):
            driver.validate_expectation("positive", symmetric)

    def test_judge_volume_requires_a_finite_measurement(self):
        for bad in (float("nan"), float("inf"), "120"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    driver.judge_volume("positive", bad)


class FrameTests(unittest.TestCase):
    def test_frame_with_v_equal_to_n_cross_u_is_accepted(self):
        driver.check_frame(good_frame())

    def test_wrong_v_wrong_u_and_non_orthonormal_frames_are_rejected(self):
        base = good_frame()
        for mutate in (
            lambda f: f.update(v_axis=[0.0, 0.0, 1.0]),
            lambda f: f.update(u_axis=[0.0, 1.0, 0.0]),
            lambda f: f.update(normal=[1.0, 0.0, 0.0]),
            lambda f: f.update(origin=[1.0, 0.0, 0.0]),
            lambda f: f.update(u_axis=[0.0, 0.0, 2.0]),
        ):
            bad = copy.deepcopy(base)
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError):
                driver.check_frame(bad)

    def test_tilted_plane_selection_comes_from_inspection(self):
        planes = [
            {"id": 1, "normal": [1.0, 0.0, 0.0], "origin": [0.0, 0.0, 0.0]},
            {
                "id": 2,
                "normal": driver.tilted_normal(),
                "origin": [0.0, 0.0, 0.0],
            },
        ]
        self.assertEqual(driver.select_tilted_plane(planes)["id"], 2)
        with self.assertRaisesRegex(ValueError, "found 0"):
            driver.select_tilted_plane([planes[0]])
        with self.assertRaisesRegex(ValueError, "found 2"):
            driver.select_tilted_plane([planes[1], dict(planes[1])])


# BUG-087: the section matrix Creo reported in the 2026-10-28 live trace
# (job c6d14112c6974d8b8dd55ccc6a399b52). The orientation reference is +Z up, so
# the section X/Y are -u/-v of the requested frame; the placement is unchanged.
SECTION_MATRIX = (
    (-0.809016994, 0.587785252, 0.0),
    (0.0, 0.0, 1.0),
    (0.587785252, 0.809016994, 0.0),
)


def section_xy(world):
    """Project a world point into the Creo section frame (rows are X, Y, Z)."""
    return [sum(world[i] * row[i] for i in range(3)) for row in SECTION_MATRIX[:2]]


def world_point(u, v):
    return [u * du + v * dv for du, dv in zip(driver.u_axis_normalized(), driver.v_axis())]


class SectionFrameTests(unittest.TestCase):
    """BUG-087: a mirrored section frame is a representation, not a placement error."""

    def test_creo_section_frame_is_the_negated_sketch_frame(self):
        row_x, row_y, row_z = SECTION_MATRIX
        expect = [
            [-value for value in driver.u_axis_normalized()],
            [-value for value in driver.v_axis()],
            list(driver.tilted_normal()),
        ]
        for got, want in zip((row_x, row_y, row_z), expect):
            for actual, expected in zip(got, want):
                self.assertAlmostEqual(actual, expected, places=6)

    def test_section_coordinates_keep_the_requested_world_placement(self):
        for u in driver.RECT_U:
            for v in driver.RECT_V:
                x, y = section_xy(world_point(u, v))
                self.assertAlmostEqual(x, -u, places=6)
                self.assertAlmostEqual(y, -v, places=6)

    def test_a_plane_parallel_to_the_orientation_reference_shares_its_line(self):
        support = driver.tilted_normal()
        orientation = [0.0, 0.0, 1.0]  # datum plane 6, the orientation reference
        duplicate = [0.0, 0.0, 1.0]  # datum plane 42, also Z = 0
        perpendicular = [0.0, 1.0, 0.0]  # datum plane 4
        line = driver.cross(support, orientation)
        same = driver.unit(driver.cross(support, duplicate))
        other = driver.unit(driver.cross(support, perpendicular))
        self.assertAlmostEqual(driver.dot(driver.unit(line), same), 1.0, places=9)
        self.assertAlmostEqual(driver.dot(other, other), 1.0, places=12)
        self.assertLess(abs(driver.dot(driver.unit(line), other)), 1e-9)


class InputPlanTests(unittest.TestCase):
    def test_six_cases_cover_both_strategies_and_all_three_directions(self):
        cases = driver.build_cases("abc123")
        self.assertEqual(len(cases), 6)
        pairs = {(c["dimensioning"], c["direction"]) for c in cases}
        self.assertEqual(
            pairs,
            {
                (s, d)
                for s in ("autodim", "coordinates")
                for d in ("positive", "negative", "symmetric")
            },
        )

    def test_model_names_are_unique_and_legal(self):
        names = [c["model_name"] for c in driver.build_cases("abc123")]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(names), 6)
        for name in names:
            self.assertLessEqual(len(name), 31)
            self.assertRegex(name, r"^[a-z0-9][a-z0-9_]*$")

    def test_model_names_carry_the_unique_run_suffix(self):
        first = {c["model_name"] for c in driver.build_cases("aaa111")}
        second = {c["model_name"] for c in driver.build_cases("bbb222")}
        self.assertFalse(first & second)

    def test_every_case_plan_survives_schema_validation(self):
        for case in driver.build_cases("abc123"):
            with self.subTest(case=case["case"]):
                sketch, extrude = validate_operations(
                    driver.slot_operations(case, driver.TILTED_FIXTURE["id"])
                )
                plane = sketch["plane"]
                self.assertEqual(plane["reference"], {"kind": "datum_plane", "id": 911})
                self.assertEqual(plane["origin"], [0.0, 0.0, 0.0])
                self.assertEqual(plane["u_axis"], [0.809017, -0.587785, 0.0])
                self.assertEqual(sketch["dimensioning"], case["dimensioning"])
                entity = sketch["entities"][0]
                self.assertEqual(entity["type"], "rectangle")
                self.assertEqual(entity["min"], [-4.0, -3.0])
                self.assertEqual(entity["max"], [0.0, 3.0])
                self.assertEqual(extrude["op"], "extrude")
                self.assertEqual(extrude["label"], "slot_cut")
                self.assertEqual(extrude["mode"], "cut")
                self.assertEqual(extrude["direction"], case["direction"])
                self.assertEqual(extrude["depth_type"], "through_all")

    def test_setup_plan_builds_the_disc_axis_and_54_degree_plane(self):
        sketch, extrude, axis, plane = validate_operations(driver.setup_operations())
        self.assertEqual(sketch["plane"], "XY")
        self.assertEqual(sketch["entities"][0]["radius"], 20.0)
        self.assertEqual(extrude["depth"], 5.0)
        self.assertEqual(extrude["mode"], "add")
        self.assertEqual(axis["label"], "rotation_axis")
        self.assertEqual(plane["label"], "tilted")
        self.assertEqual(plane["angle"], 54.0)
        self.assertEqual(plane["axis"], {"kind": "datum_axis_feature", "label": "rotation_axis"})

    def test_expected_volume_is_recorded_per_case(self):
        for case in driver.build_cases("abc123"):
            self.assertAlmostEqual(
                case["expected_volume_mm3"],
                driver.expected_volume(case["direction"]),
                places=12,
            )

    def test_validate_case_inputs_rejects_duplicate_model_names(self):
        cases = driver.build_cases("abc123")
        cases[1]["model_name"] = cases[0]["model_name"]
        with self.assertRaisesRegex(ValueError, "unique"):
            driver.validate_case_inputs(cases)

    def test_validate_case_inputs_rejects_an_illegal_model_name(self):
        for bad in ("", "x" * 32, "Bad_Name", "_leading"):
            cases = driver.build_cases("abc123")
            cases[0]["model_name"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                driver.validate_case_inputs(cases)


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
        self.assertIn("offline_cases=6 validated", text)
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
            return driver.TiltedCutAcceptance(None, Path(directory.name) / "report.json", "testrun")

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

    async def test_wait_job_never_calls_the_submit_tool(self):
        runner = self.runner()
        runner.call = AsyncMock(side_effect=[{"status": "running"}, {"status": "succeeded"}])
        with patch.object(driver.asyncio, "sleep", new=AsyncMock()):
            terminal = await runner.wait_job("j1", "succeeded", budget=360)
        self.assertEqual(terminal["status"], "succeeded")
        self.assertEqual(runner.call.await_count, 2)
        for call in runner.call.await_args_list:
            self.assertEqual(call.args[0], "creo_get_job")

    async def test_failed_slot_job_is_recorded_and_does_not_abort_the_run(self):
        import json

        runner = self.runner()
        staged = {
            "revision": 2,
            "inspection": {
                "datum_planes": [
                    {"id": 911, "normal": driver.tilted_normal(), "origin": [0.0, 0.0, 0.0]}
                ]
            },
        }
        runner.fresh_part = AsyncMock(return_value=("m1", {"revision": 1}))
        runner.snapshot = AsyncMock(return_value=staged)
        runner.submit_once = AsyncMock(side_effect=[{"job_id": "setup_j"}, {"job_id": "slot_j"}])
        runner.wait_job = AsyncMock(
            side_effect=[
                {"status": "succeeded"},
                {
                    "status": "failed",
                    "message": "Toolkit call AutodimensionSketch failed with code -1",
                    "result": {
                        "failed_stage": "execute_sketch",
                        "failed_toolkit_call": "AutodimensionSketch",
                        "toolkit_code": -1,
                        "rollback_succeeded": True,
                        "saved_file_reloaded_and_verified": False,
                    },
                },
            ]
        )
        case = driver.build_cases("tag1")[0]
        await runner.run_case(case)  # a terminal failed job must not raise

        self.assertEqual(len(runner.report["cases"]), 1)
        entry = runner.report["cases"][0]
        self.assertFalse(entry["passed"])
        self.assertEqual(entry["status"], "failed")
        self.assertEqual(entry["job_id"], "slot_j")
        self.assertEqual(entry["failed_toolkit_call"], "AutodimensionSketch")
        self.assertTrue(entry["rollback_succeeded"])
        saved = json.loads(Path(runner.output).read_text(encoding="utf-8"))
        self.assertEqual(saved["cases"][0]["job_id"], "slot_j")


class CaseSelectionTests(unittest.TestCase):
    def test_unknown_case_name_is_refused_before_any_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            buffer = io.StringIO()
            with (
                redirect_stdout(buffer),
                patch.object(
                    driver.asyncio,
                    "run",
                    side_effect=AssertionError("must not start the live stage"),
                ),
            ):
                code = driver.main(
                    [
                        "--live",
                        "--confirm-session-usable",
                        "--case",
                        "bogus_case",
                        "--output",
                        str(target),
                    ]
                )
        self.assertEqual(code, 2)
        self.assertIn("unknown case names", buffer.getvalue())

    def test_known_case_names_are_accepted_and_deduplicated(self):
        known = {case["case"] for case in driver.build_cases("tag2")}
        self.assertEqual(len(known), 6)
        self.assertIn("autodim_positive", known)
        self.assertIn("coordinates_symmetric", known)


class ReportTests(unittest.TestCase):
    def test_offline_report_states_that_live_was_not_run(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            driver.main(["--output", str(target)])
            import json

            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "offline")
            self.assertFalse(report["live_run"])
            self.assertEqual(report["native_acceptance"], "not_run")
            self.assertEqual(len(report["cases"]), 6)
            self.assertAlmostEqual(
                report["oracle"]["analytic_single_mm3"], 238.390260127791, places=9
            )

    def test_resolve_output_rejects_an_existing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            stale = Path(directory) / "report.json"
            stale.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                driver.resolve_output(stale, "run")
            fresh = Path(directory) / "fresh.json"
            self.assertEqual(driver.resolve_output(fresh, "run"), fresh)


class GeometryBasisReportTests(unittest.TestCase):
    def test_basis_embeds_direction_semantics_and_analytic_quantities(self):
        basis = driver.geometry_basis()
        self.assertAlmostEqual(basis["single_direction_expected_mm3"], 238.390260127791, places=9)
        self.assertAlmostEqual(basis["symmetric_expected_mm3"], 476.780520255582, places=9)
        self.assertEqual(basis["u_axis_input"], [0.809017, -0.587785, 0.0])
        self.assertEqual(basis["v_axis_semantics"], "v = n x u = -Z")
        self.assertEqual(basis["historical_anomaly"]["old_single_pair"], [120.0, 0.0])
        self.assertEqual(basis["historical_anomaly"]["report_approximation"], 478.0)


if __name__ == "__main__":
    unittest.main()
