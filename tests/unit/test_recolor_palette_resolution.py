"""FEAT-056: palette keys by part label and deterministic random palettes.

Registry-only unit tests: no Toolkit connection, no job execution for previews.
Random palettes are generated from the resolved family set so the same family
set always yields the same colors; executions record the resolved explicit
palette so a replay never depends on the generator.
"""

import unittest
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import appearance
from creo_mechdog.schema import validate_operations
from tests.unit.test_assembly_appearance import (
    SRC_A,
    SRC_B,
    AppearanceFixture,
)

AUTO_KEY_A = SRC_A
AUTO_KEY_B = SRC_B


class PaletteResolutionContract(AppearanceFixture):
    def test_label_keys_resolve_to_the_unique_source_family(self):
        self.write_model()
        page = appearance.preview_recolor(
            self.model_id,
            3,
            palette={"gear_a": [0.1, 0.2, 0.3], "shaft_main": [0.4, 0.5, 0.6]},
        )
        self.assertEqual(page["palette_source"], "family_label")
        self.assertEqual(sorted(page["palette"]), sorted([AUTO_KEY_A, AUTO_KEY_B]))
        self.assertEqual(page["family_counts"], {AUTO_KEY_A: 2, AUTO_KEY_B: 1})
        reds = {row["family"]: row["rgb"] for row in page["groups"]}
        self.assertEqual(reds[AUTO_KEY_A], [0.1, 0.2, 0.3])
        self.assertEqual(reds[AUTO_KEY_B], [0.4, 0.5, 0.6])

    def test_ambiguous_label_is_refused_with_the_conflicting_sources(self):
        with self.assertRaises(ValueError) as caught:
            appearance.resolve_auto_palette(
                {"dup_label": [0.1, 0.2, 0.3]},
                [AUTO_KEY_A, AUTO_KEY_B],
                {"dup_label": {AUTO_KEY_A, AUTO_KEY_B}},
            )
        message = str(caught.exception)
        self.assertIn("dup_label", message)
        self.assertIn(AUTO_KEY_A, message)
        self.assertIn(AUTO_KEY_B, message)

    def test_unknown_key_still_refuses(self):
        self.write_model()
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3, palette={"no_such_part": [0, 0, 0]})
        self.assertIn("do not name any family", str(caught.exception))

    def test_label_and_source_key_for_one_family_refuse(self):
        self.write_model()
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(
                self.model_id,
                3,
                palette={"gear_a": [0.1, 0.2, 0.3], AUTO_KEY_A: [0.3, 0.2, 0.1]},
            )
        self.assertIn("names the same family twice", str(caught.exception))

    def test_explicit_families_keep_family_keys_only(self):
        self.write_model()
        families = {"gear_family": ["gear_a", "gear_b"], "shaft_family": ["shaft_main"]}
        page = appearance.preview_recolor(
            self.model_id,
            3,
            palette={"gear_family": [0.1, 0.2, 0.3], "shaft_family": [0.4, 0.5, 0.6]},
            families=families,
        )
        self.assertEqual(page["palette_source"], "explicit")
        self.assertEqual(page["family_counts"], {"gear_family": 2, "shaft_family": 1})
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(
                self.model_id,
                3,
                palette={"gear_a": [0.1, 0.2, 0.3], "shaft_family": [0.4, 0.5, 0.6]},
                families=families,
            )
        self.assertIn("does not name a family", str(caught.exception))


class RandomPaletteContract(AppearanceFixture):
    def test_random_palette_is_deterministic_and_complete(self):
        self.write_model()
        first = appearance.preview_recolor(self.model_id, 3, random=True)
        second = appearance.preview_recolor(self.model_id, 3, random=True)
        self.assertEqual(first["palette_source"], "random")
        self.assertEqual(first["palette"], second["palette"])
        self.assertEqual(sorted(first["palette"]), sorted([AUTO_KEY_A, AUTO_KEY_B]))
        colors = list(first["palette"].values())
        self.assertEqual(len({tuple(color) for color in colors}), len(colors))
        for color in colors:
            self.assertEqual(len(color), 3)
            for channel in color:
                self.assertGreaterEqual(channel, 0.0)
                self.assertLessEqual(channel, 1.0)

    def test_random_and_palette_are_mutually_exclusive(self):
        self.write_model()
        with self.assertRaises(ValueError) as caught:
            appearance.preview_recolor(self.model_id, 3, palette={"gear_a": [0, 0, 0]}, random=True)
        self.assertIn("mutually exclusive", str(caught.exception))

    def test_plan_operation_refuses_random(self):
        with self.assertRaises(ValueError) as caught:
            validate_operations(
                [
                    {
                        "op": "recolor_assembly",
                        "palette": {AUTO_KEY_A: [0, 0, 0]},
                        "families": None,
                        "random": True,
                    }
                ]
            )
        self.assertIn("random", str(caught.exception))

    def test_submit_resolves_random_into_an_explicit_palette(self):
        self.write_model()
        self.write_template_config()
        with patch.object(general.subprocess, "Popen", return_value=None):
            manifest = appearance.submit_recolor(self.model_id, 3, random=True)
        request = bridge.read_json(bridge.job_path(manifest["job_id"]) / "request.json")
        (op,) = request["operations"]
        self.assertNotIn("random", op)
        self.assertEqual(sorted(op["families"]), sorted([AUTO_KEY_A, AUTO_KEY_B]))
        self.assertEqual(len(op["assignments"]), 3)
        self.assertEqual(manifest["palette_source"], "random")
        self.assertEqual(sorted(manifest["palette"]), sorted([AUTO_KEY_A, AUTO_KEY_B]))
        for assignment in op["assignments"]:
            self.assertEqual(assignment["rgb"], manifest["palette"][assignment["family"]])

    def test_submit_resolves_label_keys_into_family_keys(self):
        self.write_model()
        self.write_template_config()
        with patch.object(general.subprocess, "Popen", return_value=None):
            manifest = appearance.submit_recolor(
                self.model_id,
                3,
                palette={"gear_a": [0.1, 0.2, 0.3], "shaft_main": [0.4, 0.5, 0.6]},
            )
        request = bridge.read_json(bridge.job_path(manifest["job_id"]) / "request.json")
        (op,) = request["operations"]
        self.assertEqual(sorted(op["families"]), sorted([AUTO_KEY_A, AUTO_KEY_B]))
        self.assertEqual(manifest["palette_source"], "family_label")
        self.assertEqual(manifest["palette"][AUTO_KEY_A], [0.1, 0.2, 0.3])


if __name__ == "__main__":
    unittest.main()
