"""FEAT-039/H04: group-level boundary measurement (open edges, gaps, overlap).

The native executor measures the real boundary (contour edges, edge distance,
face tessellation containment); these tests pin the Python half without Creo:
the schema admission, the published registration/tool, the compact projection
and the §4.4.1 rule that a value never outlives its own status.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import server
from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS
from creo_mechdog.job_projection import compact_operation
from creo_mechdog.operation_results import (
    SURFACE_GROUP_STATES,
    annotate_surface_group,
    normalize_surface_group,
)
from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native" / "surface_group.cpp"


def group_block(**overrides):
    block = {
        "quilt_ids": [21, 22],
        "quilt_count": 2,
        "face_count": 2,
        "faces": [{"surface_id": 31, "quilt_index": 0}, {"surface_id": 41, "quilt_index": 1}],
        "boundary_edges": 8,
        "joined_edges": 2,
        "open_edges": 6,
        "open_edges_status": {
            "available": True,
            "reason": None,
            "query_code": 0,
            "unit_name": "mm",
            "scale_to_mm_known": True,
            "boundary_edges": 8,
            "joined_edges": 2,
            "topologically_shared_edges": 0,
        },
        "gap_max_mm": 0.0,
        "gap_max_status": {
            "available": True,
            "reason": None,
            "query_code": 0,
            "unit_name": "mm",
            "scale_to_mm_known": True,
            "tolerance_mm": 0.01,
            "gap_search_mm": 1.0,
            "candidate_pairs": 1,
            "joined_pairs": 1,
            "gap_pairs": 0,
            "within_tolerance": True,
        },
        "overlap_area_mm2": 0.0,
        "overlap_status": {
            "available": True,
            "reason": None,
            "query_code": 0,
            "unit_name": "mm",
            "scale_to_mm_known": True,
            "method": "face_tessellation_sample_containment",
            "tolerance_mm": 0.01,
            "face_pairs_tested": 1,
            "sample_tests": 30,
            "overlapping_face_pairs": 0,
            "detected": False,
            "area_is_estimate": True,
        },
        "overlap_pairs": [],
        "state": "closed",
        "state_reason": None,
        "boundary_closed": False,
        "tolerance_mm": 0.01,
        "gap_search_mm": 1.0,
    }
    block.update(overrides)
    return block


class SurfaceGroupMeasureSchemaTests(unittest.TestCase):
    def test_defaults_are_the_documented_tolerance_and_search_window(self):
        validated = validate_operations(
            [
                {
                    "op": "surface_group_measure",
                    "references": [{"kind": "quilt", "id": 21}, {"kind": "quilt", "id": 22}],
                }
            ]
        )[0]
        self.assertEqual(validated["op"], "surface_group_measure")
        self.assertEqual(validated["tolerance_mm"], 0.01)
        self.assertEqual(validated["gap_search_mm"], 1.0)
        self.assertEqual(len(validated["references"]), 2)

    def test_explicit_values_survive_validation(self):
        validated = validate_operations(
            [
                {
                    "op": "surface_group_measure",
                    "references": [{"kind": "quilt_feature", "label": "patch_a"}],
                    "tolerance_mm": 0.005,
                    "gap_search_mm": 0.5,
                }
            ]
        )[0]
        self.assertEqual(validated["tolerance_mm"], 0.005)
        self.assertEqual(validated["gap_search_mm"], 0.5)

    def test_refuses_unusable_references_and_windows(self):
        refused = {
            "duplicate_reference": [
                {"kind": "quilt", "id": 21},
                {"kind": "quilt", "id": 21},
            ],
            "datum_plane": [{"kind": "datum_plane", "label": "TOP"}],
            "curve": [{"kind": "curve", "id": 7}],
            "missing_kind": [{"id": 21}],
            "negative_id": [{"kind": "quilt", "id": -1}],
            "no_id": [{"kind": "quilt"}],
            "too_many": [{"kind": "quilt", "id": index} for index in range(9)],
            "no_references": [],
        }
        for name, references in refused.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    validate_operations([{"op": "surface_group_measure", "references": references}])
        for name, overrides in {
            "zero_tolerance": {"tolerance_mm": 0.0},
            "search_below_tolerance": {"tolerance_mm": 0.02, "gap_search_mm": 0.01},
            "negative_tolerance": {"tolerance_mm": -1.0},
        }.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    validate_operations(
                        [
                            {
                                "op": "surface_group_measure",
                                "references": [{"kind": "quilt", "id": 21}],
                                **overrides,
                            }
                        ]
                    )

    def test_registered_and_published(self):
        self.assertIn("surface_group_measure", REGISTERED_OPERATIONS)
        self.assertNotIn("surface_group_measure", UNAVAILABLE_OPERATIONS)


class SurfaceGroupMeasureToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_tool_is_published_with_the_same_defaults(self):
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        tool = tools["creo_measure_surface_group"]
        self.assertTrue(tool.annotations.read_only_hint)
        self.assertFalse(tool.annotations.destructive_hint)
        properties = tool.input_schema["properties"]
        self.assertEqual(properties["tolerance_mm"]["default"], 0.01)
        self.assertEqual(properties["gap_search_mm"]["default"], 1.0)
        references = properties["references"]
        self.assertEqual(references["minItems"], 1)
        self.assertEqual(references["maxItems"], 8)

    def test_readonly_admission_accepts_the_measurement_operation(self):
        source = (ROOT / "generic_bridge.py").read_text(encoding="utf-8")
        self.assertIn('"surface_group_measure"', source)
        readonly_block = source[source.index("if readonly and any(") :][:400]
        self.assertIn("surface_group_measure", readonly_block)


class SurfaceGroupMeasureProjectionTests(unittest.TestCase):
    def test_compact_projection_keeps_the_whole_group_block(self):
        projected = compact_operation(
            {"op": "surface_group_measure", "group": group_block(), "succeeded": True}
        )
        self.assertIn("group", projected)
        self.assertEqual(projected["group"]["state"], "closed")
        self.assertEqual(projected["group"]["open_edges"], 6)

    def test_normalization_keeps_measured_values(self):
        cleaned = normalize_surface_group(group_block())
        self.assertEqual(cleaned["open_edges"], 6)
        self.assertEqual(cleaned["gap_max_mm"], 0.0)
        self.assertEqual(cleaned["overlap_area_mm2"], 0.0)
        self.assertEqual(cleaned["state"], "closed")
        self.assertFalse(cleaned["boundary_closed"])

    def test_unavailable_status_nulls_its_value_and_keeps_the_reason(self):
        cleaned = normalize_surface_group(
            group_block(
                gap_max_mm=0.5,
                gap_max_status={
                    "available": False,
                    "reason": "boundary_edge_sampling_failed",
                    "query_code": -1,
                    "unit_name": "mm",
                    "scale_to_mm_known": True,
                },
            )
        )
        self.assertIsNone(cleaned["gap_max_mm"])
        self.assertEqual(cleaned["gap_max_status"]["reason"], "boundary_edge_sampling_failed")

    def test_unknown_unit_scale_keeps_every_mm_value_null(self):
        cleaned = normalize_surface_group(
            group_block(
                open_edges=4,
                open_edges_status={
                    "available": True,
                    "reason": None,
                    "query_code": 0,
                    "unit_name": None,
                    "scale_to_mm_known": False,
                },
                gap_max_mm=None,
                gap_max_status={
                    "available": False,
                    "reason": "unit_scale_unknown",
                    "query_code": 0,
                    "unit_name": None,
                    "scale_to_mm_known": False,
                },
                overlap_area_mm2=None,
                overlap_status={
                    "available": False,
                    "reason": "unit_scale_unknown",
                    "query_code": 0,
                    "unit_name": None,
                    "scale_to_mm_known": False,
                    "detected": True,
                },
                state=None,
                state_reason="unit_scale_unknown",
                boundary_closed=None,
            )
        )
        self.assertEqual(cleaned["open_edges"], 4)
        self.assertIsNone(cleaned["gap_max_mm"])
        self.assertIsNone(cleaned["overlap_area_mm2"])
        self.assertIsNone(cleaned["overlap_status"]["detected"])
        self.assertIsNone(cleaned["state"])
        self.assertEqual(cleaned["state_reason"], "unit_scale_unknown")
        self.assertIsNone(cleaned["boundary_closed"])

    def test_malformed_or_unknown_state_is_not_guessed(self):
        cleaned = normalize_surface_group(group_block(state="nearly_closed"))
        self.assertIsNone(cleaned["state"])
        self.assertEqual(cleaned["state_reason"], "surface_group_state_unknown")

    def test_all_four_states_are_recognised(self):
        self.assertEqual(SURFACE_GROUP_STATES, ("closed", "open", "micro_gap", "overlap"))
        for state in SURFACE_GROUP_STATES:
            with self.subTest(state=state):
                self.assertEqual(normalize_surface_group(group_block(state=state))["state"], state)

    def test_missing_status_nulls_unbacked_values(self):
        cleaned = normalize_surface_group(
            {"open_edges": 6, "gap_max_mm": 0.5, "overlap_area_mm2": 800.0, "state": "closed"}
        )
        self.assertIsNone(cleaned["open_edges"])
        self.assertIsNone(cleaned["gap_max_mm"])
        self.assertIsNone(cleaned["overlap_area_mm2"])
        self.assertIsNone(cleaned["boundary_closed"])

    def test_surface_loft_receipt_is_projected_too(self):
        result = {
            "operations": [
                {
                    "op": "surface_loft",
                    "surface_group": {
                        "unit_name": "mm",
                        "group": group_block(open_edges=4, state="open"),
                    },
                }
            ]
        }
        annotate_surface_group(result)
        block = result["operations"][0]["surface_group"]
        self.assertEqual(block["group"]["state"], "open")
        self.assertEqual(block["group"]["open_edges"], 4)

    def test_measurement_record_is_projected(self):
        result = {
            "operations": [
                {
                    "op": "surface_group_measure",
                    "group": group_block(
                        gap_max_mm=0.5,
                        gap_max_status={
                            "available": False,
                            "reason": "no_member_seam_candidate",
                            "query_code": 0,
                            "unit_name": "mm",
                            "scale_to_mm_known": True,
                        },
                        state="open",
                    ),
                }
            ]
        }
        annotate_surface_group(result)
        operation = result["operations"][0]
        self.assertIsNone(operation["group"]["gap_max_mm"])
        self.assertEqual(operation["group"]["state"], "open")


class SurfaceGroupNativeContractTests(unittest.TestCase):
    def test_native_measurement_uses_topology_and_real_geometry_queries(self):
        source = NATIVE.read_text(encoding="utf-8")
        for api in (
            "ProContourEdgeVisit",
            "ProEdgeTessellationGet",
            "ProEdgeLengthEval",
            "ProSurfaceParamEval",
            "ProSurfaceXyzdataEval",
            "ProSurfaceUvpntVerify",
        ):
            with self.subTest(api=api):
                self.assertIn(api, source)
        # The group answer must not be guessed from area or volume.
        self.assertNotIn("ProQuiltVolumeEval(", source)
        self.assertNotIn("quilt_area_native", source)
        self.assertIn('"no_member_seam_candidate"', source)
        self.assertIn('"boundary_edge_sampling_failed"', source)
        self.assertIn('"overlap_sample_budget_exceeded"', source)

    def test_native_four_state_thresholds_are_explicit(self):
        source = NATIVE.read_text(encoding="utf-8")
        for state in SURFACE_GROUP_STATES:
            with self.subTest(state=state):
                self.assertIn(f'"{state}"', source)
        # open/micro_gap are decided by the measured gap against the tolerance
        # and against a coincidence epsilon, not by an area or volume guess.
        self.assertIn("measurement.gap_max > tolerance + coincidence_epsilon", source)
        self.assertIn("measurement.max_joined_gap > coincidence_epsilon", source)
        self.assertIn("SURFACE_GROUP_COINCIDENT_EPSILON_MM", source)

    def test_surface_loft_publishes_the_same_group_block(self):
        loft = (ROOT / "native" / "surface_loft.cpp").read_text(encoding="utf-8")
        self.assertIn('details["surface_group"]', loft)
        self.assertIn("surface_group_receipt", loft)

    def test_dispatcher_registers_the_operation(self):
        generic = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8")
        self.assertIn('#include "surface_group.cpp"', generic)
        self.assertIn('kind == "surface_group_measure"', generic)


if __name__ == "__main__":
    unittest.main()
