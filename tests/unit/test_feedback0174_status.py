"""Offline regressions for DEV-074 preview and cached status evidence."""

import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import bridge
import creo_startup
from creo_mechdog.preview import apply_preview_projection
from creo_mechdog.update_check import UpdateChecker


class PreviewEvidenceTests(unittest.TestCase):
    def test_skipped_capture_has_no_file_path_or_byte_count(self):
        result = {
            "success": True,
            "saved_file_reloaded_and_verified": True,
            "preview_file": "missing/preview.jpg",
            "preview": {
                "status": "skipped_no_geometry",
                "path": "missing/preview.jpg",
                "bytes": -1,
                "empty_geometry_basis": {
                    "feature_visit_code": 0,
                    "non_datum_feature_count": 0,
                },
            },
        }
        apply_preview_projection(result)
        preview = result["preview"]
        self.assertIsNone(preview["path"])
        self.assertIsNone(preview["bytes"])
        self.assertIsNone(result["preview_file"])
        self.assertEqual(preview["empty_geometry_basis"]["feature_visit_code"], 0)
        self.assertEqual(preview["empty_geometry_basis"]["non_datum_feature_count"], 0)
        self.assertTrue(result["success"])
        self.assertTrue(result["saved_file_reloaded_and_verified"])
        # The normalized projection may be applied more than once during reads.
        apply_preview_projection(result)
        self.assertEqual(result["preview"], preview)

    def test_missing_geometry_evidence_stays_unknown(self):
        result = {"preview": {"status": "skipped_no_geometry"}}
        apply_preview_projection(result)
        self.assertIsNone(result["preview"]["empty_geometry_basis"])


class StartupEvidenceTests(unittest.TestCase):
    def test_stale_ready_snapshot_explicitly_reports_unverified(self):
        controller = creo_startup.CreoStartup()
        controller._state = {
            "state": "ready",
            "connected": True,
            "verified_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "message": "Connected",
        }
        with patch.object(bridge, "channel_health", return_value={}):
            result = controller.status()
        self.assertTrue(result["stale"])
        self.assertEqual(result["connection_verification"], "unverified_stale_snapshot")
        self.assertIsNone(result["current_connected"])
        self.assertIn("unverified", result["message"])
        self.assertEqual(controller._state["message"], "Connected")

    def test_fresh_snapshot_retains_verified_evidence(self):
        controller = creo_startup.CreoStartup()
        controller._state = {
            "state": "ready",
            "connected": True,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "message": "Connected",
        }
        with patch.object(bridge, "channel_health", return_value={}):
            result = controller.status()
        self.assertFalse(result["stale"])
        self.assertEqual(result["connection_verification"], "recent_snapshot")
        self.assertTrue(result["current_connected"])


class UpdateEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_pending_check_is_explicit_and_preserves_completed_status(self):
        checker = UpdateChecker()
        checker._result["status"] = "up_to_date"
        task = asyncio.create_task(asyncio.Event().wait())
        checker._inflight = task
        try:
            result = checker.snapshot()
            self.assertTrue(result["in_flight"])
            self.assertEqual(result["last_completed_status"], "up_to_date")
            self.assertEqual(result["status"], "checking")
            self.assertTrue(result["from_cache"])
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self.assertFalse(checker.snapshot()["in_flight"])


if __name__ == "__main__":
    unittest.main()
