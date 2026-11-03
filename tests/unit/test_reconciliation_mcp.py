"""DEV-034/BUG-055 and DEV-040: recovery over the real stdio MCP protocol.

Every case drives the actual tool registration, published schema and stdio
transport; the business layer is never called directly. The fixture substitutes
two native boundaries and nothing else, both pinned by patch in the child
processes:

- ``reconciliation._deployment`` returns a constant digest (deployment binding
  itself stays covered by the in-process business tests);
- the recovery runner replaces ``reconciliation._native`` with a synthetic
  native result, so this file never connects Toolkit, builds or opens Creo.

The DEV-040 configuration-change case additionally substitutes the runner's
runtime selection to exercise the real Python evidence refusal before _native.

All jobs/models/locks live in a temporary data root; the repository's own
toolkit.lock, config and history are never touched.
"""

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

import bridge
import generic_bridge as general
from creo_mechdog import reconciliation as rec

DEPLOYMENT_FIXTURE = "dev034-protocol-fixture-deployment"
DEAD_RUNNER = {"pid": 2147483647, "created": 12}
DEAD_WORKER = {"pid": 2147483646, "created": 13}
INSPECTION = {"healthy": True, "features": [], "bodies": [], "parameters": {}, "volume_mm3": 10}
#: BUG-110 fixtures: 32-hex model ids that no other case uses.
ACK_ASSEMBLY = "a1" + "0" * 30
ACK_ASSEMBLY_CONFIRM = "b1" + "0" * 30


def _write(file: Path, value: dict) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(value), encoding="utf-8")


def job_id_for(model_id: str) -> str:
    """A distinct valid 32-hex job id per fixture model, stable for the class."""
    return hashlib.sha256(model_id.encode()).hexdigest()[:32]


def _model(
    directory: Path,
    model_id: str,
    name: str,
    *,
    revision: int,
    status: str,
    baseline=False,
    pending=False,
    candidate=False,
    model_type="part",
) -> None:
    """Register one fixture model plus its stopped original job directory."""
    output = directory / "models" / model_id / "output"
    output.mkdir(parents=True, exist_ok=True)
    job_id = job_id_for(model_id)
    model = {
        "model_id": model_id,
        "model_name": name,
        "revision": revision,
        "model_type": model_type,
        "status": status,
        "aliases": {},
        "inspection": INSPECTION,
        "output_directory": str(output),
        "part_file": None,
        "part_sha256": None,
        "last_job": job_id,
        "pending_job": job_id if pending else None,
    }
    if baseline:
        part = output / f"{name}.prt.2"
        part.write_bytes(f"verified fixture part {name}".encode())
        model["part_file"] = str(part)
        model["part_sha256"] = hashlib.sha256(part.read_bytes()).hexdigest()
    original = directory / "jobs" / job_id
    original.mkdir(parents=True, exist_ok=True)
    _write(
        original / "job.json",
        {
            "job_id": job_id,
            "model_id": model_id,
            "kind": "generic",
            "status": status,
            "created_at": bridge.now(),
            "runner_identity": DEAD_RUNNER,
        },
    )
    _write(original / "request.json", {"model": model, "operations": []})
    _write(original / "native_owner.json", DEAD_WORKER)
    if model_type != "part":
        model["components"] = [{"name": "blade_1", "status": "resolved"}]
    if candidate:
        saved = output / f"{name}.prt.3"
        saved.write_bytes(f"saved-but-unregistered {name}".encode())
        _write(
            original / "native_checkpoint.json",
            {
                "part_file": str(saved),
                "success": True,
                "saved_file_reloaded_and_verified": True,
                "inspection": INSPECTION,
                "aliases": {},
            },
        )
    _write(directory / "models" / model_id / "model.json", model)


def prepare_root(directory: Path) -> Path:
    (directory / "jobs").mkdir()
    (directory / "models").mkdir()
    _write(
        directory / "config.json",
        {
            "creo_root": "C:\\dev034-fixture-creo",
            "vcvars64": "C:\\dev034-fixture-vcvars64.bat",
        },
    )
    return directory


def synthetic_native(job_directory: Path, manifest: dict) -> dict:
    """Fixture replacement for reconciliation._native; labeled substitution."""
    request = bridge.read_json(job_directory / "request.json")
    if request["model"]["model_name"] == "dev040_selection_refused":
        raise AssertionError("Python evidence refusal must precede the native boundary")
    choice = request.get("reconciliation", {})
    manifest["worker_started"] = False
    manifest.update(stage="reconciling_native_model", status="running")
    bridge.write_json(job_directory / "job.json", manifest, durable=True)
    manifest["worker_started"] = True
    bridge.write_json(job_directory / "job.json", manifest, durable=True)
    if request["model"]["model_name"] == "dev040_native_refused":
        result = {
            "success": False,
            "connected": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "failed_stage": "recovery_restore_baseline",
            "message": "Recovery refused: Creo session changed since recorded evidence",
        }
        bridge.write_json(job_directory / "native_result.json", result)
        manifest["result"] = result
        raise RuntimeError(result["message"])
    result = {
        "success": True,
        "delivery_complete": True,
        "disconnect_code": 0,
        "saved_file_reloaded_and_verified": True,
        "inspection": INSPECTION,
        "aliases": {},
        "message": "synthetic protocol fixture; no Toolkit call",
    }
    if choice.get("source_file"):
        result["part_file"] = choice["source_file"]
    bridge.write_json(job_directory / "native_result.json", result)
    return result


def child_serve(directory: Path) -> None:
    """Serve the real server.py over stdio against the isolated data root."""
    import server

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
                "tests.unit.test_reconciliation_mcp",
                "--data-root",
                str(directory),
                "--run-job",
                command[3],
            ]
            kwargs["cwd"] = ROOT
        return real_popen(command, *args, **kwargs)

    with ExitStack() as stack:
        stack.enter_context(patch.object(subprocess, "Popen", side_effect=route))
        stack.enter_context(patch.object(rec, "_deployment", return_value=DEPLOYMENT_FIXTURE))
        stack.enter_context(patch.object(server.startup, "start"))
        stack.enter_context(patch.object(server.updates, "start"))
        server.mcp.run()


def child_run_job(directory: Path, job_id: str) -> None:
    bridge.ROOT = directory
    bridge.JOBS = directory / "jobs"
    general.MODELS = directory / "models"
    with ExitStack() as stack:
        stack.enter_context(patch.object(rec, "_deployment", return_value=DEPLOYMENT_FIXTURE))
        stack.enter_context(
            patch.object(bridge, "build_native", return_value=directory / "worker.exe")
        )
        stack.enter_context(patch.object(rec, "_native", side_effect=synthetic_native))
        request = bridge.read_json(bridge.job_path(job_id) / "request.json")
        if request["model"]["model_name"] == "dev040_selection_refused":
            stack.enter_context(
                patch.object(
                    bridge,
                    "config",
                    return_value={
                        "creo_root": "C:\\dev034-fixture-creo",
                        "creo_session_id": "dev040-changed-selection",
                    },
                )
            )
        bridge.run_job(job_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="DEV-034 stdio protocol fixture child")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--run-job")
    args = parser.parse_args()
    if args.serve:
        child_serve(args.data_root)
    elif args.run_job:
        child_run_job(args.data_root, args.run_job)


class ReconcileMcpContract(unittest.IsolatedAsyncioTestCase):
    """T01-T07 protocol matrix; T08 (live Creo terminal states) is real-machine."""

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="dev040_protocol_")
        cls.directory = prepare_root(Path(cls.temporary.name))
        # N*: no pending job (mirror of the reported failed model shape).
        _model(cls.directory, "a" * 32, "dev034_null_pending", revision=0, status="failed")
        _model(cls.directory, "c" * 32, "dev034_null_omitted", revision=0, status="failed")
        _model(cls.directory, "d" * 32, "dev034_null_literals", revision=0, status="failed")
        _model(cls.directory, "e" * 32, "dev034_null_wrong_id", revision=0, status="failed")
        # P*: a real pending job plus a verified baseline (restore_baseline).
        _model(
            cls.directory,
            "1" * 32,
            "dev034_pending_restore",
            revision=1,
            status="unknown_outcome",
            baseline=True,
            pending=True,
        )
        _model(
            cls.directory,
            "2" * 32,
            "dev034_pending_omitted",
            revision=1,
            status="unknown_outcome",
            baseline=True,
            pending=True,
        )
        _model(
            cls.directory,
            "3" * 32,
            "dev034_pending_wrong",
            revision=1,
            status="unknown_outcome",
            baseline=True,
            pending=True,
        )
        _model(
            cls.directory,
            "4" * 32,
            "dev034_pending_revision",
            revision=1,
            status="unknown_outcome",
            baseline=True,
            pending=True,
        )
        _model(
            cls.directory,
            "5" * 32,
            "dev034_pending_token",
            revision=1,
            status="unknown_outcome",
            baseline=True,
            pending=True,
        )
        _model(
            cls.directory,
            "6" * 32,
            "dev034_pending_owner",
            revision=1,
            status="unknown_outcome",
            baseline=True,
            pending=True,
        )
        _model(
            cls.directory,
            "7" * 32,
            "dev034_pending_idempotent",
            revision=1,
            status="unknown_outcome",
            baseline=True,
            pending=True,
        )
        # S*: saved-but-unregistered candidate (accept_saved).
        _model(
            cls.directory,
            "8" * 32,
            "dev034_saved",
            revision=1,
            status="unknown_outcome",
            baseline=True,
            pending=True,
            candidate=True,
        )
        # L*: accept_live must keep requiring an explicit live preflight.
        _model(
            cls.directory,
            "9" * 32,
            "dev034_live_guard",
            revision=1,
            status="unknown_outcome",
            baseline=True,
            pending=True,
        )
        for model_id, name in (
            ("0" * 32, "dev040_selection_refused"),
            ("b" * 32, "dev040_native_refused"),
        ):
            _model(
                cls.directory,
                model_id,
                name,
                revision=1,
                status="unknown_outcome",
                baseline=True,
                pending=True,
            )
        # R13: failed assemblies whose components must never be re-owned.
        for model_id, name in (
            (ACK_ASSEMBLY, "r13_failed_assembly"),
            (ACK_ASSEMBLY_CONFIRM, "r13_failed_assembly_confirm"),
        ):
            _model(
                cls.directory,
                model_id,
                name,
                revision=1,
                status="failed",
                model_type="assembly",
            )

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
                    "tests.unit.test_reconciliation_mcp",
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

    async def inspect_model(self, client, model_id: str) -> dict:
        return await self.call(client, "creo_reconcile_model", {"model_id": model_id})

    def apply_arguments(
        self, model_id: str, evidence: dict, key: str, action: str, pending=...
    ) -> dict:
        """pending=... sends an explicit JSON null; pending=None omits the field."""
        arguments = {
            "model_id": model_id,
            "mode": "apply",
            "action": action,
            "expected_revision": evidence["revision"],
            "evidence_token": evidence["evidence_token"],
            "idempotency_key": key,
        }
        if pending is ...:
            arguments["expected_pending_job_id"] = None
        elif pending is not None:
            arguments["expected_pending_job_id"] = pending
        return arguments

    async def poll(self, client, job_id: str) -> dict:
        for _ in range(90):
            result = await self.call(
                client, "creo_get_job", {"job_id": job_id, "detail": "compact"}
            )
            if result["status"] not in ("queued", "running"):
                return result
            await asyncio.sleep(0.4)
        self.fail(f"recovery job {job_id} never reached a terminal state")

    async def error_text(self, client, arguments: dict) -> str:
        reply = await client.call_tool("creo_reconcile_model", arguments)
        self.assertTrue(reply.is_error, reply)
        return " ".join(block.text for block in reply.content if hasattr(block, "text"))

    def edit_model(self, model_id: str, **changes) -> None:
        file = self.directory / "models" / model_id / "model.json"
        model = json.loads(file.read_text(encoding="utf-8"))
        model.update(changes)
        _write(file, model)

    async def test_schema_publishes_nullable_pending_contract(self):
        async with self.client() as client:
            result = await client.list_tools()
            schema = next(t for t in result.tools if t.name == "creo_reconcile_model").input_schema
        property_schema = schema["properties"]["expected_pending_job_id"]
        self.assertIn({"type": "null"}, property_schema["anyOf"])
        self.assertIsNone(property_schema["default"])
        # BUG-110: the published action list and confirmation flag must match the
        # business layer, or a client cannot select the assembly exit at all.
        action_schema = json.dumps(schema["properties"]["action"])
        self.assertIn("ack_failure", action_schema)
        self.assertEqual(schema["properties"]["confirm_failure_ack"]["type"], "boolean")

    async def test_r13_ack_failure_is_the_exit_for_a_failed_assembly(self):
        model_id = ACK_ASSEMBLY
        async with self.client() as client:
            evidence = await self.inspect_model(client, model_id)
            self.assertTrue(evidence["actions"]["ack_failure"]["available"], evidence["actions"])
            for action in ("restore_baseline", "accept_saved", "accept_live", "abandon_new"):
                self.assertFalse(evidence["actions"][action]["available"], action)
            created = await self.call(
                client,
                "creo_reconcile_model",
                {
                    **self.apply_arguments(model_id, evidence, "r13_assembly_ack", "ack_failure"),
                    "confirm_failure_ack": True,
                },
            )
            result = await self.poll(client, created["job_id"])
            self.assertEqual(result["status"], "succeeded", result)
            after = await self.inspect_model(client, model_id)
            self.assertEqual(after["status"], "ready")
            self.assertEqual(after["revision"], evidence["revision"])
            record = json.loads(
                (self.directory / "models" / model_id / "model.json").read_text(encoding="utf-8")
            )
            self.assertEqual(record["reconciliation"]["action"], "ack_failure")
            self.assertTrue(record["reconciliation"]["component_ownership_preserved"])
            self.assertEqual(record["components"], [{"name": "blade_1", "status": "resolved"}])
            self.assertFalse(
                (self.directory / "jobs" / created["job_id"] / "native_result.json").exists()
            )

    async def test_r13_ack_failure_requires_the_confirmation_flag(self):
        model_id = ACK_ASSEMBLY_CONFIRM
        async with self.client() as client:
            evidence = await self.inspect_model(client, model_id)
            text = await self.error_text(
                client,
                self.apply_arguments(model_id, evidence, "r13_assembly_ack_flag", "ack_failure"),
            )
            self.assertIn("confirm_failure_ack=true", text)
            after = await self.inspect_model(client, model_id)
            self.assertEqual(after["status"], "failed")
            self.assertEqual(after["revision"], evidence["revision"])

    async def test_t01_t02_null_and_omission_apply_and_complete(self):
        async with self.client() as client:
            for model_id, key, pending in (
                ("a" * 32, "dev034_null_explicit", ...),
                ("c" * 32, "dev034_null_omitted", None),
            ):
                evidence = await self.inspect_model(client, model_id)
                self.assertIsNone(evidence["pending_job"])
                self.assertTrue(evidence["actions"]["abandon_new"]["available"])
                created = await self.call(
                    client,
                    "creo_reconcile_model",
                    self.apply_arguments(model_id, evidence, key, "abandon_new", pending),
                )
                result = await self.poll(client, created["job_id"])
                self.assertEqual(result["status"], "succeeded", result)
                after = await self.inspect_model(client, model_id)
                self.assertEqual(after["status"], "abandoned")
                self.assertEqual(after["revision"], 0)
            # Omission must not mask a real pending job on another model.
            evidence = await self.inspect_model(client, "2" * 32)
            text = await self.error_text(
                client,
                self.apply_arguments(
                    "2" * 32, evidence, "dev034_omit_masks_nothing", "restore_baseline", None
                ),
            )
            self.assertIn("Stale expected_pending_job_id", text)
            self.assertIn(job_id_for("2" * 32), text)

    async def test_t03_invalid_values_get_precise_input_errors(self):
        async with self.client() as client:
            evidence = await self.inspect_model(client, "d" * 32)
            for value, key in (("", "dev034_empty_str"), ("   ", "dev034_blank_str")):
                text = await self.error_text(
                    client,
                    self.apply_arguments("d" * 32, evidence, key, "abandon_new", value),
                )
                self.assertIn("expected_pending_job_id must be the pending job id", text)
                self.assertNotIn("Stale", text)
                self.assertIn(repr(value), text)
            # A wrong scalar type is rejected by protocol validation, not as stale.
            text = await self.error_text(
                client,
                self.apply_arguments("d" * 32, evidence, "dev034_bad_type", "abandon_new", 123),
            )
            self.assertNotIn("Stale", text)
            # The SDK pre-parses the literal string "null" to JSON null (mcp 2.3.0
            # pre_parse_json); this locks that compatibility in as contract.
            created = await self.call(
                client,
                "creo_reconcile_model",
                self.apply_arguments(
                    "d" * 32, evidence, "dev034_literal_null", "abandon_new", "null"
                ),
            )
            result = await self.poll(client, created["job_id"])
            self.assertEqual(result["status"], "succeeded", result)

    async def test_t04_t07_action_contracts_and_exact_pending_match(self):
        async with self.client() as client:
            # Exact non-empty pending id is accepted; revision is preserved.
            model_id = "1" * 32
            evidence = await self.inspect_model(client, model_id)
            self.assertTrue(evidence["actions"]["restore_baseline"]["available"])
            created = await self.call(
                client,
                "creo_reconcile_model",
                self.apply_arguments(
                    model_id,
                    evidence,
                    "dev034_restore_exact",
                    "restore_baseline",
                    evidence["pending_job"],
                ),
            )
            result = await self.poll(client, created["job_id"])
            self.assertEqual(result["status"], "succeeded", result)
            self.assertEqual(result["revision"], evidence["revision"])
            # A syntactically valid but wrong id stays stale, with both ids named.
            evidence = await self.inspect_model(client, "3" * 32)
            text = await self.error_text(
                client,
                self.apply_arguments(
                    "3" * 32, evidence, "dev034_wrong_id", "restore_baseline", "f" * 32
                ),
            )
            self.assertIn("Stale expected_pending_job_id", text)
            self.assertIn("f" * 32, text)
            self.assertIn(job_id_for("3" * 32), text)
            # A valid id sent to a model without pending is stale, not accepted.
            evidence = await self.inspect_model(client, "e" * 32)
            text = await self.error_text(
                client,
                self.apply_arguments(
                    "e" * 32, evidence, "dev034_id_on_null_model", "abandon_new", "f" * 32
                ),
            )
            self.assertIn("model pending_job is None", text)
            # accept_saved adopts the registered candidate and bumps revision once.
            evidence = await self.inspect_model(client, "8" * 32)
            self.assertTrue(evidence["actions"]["accept_saved"]["available"])
            created = await self.call(
                client,
                "creo_reconcile_model",
                self.apply_arguments(
                    "8" * 32,
                    evidence,
                    "dev034_accept_saved",
                    "accept_saved",
                    evidence["pending_job"],
                ),
            )
            result = await self.poll(client, created["job_id"])
            self.assertEqual(result["status"], "succeeded", result)
            self.assertEqual(result["revision"], evidence["revision"] + 1)
            # accept_live still demands an explicit live preflight.
            evidence = await self.inspect_model(client, "9" * 32)
            text = await self.error_text(
                client,
                self.apply_arguments(
                    "9" * 32,
                    evidence,
                    "dev034_live_without_preflight",
                    "accept_live",
                    evidence["pending_job"],
                ),
            )
            self.assertIn("live evidence is unavailable", text)

    async def test_t05_stale_token_and_owner_protections_survive(self):
        async with self.client() as client:
            evidence = await self.inspect_model(client, "4" * 32)
            self.edit_model("4" * 32, revision=2)
            text = await self.error_text(
                client,
                self.apply_arguments(
                    "4" * 32,
                    evidence,
                    "dev034_revision_moved",
                    "restore_baseline",
                    job_id_for("4" * 32),
                ),
            )
            self.assertIn("Stale expected_revision", text)
            self.assertIn("model revision is 2", text)
            # An expired token is rejected without refreshing it.
            evidence = await self.inspect_model(client, "5" * 32)
            file = (
                self.directory
                / "models"
                / ("5" * 32)
                / "reconciliation"
                / f"evidence-{evidence['evidence_token']}.json"
            )
            record = json.loads(file.read_text(encoding="utf-8"))
            record["created"] = time.time() - rec.TOKEN_SECONDS - 1
            _write(file, record)
            text = await self.error_text(
                client,
                self.apply_arguments(
                    "5" * 32,
                    evidence,
                    "dev034_token_expired",
                    "restore_baseline",
                    job_id_for("5" * 32),
                ),
            )
            self.assertIn("expired", text)
            # A foreign token from another model never authorizes this one.
            foreign = await self.inspect_model(client, "4" * 32)
            text = await self.error_text(
                client,
                {
                    **self.apply_arguments(
                        "5" * 32,
                        evidence,
                        "dev034_token_foreign",
                        "restore_baseline",
                        job_id_for("5" * 32),
                    ),
                    "evidence_token": foreign["evidence_token"],
                },
            )
            self.assertIn("missing or expired", text)
            # An existing recovery reservation reports its holder and changes nothing.
            evidence = await self.inspect_model(client, "6" * 32)
            self.edit_model("6" * 32, recovery_pending="e" * 32)
            busy = await self.call(
                client,
                "creo_reconcile_model",
                self.apply_arguments(
                    "6" * 32,
                    evidence,
                    "dev034_owner_busy",
                    "restore_baseline",
                    job_id_for("6" * 32),
                ),
                error=True,
            )
            self.assertEqual(busy["status"], "busy")
            self.assertEqual(busy["blocking_job_id"], "e" * 32)

    async def test_t06_idempotent_replay_and_key_conflicts(self):
        async with self.client() as client:
            evidence = await self.inspect_model(client, "7" * 32)
            arguments = self.apply_arguments(
                "7" * 32, evidence, "dev034_repeat_key", "restore_baseline", evidence["pending_job"]
            )
            created = await self.call(client, "creo_reconcile_model", arguments)
            self.assertEqual((await self.poll(client, created["job_id"]))["status"], "succeeded")
            duplicate = await self.call(client, "creo_reconcile_model", arguments)
            self.assertEqual(duplicate["job_id"], created["job_id"])
            self.assertEqual(duplicate["status"], "succeeded")
            text = await self.error_text(client, {**arguments, "action": "accept_saved"})
            self.assertIn("another recovery request", text)

    async def test_dev040_before_native_refusal_and_compact_idempotent_replay(self):
        model_id = "0" * 32
        original = self.directory / "jobs" / job_id_for(model_id) / "job.json"
        original_bytes = original.read_bytes()
        async with self.client() as client:
            evidence = await self.inspect_model(client, model_id)
            arguments = self.apply_arguments(
                model_id,
                evidence,
                "dev040_selection_refusal",
                "restore_baseline",
                evidence["pending_job"],
            )
            created = await self.call(client, "creo_reconcile_model", arguments)
            result = await self.poll(client, created["job_id"])
            self.assertEqual(result["status"], "failed", result)
            self.assertEqual(result["stage"], "reconciliation_refused")
            self.assertEqual(result["reason"], "session_selection_changed")
            self.assertEqual(result["failure_phase"], "before_native")
            self.assertTrue(result["recovery_pending_released"])
            self.assertIn(
                "Creo session selection changed after recovery admission", result["message"]
            )
            duplicate = await self.call(client, "creo_reconcile_model", arguments)
            for key in (
                "job_id",
                "status",
                "stage",
                "reason",
                "failure_phase",
                "recovery_pending_released",
            ):
                self.assertEqual(duplicate[key], result[key])
            after = await self.inspect_model(client, model_id)
            self.assertEqual(after["status"], "unknown_outcome")
            self.assertEqual(after["revision"], evidence["revision"])
            self.assertEqual(after["pending_job"], evidence["pending_job"])
            self.assertIsNone(after["recovery_pending"])
        self.assertEqual(original.read_bytes(), original_bytes)
        self.assertFalse(
            (self.directory / "jobs" / created["job_id"] / "native_result.json").exists()
        )

    async def test_dev040_native_refusal_retains_unknown_and_compact_phase(self):
        model_id = "b" * 32
        async with self.client() as client:
            evidence = await self.inspect_model(client, model_id)
            arguments = self.apply_arguments(
                model_id,
                evidence,
                "dev040_native_refusal",
                "restore_baseline",
                evidence["pending_job"],
            )
            created = await self.call(client, "creo_reconcile_model", arguments)
            result = await self.poll(client, created["job_id"])
            self.assertEqual(result["status"], "unknown_outcome", result)
            self.assertEqual(result["stage"], "reconciliation_unconfirmed")
            self.assertEqual(result["reason"], "native_outcome_unconfirmed")
            self.assertEqual(result["failure_phase"], "native_worker_started")
            self.assertFalse(result["recovery_pending_released"])
            self.assertEqual(result["result"]["failed_stage"], "recovery_restore_baseline")
            self.assertEqual(
                result["result"]["message"],
                "Recovery refused: Creo session changed since recorded evidence",
            )
            self.assertIn("may have started", result["message"])
            duplicate = await self.call(client, "creo_reconcile_model", arguments)
            self.assertEqual(duplicate["job_id"], result["job_id"])
            self.assertEqual(duplicate["failure_phase"], result["failure_phase"])
            self.assertEqual(duplicate["reason"], result["reason"])
            after = await self.inspect_model(client, model_id)
            self.assertEqual(after["recovery_pending"], created["job_id"])
            self.assertEqual(after["pending_job"], evidence["pending_job"])
            self.assertEqual(after["revision"], evidence["revision"])


if __name__ == "__main__":
    main()
