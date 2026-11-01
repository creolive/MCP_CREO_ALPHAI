"""Offline guards for tools/test_flange_direction.py (DEV-051 T05/T11).

The driver answers two questions - does a flange become a 90 degree bend, and does the
direction option really pick the side - and the judgement must stay bbox-only, because
232 x 80 x 1 = 18 560 mm3 is the same volume for a real bend and for the coplanar
extension the 2026-10-29 third round produced.
"""

from __future__ import annotations

import unittest

from tools import test_flange_direction as probe

PLATE = ((0.0, 0.0, 0.0), (185.0, 232.0, 1.0))


class NativeSectionTest(unittest.TestCase):
    def test_section_matches_the_stock_shape_structure(self) -> None:
        section = probe.native_section()
        self.assertTrue(section["leg_on_sketch_normal"])
        self.assertTrue(section["centerline_removed"])
        self.assertEqual(section["profile_entity_count"], 1)
        self.assertTrue(section["height_type_none"])

    def test_direction_switch_is_the_section_side(self) -> None:
        section = probe.native_section()
        self.assertTrue(section["section_side_flip_is_the_switch"])
        self.assertTrue(section["traj_normal_not_the_switch"])


class VerdictTest(unittest.TestCase):
    def test_z_growth_of_the_full_height_is_a_bend(self) -> None:
        judged = probe.verdict(PLATE, ((0.0, 0.0, 0.0), (187.54, 232.0, 81.0)), 80.0, "up")
        self.assertTrue(judged["bent"])
        self.assertEqual(judged["direction"], "up")
        self.assertTrue(judged["direction_matches"])

    def test_coplanar_extension_is_not_a_bend(self) -> None:
        judged = probe.verdict(PLATE, ((0.0, 0.0, 0.0), (265.0, 232.0, 1.0)), 80.0, "up")
        self.assertFalse(judged["bent"])
        self.assertEqual(judged["direction"], "in_plane")

    def test_downward_flange_is_a_bend_on_the_other_side(self) -> None:
        judged = probe.verdict(PLATE, ((0.0, 0.0, -81.0), (187.54, 232.0, 1.0)), 80.0, "down")
        self.assertTrue(judged["bent"])
        self.assertEqual(judged["direction"], "down")
        self.assertTrue(judged["direction_matches"])

    def test_a_side_that_did_not_change_fails_the_expectation(self) -> None:
        """The pre-fix defect: both flip values produced the same downward wall."""
        judged = probe.verdict(PLATE, ((0.0, 0.0, -81.0), (187.54, 232.0, 1.0)), 80.0, "up")
        self.assertTrue(judged["bent"])
        self.assertFalse(judged["direction_matches"])


class PlanTest(unittest.TestCase):
    def test_one_variable_per_case_with_an_explicit_side(self) -> None:
        cases = probe.plan()
        self.assertEqual([case["flip"] for case in cases], [False, True])
        self.assertEqual([case["expected_direction"] for case in cases], ["up", "down"])
        self.assertEqual(len({case["case"] for case in cases}), len(cases))

    def test_hang_budget_is_three_minutes(self) -> None:
        self.assertEqual(probe.HANG_BUDGET_SECONDS, 180.0)


class PendingValidationDesignTest(unittest.TestCase):
    """DEV-053 P08: the frozen live design awaiting the orchestrator's window."""

    def test_free_end_first_flange_covers_flip_in_both_directions(self) -> None:
        design = probe.FREE_END_FLANGE_DESIGN
        self.assertEqual(len(design["cases"]), 2)
        self.assertEqual([case["flip"] for case in design["cases"]], [False, True])
        self.assertIn("bbox-only", design["oracle"])
        self.assertIn("free", design["fixture"])

    def test_fixed_surface_design_covers_the_unbend_family_and_rejects(self) -> None:
        design = probe.FIXED_SURFACE_DESIGN
        ops = {case["op"] for case in design["cases"]}
        self.assertEqual(
            ops, {"sheetmetal_unbend", "sheetmetal_bend_back", "sheetmetal_flat_pattern"}
        )
        self.assertIn("{kind:'surface',id:N}", design["reference_contract"])
        controls = {control["name"] for control in design["negative_controls"]}
        self.assertIn("fixed_surface_datum_plane", controls)
        self.assertIn("fixed_surface_stale_edge_id", controls)
        for control in design["negative_controls"]:
            self.assertIn("reject", control["expect"])

    def test_candidate_edge_pass_never_unlocks_the_adjacent_bend_boundary(self) -> None:
        design = probe.CANDIDATE_EDGE_DESIGN
        joined = " ".join(design["acceptance"])
        self.assertIn("adjacent_bend_ends", joined)
        self.assertIn("never unlocks", joined)
        self.assertIn("creates no flange", joined)
        self.assertIn("BY GEOMETRY", design["procedure"])

    def test_pending_bundle_marks_everything_not_executed_offline(self) -> None:
        pending = probe.pending_validation()
        self.assertIn("free_end_first_flange", pending)
        self.assertIn("fixed_surface_unbend_family", pending)
        self.assertIn("candidate_edge_discovery", pending)
        self.assertIn("not_executed", pending)
        report = probe.offline_report(None)
        self.assertIn("pending_live_validation", report)
        self.assertIn("no Creo connection", report["not_executed"])


if __name__ == "__main__":
    unittest.main()
