"""DEV-079: offline fixes from the 2026-11-08 0.19.0/0.19.1 Creo 10 feedback.

These tests pin the response-budget and contract items only; the native Creo 10
reproduction (surface_loft compile gate, multi-contour cut area) stays open and
is not simulated here.
"""

from __future__ import annotations

import json
import unittest

import generic_bridge
import server
from creo_mechdog import operation_results
from tools import test_profile_endpoint_diagnostics as driver


def curvature_receipt(points: int = 144) -> dict:
    return {
        "job_id": "job1",
        "faces": [
            {
                "surface_id": 68,
                "sample_count": points,
                "failure_count": 0,
                "points": [{"u": 0.5, "v": 0.5}] * points,
            }
        ],
        "summary": {"sample_count": points, "failure_count": 0},
        "g1_points": [{"angle_deg": 0.1}],
    }


class CurvatureSampleBudgetTests(unittest.TestCase):
    def test_default_readout_omits_rows_and_keeps_the_summary(self):
        receipt = curvature_receipt()
        readout = operation_results.surface_curvature_readout(receipt)
        self.assertFalse(readout["samples_included"])
        self.assertEqual(readout["omitted_sample_count"], 144)
        self.assertEqual(readout["faces"][0]["points_omitted"], 144)
        self.assertNotIn("points", readout["faces"][0])
        self.assertEqual(readout["summary"], receipt["summary"])
        self.assertIn("include_samples=true", readout["samples_note"])
        # The native receipt is projected, never mutated.
        self.assertEqual(len(receipt["faces"][0]["points"]), 144)

    def test_include_samples_returns_every_point(self):
        readout = operation_results.surface_curvature_readout(
            curvature_receipt(), include_samples=True
        )
        self.assertTrue(readout["samples_included"])
        self.assertEqual(readout["omitted_sample_count"], 0)
        self.assertEqual(len(readout["faces"][0]["points"]), 144)
        self.assertNotIn("points_omitted", readout["faces"][0])
        self.assertNotIn("samples_note", readout)


class SurfaceGroupFailureTests(unittest.TestCase):
    def test_payload_keeps_job_identity_and_native_reason(self):
        payload = operation_results.surface_group_failure_payload(
            "job1",
            "model1",
            "failed",
            7,
            "surface_group_measure could not visit the group boundary: contour_edge_visit_failed",
        )
        self.assertEqual(payload["job_id"], "job1")
        self.assertEqual(payload["model_id"], "model1")
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["revision"], 7)
        self.assertTrue(payload["readonly"])
        self.assertEqual(
            payload["group"],
            {"state": None, "state_reason": "contour_edge_visit_failed"},
        )
        self.assertIn("creo_inspect_model", payload["hint"])

    def test_other_failures_use_the_generic_reason(self):
        payload = operation_results.surface_group_failure_payload(
            "job2", "model2", "failed", 9, "quilt boundary unavailable"
        )
        self.assertEqual(payload["group"]["state_reason"], "measurement_failed")

    def test_exception_text_is_the_structured_payload(self):
        payload = operation_results.surface_group_failure_payload(
            "job1", "model1", "failed", 7, "contour_edge_visit_failed"
        )
        error = generic_bridge.SurfaceGroupMeasurementFailed(payload)
        self.assertEqual(str(error), json.dumps(payload, ensure_ascii=False))
        self.assertIs(error.payload, payload)


class PublishedContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_curvature_tool_defaults_to_summary_only(self):
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        properties = tools["creo_measure_surface_curvature"].input_schema["properties"]
        self.assertIs(properties["include_samples"]["default"], False)

    def test_quilt_merge_docstring_matches_the_join_route(self):
        text = server.creo_quilt_merge.__doc__ or ""
        self.assertNotIn("submissions are refused", text)
        for field in ("consumed_quilt_ids", "merged_surface_ids", "input_area_mm2"):
            self.assertIn(field, text)

    def test_profile_block_names_the_analytic_input_area(self):
        result = {"operations": [{"op": "sketch", "label": "s1"}]}
        inputs = [{"op": "sketch", "label": "s1", "entities": driver.gapped_square(0.0)}]
        operation_results.annotate_profiles(result, inputs)
        profile = result["operations"][0]["profile"]
        self.assertEqual(profile["source"], "input")
        self.assertEqual(profile["method"], "analytic-input")


if __name__ == "__main__":
    unittest.main()
