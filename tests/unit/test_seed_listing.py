"""FEAT-030/BUG-034: listing and validation describe files, never a Creo session."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge
import seeds
from version import VERSION


class SeedListing(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(bridge, "ROOT", self.root))
        self.payload = b"#UGC:2 PART 2128 1860 810 1 1 15 4100 2023073 00000285 \\\n#- VERS"
        self.digest = hashlib.sha256(self.payload).hexdigest()
        self.manifest = {
            "compatible_server_version": VERSION,
            "tested_creo": "10.0.0.0",
            "seeds": [
                {
                    "name": "fixture",
                    "relative_path": "seeds/example.prt.1",
                    "seed_feature_id": 9,
                    "section_count": 2,
                    "interpolation": "straight",
                    "units": "mm",
                    "sha256": self.digest,
                }
            ],
        }
        (self.root / "docs").mkdir()
        (self.root / "docs/seed_manifest.json").write_text(
            json.dumps(self.manifest, indent=2), encoding="utf-8"
        )
        library = self.root / "seed_library/seeds"
        library.mkdir(parents=True)
        (library / "example.prt.1").write_bytes(self.payload)

    def test_available_states_file_bytes_only(self):
        listed = seeds.list_seeds()
        row = listed["seeds"][0]
        self.assertTrue(row["available"])
        self.assertIn("does not mean the current Creo session can load", row["available_scope"])
        self.assertIn("never connect to Creo", listed["native_load_probe"])
        self.assertIn("Creo 9", listed["compatibility_evidence"])
        self.assertIn("Creo 10", listed["compatibility_evidence"])
        self.assertIn("unverified", listed["compatibility_evidence"])
        self.assertEqual(row["native_compatibility"]["status"], "not_verified_for_current_session")
        self.assertIsNone(row["native_compatibility"]["current_session_loadable"])
        self.assertIsNone(row["seed_build_version"])

    def test_listing_and_validation_never_build_a_toolkit_connection(self):
        with (
            patch.object(bridge, "build_native", side_effect=AssertionError("built a worker")),
            patch.object(bridge, "toolkit_lock", side_effect=AssertionError("took the channel")),
            patch.object(generic_bridge, "submit", side_effect=AssertionError("submitted a job")),
            patch.object(
                generic_bridge,
                "run_generic_job",
                side_effect=AssertionError("ran a native job"),
            ),
        ):
            listed = seeds.list_seeds()
            validated = seeds.validate_seed("fixture")
        self.assertEqual(listed["available_count"], 1)
        self.assertTrue(validated["available"])
        self.assertIn("never connect to Creo", validated["native_load_probe"])

    def test_changed_bytes_drop_the_provenance_and_the_history(self):
        entry = {
            **self.manifest["seeds"][0],
            "seed_build_version": "10.0.0.0",
            "seed_build_version_source": "seed_manifest",
        }
        with patch.object(seeds, "manifest", return_value={**self.manifest, "seeds": [entry]}):
            resolved = seeds.list_seeds()["seeds"][0]
            self.assertEqual(resolved["seed_build_version"], "10.0.0.0")
            (self.root / "seed_library/seeds/example.prt.1").write_bytes(b"changed bytes")
            changed = seeds.list_seeds()["seeds"][0]
        self.assertFalse(changed["available"])
        self.assertIsNone(changed["seed_build_version"])
        self.assertEqual(changed["seed_build_version_status"], "unknown")
        self.assertEqual(changed["native_compatibility"]["observations"], [])

    def test_missing_file_keeps_every_provenance_claim_unknown(self):
        (self.root / "seed_library/seeds/example.prt.1").unlink()
        row = seeds.list_seeds()["seeds"][0]
        self.assertFalse(row["available"])
        self.assertIsNone(row["seed_build_version"])
        self.assertEqual(row["native_compatibility"]["observations"], [])

    def test_manifest_entry_by_digest_matches_only_the_published_bytes(self):
        self.assertEqual(seeds.manifest_entry_by_digest(self.digest)["name"], "fixture")
        self.assertIsNone(seeds.manifest_entry_by_digest("c" * 64))
        self.assertIsNone(seeds.manifest_entry_by_digest("not-a-digest"))


class SeedLoadFailureTerminalState(unittest.TestCase):
    """A diagnostic write failure must not change the modeling terminal state."""

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(bridge, "ROOT", self.root))
        self.jobs = self.root / "jobs"
        self.models = self.root / "models"
        self.jobs.mkdir()
        self.models.mkdir()
        self.enterContext(patch.object(bridge, "JOBS", self.jobs))
        self.enterContext(patch.object(generic_bridge, "MODELS", self.models))
        self.job_id = "a" * 32
        self.model_id = "b" * 32
        self.directory = self.jobs / self.job_id
        self.directory.mkdir()
        self.template = self.root / "seed.prt.1"
        self.template.write_bytes(b"isolated test bytes, never loaded by Creo")
        self.digest = hashlib.sha256(self.template.read_bytes()).hexdigest()
        request = {
            "new": True,
            "readonly": False,
            "model": {"model_id": self.model_id, "status": "ready", "revision": 0},
            "operations": [],
            "components": {},
            "assertions": {},
            "template_file": str(self.template),
            "loft_seed": {
                "snapshot_sha256": self.digest,
                "seed_name": "two_smooth",
                "seed_manifest_sha256": self.digest,
                "seed_source": str(self.template),
                "feature_id": 60,
                "interpolation": "smooth",
                "label": "loft",
                "sections": ["a", "b"],
            },
        }
        (self.directory / "request.json").write_text(json.dumps(request), encoding="utf-8")
        (self.directory / "native_result.json").write_text(
            json.dumps(
                {
                    "success": False,
                    "connected": True,
                    "toolkit_code": -16,
                    "seed_native_load": {"status": "load_failed", "toolkit_code": -16},
                    "creo_release_numeric": 41,
                    "creo_release_query_code": 0,
                    "session_fingerprint": "isolated-session",
                    "failed_stage": "connect",
                    "failed_toolkit_call": "ProMdlFiletypeLoad",
                    "message": (
                        "Toolkit call ProMdlFiletypeLoad failed with code -16 during connect"
                    ),
                }
            ),
            encoding="utf-8",
        )
        (self.models / self.model_id).mkdir()
        self.manifest = {
            "job_id": self.job_id,
            "kind": "generic",
            "model_id": self.model_id,
            "status": "queued",
            "readonly": False,
            "created_at": bridge.now(),
        }

    def run_job(self):
        import contextlib
        import subprocess

        class Completed:
            returncode = 0

        with (
            patch.object(bridge, "toolkit_lock", return_value=contextlib.nullcontext()),
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe"),
            patch.object(bridge, "config", return_value={"generic_timeout_seconds": 600}),
            patch.object(bridge, "native_environment", return_value={}),
            patch.object(bridge, "note_native_outcome"),
            patch.object(subprocess, "run", return_value=Completed()),
        ):
            generic_bridge.run_generic_job(self.job_id, self.manifest)
        return bridge.read_json(self.directory / "job.json")

    def test_failed_seed_load_ends_failed_with_the_preserved_diagnosis(self):
        published = self.run_job()
        self.assertEqual(published["status"], "failed")
        message = published["message"]
        self.assertIn("ProMdlFiletypeLoad", message)
        self.assertIn("-16", message)
        self.assertIn("two_smooth", message)
        self.assertIn(self.digest, message)
        self.assertIn("release_numeric=41", message)
        evidence = published["result"]["seed_load_evidence"]
        self.assertEqual(evidence["status"], "load_failed")
        self.assertFalse(evidence["seed_load_succeeded"])
        self.assertFalse(evidence["modeling_succeeded"])

    def test_diagnostic_write_failure_keeps_the_same_terminal_state(self):
        # A regular file where the evidence directory belongs makes the write fail
        # without touching the job records.
        (self.root / "build").mkdir()
        (self.root / "build/seed_compatibility").write_text("not a directory", encoding="utf-8")
        published = self.run_job()
        self.assertEqual(published["status"], "failed")
        self.assertIn("ProMdlFiletypeLoad", published["message"])
        evidence = published["result"]["seed_load_evidence"]
        self.assertEqual(evidence["status"], "load_failed")
        self.assertFalse(evidence["evidence_persisted"])
        self.assertIn("evidence_error", evidence)
        self.assertEqual(
            published["result"]["seed_load_evidence"]["failure_diagnosis"]["toolkit_code"], -16
        )
