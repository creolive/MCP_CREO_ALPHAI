"""T05 public projections, live guard and independent analytical oracle checks."""

import argparse
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import bridge
import server
from creo_mechdog.model_queries import inspect_page, inspection_summary
from creo_mechdog.schema import validate_operations
from tools import test_t05_native as fixture


class AxisProjectionTests(unittest.TestCase):
    def test_native_axis_and_changed_unit_header_participate_in_runtime_identity(self):
        hashes = server._source_fingerprints()
        for name in ("native/axis_geometry.h", "native/assembly_units.h"):
            self.assertIn(name, server._SOURCE_NAMES)
            self.assertEqual(len(hashes[name]), 64)

    def test_compact_job_preserves_native_axis_and_query_failures(self):
        operation = {
            "op": "datum_axis",
            "label": "axis",
            "succeeded": True,
            "axes_query_code": -4,
            "datum_axes": [
                {
                    "id": 17,
                    "origin": None,
                    "direction": None,
                    "geometry_known": False,
                    "data_query_code": -4,
                    "line_query_code": None,
                }
            ],
            "length_unit": {"name": None, "query_code": -2, "scale_to_mm": None},
        }
        result = bridge.compact_job({"result": {"operations": [operation]}})
        self.assertEqual(result["result"]["operations"], [operation])

    def test_axes_paginate_without_leaking_nested_collection_in_features(self):
        axes = [
            {"id": i, "feature_id": i, "origin": [4, -3, 0], "direction": [0, 0, 1]}
            for i in range(5)
        ]
        model = {
            "model_id": "a" * 32,
            "revision": 2,
            "inspection": {
                "datum_axes": axes,
                "features": [{"id": 0, "datum_axes": axes}],
                "length_unit": {"name": "in", "query_code": 0, "scale_to_mm": 25.4},
            },
        }
        before = copy.deepcopy(model)
        collected, cursor = [], None
        while True:
            page = inspect_page(model, detail="full", section="datum_axes", limit=2, cursor=cursor)
            collected.extend(page["data"]["datum_axes"])
            cursor = page.get("next_cursor")
            if not cursor:
                break
        self.assertEqual(collected, axes)
        feature_page = inspect_page(model, detail="full", section="features")
        self.assertNotIn("datum_axes", feature_page["data"]["features"][0])
        self.assertEqual(model, before)

    def test_compact_summary_keeps_native_cg_units_and_unexecuted_query_null(self):
        state = {
            "center_of_gravity": None,
            "volume_query_code": None,
            "length_unit": {
                "name": None,
                "scale_to_mm": None,
                "scale_query_codes": {"conversion": None},
            },
        }
        summary = inspection_summary(state)
        for key, value in state.items():
            self.assertEqual(summary[key], value)


class AcceptanceOracleTests(unittest.TestCase):
    def test_rotations_are_about_eccentric_line_with_signed_direction(self):
        fixture.near(fixture.rotate([16, -3, 0], [4, -3, 5], [0, 0, 1], 90), [4, 9, 0])
        fixture.near(fixture.rotate([16, -3, 0], [4, -3, 5], [0, 0, -1], 90), [4, -15, 0])
        fixture.near(fixture.rotate([16, -3, 0], [4, -3, 5], [0, 0, 1], -90), [4, -15, 0])

    def test_center_matching_rejects_missing_extra_duplicate_and_wrong_positions(self):
        expected = [[1, 0, 0], [-1, 0, 0]]
        fixture.match_centers(list(reversed(expected)), expected)
        for actual in (
            expected[:1],
            expected + [[0, 0, 0]],
            [expected[0]] * 2,
            [[1, 0, 0], [0, -1, 0]],
        ):
            with self.subTest(actual=actual), self.assertRaises(AssertionError):
                fixture.match_centers(actual, expected)

    def test_total_depth_box_has_independent_known_aabb_and_cg(self):
        frame = {
            "origin": [0, 0, 0],
            "u_axis": [0, 0, 1],
            "v_axis": [0.8, -0.6, 0],
            "normal": [0.6, 0.8, 0],
        }
        bounds, cg = fixture.box_oracle(frame, 4, "positive")
        fixture.near(bounds, [[-8, -6, -5], [10.4, 9.2, 5]])
        fixture.near(cg, [1.2, 1.6, 0])
        bounds, cg = fixture.box_oracle(frame, 4, "symmetric")
        fixture.near(bounds, [[-9.2, -7.6, -5], [9.2, 7.6, 5]])
        fixture.near(cg, [0, 0, 0])

    def test_fixture_inputs_pass_public_operation_validation(self):
        operations = fixture.tilt_setup() + [
            fixture.sketch(
                "profile",
                {"reference": {"kind": "datum_feature", "label": "tilted"}, "u_axis": [0, 0, 1]},
                fixture.rectangle(10, 20),
            ),
            fixture.extrude("solid", "profile", 4, "symmetric"),
        ]
        self.assertEqual(len(validate_operations(operations)), 4)

    def test_analytical_rectangle_and_circle_explicitly_select_coordinates(self):
        for plane in (
            "XY",
            {"reference": {"kind": "datum_feature", "label": "tilted"}, "u_axis": [0, 0, 1]},
        ):
            for entity in (fixture.rectangle(10, 20), fixture.circle([16, -3], 1)):
                with self.subTest(plane=plane, entity=entity["type"]):
                    operation = fixture.sketch("profile", plane, entity)
                    self.assertEqual(operation["dimensioning"], "coordinates")
                    validated = validate_operations([operation])[0]
                    self.assertEqual(validated["dimensioning"], "coordinates")
                    self.assertEqual(validated["plane"], plane)
                    self.assertEqual(validated["entities"][0]["type"], entity["type"])

    def test_default_and_import_have_no_client_or_native_calls(self):
        with (
            patch.object(fixture, "live", side_effect=AssertionError("must not connect")),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO),
        ):
            self.assertEqual(fixture.main([]), 0)
            with self.assertRaises(SystemExit) as error:
                fixture.main(["--live"])
            self.assertEqual(error.exception.code, 2)
        self.assertTrue(
            fixture.require_live(argparse.Namespace(live=True, confirm_session_usable=True))
        )

    def test_live_driver_requires_explicitly_disabled_automatic_start(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.json"
            for text in ("{}", '{"auto_start_creo": true}', '{"auto_start_creo": 0}'):
                config_file.write_text(text, encoding="utf-8")
                with self.subTest(settings=text), self.assertRaises(ValueError):
                    fixture.require_manual_start(config_file)
            config_file.write_text('{"auto_start_creo": false}', encoding="utf-8")
            fixture.require_manual_start(config_file)

    def test_provenance_records_source_and_environment_without_configuration(self):
        provenance = fixture.local_provenance()
        self.assertEqual(len(provenance["source_fingerprint"]), 64)
        self.assertIn("native/axis_geometry.h", provenance["source_sha256"])
        self.assertIn("python", provenance["environment"])
        for key in ("config", "license", "session_id", "creo_session_id"):
            self.assertNotIn(key, provenance)


class ReadinessObservationTests(unittest.IsolatedAsyncioTestCase):
    async def test_metric_matrix_success_does_not_claim_all_unit_acceptance_passed(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(fixture, "local_provenance", return_value={}),
        ):
            runner = fixture.Acceptance(None, Path(directory) / "report.json")
            runner.tilted = AsyncMock()
            runner.pattern = AsyncMock()
            await runner.metric_matrix()
            self.assertEqual(runner.tilted.await_count, 9)
            self.assertEqual(runner.pattern.await_count, 9)
            self.assertEqual(runner.report["metric_geometry_matrix"], "passed")
            self.assertEqual(runner.report["native_acceptance"], "partial")
            self.assertEqual(runner.report["native_unit_coverage"]["millimeter"], "passed")
            for name in ("non_millimeter_coordinates", "unknown_units_and_query_failures"):
                self.assertEqual(runner.report["native_unit_coverage"][name], "pending")
                self.assertIn(name, runner.report["pending_native_acceptance"])

    async def test_transport_exception_keeps_attempt_and_unknown_outcome_without_retry(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(fixture, "local_provenance", return_value={}),
        ):
            output = Path(directory) / "report.json"
            client = unittest.mock.Mock()
            args = {"operations": [{"op": "datum_axis", "label": "axis"}]}

            async def transport_error(name, inputs):
                attempted = json.loads(output.read_text(encoding="utf-8"))["calls"][0]
                self.assertEqual(attempted["tool"], name)
                self.assertEqual(attempted["args"], inputs)
                self.assertFalse(attempted["response_received"])
                self.assertEqual(attempted["outcome"], "unknown")
                raise TimeoutError("no response received")

            client.call_tool = AsyncMock(side_effect=transport_error)
            runner = fixture.Acceptance(client, output)
            with self.assertRaises(TimeoutError):
                await runner.call("creo_execute_plan", args)
            client.call_tool.assert_awaited_once_with("creo_execute_plan", args)
            record = json.loads(output.read_text(encoding="utf-8"))["calls"][0]
            self.assertFalse(record["response_received"])
            self.assertEqual(record["outcome"], "unknown")
            self.assertEqual(record["client_exception"]["type"], "TimeoutError")
            self.assertNotIn("result", record)
            self.assertNotIn("is_error", record)
            self.assertEqual(len(runner.report["calls"]), 1)

    async def test_startup_observation_waits_without_submitting_or_restarting(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(fixture, "local_provenance", return_value={}),
        ):
            runner = fixture.Acceptance(None, Path(directory) / "report.json")
            runner.call = AsyncMock(
                side_effect=[{"state": "checking"}, {"state": "ready", "connected": True}]
            )
            with patch.object(fixture.asyncio, "sleep", new_callable=AsyncMock):
                await runner.wait_ready()
            self.assertEqual(
                runner.call.await_args_list,
                [
                    unittest.mock.call("creo_startup_status", {}),
                    unittest.mock.call("creo_startup_status", {}),
                ],
            )

    async def test_busy_unknown_and_timeout_stop_without_resubmission(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(fixture, "local_provenance", return_value={}),
        ):
            runner = fixture.Acceptance(None, Path(directory) / "report.json")
            for state in ("busy", "unknown", "waiting_for_channel", "failed"):
                runner.call = AsyncMock(return_value={"state": state})
                with self.subTest(state=state), self.assertRaises(RuntimeError):
                    await runner.wait_ready()
                runner.call.assert_awaited_once_with("creo_startup_status", {})
            runner.call = AsyncMock(return_value={"state": "checking"})
            with self.assertRaises(TimeoutError):
                await runner.wait_ready(budget=0)
            runner.call.assert_awaited_once_with("creo_startup_status", {})


if __name__ == "__main__":
    unittest.main()
