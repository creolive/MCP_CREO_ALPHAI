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

    def test_custom_closure_tolerance_is_the_only_used_scale(self):
        entities = [
            {"type": "line", "name": "a", "start": [0, 0], "end": [10, 0]},
            {"type": "line", "name": "b", "start": [10, 0], "end": [10, 10]},
            {"type": "line", "name": "c", "start": [10, 10], "end": [0, 10]},
            {"type": "line", "name": "d", "start": [0, 10], "end": [0, 0.0005]},
        ]
        plan = [
            {"op": "sketch", "label": "s", "entities": entities},
            {"op": "extrude", "label": "e", "sketch": "s", "depth": 10},
        ]
        # The published default stays 1e-4 mm and still rejects this gap.
        with self.assertRaisesRegex(ValueError, "open contour"):
            validate_operations(plan)
        admitted = validate_operations([{**plan[0], "closure_tolerance_mm": 0.001}, plan[1]])
        self.assertEqual(admitted[0]["closure_tolerance_mm"], 0.001)
        for invalid in (0, -1, True, "0.001", float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                validate_operations([{**plan[0], "closure_tolerance_mm": invalid}])

    def test_update_sketch_geometry_accepts_the_same_closure_scale(self):
        (validated,) = validate_operations(
            [
                {
                    "op": "update_sketch_geometry",
                    "sketch": "s",
                    "closure_tolerance_mm": 0.002,
                    "entities": [
                        {"type": "line", "name": "a", "start": [0, 0], "end": [10, 0]},
                        {"type": "line", "name": "b", "start": [10, 0], "end": [0, 0.001]},
                    ],
                }
            ]
        )
        self.assertEqual(validated["closure_tolerance_mm"], 0.002)

    def test_profile_receipt_echoes_the_requested_closure_scale(self):
        from creo_mechdog.operation_results import annotate_profiles

        plan = [
            {
                "op": "sketch",
                "label": "s",
                "closure_tolerance_mm": 0.01,
                "entities": [
                    {"type": "line", "name": "a", "start": [0, 0], "end": [10, 0]},
                    {"type": "line", "name": "b", "start": [10, 0], "end": [0, 0.005]},
                ],
            },
            {"op": "extrude", "label": "e", "sketch": "s", "depth": 10},
        ]
        result = {"operations": [{"op": "sketch", "label": "s"}]}
        annotated = annotate_profiles(result, plan)
        self.assertEqual(annotated["operations"][0]["profile"]["closure_tolerance_mm"], 0.01)

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
