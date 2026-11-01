"""Offline contract tests for terminal job stage reporting."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge


class JobStageReporting(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(bridge, "JOBS", self.root))

    def job(self, status, stage, result=None, log=None):
        job_id = "a" * 32
        directory = bridge.job_path(job_id)
        directory.mkdir(exist_ok=True)
        bridge.write_json(
            directory / "job.json",
            {
                "job_id": job_id,
                "kind": "plate",
                "status": status,
                "stage": stage,
                "created_at": bridge.now(),
                "result": result or {},
            },
        )
        if log is not None:
            (directory / "native.log").write_bytes(log)
        return job_id

    def assert_stage_both(self, job_id, expected):
        self.assertEqual(bridge.get_job(job_id, "full")["stage"], expected)
        self.assertEqual(bridge.get_job(job_id, "compact")["stage"], expected)

    def test_connect_failure_overrides_speculative_runner_stage(self):
        job_id = self.job(
            "failed",
            "creating_native_features",
            {"failed_stage": "connect"},
            b"PHASE=connect\nPHASE=disconnect\n",
        )
        self.assert_stage_both(job_id, "connect")

    def test_success_preserves_verified_after_disconnect(self):
        job_id = self.job(
            "succeeded", "verified", {"success": True}, b"PHASE=save\nPHASE=disconnect\n"
        )
        self.assert_stage_both(job_id, "verified")

    def test_rollback_does_not_replace_failure_stage(self):
        job_id = self.job(
            "failed",
            "executing_feature_plan",
            {"failed_stage": "create_feature", "rollback_succeeded": True},
            b"PHASE=create_feature\nPHASE=rollback\nPHASE=disconnect\n",
        )
        self.assert_stage_both(job_id, "create_feature")

    def test_missing_and_truncated_log_keep_known_stage(self):
        job_id = self.job("failed", "building_worker")
        self.assert_stage_both(job_id, "building_worker")
        (bridge.job_path(job_id) / "native.log").write_bytes(b"noise PHASE=discon")
        self.assert_stage_both(job_id, "building_worker")


if __name__ == "__main__":
    unittest.main()
