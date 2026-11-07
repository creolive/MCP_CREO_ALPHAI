"""The preview acceptance report remains usable from a source archive."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creo_mechdog import source_provenance
from tools import test_t07_preview as driver


class PreviewProvenanceTests(unittest.TestCase):
    def test_no_git_repository_reports_unknown_identity_and_source_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (
                "server.py",
                "tools/test_t07_preview.py",
                "tests/unit/test_t07_preview.py",
                "src/creo_mechdog/preview.py",
                "native/example.cpp",
            ):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(name, encoding="utf-8")
            with (
                patch.object(driver, "ROOT", root),
                patch.object(
                    source_provenance.subprocess,
                    "run",
                    side_effect=subprocess.CalledProcessError(128, "git"),
                ),
            ):
                provenance = driver.local_provenance()
            self.assertEqual(provenance["git_status"], "unavailable")
            self.assertIsNone(provenance["commit"])
            self.assertIsNone(provenance["branch"])
            self.assertIsNone(provenance["dirty"])
            self.assertEqual(len(provenance["source_sha256"]), 5)
            self.assertTrue(provenance["source_fingerprint"])

    def test_git_executable_missing_is_also_supported(self):
        with patch.object(
            source_provenance.subprocess, "run", side_effect=FileNotFoundError("git")
        ):
            provenance = driver.local_provenance()
        self.assertEqual(provenance["git_status"], "unavailable")
        self.assertIsNone(provenance["commit"])

    def test_other_offline_report_drivers_share_the_missing_git_fallback(self):
        from importlib import import_module

        names = (
            "test_arc_direction",
            "test_datum_plane_contract",
            "test_datum_plane_through_points",
            "test_detail_feature_observation",
            "test_dev048_plane_frame",
            "test_dev049_profile_replay",
            "test_dev049_tilted_cut",
            "test_draft_regression",
            "test_endpoint_weld_gate",
            "test_installation_loft",
            "test_plan_performance",
            "test_profile_endpoint_diagnostics",
            "test_sheetmetal_contract",
            "test_sheetmetal_flange",
            "test_sheetmetal_overlap",
            "test_sheetmetal_relief",
            "test_sketch_origin_diagnostics",
            "test_t05_native",
            "test_t06_native",
            "test_t07_preview",
            "test_t08_feature_state",
            "test_t09_assembly_replay",
            "test_t12_examples",
            "test_tilted_sketch_3pt",
            "test_tilted_sketch_lifecycle",
        )
        modules = [import_module("tools." + name) for name in names]
        with patch.object(
            source_provenance.subprocess, "run", side_effect=FileNotFoundError("git")
        ):
            for module in modules:
                with self.subTest(driver=module.__name__):
                    collector = getattr(module, "local_provenance", None) or module.provenance
                    provenance = collector()
                    self.assertEqual(provenance["git_status"], "unavailable")
                    self.assertIsNone(provenance["dirty"])
                    self.assertTrue(provenance["source_fingerprint"])
                    if "source_sha256" in provenance:
                        self.assertIn(
                            "tools/" + module.__name__.split(".")[-1] + ".py",
                            provenance["source_sha256"],
                        )


if __name__ == "__main__":
    unittest.main()
