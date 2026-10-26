"""FEAT-008 batch-2 stage-4 pipeline driver request builders (offline).

The live driver (tools/test_assembly_pipeline.py) builds every dynamic MCP
request through the small builders in this module's source file. These tests
validate ALL branches — fixture parts, original assembly, rebuild from
inspected transforms, the final remove+re-assemble replace (remove the stale
label, re-assemble under a NEW unique label), the tab edit and
the adoption idempotency key — through the real
bridge.normalize_model_name / creo_mechdog.schema.validate_operations, so a
naming or schema regression fails here instead of inside a live session.

Occurrence identity: the rebuild joins the frozen list_components snapshot to
creo_inspect_session_assembly items by ROOT occurrence path
(occurrence_path == [feature_id] at depth 0), never by display name. Real
2026-10-25 evidence shows the same occurrence named '▩C_A3C874E18A0445A10001'
(list_components copy_name) and 'C_A3C874E18A0445A1_0' (session assembly
name), and a repeated source occurrence shares one native copy name across
different occurrence paths — name-based joins collapse or miss those.
"""

import unittest
import uuid

import bridge
from tools.test_assembly_pipeline import (
    REFRESHED_PLATE_A_LABEL,
    bind_adopted_sources,
    external_source_name,
    index_occurrences,
    original_assembly_name,
    rebuild_operations,
    rebuilt_assembly_name,
    replace_operations,
    request_plan,
    short_suffix,
    source_model_name,
    validate_plan,
)

IDENTITY4 = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
POSE_COMBINED = [[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [50, 40, 10, 1]]

# The real cross-API display-name divergence for ONE root occurrence
# (feature_id/component_id 40, occurrence_path [40], 2026-10-25 evidence):
LIST_COPY_NAME = "▩C_A3C874E18A0445A10001"
SESSION_NAME = "C_A3C874E18A0445A1_0"
# Repeated occurrences of one source share a single native copy name:
SHARED_COPY_NAME = "▩C_JOB_B_PLATE_00001"


def session_item(feature_id: int, name: str, transform, depth: int = 0) -> dict:
    """Minimal real creo_inspect_session_assembly root component DTO."""
    return {
        "component_id": feature_id,
        "depth": depth,
        "name": name,
        "occurrence_path": [feature_id],
        "transform_mm_known": True,
        "transform_to_parent": transform,
    }


def sample_plan(tag: str) -> dict:
    return request_plan(
        tag,
        {"a": "a" * 32, "b": "b" * 32},
        {
            "plate_a": {
                "feature_id": 40,
                "copy_name": LIST_COPY_NAME,
                "source_model_id": "a" * 32,
                "source_revision": 1,
                "transform": IDENTITY4,
            },
            "plate_b": {
                "feature_id": 41,
                "copy_name": SHARED_COPY_NAME,
                "source_model_id": "b" * 32,
                "source_revision": 2,
                "transform": IDENTITY4,
            },
            "plate_b_second": {
                "feature_id": 42,
                "copy_name": SHARED_COPY_NAME,  # same native copy, second occurrence
                "source_model_id": "b" * 32,
                "source_revision": 2,
                "transform": POSE_COMBINED,
            },
        },
        [
            session_item(40, SESSION_NAME, IDENTITY4),
            session_item(41, "C_JOB_B_PLATE_1_0", IDENTITY4),
            session_item(42, "C_JOB_B_PLATE_1_1", POSE_COMBINED),
        ],
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
        self.assertEqual(remove_op, {"op": "remove_component", "component": "plate_a"})
        # The stage-3 driver stripped "op" here, which execute_plan requires.
        self.assertEqual(reassemble_op["op"], "assemble_component")
        # Live evidence (assembly_pipeline_live_20261025T162553Z step 9e): the
        # entry refuses a plan that re-assembles an EXISTING label even when
        # the same job removes it first, so the refreshed snapshot enters
        # under a NEW unique label while keeping the old pose and source.
        self.assertEqual(reassemble_op["label"], REFRESHED_PLATE_A_LABEL)
        self.assertNotEqual(reassemble_op["label"], "plate_a")
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
                        "feature_id": 40,
                        "copy_name": LIST_COPY_NAME,
                        "source_model_id": "a" * 32,
                        "source_revision": 1,
                        "transform": IDENTITY4,
                    }
                },
                [],  # occurrence never inspected
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
        self.assertEqual(operations[0], {"op": "remove_component", "component": "plate_a"})
        reassemble = operations[1]
        self.assertIsNot(reassemble, pose)
        self.assertEqual(reassemble["label"], REFRESHED_PLATE_A_LABEL)
        # Everything else — op, source, original pose — is preserved.
        for key, value in pose.items():
            if key != "label":
                self.assertEqual(reassemble[key], value)
        # The input pose is not mutated by the builder.
        self.assertEqual(pose["label"], "plate_a")


class AdoptedSourceBinding(unittest.TestCase):
    """Regression for the live failure build/assembly_pipeline_live_20261025T152542Z955f3b2d
    (guard build/guarded_live_20261025T152541178279): the original assembly
    execute_plan was submitted with the offline prototype placeholder ids
    aaaa.../bbbb... and the entry refused it with Unknown model_id. The real
    adopted ids keyed by input_path must be rebound into every id-bearing
    branch before any MCP submission."""

    PLACEHOLDERS = {"a" * 32, "b" * 32}

    def fake_adoption(self, tag):
        """Real-style random non-placeholder adopted ids keyed by input_path,
        the way creo_adopt_file apply items actually return them."""
        adopted_ids = {}
        external = {}
        for key in ("a", "b"):
            path = f"build/assembly_pipeline_external_{tag}/" + external_source_name(tag, key)
            adopted_ids[path] = uuid.uuid4().hex
            external[key] = {"path": path}
        return adopted_ids, external

    def assert_no_placeholders(self, operations):
        ids = {op["source_model_id"] for op in operations if "source_model_id" in op}
        self.assertTrue(ids)
        self.assertFalse(ids & self.PLACEHOLDERS, ids)

    def test_offline_prototype_plan_alone_still_carries_placeholders(self):
        # validate_plan checks schema shape, not id reality; this documents
        # why binding after the real adoption is mandatory.
        plan = validate_plan(sample_plan("20261025T120000Z0123abcd"))
        ids = {op["source_model_id"] for op in plan["original_operations"]}
        self.assertEqual(ids, self.PLACEHOLDERS)

    def test_bind_replaces_placeholders_with_real_ids_by_input_path(self):
        tag = "20261025T120000Z0123abcd"
        adopted_ids, external = self.fake_adoption(tag)
        plan = validate_plan(sample_plan(tag))
        plan = bind_adopted_sources(plan, adopted_ids, external)
        ids = {op["source_model_id"] for op in plan["original_operations"]}
        self.assertEqual(
            ids, {adopted_ids[external["a"]["path"]], adopted_ids[external["b"]["path"]]}
        )

    def test_bind_refuses_unknown_input_path(self):
        tag = "20261025T120000Z0123abcd"
        adopted_ids, external = self.fake_adoption(tag)
        plan = validate_plan(sample_plan(tag))
        del adopted_ids[external["b"]["path"]]
        with self.assertRaises(KeyError):
            bind_adopted_sources(plan, adopted_ids, external)

    def test_whole_flow_submits_only_real_returned_ids(self):
        """Walk every phase the driver submits and trace each source id back
        to a real returned value — placeholders must not survive anywhere."""
        tag = "20261025T120000Z0123abcd"
        adopted_ids, external = self.fake_adoption(tag)
        plan = validate_plan(sample_plan(tag))
        plan = bind_adopted_sources(plan, adopted_ids, external)
        self.assert_no_placeholders(plan["original_operations"])

        # Later phases build from REAL list_components / inspect data (frozen
        # aliases carry the adopted ids and queried feature_ids), not from the
        # prototype plan.
        real_a = adopted_ids[external["a"]["path"]]
        real_b = adopted_ids[external["b"]["path"]]
        frozen = {
            "plate_a": {
                "feature_id": 40,
                "copy_name": LIST_COPY_NAME,
                "source_model_id": real_a,
                "source_revision": 1,
                "transform": IDENTITY4,
            },
            "plate_b": {
                "feature_id": 41,
                "copy_name": SHARED_COPY_NAME,
                "source_model_id": real_b,
                "source_revision": 1,
                "transform": IDENTITY4,
            },
            "plate_b_second": {
                "feature_id": 42,
                "copy_name": SHARED_COPY_NAME,
                "source_model_id": real_b,
                "source_revision": 1,
                "transform": POSE_COMBINED,
            },
        }
        occurrences = [
            session_item(40, SESSION_NAME, IDENTITY4),
            session_item(41, "C_JOB_B_PLATE_1_0", IDENTITY4),
            session_item(42, "C_JOB_B_PLATE_1_1", POSE_COMBINED),
        ]
        rebuild = rebuild_operations(frozen, occurrences)
        validate_plan({**plan, "rebuild_operations": rebuild})
        self.assert_no_placeholders(rebuild)
        replace = replace_operations(next(op for op in rebuild if op["label"] == "plate_a"))
        self.assert_no_placeholders(replace)


class OccurrencePathBinding(unittest.TestCase):
    """Regression for the driver response contract found in the 2026-10-25
    guarded matrix run: the same root occurrence is named differently by
    creo_list_components ('▩C_A3C874E18A0445A10001') and
    creo_inspect_session_assembly ('C_A3C874E18A0445A1_0'), and a repeated
    source occurrence shares one native copy name across distinct occurrence
    paths. Display names must stay evidence-only; identity is the root-level
    occurrence_path / queried feature_id."""

    FROZEN_SINGLE = {
        "plate_a": {
            "feature_id": 40,
            "copy_name": LIST_COPY_NAME,
            "source_model_id": "a" * 32,
            "source_revision": 1,
            "transform": IDENTITY4,
        }
    }

    def test_display_names_differ_across_apis_but_root_path_joins(self):
        operations = rebuild_operations(
            self.FROZEN_SINGLE,
            [session_item(40, SESSION_NAME, IDENTITY4)],
        )
        (op,) = operations
        self.assertEqual(op["source_model_id"], "a" * 32)
        self.assertEqual(op["translation"], [0, 0, 0])
        self.assertEqual(op["rotation_matrix"], [[1, 0, 0], [0, 1, 0], [0, 0, 1]])

    def test_repeated_occurrence_same_copy_name_binds_each_path(self):
        frozen = {
            "plate_b": {
                "feature_id": 41,
                "copy_name": SHARED_COPY_NAME,
                "source_model_id": "b" * 32,
                "source_revision": 2,
                "transform": IDENTITY4,
            },
            "plate_b_second": {
                "feature_id": 42,
                "copy_name": SHARED_COPY_NAME,
                "source_model_id": "b" * 32,
                "source_revision": 2,
                "transform": POSE_COMBINED,
            },
        }
        operations = rebuild_operations(
            frozen,
            [
                session_item(41, "C_JOB_B_PLATE_1_0", IDENTITY4),
                session_item(42, "C_JOB_B_PLATE_1_1", POSE_COMBINED),
            ],
        )
        by_label = {op["label"]: op for op in operations}
        self.assertEqual(by_label["plate_b"]["translation"], [0, 0, 0])
        self.assertEqual(by_label["plate_b_second"]["translation"], [50, 40, 10])
        self.assertEqual(
            by_label["plate_b_second"]["rotation_matrix"], [[0, 1, 0], [0, 0, 1], [1, 0, 0]]
        )

    def test_identical_session_names_do_not_collapse_occurrences(self):
        # Even within ONE API response, two occurrences may share a display
        # name; only occurrence_path keeps them apart.
        operations = rebuild_operations(
            self.FROZEN_SINGLE,
            [session_item(40, "dup_name", IDENTITY4)],
        )
        self.assertEqual(len(operations), 1)
        other = session_item(41, "dup_name", POSE_COMBINED)
        indexed = index_occurrences([session_item(40, "dup_name", IDENTITY4), other])
        self.assertEqual(indexed[(41,)]["name"], "dup_name")

    def test_nested_depth_is_rejected_not_guessed(self):
        with self.assertRaises(AssertionError):
            index_occurrences([session_item(40, SESSION_NAME, IDENTITY4, depth=1)])

    def test_component_id_must_match_frozen_feature_id(self):
        item = session_item(40, SESSION_NAME, IDENTITY4)
        item["component_id"] = 41
        with self.assertRaises(AssertionError):
            rebuild_operations(self.FROZEN_SINGLE, [item])

    def test_duplicate_occurrence_path_is_rejected(self):
        with self.assertRaises(AssertionError):
            index_occurrences(
                [session_item(40, SESSION_NAME, IDENTITY4), session_item(40, "other", IDENTITY4)]
            )

    def test_missing_or_empty_occurrence_path_is_rejected(self):
        item = session_item(40, SESSION_NAME, IDENTITY4)
        item["occurrence_path"] = []
        with self.assertRaises(AssertionError):
            index_occurrences([item])
        item2 = session_item(40, SESSION_NAME, IDENTITY4)
        del item2["occurrence_path"]
        with self.assertRaises(AssertionError):
            index_occurrences([item2])

    def test_unknown_mm_transform_is_rejected(self):
        item = session_item(40, SESSION_NAME, IDENTITY4)
        item["transform_mm_known"] = False
        with self.assertRaises(AssertionError):
            rebuild_operations(self.FROZEN_SINGLE, [item])


if __name__ == "__main__":
    unittest.main()
