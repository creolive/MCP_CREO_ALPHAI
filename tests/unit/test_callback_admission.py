"""A confirmed callback preflight rejection preserves the owned model reservation."""

import asyncio
import subprocess
import unittest
from unittest.mock import patch

import bridge
import generic_bridge as general
import server
from tests.unit import test_toolkit_channel as channel_tests


class CallbackAdmission(unittest.TestCase):
    setUp = channel_tests.ToolkitChannel.setUp
    submit = channel_tests.ToolkitChannel.submit
    worker = channel_tests.ToolkitChannel.worker
    run_job = channel_tests.ToolkitChannel.run_job

    def reject(self, phase: str, unchanged: bool) -> dict:
        created = self.submit()
        self.run_job(created)
        before = general.model_info(created["model_id"])
        queued = self.submit(model_id=created["model_id"], expected_revision=before["revision"])

        def worker(*args, **kwargs):
            bridge.write_json(
                bridge.job_path(queued["job_id"]) / "native_result.json",
                {
                    "success": False,
                    "failed_stage": phase,
                    "model_unchanged": unchanged,
                    "rollback_succeeded": False,
                    "disconnect_code": 0,
                    "delivery_complete": True,
                    "message": "BLEND_CALLBACK_SETUP_REQUIRED",
                },
            )
            return subprocess.CompletedProcess(args[0], 1)

        with (
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe"),
            patch.object(bridge, "native_environment", return_value={}),
            patch.object(bridge.subprocess, "run", side_effect=worker),
        ):
            bridge.run_job(queued["job_id"])
        after = general.model_info(created["model_id"])
        self.assertEqual(after["revision"], before["revision"])
        self.assertEqual(after["part_file"], before["part_file"])
        self.assertEqual(after["aliases"], before["aliases"])
        self.assertIsNone(after["pending_job"])
        return after

    def test_preflight_rejection_preserves_ready_model_without_claiming_rollback(self):
        self.assertEqual(self.reject("callback_preflight", True)["status"], "ready")

    def test_unverified_or_later_failure_cannot_use_preflight_exception(self):
        self.assertEqual(self.reject("callback_preflight", False)["status"], "failed")
        self.assertEqual(self.reject("executing_operations", True)["status"], "failed")

    def test_unknown_reservation_still_rejects_loft_without_callback_or_replay(self):
        first = self.submit()
        self.run_job(first)
        model = general.model_info(first["model_id"])
        timed = self.submit(model_id=first["model_id"], expected_revision=model["revision"])
        self.run_job(timed, "timeout")
        with patch.object(bridge.subprocess, "Popen") as spawn:
            with self.assertRaises(bridge.ToolkitBusy):
                general.submit(
                    [{"op": "loft", "label": "blend", "sections": [40, 49]}],
                    model_id=first["model_id"],
                    expected_revision=model["revision"],
                )
        spawn.assert_not_called()
        self.assertEqual(general.model_info(first["model_id"])["pending_job"], timed["job_id"])

    def test_both_public_tools_are_registered_and_startup_probe_stays_offline(self):
        tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
        self.assertEqual(len(tools), 92)
        self.assertIn("creo_reconcile_model", tools)
        self.assertTrue(tools["creo_callback_status"].annotations.read_only_hint)
        with (
            patch.object(server.startup, "status", return_value={"coordinator_running": True}),
            patch.object(bridge, "callback_status") as native,
        ):
            result = asyncio.run(server.creo_callback_status())
        native.assert_not_called()
        self.assertEqual(result["readiness"], "unknown")
        self.assertEqual(result["reason"], "startup_in_progress")
