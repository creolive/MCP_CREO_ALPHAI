"""Admission and polling safeguards of the BUG-030 developer native suite."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tools.test_editing_closeout import Closeout, StartupObserver


class EditingCloseoutSafety(unittest.IsolatedAsyncioTestCase):
    async def test_native_connection_failure_stops_on_first_observation(self):
        status = {
            "state": "waiting_for_connection",
            "connected": False,
            "native": {"toolkit_code": -4},
        }
        client = SimpleNamespace(
            call_tool=AsyncMock(return_value=SimpleNamespace(structured_content=status))
        )
        report = {}
        with self.assertRaisesRegex(RuntimeError, "no modeling submitted"):
            await StartupObserver(client, report).call_tool("creo_startup_status", {})
        client.call_tool.assert_awaited_once_with("creo_startup_status", {})
        self.assertEqual(report["startup"], status)

    async def test_building_without_a_failed_probe_can_be_observed(self):
        response = SimpleNamespace(
            structured_content={"state": "building_worker", "connected": False}
        )
        client = SimpleNamespace(call_tool=AsyncMock(return_value=response))
        self.assertIs(
            await StartupObserver(client, {}).call_tool("creo_startup_status", {}), response
        )

    async def test_busy_is_not_resubmitted(self):
        response = SimpleNamespace(is_error=True, structured_content={"status": "busy"})
        client = SimpleNamespace(call_tool=AsyncMock(return_value=response))
        with tempfile.TemporaryDirectory() as directory:
            suite = Closeout(client, Path(directory) / "report.json")
            with self.assertRaisesRegex(RuntimeError, "busy"):
                await suite.job("creo_execute_plan", {"operations": []})
        client.call_tool.assert_awaited_once()

    async def test_unknown_job_is_not_resubmitted(self):
        values = [
            SimpleNamespace(
                is_error=False, structured_content={"job_id": "job", "model_id": "model"}
            ),
            SimpleNamespace(is_error=False, structured_content={"status": "unknown_outcome"}),
        ]
        client = SimpleNamespace(call_tool=AsyncMock(side_effect=values))
        with tempfile.TemporaryDirectory() as directory:
            suite = Closeout(client, Path(directory) / "report.json")
            with self.assertRaises(AssertionError):
                await suite.job("creo_execute_plan", {"operations": []})
        self.assertEqual(client.call_tool.await_count, 2)
        self.assertEqual(client.call_tool.await_args_list[-1].args[0], "creo_get_job")

    async def test_failed_job_returns_full_failure_and_persists_it(self):
        result = {"rollback_succeeded": True, "message": "Regeneration produced a failed feature"}
        values = [
            SimpleNamespace(
                is_error=False, structured_content={"job_id": "job", "model_id": "model"}
            ),
            SimpleNamespace(is_error=False, structured_content={"status": "running"}),
            SimpleNamespace(is_error=False, structured_content={"status": "failed"}),
            SimpleNamespace(
                is_error=False, structured_content={"status": "failed", "result": result}
            ),
        ]
        client = SimpleNamespace(call_tool=AsyncMock(side_effect=values))
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("tools.test_editing_closeout.asyncio.sleep", new=AsyncMock()),
        ):
            report = Path(directory) / "report.json"
            suite = Closeout(client, report)
            value = await suite.failed_job("creo_update_sketch_geometry", {"expected_revision": 3})
            persisted = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(value["status"], "failed")
        self.assertIs(value["result"]["rollback_succeeded"], True)
        self.assertEqual(value["model_id"], "model")
        self.assertEqual(value["job_id"], "job")
        # No job-level revision in the terminal response: the evidence keeps
        # failed.get("revision") as None instead of borrowing a model value.
        self.assertIsNone(value.get("revision"))
        self.assertEqual(client.call_tool.await_count, 4)
        self.assertEqual(
            client.call_tool.await_args_list[-1].args,
            ("creo_get_job", {"job_id": "job", "detail": "full"}),
        )
        self.assertEqual(persisted["calls"][-1]["tool"], "creo_get_job")
        self.assertEqual(persisted["calls"][-1]["payload"]["status"], "failed")
        self.assertEqual(persisted["calls"][-1]["payload"]["result"], result)

    async def test_failed_job_rejects_non_failed_terminal_and_persists_it(self):
        result = {"rollback_succeeded": False, "message": "unexpected success"}
        terminal = {"status": "succeeded", "revision": 4, "result": result}
        values = [
            SimpleNamespace(
                is_error=False, structured_content={"job_id": "job", "model_id": "model"}
            ),
            SimpleNamespace(is_error=False, structured_content=terminal),
            SimpleNamespace(is_error=False, structured_content=terminal),
        ]
        client = SimpleNamespace(call_tool=AsyncMock(side_effect=values))
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            suite = Closeout(client, report)
            with self.assertRaises(AssertionError):
                await suite.failed_job("creo_update_sketch_geometry", {"expected_revision": 3})
            persisted = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(client.call_tool.await_count, 3)
        self.assertEqual(client.call_tool.await_args_list[-1].args[0], "creo_get_job")
        self.assertEqual(persisted["calls"][-1]["payload"]["status"], "succeeded")
        self.assertEqual(persisted["calls"][-1]["payload"]["result"], result)

    async def test_failed_job_busy_is_not_resubmitted(self):
        response = SimpleNamespace(is_error=True, structured_content={"status": "busy"})
        client = SimpleNamespace(call_tool=AsyncMock(return_value=response))
        with tempfile.TemporaryDirectory() as directory:
            suite = Closeout(client, Path(directory) / "report.json")
            with self.assertRaisesRegex(RuntimeError, "busy"):
                await suite.failed_job("creo_update_sketch_geometry", {"expected_revision": 3})
        client.call_tool.assert_awaited_once()

    async def test_failed_job_unknown_outcome_is_not_resubmitted(self):
        values = [
            SimpleNamespace(
                is_error=False, structured_content={"job_id": "job", "model_id": "model"}
            ),
            SimpleNamespace(is_error=False, structured_content={"status": "unknown_outcome"}),
            SimpleNamespace(is_error=False, structured_content={"status": "unknown_outcome"}),
        ]
        client = SimpleNamespace(call_tool=AsyncMock(side_effect=values))
        with tempfile.TemporaryDirectory() as directory:
            suite = Closeout(client, Path(directory) / "report.json")
            with self.assertRaises(AssertionError):
                await suite.failed_job("creo_update_sketch_geometry", {"expected_revision": 3})
        self.assertEqual(client.call_tool.await_count, 3)
        self.assertEqual(client.call_tool.await_args_list[-1].args[0], "creo_get_job")

    async def test_accepted_job_polls_same_id_and_requires_one_revision_increment(self):
        result = {"saved_file_reloaded_and_verified": True}
        values = [
            SimpleNamespace(
                is_error=False, structured_content={"job_id": "job", "model_id": "model"}
            ),
            SimpleNamespace(is_error=False, structured_content={"status": "running"}),
            SimpleNamespace(
                is_error=False,
                structured_content={"status": "succeeded", "revision": 4, "result": result},
            ),
        ]
        client = SimpleNamespace(call_tool=AsyncMock(side_effect=values))
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("tools.test_editing_closeout.asyncio.sleep", new=AsyncMock()),
        ):
            suite = Closeout(client, Path(directory) / "report.json")
            value = await suite.job("creo_update_sketch_geometry", {"expected_revision": 3})
        self.assertEqual(value["revision"], 4)
        self.assertEqual(client.call_tool.await_count, 3)
        for call in client.call_tool.await_args_list[1:]:
            self.assertEqual(call.args, ("creo_get_job", {"job_id": "job", "detail": "compact"}))

    async def test_starting_at_last_case_skips_all_prior_model_operations(self):
        client = SimpleNamespace(call_tool=AsyncMock())
        with tempfile.TemporaryDirectory() as directory:
            suite = Closeout(
                client, Path(directory) / "report.json", from_case="reorder_noop_revision_plus_one"
            )
            suite.job = AsyncMock(
                side_effect=[
                    {"model_id": "fresh", "job_id": "create", "revision": 1},
                    {"model_id": "fresh", "job_id": "noop", "revision": 2},
                ]
            )
            with (
                patch.object(suite, "detail", return_value={"reordered": False}),
                patch("builtins.print"),
            ):
                await suite.run()
            self.assertEqual(suite.job.await_count, 2)
            self.assertEqual(suite.job.await_args_list[0].args[0], "creo_execute_plan")
            self.assertEqual(
                suite.job.await_args_list[0].args[1]["operations"][0]["op"], "datum_plane"
            )
            self.assertEqual(suite.job.await_args_list[1].args[0], "creo_reorder_features")
            self.assertEqual(
                [case["name"] for case in suite.report["cases"]], ["reorder_noop_revision_plus_one"]
            )
            client.call_tool.assert_not_awaited()


class EditingEvidence(unittest.TestCase):
    def test_snapshot_keeps_revision_actual_part_bytes_and_references(self):
        import hashlib

        from tools.test_editing_closeout import model_evidence

        with tempfile.TemporaryDirectory() as directory:
            part = Path(directory) / "own.prt.1"
            part.write_bytes(b"native-checkpoint")
            model = {
                "revision": 3,
                "status": "ready",
                "part_file": str(part),
                "pending_job": None,
                "recovery_pending": None,
                "inspection": {"healthy": True, "volume_mm3": 2094.395102392602},
                "aliases": {"rev_sk": {"feature_id": 40}, "rev1": {"feature_id": 51}},
            }
            row = model_evidence(model)
        self.assertEqual(row["revision"], 3)
        self.assertEqual(row["part_sha256"], hashlib.sha256(b"native-checkpoint").hexdigest())
        self.assertEqual(row["feature_ids"], {"rev_sk": 40, "rev1": 51})
        self.assertIsNone(row["pending_job"])
        self.assertEqual(len(row["inspection_sha256"]), 64)
        self.assertEqual(len(row["aliases_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
