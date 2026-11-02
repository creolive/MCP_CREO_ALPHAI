"""BUG-105: zero-mutation acknowledgement and failure-status attribution.

Covers the metadata-only ``ack_no_mutation`` recovery action (no Toolkit, no
worker, no file writes) and the rule that a failed native job keeps a saved
model ready only when nothing was dispatched. No Creo is contacted.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import reconciliation as rec


class AckFixture(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(folder)
        self.enterContext(patch.object(bridge, "ROOT", self.root))
        self.enterContext(patch.object(bridge, "JOBS", self.root / "jobs"))
        self.enterContext(patch.object(bridge, "config", return_value={}))
        self.enterContext(patch.object(general, "MODELS", self.root / "models"))
        self.enterContext(patch.object(rec, "_deployment", return_value="fixture-deployment"))
        self.enterContext(
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe")
        )
        self.model_id = "a" * 32
        self.failed_job = "b" * 32
        output = general.model_path(self.model_id) / "output"
        output.mkdir(parents=True)
        self.file = output / "wb_asm.asm.3"
        self.file.write_bytes(b"verified assembly checkpoint fixture")
        self.model = {
            "model_id": self.model_id,
            "model_name": "wb_asm",
            "model_type": "assembly",
            "revision": 5,
            "status": "failed",
            "aliases": {},
            "inspection": {"healthy": True, "model_type": "assembly", "components": []},
            "output_directory": str(output),
            "part_file": str(self.file),
            "part_sha256": hashlib.sha256(self.file.read_bytes()).hexdigest(),
            "last_job": self.failed_job,
            "pending_job": None,
            "rollback_status": "succeeded",
        }
        self.save()
        directory = bridge.job_path(self.failed_job)
        directory.mkdir(parents=True)
        bridge.write_json(
            directory / "job.json",
            {
                "job_id": self.failed_job,
                "model_id": self.model_id,
                "kind": "generic",
                "status": "failed",
                "worker_started": False,
                "created_at": bridge.now(),
                "runner_identity": {"pid": 2147483647, "created": 11},
            },
        )
        bridge.write_json(directory / "request.json", {"model": {"model_id": self.model_id}})

    def save(self):
        bridge.write_json(general.model_path(self.model_id) / "model.json", self.model)

    def inspect(self):
        return rec.inspect(self.model_id)

    def apply_ack(self, token, key="ack_fixture_1", confirm=True, revision=None):
        return rec.apply(
            self.model_id,
            "ack_no_mutation",
            self.model["revision"] if revision is None else revision,
            None,
            token,
            key,
            confirm,
        )


class ZeroMutationAck(AckFixture):
    def test_assembly_and_drawing_models_can_acknowledge(self):
        for model_type, extension in (("assembly", "asm"), ("drawing", "drw")):
            owned = general.model_path(self.model_id) / "output" / f"wb_asm.{extension}.3"
            owned.write_bytes(self.file.read_bytes())
            self.model["model_type"] = model_type
            self.model["part_file"] = str(owned)
            self.model["part_sha256"] = hashlib.sha256(owned.read_bytes()).hexdigest()
            self.save()
            actions = self.inspect()["actions"]
            self.assertTrue(
                actions["ack_no_mutation"]["available"],
                f"{model_type}: {actions['ack_no_mutation']['reason']}",
            )
            self.assertFalse(actions["restore_baseline"]["available"], model_type)
            self.assertIn("component ownership", actions["restore_baseline"]["reason"])

    def test_confirmation_flag_is_required(self):
        token = self.inspect()["evidence_token"]
        with self.assertRaises(ValueError) as caught:
            self.apply_ack(token, confirm=False)
        self.assertIn("confirm_zero_mutation=true", str(caught.exception))
        self.assertEqual(general.model_info(self.model_id)["status"], "failed")

    def test_acknowledgement_is_a_metadata_transaction(self):
        token = self.inspect()["evidence_token"]
        with (
            patch.object(rec, "_native") as worker,
            patch.object(bridge.subprocess, "Popen") as popen,
        ):
            manifest = self.apply_ack(token)
        worker.assert_not_called()
        popen.assert_not_called()
        self.assertEqual(manifest["status"], "succeeded")
        self.assertEqual(manifest["stage"], "metadata_acknowledged")
        self.assertEqual(manifest["recovery"]["prior_status"], "failed")
        self.assertEqual(manifest["recovery"]["prior_job_id"], self.failed_job)
        model = general.model_info(self.model_id)
        self.assertEqual(model["status"], "ready")
        self.assertEqual(model["revision"], 5)
        self.assertIsNone(model["pending_job"])
        self.assertIsNone(model["recovery_pending"])
        self.assertEqual(model["reconciliation"]["action"], "ack_no_mutation")
        self.assertEqual(model["reconciliation"]["prior_status"], "failed")
        self.assertEqual(model["reconciliation"]["original_job_id"], self.failed_job)
        self.assertFalse(model["reconciliation"]["original_plan_completion_confirmed"])
        self.assertIn("acknowledged_at", model["reconciliation"])
        self.assertEqual(self.file.read_bytes(), b"verified assembly checkpoint fixture")

    def test_replay_with_the_same_key_returns_the_same_job(self):
        token = self.inspect()["evidence_token"]
        first = self.apply_ack(token, key="ack_replay_1")
        with patch.object(rec, "_native") as worker:
            second = self.apply_ack(token, key="ack_replay_1")
        worker.assert_not_called()
        self.assertEqual(first["job_id"], second["job_id"])
        journal = general.model_path(self.model_id) / "reconciliation"
        self.assertEqual(len(list(journal.glob("intent-*.json"))), 1)

    def test_contrary_evidence_refuses(self):
        pending_job = "c" * 32
        pending = bridge.job_path(pending_job)
        pending.mkdir(parents=True)
        bridge.write_json(
            pending / "job.json",
            {
                "job_id": pending_job,
                "model_id": self.model_id,
                "kind": "generic",
                "status": "running",
                "worker_started": False,
                "created_at": bridge.now(),
                "runner_identity": {"pid": 2147483647, "created": 12},
            },
        )
        bridge.write_json(pending / "request.json", {"model": {"model_id": self.model_id}})
        cases = (
            ({"status": "ready"}, "Only a failed model"),
            ({"status": "unknown_outcome"}, "Only a failed model"),
            ({"pending_job": pending_job}, "still owns a pending"),
            ({"rollback_status": "failed"}, "did not succeed"),
            ({"part_sha256": "0" * 64}, "Checkpoint identity"),
        )
        for change, reason in cases:
            self.model = {
                "model_id": self.model_id,
                "model_name": "wb_asm",
                "model_type": "assembly",
                "revision": 5,
                "aliases": {},
                "inspection": {"healthy": True, "model_type": "assembly"},
                "output_directory": str(general.model_path(self.model_id) / "output"),
                "part_file": str(self.file),
                "last_job": self.failed_job,
                "status": "failed",
                "pending_job": None,
                "rollback_status": "succeeded",
                "part_sha256": hashlib.sha256(self.file.read_bytes()).hexdigest(),
                **change,
            }
            self.save()
            actions = self.inspect()["actions"]["ack_no_mutation"]
            self.assertFalse(actions["available"], change)
            self.assertIn(reason, actions["reason"], change)


class FailedStatusAttribution(unittest.TestCase):
    def test_no_dispatch_keeps_a_saved_model_ready(self):
        result = {"model_unchanged": True, "failed_stage": "load_model"}
        self.assertEqual(general.failed_model_status({}, result, {"part_file": "x.asm.1"}), "ready")

    def test_verified_rollback_and_readonly_stay_ready(self):
        self.assertEqual(
            general.failed_model_status({}, {"rollback_succeeded": True}, {"part_file": "x"}),
            "ready",
        )
        self.assertEqual(
            general.failed_model_status({"readonly": True}, {}, {"part_file": "x"}), "ready"
        )

    def test_dispatched_failure_stays_failed(self):
        self.assertEqual(
            general.failed_model_status(
                {}, {"failed_stage": "execute_extrude"}, {"part_file": "x"}
            ),
            "failed",
        )

    def test_model_without_checkpoint_cannot_stay_ready(self):
        self.assertEqual(general.failed_model_status({}, {"model_unchanged": True}, {}), "failed")


if __name__ == "__main__":
    unittest.main()
