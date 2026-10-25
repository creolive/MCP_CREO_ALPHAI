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
        )
        self.assertEqual(
            summary["changes"], [{"op": "removed", "label": "pin_a", "feature_id": 51}]
        )

    def test_rolled_back_lists_requests_without_claiming_effect(self):
        summary = component_changes.summarize(
            [ADD, MOVE, CONSTRAIN, REMOVE],
            job_status="failed",
            prior_aliases={"pin_a": {"feature_id": 51}},
        )
        self.assertEqual(summary["status"], "rolled_back")
        self.assertEqual(
            [change["op"] for change in summary["changes"]],
            ["added", "moved", "constraints_changed", "removed"],
        )
        self.assertNotIn("feature_id", summary["changes"][0])

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
            "aliases": {"pin_a": {"op": "assemble_component", "feature_id": 51}},
            "inspection": {"components": [{"feature_id": 51, "transform": None}]},
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


if __name__ == "__main__":
    unittest.main()
