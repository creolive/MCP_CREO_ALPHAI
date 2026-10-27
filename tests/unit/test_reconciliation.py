"""BUG-001/FEAT-018: evidence, admission and crash-safe commit boundaries."""

import concurrent.futures
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import inspection_refs
from creo_mechdog import reconciliation as rec


class Reconciliation(unittest.TestCase):
    def setUp(self):
        self.folder = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.folder)
        self.enterContext(patch.object(bridge, "ROOT", self.root))
        self.enterContext(patch.object(bridge, "JOBS", self.root / "jobs"))
        self.enterContext(patch.object(bridge, "config", return_value={}))
        self.enterContext(patch.object(general, "MODELS", self.root / "models"))
        self.enterContext(patch.object(rec, "_deployment", return_value="fixture-deployment"))
        self.enterContext(
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe")
        )
        self.mid, self.original = "a" * 32, "b" * 32
        output = general.model_path(self.mid) / "output"
        output.mkdir(parents=True)
        self.part = output / "owned_part.prt.2"
        self.part.write_bytes(b"verified checkpoint fixture, never used by Creo")
        self.state = {
            "healthy": True,
            "features": [],
            "bodies": [],
            "parameters": {},
            "volume_mm3": 10,
        }
        self.model = {
            "model_id": self.mid,
            "model_name": "owned_part",
            "revision": 1,
            "model_type": "part",
            "status": "unknown_outcome",
            "aliases": {},
            "inspection": self.state,
            "output_directory": str(output),
            "part_file": str(self.part),
            "part_sha256": hashlib.sha256(self.part.read_bytes()).hexdigest(),
            "last_job": self.original,
            "pending_job": self.original,
        }
        self.save_model()
        directory = bridge.job_path(self.original)
        directory.mkdir(parents=True)
        bridge.write_json(
            directory / "job.json",
            {
                "job_id": self.original,
                "model_id": self.mid,
                "kind": "generic",
                "status": "unknown_outcome",
                "created_at": bridge.now(),
                "runner_identity": {"pid": 2147483647, "created": 12},
            },
        )
        bridge.write_json(directory / "request.json", {"model": self.model, "operations": []})
        bridge.write_json(directory / "native_owner.json", {"pid": 2147483646, "created": 13})

    def save_model(self):
        bridge.write_json(general.model_path(self.mid) / "model.json", self.model)

    def prepare(self, action="restore_baseline", key="recovery_fixture", live=False):
        evidence = rec.inspect(self.mid, live)
        args = (
            self.mid,
            action,
            self.model["revision"],
            self.model.get("pending_job"),
            evidence["evidence_token"],
            key,
        )
        with patch.object(bridge.subprocess, "Popen"):
            created = rec.apply(*args)
        return created, args

    def native(self, directory, manifest):
        manifest["worker_started"] = True
        value = {
            "success": True,
            "saved_file_reloaded_and_verified": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "inspection": self.state,
            "aliases": {},
            "part_file": str(self.part),
        }
        bridge.write_json(directory / "native_result.json", value)
        return value

    def execute(self, created, native=None):
        with patch.object(rec, "_native", side_effect=native or self.native):
            bridge.run_job(created["job_id"])
        return bridge.get_job(created["job_id"])

    def test_inspect_during_busy_is_persisted_and_does_not_clear_original(self):
        before = (general.model_path(self.mid) / "model.json").read_bytes()
        with bridge.toolkit_lock(operation="other-model", model_id="f" * 32):
            inspected = rec.inspect(self.mid)
        self.assertTrue(inspected["actions"]["restore_baseline"]["available"])
        self.assertEqual(before, (general.model_path(self.mid) / "model.json").read_bytes())

    def test_restore_keeps_revision_and_original_history_and_is_idempotent(self):
        original = (bridge.job_path(self.original) / "job.json").read_bytes()
        created, args = self.prepare()
        self.assertEqual(general.model_info(self.mid)["pending_job"], self.original)
        result = self.execute(created)
        model = general.model_info(self.mid)
        self.assertEqual(
            (result["status"], model["status"], model["revision"]), ("succeeded", "ready", 1)
        )
        self.assertIsNone(model["pending_job"])
        self.assertEqual(original, (bridge.job_path(self.original) / "job.json").read_bytes())
        with patch.object(rec, "_native") as worker:
            duplicate = rec.apply(*args)
        self.assertEqual(duplicate["job_id"], created["job_id"])
        worker.assert_not_called()
        self.assertTrue(bridge.get_job(self.original)["recovery"]["model_currently_available"])

    def test_stale_revision_pending_and_changed_file_are_rejected(self):
        for field, value in (("revision", 2), ("pending_job", None)):
            evidence = rec.inspect(self.mid)
            saved = self.model[field]
            self.model[field] = value
            self.save_model()
            with self.assertRaisesRegex(ValueError, "Stale expected"):
                rec.apply(
                    self.mid,
                    "restore_baseline",
                    1,
                    self.original,
                    evidence["evidence_token"],
                    "stale_test",
                )
            self.model[field] = saved
            self.save_model()
        evidence = rec.inspect(self.mid)
        self.part.write_bytes(b"external tampering")
        with self.assertRaisesRegex(ValueError, "Stale evidence"):
            rec.apply(
                self.mid,
                "restore_baseline",
                1,
                self.original,
                evidence["evidence_token"],
                "changed_file",
            )

    def test_active_runner_and_permission_unknown_reject(self):
        for observed in (
            {"pid": 2147483647, "created": 12, "alive": True},
            {"pid": 2147483647, "alive": None, "windows_error": 5},
        ):
            with patch.object(rec, "process_identity", return_value=observed):
                result = rec.inspect(self.mid)
                self.assertFalse(result["actions"]["restore_baseline"]["available"])

    def test_pid_reuse_is_not_old_owner(self):
        with patch.object(
            rec, "process_identity", return_value={"pid": 10, "created": 22, "alive": True}
        ):
            self.assertTrue(rec._stopped({"pid": 10, "created": 21})["stopped"])
            self.assertFalse(rec._stopped({"pid": 10})["stopped"])

    def test_exited_process_object_disappearance_does_not_expire_safe_evidence(self):
        snapshot = rec._snapshot(self.mid)
        before = rec._binding(snapshot)
        for owner in snapshot["owners"]:
            owner["runner"]["observed"] = {"alive": False, "created": 12}
            owner["worker"]["observed"] = {"alive": False, "windows_error": 87}
        self.assertEqual(before, rec._binding(snapshot))
        snapshot["owners"][0]["stopped"] = False
        self.assertNotEqual(before, rec._binding(snapshot))

    def test_live_foreign_unhealthy_or_external_dependencies_not_accepted(self):
        for field, value in (
            ("owned", False),
            ("dependency_free", False),
            ("millimeter_units", False),
        ):
            live = {
                "loaded": True,
                "owned": True,
                "dependency_free": True,
                "millimeter_units": True,
                "inspection": self.state,
                field: value,
            }
            self.assertFalse(
                rec._actions(rec._snapshot(self.mid), live)["accept_live"]["available"]
            )

    def test_missing_native_identity_does_not_authorize_recovery(self):
        (bridge.job_path(self.original) / "native_owner.json").unlink()
        self.assertFalse(rec.inspect(self.mid)["actions"]["restore_baseline"]["available"])

    def test_admission_and_execution_mutation_are_separately_checked(self):
        created, _ = self.prepare()
        self.part.write_bytes(b"changed after admission")
        with patch.object(rec, "_native") as worker:
            bridge.run_job(created["job_id"])
        worker.assert_not_called()
        model = general.model_info(self.mid)
        self.assertEqual(model["pending_job"], self.original)
        self.assertIsNone(model["recovery_pending"])
        self.assertEqual((model["status"], model["revision"]), ("unknown_outcome", 1))
        result = bridge.get_job(created["job_id"], "compact")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "reconciliation_refused")
        self.assertEqual(result["reason"], "source_changed")
        self.assertEqual(result["failure_phase"], "before_native")
        self.assertTrue(result["recovery_pending_released"])

    def test_session_selection_refusal_clears_only_its_reservation_and_replays_failure(self):
        original = (bridge.job_path(self.original) / "job.json").read_bytes()
        created, args = self.prepare()
        with (
            patch.object(bridge, "config", return_value={"creo_session_id": "changed"}),
            patch.object(rec, "_native") as worker,
        ):
            bridge.run_job(created["job_id"])
        worker.assert_not_called()
        result = bridge.get_job(created["job_id"], "compact")
        self.assertEqual(result["reason"], "session_selection_changed")
        self.assertEqual(result["failure_phase"], "before_native")
        self.assertTrue(result["recovery_pending_released"])
        with patch.object(bridge.subprocess, "Popen") as runner:
            duplicate = rec.apply(*args)
        runner.assert_not_called()
        self.assertEqual(duplicate["job_id"], created["job_id"])
        self.assertEqual(duplicate["status"], "failed")
        self.assertEqual(duplicate["reason"], result["reason"])
        self.assertIsNone(general.model_info(self.mid)["recovery_pending"])
        self.assertEqual(original, (bridge.job_path(self.original) / "job.json").read_bytes())

    def test_before_native_refusal_does_not_release_replacement_reservation(self):
        created, _ = self.prepare()
        model = general.model_info(self.mid)
        model["recovery_pending"] = "c" * 32
        bridge.write_json(general.model_path(self.mid) / "model.json", model)
        with patch.object(rec, "_native") as worker:
            bridge.run_job(created["job_id"])
        worker.assert_not_called()
        result = bridge.get_job(created["job_id"])
        self.assertEqual(result["reason"], "reservation_changed")
        self.assertFalse(result["recovery_pending_released"])
        self.assertEqual(general.model_info(self.mid)["recovery_pending"], "c" * 32)

    def test_before_native_cleanup_failure_preserves_protection_and_reports_error(self):
        created, _ = self.prepare()
        real_write = bridge.write_json

        def refuse_cleanup(file, value, **kwargs):
            if file.name == "model.json" and value.get("recovery_pending") is None:
                raise PermissionError("Injected recovery reservation write denial")
            return real_write(file, value, **kwargs)

        with (
            patch.object(bridge, "config", return_value={"creo_session_id": "changed"}),
            patch.object(bridge, "write_json", side_effect=refuse_cleanup),
            patch.object(rec, "_native") as worker,
        ):
            bridge.run_job(created["job_id"])
        worker.assert_not_called()
        result = bridge.get_job(created["job_id"], "compact")
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["recovery_pending_released"])
        self.assertIn("write denial", result["recovery_pending_cleanup_error"])
        self.assertEqual(general.model_info(self.mid)["recovery_pending"], created["job_id"])

    def test_refusal_cleanup_is_locked_and_terminal_is_published_after_release(self):
        created, _ = self.prepare()
        real_write = bridge.write_json
        observed = []

        def observe(file, value, **kwargs):
            if file.name == "model.json" and value.get("recovery_pending") is None:
                with self.assertRaises(bridge.ToolkitBusy):
                    with bridge.toolkit_lock(operation="probe_cleanup_lock"):
                        self.fail("Recovery cleanup was outside the channel lock")
                observed.append("cleanup_locked")
            if file.name == "job.json" and value.get("finished_at"):
                with bridge.toolkit_lock(operation="probe_terminal_release"):
                    observed.append("terminal_after_release")
            return real_write(file, value, **kwargs)

        with (
            patch.object(bridge, "config", return_value={"creo_session_id": "changed"}),
            patch.object(bridge, "write_json", side_effect=observe),
        ):
            self.execute(created)
        self.assertEqual(observed, ["cleanup_locked", "terminal_after_release"])

    def test_runner_launch_failure_releases_only_own_reservation_and_stays_idempotent(self):
        evidence = rec.inspect(self.mid)
        args = (
            self.mid,
            "restore_baseline",
            1,
            self.original,
            evidence["evidence_token"],
            "failed_runner_key",
        )
        real_write = bridge.write_json
        observed = []

        def observe(file, value, **kwargs):
            if file.name == "model.json" and value.get("recovery_pending") is None:
                with self.assertRaises(bridge.ToolkitBusy):
                    with bridge.toolkit_lock(operation="probe_launch_cleanup_lock"):
                        self.fail("Launch failure cleanup was outside the channel lock")
                observed.append("cleanup_locked")
            if file.name == "job.json" and value.get("finished_at"):
                with bridge.toolkit_lock(operation="probe_launch_terminal_release"):
                    observed.append("terminal_after_release")
            return real_write(file, value, **kwargs)

        with (
            patch.object(bridge.subprocess, "Popen", side_effect=OSError("runner denied")),
            patch.object(bridge, "write_json", side_effect=observe),
        ):
            with self.assertRaisesRegex(OSError, "runner denied"):
                rec.apply(*args)
        self.assertEqual(observed, ["cleanup_locked", "terminal_after_release"])
        model = general.model_info(self.mid)
        self.assertIsNone(model["recovery_pending"])
        self.assertEqual(model["pending_job"], self.original)
        with patch.object(bridge.subprocess, "Popen") as runner:
            duplicate = rec.apply(*args)
        runner.assert_not_called()
        self.assertEqual(duplicate["status"], "failed")
        self.assertEqual(duplicate["reason"], "runner_start_failed")
        self.assertTrue(duplicate["recovery_pending_released"])

    def test_channel_finalization_error_does_not_replace_refusal_or_cleanup_result(self):
        created, _ = self.prepare()
        real_lock = bridge.toolkit_lock

        @contextmanager
        def finalization_failure(**kwargs):
            with real_lock(**kwargs):
                yield
            raise OSError("Injected channel finalization failure")

        with (
            patch.object(bridge, "toolkit_lock", side_effect=finalization_failure),
            patch.object(bridge, "config", return_value={"creo_session_id": "changed"}),
            patch.object(rec, "_native") as worker,
        ):
            bridge.run_job(created["job_id"])
        worker.assert_not_called()
        result = bridge.get_job(created["job_id"], "compact")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "session_selection_changed")
        self.assertEqual(result["failure_phase"], "before_native")
        self.assertTrue(result["recovery_pending_released"])
        self.assertIn("finalization failure", result["channel_finalization_error"])
        self.assertIsNone(general.model_info(self.mid)["recovery_pending"])

    def test_runner_launch_and_channel_finalization_failures_publish_original_failure(self):
        evidence = rec.inspect(self.mid)
        args = (
            self.mid,
            "restore_baseline",
            1,
            self.original,
            evidence["evidence_token"],
            "failed_runner_and_channel_key",
        )
        launch_error = OSError("Injected runner launch failure")
        real_lock, real_write = bridge.toolkit_lock, bridge.write_json
        terminal_after_release = []

        @contextmanager
        def finalization_failure(**kwargs):
            with real_lock(**kwargs):
                yield
            raise OSError("Injected submission channel finalization failure")

        def observe(file, value, **kwargs):
            if file.name == "job.json" and value.get("finished_at"):
                with real_lock(operation="probe_combined_failure_release"):
                    terminal_after_release.append(True)
            return real_write(file, value, **kwargs)

        with (
            patch.object(bridge, "toolkit_lock", side_effect=finalization_failure),
            patch.object(bridge.subprocess, "Popen", side_effect=launch_error),
            patch.object(bridge, "write_json", side_effect=observe),
        ):
            with self.assertRaises(OSError) as raised:
                rec.apply(*args)
        self.assertIs(raised.exception, launch_error)
        self.assertEqual(terminal_after_release, [True])
        model = general.model_info(self.mid)
        self.assertIsNone(model["recovery_pending"])
        self.assertEqual(model["pending_job"], self.original)
        with patch.object(bridge.subprocess, "Popen") as runner:
            result = rec.apply(*args)
        runner.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "reconciliation_refused")
        self.assertEqual(result["reason"], "runner_start_failed")
        self.assertEqual(result["failure_phase"], "before_native")
        self.assertEqual(result["message"], str(launch_error))
        self.assertTrue(result["recovery_pending_released"])
        self.assertIn("finalization failure", result["channel_finalization_error"])

    def test_runner_channel_admission_failure_keeps_unlocked_reservation(self):
        created, _ = self.prepare()
        with bridge.toolkit_lock(operation="other_job", job_id="c" * 32):
            with patch.object(rec, "_native") as worker:
                bridge.run_job(created["job_id"])
        worker.assert_not_called()
        result = bridge.get_job(created["job_id"], "compact")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failure_phase"], "channel_admission")
        self.assertFalse(result["recovery_pending_released"])
        self.assertEqual(result["busy"]["blocking_job_id"], "c" * 32)
        self.assertEqual(general.model_info(self.mid)["recovery_pending"], created["job_id"])

    def test_delivered_native_session_refusal_keeps_unknown_and_original_message(self):
        created, _ = self.prepare()
        message = "Recovery refused: Creo session changed since recorded evidence"

        def refuse(command, **kwargs):
            # Native report substitution only: the real _native dispatch and
            # delivery checks still execute, without starting a worker/Toolkit.
            bridge.write_json(
                bridge.job_path(created["job_id"]) / "native_result.json",
                {
                    "success": False,
                    "connected": True,
                    "delivery_complete": True,
                    "disconnect_code": 0,
                    "failed_stage": "recovery_restore_baseline",
                    "message": message,
                },
            )
            return subprocess.CompletedProcess(command, 1)

        with (
            patch.object(rec.subprocess, "run", side_effect=refuse) as dispatch,
            patch.object(bridge, "native_environment", return_value={}),
        ):
            bridge.run_job(created["job_id"])
        self.assertEqual(dispatch.call_count, 1)
        result = bridge.get_job(created["job_id"], "compact")
        self.assertEqual(result["status"], "unknown_outcome")
        self.assertEqual(result["failure_phase"], "native_worker_started")
        self.assertEqual(result["reason"], "native_outcome_unconfirmed")
        self.assertEqual(result["result"]["failed_stage"], "recovery_restore_baseline")
        self.assertEqual(result["result"]["message"], message)
        self.assertIn(message, result["message"])
        self.assertIn("may have started", result["message"])
        self.assertFalse(result["recovery_pending_released"])
        self.assertEqual(general.model_info(self.mid)["recovery_pending"], created["job_id"])

    def test_post_native_evidence_refusal_remains_unknown(self):
        created, _ = self.prepare()
        with patch.object(
            rec,
            "_check_execution",
            side_effect=[None, rec.RecoveryRefused("deployment_changed", "deployment changed")],
        ):
            result = self.execute(created)
        self.assertEqual(result["status"], "unknown_outcome")
        self.assertEqual(result["stage"], "reconciliation_unconfirmed")
        self.assertEqual(result["reason"], "deployment_changed")
        self.assertEqual(result["failure_phase"], "native_worker_started")
        self.assertFalse(result["recovery_pending_released"])
        self.assertEqual(general.model_info(self.mid)["recovery_pending"], created["job_id"])

    def test_failed_native_dispatch_is_still_possibly_started(self):
        created, _ = self.prepare()
        with (
            patch.object(rec.subprocess, "run", side_effect=PermissionError("dispatch denied")),
            patch.object(bridge, "native_environment", return_value={}),
        ):
            bridge.run_job(created["job_id"])
        result = bridge.get_job(created["job_id"])
        self.assertEqual(result["status"], "unknown_outcome")
        self.assertEqual(result["failure_phase"], "native_worker_started")
        self.assertEqual(general.model_info(self.mid)["recovery_pending"], created["job_id"])

    def test_recovery_timeout_keeps_both_reservations(self):
        created, _ = self.prepare()

        def timeout(directory, manifest):
            manifest["worker_started"] = True
            raise RuntimeError("timeout")

        result = self.execute(created, timeout)
        self.assertEqual(result["status"], "unknown_outcome")
        self.assertEqual(general.model_info(self.mid)["recovery_pending"], created["job_id"])
        with self.assertRaises(bridge.ToolkitBusy):
            general.submit([], model_id=self.mid, expected_revision=1)

    def test_committed_decision_materializes_after_registry_write_crash(self):
        created, args = self.prepare()
        real_write = bridge.write_json

        def crash(file, value, **kwargs):
            if file.name == "model.json" and value.get("reconciliation"):
                raise OSError("Injected metadata write interruption")
            return real_write(file, value, **kwargs)

        with (
            patch.object(rec, "_native", side_effect=self.native),
            patch.object(bridge, "write_json", side_effect=crash),
        ):
            bridge.run_job(created["job_id"])
        self.assertEqual(general.model_info(self.mid)["recovery_pending"], created["job_id"])
        code = """
import json,sys
from pathlib import Path
import bridge,generic_bridge
from creo_mechdog import reconciliation
bridge.ROOT=Path(sys.argv[1]);bridge.JOBS=bridge.ROOT/'jobs'
generic_bridge.MODELS=bridge.ROOT/'models'
def forbidden(*args,**kwargs):raise AssertionError('Restart replayed native work')
reconciliation._native=forbidden
print(json.dumps(bridge.get_job(sys.argv[2])))
"""
        restarted = subprocess.run(
            [sys.executable, "-c", code, str(self.root), created["job_id"]],
            cwd=Path(rec.__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=bridge.HIDDEN,
        )
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        self.assertEqual(json.loads(restarted.stdout)["status"], "succeeded")
        with patch.object(rec, "_native") as native:
            result = rec.apply(*args)
        native.assert_not_called()
        self.assertEqual(result["status"], "succeeded")
        self.assertIsNone(general.model_info(self.mid)["pending_job"])

    def test_verified_but_uncommitted_decision_never_auto_completes(self):
        created, _ = self.prepare()
        real_write = bridge.write_json

        def crash(file, value, **kwargs):
            if file.name.startswith("intent-") and value.get("state") == "committed":
                raise OSError("Injected decision interruption")
            return real_write(file, value, **kwargs)

        with (
            patch.object(rec, "_native", side_effect=self.native),
            patch.object(bridge, "write_json", side_effect=crash),
        ):
            bridge.run_job(created["job_id"])
        result = bridge.get_job(created["job_id"])
        self.assertEqual(result["status"], "unknown_outcome")
        self.assertEqual(general.model_info(self.mid)["revision"], 1)
        self.assertEqual(general.model_info(self.mid)["pending_job"], self.original)

    def test_live_requires_explicit_preflight_and_increments_once(self):
        self.model.update(revision=0, part_file=None, part_sha256=None)
        self.save_model()
        evidence = rec.inspect(self.mid)
        self.assertFalse(evidence["actions"]["accept_live"]["available"])
        live = {
            "loaded": True,
            "owned": True,
            "millimeter_units": True,
            "dependency_free": True,
            "inspection": self.state,
        }
        with patch.object(rec, "_live", return_value=live):
            created, args = self.prepare("accept_live", live=True)
        result = self.execute(created)
        self.assertEqual(result["revision"], 1)
        self.assertEqual(rec.apply(*args)["revision"], 1)

    def test_abandon_preserves_files_and_prevents_ordinary_edit(self):
        self.model.update(revision=0, part_file=None, part_sha256=None)
        self.save_model()
        created, _ = self.prepare("abandon_new")
        self.execute(created)
        self.assertEqual(general.model_info(self.mid)["status"], "abandoned")
        self.assertTrue(self.part.is_file())
        with self.assertRaisesRegex(ValueError, "not ready"):
            general.submit([], model_id=self.mid, expected_revision=0)

    def test_candidate_is_bound_to_job_and_template_copy_is_not_a_candidate(self):
        checkpoint = bridge.job_path(self.original) / "native_checkpoint.json"
        bridge.write_json(checkpoint, {"part_file": str(self.part), "success": True})
        self.assertIsNone(rec.inspect(self.mid)["candidate"])
        candidate = self.part.with_name("owned_part.prt.3")
        candidate.write_bytes(b"saved but not delivered")
        bridge.write_json(
            checkpoint,
            {
                "part_file": str(candidate),
                "success": True,
                "saved_file_reloaded_and_verified": True,
                "inspection": self.state,
                "aliases": {},
            },
        )
        self.assertTrue(rec.inspect(self.mid)["actions"]["accept_saved"]["available"])
        created, _ = self.prepare("accept_saved")
        self.part = candidate
        self.assertEqual(self.execute(created)["revision"], 2)

    def test_unreadable_candidate_reference_is_dropped_not_published(self):
        checkpoint = bridge.job_path(self.original) / "native_checkpoint.json"
        candidate = self.part.with_name("owned_part.prt.3")
        candidate.write_bytes(b"saved but not delivered")
        ref = inspection_refs.make_ref(self.state, bridge.job_path(self.original), "verified")
        Path(ref["file"]).unlink()
        bridge.write_json(
            checkpoint,
            {
                "part_file": str(candidate),
                "success": True,
                "saved_file_reloaded_and_verified": True,
                "inspection_ref": ref,
                "aliases": {},
            },
        )
        # A removed sidecar must not break the recovery tool or be republished
        # as readable; the candidate identity and a bounded diagnostic remain.
        state = rec.inspect(self.mid)
        published = state["candidate"]
        self.assertEqual(published["identity"]["path"], str(candidate.resolve()))
        self.assertTrue(published["inspection_warnings"][0]["stage"] == "verified")
        self.assertEqual(
            published["inspection_warnings"][0]["reason_code"], "inspection_ref_invalid"
        )
        self.assertEqual(published["inspection_warnings"][0]["fallback_status"], "not_attempted")
        self.assertNotIn("inspection_ref", published)
        self.assertTrue(state["actions"]["accept_saved"]["available"])

    def test_external_file_and_changed_baseline_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            rec.owned_file(self.model, str(self.root / "foreign.prt.1"))
        self.part.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "identity"):
            rec.validate_baseline(self.model)

    def test_stream_hash_exceeds_old_diagnostic_limit(self):
        file = self.root / "larger-than-diagnostic.bin"
        data = b"x" * (17 * 1024 * 1024)
        file.write_bytes(data)
        self.assertEqual(rec.identity(file)["sha256"], hashlib.sha256(data).hexdigest())
        with patch.object(rec, "MAX_FILE_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "budget"):
                rec.identity(file)

    def test_token_expires_and_duplicate_key_cannot_change_action(self):
        evidence = rec.inspect(self.mid)
        jobs_before = set(bridge.JOBS.iterdir())
        with patch.object(rec.time, "time", return_value=10**12):
            with self.assertRaisesRegex(ValueError, "expired"):
                rec.apply(
                    self.mid,
                    "restore_baseline",
                    1,
                    self.original,
                    evidence["evidence_token"],
                    "expired_key",
                )
        self.assertEqual(rec.TOKEN_SECONDS, 600)
        self.assertEqual(set(bridge.JOBS.iterdir()), jobs_before)
        self.assertIsNone(general.model_info(self.mid).get("recovery_pending"))
        created, args = self.prepare()
        altered = list(args)
        altered[1] = "accept_saved"
        with self.assertRaisesRegex(ValueError, "another recovery"):
            rec.apply(*altered)
        self.assertEqual(general.model_info(self.mid)["recovery_pending"], created["job_id"])

    def test_actual_competing_admissions_only_one_succeeds(self):
        evidence = rec.inspect(self.mid)
        barrier = threading.Barrier(2)

        def contender(index):
            barrier.wait()
            try:
                return rec.apply(
                    self.mid,
                    "restore_baseline",
                    1,
                    self.original,
                    evidence["evidence_token"],
                    f"competing_{index}",
                )
            except (ValueError, bridge.ToolkitBusy) as error:
                return {"rejected": str(error)}

        with (
            patch.object(bridge.subprocess, "Popen"),
            concurrent.futures.ThreadPoolExecutor(2) as pool,
        ):
            results = list(pool.map(contender, (1, 2)))
        self.assertEqual(sum("job_id" in result for result in results), 1, results)

    def test_ordinary_checkpointless_even_ready_refuses_implicit_adoption(self):
        self.model.update(status="ready", pending_job=None, revision=0, part_file=None)
        self.save_model()
        with self.assertRaisesRegex(ValueError, "no verified saved baseline"):
            general.submit([], model_id=self.mid, expected_revision=0)

    def test_assembly_recovery_rejected_without_touching_components(self):
        self.model["model_type"] = "assembly"
        self.save_model()
        result = rec.inspect(self.mid)
        self.assertFalse(any(action["available"] for action in result["actions"].values()))


if __name__ == "__main__":
    unittest.main()
