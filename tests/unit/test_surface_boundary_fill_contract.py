"""DEV-074/H09 surface_boundary_fill contract tests (offline only).

These tests lock the Python admission surface, the gated capability, the
result projection and the native source-level route of the closed non-planar
boundary fill. They never connect to Creo: the geometric closure/order rules
live in the native executor (curve endpoint sampling) and are locked here by
source, while the schema tests cover every request shape that must be refused
before a job exists. The 2026-11-08 live probe refuted the route (create and
extract succeed, regeneration leaves status 6 and no quilt), so the operation
is registered but gated and its tool is absent from the MCP surface.
"""

from __future__ import annotations

import asyncio
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native" / "surface_boundary_fill.cpp"
GENERIC = ROOT / "native" / "generic.cpp"
SURFACES = ROOT / "native" / "surfaces.cpp"
SERVER = ROOT / "server.py"


def boundary_fill(**overrides):
    operation = {
        "op": "surface_boundary_fill",
        "label": "closed_fill",
        "boundary": [
            {"kind": "curve", "id": 44},
            {"kind": "curve", "id": 52},
            {"kind": "curve", "id": 58},
        ],
    }
    operation.update(overrides)
    return operation


class BoundaryFillSchemaTests(unittest.TestCase):
    def validate(self, operation):
        from creo_mechdog.schema import validate_operations

        return validate_operations([operation])

    def test_accepts_an_ordered_three_curve_chain(self):
        validated = self.validate(boundary_fill())
        self.assertEqual(validated[0]["op"], "surface_boundary_fill")
        self.assertEqual(
            validated[0]["boundary"],
            [
                {"kind": "curve", "id": 44},
                {"kind": "curve", "id": 52},
                {"kind": "curve", "id": 58},
            ],
        )
        self.assertTrue(validated[0]["closed"])

    def test_accepts_a_longer_chain(self):
        boundary = [{"kind": "curve", "id": value} for value in (44, 52, 58, 66)]
        self.assertEqual(len(self.validate(boundary_fill(boundary=boundary))[0]["boundary"]), 4)

    def test_rejects_an_empty_chain(self):
        with self.assertRaisesRegex(ValueError, "at least 3"):
            self.validate(boundary_fill(boundary=[]))

    def test_rejects_a_two_curve_boundary_and_names_surface_loft(self):
        with self.assertRaisesRegex(ValueError, "surface_loft"):
            self.validate(
                boundary_fill(boundary=[{"kind": "curve", "id": 44}, {"kind": "curve", "id": 52}])
            )

    def test_rejects_an_explicitly_open_chain(self):
        with self.assertRaisesRegex(ValueError, "open chain"):
            self.validate(boundary_fill(closed=False))

    def test_rejects_a_repeated_edge(self):
        with self.assertRaisesRegex(ValueError, "repeated curve"):
            self.validate(
                boundary_fill(
                    boundary=[
                        {"kind": "curve", "id": 44},
                        {"kind": "curve", "id": 52},
                        {"kind": "curve", "id": 44},
                    ]
                )
            )

    def test_rejects_nested_loops_and_holes_before_a_job_exists(self):
        for boundary in (
            [
                [{"kind": "curve", "id": 44}, {"kind": "curve", "id": 52}],
                [{"kind": "curve", "id": 58}],
            ],
            ["loop_a", "loop_b"],
        ):
            with self.subTest(boundary=boundary):
                with self.assertRaises(ValueError):
                    self.validate(boundary_fill(boundary=boundary))
        with self.assertRaises(ValueError):
            self.validate(boundary_fill(holes=[{"kind": "curve", "id": 70}]))
        with self.assertRaises(ValueError):
            self.validate(boundary_fill(loops=[[{"kind": "curve", "id": 44}]]))

    def test_rejects_non_curve_kinds_and_loop_markers(self):
        for item in (
            {"kind": "quilt", "id": 21},
            {"kind": "surface", "id": 68},
            {"kind": "edge", "id": 70},
            {"kind": "body", "id": 1},
            {"kind": "curve", "label": "sketch_a"},
            {"kind": "curve", "id": 44, "loop": 1},
            {"kind": "curve", "id": 44, "reverse": True},
        ):
            with self.subTest(item=item):
                with self.assertRaises(ValueError):
                    self.validate(
                        boundary_fill(
                            boundary=[
                                {"kind": "curve", "id": 44},
                                {"kind": "curve", "id": 52},
                                item,
                            ]
                        )
                    )

    def test_rejects_invalid_curve_ids(self):
        for value in (-1, True, 2**31, "44", 4.0):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.validate(
                        boundary_fill(
                            boundary=[
                                {"kind": "curve", "id": 44},
                                {"kind": "curve", "id": 52},
                                {"kind": "curve", "id": value},
                            ]
                        )
                    )

    def test_planar_surface_fill_is_unchanged(self):
        # The new capability must not be smuggled into the planar fill op.
        with self.assertRaises(ValueError):
            self.validate(
                {
                    "op": "surface_fill",
                    "label": "planar",
                    "sketch": "closed_profile",
                    "boundary": [{"kind": "curve", "id": 44}],
                }
            )
        self.assertIn("PRO_FLAT", SURFACES.read_text(encoding="utf-8"))
        self.assertIn("PRO_E_SEC_USE_SKETCH", SURFACES.read_text(encoding="utf-8"))


class BoundaryFillCapabilityTests(unittest.TestCase):
    def test_operation_is_registered_but_gated(self):
        from creo_mechdog.capabilities import (
            REGISTERED_OPERATIONS,
            UNAVAILABLE_OPERATIONS,
            families,
        )

        self.assertIn("surface_boundary_fill", REGISTERED_OPERATIONS)
        self.assertIn("surface_boundary_fill", UNAVAILABLE_OPERATIONS)
        self.assertIn("feature_status=6", UNAVAILABLE_OPERATIONS["surface_boundary_fill"])
        self.assertNotIn("creo_surface_boundary_fill", families()["surface_chain"]["tools"])
        self.assertNotIn("surface_boundary_fill", families())

    def test_server_registers_the_tool(self):
        text = SERVER.read_text(encoding="utf-8")
        self.assertIn("async def creo_surface_boundary_fill(", text)
        self.assertIn('"surface_boundary_fill"', text)

    def test_mcp_tool_count_excludes_the_gated_tool(self):
        import server

        tools = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
        self.assertNotIn("creo_surface_boundary_fill", tools)
        # 106 = 107 minus the gated creo_surface_boundary_fill; the read-only
        # creo_measure_surface_curvature (DEV-074/H08) stays published.
        self.assertEqual(len(tools), 106)

    def test_require_available_refuses_the_gated_operation(self):
        from creo_mechdog.capabilities import require_available

        with self.assertRaisesRegex(ValueError, "surface_boundary_fill"):
            require_available(self.validated())

    def validated(self):
        from creo_mechdog.schema import validate_operations

        return validate_operations([boundary_fill()])


class BoundaryFillProjectionTests(unittest.TestCase):
    def test_compact_projection_keeps_the_measurements(self):
        from creo_mechdog.job_projection import (
            _OPERATION_CRITERIA,
            SURFACE_BOUNDARY_FILL_KEYS,
            compact_operation,
        )

        self.assertIs(_OPERATION_CRITERIA["surface_boundary_fill"], SURFACE_BOUNDARY_FILL_KEYS)
        for key in (
            "quilt_id",
            "face_count",
            "surface_area_mm2",
            "surface_area_status",
            "quilt_closed_native",
            "has_solid",
            "boundary_edges",
            "boundary_curve_ids",
        ):
            self.assertIn(key, SURFACE_BOUNDARY_FILL_KEYS)
        record = {
            "op": "surface_boundary_fill",
            "label": "closed_fill",
            "quilt_id": 74,
            "face_count": 1,
            "surface_area_mm2": 804.247719319002,
            "boundary_edges": 3,
            "debug_note": "dropped",
        }
        compact = compact_operation(record)
        self.assertEqual(compact["quilt_id"], 74)
        self.assertEqual(compact["boundary_edges"], 3)
        self.assertNotIn("debug_note", compact)

    def test_the_group_block_is_normalized_for_the_new_op(self):
        from creo_mechdog.operation_results import annotate_surface_group

        result = {
            "operations": [
                {
                    "op": "surface_boundary_fill",
                    "surface_group": {
                        "group": {
                            "open_edges": 3,
                            "open_edges_status": {"available": True},
                            "gap_max_mm": 99.0,
                            "gap_max_status": {"available": False},
                            "state": "made_up",
                            "boundary_closed": False,
                        }
                    },
                }
            ]
        }
        group = annotate_surface_group(result)["operations"][0]["surface_group"]["group"]
        self.assertEqual(group["open_edges"], 3)
        self.assertIsNone(group["gap_max_mm"])
        self.assertIsNone(group["state"])
        self.assertEqual(group["state_reason"], "surface_group_state_unknown")


class BoundaryFillNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = NATIVE.read_text(encoding="utf-8")
        cls.code = "\n".join(
            line for line in cls.text.splitlines() if not line.lstrip().startswith("//")
        )

    def test_the_route_reuses_the_documented_closed_blend_tree(self):
        for lock in (
            "static void generic_surface_boundary_fill(const J &op)",
            "PRO_FEAT_DATUM_SURF",
            "PRO_USE_SURFS",
            "PRO_E_DTM_SRF_TYPE_BND_BLEND",
            "PRO_E_BNBLN_CURVES",
            "PRO_E_BNBLN_1DIR",
            "PRO_E_BNBLN_DIR_CURVES",
            "PRO_E_STD_CHAIN_HOLDER",
            "PRO_E_STD_CURVE_COLLECTION_APPL",
            "curve_collection",
            "PRO_E_BBL_ADD_CLOSED",
            "PRO_FEAT_CR_INCOMPLETE_FEAT",
            "ProFeatureElemtreeExtract",
            "redefine(&feature, extracted)",
        ):
            self.assertIn(lock, self.code)

    def test_the_chain_is_checked_from_real_curve_endpoints(self):
        for lock in (
            "ProCurveXyzdataEval",
            "boundary_fill_check_chain",
            "boundary_fill_link_gap",
            "not connected in the submitted order",
            "boundary chain is open",
            "SURFACE_BOUNDARY_FILL_TOLERANCE_MM",
        ):
            self.assertIn(lock, self.text)

    def test_duplicate_curves_and_non_curves_are_refused_with_alternatives(self):
        for message in (
            "is repeated",
            "is not a resolvable curve geometry id",
            "creo_project_curve",
            "creo_surface_loft",
        ):
            self.assertIn(message, self.text)

    def test_an_unknown_length_unit_is_refused_before_the_tree_is_built(self):
        self.assertIn("length unit is unknown", self.text)
        self.assertIn("scale.known", self.text)

    def test_the_result_is_measured_and_not_a_solid(self):
        for lock in (
            "quilt_area_native",
            "quilt_closed_native",
            "boundary_fill_faces",
            "surface_group_receipt",
            "has_solid",
            "must be an open quilt",
        ):
            self.assertIn(lock, self.text)

    def test_native_is_dispatched_and_included(self):
        generic = GENERIC.read_text(encoding="utf-8")
        self.assertIn('#include "surface_boundary_fill.cpp"', generic)
        self.assertIn('else if (kind == "surface_boundary_fill")', generic)
        self.assertIn("generic_surface_boundary_fill(op)", generic)


if __name__ == "__main__":
    unittest.main()
