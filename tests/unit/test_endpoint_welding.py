"""FEAT-039/W01: the endpoint weld contract, policy layer.

The fixtures are open chains whose two free ends sit within the closure
diagnostic scale (1e-4 mm), because that is the shape a weld would close. Two
closed contours stay separate chains, so a pair between them is refused
instead of bridging two rings.
"""

import unittest

from creo_mechdog.endpoint_welding import (
    CLUSTER_TOLERANCE_MM,
    POLICIES,
    prepare_endpoint_weld,
    prepare_operations,
)
from creo_mechdog.schema import validate_operations

GAP = 5e-7


def open_chain(gap: float = GAP) -> list[dict]:
    """Four lines forming a rectangle whose last end misses the first by gap."""
    return [
        {"type": "line", "name": "l1", "start": [0.0, 0.0], "end": [10.0, 0.0]},
        {"type": "line", "name": "l2", "start": [10.0, 0.0], "end": [10.0, 10.0]},
        {"type": "line", "name": "l3", "start": [10.0, 10.0], "end": [0.0, 10.0]},
        {"type": "line", "name": "l4", "start": [0.0, 10.0], "end": [0.0, gap]},
    ]


def two_rings() -> list[dict]:
    """Two closed rectangles; the last line of each stops just short of its start."""
    return [
        {"type": "line", "name": "a1", "start": [0.0, 0.0], "end": [10.0, 0.0]},
        {"type": "line", "name": "a2", "start": [10.0, 0.0], "end": [10.0, 10.0]},
        {"type": "line", "name": "a3", "start": [10.0, 10.0], "end": [0.0, 10.0]},
        {"type": "line", "name": "a4", "start": [0.0, 10.0], "end": [0.0, GAP]},
        {"type": "line", "name": "b1", "start": [20.0, 0.0], "end": [30.0, 0.0]},
        {"type": "line", "name": "b2", "start": [30.0, 0.0], "end": [30.0, 10.0]},
        {"type": "line", "name": "b3", "start": [30.0, 10.0], "end": [20.0, 10.0]},
        {"type": "line", "name": "b4", "start": [20.0, 10.0], "end": [20.0, GAP]},
    ]


class EndpointWeldPairingTests(unittest.TestCase):
    def test_weld_pairs_are_unique(self):
        receipt = prepare_endpoint_weld(open_chain())
        self.assertEqual(receipt["candidate_pairs"], 1)
        self.assertEqual(receipt["accepted_pairs"], 1)
        self.assertEqual(receipt["refused_pairs"], 0)
        # One endpoint may only be welded once, so no endpoint is listed twice.
        keys = [
            (pair["curve_a"], pair["end_a"], pair["curve_b"], pair["end_b"])
            for pair in receipt["pairs"]
        ]
        self.assertEqual(len(keys), len(set(keys)))

    def test_weld_does_not_bridge_separate_loops(self):
        receipt = prepare_endpoint_weld(two_rings())
        # Each ring closes on its own chain; the two rings are never joined.
        self.assertEqual(receipt["accepted_pairs"], 2)
        for pair in receipt["pairs"]:
            # A pair never joins the two rings: both curves are in the same one.
            self.assertEqual(pair["curve_a"] > 3, pair["curve_b"] > 3)

    def test_weld_preserves_arc_consistency(self):
        consistent = [
            {
                "type": "arc",
                "name": "a1",
                "center": [0.0, 0.0],
                "radius": 5.0,
                "start_angle": 0.0,
                "end_angle": 90.0,
            },
            {
                "type": "arc",
                "name": "a2",
                "center": [0.0, 0.0],
                "radius": 5.0,
                "start_angle": 90.0,
                "end_angle": 180.0,
            },
            {
                "type": "arc",
                "name": "a3",
                "center": [0.0, 0.0],
                "radius": 5.0,
                "start_angle": 180.0,
                "end_angle": 359.9999,
            },
        ]
        receipt = prepare_endpoint_weld(consistent)
        self.assertEqual(receipt["accepted_pairs"], 1)
        # The two arcs meet within the cluster scale but live on different
        # circles, so the pair is refused instead of welding two geometries.
        inconsistent = [
            {
                "type": "arc",
                "name": "b1",
                "center": [0.0, 0.0],
                "radius": 5.0,
                "start_angle": 0.0,
                "end_angle": 90.0,
            },
            {
                "type": "arc",
                "name": "b2",
                "center": [-5.5, 5.0 + 1e-7],
                "radius": 5.5,
                "start_angle": 0.0,
                "end_angle": 90.0,
            },
        ]
        refused = prepare_endpoint_weld(inconsistent)
        # Two arcs on different circles are never welded: the pair is refused
        # (the arcs are not one chain) instead of being merged.
        self.assertEqual(refused["accepted_pairs"], 0)
        self.assertEqual(refused["welded_pairs"], 0)

    def test_weld_maximum_displacement_is_bounded(self):
        gap = 8e-5
        entities = [
            {"type": "line", "name": "l1", "start": [0.0, 0.0], "end": [10.0, 0.0]},
            {"type": "line", "name": "l2", "start": [10.0, 0.0], "end": [10.0, 10.0]},
            {"type": "line", "name": "l3", "start": [10.0, 10.0], "end": [0.0, 10.0]},
            {"type": "line", "name": "l4", "start": [0.0, 10.0], "end": [0.0, gap]},
        ]
        allowed = prepare_endpoint_weld(entities, max_move_mm=gap / 2.0)
        self.assertEqual(allowed["accepted_pairs"], 1)
        bounded = prepare_endpoint_weld(entities, max_move_mm=gap / 10.0)
        self.assertEqual(bounded["accepted_pairs"], 0)
        self.assertTrue(any(entry["reason"] == "max_move_exceeded" for entry in bounded["refused"]))
        self.assertLessEqual(allowed["max_move_mm"], gap / 2.0)

    def test_weld_report_mode_keeps_requested_geometry(self):
        entities = open_chain()
        receipt = prepare_endpoint_weld(entities, policy="report")
        self.assertFalse(receipt["applied"])
        self.assertFalse(receipt["native_applied"])
        self.assertEqual(receipt["welded_pairs"], 0)
        self.assertIsNone(receipt["actual_geometry"])
        self.assertEqual(receipt["requested_geometry"]["entity_count"], len(entities))
        # The policy layer never rewrites the caller's geometry.
        operations = [
            {
                "op": "sketch",
                "label": "s1",
                "entities": entities,
                "endpoint_policy": "report",
            }
        ]
        self.assertEqual(prepare_operations(operations), operations)

    def test_reject_reports_endpoint_pairs(self):
        operations = [
            {
                "op": "sketch",
                "label": "s1",
                "entities": open_chain(),
                "endpoint_policy": "reject",
            }
        ]
        with self.assertRaises(ValueError) as caught:
            prepare_operations(operations)
        self.assertIn("endpoint policy reject", str(caught.exception))
        self.assertIn("weldable endpoint pair", str(caught.exception))


class EndpointWeldContractTests(unittest.TestCase):
    def test_weld_create_and_update_share_policy(self):
        create = validate_operations(
            [
                {
                    "op": "sketch",
                    "label": "s1",
                    "entities": [{"type": "line", "name": "l1", "start": [0, 0], "end": [1, 0]}],
                    "endpoint_policy": "report",
                }
            ]
        )[0]
        update = validate_operations(
            [
                {
                    "op": "update_sketch_geometry",
                    "sketch": "s1",
                    "entities": [{"type": "line", "name": "l1", "start": [0, 0], "end": [1, 0]}],
                    "endpoint_policy": "report",
                }
            ]
        )[0]
        self.assertEqual(create["endpoint_policy"], "report")
        self.assertEqual(update["endpoint_policy"], "report")
        self.assertIsNone(create.get("max_endpoint_move_mm"))
        self.assertIsNone(update.get("max_endpoint_move_mm"))

    def test_weld_policy_needs_an_explicit_bound(self):
        """The weld needs max_endpoint_move_mm: the bound is the control."""
        from creo_mechdog.capabilities import require_available

        with self.assertRaises(ValueError) as caught:
            require_available(
                [
                    {
                        "op": "sketch",
                        "label": "s1",
                        "entities": [
                            {"type": "line", "name": "l1", "start": [0, 0], "end": [1, 0]}
                        ],
                        "endpoint_policy": "weld",
                    }
                ]
            )
        self.assertIn("max_endpoint_move_mm", str(caught.exception))

    def test_weld_policy_is_accepted_with_a_bound(self):
        from creo_mechdog.capabilities import require_available

        require_available(
            [
                {
                    "op": "sketch",
                    "label": "s1",
                    "entities": [{"type": "line", "name": "l1", "start": [0, 0], "end": [1, 0]}],
                    "endpoint_policy": "weld",
                    "max_endpoint_move_mm": 0.001,
                }
            ]
        )

    def test_the_policy_layer_publishes_the_weld_plan(self):
        """The native side regularises exactly the pairs the policy accepted."""
        from creo_mechdog.endpoint_welding import prepare_operations

        operations = prepare_operations(
            [
                {
                    "op": "sketch",
                    "label": "s1",
                    "entities": [
                        {"type": "line", "name": "l1", "start": [0, 0], "end": [10, 0]},
                        {"type": "line", "name": "l2", "start": [10.00005, 0], "end": [10, 10]},
                        {"type": "line", "name": "l3", "start": [10, 10], "end": [0, 10]},
                        {"type": "line", "name": "l4", "start": [0, 10], "end": [0, 0]},
                    ],
                    "endpoint_policy": "weld",
                    "max_endpoint_move_mm": 0.001,
                }
            ]
        )
        plan = operations[0]["weld_pairs"]
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["a"]["entity"], "l1")
        self.assertEqual(plan[0]["a"]["point"], "end")
        self.assertEqual(plan[0]["b"]["entity"], "l2")
        self.assertEqual(plan[0]["b"]["point"], "start")
        self.assertLessEqual(plan[0]["required_move_mm"], 0.001)

    def test_unknown_policy_is_refused(self):
        from creo_mechdog.schema import validate_operations

        with self.assertRaises(ValueError):
            validate_operations(
                [
                    {
                        "op": "sketch",
                        "label": "s1",
                        "entities": [
                            {"type": "line", "name": "l1", "start": [0, 0], "end": [1, 0]}
                        ],
                        "endpoint_policy": "snap",
                    }
                ]
            )

    def test_the_two_scales_stay_apart(self):
        receipt = prepare_endpoint_weld(open_chain())
        self.assertEqual(receipt["threshold_mm"], CLUSTER_TOLERANCE_MM)
        self.assertEqual(receipt["threshold_source"], "closure_diagnostic_cluster")
        self.assertLess(receipt["kernel_weld_bound_mm"], receipt["threshold_mm"])
        self.assertIn("EXACT_TOLERANCE_MM", receipt["kernel_weld_bound_source"])
        self.assertEqual(set(POLICIES), {"report", "reject", "weld"})


if __name__ == "__main__":
    unittest.main()
