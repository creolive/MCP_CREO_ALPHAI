"""DEV-081 / F11: main-plane offset/direction semantics are documented; behavior unchanged."""

from __future__ import annotations

import unittest
from pathlib import Path

import server
from creo_mechdog.schema import SketchOp

REPO = Path(__file__).resolve().parents[2]
REFERENCE = REPO / "docs" / "REFERENCE_SYNTAX.md"


class PlaneSemanticsTests(unittest.TestCase):
    def test_offset_field_description_names_plane_coordinate(self):
        description = SketchOp.model_fields["offset"].description
        self.assertIsNotNone(description)
        self.assertIn("plane_coordinate", description)
        self.assertIn("global", description)

    def test_execute_plan_docstring_states_three_plane_frames(self):
        doc = server.creo_execute_plan.__doc__ or ""
        for term in ("plane_coordinate", "XZ", "negative Y"):
            self.assertIn(term, doc)

    def test_reference_syntax_table_states_xz_negative_y(self):
        text = REFERENCE.read_text(encoding="utf-8")
        for term in (
            "[0, 0, offset]",
            "[offset, 0, 0]",
            "[0, offset, 0]",
            "negative Y",
            "全局坐标",
            "不是沿法向",
        ):
            self.assertIn(term, text)

    def test_xz_offset_behavior_unchanged(self):
        sketch = SketchOp(
            op="sketch",
            label="xz_sk",
            plane="XZ",
            offset=500,
            dimensioning="coordinates",
            entities=[{"type": "line", "name": "a", "start": [0, 0], "end": [10, 0]}],
        )
        self.assertEqual(sketch.offset, 500)
        self.assertNotIn("direction", SketchOp.model_fields)


if __name__ == "__main__":
    unittest.main()
