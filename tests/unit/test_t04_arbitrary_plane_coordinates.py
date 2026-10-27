"""FEAT-010 T04: coordinate dimensioning accepts any valid sketch plane."""

import unittest

import capabilities
import server
from creo_mechdog.schema import validate_operations

DICTIONARY_PLANE = {
    "reference": {"kind": "datum_plane", "id": 163},
    "origin": [10, 0, 0],
    "u_axis": [0, 0, 1],
}


def sketch(plane, dimensioning="coordinates", entities=None):
    return {
        "op": "sketch",
        "label": "profile",
        "plane": plane,
        "dimensioning": dimensioning,
        "entities": entities or [{"type": "circle", "name": "ring", "center": [0, 0], "radius": 2}],
    }


class ArbitraryPlaneCoordinateValidation(unittest.TestCase):
    def test_dictionary_plane_with_explicit_coordinates_passes_admission(self):
        for plane in (DICTIONARY_PLANE, {"reference": {"kind": "plane", "id": 11}}):
            with self.subTest(plane=plane):
                self.assertEqual(
                    validate_operations([sketch(plane)])[0]["dimensioning"],
                    "coordinates",
                )

    def test_dictionary_plane_auto_mode_still_routes_in_native(self):
        self.assertEqual(
            validate_operations([sketch(DICTIONARY_PLANE, dimensioning="auto")])[0]["dimensioning"],
            "auto",
        )

    def test_principal_plane_behavior_is_unchanged(self):
        for name in ("XY", "XZ", "YZ"):
            with self.subTest(plane=name):
                self.assertEqual(
                    validate_operations([sketch(name)])[0]["dimensioning"],
                    "coordinates",
                )

    def test_skew_centerline_and_supported_entities_still_admissible(self):
        entities = [
            {"type": "centerline", "name": "ax", "start": [-5, -5], "end": [5, 5]},
            {"type": "line", "name": "seg", "start": [0, 0], "end": [4, 0]},
        ]
        dumped = validate_operations([sketch(DICTIONARY_PLANE, entities=entities)])[0]
        self.assertEqual([e["type"] for e in dumped["entities"]], ["centerline", "line"])
        self.assertEqual(dumped["entities"][0]["name"], "ax")

    def test_entity_and_dimension_exclusions_apply_on_any_plane(self):
        for entities in (
            [{"type": "ellipse", "name": "e", "center": [0, 0], "x_radius": 2, "y_radius": 1}],
            [{"type": "spline", "name": "s", "points": [[0, 0], [1, 1]]}],
        ):
            with self.subTest(entities=entities):
                with self.assertRaisesRegex(ValueError, "Coordinate dimensioning supports"):
                    validate_operations([sketch(DICTIONARY_PLANE, entities=entities)])
        combined = sketch(DICTIONARY_PLANE)
        combined["dimensions"] = [
            {
                "name": "d",
                "type": "radius",
                "refs": [{"entity": "ring", "point": "whole"}],
                "value": 2,
            }
        ]
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            validate_operations([combined])

    def test_coordinate_edit_admission_keeps_working_without_a_plane_field(self):
        operations = [
            {
                "op": "update_sketch_geometry",
                "sketch": "s",
                "dimensioning": "coordinates",
                "entities": [
                    {"type": "rectangle", "name": "box", "min": [-50, -10], "max": [50, 10]}
                ],
            }
        ]
        self.assertEqual(validate_operations(operations)[0]["dimensioning"], "coordinates")


class CoordinateCapabilityText(unittest.IsolatedAsyncioTestCase):
    async def test_capability_summary_covers_any_valid_plane(self):
        summary = capabilities.families()["sketch_dimensioning"]
        self.assertIn("any valid sketch plane", summary["scope"])
        self.assertNotIn("arbitrary planes use autodim", summary["limits"])
        self.assertIn("dominant native section axis", summary["limits"])
        self.assertIn("infinite lines", summary["limits"])

    async def test_public_sketch_description_mentions_any_valid_plane(self):
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        self.assertIn("any valid sketch plane", tools["creo_create_sketch"].description)
        self.assertNotIn("principal-plane profiles", tools["creo_create_sketch"].description)
        self.assertIn("any valid sketch plane", tools["creo_update_sketch_geometry"].description)


if __name__ == "__main__":
    unittest.main()
