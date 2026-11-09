import unittest
from pathlib import Path
from unittest.mock import patch

import generic_bridge


class LoftSeedValidation(unittest.TestCase):
    def sections(self):
        return [
            {
                "op": "sketch",
                "label": name,
                "offset": z,
                "entities": [
                    {"type": "circle", "name": "circle", "center": [0, 0], "radius": radius}
                ],
            }
            for name, z, radius in [("bottom", 0, 10), ("top", 30, 5)]
        ]

    def test_invalid_scope_rejected_without_queueing(self):
        cases = [self.sections()[:1], self.sections() * 2]
        inverted = self.sections()
        inverted[1]["offset"] = 0
        cases.append(inverted)
        middle = self.sections()
        middle.insert(1, {**middle[1], "label": "middle", "offset": 40})
        cases.append(middle)
        tilted = self.sections()
        tilted[1]["plane"] = "XZ"
        cases.append(tilted)
        too_many = [{**self.sections()[0], "label": f"section_{i}", "offset": i} for i in range(21)]
        cases.append(too_many)
        with patch.object(generic_bridge, "submit") as submit:
            for sections in cases:
                with self.assertRaises(ValueError):
                    generic_bridge.new_loft_part("missing.prt", 60, sections)
            submit.assert_not_called()

    def test_seed_file_and_labels_validated_before_submission(self):
        seed = Path(__file__).resolve().parent / "seed.prt.1"
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(generic_bridge, "submit", return_value={"queued": True}) as submit:
                for label in ["bottom", "../bad"]:
                    with self.assertRaises(ValueError):
                        generic_bridge.new_loft_part(str(seed), 60, self.sections(), label)
                for fid in [-1, True, 2147483648]:
                    with self.assertRaises(ValueError):
                        generic_bridge.new_loft_part(str(seed), fid, self.sections())
                with self.assertRaises(ValueError):
                    generic_bridge.new_loft_part(
                        str(seed.with_suffix(".step")), 60, self.sections()
                    )
                submit.assert_not_called()
                receipt = generic_bridge.new_loft_part(str(seed), 60, self.sections())
                self.assertTrue(receipt["queued"])
                self.assertEqual(receipt["seed_preflight"]["verdict"], "unverified")
                self.assertEqual(
                    submit.call_args.kwargs["loft_seed"]["sections"], ["bottom", "top"]
                )
                self.assertIsNone(submit.call_args.kwargs.get("model_id"))

    def test_interpolation_is_explicit_and_validated(self):
        seed = Path(__file__).resolve().parent / "seed.prt.1"
        with (
            patch.object(Path, "is_file", return_value=True),
            patch.object(generic_bridge, "submit") as submit,
        ):
            for invalid in ["spline", "SMOOTH", None, False]:
                with self.assertRaises(ValueError):
                    generic_bridge.new_loft_part(
                        str(seed), 60, self.sections(), interpolation=invalid
                    )
            submit.assert_not_called()
            generic_bridge.new_loft_part(str(seed), 60, self.sections(), interpolation="smooth")
            self.assertEqual(submit.call_args.kwargs["loft_seed"]["interpolation"], "smooth")

    def test_multisection_order_preserved_for_seed_binding(self):
        seed = Path(__file__).resolve().parent / "seed.prt.1"
        for count in [3, 5, 20]:
            sections = [
                {**self.sections()[0], "label": f"section_{i}", "offset": i * 10}
                for i in range(count)
            ]
            with (
                patch.object(Path, "is_file", return_value=True),
                patch.object(generic_bridge, "submit", return_value={"queued": True}) as submit,
            ):
                receipt = generic_bridge.new_loft_part(str(seed), 60, sections)
                self.assertTrue(receipt["queued"])
                self.assertIn("seed_preflight", receipt)
                self.assertEqual(
                    submit.call_args.kwargs["loft_seed"]["sections"], [s["label"] for s in sections]
                )
                self.assertEqual(len(submit.call_args.args[0]), count)
