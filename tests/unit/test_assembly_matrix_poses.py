"""FEAT-012 batch-2 stage-4 matrix pose math regressions (offline).

Locks the corrected bounding-box invariant used by tools/test_assembly_matrix.py:
the AABB of a rotated box keeps the source box volume ONLY for signed-
permutation (axis-aligned) rotations; the [30,90,60] pose and any genuine
rotation strictly enlarge it. The old driver asserted equality for every
pose, which is mathematically false for the last pose.
"""

import unittest

from tools.test_assembly_matrix import POSES, is_signed_permutation

# Native source sketch is [0,2]x[0,3] extruded 5 deep.
SOURCE_LO = [0.0, 0.0, 0.0]
SOURCE_HI = [2.0, 3.0, 5.0]


def map_point(matrix, point):
    return [sum(v * matrix[k][j] for k, v in enumerate(point)) + matrix[3][j] for j in range(3)]


def expected_box_volume(rotation, translation):
    corners = [
        [x, y, z]
        for x in (SOURCE_LO[0], SOURCE_HI[0])
        for y in (SOURCE_LO[1], SOURCE_HI[1])
        for z in (SOURCE_LO[2], SOURCE_HI[2])
    ]
    transform = [list(row) + [0] for row in rotation] + [list(translation) + [1]]
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for corner in corners:
        mapped = map_point(transform, corner)
        for axis in range(3):
            lo[axis] = min(lo[axis], mapped[axis])
            hi[axis] = max(hi[axis], mapped[axis])
    volume = 1.0
    for axis in range(3):
        volume *= hi[axis] - lo[axis]
    return volume


SOURCE_BOX_VOLUME = (
    (SOURCE_HI[0] - SOURCE_LO[0]) * (SOURCE_HI[1] - SOURCE_LO[1]) * (SOURCE_HI[2] - SOURCE_LO[2])
)


class MatrixPoseMath(unittest.TestCase):
    def test_pose_matrix_stays_11_with_one_non_permutation(self):
        self.assertEqual(len(POSES), 11)
        non_permutations = [
            euler for euler, rotation, _ in POSES if not is_signed_permutation(rotation)
        ]
        self.assertEqual(non_permutations, [[30, 90, 60]])

    def test_signed_permutation_detection(self):
        self.assertTrue(is_signed_permutation([[1, 0, 0], [0, 1, 0], [0, 0, 1]]))
        self.assertTrue(is_signed_permutation([[0, 1, 0], [0, 0, 1], [1, 0, 0]]))
        self.assertTrue(is_signed_permutation([[0, -1, 0], [1, 0, 0], [0, 0, 1]]))
        self.assertTrue(is_signed_permutation([[0, 0, -1], [0, 1, 0], [1, 0, 0]]))
        self.assertFalse(
            is_signed_permutation(
                [[0, 0, -1], [-0.5, 0.8660254037844386, 0], [0.8660254037844386, 0.5, 0]]
            )
        )

    def test_box_volume_invariant_only_for_axis_aligned_poses(self):
        translation = [7, -8, 9, 1]
        for euler, rotation, _ in POSES:
            volume = expected_box_volume(rotation, translation)
            if is_signed_permutation(rotation):
                self.assertAlmostEqual(volume, SOURCE_BOX_VOLUME, places=9, msg=str(euler))
            else:
                # The stage-3 assertion (equality for every pose) fails here:
                # the AABB of a genuinely rotated box is strictly larger.
                self.assertGreater(volume, SOURCE_BOX_VOLUME + 1.0, msg=str(euler))

    def test_translation_does_not_change_box_volume(self):
        for euler, rotation, _ in POSES:
            at_origin = expected_box_volume(rotation, [0, 0, 0, 1])
            translated = expected_box_volume(rotation, [7, -8, 9, 1])
            self.assertAlmostEqual(at_origin, translated, places=9, msg=str(euler))


if __name__ == "__main__":
    unittest.main()
