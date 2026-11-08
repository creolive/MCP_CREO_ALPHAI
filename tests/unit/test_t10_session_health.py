"""T10 / BUG-078: session health evidence rules; no Toolkit, Creo or live session."""

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import bridge
import creo_startup
from creo_mechdog import session_health

NOW = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)


class HealthFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="t10_session_health_")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "jobs").mkdir()
        (self.root / "build").mkdir()

    def at(self, seconds_ago: int) -> str:
        return (NOW - timedelta(seconds=seconds_ago)).isoformat()

    def write_job(self, job_id: str, manifest: dict) -> Path:
        directory = self.root / "jobs" / job_id
        directory.mkdir(parents=True, exist_ok=True)
        value = {"job_id": job_id, "created_at": self.at(120), **manifest}
        path = directory / "job.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def save_job(self, job_id: str, session: str | None, seconds_ago: int, **fields) -> Path:
        result = {
            "success": True,
            "connected": True,
            "saved_file_reloaded_and_verified": True,
            "part_file": f"output/{job_id}.prt",
        }
        if session is not None:
            result["session_fingerprint"] = session
        result.update(fields.pop("result", {}))
        manifest = {
            "kind": "generic",
            "status": "succeeded",
            "readonly": False,
            "model_id": f"model_{job_id}",
            "finished_at": self.at(seconds_ago),
            "result": result,
        }
        manifest.update(fields)
        return self.write_job(job_id, manifest)

    def failed_save_job(self, job_id: str, session: str, seconds_ago: int) -> Path:
        return self.write_job(
            job_id,
            {
                "kind": "generic",
                "status": "failed",
                "readonly": False,
                "model_id": "model_damaged",
                "finished_at": self.at(seconds_ago),
                "result": {
                    "success": False,
                    "connected": True,
                    "session_fingerprint": session,
                    "toolkit_code": -1,
                    "failed_stage": "save_and_reload",
                    "failed_toolkit_call": "ProMdlnameBackup",
                    "message": "Toolkit call ProMdlnameBackup failed with code -1",
                },
            },
        )

    def readonly_job(self, job_id: str, session: str, seconds_ago: int) -> Path:
        return self.write_job(
            job_id,
            {
                "kind": "generic",
                "status": "succeeded",
                "readonly": True,
                "model_id": "model_query",
                "finished_at": self.at(seconds_ago),
                "result": {
                    "success": True,
                    "connected": True,
                    "session_fingerprint": session,
                    "part_file": "output/query.prt",
                    "inspection": {"inspection_available": True},
                },
            },
        )

    def snapshot(self) -> dict:
        return session_health.snapshot(self.root, now=NOW, refresh=True)


class HealthStatusRules(HealthFixture):
    def test_no_evidence_is_unknown(self):
        value = self.snapshot()
        self.assertEqual((value["status"], value["reason"]), ("unknown", "no_evidence"))
        self.assertIsNone(value["observed_at"])
        self.assertIsNone(value["evidence_age_seconds"])
        self.assertIsNone(value["facts"]["last_save"])
        self.assertIsNone(value["facts"]["last_connection"])
        self.assertFalse(value["session"]["changed"])
        self.assertEqual(value["damage_signals"], [])
        self.assertTrue(value["next_steps"])
        self.assertEqual(value["evidence"]["jobs_scanned"], 0)

    def test_recent_verified_save_is_no_failure_observed(self):
        self.save_job("a" * 32, "session-a", 30)
        value = self.snapshot()
        self.assertEqual(
            (value["status"], value["reason"]), ("no_failure_observed", "recent_verified_save")
        )
        self.assertEqual(value["observed_at"], self.at(30))
        self.assertEqual(value["evidence_age_seconds"], 30)
        self.assertEqual(value["session"]["identity"], "session-a")
        self.assertEqual(value["session"]["identity_source"], "recorded")
        self.assertEqual(value["facts"]["last_save"]["outcome"], "succeeded")
        self.assertTrue(value["facts"]["last_save"]["saved_file_reloaded_and_verified"])
        self.assertEqual(value["facts"]["recent_saves"]["succeeded"], 1)
        self.assertEqual(value["facts"]["last_connection"]["outcome"], "connected")
        self.assertEqual(value["damage_signals"], [])
        steps = [step["step"] for step in value["next_steps"]]
        self.assertEqual(steps[0], "keep-evidence")
        self.assertIn("verify-next-save", steps)

    def test_recent_save_failure_is_suspected_damage(self):
        self.failed_save_job("b" * 32, "session-a", 40)
        value = self.snapshot()
        self.assertEqual((value["status"], value["reason"]), ("suspected_damage", "save_failure"))
        signal = value["damage_signals"][0]
        self.assertEqual(signal["kind"], "save_failure")
        self.assertEqual(signal["failed_stage"], "save_and_reload")
        self.assertEqual(signal["failed_toolkit_call"], "ProMdlnameBackup")
        self.assertTrue(signal["current_session"])
        steps = [step["step"] for step in value["next_steps"]]
        self.assertEqual(steps[0], "preserve")
        self.assertIn("inspect", steps)
        self.assertIn("choose", steps)
        self.assertIn("operator", steps)
        self.assertIn("reobserve", steps)

    def test_unknown_outcome_protection_is_suspected_damage(self):
        self.write_job(
            "c" * 32,
            {
                "kind": "generic",
                "status": "unknown_outcome",
                "readonly": False,
                "model_id": "model_suspended",
                "finished_at": self.at(50),
                "result": {"connected": True, "session_fingerprint": "session-a"},
            },
        )
        value = self.snapshot()
        self.assertEqual(value["status"], "suspected_damage")
        self.assertEqual(value["reason"], "unknown_outcome_protection")
        self.assertEqual(value["damage_signals"][0]["kind"], "unknown_outcome_protection")

    def test_new_session_identity_is_unknown(self):
        self.save_job("d" * 32, "session-a", 300)
        self.readonly_job("e" * 32, "session-b", 20)
        value = self.snapshot()
        self.assertEqual((value["status"], value["reason"]), ("unknown", "no_recent_verified_save"))
        self.assertEqual(value["session"]["identity"], "session-b")
        self.assertTrue(value["session"]["changed"])
        self.assertEqual(value["session"]["sessions_observed"], 2)
        self.assertEqual(value["facts"]["recent_saves"]["succeeded"], 0)
        self.assertEqual(value["facts"]["last_save"]["outcome"], "succeeded")
        self.assertEqual(value["damage_signals"], [])

    def test_expired_evidence_is_unknown(self):
        self.save_job("f" * 32, "session-a", 900)
        value = self.snapshot()
        self.assertEqual((value["status"], value["reason"]), ("unknown", "evidence_expired"))
        self.assertEqual(value["evidence_age_seconds"], 900)
        self.assertGreater(value["evidence_age_seconds"], value["freshness_window_seconds"])

    def test_stale_identity_with_fresh_connection_is_downgraded(self):
        self.save_job("0" * 32, "session-a", 30)
        (self.root / "build" / "toolkit_health.json").write_text(
            json.dumps({"connected": True, "checked_at": self.at(10)}), encoding="utf-8"
        )
        with patch.object(session_health, "FRESHNESS_SECONDS", 20):
            value = self.snapshot()
        # The identity is stale, but the fresh connected fact is real evidence:
        # the stale label becomes a warning instead of swallowing the verdict.
        self.assertEqual(value["status"], "unknown")
        self.assertEqual(value["reason"], "no_recent_verified_save")
        self.assertTrue(value["session"]["identity_stale"])
        self.assertTrue(value["session"]["identity_stale_downgraded"])
        self.assertEqual(len(value["warnings"]), 1)
        self.assertIn("no unknown protection is cleared", value["warnings"][0])
        self.assertIn(value["warnings"][0], value["caveats"])

    def test_stale_identity_without_fresh_connection_stays_stale(self):
        self.save_job("0" * 31 + "a", "session-a", 30)
        (self.root / "build" / "toolkit_health.json").write_text(
            json.dumps({"connected": False, "checked_at": self.at(10)}), encoding="utf-8"
        )
        with patch.object(session_health, "FRESHNESS_SECONDS", 20):
            value = self.snapshot()
        self.assertEqual((value["status"], value["reason"]), ("unknown", "session_identity_stale"))
        self.assertTrue(value["session"]["identity_stale"])
        self.assertFalse(value["session"]["identity_stale_downgraded"])
        self.assertEqual(value["warnings"], [])

    def test_downgrade_never_clears_an_unknown_protection(self):
        self.write_job(
            "0" * 31 + "b",
            {
                "kind": "generic",
                "status": "unknown_outcome",
                "readonly": False,
                "model_id": "model_suspended",
                "finished_at": self.at(30),
                "result": {"connected": True, "session_fingerprint": "session-a"},
            },
        )
        (self.root / "build" / "toolkit_health.json").write_text(
            json.dumps({"connected": True, "checked_at": self.at(5)}), encoding="utf-8"
        )
        with patch.object(session_health, "FRESHNESS_SECONDS", 20):
            value = self.snapshot()
        self.assertEqual(value["status"], "unknown")
        self.assertNotEqual(value["status"], "no_failure_observed")
        self.assertTrue(value["session"]["identity_stale_downgraded"])
        self.assertEqual(value["damage_signals"], [])
        protection = [
            signal
            for signal in value["historic_damage_signals"]
            if signal["kind"] == "unknown_outcome_protection"
        ]
        self.assertEqual(len(protection), 1)
        self.assertIn("Do not resubmit", " ".join(step["detail"] for step in value["next_steps"]))
        self.assertIn("never authorizes clearing", " ".join(value["caveats"]))

    def test_missing_session_identity_is_unknown(self):
        self.save_job("1" * 32, None, 30)
        value = self.snapshot()
        self.assertEqual(
            (value["status"], value["reason"]), ("unknown", "session_identity_unknown")
        )
        self.assertIsNone(value["session"]["identity"])
        self.assertIsNone(value["session"]["identity_source"])
        self.assertEqual(value["facts"]["last_save"]["outcome"], "succeeded")

    def test_readonly_connection_is_not_a_save(self):
        self.readonly_job("2" * 32, "session-a", 20)
        value = self.snapshot()
        self.assertEqual((value["status"], value["reason"]), ("unknown", "no_recent_verified_save"))
        self.assertEqual(value["facts"]["last_connection"]["outcome"], "connected")
        self.assertIsNone(value["facts"]["last_save"])
        self.assertEqual(value["facts"]["recent_saves"]["succeeded"], 0)

    def test_attributed_fact_uses_observed_session(self):
        self.readonly_job("3" * 32, "session-a", 90)
        self.write_job(
            "4" * 32,
            {
                "status": "succeeded",
                "model_id": "model_plate",
                "finished_at": self.at(60),
                "result": {
                    "success": True,
                    "connected": True,
                    "saved_file_reloaded_and_verified": True,
                    "part_file": "output/plate.prt",
                },
            },
        )
        value = self.snapshot()
        self.assertEqual(value["status"], "no_failure_observed")
        self.assertEqual(value["facts"]["last_save"]["session_source"], "attributed")
        self.assertTrue(value["facts"]["last_save"]["job_id"].startswith("4"))

    def test_damage_from_previous_session_is_not_current(self):
        self.failed_save_job("5" * 32, "session-a", 300)
        self.save_job("6" * 32, "session-b", 30)
        value = self.snapshot()
        self.assertEqual(value["status"], "no_failure_observed")
        self.assertEqual(value["damage_signals"], [])
        self.assertEqual(len(value["historic_damage_signals"]), 1)
        self.assertFalse(value["historic_damage_signals"][0]["current_session"])


class HealthFactProvenance(HealthFixture):
    def test_facts_carry_source_time_and_staleness(self):
        self.save_job("c" * 31 + "a", "session-a", 30)
        value = self.snapshot()
        for fact in (value["facts"]["last_connection"], value["facts"]["last_save"]):
            self.assertEqual(fact["source"], "recorded_job")
            self.assertEqual(fact["at"], self.at(30))
            self.assertFalse(fact["stale"])
            self.assertGreaterEqual(fact["age_seconds"], 0)
        self.assertFalse(value["session"]["identity_stale"])
        self.assertEqual(value["session"]["identity_observed_at"], self.at(30))
        self.assertEqual(value["path"], "local_evidence")
        self.assertIn("no Toolkit connection", value["path_note"])
        self.assertEqual(value["toolkit_connections"], 0)

    def test_probe_attributed_and_recorded_sources_are_distinguishable(self):
        self.save_job("c" * 31 + "b", "session-a", 120)
        self.readonly_job("c" * 31 + "c", "session-a", 90)
        self.write_job(
            "c" * 31 + "d",
            {
                "status": "succeeded",
                "model_id": "model_plate",
                "finished_at": self.at(60),
                "result": {
                    "success": True,
                    "connected": True,
                    "saved_file_reloaded_and_verified": True,
                    "part_file": "output/plate.prt",
                },
            },
        )
        (self.root / "build" / "toolkit_health.json").write_text(
            json.dumps(
                {
                    "connected": True,
                    "connection_state": "connected",
                    "checked_at": self.at(10),
                }
            ),
            encoding="utf-8",
        )
        value = self.snapshot()
        self.assertEqual(value["facts"]["last_connection"]["source"], "toolkit_probe")
        self.assertEqual(value["facts"]["last_save"]["source"], "attributed")
        self.assertEqual(len(value["facts"]["historic_saves"]), 1)
        self.assertEqual(value["facts"]["historic_saves"][0]["source"], "recorded_job")
        self.assertFalse(value["facts"]["historic_saves"][0]["stale"])

    def test_historic_failure_does_not_erase_the_current_connected_fact(self):
        self.failed_save_job("c" * 31 + "e", "session-a", 900)
        self.readonly_job("c" * 31 + "f", "session-b", 20)
        value = self.snapshot()
        self.assertEqual(value["status"], "unknown")
        self.assertNotEqual(value["status"], "ok")
        connection = value["facts"]["last_connection"]
        self.assertEqual(connection["outcome"], "connected")
        self.assertEqual(connection["source"], "recorded_job")
        self.assertFalse(connection["stale"])
        self.assertEqual(len(value["historic_damage_signals"]), 1)
        historic = value["historic_damage_signals"][0]
        self.assertTrue(historic["stale"])
        self.assertEqual(historic["source"], "recorded_job")
        self.assertFalse(value["session"]["identity_stale"])

    def test_worker_file_time_is_listed_as_suspected_evidence_only(self):
        (self.root / "build" / "creo_worker.exe").write_bytes(b"fixture")
        self.save_job("c" * 31 + "g", "session-a", 30)
        value = self.snapshot()
        worker = value["facts"]["worker"]
        self.assertTrue(worker["available"])
        self.assertEqual(worker["causality"], "suspected_only")
        self.assertIn("only suspected", worker["note"])
        self.assertIn("suspected correlation", " ".join(value["caveats"]))

    def test_missing_worker_file_is_reported_without_a_probe(self):
        self.save_job("c" * 31 + "h", "session-a", 30)
        value = self.snapshot()
        self.assertFalse(value["facts"]["worker"]["available"])
        self.assertEqual(value["facts"]["worker"]["causality"], "unproven")


class HealthEvidenceBounds(HealthFixture):
    def test_unreadable_evidence_is_unknown(self):
        self.save_job("7" * 32, "session-a", 30)
        with patch.object(bridge, "read_json", side_effect=PermissionError("denied")):
            value = self.snapshot()
        self.assertEqual((value["status"], value["reason"]), ("unknown", "evidence_unreadable"))
        self.assertGreaterEqual(value["evidence"]["jobs_unreadable"], 1)
        self.assertTrue(any("unreadable" in item for item in value["evidence"]["problems"]))
        self.assertEqual([step["step"] for step in value["next_steps"]][0], "preserve")

    def test_partial_unreadable_evidence_is_reported(self):
        good = self.save_job("8" * 32, "session-a", 30)
        self.save_job("9" * 32, "session-a", 40)
        original = bridge.read_json

        def selective(path):
            if Path(path).parent.name != "8" * 32:
                raise PermissionError("denied")
            return original(path)

        with patch.object(bridge, "read_json", side_effect=selective):
            value = self.snapshot()
        self.assertTrue(good.is_file())
        self.assertEqual(value["status"], "no_failure_observed")
        self.assertEqual(value["evidence"]["jobs_unreadable"], 1)

    def test_oversized_manifest_is_skipped(self):
        self.save_job("a" * 31 + "b", "session-a", 30)
        with patch.object(session_health, "JOB_FILE_BYTES", 16):
            value = self.snapshot()
        self.assertEqual(value["status"], "unknown")
        self.assertEqual(value["evidence"]["jobs_skipped"], 1)
        self.assertEqual(value["evidence"]["jobs_scanned"], 0)

    def test_busy_channel_is_reported_without_rewriting_status(self):
        self.save_job("a" * 31 + "c", "session-a", 30)
        (self.root / "toolkit-owner.lock").write_text(
            json.dumps(
                {
                    "job_id": "owner" * 6,
                    "model_id": "model_x",
                    "operation": "execute_plan",
                    "since": self.at(2),
                }
            ),
            encoding="utf-8",
        )
        value = self.snapshot()
        self.assertTrue(value["facts"]["channel"]["busy"])
        self.assertEqual(value["facts"]["channel"]["owner"]["operation"], "execute_plan")
        self.assertEqual(value["next_steps"][0]["step"], "wait")
        self.assertEqual(value["status"], "no_failure_observed")
        self.assertIn("cannot be told apart", value["facts"]["channel"]["note"])

    def test_busy_channel_with_damage_keeps_damage_status(self):
        self.failed_save_job("a" * 31 + "d", "session-a", 40)
        (self.root / "toolkit-owner.lock").write_text(
            json.dumps({"job_id": "owner" * 6, "operation": "execute_plan"}), encoding="utf-8"
        )
        value = self.snapshot()
        self.assertEqual(value["status"], "suspected_damage")
        self.assertEqual(value["next_steps"][0]["step"], "wait")


class HealthIsReadOnly(HealthFixture):
    def tree(self) -> dict[str, str]:
        return {
            str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }

    def test_query_changes_no_file_and_never_locks_or_connects(self):
        self.save_job("b" * 31 + "a", "session-a", 30)
        (self.root / "models" / "model_1").mkdir(parents=True)
        model = self.root / "models" / "model_1" / "model.json"
        model.write_text(
            json.dumps({"model_id": "model_1", "status": "unknown_outcome"}), encoding="utf-8"
        )
        before = self.tree()
        with (
            patch.object(bridge, "toolkit_lock", side_effect=AssertionError("lock taken")),
            patch.object(bridge, "session_status", side_effect=AssertionError("probe made")),
            patch.object(bridge, "build_native", side_effect=AssertionError("worker built")),
            patch.object(bridge, "write_json", side_effect=AssertionError("file written")),
            patch.object(
                creo_startup, "launch_creo", side_effect=AssertionError("process started")
            ),
            patch.object(creo_startup, "inventory", side_effect=AssertionError("process scanned")),
        ):
            first = self.snapshot()
            second = self.snapshot()
        self.assertEqual(self.tree(), before)
        self.assertTrue(first["read_only"])
        self.assertEqual(first["toolkit_connections"], 0)
        self.assertEqual(second["toolkit_connections"], 0)
        self.assertEqual(first["path"], "local_evidence")
        self.assertIn("separate explicit creo_session_status", first["path_note"])

    def test_cached_evidence_still_reports_current_ages(self):
        self.save_job("b" * 31 + "b", "session-a", 30)
        fresh = session_health.snapshot(self.root, now=NOW)
        later = session_health.snapshot(self.root, now=NOW + timedelta(seconds=40))
        self.assertEqual(fresh["evidence_age_seconds"], 30)
        self.assertEqual(later["evidence_age_seconds"], 70)
        self.assertEqual(later["status"], "no_failure_observed")

    def test_status_vocabulary_and_wording(self):
        self.save_job("b" * 31 + "c", "session-a", 30)
        observed = self.snapshot()
        self.failed_save_job("b" * 31 + "d", "session-a", 10)
        damaged = self.snapshot()
        unknown = session_health.snapshot(self.root / "missing", now=NOW)
        for value in (observed, damaged, unknown):
            self.assertIn(value["status"], {"unknown", "suspected_damage", "no_failure_observed"})
            self.assertEqual(value["guarantee"], "evidence_only")
            self.assertTrue(value["caveats"])
            text = json.dumps([value["next_steps"], value["caveats"]]).lower()
            self.assertNotIn("automatically restart", text)
            self.assertNotIn("is healthy", text)
            for fragment in ("restart creo", "restart this service"):
                if fragment in text:
                    self.assertIn("never " + fragment, text)
        self.assertIn("health guarantee", " ".join(observed["caveats"]))


if __name__ == "__main__":
    unittest.main()
