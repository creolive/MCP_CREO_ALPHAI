"""BUG-111: rotation is bounded before the kernel sees it, and says why.

The 0.11.5 Creo 10 report showed ``225 deg`` and ``-135 deg`` failing at the same
"fifth copy" position with a bare ``ProFeatureWithoptionsCreate = -1``, while
45/90/135/180 succeeded. The schema only bounded rotation to +/-360, so a value
outside the kernel's usable range could be submitted and fail without an
explanation, and the native flex path also rewrote every negative angle as
``+360`` (so -135 became 225).
"""

import unittest
from pathlib import Path

from creo_mechdog.schema import validate_operations

NATIVE = Path(__file__).resolve().parents[2] / "native"


def transform(**overrides):
    operation = {
        "op": "geometry_transform",
        "label": "pose",
        "references": [{"kind": "body"}],
        "translation": [0, 0, 0],
        "rotation": [0, 0, 45],
        "keep_original": True,
    }
    operation.update(overrides)
    return operation


def update(**overrides):
    operation = {
        "op": "set_geometry_transform",
        "feature": "pose",
        "translation": [0, 0, 0],
        "rotation": [0, 0, 45],
    }
    operation.update(overrides)
    return operation


class TransformRotationRange(unittest.TestCase):
    def accepted(self, rotation, translation=(0, 0, 0)):
        return validate_operations(
            [transform(rotation=list(rotation), translation=list(translation))]
        )

    def test_equivalence_is_stated_instead_of_a_bare_kernel_code(self):
        with self.assertRaises(ValueError) as caught:
            self.accepted((0, 0, 225))
        message = str(caught.exception)
        self.assertIn("-135", message)
        self.assertIn("rotation", message.lower())

    def test_the_negative_equivalent_and_the_boundary_are_accepted(self):
        self.accepted((0, 0, -135))
        for angle in (-180, 180, 179.999, -179.999):
            self.accepted((0, 0, angle))

    def test_every_axis_is_bounded(self):
        for rotation in ((181, 0, 0), (0, -180.001, 0), (0, 0, 360), (200, 0, 45)):
            with self.assertRaises(ValueError):
                self.accepted(rotation)

    def test_set_geometry_transform_shares_the_same_range(self):
        with self.assertRaises(ValueError) as caught:
            validate_operations([update(rotation=[0, 0, 225])])
        self.assertIn("-135", str(caught.exception))
        validate_operations([update(rotation=[0, 0, -45])])

    def test_translation_range_is_unchanged(self):
        with self.assertRaises(ValueError):
            self.accepted((0, 0, 45), translation=(100001, 0, 0))
        self.accepted((0, 0, 45), translation=(100000, 0, 0))


class NativeRotationNormalization(unittest.TestCase):
    """The executor must agree with the published range, not rewrite it silently."""

    def setUp(self):
        self.placement = (NATIVE / "placement.cpp").read_text(encoding="utf-8")
        self.generic = (NATIVE / "generic.cpp").read_text(encoding="utf-8")

    def test_negative_angles_are_no_longer_shifted_by_360(self):
        for stale in ("value += 360", "number += 360", "if (flex && i < 3 && number < 0)"):
            self.assertNotIn(stale, self.placement)

    def test_both_backends_normalize_into_the_same_interval(self):
        self.assertIn("static double normalized_rotation_deg(", self.placement)
        self.assertIn("value = normalized_rotation_deg(value);", self.placement)
        self.assertIn("number = normalized_rotation_deg(number);", self.placement)
        self.assertIn(
            'i < 3 ? normalized_rotation_deg(op["rotation"][axis].get<double>())',
            self.placement,
        )

    def test_transform_start_and_failure_are_reported_per_operation(self):
        self.assertIn("TRANSFORM backend=", self.placement)
        self.assertIn('report["failed_transform"] =', self.generic)


if __name__ == "__main__":
    unittest.main()
