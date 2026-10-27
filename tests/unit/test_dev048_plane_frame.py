"""DEV-048 T04: offline coverage for the Right-plane +/-Z driver and refusals."""

import copy
import inspect
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from creo_mechdog.schema import validate_operations
from tools import test_dev048_plane_frame as driver

PLANE = {"id": 163, "normal": [1.0, 0.0, 0.0], "origin": [0.0, 0.0, 0.0]}


def frame(normal, u_axis):
    return {
        "origin": [0.0, 0.0, 0.0],
        "normal": normal,
        "u_axis": u_axis,
        "v_axis": driver.cross(normal, u_axis),
    }


def snapshot(volume=800.0, bbox=None, center=None, revision=3):
    return {
        "revision": revision,
        "aliases": {"profile": {"feature_id": 7}},
        "inspection": {
            "length_unit": {"name": "mm", "scale_to_mm": 1.0},
            "volume_query_code": 0,
            "volume_mm3": volume,
            "center_of_gravity": center or [2.0, -10.0, 5.0],
            "bodies": [{"has_geometry": True, "bbox": bbox or [[0, -20, 0], [4, 0, 10]]}],
        },
    }


class InputPlanTests(unittest.TestCase):
    def test_both_pure_z_directions_survive_validation_with_the_exact_section(self):
        for u_axis in (driver.U_POSITIVE, driver.U_NEGATIVE):
            with self.subTest(u_axis=u_axis):
                sketch, extrude = validate_operations(
                    driver.plan_for(PLANE["id"], PLANE["origin"], u_axis)
                )
                self.assertEqual(sketch["plane"]["reference"], {"kind": "datum_plane", "id": 163})
                self.assertEqual(sketch["plane"]["u_axis"], u_axis)
                self.assertEqual(sketch["plane"]["origin"], [0.0, 0.0, 0.0])
                self.assertEqual(sketch["dimensioning"], "coordinates")
                entity = sketch["entities"][0]
                self.assertEqual(entity["type"], "rectangle")
                self.assertEqual(entity["min"], [0, 0])
                self.assertEqual(entity["max"], [10, 20])
                self.assertEqual(extrude["op"], "extrude")
                self.assertEqual(extrude["label"], "solid")
                self.assertEqual(extrude["sketch"], "profile")
                self.assertEqual(extrude["depth"], 4)
                self.assertEqual(extrude["mode"], "add")
                self.assertEqual(extrude["direction"], "positive")
                self.assertEqual(extrude["depth_type"], "blind")

    def test_parallel_u_axis_passes_entry_so_the_native_boundary_must_reject_it(self):
        operations = validate_operations(
            driver.plan_for(PLANE["id"], PLANE["origin"], driver.U_PARALLEL)
        )
        self.assertEqual(operations[0]["plane"]["u_axis"], [1, 0, 0])
        source = (driver.ROOT / "native" / "generic.cpp").read_text(encoding="utf-8")
        message = "parallel to the support plane normal"
        self.assertIn(message, source)
        self.assertIn(message, inspect.getsource(driver.PlaneFrameAcceptance.parallel_case))

    def test_geometry_id_comes_from_the_inspection_not_a_constant(self):
        planes = [
            {"id": 911, "normal": [-1.0, 0.0, 0.0], "origin": [0.0, 0.0, 0.0]},
            {"id": 912, "normal": [0.0, 0.0, -1.0], "origin": [0.0, 0.0, 0.0]},
        ]
        plane = driver.select_right_plane(planes)
        self.assertEqual(plane["id"], 911)
        plan = driver.plan_for(plane["id"], plane["origin"], driver.U_POSITIVE)
        self.assertEqual(plan[0]["plane"]["reference"], {"kind": "datum_plane", "id": 911})
        live_source = inspect.getsource(driver.PlaneFrameAcceptance.valid_case)
        self.assertIn('plane["id"]', live_source)
        self.assertNotIn("163", live_source)

    def test_right_plane_selection_requires_origin_and_x_normal_only(self):
        self.assertEqual(driver.select_right_plane(driver.RIGHT_FIXTURE)["id"], 163)
        with self.assertRaisesRegex(ValueError, "found 0"):
            driver.select_right_plane([driver.RIGHT_FIXTURE[3]])
        with self.assertRaisesRegex(ValueError, "found 0"):
            driver.select_right_plane([{"id": 1, "normal": [0, 1, 0], "origin": [0, 0, 0]}])
        with self.assertRaisesRegex(ValueError, "found 2"):
            driver.select_right_plane([*driver.RIGHT_FIXTURE, dict(driver.RIGHT_FIXTURE[0])])


class FrameAssertionTests(unittest.TestCase):
    def test_reported_frame_echoes_u_and_keeps_v_equal_to_n_cross_u(self):
        for normal in ([1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]):
            for u_axis in (driver.U_POSITIVE, driver.U_NEGATIVE):
                with self.subTest(normal=normal, u_axis=u_axis):
                    reported = frame(normal, u_axis)
                    driver.check_frame(reported, u_axis)
                    self.assertEqual(reported["v_axis"], driver.cross(normal, u_axis))

    def test_wrong_u_non_x_normal_flipped_v_and_non_unit_are_rejected(self):
        good = frame([1.0, 0.0, 0.0], driver.U_POSITIVE)
        driver.check_frame(good, driver.U_POSITIVE)
        for bad, u_axis in (
            ({**good, "u_axis": [0, 0, -1]}, driver.U_POSITIVE),
            ({**good, "normal": [0, 1, 0]}, driver.U_POSITIVE),
            ({**good, "v_axis": [0, 1, 0]}, driver.U_POSITIVE),
            ({**good, "u_axis": [0, 0, 2]}, driver.U_POSITIVE),
            ({**good, "normal": [0.7071, 0.7071, 0]}, driver.U_POSITIVE),
        ):
            with self.subTest(reported=bad), self.assertRaises(AssertionError):
                driver.check_frame(bad, u_axis)


class MeasurementTests(unittest.TestCase):
    def test_eight_corners_give_800_mm3_and_an_independent_box(self):
        for normal in ([1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]):
            with self.subTest(normal=normal):
                reported = frame(normal, driver.U_POSITIVE)
                measured = driver.box_measurements(reported)
                self.assertEqual(measured["volume_mm3"], 800.0)
                expected_bbox = (
                    [[0, -20, 0], [4, 0, 10]] if normal[0] > 0 else [[-4, 0, 0], [0, 20, 10]]
                )
                expected_center = [2, -10, 5] if normal[0] > 0 else [-2, 10, 5]
                driver.near(measured["bbox"], expected_bbox)
                driver.near(measured["center_of_gravity"], expected_center)
                self.assertEqual(driver.VOLUME, 800)

    def test_native_measurements_must_match_the_independent_box(self):
        expected = driver.box_measurements(frame([-1.0, 0.0, 0.0], driver.U_NEGATIVE))
        with self.assertRaises(AssertionError):
            driver.check_measurements(snapshot(), expected)
        accepted = snapshot(
            bbox=expected["bbox"], center=expected["center_of_gravity"], volume=800.0
        )
        state = accepted["inspection"]
        body = state["bodies"][0]
        body["bbox"] = expected["bbox"]
        driver.check_measurements(accepted, expected)

    def test_wrong_volume_bbox_or_center_is_rejected(self):
        expected = driver.box_measurements(frame([1.0, 0.0, 0.0], driver.U_POSITIVE))
        good = snapshot(
            volume=800.0,
            bbox=expected["bbox"],
            center=expected["center_of_gravity"],
        )
        state = good["inspection"]
        state["bodies"][0]["bbox"] = expected["bbox"]
        driver.check_measurements(good, expected)
        for mutate in (
            lambda value: value["inspection"].update(volume_mm3=799.0),
            lambda value: value["inspection"].update(center_of_gravity=[0.0, 0.0, 0.0]),
            lambda value: value["inspection"]["bodies"][0].update(bbox=[[0, 0, 0], [4, 20, 10]]),
        ):
            bad = copy.deepcopy(good)
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError):
                driver.check_measurements(bad, expected)

    def test_refusal_state_must_keep_revision_aliases_volume_and_bbox(self):
        before = snapshot()
        driver.check_unchanged(before, copy.deepcopy(before))
        for mutate in (
            lambda value: value.update(revision=4),
            lambda value: value.update(aliases={}),
            lambda value: value["inspection"].update(volume_mm3=1600.0),
            lambda value: value["inspection"]["bodies"][0].update(bbox=[[0, 0, 0], [4, 20, 10]]),
        ):
            bad = copy.deepcopy(before)
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError):
                driver.check_unchanged(before, bad)


class RefusalTests(unittest.IsolatedAsyncioTestCase):
    def runner(self, before):
        with patch.object(driver, "local_provenance", return_value={}):
            directory = tempfile.TemporaryDirectory()
            self.addCleanup(directory.cleanup)
            runner = driver.PlaneFrameAcceptance(None, Path(directory.name) / "report.json")
        runner.last_valid = {
            "model_id": "a" * 32,
            "plane": PLANE,
            "snapshot": before,
        }
        runner.snapshot = AsyncMock(return_value=copy.deepcopy(before))
        return runner

    async def test_entry_refusal_creates_no_job_and_changes_nothing(self):
        before = snapshot()
        runner = self.runner(before)
        runner._invoke = AsyncMock(
            return_value=Mock(
                is_error=True,
                structured_content={},
                content="operations[0].plane.u_axis is parallel to the support plane normal",
            )
        )
        await runner.parallel_case()
        case = runner.report["cases"][-1]
        self.assertEqual(case["rejection"], "entry_refusal")
        self.assertIsNone(case["job_id"])
        self.assertFalse(case["geometry_passed"])
        self.assertTrue(case["refusal_verified"])
        self.assertEqual(case["revision_after"], before["revision"])
        runner.snapshot.assert_awaited_once_with("a" * 32)

    async def test_unrelated_entry_refusal_or_busy_is_not_counted_as_the_expected_refusal(self):
        for content, structured in (
            ("Stale revision: current model revision is 4", {}),
            ("{}", {"status": "busy", "blocking_job_id": "j"}),
        ):
            runner = self.runner(snapshot())
            runner._invoke = AsyncMock(
                return_value=Mock(is_error=True, structured_content=structured, content=content)
            )
            with self.subTest(content=content), self.assertRaises((RuntimeError, AssertionError)):
                await runner.parallel_case()
            self.assertEqual(runner.report["cases"], [])

    async def test_native_refusal_requires_rollback_and_unchanged_state(self):
        before = snapshot()
        runner = self.runner(before)
        runner._invoke = AsyncMock(
            return_value=Mock(is_error=False, structured_content={"job_id": "j1"})
        )
        runner.wait_job = AsyncMock(
            return_value={
                "status": "failed",
                "result": {"rollback_succeeded": True},
                "message": "Sketch u_axis is parallel to the support plane normal",
            }
        )
        await runner.parallel_case()
        case = runner.report["cases"][-1]
        self.assertEqual(case["rejection"], "native_refusal")
        self.assertEqual(case["job_id"], "j1")
        self.assertFalse(case["geometry_passed"])
        self.assertEqual(case["volume_unchanged_mm3"], 800.0)

    async def test_native_refusal_without_rollback_or_other_error_fails(self):
        for terminal, before, after in (
            (
                {
                    "status": "failed",
                    "result": {"rollback_succeeded": False},
                    "message": "Sketch u_axis is parallel to the support plane normal",
                },
                snapshot(),
                snapshot(),
            ),
            (
                {
                    "status": "failed",
                    "result": {"rollback_succeeded": True},
                    "message": "Sketch support must be planar",
                },
                snapshot(),
                snapshot(),
            ),
            (
                {
                    "status": "failed",
                    "result": {"rollback_succeeded": True},
                    "message": "Sketch u_axis is parallel to the support plane normal",
                },
                snapshot(),
                snapshot(revision=4),
            ),
        ):
            runner = self.runner(before)
            runner.snapshot = AsyncMock(return_value=after)
            runner._invoke = AsyncMock(
                return_value=Mock(is_error=False, structured_content={"job_id": "j1"})
            )
            runner.wait_job = AsyncMock(return_value=terminal)
            with self.subTest(message=terminal["message"]), self.assertRaises(AssertionError):
                await runner.parallel_case()

    async def test_parallel_case_reuses_the_last_valid_part(self):
        runner = self.runner(snapshot())
        runner._invoke = AsyncMock(
            return_value=Mock(
                is_error=True,
                structured_content={},
                content="Sketch u_axis is parallel to the support plane normal",
            )
        )
        await runner.parallel_case()
        applied = runner._invoke.await_args.args[1]
        self.assertEqual(applied["model_id"], "a" * 32)
        self.assertEqual(applied["expected_revision"], 3)
        self.assertEqual(applied["operations"][0]["plane"]["reference"]["id"], PLANE["id"])


class OfflineEntryTests(unittest.TestCase):
    def run_main(self, argv):
        output = io.StringIO()
        with redirect_stdout(output):
            code = driver.main(argv)
        return code, output.getvalue()

    def test_default_and_single_flag_runs_are_offline_and_exit_zero(self):
        for argv in ([], ["--live"], ["--confirm-session-usable"]):
            with patch.object(driver, "live", new=AsyncMock()) as live:
                with self.subTest(argv=argv):
                    code, text = self.run_main(argv)
                    self.assertEqual(code, 0)
                    self.assertIn("OFFLINE ONLY", text)
                    self.assertIn("offline_checks=8/8 passed", text)
                    self.assertIn("LIVE NOT RUN", text)
                    live.assert_not_awaited()

    def test_both_flags_reach_the_live_entry_point_only(self):
        with patch.object(driver, "live", new=AsyncMock()) as live:
            code, text = self.run_main(["--live", "--confirm-session-usable"])
        self.assertEqual(code, 0)
        self.assertEqual(text, "")
        live.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
