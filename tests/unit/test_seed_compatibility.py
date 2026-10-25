"""FEAT-030: valid bytes and historical load evidence are distinct capabilities."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
from creo_mechdog import seed_compatibility as compatibility


class SeedCompatibility(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(bridge, "ROOT", self.root))
        self.seed = self.root / "seed.prt.1"
        self.seed.write_bytes(b"isolated test bytes, never loaded by Creo")
        self.digest = hashlib.sha256(self.seed.read_bytes()).hexdigest()
        self.entry = {"sha256": self.digest, "tested_creo": "10.0.0.0"}
        self.request = {
            "loft_seed": {"snapshot_sha256": self.digest},
            "template_file": str(self.seed),
        }
        self.result = {
            "seed_native_load": {"status": "loaded", "toolkit_code": 0},
            "creo_release_numeric": 44,
            "creo_release_query_code": 0,
            "session_fingerprint": "isolated-session",
            "success": True,
            "saved_file_reloaded_and_verified": True,
        }

    def test_tested_version_is_not_production_version_or_current_compatibility(self):
        value = compatibility.metadata(self.entry)
        self.assertIsNone(value["seed_build_version"])
        self.assertEqual(value["native_compatibility"]["observations"], [])
        self.assertEqual(
            value["native_compatibility"]["status"], "not_verified_for_current_session"
        )

    def test_success_record_is_bound_to_exact_bytes_runtime_and_job(self):
        value = compatibility.observe_load(self.request, self.result, "a" * 32)
        self.assertTrue(value["evidence_persisted"])
        row = compatibility.metadata(self.entry)["native_compatibility"]["observations"][0]
        self.assertEqual(row["seed_sha256"], self.digest)
        self.assertEqual(row["creo_release_numeric"], 44)
        self.assertEqual(row["job_id"], "a" * 32)
        self.assertEqual(
            compatibility.metadata({"sha256": "b" * 64})["native_compatibility"]["observations"], []
        )

    def test_load_failure_does_not_infer_unsupported_creo_version(self):
        self.result["seed_native_load"] = {"status": "load_failed", "toolkit_code": -16}
        self.result["saved_file_reloaded_and_verified"] = False
        value = compatibility.observe_load(self.request, self.result, "a" * 32)
        self.assertEqual(value["toolkit_code"], -16)
        self.assertEqual(value["status"], "load_failed")
        self.assertFalse(value["modeling_saved_reloaded_verified"])

    def test_incomplete_runtime_or_load_attempt_does_not_record_compatibility(self):
        for key, value in (
            ("creo_release_numeric", None),
            ("session_fingerprint", None),
            ("seed_native_load", {"status": "not_attempted"}),
        ):
            with self.subTest(key=key):
                result = {**self.result, key: value}
                observed = compatibility.observe_load(self.request, result, "a" * 32)
                self.assertFalse(observed["evidence_persisted"])
        self.assertFalse((self.root / "build").exists())

    def test_changed_snapshot_or_diagnostic_write_failure_does_not_change_model_success(self):
        self.seed.write_bytes(b"changed snapshot")
        observed = compatibility.observe_load(self.request, self.result, "a" * 32)
        self.assertFalse(observed["evidence_persisted"])
        self.assertIn("changed", observed["evidence_error"])
        self.seed.write_bytes(b"isolated test bytes, never loaded by Creo")
        with patch.object(
            bridge, "write_json", side_effect=OSError("diagnostic storage unavailable")
        ):
            observed = compatibility.observe_load(self.request, self.result, "a" * 32)
        self.assertFalse(observed["evidence_persisted"])
        self.assertTrue(self.result["success"])

    def test_query_drops_unbounded_diagnostic_content(self):
        import json

        folder = self.root / "build/seed_compatibility" / self.digest
        folder.mkdir(parents=True)
        (folder / "untrusted.json").write_text(
            json.dumps(
                {
                    "seed_sha256": self.digest,
                    "status": "loaded",
                    "session_fingerprint": "x" * 4000,
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            compatibility.metadata(self.entry)["native_compatibility"]["observations"], []
        )


class SeedProvenance(unittest.TestCase):
    """FEAT-030/BUG-034: the production version follows provable, hash-bound records."""

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(bridge, "ROOT", self.root))
        self.seed = self.root / "seed.prt.1"
        self.seed.write_bytes(b"isolated test bytes, never loaded by Creo")
        self.digest = hashlib.sha256(self.seed.read_bytes()).hexdigest()
        self.entry = {"sha256": self.digest, "tested_creo": "10.0.0.0"}

    def test_unknown_provenance_keeps_the_production_version_null(self):
        value = compatibility.metadata(self.entry, actual_sha256=self.digest)
        self.assertIsNone(value["seed_build_version"])
        self.assertEqual(value["seed_build_version_status"], "unknown")
        self.assertIsNone(value["seed_build_version_source"])
        self.assertIsNone(value["seed_build_version_evidence"])

    def test_ugc_header_token_stays_an_unverified_clue(self):
        self.seed.write_bytes(b"#UGC:2 PART 2128 1860 810 1 1 15 4100 2023073 00000285 \\\n#- VERS")
        digest = hashlib.sha256(self.seed.read_bytes()).hexdigest()
        entry = {**self.entry, "sha256": digest}
        value = compatibility.metadata(entry, actual_sha256=digest, seed_path=self.seed)
        clue = value["seed_file_diagnostic"]
        self.assertEqual(clue["ugc_part_version_token"], 2128)
        self.assertEqual(clue["ugc_interpretation"], "unverified_clue")
        # The token never becomes a product version.
        self.assertIsNone(value["seed_build_version"])
        self.assertNotIn("12.4", json.dumps(value))

    def test_generation_record_resolves_only_for_the_same_bytes(self):
        entry = {
            **self.entry,
            "seed_build_version": "10.0.0.0",
            "seed_build_version_source": "seed_manifest",
            "seed_build_version_evidence": "docs/SEED_LIBRARY.md",
            "seed_build_version_release_numeric": 42,
        }
        resolved = compatibility.metadata(entry, actual_sha256=self.digest)
        self.assertEqual(resolved["seed_build_version"], "10.0.0.0")
        self.assertEqual(resolved["seed_build_version_source"], "seed_manifest")
        self.assertEqual(resolved["seed_build_version_status"], "resolved")
        changed = compatibility.metadata(entry, actual_sha256="c" * 64)
        self.assertIsNone(changed["seed_build_version"])
        self.assertEqual(changed["seed_build_version_status"], "unknown")

    def test_native_evidence_resolves_and_stays_bound_to_the_seed_bytes(self):
        compatibility.record_native_build_evidence(
            self.digest, 42, seed_build_version="10.0.0.0", job_id="c" * 32
        )
        resolved = compatibility.metadata(self.entry, actual_sha256=self.digest)
        self.assertEqual(resolved["seed_build_version"], "10.0.0.0")
        self.assertEqual(resolved["seed_build_version_source"], "native_evidence")
        self.assertEqual(resolved["seed_build_version_release_numeric"], 42)
        other = compatibility.metadata(self.entry, actual_sha256="c" * 64)
        self.assertIsNone(other["seed_build_version"])
        self.assertEqual(other["seed_build_version_status"], "unknown")

    def test_history_is_isolated_between_seeds_and_never_proves_the_session(self):
        other = self.root / "other.prt.1"
        other.write_bytes(b"other seed bytes, never loaded by Creo")
        other_digest = hashlib.sha256(other.read_bytes()).hexdigest()
        other_request = {
            "loft_seed": {"snapshot_sha256": other_digest, "seed_name": "other"},
            "template_file": str(other),
        }
        other_result = {
            "seed_native_load": {"status": "loaded", "toolkit_code": 0},
            "creo_release_numeric": 41,
            "creo_release_query_code": 0,
            "session_fingerprint": "other-session",
            "success": True,
            "saved_file_reloaded_and_verified": True,
        }
        compatibility.observe_load(other_request, other_result, "b" * 32)
        value = compatibility.metadata(self.entry, actual_sha256=self.digest)
        self.assertEqual(value["native_compatibility"]["observations"], [])
        self.assertEqual(
            value["native_compatibility"]["status"], "not_verified_for_current_session"
        )
        self.assertIsNone(value["native_compatibility"]["current_session_loadable"])


class SeedLoadFailureDiagnosis(unittest.TestCase):
    """BUG-034: a failed native load keeps the evidence the operator needs."""

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(bridge, "ROOT", self.root))
        self.seed = self.root / "seed.prt.1"
        self.seed.write_bytes(b"isolated test bytes, never loaded by Creo")
        self.digest = hashlib.sha256(self.seed.read_bytes()).hexdigest()
        self.request = {
            "loft_seed": {
                "snapshot_sha256": self.digest,
                "seed_name": "two_smooth",
                "seed_manifest_sha256": self.digest,
                "seed_source": str(self.seed),
            },
            "template_file": str(self.seed),
        }
        self.result = {
            "seed_native_load": {"status": "load_failed", "toolkit_code": -16},
            "creo_release_numeric": 41,
            "creo_release_query_code": 0,
            "session_fingerprint": "isolated-session",
            "success": False,
            "saved_file_reloaded_and_verified": False,
            "failed_stage": "connect",
            "failed_toolkit_call": "ProMdlFiletypeLoad",
            "message": "Toolkit call ProMdlFiletypeLoad failed with code -16 during connect",
        }

    def test_diagnosis_keeps_api_code_stage_seed_identity_and_release(self):
        observed = compatibility.observe_load(self.request, self.result, "a" * 32)
        diagnosis = observed["failure_diagnosis"]
        self.assertEqual(diagnosis["toolkit_api"], "ProMdlFiletypeLoad")
        self.assertEqual(diagnosis["toolkit_code"], -16)
        self.assertEqual(diagnosis["failed_stage"], "connect")
        self.assertEqual(diagnosis["seed_name"], "two_smooth")
        self.assertEqual(diagnosis["seed_sha256"], self.digest)
        self.assertEqual(diagnosis["seed_manifest_sha256"], self.digest)
        self.assertEqual(diagnosis["creo_release_numeric"], 41)
        self.assertFalse(diagnosis["seed_load_succeeded"])
        self.assertFalse(diagnosis["modeling_succeeded"])
        self.assertIn("provenance", diagnosis["guidance"])

    def test_without_evidence_no_version_cause_is_claimed(self):
        observed = compatibility.observe_load(self.request, self.result, "a" * 32)
        diagnosis = observed["failure_diagnosis"]
        self.assertIsNone(diagnosis["version_incompatibility"])
        self.assertEqual(diagnosis["cause"], "undetermined_by_error_alone")
        self.assertIsNone(diagnosis["seed_build_version"])
        self.assertEqual(diagnosis["seed_build_version_status"], "unknown")
        # No unproven "built by X" claim and no invented minimum version.
        text = json.dumps(diagnosis, ensure_ascii=False)
        self.assertNotIn("12.4", text)
        self.assertNotIn("Creo 12.4", text)

    def test_recorded_release_evidence_yields_a_bounded_indication(self):
        compatibility.record_native_build_evidence(
            self.digest, 44, seed_build_version="12.4.0.0", job_id="d" * 32
        )
        observed = compatibility.observe_load(self.request, self.result, "a" * 32)
        diagnosis = observed["failure_diagnosis"]
        indication = diagnosis["version_incompatibility"]
        self.assertIsNotNone(indication)
        self.assertEqual(indication["recorded_release_numeric"], 44)
        self.assertEqual(indication["current_release_numeric"], 41)
        self.assertEqual(diagnosis["cause"], "recorded_release_newer_than_session_release")
        self.assertIn("does not prove the cause", indication["detail"])

    def test_failure_message_keeps_the_native_wording_and_adds_the_identity(self):
        observed = compatibility.observe_load(self.request, self.result, "a" * 32)
        result = {
            "seed_load_evidence": observed,
            "native_message": self.result["message"],
            "message": self.result["message"],
        }
        message = compatibility.load_failure_message(result)
        self.assertIn("ProMdlFiletypeLoad", message)
        self.assertIn("-16", message)
        self.assertIn("connect", message)
        self.assertIn("two_smooth", message)
        self.assertIn(self.digest, message)
        self.assertIn("release_numeric=41", message)

    def test_load_success_and_modeling_success_are_recorded_apart(self):
        result = {
            **self.result,
            "seed_native_load": {"status": "loaded", "toolkit_code": 0},
            "success": True,
        }
        observed = compatibility.observe_load(self.request, result, "a" * 32)
        self.assertTrue(observed["seed_load_succeeded"])
        self.assertTrue(observed["modeling_succeeded"])
        self.assertNotIn("failure_diagnosis", observed)
