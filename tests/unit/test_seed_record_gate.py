"""DEV-061: the repository seed record must match a fresh rebuild.

BUG-089/DEV-053 P04 already gate the archive at pack time, at install time and
in the release checklist. What was still missing is a check that *this tree's*
``docs/seed_package.json`` equals the archive a rebuild of *this tree* produces:
the existing fixture writes its own record, so a forgotten backfill only
surfaced when someone ran the packager. This test is that gate.
"""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from creo_mechdog import release_integrity
from tools import package_seeds

ROOT = Path(__file__).resolve().parents[2]
VERSION = release_integrity.read_version(ROOT)
RECORD = ROOT / release_integrity.TRUSTED_RECORD


class RepositoryRecordGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.archive = self.temp / "seed-library.zip"

    def build(self) -> str:
        return package_seeds.build_seed_archive(ROOT, self.archive)

    def record_copy(self, **overrides) -> Path:
        record = json.loads(RECORD.read_text(encoding="utf-8"))
        record.update(overrides)
        path = self.temp / "seed_package.json"
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return path

    def test_repository_record_matches_a_fresh_rebuild(self):
        digest = self.build()
        checked = release_integrity.assert_repo_record_matches(ROOT, self.archive)
        self.assertEqual(checked["seed_archive_sha256"], digest)
        self.assertEqual(checked["compatible_server_version"], VERSION)
        self.assertEqual(checked["record"], str(RECORD))

    def test_stale_digest_fails_with_a_backfill_hint(self):
        self.build()
        stale = self.record_copy(seed_archive_sha256="0" * 64)
        with self.assertRaises(ValueError) as caught:
            release_integrity.assert_repo_record_matches(ROOT, self.archive, record_path=stale)
        message = str(caught.exception)
        self.assertIn("seed_archive_sha256", message)
        self.assertIn("docs/seed_package.json", message)

    def test_record_version_must_match_version_py(self):
        self.build()
        stale = self.record_copy(compatible_server_version="0.0.0")
        with self.assertRaises(ValueError) as caught:
            release_integrity.assert_repo_record_matches(ROOT, self.archive, record_path=stale)
        self.assertIn("0.0.0", str(caught.exception))
        self.assertIn(VERSION, str(caught.exception))

    def test_missing_archive_is_rejected(self):
        with self.assertRaises(ValueError):
            release_integrity.assert_repo_record_matches(ROOT, self.temp / "absent.zip")

    def test_cli_exits_nonzero_when_the_record_is_stale(self):
        def fake_build(root: Path, archive: Path) -> str:
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
                output.writestr("dummy.txt", b"not the real seed archive")
            return "0" * 64

        original = package_seeds.build_seed_archive
        package_seeds.build_seed_archive = fake_build
        try:
            code = package_seeds.main(["--output", str(self.archive)])
        finally:
            package_seeds.build_seed_archive = original
        self.assertNotEqual(code, 0)
        self.assertTrue(self.archive.exists(), "the built archive must stay for inspection")

    def test_cli_exit_zero_when_the_record_matches(self):
        self.assertEqual(package_seeds.main(["--output", str(self.archive)]), 0)

    def test_cli_can_explicitly_skip_the_gate_while_preparing_a_backfill(self):
        def fake_build(root: Path, archive: Path) -> str:
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
                output.writestr("dummy.txt", b"draft")
            return "0" * 64

        original = package_seeds.build_seed_archive
        package_seeds.build_seed_archive = fake_build
        try:
            code = package_seeds.main(["--output", str(self.archive), "--allow-record-mismatch"])
        finally:
            package_seeds.build_seed_archive = original
        self.assertEqual(code, 0)
