"""DEV-074/H08: numerical curvature and G1 analysis contract tests (offline).

The SDK has no zebra-stripe or curvature-comb API; the deliverable is numeric.
These tests pin the request shape, the published read-only tool, the compact
projection and the §4.4.1 rule that a value never outlives its status. The
native sampling itself (ProSurfacePrincipalCrvtEval, ProSurfaceDataGet UV
extents, ProSurfaceUvpntVerify and the seam normal angle) is locked by source,
not executed: no test here connects to Creo.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import server
from creo_mechdog.capabilities import (
    REGISTERED_OPERATIONS,
    UNAVAILABLE_OPERATIONS,
    families,
    require_available,
)
from creo_mechdog.job_projection import (
    _OPERATION_CRITERIA,
    SURFACE_CURVATURE_KEYS,
    compact_operation,
)
from creo_mechdog.operation_results import (
    normalize_surface_curvature,
    normalize_surface_curvature_face,
)
from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native" / "surface_curvature.cpp"
GENERIC = ROOT / "native" / "generic.cpp"
SERVER = ROOT / "server.py"


def curvature(**overrides):
    operation = {
        "op": "surface_curvature",
        "target": {"kind": "quilt", "id": 70},
        "faces": [{"kind": "surface", "id": 68}],
    }
    operation.update(overrides)
    return operation


def status(available=True, reason=None, **extra):
    payload = {
        "available": available,
        "reason": reason,
        "query_code": 0 if available else -1,
        "unit_name": "mm",
        "scale_to_mm_known": True,
    }
    payload.update(extra)
    return payload


class SurfaceCurvatureSchemaTests(unittest.TestCase):
    def validate(self, operation):
        return validate_operations([operation])

    def test_defaults_to_twelve_samples_per_direction(self):
        validated = self.validate(curvature())[0]
        self.assertEqual(validated["op"], "surface_curvature")
        self.assertEqual(validated["samples_per_direction"], 12)
        self.assertEqual(validated["faces"], [{"kind": "surface", "id": 68}])

    def test_accepts_a_member_index_and_two_faces(self):
        validated = self.validate(
            curvature(
                faces=[0, {"kind": "surface", "id": 66}],
                samples_per_direction=24,
            )
        )[0]
        self.assertEqual(validated["faces"], [0, {"kind": "surface", "id": 66}])
        self.assertEqual(validated["samples_per_direction"], 24)

    def test_density_bounds_are_inclusive(self):
        for density in (5, 50):
            with self.subTest(density=density):
                validated = self.validate(curvature(samples_per_direction=density))[0]
                self.assertEqual(validated["samples_per_direction"], density)

    def test_non_numeric_and_out_of_range_density_is_refused(self):
        for density in (4, 51, 0, -3, 12.5, True, "12", None):
            with self.subTest(density=density):
                with self.assertRaises(ValueError):
                    self.validate(curvature(samples_per_direction=density))

    def test_refuses_unusable_targets_and_faces(self):
        refused = {
            "datum_plane_target": curvature(target={"kind": "datum_plane", "label": "TOP"}),
            "quilt_without_id": curvature(target={"kind": "quilt"}),
            "no_faces": curvature(faces=[]),
            "three_faces": curvature(
                faces=[
                    {"kind": "surface", "id": 68},
                    {"kind": "surface", "id": 66},
                    {"kind": "surface", "id": 64},
                ]
            ),
            "edge_face": curvature(faces=[{"kind": "edge", "id": 70}]),
            "face_label": curvature(faces=[{"kind": "surface", "label": "face_a"}]),
            "extra_face_key": curvature(faces=[{"kind": "surface", "id": 68, "label": "x"}]),
            "negative_index": curvature(faces=[-1]),
            "negative_id": curvature(faces=[{"kind": "surface", "id": -1}]),
            "same_face_twice": curvature(
                faces=[{"kind": "surface", "id": 68}, {"kind": "surface", "id": 68}]
            ),
        }
        for name, operation in refused.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.validate(operation)

    def test_registered_and_admitted_read_only(self):
        self.assertIn("surface_curvature", REGISTERED_OPERATIONS)
        self.assertNotIn("surface_curvature", UNAVAILABLE_OPERATIONS)
        require_available(self.validate(curvature()))


class SurfaceCurvatureRegistrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_read_only_tool_is_published(self):
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        self.assertIn("creo_measure_surface_curvature", tools)
        tool = tools["creo_measure_surface_curvature"]
        self.assertTrue(tool.annotations.read_only_hint)
        self.assertFalse(tool.annotations.destructive_hint)
        properties = tool.input_schema["properties"]
        self.assertEqual(properties["samples_per_direction"]["default"], 12)
        self.assertEqual(properties["faces"]["minItems"], 1)
        self.assertEqual(properties["faces"]["maxItems"], 2)
        # 107 adds this tool to the 106 that carry creo_surface_boundary_fill.
        self.assertEqual(len(tools), 107)

    def test_capability_family_publishes_the_numeric_equivalence(self):
        self.assertIn("creo_measure_surface_curvature", families()["surface_chain"]["tools"])
        entry = families()["surface_curvature"]
        self.assertTrue(entry["enabled"])
        self.assertEqual(entry["tool"], "creo_measure_surface_curvature")
        self.assertIn("no zebra-stripe or curvature-comb image", entry["limits"])
        self.assertIn("zebra-stripe", families()["surface_chain"]["scope"])

    def test_server_registers_the_tool_and_the_route_name(self):
        text = SERVER.read_text(encoding="utf-8")
        self.assertIn("async def creo_measure_surface_curvature(", text)
        self.assertIn("general.measure_surface_curvature", text)

    def test_readonly_admission_accepts_the_curvature_query(self):
        source = (ROOT / "generic_bridge.py").read_text(encoding="utf-8")
        readonly_block = source[source.index("if readonly and any(") :][:400]
        self.assertIn("surface_curvature", readonly_block)


class SurfaceCurvatureProjectionTests(unittest.TestCase):
    def test_compact_projection_keeps_the_face_and_g1_blocks(self):
        self.assertIs(_OPERATION_CRITERIA["surface_curvature"], SURFACE_CURVATURE_KEYS)
        for key in ("faces", "summary", "g1_points", "g1_status", "within_g1"):
            self.assertIn(key, SURFACE_CURVATURE_KEYS)
        compact = compact_operation(
            {
                "op": "surface_curvature",
                "faces": [{"surface_id": 68, "points": []}],
                "summary": {"sample_count": 144},
                "g1_points": [],
                "debug_note": "dropped",
            }
        )
        self.assertIn("faces", compact)
        self.assertIn("summary", compact)
        self.assertNotIn("debug_note", compact)

    def test_unavailable_status_nulls_its_face_values(self):
        cleaned = normalize_surface_curvature_face(
            {
                "surface_id": 68,
                "max_abs_curvature_per_mm": 0.5,
                "max_abs_curvature_status": status(False, "principal_curvature_eval_failed"),
                "min_curvature_radius_mm": 2.0,
                "min_curvature_radius_status": status(False, "principal_curvature_eval_failed"),
            }
        )
        self.assertIsNone(cleaned["max_abs_curvature_per_mm"])
        self.assertIsNone(cleaned["min_curvature_radius_mm"])
        self.assertEqual(
            cleaned["max_abs_curvature_status"]["reason"], "principal_curvature_eval_failed"
        )

    def test_a_measured_zero_curvature_is_kept(self):
        cleaned = normalize_surface_curvature_face(
            {
                "surface_id": 68,
                "max_abs_curvature_per_mm": 0.0,
                "max_abs_curvature_status": status(),
                "min_curvature_radius_mm": None,
                "min_curvature_radius_status": status(False, "zero_curvature"),
            }
        )
        self.assertEqual(cleaned["max_abs_curvature_per_mm"], 0.0)
        self.assertIsNone(cleaned["min_curvature_radius_mm"])
        self.assertEqual(cleaned["min_curvature_radius_status"]["reason"], "zero_curvature")

    def test_unknown_unit_scale_keeps_every_mm_value_null(self):
        cleaned = normalize_surface_curvature(
            {
                "length_scale_to_mm": None,
                "faces": [
                    {
                        "surface_id": 68,
                        "max_abs_curvature_per_mm": None,
                        "max_abs_curvature_status": status(
                            False, "unit_scale_unknown", scale_to_mm_known=False
                        ),
                        "min_curvature_radius_mm": None,
                        "min_curvature_radius_status": status(
                            False, "unit_scale_unknown", scale_to_mm_known=False
                        ),
                        "points": [
                            {
                                "u": 0.5,
                                "v": 0.5,
                                "max_curvature_per_mm": None,
                                "min_curvature_per_mm": None,
                                "max_radius_mm": None,
                                "min_radius_mm": None,
                                "status": status(
                                    False, "unit_scale_unknown", scale_to_mm_known=False
                                ),
                            }
                        ],
                    }
                ],
                "summary": {
                    "max_abs_curvature_per_mm": None,
                    "max_abs_curvature_status": status(
                        False, "unit_scale_unknown", scale_to_mm_known=False
                    ),
                    "min_curvature_radius_mm": None,
                    "min_curvature_radius_status": status(
                        False, "unit_scale_unknown", scale_to_mm_known=False
                    ),
                },
            }
        )
        self.assertIsNone(cleaned["faces"][0]["max_abs_curvature_per_mm"])
        self.assertIsNone(cleaned["summary"]["max_abs_curvature_per_mm"])
        self.assertIsNone(cleaned["faces"][0]["points"][0]["max_curvature_per_mm"])
        self.assertEqual(cleaned["faces"][0]["points"][0]["status"]["reason"], "unit_scale_unknown")

    def test_within_g1_is_only_a_threshold_marker(self):
        def receipt(angle):
            return normalize_surface_curvature(
                {
                    "g1_max_angle_deg": angle,
                    "g1_threshold_deg": 0.5,
                    "g1_status": status(),
                    "within_g1": None,
                }
            )

        self.assertTrue(receipt(0.4)["within_g1"])
        self.assertFalse(receipt(0.6)["within_g1"])
        # The angle itself is preserved, never replaced by the marker.
        self.assertEqual(receipt(0.6)["g1_max_angle_deg"], 0.6)

    def test_unavailable_g1_nulls_the_angle(self):
        cleaned = normalize_surface_curvature(
            {
                "g1_max_angle_deg": 0.1,
                "g1_threshold_deg": 0.5,
                "g1_status": status(False, "no_shared_edge"),
                "within_g1": True,
            }
        )
        self.assertIsNone(cleaned["g1_max_angle_deg"])
        self.assertIsNone(cleaned["within_g1"])
        self.assertEqual(cleaned["g1_status"]["reason"], "no_shared_edge")


class SurfaceCurvatureNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = NATIVE.read_text(encoding="utf-8")
        cls.code = "\n".join(
            line for line in cls.text.splitlines() if not line.lstrip().startswith("//")
        )

    def test_the_numeric_route_uses_the_documented_queries(self):
        for lock in (
            "static void generic_surface_curvature(const J &op)",
            "ProSurfacePrincipalCrvtEval",
            "ProSurfaceDataGet",
            "ProSurfaceUvpntVerify",
            "ProSurfaceXyzdataEval",
            "ProSurfaceParamEval",
            "ProEdgeXyzdataEval",
            "SURFACE_CURVATURE_G1_THRESHOLD_DEG",
        ):
            self.assertIn(lock, self.code)

    def test_no_visualization_api_is_claimed(self):
        # The module must not pretend a zebra/comb API exists; it is numeric.
        for forbidden in ("Zebra", "CurvatureComb", "ProCurvature"):
            self.assertNotIn(forbidden, self.code)
        self.assertIn("no zebra-stripe or curvature-comb visualization API", self.text)

    def test_failures_are_counts_and_never_fabricated_zero(self):
        for lock in (
            "failure_count",
            "outside_contour_count",
            "principal_curvature_eval_failed",
            "no_curvature_samples_inside_face",
            "unit_scale_unknown",
        ):
            self.assertIn(lock, self.text)
        self.assertIn("failure_count++", self.code)

    def test_native_is_dispatched_included_and_not_regenerated(self):
        generic = GENERIC.read_text(encoding="utf-8")
        self.assertIn('#include "surface_curvature.cpp"', generic)
        self.assertIn('else if (kind == "surface_curvature")', generic)
        self.assertIn("generic_surface_curvature(op)", generic)
        self.assertIn('kind != "surface_curvature"', generic)


if __name__ == "__main__":
    unittest.main()
