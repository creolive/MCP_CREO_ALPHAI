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
        self.enterContext(
            patch.object(bridge, "config", return_value={"native_timeout_seconds": 180})
        )

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

    def test_running_job_reports_substage_progress(self):
        job_id = self.job(
            "running",
            "verify_model",
            log=(
                b"PHASE=verify_model\n"
                b"STAGE name=verify_model_save elapsed_ms=40 since_start_ms=900 "
                b"ts=1700000000000\n"
            ),
        )
        full = bridge.get_job(job_id, "full")
        self.assertEqual(full["native_progress"]["stage"], "verify_model")
        self.assertEqual(full["native_progress"]["sub_stage"], "verify_model_save")
        self.assertEqual(full["native_progress"]["elapsed_ms"], 40)
        self.assertEqual(full["native_progress"]["since_start_ms"], 900)
        compact = bridge.get_job(job_id, "compact")
        self.assertEqual(compact["native_progress"]["sub_stage"], "verify_model_save")

    def test_running_job_compact_progress_exposes_index_and_total(self):
        job_id = self.job(
            "running",
            "executing_feature_plan",
            log=(
                b"PHASE=execute_extrude\n"
                b"PROGRESS index=3 total=20 op=extrude label=deck_cut state=start "
                b"elapsed_ms=1200 since_start_ms=3400 ts=1700000000000\n"
            ),
        )
        progress = bridge.get_job(job_id, "compact")["native_progress"]
        self.assertEqual(progress["operation_index"], 3)
        self.assertEqual(progress["operation_total"], 20)
        self.assertEqual(progress["progress_text"], "3/20 extrude:deck_cut start")

    def test_failed_job_without_stage_lines_states_the_reason(self):
        job_id = self.job(
            "failed",
            "verify_model",
            {"failed_stage": "verify_model"},
            log=b"PHASE=verify_model\n",
        )
        full = bridge.get_job(job_id, "full")
        self.assertEqual(full["stage"], "verify_model")
        self.assertEqual(full["native_progress"]["reason"], "no_stage_timing")
        self.assertIsNone(full["native_progress"]["sub_stage"])

    def test_failed_job_uses_verify_stages_when_log_is_truncated(self):
        job_id = self.job(
            "failed",
            "execute_boolean_bodies",
            {
                "failed_stage": "execute_boolean_bodies",
                "verify_stages": [
                    {"name": "connect", "elapsed_ms": 68, "since_start_ms": 68},
                    {"name": "connected", "elapsed_ms": 4710, "since_start_ms": 4778},
                ],
            },
            log=(
                b"PHASE=failed\n"
                + b"diagnostic filler\n" * 1000
                + b"PHASE=execute_boolean_bodies\n"
            ),
        )
        progress = bridge.get_job(job_id, "full")["native_progress"]
        self.assertTrue(progress["truncated"])
        self.assertNotEqual(progress["reason"], "no_stage_timing")
        self.assertEqual(progress["connect_timing"]["connect"]["elapsed_ms"], 68)
        self.assertEqual(progress["timing_source"], "verify_stages")

    def test_finished_jobs_keep_the_polling_payload_small(self):
        job_id = self.job(
            "succeeded",
            "verified",
            {"success": True},
            b"PHASE=verify_model\nPHASE=disconnect\n",
        )
        self.assertNotIn("native_progress", bridge.get_job(job_id, "full"))

    def test_timeout_message_names_the_stalled_substage(self):
        message = bridge.timeout_message(
            {"sub_stage": "verify_model_erase", "idle_seconds": 431.25}
        )
        self.assertIn("Last sub-stage: verify_model_erase", message)
        self.assertIn("idle 431.2 s", message)

    def test_timeout_message_without_progress_keeps_original_wording(self):
        expected = (
            "Native helper timed out and was stopped; inspect native checkpoint and Creo "
            "before retrying."
        )
        self.assertEqual(bridge.timeout_message({}), expected)
        self.assertEqual(bridge.timeout_message(None), expected)
        self.assertEqual(bridge.timeout_message({"sub_stage": None, "idle_seconds": 5}), expected)


if __name__ == "__main__":
    unittest.main()
