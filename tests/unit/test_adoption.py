"""FEAT-042: managed-copy adoption over the real stdio MCP protocol.

Every MCP case drives the actual tool registration, published schema and stdio
transport. The native boundary is substituted in the child processes only:
``adoption._native`` returns a synthetic probe/apply result so this file never
connects Toolkit, builds or opens Creo. Process-level cases additionally pin
``bridge.build_native``. All jobs/models/locks live in a temporary data root.
"""

import argparse
import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

import bridge
import generic_bridge as general
from creo_mechdog import adoption, inspection_refs
from creo_mechdog import reconciliation as rec

INSPECTION = {
    "healthy": True,
    "features": [],
    "surfaces": [],
    "edges": [],
    "bodies": [],
    "datum_planes": [],
    "parameters": {},
    "volume_mm3": 10,
    "units": "mm",
    "units_query_code": 0,
    "model_type": "part",
}


def _write(file: Path, value: dict) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(value), encoding="utf-8")


def prepare_root(directory: Path) -> Path:
    (directory / "jobs").mkdir()
    (directory / "models").mkdir()
    source = directory / "user_parts"
    source.mkdir()
    part = source / "001.prt"
    part.write_bytes(b"fixture user part bytes 001")
    _write(
        directory / "config.json",
        {"creo_root": "C:\\feat042-fixture-creo", "vcvars64": "C:\\feat042-vcvars64.bat"},
    )
    return directory


def synthetic_native(job_directory: Path, manifest: dict) -> dict:
    """Fixture replacement for adoption._native; labeled substitution."""
    request = bridge.read_json(job_directory / "request.json")
    choice = request.get("adoption", {})
    manifest["worker_started"] = False
    manifest.update(stage="adopting_native_model", status="running")
    bridge.write_json(job_directory / "job.json", manifest, durable=True)
    manifest["worker_started"] = True
    bridge.write_json(job_directory / "job.json", manifest, durable=True)
    # The real worker persists its process identity; mirror a dead one so
    # recovery ownership checks can prove the synthetic worker stopped.
    _write(
        job_directory / "native_owner.json",
        {"pid": 2147483645, "created": 14},
    )
    result = {"connected": True, "delivery_complete": True, "disconnect_code": 0}
    if choice.get("action") in ("inspect", "prepare") and not request["model"][
        "model_name"
    ].startswith("fail"):
        result.update(
            success=True,
            live={
                "origin": ""
                if choice["action"] == "prepare"
                else str(bridge.ROOT / "user_parts" / "001.prt"),
                "model_type": "part",
                "healthy": True,
                "millimeter_units": True,
                "dependency_free": True,
                "session_fingerprint": "feat042-fixture-session",
                "inspection": INSPECTION,
                "volume_mm3": INSPECTION["volume_mm3"],
            },
        )
        units_fixture = bridge.ROOT / "inspection_units.json"
        if units_fixture.exists():
            unit_state = bridge.read_json(units_fixture)
            result["live"].update(
                millimeter_units=unit_state["units"] == "mm",
                volume_mm3=unit_state["volume_mm3"],
                inspection={**INSPECTION, **unit_state},
            )
        marker = bridge.ROOT / "window_sidecar.json"
        if marker.exists() and bridge.read_json(marker).get("location") == "staging":
            # Mimic the real worker: adoption writes its sidecar into the
            # model output directory, so a refusal that removes that staging
            # leaves the native reference dangling (DEV-048 T02).
            payload = result["live"].pop("inspection", None)
            result["live"]["inspection_ref"] = inspection_refs.make_ref(
                payload, Path(request["model"]["output_directory"]), "live"
            )
        if choice["action"] == "prepare":
            model = request["model"]
            part = Path(model["output_directory"]) / f"{model['model_name']}.prt.1"
            part.write_bytes(b"frozen never-saved source state")
            result.update(
                saved_file_reloaded_and_verified=True,
                inspection=INSPECTION,
                aliases={},
                part_file=str(part),
                adopted=True,  # Exercise compatibility with an old native worker.
            )
    elif request["model"]["model_name"].startswith("fail"):
        result.update(
            success=False,
            failed_stage="adoption_apply",
            message="synthetic adoption failure; no Toolkit call",
        )
        bridge.write_json(job_directory / "native_result.json", result)
        manifest["result"] = result
        raise RuntimeError(result["message"])
    else:
        model = request["model"]
        part = Path(model["output_directory"]) / f"{model['model_name']}.prt.1"
        if choice.get("action") == "confirm_snapshot":
            part = Path(choice["source_file"])
        else:
            part.write_bytes(f"adopted managed copy {model['model_name']}".encode())
        result.update(
            success=True,
            saved_file_reloaded_and_verified=True,
            inspection=INSPECTION,
            aliases={},
            part_file=str(part),
            adopted=True,
            message="synthetic adoption fixture; no Toolkit call",
        )
    # The real boundary persists the result on the job manifest as well; the
    # refusal lifecycle is verified through that persisted projection.
    manifest["result"] = result
    bridge.write_json(job_directory / "native_result.json", result)
    return result


def child_serve(directory: Path) -> None:
    import server
    from creo_mechdog import session_models
    from tests.unit.test_session_models import synthetic_inventory

    bridge.ROOT = directory
    bridge.JOBS = directory / "jobs"
    general.MODELS = directory / "models"
    real_popen = subprocess.Popen

    def route(command, *args, **kwargs):
        if (
            isinstance(command, list)
            and len(command) == 4
            and Path(command[1]).name == "bridge.py"
            and command[2] == "run-job"
        ):
            command = [
                command[0],
                "-m",
                "tests.unit.test_adoption",
                "--data-root",
                str(directory),
                "--run-job",
                command[3],
            ]
            kwargs["cwd"] = ROOT
        return real_popen(command, *args, **kwargs)

    with ExitStack() as stack:
        stack.enter_context(patch.object(subprocess, "Popen", side_effect=route))
        stack.enter_context(patch.object(server.startup, "start"))
        stack.enter_context(patch.object(server.updates, "start"))
        stack.enter_context(
            patch.object(bridge, "build_native", return_value=directory / "worker.exe")
        )
        stack.enter_context(patch.object(adoption, "_native", side_effect=synthetic_native))
        stack.enter_context(patch.object(session_models, "_probe", side_effect=synthetic_inventory))
        # reconcile inspect (used by the failure-path test) binds deployment
        # identity against repository files that do not exist in the data root.
        stack.enter_context(
            patch.object(rec, "_deployment", return_value="feat042-fixture-deployment")
        )
        server.mcp.run()


def child_run_job(directory: Path, job_id: str) -> None:
    bridge.ROOT = directory
    bridge.JOBS = directory / "jobs"
    general.MODELS = directory / "models"
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(bridge, "build_native", return_value=directory / "worker.exe")
        )
        stack.enter_context(patch.object(adoption, "_native", side_effect=synthetic_native))
        bridge.run_job(job_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="FEAT-042 adoption protocol fixture child")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--run-job")
    args = parser.parse_args()
    if args.serve:
        child_serve(args.data_root)
    elif args.run_job:
        child_run_job(args.data_root, args.run_job)


class AdoptionMcpContract(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="feat042_protocol_")
        cls.directory = prepare_root(Path(cls.temporary.name))

    @classmethod
    def tearDownClass(cls):
        for survivor in ("toolkit.lock", "toolkit-owner.lock"):
            (cls.directory / survivor).unlink(missing_ok=True)
        cls.temporary.cleanup()

    def client(self):
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters

        return Client(
            StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "tests.unit.test_adoption",
                    "--data-root",
                    str(self.directory),
                    "--serve",
                ],
                cwd=str(ROOT),
            ),
            read_timeout_seconds=90,
        )

    async def call(self, client, tool: str, arguments: dict, error: bool = False):
        reply = await client.call_tool(tool, arguments)
        self.assertEqual(bool(reply.is_error), error, reply)
        return reply.structured_content

    async def error_text(self, client, arguments: dict) -> str:
        reply = await client.call_tool("creo_adopt_current_model", arguments)
        self.assertTrue(reply.is_error, reply)
        return " ".join(block.text for block in reply.content if hasattr(block, "text"))

    async def poll(self, client, job_id: str) -> dict:
        for _ in range(90):
            result = await self.call(
                client, "creo_get_job", {"job_id": job_id, "detail": "compact"}
            )
            if result["status"] not in ("queued", "running"):
                return result
            await asyncio.sleep(0.4)
        self.fail(f"adoption job {job_id} never reached a terminal state")

    def model_file(self, model_id: str) -> dict:
        return json.loads(
            (self.directory / "models" / model_id / "model.json").read_text(encoding="utf-8")
        )

    def reset_registry(self) -> None:
        """Each MCP test adopts the same fixture source from a clean registry."""
        import shutil

        self.source_file().write_bytes(b"fixture user part bytes 001")
        for child in (self.directory / "models").iterdir():
            shutil.rmtree(child, ignore_errors=True)

    def source_file(self) -> Path:
        return (self.directory / "user_parts" / "001.prt").resolve()

    async def test_tool_is_published_with_two_modes(self):
        self.reset_registry()
        async with self.client() as client:
            result = await client.list_tools()
            tool = next(t for t in result.tools if t.name == "creo_adopt_current_model")
            schema = json.dumps(tool.input_schema)
        self.assertIn("inspect", schema)
        self.assertIn("apply", schema)
        self.assertIn("prepare", schema)
        self.assertIn("idempotency_key", schema)

    async def test_prepare_renew_confirm_and_replay_over_stdio(self):
        self.reset_registry()
        async with self.client() as client:
            args = {
                "mode": "prepare",
                "model_name": "001_snapshot",
                "idempotency_key": "prepare_snapshot_once",
            }
            submitted = await self.call(client, "creo_adopt_current_model", args)
            prepared = await self.poll(client, submitted["job_id"])
            self.assertEqual(prepared["status"], "succeeded", prepared)
            self.assertEqual(prepared["stage"], "snapshot_prepared")
            self.assertIs(prepared["result"]["adopted"], False)
            full = await self.call(
                client, "creo_get_job", {"job_id": submitted["job_id"], "detail": "full"}
            )
            self.assertIs(full["result"]["adopted"], False)
            pending_list = await self.call(client, "creo_list_models", {})
            self.assertIs(pending_list["models"][0]["adopted"], False)
            evidence = prepared["result"]["adoption"]
            mid = evidence["model_id"]
            model = self.model_file(mid)
            self.assertEqual(
                (model["status"], model["revision"], model["part_file"]), ("adopt_pending", 0, None)
            )
            renewed = await self.call(
                client, "creo_adopt_current_model", {"mode": "inspect", "model_id": mid}
            )
            self.assertNotEqual(renewed["evidence_token"], evidence["evidence_token"])
            self.assertEqual(renewed["file"], evidence["file"])
            # The external source changes after freezing; confirmation only uses
            # the stored snapshot, not the now-changed current source fixture.
            self.source_file().write_bytes(b"changed after prepare")
            applied = await self.call(
                client,
                "creo_adopt_current_model",
                {
                    "mode": "apply",
                    "model_id": mid,
                    "evidence_token": renewed["evidence_token"],
                    "idempotency_key": "confirm_snapshot_once",
                },
            )
            result = await self.poll(client, applied["job_id"])
            self.assertEqual(result["status"], "succeeded", result)
            self.assertIs(result["result"]["adopted"], True)
            after = self.model_file(mid)
            self.assertEqual((after["status"], after["revision"]), ("ready", 1))
            self.assertEqual(
                Path(after["part_file"]).read_bytes(), b"frozen never-saved source state"
            )
            replay = await self.call(client, "creo_adopt_current_model", args)
            self.assertEqual(replay["job_id"], submitted["job_id"])
            self.assertIs(replay["result"]["adopted"], False)
            self.assertEqual(self.model_file(mid)["revision"], 1)
            listing = await self.call(client, "creo_list_models", {})
            self.assertTrue(listing["models"][0]["adopted"])
            self.assertEqual(listing["models"][0]["source_kind"], "session_snapshot")
            self.source_file().write_bytes(b"fixture user part bytes 001")

    async def test_length_unit_and_unavailable_volume_survive_stdio_preflight(self):
        fixture = self.directory / "inspection_units.json"
        try:
            async with self.client() as client:
                for units, code, volume in (("mm", 0, 10), ("in", 0, None), (None, -2, None)):
                    with self.subTest(units=units):
                        self.reset_registry()
                        _write(
                            fixture,
                            {"units": units, "units_query_code": code, "volume_mm3": volume},
                        )
                        evidence = await self.call(client, "creo_adopt_current_model", {})
                        live = evidence["current_model"]
                        # Full payloads live behind inspection_ref; the visible
                        # live entry carries the summary (BUG-076).
                        summary = live["inspection_summary"]
                        self.assertEqual(summary["units"], units)
                        self.assertEqual(summary["units_query_code"], code)
                        self.assertEqual(summary["volume_mm3"], volume)
                        self.assertEqual(live["volume_mm3"], volume)
                        self.assertEqual(evidence["available"], units == "mm")
                        if units != "mm":
                            self.assertIn("millimeter", evidence["reason"])
                            self.assertIsNone(evidence["model_id"])
                            self.assertIsNone(evidence["evidence_token"])
                            self.assertEqual(list(self.directory.glob("models/*/model.json")), [])
                        self.assertEqual(
                            self.source_file().read_bytes(), b"fixture user part bytes 001"
                        )
        finally:
            fixture.unlink(missing_ok=True)

    async def test_inspect_apply_idempotent_replay_and_managed_copy(self):
        self.reset_registry()
        async with self.client() as client:
            evidence = await self.call(client, "creo_adopt_current_model", {})
            self.assertTrue(evidence["available"], evidence)
            self.assertEqual(evidence["status"], "adopt_pending")
            self.assertTrue(evidence["evidence_token"])
            self.assertEqual(evidence["file"]["path"], str(self.source_file()))
            model_id = evidence["model_id"]
            registered = self.model_file(model_id)
            self.assertEqual(registered["status"], "adopt_pending")
            self.assertEqual(registered["model_type"], "part")
            created = await self.call(
                client,
                "creo_adopt_current_model",
                {
                    "mode": "apply",
                    "model_id": model_id,
                    "evidence_token": evidence["evidence_token"],
                    "model_name": "feat042_managed",
                    "idempotency_key": "feat042_apply_once",
                },
            )
            job_id = created["job_id"]
            result = await self.poll(client, job_id)
            self.assertEqual(result["status"], "succeeded", result)
            after = self.model_file(model_id)
            self.assertEqual(after["status"], "ready")
            self.assertEqual(after["revision"], 1)
            self.assertEqual(after["model_name"], "feat042_managed")
            self.assertEqual(after["adopted_from"]["origin"], str(self.source_file()))
            self.assertEqual(after["adopted_from"]["adoption_id"], job_id)
            part = Path(after["part_file"])
            self.assertEqual(part.parent, Path(after["output_directory"]))
            self.assertEqual(after["part_sha256"], hashlib.sha256(part.read_bytes()).hexdigest())
            # The source file was never rewritten.
            self.assertEqual(
                (self.directory / "user_parts" / "001.prt").read_bytes(),
                b"fixture user part bytes 001",
            )
            replay = await self.call(
                client,
                "creo_adopt_current_model",
                {
                    "mode": "apply",
                    "model_id": model_id,
                    "evidence_token": evidence["evidence_token"],
                    "model_name": "feat042_managed",
                    "idempotency_key": "feat042_apply_once",
                },
            )
            self.assertEqual(replay["job_id"], job_id)

    async def test_window_refusal_never_publishes_a_removed_reference(self):
        self.reset_registry()
        units = self.directory / "inspection_units.json"
        marker = self.directory / "window_sidecar.json"
        before = {path.name for path in (self.directory / "jobs").iterdir()}
        try:
            _write(units, {"units": "in", "units_query_code": 0, "volume_mm3": None})
            _write(marker, {"location": "staging"})
            async with self.client() as client:
                evidence = await self.call(client, "creo_adopt_current_model", {})
                self.assertFalse(evidence["available"])
                self.assertEqual(evidence["reason_code"], "non_millimeter_units")
                current = evidence["current_model"]
                self.assertNotIn("inspection_ref", current)
                self.assertEqual(current["inspection_summary"]["units"], "in")
                self.assertEqual(evidence["refusal_details"]["actual_units"], "in")
                self.assertEqual(evidence["staging_cleanup"]["state"], "removed")
                self.assertEqual(
                    current["inspection_warnings"][0]["reason_code"],
                    "inspection_ref_removed_after_refusal",
                )
                jobs = [
                    path.name
                    for path in (self.directory / "jobs").iterdir()
                    if path.name not in before
                ]
                self.assertEqual(len(jobs), 1, jobs)
                compact = await self.call(
                    client, "creo_get_job", {"job_id": jobs[0], "detail": "compact"}
                )
                full = await self.call(
                    client, "creo_get_job", {"job_id": jobs[0], "detail": "full"}
                )
                for manifest in (compact, full):
                    self.assertNotIn("inspection_ref", manifest["result"]["live"])
                    self.assertEqual(
                        manifest["result"]["live"]["inspection_summary"]["units"], "in"
                    )
                    self.assertEqual(
                        manifest["inspection_warnings"][0]["reason_code"],
                        "inspection_ref_removed_after_refusal",
                    )
        finally:
            marker.unlink(missing_ok=True)
            units.unlink(missing_ok=True)

    async def test_apply_rejects_missing_and_invalid_inputs(self):
        self.reset_registry()
        async with self.client() as client:
            evidence = await self.call(client, "creo_adopt_current_model", {})
            model_id = evidence["model_id"]
            for arguments, fragment in (
                ({"mode": "apply"}, "model_id, evidence_token"),
                (
                    {
                        "mode": "apply",
                        "model_id": model_id,
                        "evidence_token": "0" * 32,
                        "idempotency_key": "feat042_bad_token",
                    },
                    "missing or expired",
                ),
                (
                    {
                        "mode": "apply",
                        "model_id": model_id,
                        "evidence_token": evidence["evidence_token"],
                        "model_name": "Bad-Name",
                        "idempotency_key": "feat042_bad_name",
                    },
                    "model_name",
                ),
            ):
                with self.subTest(fragment=fragment):
                    text = await self.error_text(client, arguments)
                    self.assertIn(fragment, text)

    async def test_repeated_inspect_of_same_source_reports_conflict(self):
        self.reset_registry()
        async with self.client() as client:
            first = await self.call(client, "creo_adopt_current_model", {})
            self.assertTrue(first["available"])
            created = await self.call(
                client,
                "creo_adopt_current_model",
                {
                    "mode": "apply",
                    "model_id": first["model_id"],
                    "evidence_token": first["evidence_token"],
                    "idempotency_key": "feat042_conflict_apply",
                },
            )
            self.assertEqual((await self.poll(client, created["job_id"]))["status"], "succeeded")
            second = await self.call(client, "creo_adopt_current_model", {})
            self.assertFalse(second["available"])
            self.assertEqual(second["conflict"]["reason"], "already_adopted")
            self.assertEqual(second["conflict"]["model_id"], first["model_id"])

    async def test_native_failure_keeps_adopt_pending_and_abandonable(self):
        self.reset_registry()
        async with self.client() as client:
            evidence = await self.call(client, "creo_adopt_current_model", {})
            model_id = evidence["model_id"]
            created = await self.call(
                client,
                "creo_adopt_current_model",
                {
                    "mode": "apply",
                    "model_id": model_id,
                    "evidence_token": evidence["evidence_token"],
                    "model_name": "fail_native",
                    "idempotency_key": "feat042_fail_once",
                },
            )
            result = await self.poll(client, created["job_id"])
            # The worker dispatch began, so the outcome stays protected exactly
            # like reconciliation: never a plain failure, never an auto-release.
            self.assertEqual(result["status"], "unknown_outcome", result)
            self.assertTrue(result["recovery_required"])
            after = self.model_file(model_id)
            self.assertEqual(after["status"], "adopt_pending")
            self.assertEqual(after["pending_job"], created["job_id"])
            # Terminal publication precedes process exit. Wait for the fixture
            # runner to stop before taking recovery evidence across that boundary.
            runner = result.get("runner_identity")
            for _ in range(30):
                if runner and rec._stopped(runner)["stopped"]:
                    break
                await asyncio.sleep(0.1)
            self.assertTrue(runner and rec._stopped(runner)["stopped"])
            # The failed registration resolves through the existing recovery tool
            # once the runner/worker can be proven stopped.
            for _ in range(20):
                reconcile_state = await self.call(
                    client, "creo_reconcile_model", {"model_id": model_id}
                )
                if reconcile_state["actions"]["abandon_new"]["available"]:
                    break
                await asyncio.sleep(0.5)
            else:
                self.fail("abandon_new never became available for the failed adoption")


class AdoptionBusinessRules(unittest.TestCase):
    """Process-level evidence guards against a synthetic native boundary."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="feat042_business_")
        self.directory = prepare_root(Path(self._temporary.name))
        real_root, real_jobs, real_models = bridge.ROOT, bridge.JOBS, general.MODELS
        bridge.ROOT = self.directory
        bridge.JOBS = self.directory / "jobs"
        general.MODELS = self.directory / "models"
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.callback(setattr, general, "MODELS", real_models)
        stack.callback(setattr, bridge, "JOBS", real_jobs)
        stack.callback(setattr, bridge, "ROOT", real_root)
        self.addCleanup(self._temporary.cleanup)
        stack.enter_context(
            patch.object(bridge, "build_native", return_value=self.directory / "worker.exe")
        )
        stack.enter_context(patch.object(adoption, "_native", side_effect=synthetic_native))

    def test_expired_evidence_is_refused(self):
        evidence = adoption.inspect()
        file = (
            general.model_path(evidence["model_id"])
            / "adoption"
            / f"evidence-{evidence['evidence_token']}.json"
        )
        record = json.loads(file.read_text(encoding="utf-8"))
        record["created"] -= adoption.TOKEN_SECONDS + 1
        _write(file, record)
        with self.assertRaisesRegex(ValueError, "expired"):
            adoption.apply(evidence["model_id"], evidence["evidence_token"], None, "feat042exp1")

    def test_changed_source_file_is_refused(self):
        evidence = adoption.inspect()
        (self.directory / "user_parts" / "001.prt").write_bytes(b"mutated after inspect")
        with self.assertRaisesRegex(ValueError, "changed since inspect"):
            adoption.apply(evidence["model_id"], evidence["evidence_token"], None, "feat042chg1")

    def test_non_millimeter_refusal_keeps_unit_metadata_after_split(self):
        # BUG-076 split records replace the inline inspection with a bounded
        # summary; a non-millimeter refusal must still report the real unit
        # name and query code instead of degrading known facts to unknown.
        def inch_split(job_directory, manifest):
            result = synthetic_native(job_directory, manifest)
            result["live"] = {
                key: value for key, value in result["live"].items() if key != "inspection"
            }
            result["live"].update(
                millimeter_units=False,
                inspection_summary={
                    "units": "inch",
                    "units_query_code": 0,
                    "length_unit": {"name": "inch", "scale_to_mm": 25.4},
                    "volume_mm3": 7000.0,
                    "volume_query_code": 0,
                },
            )
            return result

        with patch.object(adoption, "_native", side_effect=inch_split):
            evidence = adoption.inspect()
        self.assertFalse(evidence["available"])
        self.assertEqual(evidence["reason_code"], "non_millimeter_units")
        details = evidence["refusal_details"]
        self.assertTrue(details["actual_units_known"])
        self.assertEqual(details["actual_units"], "inch")
        self.assertEqual(details["units_query_code"], 0)

    def window_native(self, *, units_mm: bool, location: str = "staging", inspection=None):
        """Fixture worker that writes its live sidecar where the real one does.

        The real executor points ``folder`` at the model output directory, so a
        window refusal that removes that staging leaves the native reference
        dangling. ``location="job"`` mirrors the Python fallback, whose sidecar
        lives in the preflight job and survives the refusal.
        """

        def native(job_directory, manifest):
            request = bridge.read_json(job_directory / "request.json")
            directory = (
                Path(request["model"]["output_directory"])
                if location == "staging"
                else job_directory
            )
            ref = inspection_refs.make_ref(inspection or INSPECTION, directory, "live")
            result = {
                "connected": True,
                "delivery_complete": True,
                "disconnect_code": 0,
                "success": True,
                "live": {
                    "origin": str(self.directory / "user_parts" / "001.prt"),
                    "model_type": "part",
                    "healthy": True,
                    "millimeter_units": units_mm,
                    "dependency_free": True,
                    "session_fingerprint": "dev048-t02-session",
                    "volume_mm3": 10,
                    "inspection_ref": ref,
                },
            }
            bridge.write_json(job_directory / "native_result.json", result)
            manifest["result"] = result
            return result

        return native

    def only_job(self) -> list:
        return [path.parent.name for path in sorted((self.directory / "jobs").glob("*/job.json"))]

    def test_window_refusal_drops_the_reference_its_staging_removed(self):
        inch = {**INSPECTION, "units": "inch", "volume_mm3": None}
        with patch.object(
            adoption, "_native", side_effect=self.window_native(units_mm=False, inspection=inch)
        ):
            evidence = adoption.inspect()
        self.assertFalse(evidence["available"])
        self.assertEqual(evidence["reason_code"], "non_millimeter_units")
        # The staging sidecar the native result pointed at is gone; the
        # reference is not published as readable and the known units stay.
        current = evidence["current_model"]
        self.assertNotIn("inspection_ref", current)
        self.assertEqual(current["inspection_summary"]["units"], "inch")
        self.assertEqual(evidence["refusal_details"]["actual_units"], "inch")
        self.assertTrue(evidence["refusal_details"]["actual_units_known"])
        self.assertEqual(evidence["staging_cleanup"]["state"], "removed")
        self.assertFalse(Path(evidence["staging_cleanup"]["staging"]).exists())
        warnings = current["inspection_warnings"]
        self.assertEqual(len(warnings), 1, warnings)
        self.assertEqual(warnings[0]["stage"], "live")
        self.assertEqual(warnings[0]["reason_code"], "inspection_ref_removed_after_refusal")
        self.assertEqual(warnings[0]["fallback_status"], "not_attempted")
        # job.json, compact and full carry the same meaning as the response.
        jobs = self.only_job()
        self.assertEqual(len(jobs), 1)
        full = bridge.get_job(jobs[0], "full")
        compact = bridge.get_job(jobs[0], "compact")
        for manifest in (full, compact):
            live = manifest["result"]["live"]
            self.assertNotIn("inspection_ref", live)
            self.assertEqual(live["inspection_summary"]["units"], "inch")
            self.assertEqual(
                manifest["inspection_warnings"], warnings, manifest["inspection_warnings"]
            )
        self.assertEqual(full["staging_cleanup"]["state"], "removed")
        # Re-reading the job repeats the same projection without duplicating
        # the bounded diagnostic.
        again = bridge.get_job(jobs[0], "full")
        self.assertEqual(again["result"], full["result"])
        self.assertEqual(len(again["inspection_warnings"]), 1)
        self.assertTrue((bridge.job_path(jobs[0]) / "request.json").is_file())

    def test_window_refusal_keeps_a_reference_that_still_verifies(self):
        with patch.object(
            adoption, "_native", side_effect=self.window_native(units_mm=False, location="job")
        ):
            evidence = adoption.inspect()
        current = evidence["current_model"]
        ref = current["inspection_ref"]
        inspection_refs.verify_ref(ref)
        self.assertTrue(Path(ref["file"]).is_file())
        self.assertEqual(evidence["staging_cleanup"]["state"], "removed")
        self.assertEqual(current["inspection_summary"]["units"], "mm")
        self.assertNotIn("inspection_warnings", current)

    def test_window_refusal_records_a_failed_cleanup_truthfully(self):
        with (
            patch.object(adoption, "_native", side_effect=self.window_native(units_mm=False)),
            patch.object(shutil, "rmtree", side_effect=OSError("staging is locked")),
        ):
            evidence = adoption.inspect()
        cleanup = evidence["staging_cleanup"]
        self.assertEqual(cleanup["state"], "failed")
        self.assertIn("staging is locked", cleanup["error"])
        self.assertTrue(Path(cleanup["staging"]).is_dir())
        # Nothing was removed, so the reference still verifies and is kept; the
        # response never claims the file disappeared.
        ref = evidence["current_model"]["inspection_ref"]
        inspection_refs.verify_ref(ref)
        self.assertTrue(Path(ref["file"]).is_file())
        self.assertNotIn("inspection_warnings", evidence["current_model"])

    def test_modeling_submit_is_refused_while_adopt_pending(self):
        evidence = adoption.inspect()
        with self.assertRaisesRegex(ValueError, "not ready"):
            general.submit([{"op": "regenerate"}], evidence["model_id"], None, 0)
        self.assertEqual(self.model_json(evidence["model_id"])["status"], "adopt_pending")

    def model_json(self, model_id: str) -> dict:
        return json.loads(
            (self.directory / "models" / model_id / "model.json").read_text(encoding="utf-8")
        )

    def test_unsupported_types_are_refused_at_inspect(self):
        def unsupported(job_directory, manifest):
            result = synthetic_native(job_directory, manifest)
            result["live"] = {
                **result["live"],
                "model_type": "assembly",
                "dependency_free": False,
                "millimeter_units": False,
                "healthy": False,
            }
            return result

        with patch.object(adoption, "_native", side_effect=unsupported):
            evidence = adoption.inspect()
        self.assertFalse(evidence["available"])
        self.assertIn("part or sheetmetal", evidence["reason"])

    def test_native_prefix_refusal_returns_structured_details(self):
        # An assembly current window is refused by the native executor before a
        # live summary exists; the stable prefix becomes a structured refusal
        # with unknown-marked details instead of a bare tool error.
        def refused(job_directory, manifest):
            raise RuntimeError(
                "unsupported_model_type: only part or sheetmetal models can be "
                "adopted; assemblies and drawings keep their own ownership "
                "(adoption refused)"
            )

        with patch.object(adoption, "_native", side_effect=refused):
            evidence = adoption.inspect()
        self.assertFalse(evidence["available"])
        self.assertEqual(evidence["reason_code"], "unsupported_model_type")
        self.assertTrue(evidence["reason"].startswith("unsupported_model_type:"))
        details = evidence["refusal_details"]
        self.assertFalse(details["actual_units_known"])
        self.assertIsNone(details["actual_units"])
        self.assertEqual(details["dependency_inventory"], "unknown")
        self.assertIsNone(evidence["model_id"])
        # The structured refusal must not leave a staging registration behind.
        self.assertEqual(list((self.directory / "models").iterdir()), [])

    def test_native_failure_without_known_prefix_still_raises(self):
        def broken(job_directory, manifest):
            raise RuntimeError("Toolkit call SomethingGet(&x) failed with code -1")

        with patch.object(adoption, "_native", side_effect=broken):
            with self.assertRaisesRegex(RuntimeError, "SomethingGet"):
                adoption.inspect()

    def test_unhealthy_refusal_lists_bounded_feature_details(self):
        # FEAT-006: the unhealthy_features refusal carries the native scan's
        # bounded per-feature diagnosis (id/name/type/status code) plus the
        # true total and truncation flag; admission itself still refuses.
        def unhealthy(job_directory, manifest):
            result = synthetic_native(job_directory, manifest)
            result["live"] = {
                **result["live"],
                "healthy": False,
                "health_details": {
                    "unhealthy_total": 132,
                    "returned": 20,
                    "item_limit": 20,
                    "truncated": True,
                    "items": [
                        {
                            "id": 5,
                            "name": "CUT ID 5",
                            "type_name": "cut",
                            "status_code": 5,
                            "status": "suppressed",
                            "incomplete": False,
                        },
                        {
                            "id": 9,
                            "name": "",
                            "type_name": "protrusion",
                            "status_code": 6,
                            "status": "unregenerated",
                            "incomplete": True,
                        },
                    ],
                },
            }
            return result

        with patch.object(adoption, "_native", side_effect=unhealthy):
            evidence = adoption.inspect()
        self.assertFalse(evidence["available"])
        self.assertEqual(evidence["reason_code"], "unhealthy_features")
        details = evidence["refusal_details"]["unhealthy_features"]
        self.assertEqual(details["unhealthy_total"], 132)
        self.assertTrue(details["truncated"])
        self.assertEqual(details["returned"], 2)
        first, second = details["items"]
        self.assertEqual(first["id"], 5)
        self.assertEqual(first["status_code"], 5)
        self.assertEqual(first["status"], "suppressed")
        self.assertFalse(first["incomplete"])
        self.assertTrue(second["incomplete"])
        self.assertIn("per-feature", evidence["refusal_details"]["health_breakdown"])
        self.assertIn("132", evidence["refusal_details"]["health_breakdown"])

    def test_unhealthy_refusal_without_native_details_stays_unknown(self):
        # An older executor without health_details keeps the combined
        # unknown-marker wording; nothing is invented about causes.
        def unhealthy(job_directory, manifest):
            result = synthetic_native(job_directory, manifest)
            result["live"] = {**result["live"], "healthy": False}
            return result

        with patch.object(adoption, "_native", side_effect=unhealthy):
            evidence = adoption.inspect()
        self.assertFalse(evidence["available"])
        self.assertEqual(evidence["reason_code"], "unhealthy_features")
        self.assertNotIn("unhealthy_features", evidence["refusal_details"])
        self.assertEqual(
            evidence["refusal_details"]["health_breakdown"],
            "combined failed/suppressed/incomplete feature check; per-feature "
            "reasons are unavailable",
        )

    def test_malformed_health_details_fall_back_to_unknown(self):
        def malformed(job_directory, manifest):
            result = synthetic_native(job_directory, manifest)
            result["live"] = {
                **result["live"],
                "healthy": False,
                "health_details": {"unhealthy_total": "many", "items": [{"id": 1}]},
            }
            return result

        with patch.object(adoption, "_native", side_effect=malformed):
            evidence = adoption.inspect()
        self.assertFalse(evidence["available"])
        self.assertEqual(evidence["reason_code"], "unhealthy_features")
        self.assertNotIn("unhealthy_features", evidence["refusal_details"])
        self.assertIn("unavailable", evidence["refusal_details"]["health_breakdown"])

    def test_oversized_health_item_list_is_truncated_defensively(self):
        # A substituted executor that ignores the documented bound still cannot
        # push an unbounded item list into control metadata.
        def oversized(job_directory, manifest):
            result = synthetic_native(job_directory, manifest)
            result["live"] = {
                **result["live"],
                "healthy": False,
                "health_details": {
                    "unhealthy_total": 500,
                    "items": [{"id": i, "status_code": 5, "incomplete": False} for i in range(500)],
                },
            }
            return result

        with patch.object(adoption, "_native", side_effect=oversized):
            evidence = adoption.inspect()
        details = evidence["refusal_details"]["unhealthy_features"]
        self.assertEqual(details["unhealthy_total"], 500)
        self.assertEqual(details["returned"], adoption._HEALTH_ITEM_LIMIT)
        self.assertTrue(details["truncated"])

    def test_inspect_hash_conflict_and_token_failures_leave_no_registration(self):
        real_write = adoption.bridge.write_json

        def fail_token(file, value, **kwargs):
            if file.name.startswith("evidence-"):
                raise OSError("synthetic token write failure")
            return real_write(file, value, **kwargs)

        for name, replacement in (
            (
                "identity",
                patch.object(
                    adoption, "identity", side_effect=PermissionError("synthetic hash failure")
                ),
            ),
            (
                "conflict",
                patch.object(
                    adoption, "_origin_conflict", side_effect=OSError("synthetic scan failure")
                ),
            ),
            ("token", patch.object(adoption.bridge, "write_json", side_effect=fail_token)),
        ):
            with self.subTest(stage=name), replacement:
                with self.assertRaises(OSError):
                    adoption.inspect()
            self.assertEqual(list(general.MODELS.glob("*/model.json")), [])

    def test_empty_origin_inspect_requires_prepare_without_hashing_directory(self):
        def no_origin(directory, manifest):
            result = synthetic_native(directory, manifest)
            result["live"]["origin"] = ""
            return result

        with (
            patch.object(adoption, "_native", side_effect=no_origin),
            patch.object(adoption, "identity") as hashing,
        ):
            result = adoption.inspect()
        self.assertFalse(result["available"])
        self.assertEqual(result["available_modes"], ["prepare"])
        self.assertIsNone(result["model_id"])
        hashing.assert_not_called()
        self.assertEqual(list(general.MODELS.glob("*/model.json")), [])

    def test_missing_nonempty_origin_is_not_downgraded_to_unsaved(self):
        (self.directory / "user_parts" / "001.prt").unlink()
        with self.assertRaises(FileNotFoundError):
            adoption.inspect()
        self.assertEqual(list(general.MODELS.glob("*/model.json")), [])

    def prepare_snapshot(self, key="prepare_business_once", name=None):
        with patch.object(adoption.subprocess, "Popen"):
            job = adoption.prepare(name, key)
        bridge.run_job(job["job_id"])
        result = bridge.get_job(job["job_id"], "compact")
        self.assertEqual(result["status"], "succeeded", result)
        return job, result["result"]["adoption"]

    def test_snapshot_tamper_blocks_renewal_and_apply(self):
        _, evidence = self.prepare_snapshot()
        Path(evidence["file"]["path"]).write_bytes(b"changed staged snapshot")
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            adoption.inspect(evidence["model_id"])
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            adoption.apply(
                evidence["model_id"], evidence["evidence_token"], None, "confirm_tampered"
            )

    def test_prepare_public_result_is_unadopted_without_rewriting_native_evidence(self):
        job, evidence = self.prepare_snapshot()
        native = bridge.read_json(bridge.job_path(job["job_id"]) / "native_result.json")
        self.assertIs(native["adopted"], True)
        for detail in ("compact", "full"):
            result = bridge.get_job(job["job_id"], detail)
            self.assertIs(result["result"]["adopted"], False)
            self.assertEqual(result["result"]["adoption"]["status"], "adopt_pending")
            self.assertEqual(result["revision"], 0)
        self.assertEqual(self.model_json(evidence["model_id"])["adopted_from"]["state"], "prepared")

    def test_snapshot_expiry_renewal_never_repeats_native_and_name_is_frozen(self):
        _, evidence = self.prepare_snapshot()
        mid = evidence["model_id"]
        path = general.model_path(mid) / "adoption" / f"evidence-{evidence['evidence_token']}.json"
        record = bridge.read_json(path)
        record["created"] -= adoption.TOKEN_SECONDS + 1
        _write(path, record)
        with self.assertRaisesRegex(ValueError, "expired"):
            adoption.apply(mid, evidence["evidence_token"], None, "confirm_expired")
        with patch.object(
            adoption, "_native", side_effect=AssertionError("renewal must not call native")
        ):
            renewed = adoption.inspect(mid)
        with self.assertRaisesRegex(ValueError, "cannot be renamed"):
            adoption.apply(mid, renewed["evidence_token"], "different_name", "confirm_renamed")

    def test_snapshot_only_allows_confirm_or_abandon_and_ordinary_submit_is_refused(self):
        _, evidence = self.prepare_snapshot()
        mid = evidence["model_id"]
        with self.assertRaisesRegex(ValueError, "not ready"):
            general.submit([{"op": "regenerate"}], mid, None, 0)
        snapshot = {
            "model": self.model_json(mid),
            "owners": [{"stopped": True}],
            "baseline": {"verified": True},
            "candidate": {"identity": {"path": evidence["file"]["path"]}},
        }
        actions = rec._actions(
            snapshot,
            {
                "loaded": True,
                "owned": True,
                "inspection": {"healthy": True},
                "millimeter_units": True,
                "dependency_free": True,
            },
        )
        self.assertTrue(actions["abandon_new"]["available"])
        for action in ("accept_saved", "accept_live", "restore_baseline"):
            self.assertFalse(actions[action]["available"])

    def test_prepare_same_key_different_arguments_is_refused(self):
        job, _ = self.prepare_snapshot(name="frozen_name")
        replay = adoption.prepare("FROZEN_NAME", "prepare_business_once")
        self.assertEqual(replay["job_id"], job["job_id"])
        with self.assertRaisesRegex(ValueError, "another adoption request"):
            adoption.prepare("another_name", "prepare_business_once")

    def test_prepare_native_failure_stays_protected_and_replay_does_not_rerun(self):
        with patch.object(adoption.subprocess, "Popen"):
            job = adoption.prepare("fail_prepared", "prepare_fail_once")
        bridge.run_job(job["job_id"])
        result = bridge.get_job(job["job_id"], "compact")
        self.assertEqual(result["status"], "unknown_outcome")
        self.assertEqual(self.model_json(job["model_id"])["pending_job"], job["job_id"])
        with patch.object(adoption, "_native", side_effect=AssertionError("no replay")):
            replay = adoption.prepare("fail_prepared", "prepare_fail_once")
        self.assertEqual(replay["job_id"], job["job_id"])

    def test_durable_prepare_commit_finishes_by_polling_without_native_replay(self):
        with patch.object(adoption.subprocess, "Popen"):
            job = adoption.prepare(None, "prepare_commit_once")
        with patch.object(
            adoption, "_finish", side_effect=OSError("synthetic registry materialization failure")
        ):
            bridge.run_job(job["job_id"])
        with patch.object(adoption, "_native", side_effect=AssertionError("no native replay")):
            result = bridge.get_job(job["job_id"], "compact")
        self.assertEqual(result["status"], "succeeded", result)
        self.assertIsNone(self.model_json(job["model_id"])["pending_job"])

    def test_prepare_real_thread_admission_returns_busy_without_second_job(self):
        import threading

        entered, release = threading.Event(), threading.Event()
        outcomes = []

        def hold_spawn(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test barrier timed out")

        def first():
            try:
                outcomes.append(adoption.prepare(None, "prepare_thread_first"))
            except Exception as error:
                outcomes.append(error)

        with patch.object(adoption.subprocess, "Popen", side_effect=hold_spawn):
            thread = threading.Thread(target=first)
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(bridge.ToolkitBusy):
                    adoption.prepare(None, "prepare_thread_second")
            finally:
                release.set()
                thread.join(5)
        self.assertEqual(len(outcomes), 1)
        self.assertIsInstance(outcomes[0], dict, outcomes)
        self.assertEqual(len(list(general.MODELS.glob("*/model.json"))), 1)

    def test_source_change_after_admission_refuses_before_native(self):
        evidence = adoption.inspect()
        with patch.object(adoption.subprocess, "Popen"):
            job = adoption.apply(
                evidence["model_id"], evidence["evidence_token"], None, "admitted_source_changes"
            )
        (self.directory / "user_parts" / "001.prt").write_bytes(b"changed after admission")
        with patch.object(adoption, "_native", side_effect=AssertionError("no native execution")):
            bridge.run_job(job["job_id"])
        result = bridge.get_job(job["job_id"], "compact")
        self.assertEqual((result["status"], result["failure_phase"]), ("failed", "before_native"))
        self.assertIsNone(self.model_json(evidence["model_id"])["pending_job"])

    def test_launch_failure_keeps_auditable_failed_prepare_and_replay_is_stable(self):
        with patch.object(
            adoption.subprocess, "Popen", side_effect=OSError("synthetic launch failure")
        ):
            with self.assertRaisesRegex(OSError, "launch failure"):
                adoption.prepare(None, "prepare_launch_failure")
        result = adoption.prepare(None, "prepare_launch_failure")
        self.assertEqual((result["status"], result["failure_phase"]), ("failed", "before_native"))
        model = self.model_json(result["model_id"])
        self.assertEqual(model["last_job"], result["job_id"])
        self.assertIsNone(model["pending_job"])

    def test_prepared_file_change_after_admission_is_refused_before_worker(self):
        _, evidence = self.prepare_snapshot()
        with patch.object(adoption.subprocess, "Popen"):
            job = adoption.apply(
                evidence["model_id"],
                evidence["evidence_token"],
                None,
                "snapshot_changes_after_admit",
            )
        Path(evidence["file"]["path"]).write_bytes(b"changed after admission")
        with patch.object(adoption, "_native", side_effect=AssertionError("no native execution")):
            bridge.run_job(job["job_id"])
        result = bridge.get_job(job["job_id"], "compact")
        self.assertEqual((result["status"], result["reason"]), ("failed", "snapshot_changed"))
        self.assertEqual(self.model_json(evidence["model_id"])["revision"], 0)

    def test_old_prepare_commit_replay_cannot_revert_later_model_edits(self):
        job, evidence = self.prepare_snapshot()
        mid = evidence["model_id"]
        model = self.model_json(mid)
        model.update(status="ready", revision=7, pending_job=None)
        bridge.write_json(general.model_path(mid) / "model.json", model)
        manifest = bridge.read_json(bridge.job_path(job["job_id"]) / "job.json")
        manifest["status"] = "running"  # Simulate a lost terminal publication.
        bridge.write_json(bridge.job_path(job["job_id"]) / "job.json", manifest)
        with patch.object(adoption, "_native", side_effect=AssertionError("no native replay")):
            result = bridge.get_job(job["job_id"], "compact")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(self.model_json(mid)["revision"], 7)


if __name__ == "__main__":
    main()
