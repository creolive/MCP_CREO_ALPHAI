"""BUG-112: the surface_offset source-area receipt and its distance guard.

Offline only. The executor publishes ``source_area_status`` beside the existing
``source_area_mm2``; when the area is unavailable, the source area and the
``volume_after / source_area`` distance are nulls, never a fabricated finite
value. The native branch sharing ``quilt_gauge_ready`` is covered by
``tests/native/test_surface_measure_guard.cpp`` (run by
``tools/test_surface_measure_guard.py``); these tests lock the Python side.
"""

import unittest
from pathlib import Path

from creo_mechdog.operation_results import (
    annotate_native_result,
    annotate_offset_distance_status,
    annotate_source_area_status,
    normalize_offset_distance_status,
    normalize_source_area_status,
)

ROOT = Path(__file__).resolve().parents[2]


def offset_result(status, *, area=800.0, measured=5.0):
    record = {
        "op": "surface_offset",
        "succeeded": True,
        "feature_id": 12,
        "source_area_mm2": area,
        "measured_offset_distance_mm": measured,
        "offset_distance_mm": 5.0,
        "direction": "positive",
        "offset_method": "normal_to_surface",
        "volume_after_mm3": 4000.0,
    }
    if status is not None:
        record["source_area_status"] = status
    return {"success": True, "operations": [record]}


class SourceAreaStatusProjectionTests(unittest.TestCase):
    def test_failed_init_keeps_the_code_and_nulls_the_distance(self):
        result = annotate_source_area_status(
            offset_result(
                {
                    "available": False,
                    "init_code": -1,
                    "query_code": None,
                    "reason": "quilt_init_failed",
                }
            )
        )
        record = result["operations"][0]
        self.assertEqual(
            record["source_area_status"],
            {
                "available": False,
                "init_code": -1,
                "query_code": None,
                "reason": "quilt_init_failed",
            },
        )
        self.assertIsNone(record["source_area_mm2"])
        self.assertIsNone(record["measured_offset_distance_mm"])

    def test_missing_handle_is_reported_not_measured(self):
        result = annotate_source_area_status(
            offset_result(
                {
                    "available": False,
                    "init_code": 0,
                    "query_code": None,
                    "reason": "quilt_handle_missing",
                }
            )
        )
        status = result["operations"][0]["source_area_status"]
        self.assertFalse(status["available"])
        self.assertEqual(status["init_code"], 0)
        self.assertIsNone(status["query_code"])
        self.assertEqual(status["reason"], "quilt_handle_missing")

    def test_measurement_failure_keeps_its_own_query_code(self):
        result = annotate_source_area_status(
            offset_result(
                {
                    "available": False,
                    "init_code": 0,
                    "query_code": -34,
                    "reason": "quilt_surface_visit_failed",
                }
            )
        )
        record = result["operations"][0]
        self.assertEqual(record["source_area_status"]["query_code"], -34)
        self.assertEqual(record["source_area_status"]["reason"], "quilt_surface_visit_failed")
        self.assertIsNone(record["measured_offset_distance_mm"])

    def test_available_area_keeps_the_measured_distance(self):
        result = annotate_source_area_status(
            offset_result({"available": True, "init_code": 0, "query_code": 0, "reason": None})
        )
        record = result["operations"][0]
        self.assertEqual(record["source_area_mm2"], 800.0)
        self.assertEqual(record["measured_offset_distance_mm"], 5.0)
        self.assertEqual(record["source_area_status"]["init_code"], 0)

    def test_a_non_finite_distance_is_unknown_even_when_available(self):
        result = annotate_source_area_status(
            offset_result(
                {"available": True, "init_code": 0, "query_code": 0, "reason": None},
                measured=float("inf"),
            )
        )
        record = result["operations"][0]
        self.assertIsNone(record["measured_offset_distance_mm"])
        self.assertEqual(record["source_area_mm2"], 800.0)


class SourceAreaStatusShapeTests(unittest.TestCase):
    def test_an_unavailable_receipt_without_reason_gains_one(self):
        status = normalize_source_area_status({"available": False})
        self.assertFalse(status["available"])
        self.assertIsNone(status["init_code"])
        self.assertIsNone(status["query_code"])
        self.assertEqual(status["reason"], "source_area_unavailable")

    def test_codes_of_the_wrong_type_stay_unknown(self):
        status = normalize_source_area_status(
            {"available": False, "init_code": "0", "query_code": 1.5, "reason": 7}
        )
        self.assertIsNone(status["init_code"])
        self.assertIsNone(status["query_code"])
        self.assertEqual(status["reason"], "source_area_unavailable")

    def test_a_malformed_receipt_degrades_to_unavailable(self):
        result = annotate_source_area_status(offset_result([]))
        record = result["operations"][0]
        self.assertEqual(record["source_area_status"]["reason"], "source_area_status_missing")
        self.assertIsNone(record["measured_offset_distance_mm"])

    def test_a_legacy_record_without_the_receipt_is_untouched(self):
        result = annotate_source_area_status(offset_result(None))
        record = result["operations"][0]
        self.assertNotIn("source_area_status", record)
        self.assertEqual(record["measured_offset_distance_mm"], 5.0)

    def test_records_of_other_operations_are_untouched(self):
        result = {
            "success": True,
            "operations": [
                {
                    "op": "surface_trim",
                    "area_after_mm2": 700.0,
                    "source_area_status": {"available": False},
                }
            ],
        }
        record = annotate_source_area_status(result)["operations"][0]
        # Only surface_offset owns this receipt; another op's block is not
        # rewritten into the surface_offset shape.
        self.assertEqual(record["source_area_status"], {"available": False})
        self.assertEqual(record["area_after_mm2"], 700.0)


class OffsetDistanceStatusTests(unittest.TestCase):
    """FEAT-039/R01: the distance is a scoped measurement, not a ratio."""

    def receipt(self, status, *, area=800.0, measured=None, area_available=True):
        record = {
            "op": "surface_offset",
            "succeeded": True,
            "feature_id": 12,
            "source_area_mm2": area,
            "measured_offset_distance_mm": measured,
            "offset_distance_mm": 5.0,
            "direction": "positive",
            "offset_method": "normal_to_surface",
            "source_area_status": {
                "available": area_available,
                "init_code": 0,
                "query_code": 0 if area_available else None,
                "reason": None if area_available else "quilt_surface_visit_failed",
            },
        }
        if status is not None:
            record["offset_distance_status"] = status
        return {"success": True, "operations": [record]}

    def test_existing_solid_does_not_become_offset_distance(self):
        # 800 mm2 source, 5 mm offset, 1000 mm3 already in the part: the total
        # 5000/800 = 6.25 is not the offset. The native receipt refuses it and
        # the projection must not resurrect a number from the volumes.
        result = annotate_offset_distance_status(
            self.receipt(
                {
                    "available": False,
                    "source": None,
                    "query_code": None,
                    "reason": "pre_existing_volume",
                },
                measured=None,
            )
        )
        record = annotate_source_area_status(result)["operations"][0]
        self.assertIsNone(record["measured_offset_distance_mm"])
        self.assertEqual(record["offset_distance_status"]["reason"], "pre_existing_volume")
        self.assertTrue(record["source_area_status"]["available"])
        self.assertEqual(record["source_area_mm2"], 800.0)

    def test_curved_source_has_unverified_distance(self):
        result = annotate_offset_distance_status(
            self.receipt(
                {
                    "available": False,
                    "source": None,
                    "query_code": None,
                    "reason": "source_quilt_not_a_single_plane",
                }
            )
        )
        record = result["operations"][0]
        self.assertIsNone(record["measured_offset_distance_mm"])
        self.assertEqual(
            record["offset_distance_status"]["reason"], "source_quilt_not_a_single_plane"
        )
        self.assertEqual(record["source_area_mm2"], 800.0)

    def test_verified_single_plane_keeps_its_source(self):
        result = annotate_offset_distance_status(
            self.receipt(
                {
                    "available": True,
                    "source": "volume_over_source_area",
                    "query_code": None,
                    "reason": None,
                },
                measured=5.0,
            )
        )
        record = result["operations"][0]
        self.assertEqual(record["measured_offset_distance_mm"], 5.0)
        self.assertEqual(
            record["offset_distance_status"],
            {
                "available": True,
                "source": "volume_over_source_area",
                "query_code": None,
                "reason": None,
            },
        )

    def test_available_receipt_without_a_known_source_is_downgraded(self):
        result = annotate_offset_distance_status(
            self.receipt(
                {"available": True, "source": "bounding_box_ratio", "query_code": 0},
                measured=5.0,
            )
        )
        record = result["operations"][0]
        self.assertIsNone(record["measured_offset_distance_mm"])
        self.assertFalse(record["offset_distance_status"]["available"])
        self.assertEqual(
            record["offset_distance_status"]["reason"], "offset_distance_source_unknown"
        )

    def test_a_non_finite_measured_value_is_downgraded(self):
        result = annotate_offset_distance_status(
            self.receipt(
                {
                    "available": True,
                    "source": "volume_over_source_area",
                    "query_code": None,
                    "reason": None,
                },
                measured=float("inf"),
            )
        )
        record = result["operations"][0]
        self.assertIsNone(record["measured_offset_distance_mm"])
        self.assertEqual(record["offset_distance_status"]["reason"], "offset_distance_not_finite")

    def test_a_malformed_receipt_degrades_to_unavailable(self):
        result = annotate_offset_distance_status(self.receipt(["unexpected"]))
        record = result["operations"][0]
        self.assertEqual(
            record["offset_distance_status"]["reason"], "offset_distance_status_missing"
        )
        self.assertIsNone(record["measured_offset_distance_mm"])

    def test_a_legacy_record_without_the_receipt_is_untouched(self):
        result = self.receipt(None)
        annotate_offset_distance_status(result)
        record = result["operations"][0]
        self.assertNotIn("offset_distance_status", record)
        self.assertIsNone(record["measured_offset_distance_mm"])

    def test_normalizer_defaults_to_unavailable(self):
        status = normalize_offset_distance_status({"available": False})
        self.assertEqual(
            status,
            {
                "available": False,
                "source": None,
                "query_code": None,
                "reason": "offset_distance_unavailable",
            },
        )

    def test_the_native_offset_gates_the_ratio(self):
        native = (ROOT / "native" / "surfaces.cpp").read_text(encoding="utf-8")
        self.assertIn('"offset_distance_status"', native)
        self.assertIn('"pre_existing_volume"', native)
        self.assertIn('"source_quilt_not_a_single_plane"', native)
        self.assertIn("quilt_planarity_native(quilt)", native)
        self.assertNotIn("volume_after / source_area", native)
        header = (ROOT / "native" / "quilt_query.h").read_text(encoding="utf-8")
        self.assertIn("struct QuiltPlanarity", header)
        self.assertIn("PRO_SRF_PLANE", header)


class NativeWiringTests(unittest.TestCase):
    def test_annotate_native_result_applies_the_receipt(self):
        annotated = annotate_native_result(
            offset_result(
                {
                    "available": False,
                    "init_code": -1,
                    "query_code": None,
                    "reason": "quilt_init_failed",
                }
            ),
            readonly=False,
            inputs=None,
        )
        record = annotated["operations"][0]
        self.assertIsNone(record["measured_offset_distance_mm"])
        self.assertEqual(record["source_area_status"]["reason"], "quilt_init_failed")

    def test_the_native_offset_measures_only_through_the_shared_guard(self):
        native = (ROOT / "native" / "surfaces.cpp").read_text(encoding="utf-8")
        self.assertIn('#include "quilt_gauge_guard.h"', native)
        self.assertIn("quilt_gauge_ready((int)init_code, quilt)", native)
        self.assertIn('"source_area_status"', native)
        self.assertNotIn("; quilt)", native)

    def test_c4552_is_an_error_for_the_repository_native_sources(self):
        bridge = (ROOT / "bridge.py").read_text(encoding="utf-8")
        cl_lines = [line for line in bridge.splitlines() if line.startswith("cl ")]
        native_lines = [line for line in cl_lines if "native/" in line]
        self.assertTrue(native_lines)
        for line in native_lines:
            self.assertIn("/we4552", line)


if __name__ == "__main__":
    unittest.main()
