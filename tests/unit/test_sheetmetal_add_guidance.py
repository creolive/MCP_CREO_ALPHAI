"""Keep sheetmetal solid-add guidance aligned with the admission boundary."""

import unittest

from creo_mechdog.sheetmetal import solid_add_on_sheetmetal_problem


class SheetmetalAddGuidanceTest(unittest.TestCase):
    def test_blocked_add_explains_separate_body_and_unverified_paths(self) -> None:
        problem = solid_add_on_sheetmetal_problem(
            [{"op": "extrude", "label": "boss", "mode": "add"}]
        )
        self.assertIsNotNone(problem)
        assert problem is not None
        self.assertIn("SHEETMETAL_SOLID_ADD_UNSUPPORTED", problem)
        self.assertIn("new_body=true", problem)
        self.assertIn("not fused with the sheetmetal body", problem)
        self.assertIn("thin extrude add and revolve add are not blocked", problem)
        self.assertIn("not verified", problem)

    def test_existing_admission_boundaries_remain(self) -> None:
        allowed = (
            {"op": "extrude", "label": "cut", "mode": "cut"},
            {"op": "extrude", "label": "surface", "mode": "surface"},
            {"op": "extrude", "label": "thin", "mode": "add", "thin": 1.0},
            {"op": "extrude", "label": "separate", "mode": "add", "new_body": True},
            {"op": "revolve", "label": "turn", "mode": "add"},
        )
        for operation in allowed:
            with self.subTest(operation=operation):
                self.assertIsNone(solid_add_on_sheetmetal_problem([operation]))


if __name__ == "__main__":
    unittest.main()
