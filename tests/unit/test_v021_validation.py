"""DEV-002 pure validation and modeling-helper regressions."""

import unittest

from creo_mechdog.schema import validate_operations


class AdvancedValidation(unittest.TestCase):
    def valid(self, op):
        return validate_operations([op])[0]

    def invalid(self, op):
        with self.assertRaises(ValueError):
            self.valid(op)

    def test_mirror_geometry_and_feature_references(self):
        base = {"op": "mirror", "label": "copy", "plane": {"kind": "datum_plane", "axis": "x"}}
        self.assertEqual(self.valid(base)["references"], [])
        feature = self.valid({**base, "references": [{"kind": "feature", "label": "solid"}]})
        self.assertEqual(feature["references"], [{"kind": "feature", "label": "solid"}])
        self.invalid({**base, "references": [{"kind": "feature"}]})
        self.invalid({**base, "references": [{"kind": "part"}, {"kind": "curve", "id": 1}]})

    def test_invalid_new_reference_ids(self):
        for kind in ("quilt", "csys", "point"):
            self.invalid(
                {
                    "op": "mirror",
                    "label": "copy",
                    "plane": {"kind": "datum_plane", "axis": "x"},
                    "references": [{"kind": kind, "id": -1}],
                }
            )

    def test_sweep_profile_and_trajectory(self):
        base = {
            "op": "sweep",
            "label": "pipe",
            "trajectory": "path",
            "profile": [{"type": "circle", "name": "c", "center": [0, 0], "radius": 2}],
        }
        self.assertEqual(self.valid(base)["mode"], "add")
        self.invalid({**base, "trajectory": []})
        self.invalid(
            {
                **base,
                "dimensions": [
                    {
                        "name": "size",
                        "type": "diameter",
                        "value": 4,
                        "refs": [{"entity": "missing"}],
                    }
                ],
            }
        )

    def test_loft_sections_and_draft_angle(self):
        self.invalid({"op": "loft", "label": "loft", "sections": ["a", "a"]})
        self.invalid({"op": "loft", "label": "loft", "sections": ["a"]})
        base = {
            "op": "draft",
            "label": "draft",
            "surfaces": [{"kind": "surface", "id": 1}],
            "neutral_plane": {"kind": "datum_plane", "axis": "z"},
            "angle": 0,
        }
        self.invalid(base)
        self.assertEqual(self.valid({**base, "angle": -3})["angle"], -3)

    def test_sheetmetal_numeric_limits(self):
        base = {
            "op": "sheetmetal_wall",
            "label": "wall",
            "sketch": "profile",
            "depth": 20,
            "thickness": 1,
        }
        self.assertEqual(self.valid(base)["thickness"], 1)
        self.invalid({**base, "thickness": 0})
        self.invalid({**base, "y_factor": 1.5})
        self.invalid(
            {
                "op": "sheetmetal_flange",
                "label": "flange",
                "edge": {"kind": "edge", "id": 1},
                "height": 10,
                "angle": 180,
            }
        )

    def test_assembly_placement_constraints_must_agree(self):
        base = {"op": "assemble_component", "label": "component", "source_model_id": "a" * 32}
        self.assertEqual(self.valid(base)["placement"], "fixed")
        self.invalid({**base, "placement": "constraints"})
        self.invalid({**base, "rotation": [0, 0]})
        self.invalid({**base, "source_model_id": "../file.prt"})

    def test_sheetmetal_unused_options_are_rejected(self):
        base = {
            "op": "sheetmetal_wall",
            "label": "wall",
            "sketch": "profile",
            "depth": 20,
            "thickness": 1,
        }
        self.invalid({**base, "bend_radius": 2})
        self.invalid({**base, "bend_sharps": True})


if __name__ == "__main__":
    unittest.main()
