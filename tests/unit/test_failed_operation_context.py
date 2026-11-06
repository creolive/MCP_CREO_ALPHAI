"""FEAT-012 / FEAT-008: the bounded failed_operation contract.

Offline contract tests for the 0.12.0 feedback P-2/P-3 (F01) and the assembly
rotation item (F04 P5): one bounded failure context beside the existing
``failed_operation_index``, the raw Toolkit code with its provenance, the
caller's echoed 4x4 placement matrix and its determinant/orthogonality
residual, and a length-bounded message. The matrix is never repaired,
normalized or transposed, and a missing code is published as null instead of
a fabricated value.
"""

import unittest

from creo_mechdog.failure_context import (
    FAILED_OPERATION_MESSAGE_LIMIT,
    annotate_failed_operation,
    bounded_message,
    placement_matrix,
)
from creo_mechdog.operation_results import annotate_native_result

# The F01 report's failing placement: orthonormal within 1e-6, det +1, but the
# kernel still returned -2. Rows are local axes in the parent (row vectors).
F01_ROTATION = [
    [0.0, 0.307383, -0.951586],
    [0.0, 0.951586, 0.307383],
    [1.0, 0.0, 0.0],
]
F01_TRANSLATION = [12.5, -4.25, 30.0]


def failed_extrude_result(**overrides):
    result = {
        "success": False,
        "toolkit_code": -1,
        "message": "Regeneration produced a failed, suppressed or incomplete feature",
        "failed_stage": "execute_extrude",
        "failed_toolkit_call": "ProSolidRegenerate",
        "failed_operation_index": 1,
    }
    result.update(overrides)
    return result


def extrude_inputs():
    return [
        {"op": "sketch", "label": "p10_sk1"},
        {"op": "extrude", "label": "p10_ex2", "sketch": "p10_sk1"},
        {"op": "extrude", "label": "p10_ex3", "sketch": 12},
    ]


def placement_operation(**overrides):
    operation = {
        "op": "assemble_component",
        "label": "i032",
        "source_model_id": "a" * 32,
        "rotation_matrix": F01_ROTATION,
        "translation": F01_TRANSLATION,
    }
    operation.update(overrides)
    return operation


class SuccessPathTest(unittest.TestCase):
    def test_a_succeeded_result_never_carries_the_block(self):
        result = {"success": True, "toolkit_code": 0}
        annotate_failed_operation(result, extrude_inputs())
        self.assertNotIn("failed_operation", result)

    def test_a_stale_block_is_removed_from_a_succeeded_result(self):
        stale = {"index": 0, "operation": "extrude", "pro_error": -2}
        result = {"success": True, "failed_operation": stale}
        annotate_failed_operation(result)
        self.assertNotIn("failed_operation", result)


class MappingTest(unittest.TestCase):
    def test_index_operation_stage_and_names_come_from_the_request(self):
        result = failed_extrude_result()
        annotate_failed_operation(result, extrude_inputs())
        block = result["failed_operation"]
        self.assertEqual(block["index"], 1)
        self.assertEqual(block["operation"], "extrude")
        self.assertEqual(block["stage"], "execute_extrude")
        self.assertEqual(block["feature_label"], "p10_ex2")
        self.assertEqual(block["sketch_name"], "p10_sk1")
        self.assertIsNone(block["input_matrix"])

    def test_an_integer_sketch_id_is_not_turned_into_a_name(self):
        result = failed_extrude_result(failed_operation_index=2)
        annotate_failed_operation(result, extrude_inputs())
        block = result["failed_operation"]
        self.assertEqual(block["feature_label"], "p10_ex3")
        self.assertIsNone(block["sketch_name"])

    def test_an_out_of_range_index_keeps_the_number_but_names_nothing(self):
        result = failed_extrude_result(failed_operation_index=99)
        annotate_failed_operation(result, extrude_inputs())
        block = result["failed_operation"]
        self.assertEqual(block["index"], 99)
        self.assertIsNone(block["operation"])
        self.assertIsNone(block["feature_label"])

    def test_a_failure_before_any_operation_keeps_the_stage_and_null_index(self):
        result = {
            "success": False,
            "message": "Toolkit call connect_creo failed with code -4 during connect",
            "failed_stage": "connect",
            "failed_toolkit_call": "connect_creo",
            "toolkit_code": -4,
            "failed_operation_index": None,
        }
        annotate_failed_operation(result, extrude_inputs())
        block = result["failed_operation"]
        self.assertIsNone(block["index"])
        self.assertIsNone(block["operation"])
        self.assertEqual(block["stage"], "connect")
        self.assertEqual(block["pro_error"], -4)
        self.assertEqual(block["pro_error_source"], "toolkit")

    def test_the_native_block_wins_over_the_request_echo(self):
        block = {
            "index": 1,
            "operation": "extrude",
            "stage": "execute_extrude",
            "feature_label": "native_label",
            "sketch_name": "native_sketch",
            "toolkit_call": "ProFeatureWithoptionsCreate",
            "pro_error": -1,
            "pro_error_source": "toolkit",
            "message": "native text",
            "message_truncated": False,
        }
        result = failed_extrude_result(failed_operation=block)
        annotate_failed_operation(result, extrude_inputs())
        projected = result["failed_operation"]
        self.assertEqual(projected["feature_label"], "native_label")
        self.assertEqual(projected["sketch_name"], "native_sketch")
        self.assertEqual(projected["toolkit_call"], "ProFeatureWithoptionsCreate")
        self.assertEqual(projected["message"], "native text")


class ProErrorTest(unittest.TestCase):
    def test_a_toolkit_failure_keeps_its_raw_code(self):
        result = failed_extrude_result(
            toolkit_code=-2,
            failed_toolkit_call="ProAsmcompAssemble",
        )
        annotate_failed_operation(result, extrude_inputs())
        block = result["failed_operation"]
        self.assertEqual(block["pro_error"], -2)
        self.assertEqual(block["pro_error_source"], "toolkit")
        self.assertEqual(block["toolkit_call"], "ProAsmcompAssemble")

    def test_a_non_toolkit_failure_is_null_and_marked_unsupported(self):
        # The native general-error fallback is -1, but no Toolkit call failed;
        # re-publishing that as a toolkit code would fabricate provenance.
        result = failed_extrude_result(
            toolkit_code=-1,
            failed_toolkit_call=None,
        )
        annotate_failed_operation(result, extrude_inputs())
        block = result["failed_operation"]
        self.assertIsNone(block["pro_error"])
        self.assertEqual(block["pro_error_source"], "unsupported")
        self.assertIsNone(block["toolkit_call"])

    def test_an_explicit_native_null_is_not_replaced_by_the_general_code(self):
        native = {
            "index": 0,
            "operation": "extrude",
            "pro_error": None,
            "pro_error_source": "unsupported",
        }
        result = failed_extrude_result(failed_operation=native, toolkit_code=-1)
        annotate_failed_operation(result, extrude_inputs())
        block = result["failed_operation"]
        self.assertIsNone(block["pro_error"])
        self.assertEqual(block["pro_error_source"], "unsupported")


class PlacementMatrixTest(unittest.TestCase):
    def test_the_caller_matrix_is_echoed_verbatim_with_det_and_residual(self):
        operation = placement_operation()
        matrix = placement_matrix(operation)
        self.assertEqual(matrix["matrix_source"], "rotation_matrix")
        self.assertEqual(matrix["input_matrix"][:3], [row + [0.0] for row in F01_ROTATION])
        self.assertEqual(matrix["input_matrix"][3], F01_TRANSLATION + [1.0])
        self.assertAlmostEqual(matrix["determinant"], 1.0, delta=1e-6)
        residual = matrix["orthogonality_residual"]
        # Small but real: the F01 matrix passed the 1e-6 admission gate.
        self.assertGreater(residual, 0.0)
        self.assertLess(residual, 1e-6)

    def test_the_echo_is_not_orthonormalized_or_transposed(self):
        operation = placement_operation()
        echoed = placement_matrix(operation)["input_matrix"]
        self.assertEqual(echoed[0][:3], F01_ROTATION[0])
        self.assertEqual(echoed[1][:3], F01_ROTATION[1])
        self.assertEqual(echoed[2][:3], F01_ROTATION[2])

    def test_euler_input_expands_with_the_row_vector_convention(self):
        matrix = placement_matrix(
            {"op": "assemble_component", "rotation": [0, 0, 90], "translation": [1, 2, 3]}
        )
        self.assertEqual(matrix["matrix_source"], "euler")
        expected = [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
        for row, expected_row in zip(matrix["input_matrix"][:3], expected, strict=True):
            for value, expected_value in zip(row[:3], expected_row, strict=True):
                self.assertAlmostEqual(value, expected_value, places=9)
        self.assertAlmostEqual(matrix["determinant"], 1.0, places=9)
        self.assertAlmostEqual(matrix["orthogonality_residual"], 0.0, places=9)

    def test_an_unusable_pose_leaves_every_matrix_field_null(self):
        result = {"success": False, "failed_operation_index": 0}
        annotate_failed_operation(
            result, [{"op": "assemble_component", "rotation_matrix": [[1, 2], [3, 4]]}]
        )
        block = result["failed_operation"]
        for field in (
            "input_matrix",
            "matrix_source",
            "determinant",
            "orthogonality_residual",
        ):
            self.assertIsNone(block[field])

    def test_a_placement_failure_carries_the_matrix_through_the_result(self):
        result = {
            "success": False,
            "toolkit_code": -2,
            "failed_stage": "execute_assemble_component",
            "failed_toolkit_call": "ProAsmcompAssemble",
            "failed_operation_index": 31,
            "message": (
                "Toolkit call ProAsmcompAssemble((ProAssembly)board, (ProSolid)child, "
                "position, &comp) failed with code -2 during execute_assemble_component"
            ),
        }
        operations = [placement_operation()] * 31 + [
            placement_operation(label="i033"),
        ]
        annotate_failed_operation(result, operations)
        block = result["failed_operation"]
        self.assertEqual(block["index"], 31)
        self.assertEqual(block["operation"], "assemble_component")
        self.assertEqual(block["stage"], "execute_assemble_component")
        self.assertEqual(block["pro_error"], -2)
        self.assertEqual(block["pro_error_source"], "toolkit")
        self.assertEqual(block["input_matrix"][:3], [row + [0.0] for row in F01_ROTATION])
        self.assertAlmostEqual(block["determinant"], 1.0, delta=1e-6)
        self.assertLess(block["orthogonality_residual"], 1e-6)
        # The request echo is never repaired or rewritten in place.
        self.assertEqual(operations[31]["rotation_matrix"], F01_ROTATION)

    def test_the_native_matrix_is_used_and_its_missing_arithmetic_recomputed(self):
        native = {
            "index": 0,
            "operation": "component_placement",
            "input_matrix": [row + [0.0] for row in F01_ROTATION] + [F01_TRANSLATION + [1.0]],
            "matrix_source": "rotation_matrix",
            "determinant": None,
            "orthogonality_residual": None,
        }
        result = {"success": False, "failed_operation": native}
        annotate_failed_operation(result)
        block = result["failed_operation"]
        self.assertAlmostEqual(block["determinant"], 1.0, delta=1e-6)
        self.assertLess(block["orthogonality_residual"], 1e-6)

    def test_non_placement_operations_keep_the_matrix_fields_null(self):
        result = failed_extrude_result()
        annotate_failed_operation(result, extrude_inputs())
        block = result["failed_operation"]
        for field in (
            "input_matrix",
            "matrix_source",
            "determinant",
            "orthogonality_residual",
        ):
            self.assertIsNone(block[field])


class MessageBoundTest(unittest.TestCase):
    def test_a_long_message_is_cut_to_the_fixed_bound(self):
        long_text = "x" * (FAILED_OPERATION_MESSAGE_LIMIT + 200)
        result = failed_extrude_result(message=long_text)
        annotate_failed_operation(result, extrude_inputs())
        block = result["failed_operation"]
        self.assertEqual(len(block["message"]), FAILED_OPERATION_MESSAGE_LIMIT)
        self.assertTrue(block["message_truncated"])
        self.assertEqual(block["message"], long_text[:FAILED_OPERATION_MESSAGE_LIMIT])

    def test_a_short_message_is_kept_whole(self):
        result = failed_extrude_result()
        annotate_failed_operation(result, extrude_inputs())
        block = result["failed_operation"]
        self.assertEqual(block["message"], result["message"])
        self.assertFalse(block["message_truncated"])

    def test_the_native_truncation_flag_stays_true(self):
        native = {"index": 0, "message": "already cut", "message_truncated": True}
        result = {"success": False, "failed_operation": native}
        annotate_failed_operation(result)
        self.assertTrue(result["failed_operation"]["message_truncated"])

    def test_the_whole_block_stays_bounded(self):
        message, truncated = bounded_message("y" * 5000)
        self.assertEqual(len(message), FAILED_OPERATION_MESSAGE_LIMIT)
        self.assertTrue(truncated)
        result = failed_extrude_result(message="z" * 5000)
        annotate_failed_operation(result, extrude_inputs())
        self.assertEqual(len(result["failed_operation"]["message"]), FAILED_OPERATION_MESSAGE_LIMIT)


class AnnotateNativeResultTest(unittest.TestCase):
    def test_a_failed_result_without_operations_still_carries_the_block(self):
        result = failed_extrude_result()
        annotate_native_result(result, readonly=False, inputs=None)
        self.assertIn("failed_operation", result)
        self.assertEqual(result["failed_operation"]["stage"], "execute_extrude")
        self.assertEqual(result["failed_operation"]["pro_error"], -1)

    def test_a_succeeded_result_carries_no_block(self):
        result = {"success": True, "toolkit_code": 0}
        annotate_native_result(result, readonly=False, inputs=extrude_inputs())
        self.assertNotIn("failed_operation", result)


class CompactVisibilityTest(unittest.TestCase):
    def test_the_compact_job_keeps_the_bounded_block(self):
        from bridge import compact_job

        result = failed_extrude_result()
        annotate_failed_operation(result, extrude_inputs())
        compact = compact_job({"job_id": "j", "status": "failed", "result": result})
        block = compact["result"]["failed_operation"]
        self.assertEqual(block["index"], 1)
        self.assertEqual(block["operation"], "extrude")
        self.assertEqual(block["stage"], "execute_extrude")
        self.assertEqual(block["pro_error"], -1)
        self.assertEqual(block["pro_error_source"], "toolkit")


if __name__ == "__main__":
    unittest.main()
