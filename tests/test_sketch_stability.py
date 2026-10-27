"""Reject malformed profiles without ruling out valid complex or open sketches."""

import unittest
from unittest.mock import patch

import generic_bridge
from creo_mechdog.schema import validate_operations


class SketchStability(unittest.TestCase):
    def test_open_report_fragment_rejected_before_queue(self):
        entities = [
            {"type": "line", "name": "d1", "start": [0, -6800], "end": [0, 6800]},
            {"type": "line", "name": "d2", "start": [0, 6900], "end": [68300, 6900]},
            {
                "type": "arc",
                "name": "d3",
                "center": [68300, -9176.0869],
                "radius": 16076.0869,
                "start_angle": 34.8054,
                "end_angle": 90,
            },
            {"type": "line", "name": "d5", "start": [68300, -6900], "end": [0, -6900]},
        ]
        sections = [
            dict(op="sketch", label=f"s{i}", entities=entities, offset=i * 1000) for i in range(2)
        ]
        with patch.object(generic_bridge, "submit") as submit:
            with self.assertRaisesRegex(ValueError, "open or branched"):
                generic_bridge.new_loft_part(None, None, sections)
            submit.assert_not_called()

    def test_coordinate_mode_scope_and_mixed_dimensions_rejected_before_queue(self):
        sketch = dict(
            op="sketch",
            label="s",
            dimensioning="coordinates",
            entities=[
                dict(
                    type="arc", name="a", center=[0, 0], radius=5000, start_angle=-90, end_angle=90
                )
            ],
        )
        self.assertEqual(validate_operations([sketch])[0]["dimensioning"], "coordinates")
        # FEAT-010 T04: dictionary planes now join coordinate dimensioning; the
        # mode, entity-type and mixing rules below stay admission failures.
        dictionary = validate_operations(
            [{**sketch, "plane": {"reference": {"kind": "surface", "id": 1}}}]
        )[0]
        self.assertEqual(dictionary["dimensioning"], "coordinates")
        for change in (
            {"dimensioning": "rigid"},
            {"entities": [dict(type="spline", name="s", points=[[0, 0], [10, 5], [20, 0]])]},
            {"dimensions": [dict(name="r", type="radius", refs=[{"entity": "a"}], value=5000)]},
            {"constraints": [dict(type="horizontal", refs=[{"entity": "a"}])]},
        ):
            with patch.object(generic_bridge.bridge, "toolkit_lock") as lock:
                with self.assertRaises(ValueError):
                    generic_bridge.submit([{**sketch, **change}])
                lock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
