"""BUG-089 / DEV-053 P04: the seed archive and the release inputs must agree.

The failure regressions here use real built archives and real bytes: a tampered
archive, a wrong digest, a foreign version, disagreeing manifests and a stale
README version section are all rejected before anything is written.
"""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import bridge
import seeds
from creo_mechdog import release_integrity
from tools import package, package_seeds

ROOT = Path(__file__).resolve().parents[2]
VERSION = release_integrity.read_version(ROOT)


def build_seed_archive(root: Path, archive: Path) -> str:
    """Build the real seed archive of ``root`` and return its SHA256."""
    return package_seeds.build_seed_archive(root, archive)


class SeedArchiveFixture(unittest.TestCase):
    """A source tree whose seed library, manifests and record describe one release."""

    def setUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root = self.temp / "source"
        self.root.mkdir()
        shutil.copytree(ROOT / "seed_library", self.root / "seed_library")
        (self.root / "docs").mkdir()
        shutil.copy2(ROOT / "docs/seed_manifest.json", self.root / "docs/seed_manifest.json")
        shutil.copy2(ROOT / "LICENSE", self.root / "LICENSE")
        shutil.copy2(ROOT / "README.md", self.root / "README.md")
        (self.root / "version.py").write_text(f'VERSION = "{VERSION}"\n', encoding="utf-8")
        self.archive = self.temp / "seed-library.zip"
        self.digest = build_seed_archive(self.root, self.archive)
        self.write_record(self.digest, VERSION)

    def write_record(self, digest: str, version: str, name: str | None = None):
        record = {
            "compatible_server_version": version,
            "seed_archive_name": name or self.archive.name,
            "seed_archive_sha256": digest,
        }
        (self.root / "docs/seed_package.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )

    def rewrite_archive(self, mutate) -> Path:
        """Rebuild the archive with one member mutated; return the new archive path."""
        target = self.temp / "mutated.zip"
        with zipfile.ZipFile(self.archive) as source:
            members = [(info.filename, source.read(info.filename)) for info in source.infolist()]
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for name, data in members:
                output.writestr(name, mutate(name, data))
        return target


class SeedArchiveValidationTests(SeedArchiveFixture):
    def test_real_built_archive_matches_the_repository_release_inputs(self):
        summary = release_integrity.validate_release_inputs(self.root, self.archive)
        self.assertEqual(summary["version"], VERSION)
        self.assertEqual(summary["seed_archive_sha256"], self.digest)
        self.assertEqual(summary["seed_count"], 9)
        self.assertEqual(summary["readme_title_version"], VERSION)
        self.assertEqual(summary["readme_current_version"], VERSION)

    def test_tampered_archive_bytes_are_rejected(self):
        tampered = self.rewrite_archive(
            lambda name, data: data + b"\x00" if name.endswith(".prt.1") else data
        )
        with self.assertRaisesRegex(ValueError, "SHA256 differs"):
            release_integrity.validate_seed_archive(self.root, tampered)

    def test_trusted_record_digest_mismatch_is_rejected(self):
        self.write_record("0" * 64, VERSION)
        with self.assertRaisesRegex(ValueError, "SHA256 differs"):
            release_integrity.validate_seed_archive(self.root, self.archive)

    def test_foreign_archive_version_is_rejected(self):
        foreign = self.temp / "foreign.zip"
        with zipfile.ZipFile(self.archive) as source:
            members = [(info.filename, source.read(info.filename)) for info in source.infolist()]
        with zipfile.ZipFile(foreign, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for name, data in members:
                output.writestr(
                    name.replace(f"-{VERSION}-seed-library/", "-0.0.1-seed-library/"), data
                )
        self.write_record(hashlib.sha256(foreign.read_bytes()).hexdigest(), VERSION)
        with self.assertRaisesRegex(ValueError, "outside"):
            release_integrity.validate_seed_archive(self.root, foreign)

    def test_archive_manifest_version_mismatch_is_rejected(self):
        manifest = json.loads((self.root / "docs/seed_manifest.json").read_text(encoding="utf-8"))
        manifest["compatible_server_version"] = "0.0.1"
        (self.root / "docs/seed_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "manifest differs"):
            release_integrity.validate_seed_archive(self.root, self.archive)

    def test_native_seed_bytes_inside_the_archive_are_protected(self):
        tampered = self.rewrite_archive(
            lambda name, data: data + b"\x00" if name.endswith(".prt.1") else data
        )
        self.write_record(hashlib.sha256(tampered.read_bytes()).hexdigest(), VERSION)
        with self.assertRaisesRegex(ValueError, "differ from the published SHA256"):
            release_integrity.validate_seed_archive(self.root, tampered)

    def test_unsafe_archive_member_path_is_rejected(self):
        unsafe = self.temp / "unsafe.zip"
        with zipfile.ZipFile(self.archive) as source:
            members = [(info.filename, source.read(info.filename)) for info in source.infolist()]
        with zipfile.ZipFile(unsafe, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for name, data in members:
                output.writestr(name.replace("seeds/", "../escape/", 1), data)
        self.write_record(hashlib.sha256(unsafe.read_bytes()).hexdigest(), VERSION)
        with self.assertRaisesRegex(ValueError, "Unsafe seed archive path"):
            release_integrity.validate_seed_archive(self.root, unsafe)

    def test_disagreeing_seed_manifests_are_rejected(self):
        manifest = json.loads((self.root / "docs/seed_manifest.json").read_text(encoding="utf-8"))
        manifest["compatible_server_version"] = "0.0.1"
        (self.root / "seed_library/seed_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "manifests differ"):
            release_integrity.validate_release_inputs(self.root, self.archive)

    def test_stale_readme_current_version_section_is_rejected(self):
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        (self.root / "README.md").write_text(
            readme.replace(f"当前正式版 **{VERSION}**", "当前正式版 **0.0.1**"), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "README current release section"):
            release_integrity.validate_release_inputs(self.root, self.archive)

    def test_stale_readme_title_version_is_rejected(self):
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        (self.root / "README.md").write_text(
            readme.replace(f"# MCP_CREO_MechDog {VERSION}", "# MCP_CREO_MechDog 0.0.1"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "README title version"):
            release_integrity.validate_release_inputs(self.root, self.archive)

    def test_missing_trusted_record_is_rejected(self):
        (self.root / "docs/seed_package.json").unlink()
        with self.assertRaisesRegex(ValueError, "Trusted seed package record is missing"):
            release_integrity.validate_seed_archive(self.root, self.archive)


class SeedArchiveInstallTests(SeedArchiveFixture):
    """The published archive installs through the public seed library entry."""

    def install_root(self) -> Path:
        root = self.temp / "install-root"
        root.mkdir()
        shutil.copytree(ROOT / "seed_library", root / "seed_library")
        (root / "docs").mkdir()
        shutil.copy2(ROOT / "docs/seed_manifest.json", root / "docs/seed_manifest.json")
        shutil.copy2(ROOT / "docs/seed_package.json", root / "docs/seed_package.json")
        shutil.copy2(ROOT / "LICENSE", root / "LICENSE")
        shutil.copy2(ROOT / "version.py", root / "version.py")
        return root

    def test_published_archive_installs_into_a_temporary_root(self):
        install_root = self.install_root()
        shutil.rmtree(install_root / "seed_library")
        with patch.object(bridge, "ROOT", install_root):
            result = seeds.install_seed_library(archive_file=str(self.archive))
        self.assertTrue(result["installed"])
        self.assertEqual(result["available_count"], 9)
        self.assertTrue((install_root / "seed_library/seed_manifest.json").is_file())

    def test_tampered_archive_is_refused_before_writing_the_target(self):
        install_root = self.install_root()
        shutil.rmtree(install_root / "seed_library")
        tampered = self.rewrite_archive(
            lambda name, data: data + b"\x00" if name.endswith(".prt.1") else data
        )
        with patch.object(bridge, "ROOT", install_root):
            with self.assertRaisesRegex(ValueError, "SHA256 differs"):
                seeds.install_seed_library(archive_file=str(tampered))
        self.assertFalse((install_root / "seed_library").exists())

    def test_wrong_digest_archive_is_refused_before_writing_the_target(self):
        install_root = self.install_root()
        shutil.rmtree(install_root / "seed_library")
        record = json.loads((install_root / "docs/seed_package.json").read_text(encoding="utf-8"))
        record["seed_archive_sha256"] = "0" * 64
        (install_root / "docs/seed_package.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        with patch.object(bridge, "ROOT", install_root):
            with self.assertRaisesRegex(ValueError, "SHA256 differs"):
                seeds.install_seed_library(archive_file=str(self.archive))
        self.assertFalse((install_root / "seed_library").exists())

    def test_directory_install_stays_compatible(self):
        install_root = self.install_root()
        with patch.object(bridge, "ROOT", install_root):
            result = seeds.install_seed_library()
        self.assertTrue(result["installed"])
        self.assertEqual(result["available_count"], 9)


class SeedPackagingGateTests(SeedArchiveFixture):
    """The source package entry refuses a missing or mismatched seed archive."""

    def run_package(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "tools/package.py"), *args],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            check=False,
        )

    def test_missing_seed_archive_argument_is_refused(self):
        result = self.run_package("--output", str(self.temp / "source.zip"))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.temp / "source.zip").exists())

    def test_mismatched_seed_archive_is_refused_without_writing_a_source_package(self):
        wrong = self.temp / "wrong.zip"
        shutil.copy2(self.archive, wrong)
        with zipfile.ZipFile(wrong, "a") as archive:
            archive.writestr("extra.txt", "not part of the release")
        result = self.run_package(
            "--seed-archive", str(wrong), "--output", str(self.temp / "source.zip")
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused", result.stderr)
        self.assertFalse((self.temp / "source.zip").exists())
        self.assertFalse((self.temp / "source.zip.sha256").exists())

    def test_valid_seed_archive_packages_the_source_with_the_explicit_output(self):
        output = self.temp / "source.zip"
        result = self.run_package("--seed-archive", str(self.archive), "--output", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.is_file())
        self.assertTrue((self.temp / "source.zip.sha256").is_file())
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
        self.assertIn("MCP_CREO_MechDog/version.py", names)
        self.assertIn("MCP_CREO_MechDog/docs/seed_manifest.json", names)
        self.assertIn("MCP_CREO_MechDog/seed_library/seed_manifest.json", names)

    def test_valid_seed_archive_packages_the_source_with_the_default_output(self):
        default = ROOT.parent / f"MCP_CREO_MechDog-{VERSION}-source.zip"
        self.assertFalse(default.exists(), "default output path is already taken")
        result = self.run_package("--seed-archive", str(self.archive))
        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(default.is_file())
        finally:
            default.unlink(missing_ok=True)
            default.with_suffix(".zip.sha256").unlink(missing_ok=True)

    def test_valid_seed_archive_packages_a_new_empty_stage_directory(self):
        stage = self.temp / "stage"
        result = self.run_package(
            "--seed-archive",
            str(self.archive),
            "--output",
            str(self.temp / "source.zip"),
            "--stage",
            str(stage),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((stage / "version.py").is_file())
        self.assertTrue((stage / "docs/seed_manifest.json").is_file())

    def test_existing_output_archive_is_still_refused(self):
        output = self.temp / "source.zip"
        output.write_bytes(b"existing")
        result = self.run_package("--seed-archive", str(self.archive), "--output", str(output))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_bytes(), b"existing")

    def test_non_empty_stage_directory_is_still_refused(self):
        stage = self.temp / "stage"
        stage.mkdir()
        (stage / "occupied.txt").write_text("keep me", encoding="utf-8")
        result = self.run_package(
            "--seed-archive",
            str(self.archive),
            "--output",
            str(self.temp / "source.zip"),
            "--stage",
            str(stage),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((stage / "occupied.txt").read_text(encoding="utf-8"), "keep me")


class SeedPackagerAllowlistTests(unittest.TestCase):
    def test_seed_packager_and_release_gate_share_one_member_set(self):
        members = {
            path.relative_to(ROOT / "seed_library").as_posix()
            for path in release_integrity.seed_library_files(ROOT)
        }
        self.assertEqual(len(members), 24)
        self.assertIn("seed_manifest.json", members)
        self.assertIn("LICENSE", members)
        self.assertIn("resolve_seed.py", members)
        self.assertTrue(any(name.endswith(".prt.1") for name in members))

    def test_source_package_allowlist_includes_the_seed_library_members(self):
        packaged = {path.relative_to(ROOT).as_posix() for path in package.source_files()}
        for path in release_integrity.seed_library_files(ROOT):
            self.assertIn(path.relative_to(ROOT).as_posix(), packaged)

    def test_seeds_module_exposes_the_trusted_digest_entry_point(self):
        self.assertEqual(
            seeds.expected_archive_sha256(), release_integrity.trusted_seed_archive_digest(ROOT)
        )
        self.assertRegex(seeds.expected_archive_sha256(), r"^[a-f0-9]{64}$")


if __name__ == "__main__":
    unittest.main()
