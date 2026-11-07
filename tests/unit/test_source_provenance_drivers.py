"""Evidence drivers degrade explicitly when Git is unavailable.

DEV-074 H13: every evidence driver must share ``source_provenance``. In an
extracted distribution without ``.git`` or a Git executable the reports keep
their existing fields but must show ``git_status="unavailable"`` and never
invent a commit, branch or dirty flag.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from creo_mechdog import source_provenance
from tools import (
    dev_check,
    test_adoption_planar_wall,
    test_adoption_product_rules,
    test_assembly_ack_failure,
    test_assembly_bundle,
    test_failed_model_cleanup,
    test_first_wall_origin,
    test_g5_native_probe,
    test_geometry_transform_copies,
    test_native_countersink,
    test_sheetmetal_box_live,
    test_sketch_geometry_deviation,
    test_sketch_shift_batch,
    test_startup_retry,
    test_toolkit_channel,
    test_toolkit_recovery,
    test_update_check,
)

DRIVERS = (
    ("test_update_check.provenance", test_update_check, "ROOT", "provenance", ()),
    ("test_toolkit_recovery.provenance", test_toolkit_recovery, "ROOT", "provenance", ()),
    ("test_toolkit_channel.provenance", test_toolkit_channel, "ROOT", "provenance", ()),
    ("test_startup_retry.provenance", test_startup_retry, "ROOT", "provenance", ()),
    (
        "test_sketch_geometry_deviation.provenance",
        test_sketch_geometry_deviation,
        "ROOT",
        "provenance",
        (
            "tools/test_sketch_geometry_deviation.py",
            "tests/unit/test_sketch_geometry_deviation.py",
        ),
    ),
    (
        "test_native_countersink.provenance",
        test_native_countersink,
        "ROOT",
        "provenance",
        ("tests/unit/test_native_countersink.py", "tools/test_native_countersink.py"),
    ),
    (
        "test_assembly_bundle.provenance",
        test_assembly_bundle,
        "ROOT",
        "provenance",
        ("tests/unit/test_assembly_bundle.py", "tools/test_assembly_bundle.py"),
    ),
    (
        "test_failed_model_cleanup.local_provenance",
        test_failed_model_cleanup,
        "ROOT",
        "local_provenance",
        (),
    ),
    (
        "test_sheetmetal_box_live.local_provenance",
        test_sheetmetal_box_live,
        "ROOT",
        "local_provenance",
        (
            "tools/test_sheetmetal_box_live.py",
            "tests/unit/test_sheetmetal_box_live.py",
            "tools/test_sheetmetal_flange.py",
            "tests/unit/test_sheetmetal_flange.py",
            "tests/unit/test_sheetmetal_relief.py",
            "tools/sheetmetal_live.py",
        ),
    ),
    (
        "test_g5_native_probe.local_provenance",
        test_g5_native_probe,
        "ROOT",
        "local_provenance",
        (
            "docs/development/G5-NATIVE-CONTRACT.md",
            "tools/test_g5_native_probe.py",
            "tools/generate_constants.py",
            "src/creo_mechdog/schema.py",
            "native/generic.cpp",
            "native/surfaces.cpp",
            "native/blend_create.cpp",
        ),
    ),
    ("test_sketch_shift_batch._environment", test_sketch_shift_batch, "ROOT", "_environment", ()),
    (
        "test_geometry_transform_copies._identity",
        test_geometry_transform_copies,
        "ROOT",
        "_identity",
        ("version.py",),
    ),
    ("test_assembly_ack_failure._identity", test_assembly_ack_failure, "ROOT", "_identity", ()),
    (
        "test_first_wall_origin.source_identity",
        test_first_wall_origin,
        "ROOT",
        "source_identity",
        test_first_wall_origin.SOURCE_FILES,
    ),
    (
        "test_adoption_planar_wall.source_identity",
        test_adoption_planar_wall,
        "ROOT",
        "source_identity",
        test_adoption_planar_wall.SOURCE_FILES,
    ),
)


def write_files(root: Path, names) -> None:
    for name in names:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(name, encoding="utf-8")


class LocalProvenanceTests(unittest.TestCase):
    def test_git_executable_missing_falls_back_to_directory_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_files(root, ("tools/driver.py",))
            with patch.object(
                source_provenance.subprocess, "run", side_effect=FileNotFoundError("git")
            ):
                evidence = source_provenance.local_provenance(root)
        self.assertEqual(evidence["git_status"], "unavailable")
        self.assertIsNone(evidence["commit"])
        self.assertIsNone(evidence["branch"])
        self.assertIsNone(evidence["dirty"])
        self.assertIn("tools/driver.py", evidence["source_sha256"])
        self.assertTrue(evidence["source_fingerprint"])

    def test_directory_outside_a_git_root_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_files(root, ("src/creo_mechdog/driver.py",))
            with patch.object(
                source_provenance.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(128, "git"),
            ):
                evidence = source_provenance.local_provenance(root)
        self.assertEqual(evidence["git_status"], "unavailable")
        self.assertIsNone(evidence["commit"])
        self.assertIn("src/creo_mechdog/driver.py", evidence["source_sha256"])

    def test_repository_root_records_the_real_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_files(root, ("tools/driver.py",))
            with patch.object(
                source_provenance.subprocess,
                "run",
                side_effect=[
                    subprocess.CompletedProcess([], 0, str(root) + "\n"),
                    subprocess.CompletedProcess([], 0, "tools/driver.py\n"),
                    subprocess.CompletedProcess([], 0, "b" * 40 + "\n"),
                    subprocess.CompletedProcess([], 0, "main\n"),
                    subprocess.CompletedProcess([], 0, " M tools/driver.py\n"),
                ],
            ):
                evidence = source_provenance.local_provenance(root)
        self.assertEqual(evidence["git_status"], "available")
        self.assertEqual(evidence["commit"], "b" * 40)
        self.assertEqual(evidence["branch"], "main")
        self.assertTrue(evidence["dirty"])


class DriverFallbackTests(unittest.TestCase):
    def assert_degraded(self, evidence: dict) -> None:
        self.assertEqual(evidence["git_status"], "unavailable")
        for key in ("commit", "head", "source_commit", "branch", "dirty"):
            if key in evidence:
                self.assertIsNone(evidence[key], key)

    def test_every_migrated_driver_degrades_without_git(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for label, module, root_attr, function_name, files in DRIVERS:
                with self.subTest(driver=label):
                    write_files(root, files)
                    collector = getattr(module, function_name)
                    with (
                        patch.object(module, root_attr, root),
                        patch.object(
                            source_provenance.subprocess,
                            "run",
                            side_effect=FileNotFoundError("git"),
                        ),
                    ):
                        self.assert_degraded(collector())

    def test_dev_check_git_state_degrades_outside_a_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "extracted"
            with patch.object(
                source_provenance.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(128, "git"),
            ):
                self.assertEqual(
                    dev_check.git_state(root),
                    {"commit": None, "dirty": None, "git_status": "unavailable"},
                )

    def test_product_rules_identity_degrades_without_git(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(
                    test_adoption_product_rules,
                    "SOURCE_PATHS",
                    SimpleNamespace(resource_root=root),
                ),
                patch.object(
                    source_provenance.subprocess, "run", side_effect=FileNotFoundError("git")
                ),
            ):
                identity = test_adoption_product_rules.git_identity()
        self.assertEqual(identity, {"commit": None, "dirty": None, "git_status": "unavailable"})


if __name__ == "__main__":
    unittest.main()
