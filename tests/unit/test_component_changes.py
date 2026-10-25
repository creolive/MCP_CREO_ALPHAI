"""FEAT-008 component change summary regressions (batch 2 stage 2)."""

import copy
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import component_changes, model_registry


def op(kind, **kwargs):
    return {"op": kind, **kwargs}


ADD = op("assemble_component", label="pin_a", source_model_id="a" * 32, translation=[0, 0, 0])
MOVE = op("component_placement", component="pin_a", translation=[1, 0, 0])
CONSTRAIN = op("component_constraints", component="pin_a", constraints=[])
REMOVE = op("remove_component", component="pin_a")
EXTRUDE = op("extrude", label="solid", sketch="profile", depth=5)


class SummarizeContract(unittest.TestCase):
    def test_no_component_operations_returns_none(self):
        self.assertIsNone(component_changes.summarize([EXTRUDE], job_status="succeeded"))

    def test_committed_add_uses_native_alias_identities(self):
        summary = component_changes.summarize(
            [ADD],
            job_status="succeeded",
            result_aliases={
                "pin_a": {"op": "assemble_component", "feature_id": 51, "source_revision": 3}
            },
        )
        self.assertEqual(summary["status"], "committed")
        self.assertEqual(
            summary["changes"],
            [
                {
                    "op": "added",
                    "label": "pin_a",
                    "feature_id": 51,
                    "source_model_id": "a" * 32,
                    "source_revision": 3,
                }
            ],
        )

    def test_committed_move_carries_queried_from_to_transforms(self):
        prior = {
            "components": [
                {
                    "feature_id": 51,
                    "transform": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                }
            ]
        }
        new = {
            "components": [
                {
                    "feature_id": 51,
                    "transform": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [9, 0, 0, 1]],
                }
            ]
        }
        summary = component_changes.summarize(
            [MOVE],
            job_status="succeeded",
            prior_aliases={"pin_a": {"feature_id": 51}},
            prior_inspection=prior,
            result_aliases={"pin_a": {"feature_id": 51}},
            result_inspection=new,
        )
        change = summary["changes"][0]
        self.assertEqual(change["op"], "moved")
        self.assertEqual(change["label"], "pin_a")
        self.assertEqual(change["from"][3][:3], [0, 0, 0])
        self.assertEqual(change["to"][3][:3], [9, 0, 0])

    def test_committed_remove_resolves_label_from_prior_alias_feature_id(self):
        summary = component_changes.summarize(
            [op("remove_component", component=51)],
            job_status="succeeded",
            prior_aliases={"pin_a": {"feature_id": 51}},
            result_aliases={},
        )
        self.assertEqual(
            summary["changes"], [{"op": "removed", "label": "pin_a", "feature_id": 51}]
        )

    def test_add_then_move_in_one_job_reports_only_added(self):
        # Net semantics: the component did not exist before the job, so the
        # only verified net change is the add — not add + a spurious moved.
        summary = component_changes.summarize(
            [ADD, MOVE],
            job_status="succeeded",
            result_aliases={"pin_a": {"feature_id": 77, "source_revision": 2}},
            result_inspection={
                "components": [
                    {
                        "feature_id": 77,
                        "transform": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 1]],
                    }
                ]
            },
        )
        self.assertEqual(
            summary["changes"],
            [
                {
                    "op": "added",
                    "label": "pin_a",
                    "feature_id": 77,
                    "source_model_id": "a" * 32,
                    "source_revision": 2,
                }
            ],
        )

    def test_add_then_remove_in_one_job_reports_no_net_change(self):
        summary = component_changes.summarize(
            [ADD, REMOVE],
            job_status="succeeded",
            prior_aliases={},
            result_aliases={},
        )
        self.assertEqual(summary["status"], "committed")
        self.assertEqual(summary["changes"], [])

    def test_consecutive_moves_report_single_net_move(self):
        transform_a = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        transform_b = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [5, 0, 0, 1]]
        transform_c = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [9, 0, 0, 1]]
        summary = component_changes.summarize(
            [MOVE, MOVE],
            job_status="succeeded",
            prior_aliases={"pin_a": {"feature_id": 51}},
            prior_inspection={"components": [{"feature_id": 51, "transform": transform_a}]},
            result_aliases={"pin_a": {"feature_id": 51}},
            result_inspection={"components": [{"feature_id": 51, "transform": transform_c}]},
        )
        self.assertEqual(
            summary["changes"],
            [
                {
                    "op": "moved",
                    "label": "pin_a",
                    "feature_id": 51,
                    "from": transform_a,
                    "to": transform_c,
                }
            ],
        )
        self.assertNotEqual(summary["changes"][0]["from"], transform_b)

    def test_remove_reinsert_then_move_reports_old_removed_new_added(self):
        # The move after the reinsert concerns the NEW identity; the removed
        # entry must keep the OLD identity and no moved entry may use it.
        summary = component_changes.summarize(
            [REMOVE, ADD, MOVE],
            job_status="succeeded",
            prior_aliases={"pin_a": {"feature_id": 51}},
            prior_inspection={
                "components": [
                    {
                        "feature_id": 51,
                        "transform": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                    }
                ]
            },
            result_aliases={"pin_a": {"feature_id": 77, "source_revision": 4}},
            result_inspection={
                "components": [
                    {
                        "feature_id": 77,
                        "transform": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [9, 0, 0, 1]],
                    }
                ]
            },
        )
        removed, added = summary["changes"]
        self.assertEqual(removed, {"op": "removed", "label": "pin_a", "feature_id": 51})
        self.assertEqual(added["op"], "added")
        self.assertEqual(added["feature_id"], 77)

    def test_committed_without_verified_result_aliases_raises(self):
        with self.assertRaises(ValueError):
            component_changes.summarize([ADD], job_status="succeeded")

    def test_rolled_back_requires_confirmed_native_rollback(self):
        summary = component_changes.summarize(
            [ADD, MOVE, CONSTRAIN, REMOVE],
            job_status="failed",
            rollback={"rollback_succeeded": True, "failed_stage": "executing_feature_plan"},
            executed=True,
            prior_aliases={"pin_a": {"feature_id": 51}},
        )
        self.assertEqual(summary["status"], "rolled_back")
        self.assertEqual(
            [change["op"] for change in summary["changes"]],
            ["added", "moved", "constraints_changed", "removed"],
        )
        self.assertNotIn("feature_id", summary["changes"][0])

    def test_busy_rejection_is_no_effect_not_rolled_back(self):
        summary = component_changes.summarize([ADD], job_status="failed", executed=False)
        self.assertEqual(summary["status"], "no_effect")
        self.assertEqual(summary["changes"], [])
        self.assertIn("never executed", summary["note"])

    def test_preflight_refusal_model_unchanged_is_no_effect(self):
        summary = component_changes.summarize(
            [ADD],
            job_status="failed",
            rollback={"model_unchanged": True, "failed_stage": "callback_preflight"},
            executed=True,
        )
        self.assertEqual(summary["status"], "no_effect")
        self.assertEqual(summary["changes"], [])

    def test_failed_after_execution_without_rollback_evidence_stays_unknown(self):
        summary = component_changes.summarize(
            [ADD],
            job_status="failed",
            rollback={"failed_stage": "executing_feature_plan"},
            executed=True,
        )
        self.assertEqual(summary["status"], "unknown_outcome")
        self.assertEqual(summary["changes"], [])
        self.assertIn("rollback is unconfirmed", summary["note"])

    def test_remove_and_reinsert_same_label_keeps_both_identities(self):
        summary = component_changes.summarize(
            [REMOVE, ADD],
            job_status="succeeded",
            prior_aliases={"pin_a": {"feature_id": 51}},
            result_aliases={"pin_a": {"feature_id": 77, "source_revision": 4}},
        )
        removed, added = summary["changes"]
        self.assertEqual(removed, {"op": "removed", "label": "pin_a", "feature_id": 51})
        self.assertEqual(added["op"], "added")
        self.assertEqual(added["feature_id"], 77)
        self.assertEqual(added["source_revision"], 4)

    def test_unknown_outcome_reports_no_change(self):
        summary = component_changes.summarize([ADD], job_status="unknown_outcome")
        self.assertEqual(summary["status"], "unknown_outcome")
        self.assertEqual(summary["changes"], [])


class RunJobAttachment(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="feat008_changes_")
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
        stack.enter_context(
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe")
        )
        self.model_id = "b" * 32
        path = general.model_path(self.model_id)
        (path / "output").mkdir(parents=True)
        self.part = path / "output" / "asm.asm.1"
        self.part.write_bytes(b"native assembly bytes")
        model = {
            "model_id": self.model_id,
            "model_name": "demo_asm",
            "revision": 1,
            "status": "ready",
            "model_type": "assembly",
            "aliases": {},
            "inspection": {"components": []},
            "part_file": str(self.part),
            "output_directory": str(path / "output"),
        }
        model_registry.write_model(path, model)
        self.job_id = "c" * 32
        directory = bridge.job_path(self.job_id)
        (directory / "output").mkdir(parents=True)
        self.request = {
            "new": False,
            "model": {k: model[k] for k in ("model_id", "model_name", "model_type", "revision")},
            "operations": [ADD],
            "readonly": False,
            "components": {},
        }
        bridge.write_json(directory / "request.json", self.request)
        self.manifest = {
            "job_id": self.job_id,
            "kind": "generic",
            "model_id": self.model_id,
            "status": "queued",
        }
        bridge.write_json(directory / "job.json", self.manifest)

    def run_worker(self, result):
        directory = bridge.job_path(self.job_id)

        def fake_run(*args, **kwargs):
            bridge.write_json(directory / "native_result.json", result)
            return subprocess.CompletedProcess([], 0)

        with (
            patch.object(bridge.subprocess, "run", side_effect=fake_run),
            patch.object(bridge, "native_environment", return_value={}),
            patch.object(bridge, "note_native_outcome", return_value=None),
            patch.object(bridge, "config", return_value={}),
        ):
            general.run_generic_job(self.job_id, copy.deepcopy(self.manifest))
        return bridge.read_json(directory / "job.json")

    def test_success_attaches_committed_changes(self):
        result = {
            "success": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "saved_file_reloaded_and_verified": True,
            "part_file": str(self.part),
            "aliases": {
                "pin_a": {"op": "assemble_component", "feature_id": 77, "source_revision": 2}
            },
            "inspection": {"components": [{"feature_id": 77}]},
        }
        manifest = self.run_worker(result)
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["revision"], 2)
        self.assertEqual(
            manifest["component_changes"],
            {
                "status": "committed",
                "changes": [
                    {
                        "op": "added",
                        "label": "pin_a",
                        "feature_id": 77,
                        "source_model_id": "a" * 32,
                        "source_revision": 2,
                    }
                ],
            },
        )

    def test_failure_marks_changes_rolled_back(self):
        result = {
            "success": False,
            "delivery_complete": True,
            "disconnect_code": 0,
            "rollback_succeeded": True,
            "message": "Toolkit call failed",
        }
        manifest = self.run_worker(result)
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["component_changes"]["status"], "rolled_back")
        self.assertEqual(
            manifest["component_changes"]["changes"],
            [{"op": "added", "label": "pin_a"}],
        )

    def test_unknown_outcome_never_reports_committed_changes(self):
        result = {
            "success": False,
            "delivery_complete": False,
            "disconnect_code": 9,
            "message": "unconfirmed",
        }
        manifest = self.run_worker(result)
        self.assertEqual(manifest["status"], "unknown_outcome")
        self.assertEqual(manifest["component_changes"]["status"], "unknown_outcome")
        self.assertEqual(manifest["component_changes"]["changes"], [])

    def test_busy_rejection_reports_no_effect(self):
        directory = bridge.job_path(self.job_id)
        with patch.object(
            bridge, "toolkit_lock", side_effect=bridge.ToolkitBusy(holder={"operation": "other"})
        ):
            general.run_generic_job(self.job_id, copy.deepcopy(self.manifest))
        manifest = bridge.read_json(directory / "job.json")
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["component_changes"]["status"], "no_effect")
        self.assertEqual(manifest["component_changes"]["changes"], [])
        self.assertIn("busy", manifest)

    def test_busy_rejection_with_broken_sidecar_keeps_no_effect_semantics(self):
        # The pre-job snapshot read failure is auxiliary: a status that never
        # uses the prior state (busy rejection) must keep its original
        # semantics instead of being masked as unavailable.
        directory = bridge.job_path(self.job_id)
        with (
            patch.object(
                model_registry,
                "aliases_of",
                side_effect=ValueError("synthetic broken alias sidecar"),
            ),
            patch.object(
                bridge,
                "toolkit_lock",
                side_effect=bridge.ToolkitBusy(holder={"operation": "other"}),
            ),
        ):
            general.run_generic_job(self.job_id, copy.deepcopy(self.manifest))
        manifest = bridge.read_json(directory / "job.json")
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["component_changes"]["status"], "no_effect")
        self.assertEqual(manifest["component_changes"]["changes"], [])

    def test_summary_failure_marks_unavailable_but_preserves_terminal_state(self):
        result = {
            "success": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "saved_file_reloaded_and_verified": True,
            "part_file": str(self.part),
            "aliases": {
                "pin_a": {"op": "assemble_component", "feature_id": 77, "source_revision": 2}
            },
            "inspection": {"components": [{"feature_id": 77}]},
        }
        with patch.object(
            component_changes, "summarize", side_effect=RuntimeError("synthetic summary fault")
        ):
            manifest = self.run_worker(result)
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["revision"], 2)
        self.assertEqual(manifest["component_changes"]["status"], "unavailable")
        self.assertIn("synthetic summary fault", manifest["component_changes"]["error"])
        self.assertTrue(manifest["finished_at"])

    def test_plain_job_has_no_summary_key(self):
        directory = bridge.job_path(self.job_id)
        self.request["operations"] = [EXTRUDE]
        bridge.write_json(directory / "request.json", self.request)
        result = {
            "success": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "saved_file_reloaded_and_verified": True,
            "part_file": str(self.part),
        }
        manifest = self.run_worker(result)
        self.assertEqual(manifest["status"], "succeeded")
        self.assertNotIn("component_changes", manifest)

    def test_plain_job_never_hydrates_alias_sidecars(self):
        # Regression for the batch-2 stage-3 defect: aliases_of/inspection_of
        # ran unconditionally before the worker, so a broken alias sidecar on
        # a model aborted even jobs that never touched a component. Plain
        # jobs must not read the sidecars at all.
        directory = bridge.job_path(self.job_id)
        self.request["operations"] = [EXTRUDE]
        bridge.write_json(directory / "request.json", self.request)
        result = {
            "success": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "saved_file_reloaded_and_verified": True,
            "part_file": str(self.part),
        }
        with patch.object(
            model_registry,
            "aliases_of",
            side_effect=AssertionError("plain jobs must not hydrate aliases"),
        ):
            manifest = self.run_worker(result)
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["revision"], 2)
        self.assertNotIn("component_changes", manifest)

    def test_summary_sidecar_read_failure_degrades_to_unavailable(self):
        # A read that exists ONLY for the summary must downgrade the summary
        # to unavailable without touching the confirmed terminal state.
        result = {
            "success": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "saved_file_reloaded_and_verified": True,
            "part_file": str(self.part),
            "aliases": {
                "pin_a": {"op": "assemble_component", "feature_id": 77, "source_revision": 2}
            },
            "inspection": {"components": [{"feature_id": 77}]},
        }
        with patch.object(
            model_registry,
            "aliases_of",
            side_effect=ValueError("synthetic auxiliary sidecar fault"),
        ):
            manifest = self.run_worker(result)
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["revision"], 2)
        self.assertEqual(manifest["component_changes"]["status"], "unavailable")
        self.assertIn("synthetic auxiliary sidecar fault", manifest["component_changes"]["error"])
        self.assertTrue(manifest["finished_at"])

    def test_committed_summary_without_result_aliases_is_unavailable(self):
        # The verified post-state did not reach the summary; identities must
        # never be invented, so the summary is unavailable, not guessed.
        result = {
            "success": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "saved_file_reloaded_and_verified": True,
            "part_file": str(self.part),
        }
        manifest = self.run_worker(result)
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["revision"], 2)
        self.assertEqual(manifest["component_changes"]["status"], "unavailable")
        self.assertIn("verified result aliases", manifest["component_changes"]["error"])


if __name__ == "__main__":
    unittest.main()
