"""DEV-047 T08: part feature lifecycle admission, identity and registries."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import feature_state, model_registry
from creo_mechdog.operation_results import annotate_native_result
from creo_mechdog.schema import validate_operations

NATIVE = Path(__file__).resolve().parents[2] / "native"


def native_source(name: str) -> str:
    return (NATIVE / name).read_text(encoding="utf-8")


def feature(
    feature_id: int,
    *,
    status: int = 0,
    type_name: str = "protrusion",
    parents: list[int] | None = None,
    children: list[int] | None = None,
    system_required: bool = False,
    group_status: int = 0,
    pattern_status: int = 0,
    grppattern_status: int = 0,
    incomplete: bool = False,
) -> dict:
    return {
        "id": feature_id,
        "status": status,
        "type_name": type_name,
        "name": f"FEATURE_{feature_id}",
        "parent_ids": list(parents or []),
        "child_ids": list(children or []),
        "parents_query_code": 0,
        "children_query_code": 0,
        "group_status": group_status,
        "pattern_status": pattern_status,
        "grppattern_status": grppattern_status,
        "embedded": False,
        "system_required": system_required,
        "incomplete": incomplete,
        "dimensions": [],
    }


def model(
    features: list[dict],
    *,
    aliases: dict | None = None,
    tombstones: dict | None = None,
    suppressed: dict | None = None,
    model_type: str = "part",
    with_inspection: bool = True,
) -> dict:
    record = {
        "model_id": "a" * 32,
        "model_name": "plate",
        "model_type": model_type,
        "revision": 3,
        "status": "ready",
        "aliases": aliases or {},
    }
    if with_inspection:
        record["inspection"] = {"features": features, "healthy": True}
    if tombstones is not None:
        record["feature_tombstones"] = tombstones
    if suppressed is not None:
        record["suppressed_features"] = suppressed
    return record


def sketch_plan(**kwargs) -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "profile",
            "plane": "XY",
            "entities": [{"type": "rectangle", "name": "box", "min": [0, 0], "max": [10, 8]}],
            **kwargs,
        }
    ]


class TargetSyntax(unittest.TestCase):
    def test_labels_ids_and_digit_strings_are_accepted(self):
        dumped = validate_operations(
            [{"op": "feature_state", "action": "delete", "targets": ["boss", 12, "9"]}]
        )
        self.assertEqual(dumped[0]["targets"], ["boss", 12, 9])

    def test_action_vocabulary_is_closed(self):
        for action in ("remove", "hide", "restore"):
            with self.subTest(action=action):
                with self.assertRaises(Exception):
                    validate_operations(
                        [{"op": "feature_state", "action": action, "targets": ["boss"]}]
                    )

    def test_empty_negative_boolean_and_bad_label_targets_are_refused(self):
        for targets in ([], [-1], [True], ["Boss"], ["bad-label"], [None]):
            with self.subTest(targets=targets):
                with self.assertRaises(Exception):
                    validate_operations(
                        [{"op": "feature_state", "action": "suppress", "targets": targets}]
                    )

    def test_duplicate_targets_are_refused_across_label_and_id_forms(self):
        with self.assertRaises(Exception):
            validate_operations(
                [{"op": "feature_state", "action": "delete", "targets": ["boss", "boss"]}]
            )
        with self.assertRaises(Exception):
            validate_operations([{"op": "feature_state", "action": "delete", "targets": [7, "7"]}])


class DependencyCoverage(unittest.TestCase):
    def setUp(self):
        self.features = [
            feature(1, type_name="sketch_or_curve"),
            feature(2, parents=[1], children=[3]),
            feature(3, type_name="cut", parents=[2]),
        ]
        self.record = model(
            self.features,
            aliases={
                "probe": {"feature_id": 1},
                "pad": {"feature_id": 2},
                "pocket": {"feature_id": 3},
            },
        )

    def test_missing_descendant_is_refused_with_the_dependency_list(self):
        with self.assertRaises(ValueError) as caught:
            feature_state.validate_plan(
                self.record,
                [{"op": "feature_state", "action": "delete", "targets": ["pad"]}],
            )
        message = str(caught.exception)
        self.assertIn("do not cover every affected dependency", message)
        self.assertIn("feature_id", message)
        self.assertIn("3", message)

    def test_explicit_full_target_set_is_accepted(self):
        feature_state.validate_plan(
            self.record,
            [{"op": "feature_state", "action": "delete", "targets": ["pad", 3]}],
        )

    def test_grouped_members_follow_their_header(self):
        features = [
            feature(1, group_status=0, children=[2]),
            feature(2, group_status=1, parents=[1]),
        ]
        record = model(features, aliases={"group_a": {"feature_id": 1}})
        # The member cannot be an independent target, so the header operation
        # covers it instead of demanding an impossible explicit entry.
        feature_state.validate_plan(
            record, [{"op": "feature_state", "action": "suppress", "targets": ["group_a"]}]
        )

    def test_individual_group_and_pattern_members_are_refused(self):
        for number, updates in ((1, {"group_status": 1}), (2, {"pattern_status": 2})):
            with self.subTest(member=number):
                features = [feature(5, **updates)]
                record = model(features, aliases={"member": {"feature_id": 5}})
                with self.assertRaises(ValueError) as caught:
                    feature_state.validate_plan(
                        record,
                        [{"op": "feature_state", "action": "suppress", "targets": ["member"]}],
                    )
                self.assertIn("member", str(caught.exception))

    def test_system_required_objects_are_refused(self):
        record = model(
            [feature(1, type_name="datum_plane", system_required=True)],
            aliases={"front": {"feature_id": 1}},
        )
        with self.assertRaises(ValueError) as caught:
            feature_state.validate_plan(
                record, [{"op": "feature_state", "action": "delete", "targets": ["front"]}]
            )
        self.assertIn("system-required", str(caught.exception))

    def test_unknown_and_absent_targets_are_refused(self):
        with self.assertRaises(ValueError):
            feature_state.validate_plan(
                self.record,
                [{"op": "feature_state", "action": "delete", "targets": ["missing"]}],
            )
        with self.assertRaises(ValueError):
            feature_state.validate_plan(
                self.record, [{"op": "feature_state", "action": "delete", "targets": [99]}]
            )


class Tombstones(unittest.TestCase):
    def test_deleted_label_is_refused_for_targets_references_and_new_features(self):
        record = model(
            [feature(1), feature(2)],
            aliases={"keep": {"feature_id": 1}},
            tombstones={
                "probe": {
                    "feature_id": 2,
                    "label": "probe",
                    "type_name": "sketch_or_curve",
                    "job_id": "b" * 32,
                }
            },
        )
        self.assertEqual(feature_state.tombstone_labels(record), {"probe"})
        with self.assertRaises(ValueError) as caught:
            feature_state.validate_plan(
                record, [{"op": "feature_state", "action": "delete", "targets": ["probe"]}]
            )
        self.assertIn("tombstone", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            feature_state.validate_plan(
                record, [{"op": "feature_state", "action": "delete", "targets": [2]}]
            )
        self.assertIn("deleted", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            feature_state.reject_tombstoned_labels(record, sketch_plan(label="probe"))
        self.assertIn("deleted labels cannot be reused", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            feature_state.reject_tombstoned_labels(
                record,
                [
                    {
                        "op": "hole",
                        "label": "hole_1",
                        "placement": {"kind": "feature", "label": "probe"},
                    }
                ],
            )
        self.assertIn("cannot be referenced", str(caught.exception))

    def test_new_labels_not_in_the_registry_are_unaffected(self):
        record = model([feature(1)], aliases={"keep": {"feature_id": 1}})
        feature_state.reject_tombstoned_labels(record, sketch_plan(label="fresh"))
        feature_state.reject_tombstoned_labels(None, sketch_plan(label="fresh"))

    def test_registry_is_persisted_only_from_a_valid_result(self):
        record = model([feature(1)])
        feature_state.apply_result(
            record,
            {
                "feature_tombstones": {"old": {"feature_id": 4, "label": "old"}},
                "suppressed_features": {},
            },
        )
        self.assertIn("old", record["feature_tombstones"])
        with self.assertRaises(ValueError):
            feature_state.apply_result(record, {"feature_tombstones": {"bad": {"label": "x"}}})
        with self.assertRaises(ValueError):
            feature_state.apply_result(record, {"suppressed_features": []})


class SuppressionRegistry(unittest.TestCase):
    def test_recorded_suppression_must_actually_be_suppressed(self):
        record = model(
            [feature(1, status=0)],
            suppressed={"pad": {"feature_id": 1, "label": "pad"}},
        )
        issues = feature_state.registry_issues(record)
        self.assertEqual(len(issues), 1)
        self.assertIn("not suppressed", issues[0])
        with self.assertRaises(ValueError) as caught:
            feature_state.validate_plan(
                record, [{"op": "feature_state", "action": "resume", "targets": [1]}]
            )
        self.assertIn("does not match", str(caught.exception))

    def test_unrecorded_suppression_is_refused(self):
        record = model([feature(1, status=5)])
        self.assertTrue(
            any("not recorded" in issue for issue in feature_state.registry_issues(record))
        )
        with self.assertRaises(ValueError):
            feature_state.validate_plan(
                record, [{"op": "feature_state", "action": "suppress", "targets": [1]}]
            )

    def test_recorded_and_actual_suppression_is_consistent(self):
        record = model(
            [feature(1, status=5)],
            suppressed={"pad": {"feature_id": 1, "label": "pad"}},
        )
        self.assertEqual(feature_state.registry_issues(record), [])
        feature_state.validate_plan(
            record, [{"op": "feature_state", "action": "resume", "targets": [1]}]
        )

    def test_missing_suppressed_feature_is_reported(self):
        record = model(
            [feature(2)],
            suppressed={"gone": {"feature_id": 1, "label": "gone"}},
        )
        self.assertTrue(any("absent" in issue for issue in feature_state.registry_issues(record)))


class ResumeBoundaries(unittest.TestCase):
    def test_resume_requires_suppressed_targets_only(self):
        record = model([feature(1, status=0)], aliases={"pad": {"feature_id": 1}})
        with self.assertRaises(ValueError) as caught:
            feature_state.validate_plan(
                record, [{"op": "feature_state", "action": "resume", "targets": ["pad"]}]
            )
        self.assertIn("not suppressed", str(caught.exception))

    def test_repeated_suppression_is_refused(self):
        record = model(
            [feature(1, status=5)],
            aliases={"pad": {"feature_id": 1}},
            suppressed={"pad": {"feature_id": 1}},
        )
        with self.assertRaises(ValueError) as caught:
            feature_state.validate_plan(
                record, [{"op": "feature_state", "action": "suppress", "targets": ["pad"]}]
            )
        self.assertIn("already suppressed", str(caught.exception))

    def test_resume_requires_suppressed_parents_in_the_same_request(self):
        features = [
            feature(1, type_name="sketch_or_curve", status=5, children=[2]),
            feature(2, status=5, parents=[1]),
        ]
        record = model(
            features,
            suppressed={"probe": {"feature_id": 1}, "pad": {"feature_id": 2}},
        )
        with self.assertRaises(ValueError) as caught:
            feature_state.validate_plan(
                record, [{"op": "feature_state", "action": "resume", "targets": [2]}]
            )
        self.assertIn("suppressed parents", str(caught.exception))
        feature_state.validate_plan(
            record, [{"op": "feature_state", "action": "resume", "targets": [1, 2]}]
        )


class AssemblyBoundary(unittest.TestCase):
    def test_assembly_and_drawing_models_are_refused(self):
        for model_type in ("assembly", "drawing"):
            with self.subTest(model_type=model_type):
                record = model(
                    [feature(1)], aliases={"part1": {"feature_id": 1}}, model_type=model_type
                )
                with self.assertRaises(ValueError) as caught:
                    feature_state.validate_plan(
                        record,
                        [{"op": "feature_state", "action": "delete", "targets": ["part1"]}],
                    )
                self.assertIn("remove_component", str(caught.exception))

    def test_missing_inspection_is_refused_without_guessing(self):
        record = model([], with_inspection=False, aliases={"pad": {"feature_id": 1}})
        with self.assertRaises(ValueError) as caught:
            feature_state.validate_plan(
                record, [{"op": "feature_state", "action": "delete", "targets": ["pad"]}]
            )
        self.assertIn("inspection", str(caught.exception))


class ResultContract(unittest.TestCase):
    def test_target_detail_stays_inside_one_operation_record(self):
        operation = {
            "op": "feature_state",
            "index": 0,
            "succeeded": True,
            "execution_status": "succeeded",
            "targets": [
                {
                    "target": "pad",
                    "feature_id": 2,
                    "before": {"status": 0, "suppressed": False},
                    "after": {"status": 5, "suppressed": True},
                    "effect": "suppressed",
                }
            ],
        }
        result = {
            "success": True,
            "operations": [operation],
            "feature_tombstones": {},
            "suppressed_features": {"pad": {"feature_id": 2}},
        }
        annotated = annotate_native_result(
            result,
            readonly=False,
            inputs=[{"op": "feature_state", "action": "suppress", "targets": ["pad"]}],
        )
        self.assertEqual(len(annotated["operations"]), 1)
        self.assertEqual(annotated["operations"][0]["effect_status"], "committed")
        self.assertEqual(annotated["operations"][0]["target_count"], 1)
        self.assertTrue(annotated["operations"][0]["targets_complete"])

    def test_missing_native_detail_is_never_fabricated(self):
        result = {
            "success": True,
            "operations": [{"op": "feature_state", "index": 0, "succeeded": True}],
        }
        annotate_native_result(
            result,
            readonly=False,
            inputs=[{"op": "feature_state", "action": "delete", "targets": ["pad"]}],
        )
        self.assertNotIn("targets", result["operations"][0])
        self.assertNotIn("target_count", result["operations"][0])

    def test_compact_projection_keeps_feature_state_fields(self):
        manifest = {
            "result": {
                "operations": [
                    {
                        "op": "feature_state",
                        "index": 0,
                        "succeeded": True,
                        "execution_status": "succeeded",
                        "effect_status": "committed",
                        "feature_state": {"action": "delete", "applied": 1},
                        "targets": [{"feature_id": 2, "effect": "deleted"}],
                        "target_count": 1,
                        "requested_target_count": 1,
                        "targets_complete": True,
                    }
                ],
                "feature_tombstones": {"pad": {"feature_id": 2}},
                "suppressed_features": {},
            }
        }
        compact = bridge.compact_job(manifest)
        operation = compact["result"]["operations"][0]
        self.assertEqual(operation["feature_state"]["action"], "delete")
        self.assertEqual(operation["targets"][0]["effect"], "deleted")
        self.assertEqual(compact["result"]["feature_tombstones"]["pad"]["feature_id"], 2)
        self.assertEqual(compact["result"]["suppressed_features"], {})


class SubmitAdmission(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dev047_t08_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "jobs").mkdir()
        (self.root / "models").mkdir()
        stack = ExitStack()
        self.addCleanup(stack.close)
        for obj, name, value in (
            (bridge, "ROOT", self.root),
            (bridge, "JOBS", self.root / "jobs"),
            (general, "MODELS", self.root / "models"),
        ):
            stack.enter_context(patch.object(obj, name, value))
        self.model_id = "c" * 32
        path = general.model_path(self.model_id)
        (path / "output").mkdir(parents=True)
        self.part = path / "output" / "plate.prt.1"
        self.part.write_bytes(b"native part bytes")
        features = [
            feature(1, type_name="sketch_or_curve", children=[2]),
            feature(2, parents=[1], children=[3]),
            feature(3, type_name="cut", parents=[2]),
        ]
        self.record = {
            "model_id": self.model_id,
            "model_name": "plate",
            "model_type": "part",
            "revision": 1,
            "status": "ready",
            "aliases": {"pad": {"feature_id": 2}, "pocket": {"feature_id": 3}},
            "inspection": {"features": features, "healthy": True},
            "part_file": str(self.part),
            "part_sha256": hashlib.sha256(self.part.read_bytes()).hexdigest(),
            "output_directory": str(path / "output"),
        }
        model_registry.write_model(path, self.record)

    def test_dependency_refusal_creates_no_job(self):
        with self.assertRaises(ValueError) as caught:
            general.submit(
                [{"op": "feature_state", "action": "delete", "targets": ["pad"]}],
                model_id=self.model_id,
                expected_revision=1,
            )
        self.assertIn("do not cover every affected dependency", str(caught.exception))
        self.assertEqual(list((self.root / "jobs").iterdir()), [])
        self.assertIsNone(general.model_info(self.model_id).get("pending_job"))

    def test_tombstoned_label_refusal_creates_no_job(self):
        record = general.model_info(self.model_id)
        record["feature_tombstones"] = {"probe": {"feature_id": 9, "label": "probe"}}
        model_registry.write_model(general.model_path(self.model_id), record)
        with self.assertRaises(ValueError) as caught:
            general.submit(
                sketch_plan(label="probe"),
                model_id=self.model_id,
                expected_revision=1,
            )
        self.assertIn("tombstone", str(caught.exception))
        self.assertEqual(list((self.root / "jobs").iterdir()), [])

    def test_registry_is_written_back_after_a_successful_feature_state_job(self):
        model = general.model_info(self.model_id)
        directory = bridge.job_path("f" * 32)
        (directory / "output").mkdir(parents=True)
        pending = dict(model, pending_job="f" * 32)
        model_registry.write_model(general.model_path(self.model_id), pending)
        request = {
            "new": False,
            "model": general._request_view(pending),
            "operations": [
                {"op": "feature_state", "action": "delete", "targets": ["pad", "pocket"]}
            ],
            "readonly": False,
            "components": {},
        }
        bridge.write_json(directory / "request.json", request)
        result = {
            "success": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "saved_file_reloaded_and_verified": True,
            "part_file": str(self.part),
            "aliases": {"pocket": {"feature_id": 3}},
            "inspection": {
                "features": [feature(1, children=[]), feature(3, type_name="cut")],
                "healthy": True,
            },
            "operations": [
                {
                    "op": "feature_state",
                    "index": 0,
                    "succeeded": True,
                    "targets": [{"feature_id": 2}, {"feature_id": 3}],
                }
            ],
            "feature_tombstones": {
                "pad": {"feature_id": 2, "label": "pad"},
                "pocket": {"feature_id": 3, "label": "pocket"},
            },
            "suppressed_features": {},
        }

        def fake_run(*args, **kwargs):
            bridge.write_json(directory / "native_result.json", result)
            return bridge.subprocess.CompletedProcess([], 0)

        with (
            patch.object(bridge.subprocess, "run", side_effect=fake_run),
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe"),
            patch.object(bridge, "native_environment", return_value={}),
            patch.object(bridge, "note_native_outcome", return_value=None),
            patch.object(bridge, "config", return_value={}),
        ):
            general.run_generic_job("f" * 32, {"job_id": "f" * 32, "kind": "generic"})
        stored = general.model_info(self.model_id)
        self.assertEqual(stored["revision"], 2)
        self.assertEqual(stored["feature_tombstones"]["pad"]["feature_id"], 2)
        self.assertEqual(stored["suppressed_features"], {})
        manifest = bridge.read_json(directory / "job.json")
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["result"]["feature_tombstones"]["pocket"]["feature_id"], 3)


class NativeContract(unittest.TestCase):
    def test_native_operation_is_implemented_once_without_cascade_options(self):
        source = native_source("feature_state.cpp")
        self.assertIn("ProFeatureWithoptionsDelete", source)
        self.assertIn("ProFeatureWithoptionsSuppress", source)
        self.assertIn("ProFeatureWithoptionsResume", source)
        self.assertIn("PRO_FEAT_DELETE_NO_OPTS", source)
        self.assertIn("PRO_FEAT_RESUME_NO_OPTS", source)
        # No auto-cascade flags: affected children must be explicit targets.
        for flag in (
            "PRO_FEAT_DELETE_CLIP",
            "PRO_FEAT_DELETE_FIX",
            "PRO_FEAT_DELETE_CLIP_ALL",
            "PRO_FEAT_RESUME_INCLUDE_PARENTS",
        ):
            with self.subTest(flag=flag):
                self.assertNotIn(flag, source)
        self.assertIn("do not cover every affected dependency", source)
        self.assertIn("system-required", source)
        self.assertIn("group/pattern member", source)

    def test_dispatch_and_registry_field_names_are_wired(self):
        generic = native_source("generic.cpp")
        self.assertIn('kind == "feature_state"', generic)
        self.assertIn("generic_feature_state", generic)
        self.assertIn('"feature_tombstones"', generic)
        self.assertIn('"suppressed_features"', generic)
        self.assertIn("ProFeatureParentsGet", generic)
        self.assertIn("ProFeatureChildrenGet", generic)
        self.assertIn("SUPPRESSION_REGISTRY_MISMATCH", generic)
        self.assertIn("Saved feature status does not match the requested feature_state", generic)

    def test_python_module_is_part_of_the_public_capability_surface(self):
        from capabilities import REGISTERED_OPERATIONS, families

        self.assertIn("feature_state", REGISTERED_OPERATIONS)
        self.assertEqual(
            families()["feature_lifecycle"]["actions"], ["delete", "suppress", "resume"]
        )


class RegistrySection(unittest.TestCase):
    def test_model_summary_exposes_the_registries(self):
        from creo_mechdog.model_queries import model_summary

        record = model(
            [feature(1, status=5)],
            aliases={"pad": {"feature_id": 1}},
            tombstones={"probe": {"feature_id": 9}},
            suppressed={"pad": {"feature_id": 1}},
        )
        summary = model_summary(record)
        self.assertEqual(summary["feature_state"]["tombstone_count"], 1)
        self.assertEqual(summary["feature_state"]["suppressed_count"], 1)
        self.assertEqual(summary["feature_state"]["suppressed"]["pad"]["feature_id"], 1)
        # The registries stay bounded: small dicts, no detail payloads.
        self.assertLess(
            len(json.dumps(summary["feature_state"], ensure_ascii=False).encode("utf-8")),
            2048,
        )


if __name__ == "__main__":
    unittest.main()
