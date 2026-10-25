"""FEAT-008 batch-2 stage-4 pipeline driver request builders (offline).

The live driver (tools/test_assembly_pipeline.py) builds every dynamic MCP
request through the small builders in this module's source file. These tests
validate ALL branches — fixture parts, original assembly, rebuild from
inspected transforms, the final remove+re-assemble replace, the tab edit and
the adoption idempotency key — through the real
bridge.normalize_model_name / creo_mechdog.schema.validate_operations, so a
naming or schema regression fails here instead of inside a live session.
"""

import unittest

import bridge
from tools.test_assembly_pipeline import (
    external_source_name,
    original_assembly_name,
    rebuilt_assembly_name,
    replace_operations,
    request_plan,
    short_suffix,
    source_model_name,
    validate_plan,
)

IDENTITY4 = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
POSE_COMBINED = [[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [50, 40, 10, 1]]


def sample_plan(tag: str) -> dict:
    return request_plan(
        tag,
        {"a": "a" * 32, "b": "b" * 32},
        {
            "plate_a": {
                "copy_name": "c_job_0",
                "source_model_id": "a" * 32,
                "source_revision": 1,
                "transform": IDENTITY4,
            },
            "plate_b": {
                "copy_name": "c_job_1",
                "source_model_id": "b" * 32,
                "source_revision": 2,
                "transform": IDENTITY4,
            },
            "plate_b_second": {
                "copy_name": "c_job_2",
                "source_model_id": "b" * 32,
                "source_revision": 2,
                "transform": POSE_COMBINED,
            },
        },
        {
            "c_job_0": {"transform_mm_known": True, "transform_to_parent": IDENTITY4},
            "c_job_1": {"transform_mm_known": True, "transform_to_parent": IDENTITY4},
            "c_job_2": {"transform_mm_known": True, "transform_to_parent": POSE_COMBINED},
        },
    )


class PipelineRequestBuilders(unittest.TestCase):
    def test_short_suffix_is_stable_unique_and_lowercase(self):
        first = short_suffix("20261025T000000Zabcdef123456")
        self.assertEqual(first, short_suffix("20261025T000000Zabcdef123456"))
        self.assertEqual(first, short_suffix("20261025T000000Zabcdef123456").lower())
        self.assertEqual(len(first), 8)
        other = short_suffix("20261025T000001Zabcdef123456")
        self.assertNotEqual(first, other)

    def test_native_names_fit_the_31_character_limit(self):
        tag = "20261025T120000Z0123abcd"
        names = [
            source_model_name(tag, "a"),
            source_model_name(tag, "b"),
            original_assembly_name(tag),
            rebuilt_assembly_name(tag),
        ]
        for name in names:
            self.assertLessEqual(len(name), 31, name)
            self.assertEqual(name, bridge.normalize_model_name(name))
        for key in ("a", "b"):
            stem = external_source_name(tag, key).split(".")[0]
            self.assertLessEqual(len(stem), 31, stem)
            self.assertEqual(stem, bridge.normalize_model_name(stem))

    def test_previous_long_tag_naming_is_rejected_by_real_validator(self):
        # Regression anchor: the stage-3 driver used the 24-char tag directly
        # (pipe_src_a_<tag> = 35 chars, pipe_rebuilt_asm_<tag> = 41 chars) and
        # the real bridge.normalize_model_name refuses it.
        tag = "20261025T120000Z0123abcd"
        self.assertEqual(len(tag), 24)
        with self.assertRaises(ValueError):
            bridge.normalize_model_name(f"pipe_src_a_{tag}")
        with self.assertRaises(ValueError):
            bridge.normalize_model_name(f"pipe_rebuilt_asm_{tag}")

    def test_full_plan_validates_through_real_validators(self):
        plan = validate_plan(sample_plan("20261025T120000Z0123abcd"))
        self.assertEqual(len(plan["original_operations"]), 3)
        self.assertEqual(len(plan["rebuild_operations"]), 3)
        self.assertEqual(len(plan["replace_operations"]), 2)

    def test_replace_operations_keep_the_op_field(self):
        plan = sample_plan("20261025T120000Z0123abcd")
        remove_op, reassemble_op = plan["replace_operations"]
        self.assertEqual(remove_op["op"], "remove_component")
        # The stage-3 driver stripped "op" here, which execute_plan requires.
        self.assertEqual(reassemble_op["op"], "assemble_component")
        self.assertEqual(reassemble_op["label"], "plate_a")
        self.assertIn("rotation_matrix", reassemble_op)

    def test_rebuild_operations_use_inspected_normalized_transforms(self):
        plan = sample_plan("20261025T120000Z0123abcd")
        second = next(op for op in plan["rebuild_operations"] if op["label"] == "plate_b_second")
        self.assertEqual(second["translation"], [50, 40, 10])
        self.assertEqual(second["rotation_matrix"], [[0, 1, 0], [0, 0, 1], [1, 0, 0]])
        self.assertEqual(second["source_model_id"], "b" * 32)

    def test_missing_occurrence_fails_at_build_time(self):
        plan_tag = "20261025T120000Z0123abcd"
        with self.assertRaises(AssertionError):
            request_plan(
                plan_tag,
                {"a": "a" * 32, "b": "b" * 32},
                {
                    "plate_a": {
                        "copy_name": "c_job_0",
                        "source_model_id": "a" * 32,
                        "source_revision": 1,
                        "transform": IDENTITY4,
                    }
                },
                {},  # occurrence never inspected
            )

    def test_replace_operations_builder_directly(self):
        pose = {
            "op": "assemble_component",
            "label": "plate_a",
            "source_model_id": "a" * 32,
            "translation": [0, 0, 0],
            "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "placement": "fixed",
        }
        operations = replace_operations(pose)
        self.assertEqual(operations[1], pose)
        self.assertIsNot(operations[1], pose)


if __name__ == "__main__":
    unittest.main()
