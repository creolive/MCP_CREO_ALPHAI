"""BUG-046 / DEV-051 T04: solid add into a sheetmetal body is refused at admission.

Live isolation on Creo 12.4.0.0 (2026-10-29) measured the boundary this rule
encodes: the same 10 x 10 x 5 solid add over the 1 mm sheet and far away from it
both returned ProFeatureWithoptionsCreate -1 with no element errors, the same
rectangle as a cut removed 100 mm3, and the same add with new_body=true
succeeded as a separate solid body. The plan is therefore rejected before a job
exists, with an identifiable code and the viable sheetmetal operations instead
of a bare native -1.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from creo_mechdog.sheetmetal import (
    SOLID_ADD_UNSUPPORTED,
    solid_add_on_sheetmetal_problem,
)
from generic_bridge import submit


def sketch() -> dict:
    return {
        "op": "sketch",
        "label": "box_sketch",
        "plane": "XY",
        "entities": [
            {"type": "rectangle", "name": "box", "min": [20.0, -30.0], "max": [30.0, -20.0]}
        ],
    }


def extrude(**overrides) -> dict:
    operation = {
        "op": "extrude",
        "label": "boss_add",
        "sketch": "box_sketch",
        "depth": 5.0,
        "mode": "add",
        "direction": "symmetric",
        "depth_type": "blind",
    }
    operation.update(overrides)
    return operation


class SolidAddOnSheetmetalTest(unittest.TestCase):
    def test_solid_add_is_refused_with_code_and_guidance(self) -> None:
        problem = solid_add_on_sheetmetal_problem([sketch(), extrude()])
        self.assertIsNotNone(problem)
        assert problem is not None
        self.assertIn(SOLID_ADD_UNSUPPORTED, problem)
        self.assertIn("sheetmetal_wall", problem)
        self.assertIn("sheetmetal_flange", problem)
        self.assertIn("new_body=true", problem)
        self.assertIn("boss_add", problem)
        self.assertIn("ProFeatureWithoptionsCreate", problem)
        # FEAT-014 H05 (Creo 12.4.0.0, 2026-11-07): the new_body escape hatch is a
        # separate body, not attached material - union into the sheetmetal body
        # returns -1 and the reverse union consumes the sheetmetal body.
        self.assertIn("union", problem)
        self.assertIn("Creo 10 is untested", problem)

    def test_cut_surface_thin_and_new_body_are_not_blocked(self) -> None:
        for operation in (
            extrude(mode="cut"),
            extrude(mode="surface"),
            extrude(thin=1.0),
            extrude(new_body=True),
        ):
            self.assertIsNone(
                solid_add_on_sheetmetal_problem([sketch(), operation]), operation["mode"]
            )

    def test_non_extrude_operations_are_outside_this_rule(self) -> None:
        self.assertIsNone(
            solid_add_on_sheetmetal_problem(
                [sketch(), {"op": "revolve", "label": "r", "mode": "add"}]
            )
        )


class SubmitAdmissionTest(unittest.TestCase):
    def test_sheetmetal_plan_rejected_before_a_job_exists(self) -> None:
        with (
            patch("generic_bridge.bridge.toolkit_lock"),
            patch("generic_bridge.bridge.job_path") as job_path,
        ):
            with self.assertRaisesRegex(ValueError, SOLID_ADD_UNSUPPORTED):
                submit([sketch(), extrude()], model_type="sheetmetal")
            job_path.assert_not_called()

    def test_part_plan_keeps_the_solid_add_path(self) -> None:
        # The same plan on a normal part must get past this rule; the template
        # check is the next admission step, so the error proves the rule did not fire.
        with (
            patch("generic_bridge.bridge.toolkit_lock"),
            patch("generic_bridge.bridge.config", return_value={"creo_root": "C:/Creo"}),
            patch("pathlib.Path.is_file", return_value=False),
        ):
            with self.assertRaisesRegex(ValueError, "Missing local model template"):
                submit([sketch(), extrude()], model_type="part")


if __name__ == "__main__":
    unittest.main()
