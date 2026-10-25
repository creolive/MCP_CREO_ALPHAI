"""FEAT-048 live driver must observe public startup readiness before any inventory.

Offline regression with a fake stdio client: no Toolkit, no MCP server, no Creo.
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import tools.test_file_adoption as driver


def reply(is_error, content):
    return SimpleNamespace(is_error=is_error, structured_content=content, content=content)


class FakeClient:
    """Minimal async-context-manager client recording tool call order."""

    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        return self.handler(name, arguments)


def startup_then_busy(name, arguments):
    if name == "creo_startup_status":
        return reply(False, {"state": "ready", "connected": True})
    if name == "creo_list_session_models":
        return reply(
            True,
            {
                "status": "busy",
                "blocking_operation": "startup_build",
                "blocking_job_id": None,
                "blocking_model_id": None,
            },
        )
    raise AssertionError(f"unexpected tool call: {name}")


class DriverReadinessGate(unittest.IsolatedAsyncioTestCase):
    async def test_scenario_observes_startup_before_inventory_and_busy_stops(self):
        client = FakeClient(startup_then_busy)
        report = {"calls": []}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json"
            with patch.object(driver, "Client", return_value=client):
                with self.assertRaises(RuntimeError):
                    await driver.scenario(["a.prt.1", "a.prt.1"], report, output)
            self.assertEqual(client.calls[0], "creo_startup_status")
            self.assertEqual(client.calls, ["creo_startup_status", "creo_list_session_models"])
            # Busy inventory is a stop: never retried, never followed by adoption.
            self.assertNotIn("creo_adopt_file", client.calls)
            self.assertEqual(report["startup"]["state"], "ready")
            self.assertTrue(output.exists())

    async def test_scenario_waits_through_building_worker_states(self):
        phases = iter(
            [
                {"state": "building_worker", "connected": False},
                {"state": "waiting_for_connection", "connected": False},
                {"state": "ready", "connected": True},
            ]
        )

        def handler(name, arguments):
            if name == "creo_startup_status":
                return reply(False, next(phases))
            if name == "creo_list_session_models":
                return reply(True, {"status": "busy"})
            raise AssertionError(f"unexpected tool call: {name}")

        client = FakeClient(handler)
        report = {"calls": []}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json"
            with patch.object(driver.asyncio, "sleep", new=self._noop_sleep()):
                with patch.object(driver, "Client", return_value=client):
                    with self.assertRaises(RuntimeError):
                        await driver.scenario(["a.prt.1"], report, output)
            self.assertEqual(
                client.calls,
                ["creo_startup_status"] * 3 + ["creo_list_session_models"],
            )
            self.assertEqual(len(report["startup_queries"]), 3)
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["startup_queries"]), 3)

    @staticmethod
    def _noop_sleep():
        async def sleep(_seconds):
            return None

        return sleep


class ReportDestination(unittest.TestCase):
    def test_destination_unique_per_invocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(driver, "ROOT", Path(temporary)):
                first = driver.report_destination()
                second = driver.report_destination()
        self.assertNotEqual(first, second)
        suffix = first.parent.name.removeprefix("file_adoption_integration_").rsplit("_", 1)[-1]
        self.assertTrue(suffix)
        self.assertRegex(suffix, r"^[0-9a-f]{8}$")
        self.assertIn("file_adoption_integration_", first.parent.name)

    def test_main_saves_failure_report_without_running_scenario(self):
        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch.object(driver, "ROOT", Path(temporary)),
                patch.object(driver, "scenario", side_effect=RuntimeError("synthetic stop")),
            ):
                with self.assertRaises(RuntimeError):
                    driver.main(["a.prt.1"])
            reports = list(Path(temporary).glob("build/file_adoption_integration_*/report.json"))
            self.assertEqual(len(reports), 1)
            saved = json.loads(reports[0].read_text(encoding="utf-8"))
            self.assertFalse(saved["success"])
            self.assertEqual(saved["calls"], [])


if __name__ == "__main__":
    unittest.main()
