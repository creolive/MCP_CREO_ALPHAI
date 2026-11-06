"""FEAT-012 batch-2 stage-4 matrix pose math regressions (offline).

Locks the corrected bounding-box invariant used by tools/test_assembly_matrix.py:
the AABB of a rotated box keeps the source box volume ONLY for signed-
permutation (axis-aligned) rotations; the [30,90,60] pose and any genuine
rotation strictly enlarge it. The old driver asserted equality for every
pose, which is mathematically false for the last pose.

R05 (BUG-045/FEAT-012) adds the published row-vector convention: the
``assemble_component`` and ``component_placement`` input branches must state
``p_parent = p_local * rotation_matrix + translation``, and a 17.9-degree
matrix must map an asymmetric point and the basis vectors as
``p_local * R`` — never as a transposed column-vector product.
"""

import math
import unittest

from pydantic import TypeAdapter, ValidationError

from creo_mechdog.schema import (
    ROTATION_CONVENTION,
    ROTATION_FORMULA,
    AssembleOp,
    ComponentPlacementOp,
    Operation,
    validate_operations,
)
from tools.test_assembly_matrix import POSES, is_signed_permutation

Z_ANGLE = 17.9
SOURCE_ID = "a" * 32


def z_rotation(angle=Z_ANGLE, digits=None):
    """Row-vector Z rotation: row 0 is the mapped local X axis."""
    radians = math.radians(angle)
    rotation = [
        [math.cos(radians), math.sin(radians), 0.0],
        [-math.sin(radians), math.cos(radians), 0.0],
        [0.0, 0.0, 1.0],
    ]
    if digits is not None:
        return [[round(value, digits) for value in row] for row in rotation]
    return rotation


def row_vector_map(rotation, translation, point):
    return [sum(point[k] * rotation[k][j] for k in range(3)) + translation[j] for j in range(3)]


def column_vector_map(rotation, translation, point):
    """What a transposed (column-vector) reading would produce; must differ."""
    return [sum(rotation[j][k] * point[k] for k in range(3)) + translation[j] for j in range(3)]


def assemble_operation(rotation_matrix, translation=(0.0, 0.0, 0.0)):
    return {
        "op": "assemble_component",
        "label": "i032",
        "source_model_id": SOURCE_ID,
        "rotation_matrix": rotation_matrix,
        "translation": list(translation),
    }


def placement_operation(rotation_matrix, translation=(0.0, 0.0, 0.0)):
    return {
        "op": "component_placement",
        "component": "i032",
        "rotation_matrix": rotation_matrix,
        "translation": list(translation),
    }


def plan_schema():
    """The execute_plan input: a discriminated union of operations per entry."""
    return TypeAdapter(list[Operation]).json_schema()


def branch_properties(kind):
    schema = plan_schema()
    reference = schema["items"]["discriminator"]["mapping"][kind]
    return schema["$defs"][reference.rsplit("/", 1)[-1]]["properties"]


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


class RotationContractTest(unittest.TestCase):
    """R05: both assembly branches state the same row-vector formula."""

    def test_both_assembly_branches_state_the_same_formula(self):
        assemble = branch_properties("assemble_component")
        placement = branch_properties("component_placement")
        for field in ("rotation_matrix", "rotation"):
            self.assertEqual(assemble[field]["description"], placement[field]["description"], field)
            self.assertIn(ROTATION_FORMULA, assemble[field]["description"], field)

    def test_the_matrix_description_states_the_gate_and_refuses_repair(self):
        description = branch_properties("assemble_component")["rotation_matrix"]["description"]
        for phrase in (
            "3x3",
            "orthogonal",
            "1e-6",
            "determinant +1",
            "mutually exclusive",
            "never transposed",
        ):
            self.assertIn(phrase, description)

    def test_the_published_convention_name_is_the_row_vector_mapping(self):
        self.assertEqual(ROTATION_CONVENTION, "row_vectors_local_to_parent")
        self.assertIn("p_local", ROTATION_FORMULA)


class RowVectorPoseTest(unittest.TestCase):
    """R05: the admitted matrix is applied as p_local * R, never R * p_local."""

    def test_basis_vectors_map_to_the_matrix_rows(self):
        rotation = z_rotation()
        for axis, row in enumerate(rotation):
            point = [0.0, 0.0, 0.0]
            point[axis] = 1.0
            mapped = row_vector_map(rotation, [0.0, 0.0, 0.0], point)
            for actual, expected in zip(mapped, row, strict=True):
                self.assertAlmostEqual(actual, expected, places=12)

    def test_an_asymmetric_point_uses_p_local_times_r(self):
        rotation = z_rotation()
        translation = [1.5, -2.25, 7.0]
        point = [3.0, 4.0, 0.0]
        cosine, sine = math.cos(math.radians(Z_ANGLE)), math.sin(math.radians(Z_ANGLE))
        expected = [
            3 * cosine - 4 * sine + translation[0],
            3 * sine + 4 * cosine + translation[1],
            translation[2],
        ]
        mapped = row_vector_map(rotation, translation, point)
        for actual, value in zip(mapped, expected, strict=True):
            self.assertAlmostEqual(actual, value, places=12)
        transposed = column_vector_map(rotation, translation, point)
        self.assertGreater(abs(mapped[0] - transposed[0]), 1.0)
        self.assertGreater(abs(mapped[1] - transposed[1]), 1.0)

    def test_full_precision_and_six_decimal_poses_are_admitted_unchanged(self):
        for digits in (None, 6):
            rotation = z_rotation(digits=digits)
            for operation, model in (
                (assemble_operation(rotation), AssembleOp),
                (placement_operation(rotation), ComponentPlacementOp),
            ):
                admitted = model(**operation)
                # The echo is the caller's matrix: no repair and no transpose.
                self.assertEqual(admitted.rotation_matrix, rotation)
                self.assertIsNone(admitted.rotation)
                validate_operations([operation])

    def test_rounding_below_the_gate_is_rejected_without_repair(self):
        rotation = z_rotation(digits=4)
        for operation, model in (
            (assemble_operation(rotation), AssembleOp),
            (placement_operation(rotation), ComponentPlacementOp),
        ):
            with self.assertRaises(ValidationError):
                model(**operation)
        with self.assertRaises(ValidationError):
            # Admission rejects before any job exists; nothing is repaired.
            validate_operations([assemble_operation(rotation)])

    def test_a_reflection_and_a_second_orientation_are_rejected(self):
        with self.assertRaises(ValidationError):
            AssembleOp(**assemble_operation([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]))
        both = assemble_operation(z_rotation())
        both["rotation"] = [0.0, 0.0, Z_ANGLE]
        with self.assertRaises(ValidationError):
            AssembleOp(**both)
        with self.assertRaises(ValidationError):
            ComponentPlacementOp(**placement_operation([[1.0, 2.0], [3.0, 4.0]]))


if __name__ == "__main__":
    unittest.main()
