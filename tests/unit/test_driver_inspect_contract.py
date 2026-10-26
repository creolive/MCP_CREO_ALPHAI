"""FEAT-008/012 driver response-contract regressions (offline).

Real public MCP payload shapes observed 2026-10-25 (semantic copies kept in
build/driver_real_contract_20261025T1555/mcp_payloads.json, read-only
evidence; these tests rebuild the minimal DTOs inline and never reference
that absolute path):

- A compact ``creo_inspect_model`` carries volume/units/query codes under
  ``inspection`` with ``revision`` TOP-LEVEL (real source part: volume 30 at
  ``inspection.volume_mm3``, revision 1). There is no top-level
  ``volume_mm3``.
- A full ``creo_inspect_model`` section carries records under
  ``data.<section>`` (``data.bodies[0].bbox``); there is no top-level
  ``bodies`` key.
- One root assembly occurrence is rendered under DIFFERENT display names by
  different APIs: ``creo_list_components`` component ``model_name``
  '▩C_A3C874E18A0445A10001' vs ``creo_inspect_session_assembly`` item
  ``name`` 'C_A3C874E18A0445A1_0', same feature_id/component_id 40,
  occurrence_path [40]. Display names are not identity.

Both live drivers initially read top-level ``volume_mm3`` / ``bodies`` and
joined occurrences by display name; the matrix driver raised KeyError at its
line 323 in the 2026-10-25 guarded run after all 11 pose groups had already
passed, so none of the geometry assertions ever ran.
"""

import unittest

import tools.test_assembly_matrix as matrix_driver
import tools.test_assembly_pipeline as pipeline_driver
from tools.test_assembly_matrix import compact_inspection, full_section_records

MODEL_ID = "fd09fe5a21524488af34a5c868de8f32"


def compact_payload(volume=30.0, revision=1) -> dict:
    """Minimal DTO matching the real compact creo_inspect_model payload."""
    return {
        "model_id": MODEL_ID,
        "model_name": "ai_part_fd09fe5a2152",
        "model_type": "part",
        "status": "ready",
        "revision": revision,
        "part_sha256": "9c1673465cb460da5fdc3ab3caed48795132d5e093f7e3cf61d14ab13e5b7d80",
        "inspection": {
            "healthy": True,
            "has_solid": True,
            "units": "mm",
            "units_query_code": 0,
            "model_type": "part",
            "volume_mm3": volume,
            "volume_query_code": 0,
            "inspection_source": "saved_reloaded",
            "inspection_available": True,
            "counts": {"features": 8, "surfaces": 6, "edges": 12, "bodies": 1},
        },
        "snapshot": {
            "source": "saved_verified",
            "revision": revision,
            "live_state_verified": False,
            "mutation_pending": False,
        },
        "detail": "compact",
        "complete": True,
    }


def bodies_payload() -> dict:
    """Minimal DTO matching the real full bodies section payload."""
    return {
        "model_id": MODEL_ID,
        "revision": 1,
        "detail": "full",
        "section": "bodies",
        "data": {
            "bodies": [
                {
                    "bbox": [[0, 0, 0], [2, 3, 5]],
                    "has_geometry": True,
                    "id": 52,
                    "state": 4,
                }
            ]
        },
        "next_cursor": None,
        "offset": 0,
        "unavailable_sections": [],
        "returned_count": 1,
    }


class CompactInspectionContract(unittest.TestCase):
    def test_real_compact_shape_extracts_volume_and_revision(self):
        info = compact_inspection(compact_payload())
        self.assertEqual(info["revision"], 1)
        self.assertEqual(info["volume_mm3"], 30)
        self.assertEqual(info["units"], "mm")
        self.assertEqual(info["volume_query_code"], 0)
        self.assertEqual(info["inspection_source"], "saved_reloaded")

    def test_old_top_level_volume_access_reproduces_live_keyerror(self):
        payload = compact_payload()
        with self.assertRaises(KeyError):
            _ = payload["volume_mm3"]  # exactly what matrix line 323 did
        compact_inspection(payload)  # corrected path still works

    def test_missing_volume_is_a_failure_not_a_default_zero(self):
        payload = compact_payload()
        del payload["inspection"]["volume_mm3"]
        with self.assertRaises(AssertionError):
            compact_inspection(payload)
        payload = compact_payload(volume=None)
        payload["inspection"]["volume_query_code"] = -4
        with self.assertRaises(AssertionError):
            compact_inspection(payload)

    def test_non_millimeter_units_fail_without_unverified_conversion(self):
        # BUG-072 semantics: non-mm units legitimately yield volume_mm3 None;
        # the driver must refuse, never convert or pass.
        payload = compact_payload(volume=None, revision=1)
        payload["inspection"]["units"] = "in"
        payload["inspection"]["units_query_code"] = 0
        payload["inspection"]["volume_query_code"] = -3
        with self.assertRaises(AssertionError):
            compact_inspection(payload)

    def test_missing_top_level_revision_fails(self):
        payload = compact_payload()
        del payload["revision"]
        with self.assertRaises(AssertionError):
            compact_inspection(payload)

    def test_assembly_volume_invariance_math_matches_matrix_driver(self):
        # 11 posed occurrences of the 30 mm3 source -> 330 mm3 assembly.
        source = compact_inspection(compact_payload(volume=30.0, revision=1))
        assembly = compact_inspection(compact_payload(volume=330.0, revision=34))
        expected = 11 * source["volume_mm3"]
        self.assertLessEqual(abs(assembly["volume_mm3"] - expected), 0.01)


class FullSectionContract(unittest.TestCase):
    def test_bodies_records_live_under_data(self):
        payload = bodies_payload()
        (body,) = full_section_records(payload, "bodies")
        self.assertEqual(body["bbox"], [[0, 0, 0], [2, 3, 5]])
        self.assertTrue(body["has_geometry"])

    def test_old_top_level_bodies_access_reproduces_keyerror(self):
        payload = bodies_payload()
        with self.assertRaises(KeyError):
            _ = payload["bodies"]  # exactly what the matrix driver did
        full_section_records(payload, "bodies")

    def test_empty_section_records_fail(self):
        payload = bodies_payload()
        payload["data"]["bodies"] = []
        with self.assertRaises(AssertionError):
            full_section_records(payload, "bodies")

    def test_missing_data_block_fails(self):
        payload = bodies_payload()
        del payload["data"]
        with self.assertRaises(AssertionError):
            full_section_records(payload, "bodies")


class SharedContractImplementation(unittest.TestCase):
    def test_both_drivers_use_one_compact_inspection_helper(self):
        # The exact defect class fixed here was two drivers parsing the same
        # contract differently; keep a single implementation for both.
        self.assertIs(pipeline_driver.compact_inspection, matrix_driver.compact_inspection)


if __name__ == "__main__":
    unittest.main()
