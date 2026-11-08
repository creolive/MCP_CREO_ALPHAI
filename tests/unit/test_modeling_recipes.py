"""DEV-078 offline recipe preparation; no native success is inferred."""

from __future__ import annotations

import unittest


class ModelingRecipeTests(unittest.TestCase):
    def test_single_hole_is_inside_the_documented_native_wall(self):
        from creo_mechdog.modeling_recipes import grille_cut_recipe
        from creo_mechdog.schema import validate_operations

        recipe = grille_cut_recipe()
        ops = validate_operations(recipe["operations"])
        self.assertEqual(recipe["preparation"]["arguments"]["template"], "native_planar")
        self.assertEqual(ops[0]["op"], "sheetmetal_planar_wall")
        self.assertEqual(ops[0]["origin"], [0.0, 0.0])
        self.assertEqual(ops[1]["offset"], 0.5)
        self.assertEqual(ops[2]["mode"], "cut")
        self.assertEqual(ops[2]["depth_type"], "through_all")
        self.assertEqual(recipe["oracle"]["expected_removed_volume_mm3"], 24.0)
        self.assertEqual(recipe["native_validation"], "not_run")

    def test_nine_rectangles_are_nonoverlapping_and_inside_the_wall(self):
        from creo_mechdog.modeling_recipes import grille_cut_recipe

        recipe = grille_cut_recipe(rows=3, columns=3)
        rectangles = recipe["operations"][1]["entities"]
        self.assertEqual(len(rectangles), 9)
        boxes = []
        for entity in rectangles:
            x0, y0 = entity["min"]
            x1, y1 = entity["max"]
            self.assertTrue(0 < x0 < x1 < 100)
            self.assertTrue(0 < y0 < y1 < 60)
            boxes.append((x0, y0, x1, y1))
        for i, (ax0, ay0, ax1, ay1) in enumerate(boxes):
            for bx0, by0, bx1, by1 in boxes[i + 1 :]:
                self.assertTrue(ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0)
        self.assertEqual(recipe["oracle"]["expected_removed_volume_mm3"], 216.0)

    def test_recipe_rejects_unbounded_or_coerced_grid_counts(self):
        from creo_mechdog.modeling_recipes import grille_cut_recipe

        for value in (True, 0, -1, 4, 1.0, "2", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                grille_cut_recipe(rows=value)

    def test_reference_routes_require_real_samples(self):
        from creo_mechdog.modeling_recipes import reference_route

        for route in ("standard_quilt_offset", "punch_die_form"):
            recipe = reference_route(route)
            self.assertEqual(recipe["status"], "pending_reference")
            self.assertEqual(recipe["operations"], [])
            self.assertEqual(recipe["native_validation"], "not_run")
            self.assertTrue(recipe["acceptance"])
        with self.assertRaises(ValueError):
            reference_route("copy_translate")

    def test_udf_preparation_keeps_exact_prompt_names_and_does_not_claim_success(self):
        from creo_mechdog.modeling_recipes import udf_placement_recipe

        recipe = udf_placement_recipe(
            "standard_quilt_offset",
            file_path="E:/Samples/offset.gph",
            references={"Source quilt": {"kind": "quilt", "id": 82}},
            dimensions={"OFFSET": 2.0},
        )
        self.assertEqual(recipe["operations"][0]["op"], "udf_create")
        self.assertIn("Source quilt", recipe["operations"][0]["references"])
        self.assertEqual(recipe["status"], "static_only")
        self.assertEqual(recipe["native_validation"], "not_run")
        self.assertEqual(recipe["prerequisites"][0]["tool"], "creo_inspect_udf")

    def test_udf_preparation_rejects_nonlocal_paths_and_invalid_values(self):
        from creo_mechdog.modeling_recipes import udf_placement_recipe

        kwargs = dict(
            file_path="E:/Samples/offset.gph",
            references={"Source": {"kind": "quilt", "id": 82}},
            dimensions={"OFFSET": 2.0},
        )
        for patch in (
            {"file_path": "relative.gph"},
            {"file_path": "https://example.com/offset.gph"},
            {"file_path": "E:/Samples/not_a_udf.prt"},
            {"references": {"Source": {"kind": "quilt", "id": True}}},
            {"references": {"Source": {"kind": "datum_csys", "label": "place"}}},
            {"references": {"Source": {"kind": "datum_plane", "label": "top"}}},
            {"dimensions": {"OFFSET": True}},
            {"dimensions": {"OFFSET": float("nan")}},
            {"dimensions": {"OFFSET": 10**400}},
        ):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                udf_placement_recipe("standard_quilt_offset", **(kwargs | patch))

    def test_udf_feature_references_match_native_resolver_names(self):
        from creo_mechdog.modeling_recipes import udf_placement_recipe

        for reference in (
            {"kind": "datum_feature", "label": "plane_a"},
            {"kind": "datum_csys_feature", "label": "placement"},
            {"kind": "datum_plane", "id": 15},
            {"kind": "default_csys"},
        ):
            with self.subTest(reference=reference):
                recipe = udf_placement_recipe(
                    "punch_die_form",
                    file_path="E:/Samples/form.gph",
                    references={"Tool placement": reference},
                    dimensions={},
                )
                self.assertEqual(recipe["operations"][0]["references"]["Tool placement"], reference)

    def test_recipes_return_independent_data(self):
        from creo_mechdog.modeling_recipes import reference_route

        first = reference_route("standard_quilt_offset")
        first["acceptance"].clear()
        self.assertTrue(reference_route("standard_quilt_offset")["acceptance"])


if __name__ == "__main__":
    unittest.main()
