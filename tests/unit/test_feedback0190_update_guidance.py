"""DEV-081 / F07: a failed update check names the caller's next executable step."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from creo_mechdog import update_check as updates


def _release():
    return {
        "tag_name": "v0.3.0",
        "draft": False,
        "published_at": "2026-10-14T00:00:00Z",
        "prerelease": False,
        "html_url": updates.RELEASE_ROOT + "/tag/v0.3.0",
        "assets": [],
    }


class UpdateGuidanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.checker = updates.UpdateChecker("0.2.6")
        self.addAsyncCleanup(self.checker.stop)
        self.fetch = self.enterContext(
            patch.object(updates, "fetch_releases", new_callable=AsyncMock)
        )
        self.fetch.return_value = [_release()]

    async def test_timeout_error_names_configurable_budget(self):
        self.fetch.side_effect = TimeoutError()
        result = await self.checker.check()
        self.assertEqual(result["status"], "failed")
        self.assertIn("MECHDOG_UPDATE_TIMEOUT_SECONDS", result["error"])

    async def test_timeout_message_names_force_retry_tool(self):
        self.fetch.side_effect = TimeoutError()
        result = await self.checker.check()
        self.assertIn("creo_check_update", result["message"])
        self.assertIn("force=true", result["message"])

    async def test_failed_check_never_claims_latest(self):
        await self.checker.check()
        self.fetch.side_effect = TimeoutError()
        result = await self.checker.check(force=True)
        self.assertEqual(result["status"], "failed")
        self.assertIn("不代表已是最新版本", result["message"])
        self.assertTrue(result["stale"])
        self.assertIn("stale", result["message"])

    async def test_default_network_budget_is_five_seconds(self):
        self.assertEqual(self.checker.snapshot()["network_timeout_seconds"], 5)


if __name__ == "__main__":
    unittest.main()
