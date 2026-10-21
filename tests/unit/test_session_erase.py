"""FEAT-046: explicit session-model erasure contract.

The native boundary is substituted; every check here covers the Python
contract: manifest validation, evidence-token discipline (missing, expired,
mismatched key), idempotent replay and refusal without execution.
"""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge as general
from creo_mechdog import session_erase


def _write(file: Path, value: dict) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(value), encoding="utf-8")


def _native_summary(available: bool = True) -> dict:
    summary = {
        "action": "inspect",
        "targets": [
            {
                "name": "ASSY",
                "model_type": "assembly",
                "origin": "C:\\parts\\assy.asm.4",
                "modified": False,
                "is_current": False,
            },
            {
                "name": "COMP",
                "model_type": "part",
                "origin": "C:\\parts\\comp.prt.2",
                "modified": False,
                "is_current": False,
            },
        ],
        "erase_order": [
            {
                "name": "ASSY",
                "model_type": "assembly",
                "origin": "C:\\parts\\assy.asm.4",
                "modified": False,
            },
            {
                "name": "COMP",
                "model_type": "part",
                "origin": "C:\\parts\\comp.prt.2",
                "modified": False,
            },
        ],
        "remaining_after": [],
        "available": available,
        "reason_code": None if available else "blocked_targets",
        "message": "fixture summary",
    }
    if not available:
        summary["targets"][1]["blocked"] = {"reason": "modified", "message": "fixture blocked"}
    return summary


class SessionEraseContract(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="feat046_erase_")
        self.root = Path(self.temporary.name)
        (self.root / "jobs").mkdir()
        (self.root / "models").mkdir()
        _write(
            self.root / "config.json",
            {
                "creo_root": "C:\\feat046-fixture-creo",
                "vcvars64": "C:\\feat046-vcvars64.bat",
                "native_timeout_seconds": 115,
            },
        )
        for patcher in (
            patch.object(bridge, "ROOT", self.root),
            patch.object(bridge, "JOBS", self.root / "jobs"),
            patch.object(general, "MODELS", self.root / "models"),
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe"),
            # Apply submissions spawn a detached runner; keep it inside this
            # process's test boundary.
            patch.object(session_erase.subprocess, "Popen"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.temporary.cleanup()

    def _probe_result(self, summary: dict) -> dict:
        result = {
            "connected": True,
            "delivery_complete": True,
            "disconnect_code": 0,
            "success": summary.get("available", True) is True or "erased" in summary,
            "session_erase": summary,
            "message": "fixture probe",
        }
        return result

    def test_inspect_publishes_token_only_for_available_manifest(self):
        for available, tokens in ((True, 1), (False, 0)):
            with self.subTest(available=available):
                probe = lambda directory, manifest: self._probe_result(_native_summary(available))
                with patch.object(session_erase, "_probe", side_effect=probe):
                    response = session_erase.erase_session_models(
                        "inspect",
                        [
                            {"name": "ASSY", "model_type": "assembly"},
                            {"name": "COMP", "model_type": "part"},
                        ],
                    )
                self.assertIs(response["session_erase"]["available"], available)
                self.assertEqual(response["evidence_token"] is not None, available)
                self.assertEqual(bool(response["expires_in_seconds"]), available)

    def test_invalid_targets_refused_before_any_job(self):
        for targets in (
            [],
            [{"name": "A", "model_type": "drawing"}],
            [{"name": "A"}],
            [{"name": "A", "model_type": "part"}, {"name": "a", "model_type": "sheetmetal"}],
            "not-a-list",
        ):
            with self.subTest(targets=targets):
                with patch.object(session_erase, "_probe") as probe:
                    with self.assertRaises(ValueError):
                        session_erase.erase_session_models("inspect", targets)
                    probe.assert_not_called()

    def test_apply_rejects_missing_expired_and_mismatched_tokens(self):
        probe = lambda directory, manifest: self._probe_result(_native_summary(True))
        with patch.object(session_erase, "_probe", side_effect=probe):
            response = session_erase.erase_session_models(
                "inspect",
                [
                    {"name": "ASSY", "model_type": "assembly"},
                    {"name": "COMP", "model_type": "part"},
                ],
            )
            token = response["evidence_token"]
        with patch.object(session_erase, "_probe") as apply_probe:
            with self.assertRaises(ValueError):
                session_erase.erase_session_models(
                    "apply", evidence_token="0" * 32, idempotency_key="missing_token_1"
                )
            record_file = self.root / "session_erase" / f"evidence-{token}.json"
            record = bridge.read_json(record_file)
            record["created"] = time.time() - session_erase.TOKEN_SECONDS - 1
            _write(record_file, record)
            with self.assertRaises(ValueError):
                session_erase.erase_session_models(
                    "apply", evidence_token=token, idempotency_key="expired_token_1"
                )
            apply_probe.assert_not_called()

    def test_apply_replay_returns_same_job_and_cross_key_rejects(self):
        probe = lambda directory, manifest: self._probe_result(_native_summary(True))
        with patch.object(session_erase, "_probe", side_effect=probe):
            token = session_erase.erase_session_models(
                "inspect",
                [
                    {"name": "ASSY", "model_type": "assembly"},
                    {"name": "COMP", "model_type": "part"},
                ],
            )["evidence_token"]
        submitted = session_erase.erase_session_models(
            "apply", evidence_token=token, idempotency_key="replay_key_001"
        )
        replay = session_erase.erase_session_models(
            "apply", evidence_token=token, idempotency_key="replay_key_001"
        )
        self.assertEqual(replay["job_id"], submitted["job_id"])
        with self.assertRaises(ValueError):
            session_erase.erase_session_models(
                "apply", evidence_token="f" * 32, idempotency_key="replay_key_001"
            )

    def test_apply_records_session_change_on_success(self):
        manifest = {
            "job_id": "1" * 32,
            "kind": "session_erase",
            "session_erase_action": "apply",
            "model_id": None,
            "status": "queued",
            "created_at": bridge.now(),
        }
        directory = bridge.job_path(manifest["job_id"])
        (directory / "output").mkdir(parents=True)
        apply_summary = {
            "action": "apply",
            "erased": [
                {"name": "ASSY", "model_type": "assembly"},
                {"name": "COMP", "model_type": "part"},
            ],
            "unconfirmed": None,
            "remaining_after": [],
            "stopped_early": False,
            "message": "fixture apply",
        }
        apply_probe = lambda d, m: self._probe_result(apply_summary)
        with patch.object(session_erase, "_probe", side_effect=apply_probe):
            session_erase.run(manifest["job_id"], manifest)
        final = bridge.read_json(directory / "job.json")
        self.assertEqual(final["status"], "succeeded")
        self.assertEqual(len(final["result"]["session_erase"]["erased"]), 2)
        activity = bridge.read_json(self.root / "session_activity.json")
        self.assertTrue(
            any(entry.get("tool") == "creo_erase_session_models" for entry in activity["entries"])
        )


if __name__ == "__main__":
    unittest.main()
