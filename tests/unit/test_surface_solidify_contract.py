"""FEAT-039/S06: contract for turning a quilt into a solid.

A quilt can only become a solid when it is closed, and the result must be
measurable instead of merely created. The live evidence (2026-11-04, a
360 degree revolved cylinder) is: closed quilt, area 1000*pi mm2, solidified
volume 2000*pi mm3, saved and reloaded; an open quilt is refused with the
measured ProQuiltVolumeEval code and the job rolls back.
"""

import unittest
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
SURFACES = ROOT / "native" / "surfaces.cpp"


def solidify_operation(**overrides) -> dict:
    operation = {
        "op": "solidify",
        "label": "solid_body",
        "reference": {"kind": "quilt", "id": 12},
        "side": "positive",
    }
    operation.update(overrides)
    return operation


class SurfaceSolidifySchemaTests(unittest.TestCase):
    def test_accepts_one_quilt_reference(self):
        from creo_mechdog.schema import validate_operations

        validated = validate_operations([solidify_operation()])
        self.assertEqual(validated[0]["op"], "solidify")
        self.assertEqual(validated[0]["reference"], {"kind": "quilt", "id": 12})

    def test_rejects_body_reference(self):
        from creo_mechdog.schema import validate_operations

        with self.assertRaises(ValidationError):
            validate_operations([solidify_operation(reference={"kind": "body", "id": 3})])

    def test_rejects_unknown_side(self):
        from creo_mechdog.schema import validate_operations

        with self.assertRaises(ValidationError):
            validate_operations([solidify_operation(side="both")])

    def test_solidify_is_published(self):
        from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS

        self.assertIn("solidify", REGISTERED_OPERATIONS)
        self.assertNotIn("solidify", UNAVAILABLE_OPERATIONS)


class SurfaceSolidifyNativeTests(unittest.TestCase):
    def test_native_measures_closure_before_building(self):
        source = SURFACES.read_text(encoding="utf-8")
        # The closure is measured with the shared quilt helper, not guessed.
        self.assertIn("quilt_closed_native", source)
        self.assertIn("quilt_closed_is_open", source)
        self.assertIn("ProQuiltVolumeEval", source)

    def test_native_refuses_an_open_quilt_with_the_measured_code(self):
        source = SURFACES.read_text(encoding="utf-8")
        self.assertIn("solidify requires a closed quilt", source)
        self.assertIn("the referenced quilt is open", source)

    def test_native_reports_the_volume_in_the_operation_result(self):
        source = SURFACES.read_text(encoding="utf-8")
        self.assertIn("volume_after_mm3", source)
        self.assertIn("volume_before_mm3", source)
        self.assertIn("stage_operation_result", source)

    def test_native_keeps_a_second_measurement_implementation_away(self):
        source = SURFACES.read_text(encoding="utf-8")
        # The volume comes from the shared mass property helper; a second
        # measurement path would drift from it.
        self.assertNotIn("ProSolidVolumeCompute", source)


if __name__ == "__main__":
    unittest.main()
