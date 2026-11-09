"""DEV-081 / F02: exact-arc closed contours must not be rejected by near_tolerance."""

from __future__ import annotations

import copy
import unittest

from creo_mechdog.profile_diagnostics import validate_solid_profile
from creo_mechdog.schema import validate_operations

DECK_ENTITIES = [
    {"type": "line", "name": "a", "start": [0, 680], "end": [0, -680]},
    {"type": "line", "name": "b", "start": [0, -680], "end": [6830, -690]},
    {
        "type": "arc",
        "name": "d4",
        "center": [6830, 917.6086957],
        "radius": 1607.6086957,
        "start_angle": 270,
        "end_angle": 325.194591737,
    },
    {
        "type": "arc",
        "name": "d5",
        "center": [6830, -917.6086957],
        "radius": 1607.6086957,
        "start_angle": 34.805408263,
        "end_angle": 90,
    },
    {"type": "line", "name": "c", "start": [6830, 690], "end": [0, 680]},
]


def _opened_deck() -> list[dict]:
    entities = copy.deepcopy(DECK_ENTITIES)
    for entity in entities:
        if entity["name"] == "d5":
            entity["start_angle"] = 34.9
    return entities


def _plan(entities: list[dict]) -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "deck",
            "plane": "XY",
            "offset": 0,
            "dimensioning": "coordinates",
            "endpoint_policy": "weld",
            "entities": entities,
        },
        {
            "op": "extrude",
            "label": "hull",
            "sketch": "deck",
            "mode": "add",
            "direction": "negative",
            "depth": 660,
        },
    ]


GAPPED_SQUARE = [
    {"type": "line", "name": "g0", "start": [0, 0], "end": [10, 0]},
    {"type": "line", "name": "g1", "start": [10, 0], "end": [10, 10]},
    {"type": "line", "name": "g2", "start": [10, 10], "end": [0, 10]},
    {"type": "line", "name": "g3", "start": [0, 10], "end": [0, 5e-7]},
]


class ExactArcClosureTests(unittest.TestCase):
    def test_coordinate_deck_arc_closure_is_accepted(self):
        report = validate_solid_profile(DECK_ENTITIES, "coordinates")
        self.assertEqual(report["closed_contour_count"], 1)
        self.assertEqual(report["open_contour_count"], 0)

    def test_plan_validation_accepts_deck_with_weld_policy(self):
        self.assertEqual(len(validate_operations(_plan(DECK_ENTITIES))), 2)

    def test_open_near_tolerance_profile_still_rejected(self):
        with self.assertRaises(ValueError) as caught:
            validate_solid_profile(_opened_deck(), "coordinates")
        self.assertIn("open", str(caught.exception))

    def test_rejection_text_names_remediation(self):
        with self.assertRaises(ValueError) as caught:
            validate_solid_profile(_opened_deck(), "coordinates")
        text = str(caught.exception)
        for term in ("closure_tolerance_mm", "polyline", "snap_endpoints"):
            self.assertIn(term, text)

    def test_explicit_closure_tolerance_still_controls_near_tolerance(self):
        with self.assertRaises(ValueError):
            validate_solid_profile(_opened_deck(), "coordinates", tolerance=1e-6)

    def test_weld_policy_order_is_stated_in_error(self):
        with self.assertRaises(ValueError) as caught:
            validate_solid_profile(_opened_deck(), "coordinates")
        self.assertIn("submission", str(caught.exception))

    def test_larger_near_tolerance_gap_still_rejected(self):
        with self.assertRaisesRegex(ValueError, "near_tolerance"):
            validate_solid_profile(GAPPED_SQUARE, "coordinates")


if __name__ == "__main__":
    unittest.main()
