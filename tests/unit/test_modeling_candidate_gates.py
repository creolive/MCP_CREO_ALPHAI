"""DEV-078 candidates are schema-valid but cannot submit native jobs."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch


def candidate_operations():
    return [
        {
            "op": "sheetmetal_corner_relief",
            "label": "corner_candidate",
            "flat": {"kind": "surface", "id": 12},
            "bends": [{"kind": "surface", "id": 20}, {"kind": "surface", "id": 21}],
            "width": 1.0,
            "depth": 1.0,
        },
        {
            "op": "sheetmetal_quilt_form",
            "label": "form_candidate",
            "quilt": {"kind": "quilt", "id": 82},
        },
        {
            "op": "sheetmetal_flange_profile",
            "label": "profile_candidate",
            "edge": {"kind": "edge", "id": 31},
            "profile": {
                "entities": [
                    {"type": "line", "name": "leg1", "start": [0, 0], "end": [10, 0]},
                    {"type": "line", "name": "leg2", "start": [10, 0], "end": [10, 5]},
                ]
            },
        },
    ]


class ModelingCandidateGateTests(unittest.TestCase):
    def test_candidates_validate_but_are_all_unavailable(self):
        from creo_mechdog.capabilities import REGISTERED_OPERATIONS, require_available
        from creo_mechdog.schema import validate_operations

        for op in candidate_operations():
            with self.subTest(op=op["op"]):
                normalized = validate_operations([op])
                self.assertIn(op["op"], REGISTERED_OPERATIONS)
                with self.assertRaisesRegex(ValueError, "no native job was queued"):
                    require_available(normalized)

    def test_plan_gate_rejects_before_creo_or_registry_work(self):
        import generic_bridge

        for op in candidate_operations():
            with self.subTest(op=op["op"]), patch("bridge.toolkit_lock") as channel:
                with self.assertRaises(ValueError):
                    generic_bridge.submit([op])
                channel.assert_not_called()

    def test_candidates_have_no_public_tools(self):
        import server

        names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
        self.assertEqual(len(names), 107)
        for op in candidate_operations():
            self.assertNotIn("creo_" + op["op"], names)

    def test_profile_cannot_enter_old_flange_or_override_height_angle(self):
        from creo_mechdog.schema import validate_operations

        profile = candidate_operations()[2]
        for extra in ({"height": 10}, {"angle": 90}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_operations([profile | extra])
        with self.assertRaises(ValueError):
            validate_operations([profile | {"op": "sheetmetal_flange", "height": 10}])

    def test_profile_reuses_strict_edge_and_scalar_admission(self):
        from creo_mechdog.schema import validate_operations

        for extra in (
            {"edge": {"kind": "edge", "id": True}},
            {"radius": True},
            {"radius": 10**400},
            {"y_factor": float("nan")},
            {"end_trim_mm": True},
            {"flip": 1},
            {"miter_cuts": {"width": True}},
            {"relief": {"type": "rectangular", "width": 1, "depth": True}},
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_operations([candidate_operations()[2] | extra])


if __name__ == "__main__":
    unittest.main()
