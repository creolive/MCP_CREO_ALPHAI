"""FEAT-039/S07: the controlled surface offset contract."""

import unittest
from pathlib import Path


class SurfaceOffsetContractTests(unittest.TestCase):
    def test_the_schema_accepts_a_quilt_reference(self):
        from creo_mechdog.schema import validate_operations

        operations = validate_operations(
            [
                {
                    "op": "surface_offset",
                    "label": "offset",
                    "reference": {"kind": "quilt", "id": 3},
                    "distance": 5.0,
                }
            ]
        )
        self.assertEqual(operations[0]["distance"], 5.0)
        self.assertEqual(operations[0]["side"], "positive")

    def test_a_body_reference_is_refused(self):
        from creo_mechdog.schema import validate_operations

        with self.assertRaises(ValueError):
            validate_operations(
                [
                    {
                        "op": "surface_offset",
                        "label": "offset",
                        "reference": {"kind": "body", "id": 3},
                        "distance": 5.0,
                    }
                ]
            )

    def test_a_non_positive_distance_is_refused(self):
        from creo_mechdog.schema import validate_operations

        with self.assertRaises(ValueError):
            validate_operations(
                [
                    {
                        "op": "surface_offset",
                        "label": "offset",
                        "reference": {"kind": "quilt", "id": 3},
                        "distance": 0.0,
                    }
                ]
            )

    def test_the_operator_is_published(self):
        from creo_mechdog.capabilities import REGISTERED_OPERATIONS, families

        self.assertIn("surface_offset", REGISTERED_OPERATIONS)
        entry = families()["surface_offset"]
        self.assertTrue(entry["enabled"])
        # The published evidence is the measured acceptance, not the request.
        self.assertIn("3999.9999999999995 mm3", entry["native_test"])
        self.assertIn("4.999999999999999 mm", entry["native_test"])

    def test_the_release_record_lists_s07_as_published(self):
        record = (
            Path(__file__).resolve().parents[2] / "docs" / "validation" / "RELEASE-0.13.0.md"
        ).read_text(encoding="utf-8")
        self.assertIn("| S07 偏置 | ✅ 实机公开（`creo_surface_offset`）", record)

    def test_the_native_side_uses_the_documented_offset_method(self):
        native = (Path(__file__).resolve().parents[2] / "native" / "surfaces.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("PRO_E_SRF_OFFS_METHOD, PRO_OFFS_METH_NORMTOSURF", native)
        self.assertIn("PRO_E_STD_USEQLT_SIDE", native)
        self.assertIn("measured_offset_distance_mm", native)


if __name__ == "__main__":
    unittest.main()
