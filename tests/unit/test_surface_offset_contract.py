"""FEAT-039/S07: the offset request is well formed but stays gated.

ProTrim.h documents a thin-trim variant that offsets the trimming surface
before it cuts. On this machine the kernel accepts those elements but the cut
does not move (2026-11-04: a 5 mm offset on a 40x20 fill still leaves
400/400 mm2, and a 50 mm offset that cannot intersect is not refused), so the
request is refused before a job is queued instead of silently doing nothing.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SURFACE_TRIM = ROOT / "native" / "surface_trim.cpp"


def trim_operation(**overrides) -> dict:
    operation = {
        "op": "surface_trim",
        "label": "offset_trim",
        "target": {"kind": "quilt", "id": 12},
        "tool": {"kind": "datum_plane", "label": "cut_plane"},
        "keep_side": "one",
    }
    operation.update(overrides)
    return operation


class SurfaceOffsetSchemaTests(unittest.TestCase):
    def test_accepts_a_distance_with_a_direction(self):
        from creo_mechdog.schema import validate_operations

        validated = validate_operations([trim_operation(offset_mm=5.0, offset_side="one")])
        self.assertEqual(validated[0]["offset_mm"], 5.0)
        self.assertEqual(validated[0]["offset_side"], "one")

    def test_refuses_a_distance_without_a_direction(self):
        from creo_mechdog.schema import validate_operations

        with self.assertRaises(ValueError):
            validate_operations([trim_operation(offset_mm=5.0)])

    def test_refuses_a_direction_without_a_distance(self):
        from creo_mechdog.schema import validate_operations

        with self.assertRaises(ValueError):
            validate_operations([trim_operation(offset_side="two")])

    def test_refuses_an_offset_for_a_curve_tool(self):
        from creo_mechdog.schema import validate_operations

        with self.assertRaises(ValueError):
            validate_operations(
                [
                    trim_operation(
                        tool={"kind": "curve", "id": 7},
                        offset_mm=5.0,
                        offset_side="one",
                    )
                ]
            )


class SurfaceOffsetGateTests(unittest.TestCase):
    def test_offset_requests_are_refused_before_a_job_is_queued(self):
        from creo_mechdog.capabilities import require_available

        with self.assertRaises(ValueError) as caught:
            require_available([trim_operation(offset_mm=5.0, offset_side="one")])
        message = str(caught.exception)
        self.assertIn("offset_mm is not published", message)
        # The refusal carries the measured reason, not a generic denial.
        self.assertIn("400/400", message)

    def test_a_plain_trim_is_not_blocked(self):
        from creo_mechdog.capabilities import require_available

        require_available([trim_operation()])

    def test_native_uses_the_documented_thin_trim_elements(self):
        source = SURFACE_TRIM.read_text(encoding="utf-8")
        self.assertIn("PRO_E_THICKNESS", source)
        self.assertIn("PRO_E_STD_USEQLT_SIDE", source)
        self.assertIn("PRO_E_SRF_OFFS_METHOD", source)
        self.assertIn("PRO_TRIM_SRF_OFFS_METH_NORMTOSURF", source)


if __name__ == "__main__":
    unittest.main()
