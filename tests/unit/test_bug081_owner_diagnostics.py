"""BUG-081: migration owner refusals carry bounded diagnostics; stop semantics unchanged."""

import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import registry_ops
from tests.unit.test_model_registry import RegistryBase, _model


def boot(delta=3600):
    # Synthetic boot later than fixture creation; no actual restart or native work.
    stamp = time.time() + delta
    return {
        "started_at": datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
        "time_ns": int(stamp * 1e9),
        "source": "isolated cross-checked boot fixture",
    }


class OwnerDiagnostics(RegistryBase):
    def install(self, model_id="1" * 32, job_id="a" * 32, *, job=None, **model_extra):
        self.legacy_entry(model_id, last_job=job_id, **model_extra)
        directory = bridge.job_path(job_id)
        directory.mkdir(parents=True, exist_ok=True)
        bridge.write_json(
            directory / "job.json",
            {
                "job_id": job_id,
                "model_id": model_id,
                "created_at": "2026-10-01T00:00:00+00:00",
                **(job or {}),
            },
        )
        bridge.write_json(directory / "request.json", {"model": _model(model_id)})
        return directory

    def apply(self, model_id="1" * 32, key="bug081-apply-01"):
        return registry_ops.migrate("apply", [model_id], key)

    def inspect(self, model_id="1" * 32):
        return registry_ops.migrate("inspect", [model_id])

    def test_process_not_found_error_87_unblocks_migration(self):
        self.install(job={"status": "succeeded", "runner_identity": {"pid": 4242, "created": 99}})
        observed = {"pid": 4242, "alive": False, "windows_error": 87}
        with patch("creo_mechdog.reconciliation.process_identity", return_value=observed):
            report = self.inspect()
            self.assertEqual(report["blocked_entries"], 0)
            self.assertNotIn("owner_block", report["entries"][0])
            result = self.apply()
        self.assertEqual(result["migrated"], 1)

    def test_same_live_process_blocks_with_recorded_and_observed_evidence(self):
        directory = self.install(
            job={"status": "succeeded", "runner_identity": {"pid": 7, "created": 50}}
        )
        bridge.write_json(directory / "native_owner.json", {"pid": 8, "created": 60})
        seen = lambda pid: {"pid": pid, "alive": True, "created": 50 if pid == 7 else 60}
        with patch("creo_mechdog.reconciliation.process_identity", side_effect=seen):
            report = self.inspect()
            self.assertEqual(report["blocked_entries"], 1)
            block = report["entries"][0]["owner_block"]
            result_error = None
            try:
                self.apply()
            except bridge.ToolkitBusy as error:
                result_error = error
        self.assertIsNotNone(result_error)
        payload = result_error.payload
        self.assertEqual(payload["blocking_job_id"], "a" * 32)
        self.assertEqual(payload["blocking_operation"], "registry_owner")
        self.assertEqual(payload["owner_block"], block)
        self.assertEqual(block["reason_code"], "runner_unproven")
        self.assertEqual(block["job_status"], "succeeded")
        self.assertEqual(block["runner"]["recorded"], {"pid": 7, "created": 50})
        self.assertEqual(block["runner"]["observed"]["alive"], True)
        self.assertEqual(block["runner"]["observed"]["created"], 50)
        self.assertFalse(block["runner"]["stopped"])
        self.assertIn(block["reason_code"], registry_ops.OWNER_BLOCK_REASONS)
        self.assertLessEqual(len(block["next_steps"]), 600)
        self.assertNotIn("pre-split-bak", [p.name for p in general.model_path("1" * 32).iterdir()])

    def test_live_worker_with_stopped_runner_blocks_as_worker_unproven(self):
        directory = self.install(
            job={"status": "succeeded", "runner_identity": {"pid": 7, "created": 50}}
        )
        bridge.write_json(directory / "native_owner.json", {"pid": 8, "created": 60})

        def seen(pid):
            return {"pid": pid, "alive": pid == 8, "created": 60}

        with patch("creo_mechdog.reconciliation.process_identity", side_effect=seen):
            with self.assertRaises(bridge.ToolkitBusy) as caught:
                self.apply()
        block = caught.exception.payload["owner_block"]
        self.assertEqual(block["reason_code"], "worker_unproven")
        self.assertTrue(block["runner"]["stopped"])
        self.assertEqual(block["worker"]["recorded"], {"pid": 8, "created": 60})

    def test_confirmed_pid_reuse_with_complete_identity_unblocks(self):
        self.install(job={"status": "succeeded", "runner_identity": {"pid": 7, "created": 50}})
        # The PID now belongs to a different process: verifiable creation identity.
        seen = lambda pid: {"pid": pid, "alive": True, "created": 999}
        with patch("creo_mechdog.reconciliation.process_identity", side_effect=seen):
            result = self.apply()
        self.assertEqual(result["migrated"], 1)

    def test_pid_reuse_with_incomplete_identity_stays_refused_and_never_time_released(self):
        self.install(job={"status": "succeeded", "runner_identity": {"pid": 7}})
        seen = lambda pid: {"pid": pid, "alive": True, "created": 999}
        with (
            patch("creo_mechdog.reconciliation.process_identity", side_effect=seen),
            patch("creo_mechdog.reconciliation.boot_info") as query,
        ):
            with self.assertRaises(bridge.ToolkitBusy) as caught:
                self.apply()
            query.assert_not_called()
        block = caught.exception.payload["owner_block"]
        self.assertEqual(block["reason_code"], "runner_unproven")
        self.assertEqual(block["runner"]["recorded"], {"pid": 7})
        self.assertEqual(block["runner"]["observed"]["created"], 999)
        self.assertFalse(block["runner"]["stopped"])

    def test_access_denied_error_5_blocks_with_windows_error(self):
        # A complete identity from long before any boot is still never released
        # by time; an old created timestamp is not stop evidence.
        self.install(job={"status": "succeeded", "runner_identity": {"pid": 7, "created": 1}})
        observed = {"pid": 7, "alive": None, "windows_error": 5}
        with (
            patch("creo_mechdog.reconciliation.process_identity", return_value=observed),
            patch("creo_mechdog.reconciliation.boot_info") as query,
        ):
            report = self.inspect()
            with self.assertRaises(bridge.ToolkitBusy) as caught:
                self.apply()
            query.assert_not_called()
        block = caught.exception.payload["owner_block"]
        self.assertEqual(report["entries"][0]["owner_block"], block)
        self.assertEqual(block["reason_code"], "runner_unproven")
        self.assertEqual(
            block["runner"]["observed"],
            {"pid": 7, "alive": None, "created": None, "windows_error": 5},
        )
        self.assertIn("unproven", block["next_steps"])

    def test_get_process_times_query_failure_blocks_with_reason(self):
        self.install(job={"status": "succeeded", "runner_identity": {"pid": 7, "created": 50}})
        observed = {"pid": 7, "alive": None, "windows_error": 998}
        with patch("creo_mechdog.reconciliation.process_identity", return_value=observed):
            with self.assertRaises(bridge.ToolkitBusy) as caught:
                self.apply()
        block = caught.exception.payload["owner_block"]
        self.assertEqual(block["runner"]["observed"]["windows_error"], 998)
        self.assertFalse(block["runner"]["stopped"])
        self.assertIn("fresh idempotency_key", block["next_steps"])

    def test_missing_identity_without_reservation_still_migrates(self):
        # No recorded identity at all, terminal job, not reserved: the guard
        # never blocked this shape before BUG-081 and still must not.
        self.install(job={"status": "succeeded"})
        result = self.apply()
        self.assertEqual(result["migrated"], 1)

    def test_malformed_identities_block_without_crash_or_release(self):
        directory = self.install(job={"status": "succeeded"})
        job = bridge.read_json(directory / "job.json")
        expected_views = {
            "invalid": None,
            str({"pid": True}): None,
            str({"pid": -3}): None,
            str({"pid": 12, "created": "12"}): {"pid": 12},
        }
        for recorded in ("invalid", {"pid": True}, {"pid": -3}, {"pid": 12, "created": "12"}):
            with (
                self.subTest(recorded=recorded),
                patch(
                    "creo_mechdog.reconciliation.process_identity",
                    return_value={"pid": 12, "alive": True, "created": 12},
                ),
                patch("creo_mechdog.reconciliation.boot_info") as query,
            ):
                job["runner_identity"] = recorded
                bridge.write_json(directory / "job.json", job)
                with self.assertRaises(bridge.ToolkitBusy) as caught:
                    self.apply(key=f"bug081-malformed-{len(str(recorded))}")
                query.assert_not_called()
            block = caught.exception.payload["owner_block"]
            self.assertEqual(block["reason_code"], "runner_unproven")
            self.assertEqual(block["runner"]["recorded"], expected_views[str(recorded)])

    def test_previous_boot_evidence_applies_only_to_incomplete_protected_identities(self):
        directory = self.install(
            job={"status": "unknown_outcome", "finished_at": "2026-10-01T01:00:00+00:00"},
            pending_job="a" * 32,
        )
        bridge.write_json(directory / "native_checkpoint.json", {"native_pid": 5555})
        seen = lambda pid: {"pid": pid, "alive": True, "created": 12}
        with (
            patch("creo_mechdog.reconciliation.process_identity", side_effect=seen),
            patch("creo_mechdog.reconciliation.boot_info", return_value=boot()),
        ):
            result = self.apply(key="bug081-boot-allowed")
        self.assertEqual(result["migrated"], 1)

    def test_complete_identity_is_never_released_by_previous_boot(self):
        self.install(
            job={"status": "unknown_outcome", "runner_identity": {"pid": 7, "created": 5}},
            pending_job="a" * 32,
        )
        seen = lambda pid: {"pid": pid, "alive": True, "created": 5}
        with (
            patch("creo_mechdog.reconciliation.process_identity", side_effect=seen),
            patch("creo_mechdog.reconciliation.boot_info") as query,
        ):
            with self.assertRaises(bridge.ToolkitBusy) as caught:
                self.apply(key="bug081-boot-refused")
            query.assert_not_called()
        self.assertEqual(caught.exception.payload["owner_block"]["reason_code"], "runner_unproven")

    def test_protected_owner_without_any_identity_requires_boot_proof(self):
        self.install(
            job={"status": "unknown_outcome", "finished_at": "2026-10-01T01:00:00+00:00"},
            pending_job="a" * 32,
        )
        with patch("creo_mechdog.reconciliation.boot_info", return_value=None):
            with self.assertRaises(bridge.ToolkitBusy) as caught:
                self.apply(key="bug081-protected-01")
        payload = caught.exception.payload
        self.assertEqual(payload["owner_block"]["reason_code"], "protected_owner_unproven")
        self.assertIn("protected owners stopped", payload["message"])

    def test_inspect_pass_does_not_authorize_apply_after_state_change(self):
        self.install(job={"status": "succeeded", "runner_identity": {"pid": 7, "created": 50}})
        dead = {"pid": 7, "alive": False, "windows_error": 87}
        with patch("creo_mechdog.reconciliation.process_identity", return_value=dead):
            report = self.inspect()
        self.assertEqual(report["blocked_entries"], 0)
        # Between inspect and apply the same PID comes alive again: apply must
        # re-verify under the channel lock and refuse.
        alive = {"pid": 7, "alive": True, "created": 50}
        with patch("creo_mechdog.reconciliation.process_identity", return_value=alive):
            with self.assertRaises(bridge.ToolkitBusy) as caught:
                self.apply(key="bug081-stale-inspect")
        self.assertEqual(caught.exception.payload["owner_block"]["reason_code"], "runner_unproven")
        directory = general.model_path("1" * 32)
        self.assertFalse((directory / registry_ops.MODEL_BACKUP).exists())

    def test_idempotent_replay_returns_recorded_result_without_rerunning_guard(self):
        self.install(job={"status": "succeeded", "runner_identity": {"pid": 7, "created": 50}})
        dead = {"pid": 7, "alive": False, "windows_error": 87}
        with patch("creo_mechdog.reconciliation.process_identity", return_value=dead):
            first = self.apply(key="bug081-replay-01")
        self.assertEqual(first["migrated"], 1)
        # Owners turn unprovable after the fact; a same-key replay is a
        # duplicate query and must return the recorded result, not re-audit.
        alive = {"pid": 7, "alive": True, "created": 50}
        with patch("creo_mechdog.reconciliation.process_identity", return_value=alive):
            replay = self.apply(key="bug081-replay-01")
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["migrated"], 1)

    def test_pending_and_recovery_reservations_and_active_status_still_block(self):
        directory = self.install(
            job={"status": "succeeded", "runner_identity": {"pid": 7, "created": 50}},
            recovery_pending="a" * 32,
        )
        bridge.write_json(directory / "native_owner.json", {"pid": 8, "created": 60})

        def seen(pid):
            return {"pid": pid, "alive": pid == 8, "created": 60}

        with patch("creo_mechdog.reconciliation.process_identity", side_effect=seen):
            with self.assertRaises(bridge.ToolkitBusy) as caught:
                self.apply(key="bug081-recovery-block")
        self.assertEqual(caught.exception.payload["owner_block"]["reason_code"], "worker_unproven")
        # Even fully stopped owners cannot migrate an active job.
        job = bridge.read_json(directory / "job.json")
        job["status"] = "running"
        bridge.write_json(directory / "job.json", job)
        seen = lambda pid: {"pid": pid, "alive": False, "windows_error": 87}
        with patch("creo_mechdog.reconciliation.process_identity", side_effect=seen):
            with self.assertRaises(bridge.ToolkitBusy) as caught:
                self.apply(key="bug081-active-block")
        block = caught.exception.payload["owner_block"]
        self.assertEqual(block["reason_code"], "active_job")
        self.assertTrue(block["runner"]["stopped"])
        self.assertEqual(block["job_status"], "running")


if __name__ == "__main__":
    unittest.main()
