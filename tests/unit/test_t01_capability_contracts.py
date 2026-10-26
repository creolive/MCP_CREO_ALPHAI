"""DEV-047 T01: public capability and local release summaries without Toolkit."""

import copy
import json
import unittest
from unittest.mock import patch

import capabilities
import server
from creo_mechdog import capability_pages


class CapabilitySummaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        capability_pages.reset_snapshot()

    async def test_shipped_summaries_match_registered_tools_and_family_modes(self):
        tools = {tool.name for tool in await server.mcp.list_tools()}
        self.assertEqual(len(tools), 92)
        status = server._support_status()
        families = capabilities.families()
        for summary, family in (
            ("adoption", "model_adoption"),
            ("file_adoption", "file_adoption"),
            ("session_erase", "session_erase"),
            ("registry_maintenance", "registry_maintenance"),
        ):
            with self.subTest(summary=summary):
                entry = status[summary]
                self.assertTrue(families[family]["enabled"])
                listed = entry.get("tools", [entry.get("tool")])
                self.assertTrue(set(listed) <= tools)
                self.assertNotIn("not_available", entry["status"])
                self.assertNotIn("planned", entry["status"])
        self.assertEqual(status["adoption"]["actions"], ["inspect", "prepare", "apply"])
        self.assertIn("prepare", status["adoption"]["summary"])
        self.assertEqual(status["file_adoption"]["actions"], ["inspect", "apply"])
        self.assertEqual(status["file_adoption"]["maximum_paths"], 20)
        self.assertIn("path", status["file_adoption"]["summary"])
        self.assertIn("inspect", status["session_erase"]["summary"])
        self.assertIn("apply", status["registry_maintenance"]["summary"])

    async def test_disabled_family_does_not_claim_enabled_support(self):
        families = copy.deepcopy(capabilities.families())
        families["file_adoption"]["enabled"] = False
        with patch.object(server, "families", return_value=families):
            self.assertEqual(server._support_status()["file_adoption"]["status"], "not_available")

    async def test_compact_and_full_reconstruct_the_same_public_summary_under_budget(self):
        compact = await server.creo_capabilities()
        registered = {tool.name for tool in await server.mcp.list_tools()}
        self.assertEqual(compact["tool_count"], len(registered))
        self.assertLessEqual(len(json.dumps(compact, ensure_ascii=False).encode("utf-8")), 32768)
        overview = {}
        cursor = None
        while True:
            page = await server.creo_capabilities(
                detail="full", section="overview", limit=2, cursor=cursor
            )
            self.assertLessEqual(len(json.dumps(page, ensure_ascii=False).encode("utf-8")), 32768)
            overview.update({entry["key"]: entry["value"] for entry in page["entries"]})
            cursor = page.get("next_cursor")
            if cursor is None:
                break
        self.assertEqual(compact["support_status"], overview["support_status"])
        self.assertEqual(compact["release_status"], overview["release_status"])
        self.assertEqual(compact["complete_creo_coverage"], overview["complete_creo_coverage"])


class LocalReleaseStatusTests(unittest.TestCase):
    def test_local_version_maturity_is_independent_of_remote_update_cache(self):
        remote_cases = [
            {"status": "not_checked", "latest_version": None, "is_prerelease": None},
            {"status": "unknown", "latest_version": None, "is_prerelease": None},
            {
                "status": "checking",
                "latest_version": "0.7.0-rc.1",
                "is_prerelease": True,
                "stale": True,
            },
            {
                "status": "failed",
                "latest_version": "0.7.0-rc.1",
                "is_prerelease": True,
                "stale": True,
            },
            {"status": "up_to_date", "latest_version": "0.6.1", "is_prerelease": False},
        ]
        for version, expected in (
            ("0.6.1", "stable"),
            ("0.7.0+dev", "stable"),
            ("0.7.0-rc.1", "pre-release"),
            ("unparseable", "unknown"),
        ):
            for remote in remote_cases:
                with self.subTest(version=version, remote=remote["status"]):
                    with (
                        patch.object(server, "VERSION", version),
                        patch.object(server.updates, "snapshot", return_value=remote),
                        patch.object(server.seeds, "list_seeds", return_value={"seeds": []}),
                        patch.object(server, "callback_setup_status", return_value={}),
                    ):
                        payload = server._capabilities_payload([])
                    self.assertEqual(payload["release_status"], expected)
                    self.assertEqual(payload["update"], remote)
                    self.assertFalse(payload["complete_creo_coverage"])
