"""DEV-002 pure validation and modeling-helper regressions."""

import math
import unittest

from creo_mechdog.schema import Assertions, validate_operations


class FidelityAssertions(unittest.TestCase):
    def test_fidelity_assertions_are_admitted_and_echoed(self):
        admitted = Assertions.model_validate(
            {
                "max_geometry_deviation_mm": 0.001,
                "require_exact_solve": True,
                "preserve_input_geometry": True,
            }
        )
        dumped = admitted.model_dump(exclude_none=True)
        self.assertEqual(dumped["max_geometry_deviation_mm"], 0.001)
        self.assertTrue(dumped["require_exact_solve"])
        self.assertTrue(dumped["preserve_input_geometry"])

    def test_deviation_bound_rejects_non_positive_and_non_numeric(self):
        for bad in (0, -1, True, "0.001", float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                Assertions.model_validate({"max_geometry_deviation_mm": bad})
        self.assertIsNone(
            Assertions.model_validate({})
            .model_dump(exclude_none=True)
            .get("max_geometry_deviation_mm")
        )


class GeneralValidation(unittest.TestCase):
    def test_unknown_operation_and_invalid_mirror(self):
        for op in (
            {"op": "run_shell", "command": "cmd"},
            {"op": "mirror", "label": "mirror", "features": ["x"], "plane": {}},
        ):
            with self.assertRaises(ValueError):
                validate_operations([op])

    def test_invalid_sketch_references_and_expansion_collision(self):
        sketch = {
            "op": "sketch",
            "label": "profile",
            "entities": [{"type": "rectangle", "name": "box", "min": [0, 0], "max": [10, 10]}],
        }
        with self.assertRaises(ValueError):
            validate_operations(
                [
                    {
                        **sketch,
                        "dimensions": [
                            {
                                "name": "width",
                                "type": "length",
                                "value": 10,
                                "refs": [{"entity": "unknown"}],
                            }
                        ],
                    }
                ]
            )
        with self.assertRaises(ValueError):
            validate_operations(
                [
                    {
                        **sketch,
                        "entities": sketch["entities"]
                        + [{"type": "line", "name": "box_0", "start": [0, 0], "end": [1, 1]}],
                    }
                ]
            )

    def test_finite_values_and_plane_normals(self):
        for ref in (
            {"kind": "surface", "id": -1},
            {"kind": "datum_plane", "normal": [0, 0, 0]},
            {"kind": "datum_plane", "axis": "bad"},
        ):
            with self.assertRaises(ValueError):
                validate_operations([{"op": "datum_plane", "label": "plane", "reference": ref}])
        with self.assertRaises(ValueError):
            validate_operations(
                [
                    {
                        "op": "datum_plane",
                        "label": "plane",
                        "reference": {"kind": "datum_plane", "axis": "z"},
                        "offset": math.inf,
                    }
                ]
            )

    def test_feature_tree_rejects_ambiguous_values(self):
        with self.assertRaises(ValueError):
            validate_operations(
                [
                    {
                        "op": "feature_tree",
                        "label": "feature",
                        "tree": {"id": "PRO_E_FEATURE_TREE", "integer": 1, "double": 1},
                    }
                ]
            )
        tree = {"id": "PRO_E_FEATURE_TREE"}
        for _ in range(42):
            tree = {"id": "PRO_E_FEATURE_TREE", "children": [tree]}
        with self.assertRaises(ValueError):
            validate_operations([{"op": "feature_tree", "label": "feature", "tree": tree}])

    def test_relations_external_function_and_duplicate_labels(self):
        for line in ('SIZE = execute("x")', "SIZE = read_file(1)", "SIZE = 10\nSIZE=20"):
            with self.assertRaises(ValueError):
                validate_operations([{"op": "set_relations", "lines": [line]}])
        op = {
            "op": "datum_axis",
            "label": "axis",
            "references": [{"kind": "datum_plane", "axis": "x"}],
        }
        with self.assertRaises(ValueError):
            validate_operations([op, op])

    def test_supported_explicit_dimension_and_pattern(self):
        valid = validate_operations(
            [
                {
                    "op": "sketch",
                    "label": "profile",
                    "entities": [
                        {"type": "circle", "name": "circle", "center": [0, 0], "radius": 5}
                    ],
                    "dimensions": [
                        {
                            "name": "diameter",
                            "type": "diameter",
                            "value": 10,
                            "refs": [{"entity": "circle"}],
                        }
                    ],
                },
                {
                    "op": "dimension_pattern",
                    "label": "holes",
                    "feature": "hole",
                    "dimension_id": 5,
                    "count": 4,
                    "increment": -10,
                },
            ]
        )
        self.assertEqual(len(valid), 2)


if __name__ == "__main__":
    unittest.main()
