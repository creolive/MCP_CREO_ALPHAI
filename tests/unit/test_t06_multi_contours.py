"""DEV-047 T06 multi-contour admission, projection and diagnostics."""

import math
import unittest

import bridge
from creo_mechdog import operation_results
from creo_mechdog.profile_diagnostics import analyze_profile, validate_solid_profile
from creo_mechdog.schema import validate_operations
from tools import t06_fixtures as fixtures


def plan(entities, dimensioning="coordinates", **extrude):
    return [
        {"op": "sketch", "label": "profile", "entities": entities, "dimensioning": dimensioning},
        {
            "op": "extrude",
            "label": "solid",
            "sketch": "profile",
            "depth": fixtures.DEPTH_MM,
            **extrude,
        },
    ]


class LegalMultiContourAdmission(unittest.TestCase):
    def test_two_five_ten_circles_and_arc_rings_pass_admission(self):
        for case in fixtures.legal_cases():
            with self.subTest(case=case["name"]):
                operations = validate_operations(plan(case["entities"]))
                self.assertEqual(len(operations), 2)
                self.assertEqual(operations[1]["op"], "extrude")

    def test_diagnostics_count_contours_entities_and_analytic_area(self):
        for case in fixtures.legal_cases():
            with self.subTest(case=case["name"]):
                report = analyze_profile(case["entities"])
                self.assertEqual(report["analysis"], "complete")
                self.assertEqual(report["contour_count"], case["expected_contour_count"])
                self.assertEqual(report["closed_contour_count"], case["expected_contour_count"])
                self.assertEqual(report["open_contour_count"], 0)
                self.assertEqual(report["entity_count"], case["expected_entity_count"])
                self.assertAlmostEqual(
                    report["material_area_mm2"], case["expected_area_mm2"], places=9
                )
                self.assertEqual(report["categories"]["intersecting"]["count"], 0)
                self.assertEqual(report["categories"]["self_intersecting"]["count"], 0)
                self.assertEqual(report["categories"]["zero_area"]["count"], 0)
                self.assertEqual(report["categories"]["near_tolerance"]["count"], 0)

    def test_two_circles_plus_five_four_arc_rings_is_not_special_cased(self):
        case = fixtures.mixed()
        report = analyze_profile(case["entities"])
        self.assertEqual((report["closed_contour_count"], report["entity_count"]), (7, 22))
        self.assertAlmostEqual(report["material_area_mm2"], 7 * math.pi * 3**2, places=9)

    def test_ten_arc_rings_are_admitted_without_a_two_loop_limit(self):
        case = fixtures.separated(10, "arc_ring")
        validate_operations(plan(case["entities"]))
        report = analyze_profile(case["entities"])
        self.assertEqual((report["closed_contour_count"], report["entity_count"]), (10, 40))
        self.assertAlmostEqual(report["material_area_mm2"], 10 * math.pi * 3**2, places=9)

    def test_nested_loops_are_legal_and_subtract_the_hole_area(self):
        case = fixtures.nested()
        validate_operations(plan(case["entities"]))
        report = analyze_profile(case["entities"])
        depths = [contour["nesting_depth"] for contour in report["contours"]]
        self.assertEqual(depths, [0, 1])
        self.assertAlmostEqual(report["material_area_mm2"], math.pi * (100 - 16), places=9)


class InvalidProfileAdmission(unittest.TestCase):
    def test_each_confirmed_invalid_category_is_rejected_separately(self):
        for name, factory in fixtures.INVALID.items():
            with self.subTest(category=name):
                entities = factory()
                report = analyze_profile(entities)
                self.assertGreater(report["categories"][name]["count"], 0)
                with self.assertRaisesRegex(ValueError, name):
                    validate_operations(plan(entities))

    def test_rejection_reports_contour_entity_counts_and_position(self):
        with self.assertRaises(ValueError) as caught:
            validate_solid_profile(fixtures.intersecting(), "coordinates")
        message = str(caught.exception)
        self.assertIn("detected 2 closed contour(s)", message)
        self.assertIn("2 curve entities", message)
        self.assertIn("[intersecting]", message)
        self.assertIn("mm", message)

    def test_near_tolerance_is_fatal_only_for_explicit_coordinates(self):
        entities = fixtures.near_tolerance()
        report = analyze_profile(entities)
        self.assertEqual(report["categories"]["near_tolerance"]["count"], 1)
        self.assertGreater(report["categories"]["near_tolerance"]["items"][0]["gap_mm"], 0)
        validate_solid_profile(entities, "autodim")
        with self.assertRaisesRegex(ValueError, "near_tolerance"):
            validate_solid_profile(entities, "coordinates")

    def test_open_sketch_is_legal_but_not_a_solid_profile(self):
        entities = fixtures.open_chain()
        validate_operations([{"op": "sketch", "label": "path", "entities": entities}])
        with self.assertRaisesRegex(ValueError, "open"):
            validate_operations(plan(entities))
        validate_operations(plan(entities, thin=0.5))

    def test_centerline_only_sketch_cannot_be_a_solid_profile(self):
        entities = [
            {"type": "centerline", "name": "axis", "start": [0, 0], "end": [20, 0]},
        ]
        with self.assertRaisesRegex(ValueError, "no_closed_contour"):
            validate_operations(plan(entities))

    def test_surface_and_existing_sketch_references_keep_native_authority(self):
        entities = fixtures.open_chain()
        validate_operations(plan(entities, mode="surface"))
        validate_operations(
            [
                {
                    "op": "extrude",
                    "label": "solid",
                    "sketch": "earlier",
                    "depth": 4,
                }
            ]
        )

    def test_unsupported_entities_disable_the_static_verdict(self):
        entities = [
            {"type": "ellipse", "name": "oval", "center": [0, 0], "x_radius": 5, "y_radius": 3}
        ]
        report = validate_solid_profile(entities, "autodim")
        self.assertEqual(report["analysis"], "partial")
        self.assertEqual(report["categories"]["unsupported"]["count"], 1)
        validate_operations(plan(entities, dimensioning="autodim"))


class ResultProjection(unittest.TestCase):
    def test_sketch_result_carries_input_report_and_native_section(self):
        case = fixtures.mixed()
        inputs = plan(case["entities"])
        native_section = {
            "available": True,
            "closed_contours": 7,
            "contours": 7,
            "entities": 22,
            "open_ends": 0,
        }
        result = {
            "success": True,
            "operations": [
                {
                    "op": "sketch",
                    "index": 0,
                    "label": "profile",
                    "succeeded": True,
                    "native_section": native_section,
                },
                {"op": "extrude", "index": 1, "label": "solid", "succeeded": True},
            ],
        }
        annotated = operation_results.annotate_native_result(result, readonly=False, inputs=inputs)
        profile = annotated["operations"][0]["profile"]
        self.assertEqual(profile["source"], "input")
        self.assertEqual(profile["closed_contour_count"], 7)
        self.assertEqual(profile["entity_count"], 22)
        self.assertAlmostEqual(profile["material_area_mm2"], case["expected_area_mm2"], places=9)
        self.assertEqual(annotated["operations"][0]["native_section"], native_section)
        compact = bridge.compact_job({"result": annotated})
        projected = compact["result"]["operations"][0]
        self.assertEqual(projected["profile"], profile)
        self.assertEqual(projected["native_section"], native_section)
        self.assertNotIn("profile", compact["result"]["operations"][1])

    def test_missing_inputs_keep_legacy_results_unchanged(self):
        result = {"success": True, "operations": [{"op": "sketch", "succeeded": True}]}
        annotated = operation_results.annotate_native_result(result, readonly=False)
        self.assertNotIn("profile", annotated["operations"][0])

    def test_profile_follows_the_sketch_label_not_the_result_position(self):
        inputs = [
            {
                "op": "sketch",
                "label": "first",
                "entities": fixtures.separated(2, "circle")["entities"],
            },
            {
                "op": "sketch",
                "label": "second",
                "entities": fixtures.separated(5, "circle")["entities"],
            },
        ]
        result = {
            "success": True,
            "operations": [{"op": "sketch", "index": 0, "label": "second", "succeeded": True}],
        }
        annotated = operation_results.annotate_native_result(result, readonly=False, inputs=inputs)
        self.assertEqual(annotated["operations"][0]["profile"]["closed_contour_count"], 5)


if __name__ == "__main__":
    unittest.main()
