"""BUG-062: update_sketch_geometry accepts revolve centerlines."""

import unittest

from creo_mechdog.schema import SketchGeometryOp, validate_operations

CENTERLINE = dict(type="centerline", name="axis", start=[-6, 0], end=[6, 0])
ARC = dict(type="arc", name="rim", center=[0, 0], radius=5, start_angle=0, end_angle=180)
LINE = dict(type="line", name="base", start=[-5, 0], end=[5, 0])


class SketchGeometryEditCenterline(unittest.TestCase):
    def test_centerline_accepted_in_update(self):
        op = SketchGeometryOp.model_validate(
            dict(op="update_sketch_geometry", sketch="profile", entities=[ARC, LINE, CENTERLINE])
        )
        self.assertEqual(op.entities[-1].type, "centerline")

    def test_centerline_accepted_via_plan_validation(self):
        validate_operations(
            [
                dict(
                    op="update_sketch_geometry",
                    sketch="profile",
                    entities=[ARC, LINE, CENTERLINE],
                )
            ]
        )

    def test_second_centerline_still_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            SketchGeometryOp.model_validate(
                dict(
                    op="update_sketch_geometry",
                    sketch="profile",
                    entities=[ARC, LINE, CENTERLINE, dict(CENTERLINE, name="axis2")],
                )
            )
        self.assertIn("One revolve centerline", str(ctx.exception))

    def test_entity_names_must_stay_unique(self):
        with self.assertRaises(ValueError):
            SketchGeometryOp.model_validate(
                dict(op="update_sketch_geometry", sketch="profile", entities=[ARC, ARC])
            )


if __name__ == "__main__":
    unittest.main()
