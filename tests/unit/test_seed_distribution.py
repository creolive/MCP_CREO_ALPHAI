import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import bridge
from creo_mechdog import seeds
from tools import package_seeds
from version import VERSION


class SeedDistributionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.native = b"native\x00\r\n\xffPRT"

    def fixture(self, name, newline):
        root = self.temp / name
        library = root / "seed_library"
        (library / "seeds").mkdir(parents=True)
        (root / "docs").mkdir()
        manifest = {
            "compatible_server_version": VERSION,
            "seeds": [
                {
                    "name": "fixture",
                    "seed_feature_id": 9,
                    "section_count": 2,
                    "relative_path": "seeds/example.prt.1",
                    "sha256": hashlib.sha256(self.native).hexdigest(),
                }
            ],
        }
        for path, text in (
            (root / "LICENSE", "MIT fixture\nCopyright fixture\n"),
            (library / "LICENSE", "MIT fixture\nCopyright fixture\n"),
            (library / "README.md", "# Fixture\nSeed description\n"),
            (library / "seed_manifest.json", json.dumps(manifest, indent=2) + "\n"),
            (root / "docs/seed_manifest.json", json.dumps(manifest, indent=2) + "\n"),
            (root / "version.py", f'VERSION = "{VERSION}"\n'),
        ):
            path.write_bytes(text.replace("\n", newline).encode())
        (library / "seeds/example.prt.1").write_bytes(self.native)
        return root, library, manifest

    def test_seed_zip_identical_across_text_newlines_and_native_bytes_preserved(self):
        archives = []
        for name, newline in (("lf", "\n"), ("crlf", "\r\n")):
            root, library, _ = self.fixture(name, newline)
            output = self.temp / (name + ".zip")
            package_seeds.build_seed_archive(root, output)
            archives.append(output.read_bytes())
            with zipfile.ZipFile(output) as archive:
                prefix = f"MCP_CREO_MechDog-{VERSION}-seed-library/"
                self.assertEqual(archive.read(prefix + "seeds/example.prt.1"), self.native)
                self.assertNotIn(b"\r\n", archive.read(prefix + "seed_manifest.json"))
            self.assertEqual((library / "seeds/example.prt.1").read_bytes(), self.native)
        self.assertEqual(archives[0], archives[1])

    def test_license_comparison_accepts_newline_difference_but_rejects_changed_terms(self):
        root, library, manifest = self.fixture("license", "\r\n")
        (root / "LICENSE").write_bytes(b"MIT fixture\nCopyright fixture\n")
        with (
            patch.object(bridge, "ROOT", root),
            patch.object(seeds, "manifest", return_value=manifest),
        ):
            seeds._validate_library(library)
            (library / "LICENSE").write_bytes(b"Changed license terms\r\n")
            with self.assertRaisesRegex(ValueError, "MIT license"):
                seeds._validate_library(library)

    def test_directory_install_stays_compatible(self):
        root, library, manifest = self.fixture("directory", "\n")
        with (
            patch.object(bridge, "ROOT", root),
            patch.object(seeds, "manifest", return_value=manifest),
        ):
            result = seeds.install_seed_library(directory=str(library))
        self.assertTrue(result["installed"])
        self.assertEqual(result["available_count"], 1)

    def test_zip_member_native_bytes_are_verified_against_the_manifest(self):
        root, library, manifest = self.fixture("native", "\n")
        archive = root / "library.zip"
        prefix = f"MCP_CREO_MechDog-{VERSION}-seed-library/"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for name, data in (
                (f"{prefix}seed_manifest.json", b"{}"),
                (f"{prefix}seeds/example.prt.1", self.native),
            ):
                output.writestr(name, data)
        (root / "docs/seed_package.json").write_text(
            json.dumps(
                {
                    "compatible_server_version": VERSION,
                    "seed_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        with (
            patch.object(bridge, "ROOT", root),
            patch.object(seeds, "manifest", return_value=manifest),
        ):
            with self.assertRaisesRegex(ValueError, "manifest differs"):
                seeds.install_seed_library(archive_file=str(archive))

    def test_zip_member_native_bytes_are_rejected_when_they_do_not_match(self):
        root, library, manifest = self.fixture("native-mismatch", "\n")
        archive = root / "library.zip"
        prefix = f"MCP_CREO_MechDog-{VERSION}-seed-library/"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            output.writestr(f"{prefix}seed_manifest.json", json.dumps(manifest).encode())
            output.writestr(f"{prefix}seeds/example.prt.1", self.native + b"\x00")
        (root / "docs/seed_package.json").write_text(
            json.dumps(
                {
                    "compatible_server_version": VERSION,
                    "seed_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        with (
            patch.object(bridge, "ROOT", root),
            patch.object(seeds, "manifest", return_value=manifest),
        ):
            with self.assertRaisesRegex(ValueError, "published SHA256"):
                seeds.install_seed_library(archive_file=str(archive))

    def test_zip_member_paths_cannot_escape_the_install_root(self):
        root, library, manifest = self.fixture("escape", "\n")
        archive = root / "library.zip"
        prefix = f"MCP_CREO_MechDog-{VERSION}-seed-library/"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            output.writestr(f"{prefix}seed_manifest.json", json.dumps(manifest).encode())
            output.writestr(f"{prefix}../escape.prt.1", self.native)
        (root / "docs/seed_package.json").write_text(
            json.dumps(
                {
                    "compatible_server_version": VERSION,
                    "seed_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        with (
            patch.object(bridge, "ROOT", root),
            patch.object(seeds, "manifest", return_value=manifest),
        ):
            with self.assertRaisesRegex(ValueError, "Unsafe seed archive path"):
                seeds.install_seed_library(archive_file=str(archive))
        self.assertFalse((root / "escape.prt.1").exists())
