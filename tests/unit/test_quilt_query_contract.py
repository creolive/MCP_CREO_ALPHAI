"""S01 quilt query contract tests (FEAT-055 / FEAT-039).

Offline only: the Python side is exercised against synthetic snapshots, and
the native half is locked at source level (single home of quilt enumeration,
bounded reference candidates, unit-safe measurements). Live geometry is the
driver's job (`tools/test_surface_chain.py --case quilts` against a running
session); these tests never pretend native behavior passed.
"""

import unittest
from pathlib import Path

from creo_mechdog.model_queries import (
    COUNT_KEYS,
    SECTIONS,
    inspect_page,
    inspection_summary,
    section_records,
)

ROOT = Path(__file__).resolve().parents[2]
GENERIC = ROOT / "native" / "generic.cpp"
QUILT_QUERY = ROOT / "native" / "quilt_query.h"
SURFACE_MEASURE = ROOT / "native" / "surface_measure.h"

QUILT_RECORD = {
    "quilt_id": 7,
    "feature_ids": [3],
    "face_count": 2,
    "surface_ids": [11, 12],
    "area_mm2": None,
    "area_status": {
        "available": False,
        "reason": "unit_scale_unknown",
        "query_code": 0,
        "scale_to_mm_known": False,
        "unit_name": None,
    },
    "closed": None,
    "closed_status": {
        "available": False,
        "reason": "quilt_volume_eval_failed",
        "query_code": 3,
        "scale_to_mm_known": False,
        "unit_name": None,
    },
    "bbox_mm": None,
    "bbox_status": {
        "available": False,
        "reason": "surface_data_get_failed",
        "query_code": 2,
        "scale_to_mm_known": False,
        "unit_name": None,
    },
}


def synthetic_model(quilts):
    inspection = {
        "healthy": True,
        "has_solid": True,
        "model_type": "part",
        "features": [],
        "surfaces": [{"id": 11}, {"id": 12}],
        "edges": [],
        "bodies": [],
        "counts": {"surfaces": 2, "edges": 0},
    }
    if quilts is not None:
        inspection["quilts"] = quilts
    return {
        "model_id": "m1",
        "model_name": "m1.prt",
        "model_type": "part",
        "revision": 1,
        "inspection": inspection,
        "part_file": "m1.prt",
        "status": "ready",
    }


class QuiltSectionTests(unittest.TestCase):
    def test_quilts_section_available(self):
        self.assertIn("quilts", SECTIONS)
        self.assertIn("quilts", COUNT_KEYS)
        model = synthetic_model([QUILT_RECORD])
        self.assertEqual(section_records(model, "quilts"), [QUILT_RECORD])
        summary = inspection_summary(model["inspection"])
        self.assertEqual(summary["counts"]["quilts"], 1)
        page = inspect_page(model, "full", section="quilts")
        self.assertEqual(page["data"]["quilts"], [QUILT_RECORD])
        self.assertIn("quilts", page["sections_available"])
        # A legacy snapshot keeps its surfaces section untouched; the new
        # section is additive (FEAT-055: old fields never change meaning).
        self.assertEqual(section_records(model, "surfaces"), [{"id": 11}, {"id": 12}])

    def test_legacy_snapshot_quilts_unavailable(self):
        model = synthetic_model(None)
        self.assertIsNone(section_records(model, "quilts"))
        summary = inspection_summary(model["inspection"])
        # Absent means unknown, never zero (BUG-040 precedent).
        self.assertIsNone(summary["counts"]["quilts"])

    def test_quilts_cursor_bound_to_snapshot(self):
        model = synthetic_model([QUILT_RECORD])
        first = inspect_page(model, "full", section="quilts", limit=1)
        cursor = first["next_cursor"]
        self.assertIsNone(cursor)  # one record fits within the page
        grown = synthetic_model([QUILT_RECORD, {**QUILT_RECORD, "quilt_id": 8}])
        second = inspect_page(grown, "full", section="quilts", limit=1)
        self.assertIsNotNone(second["next_cursor"])
        with self.assertRaises(ValueError):
            inspect_page(
                {**grown, "revision": 2},
                "full",
                section="quilts",
                limit=1,
                cursor=second["next_cursor"],
            )

    def test_quilt_record_keeps_ids_apart(self):
        # S00 R1: a quilt id is not a surface id. surface_ids lists member
        # faces for face-level references; quilt_id references the quilt.
        record = dict(QUILT_RECORD)
        self.assertIsInstance(record["quilt_id"], int)
        self.assertIsInstance(record["surface_ids"], list)
        self.assertNotIn(record["quilt_id"], record["surface_ids"])

    def test_unknown_unit_keeps_measurements_null(self):
        model = synthetic_model([QUILT_RECORD])
        served = section_records(model, "quilts")[0]
        for field, status in (
            ("area_mm2", "area_status"),
            ("bbox_mm", "bbox_status"),
        ):
            self.assertIsNone(served[field])
            self.assertFalse(served[status]["available"])
            self.assertFalse(served[status]["scale_to_mm_known"])
            self.assertTrue(served[status]["reason"])
        # The query side never backfills a fabricated number or status.
        self.assertEqual(served["area_status"]["reason"], "unit_scale_unknown")


class QuiltNativeContractTests(unittest.TestCase):
    """Source-level locks for the native half; live evidence comes from the driver."""

    def test_quilt_helpers_live_in_their_single_home(self):
        text = QUILT_QUERY.read_text(encoding="utf-8")
        for marker in (
            "collect_model_quilts",
            "resolve_quilt_reference",
            "quilt_reference_candidates",
            "QUILT_CANDIDATE_SAMPLE_LIMIT",
        ):
            self.assertIn(marker, text)
        generic = GENERIC.read_text(encoding="utf-8")
        self.assertIn('#include "quilt_query.h"', generic)
        self.assertIn("collect_model_quilts((ProSolid)board", generic)

    def test_quilt_and_surface_ids_never_share_a_resolver_path(self):
        text = GENERIC.read_text(encoding="utf-8")
        self.assertIn('kind == "quilt"', text)
        self.assertIn("return resolve_quilt_reference(r", text)
        # The old one-liner that selected any id as PRO_QUILT is gone; the
        # explicit quilt path validates the id against the collected quilts.
        self.assertNotIn('kind == "point" || kind == "quilt"', text)

    def test_candidates_are_bounded_and_annotated(self):
        text = QUILT_QUERY.read_text(encoding="utf-8")
        self.assertIn("QUILT_CANDIDATE_SAMPLE_LIMIT = 20", text)
        self.assertIn("feature_ids", text)
        self.assertIn("face_count", text)
        self.assertIn("area_mm2", text)

    def test_measurements_refuse_unknown_scale(self):
        text = SURFACE_MEASURE.read_text(encoding="utf-8")
        self.assertIn("unit_scale_unknown", text)
        self.assertIn("scale.known", text)
        self.assertIn("ProContourAreaEval", text)
        self.assertIn("ProContourTraversalGet", text)
        self.assertIn("ProCurveLengthEval", text)

    def test_closed_uses_the_documented_quilt_probe(self):
        # S03 moved the probe into surface_measure.h so trim and merge share one
        # implementation; quilt_query.h must delegate instead of keeping a copy.
        text = QUILT_QUERY.read_text(encoding="utf-8")
        self.assertIn("quilt_closed_native", text)
        self.assertNotIn("ProQuiltVolumeEval", text)
        measure = SURFACE_MEASURE.read_text(encoding="utf-8")
        self.assertIn("ProQuiltVolumeEval", measure)
        self.assertIn("PRO_TK_INVALID_TYPE", measure)


if __name__ == "__main__":
    unittest.main()
