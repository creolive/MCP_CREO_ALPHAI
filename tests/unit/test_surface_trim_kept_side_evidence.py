"""FEAT-039/H06: the surface_trim kept-side evidence contract.

Offline only. The native executor now samples the target and retained regions
(tessellation triangles) and reports ``target_centroid``/``kept_centroid``,
``*_bbox_mm`` and ``*_direction`` beside one status per measurement. These tests
lock the Python projection: a value never outlives its status, an unknown unit
scale keeps millimeter values null, and an unavailable status keeps its reason
instead of a zero. No Creo session is involved.
"""

import unittest

from creo_mechdog.operation_results import (
    annotate_kept_side_basis,
    annotate_native_result,
    normalize_kept_side_basis,
    normalize_region_measurement_status,
)

STATUS_OK = {
    "available": True,
    "reason": None,
    "query_code": 0,
    "scale_to_mm_known": True,
    "unit_name": "mm",
    "source": "surface_tessellation",
    "face_count": 1,
    "triangle_count": 2,
    "tessellation_complete": True,
}


def basis(**overrides):
    block = {
        "keep_side": "one",
        "tool_kind": "datum_plane",
        "tool_normal": [1.0, 0.0, 0.0],
        "tool_normal_source": "datum_plane_axis",
        "target_centroid": [20.0, 10.0, 0.0],
        "target_centroid_status": dict(STATUS_OK),
        "kept_centroid": [22.5, 10.0, 0.0],
        "kept_centroid_status": dict(STATUS_OK),
        "centroid_delta_mm": [2.5, 0.0, 0.0],
        "target_bbox_mm": {
            "min": [0.0, 0.0, 0.0],
            "max": [40.0, 20.0, 0.0],
            "size": [40.0, 20.0, 0.0],
        },
        "target_bbox_status": dict(STATUS_OK),
        "kept_bbox_mm": {
            "min": [5.0, 0.0, 0.0],
            "max": [40.0, 20.0, 0.0],
            "size": [35.0, 20.0, 0.0],
        },
        "kept_bbox_status": dict(STATUS_OK),
        "target_direction": [0.0, 0.0, -1.0],
        "target_direction_status": {**STATUS_OK, "planar": True, "max_normal_deviation_deg": 0.0},
        "kept_direction": [0.0, 0.0, -1.0],
        "kept_direction_status": {**STATUS_OK, "planar": True, "max_normal_deviation_deg": 0.0},
        "signed_offset_mm": 2.5,
        "signed_offset_status": dict(STATUS_OK),
        "centroid_status": dict(STATUS_OK),
    }
    block.update(overrides)
    return block


def trim_result(block=None, *, op="surface_trim"):
    record = {"op": op, "succeeded": True}
    if block is not None:
        record["kept_side_basis"] = block
    return {"success": True, "operations": [record]}


class NormalizeMeasurementStatusTests(unittest.TestCase):
    def test_missing_block_keeps_a_reason(self):
        status = normalize_region_measurement_status(None, "kept_centroid_status")
        self.assertFalse(status["available"])
        self.assertEqual(status["reason"], "kept_centroid_missing")
        self.assertIsNone(status["query_code"])

    def test_unavailable_without_reason_gets_a_default(self):
        status = normalize_region_measurement_status(
            {"available": False, "query_code": -68}, "kept_bbox_status"
        )
        self.assertEqual(status["reason"], "kept_bbox_unavailable")
        self.assertEqual(status["query_code"], -68)

    def test_reason_and_unit_context_survive(self):
        status = normalize_region_measurement_status(
            {
                "available": False,
                "reason": "surface_tessellation_failed",
                "query_code": -68,
                "scale_to_mm_known": False,
                "unit_name": "inch",
            },
            "kept_centroid_status",
        )
        self.assertEqual(status["reason"], "surface_tessellation_failed")
        self.assertEqual(status["unit_name"], "inch")
        self.assertFalse(status["scale_to_mm_known"])

    def test_diagnostics_ride_through(self):
        status = normalize_region_measurement_status(STATUS_OK, "target_bbox_status")
        self.assertEqual(status["source"], "surface_tessellation")
        self.assertEqual(status["triangle_count"], 2)
        self.assertTrue(status["tessellation_complete"])


class KeptSideBasisTests(unittest.TestCase):
    def test_measured_block_is_kept(self):
        normalized = normalize_kept_side_basis(basis())
        self.assertEqual(normalized["target_centroid"], [20.0, 10.0, 0.0])
        self.assertEqual(normalized["kept_centroid"], [22.5, 10.0, 0.0])
        self.assertEqual(normalized["centroid_delta_mm"], [2.5, 0.0, 0.0])
        self.assertEqual(normalized["kept_bbox_mm"]["max"], [40.0, 20.0, 0.0])
        self.assertEqual(normalized["kept_direction"], [0.0, 0.0, -1.0])
        self.assertEqual(normalized["signed_offset_mm"], 2.5)
        # Unrelated evidence is untouched.
        self.assertEqual(normalized["tool_normal"], [1.0, 0.0, 0.0])
        self.assertEqual(normalized["tool_normal_source"], "datum_plane_axis")

    def test_unavailable_status_nulls_the_value_and_keeps_the_reason(self):
        block = basis(
            kept_centroid=None,
            kept_centroid_status={
                "available": False,
                "reason": "no_tessellation_triangles",
                "query_code": 0,
                "scale_to_mm_known": True,
                "unit_name": "mm",
            },
        )
        normalized = normalize_kept_side_basis(block)
        self.assertIsNone(normalized["kept_centroid"])
        self.assertEqual(normalized["kept_centroid_status"]["reason"], "no_tessellation_triangles")
        # The delta cannot survive one missing side.
        self.assertIsNone(normalized["centroid_delta_mm"])

    def test_unknown_unit_keeps_millimeter_values_null(self):
        unit_unknown = {
            "available": True,
            "reason": None,
            "query_code": 0,
            "scale_to_mm_known": False,
            "unit_name": "inch",
        }
        normalized = normalize_kept_side_basis(
            basis(
                target_centroid_status=dict(unit_unknown),
                kept_centroid_status=dict(unit_unknown),
                target_bbox_status=dict(unit_unknown),
                kept_bbox_status=dict(unit_unknown),
                signed_offset_status=dict(unit_unknown),
            )
        )
        self.assertIsNone(normalized["target_centroid"])
        self.assertIsNone(normalized["kept_centroid"])
        self.assertIsNone(normalized["target_bbox_mm"])
        self.assertIsNone(normalized["kept_bbox_mm"])
        self.assertIsNone(normalized["centroid_delta_mm"])
        self.assertIsNone(normalized["signed_offset_mm"])
        self.assertTrue(normalized["kept_centroid_status"]["available"])
        self.assertFalse(normalized["kept_centroid_status"]["scale_to_mm_known"])
        self.assertEqual(normalized["signed_offset_status"]["reason"], "unit_scale_unknown")
        # A direction is unitless, so it survives an unknown length scale.
        self.assertEqual(normalized["kept_direction"], [0.0, 0.0, -1.0])

    def test_non_planar_region_has_no_direction(self):
        normalized = normalize_kept_side_basis(
            basis(
                kept_direction=[0.0, 0.0, -1.0],
                kept_direction_status={
                    **STATUS_OK,
                    "available": False,
                    "reason": "region_not_planar",
                    "planar": False,
                    "max_normal_deviation_deg": 42.0,
                },
            )
        )
        self.assertIsNone(normalized["kept_direction"])
        self.assertEqual(normalized["kept_direction_status"]["reason"], "region_not_planar")
        self.assertFalse(normalized["kept_direction_status"]["planar"])

    def test_direction_without_planar_flag_is_dropped(self):
        normalized = normalize_kept_side_basis(
            basis(kept_direction_status={**STATUS_OK, "planar": False})
        )
        self.assertIsNone(normalized["kept_direction"])

    def test_malformed_bbox_becomes_null(self):
        normalized = normalize_kept_side_basis(
            basis(kept_bbox_mm={"min": [5.0, 0.0, 0.0], "max": [40.0, 20.0, 0.0]})
        )
        self.assertIsNone(normalized["kept_bbox_mm"])

    def test_non_finite_measurement_is_not_evidence(self):
        normalized = normalize_kept_side_basis(
            basis(kept_centroid=[22.5, float("nan"), 0.0], signed_offset_mm=float("inf"))
        )
        self.assertIsNone(normalized["kept_centroid"])
        self.assertIsNone(normalized["signed_offset_mm"])
        self.assertEqual(normalized["signed_offset_status"]["reason"], "signed_offset_not_finite")

    def test_signed_offset_without_status_is_an_unbacked_claim(self):
        block = basis()
        block.pop("signed_offset_status")
        normalized = normalize_kept_side_basis(block)
        self.assertIsNone(normalized["signed_offset_mm"])

    def test_legacy_block_without_new_fields_is_not_extended(self):
        legacy = {
            "keep_side": "one",
            "tool_normal": [1.0, 0.0, 0.0],
            "target_centroid": None,
            "kept_centroid": None,
            "signed_offset_mm": None,
            "centroid_status": {
                "available": False,
                "reason": "quilt_centroid_not_measured",
                "query_code": 0,
                "scale_to_mm_known": False,
                "unit_name": None,
            },
        }
        normalized = normalize_kept_side_basis(legacy)
        self.assertNotIn("target_bbox_mm", normalized)
        self.assertNotIn("kept_direction", normalized)
        self.assertIsNone(normalized["target_centroid"])
        # A value whose status was never reported gets an explicit reason; no
        # measurement and no synthetic bbox/direction block appears.
        self.assertEqual(normalized["target_centroid_status"]["reason"], "target_centroid_missing")
        self.assertEqual(normalized["centroid_status"]["reason"], "quilt_centroid_not_measured")


class AnnotateKeptSideBasisTests(unittest.TestCase):
    def test_surface_trim_record_is_projected(self):
        result = annotate_kept_side_basis(
            trim_result(
                basis(
                    kept_centroid=[999.0, 999.0, 999.0],
                    kept_centroid_status={
                        "available": False,
                        "reason": "quilt_surface_visit_failed",
                        "query_code": -4,
                        "scale_to_mm_known": True,
                        "unit_name": "mm",
                    },
                )
            )
        )
        record = result["operations"][0]
        self.assertIsNone(record["kept_side_basis"]["kept_centroid"])
        self.assertEqual(
            record["kept_side_basis"]["kept_centroid_status"]["reason"],
            "quilt_surface_visit_failed",
        )

    def test_other_operations_and_missing_blocks_are_untouched(self):
        other = trim_result(basis(), op="surface_fill")
        annotate_kept_side_basis(other)
        self.assertEqual(other["operations"][0]["kept_side_basis"], basis())
        without = trim_result()
        annotate_kept_side_basis(without)
        self.assertNotIn("kept_side_basis", without["operations"][0])

    def test_native_result_entry_applies_the_projection(self):
        result = annotate_native_result(
            trim_result(
                basis(
                    signed_offset_mm=2.5,
                    signed_offset_status={**STATUS_OK, "scale_to_mm_known": False},
                )
            ),
            readonly=False,
        )
        record = result["operations"][0]
        self.assertIsNone(record["kept_side_basis"]["signed_offset_mm"])
        self.assertEqual(
            record["kept_side_basis"]["signed_offset_status"]["reason"],
            "unit_scale_unknown",
        )


if __name__ == "__main__":
    unittest.main()
