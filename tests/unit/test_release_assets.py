"""DEV-045/C01: a release must publish both ZIPs and both SHA256 sidecars."""

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from creo_mechdog import release_download, release_integrity
from tools import check_release_assets, package


class ReleaseAssetGateTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.version = "9.9.9"
        (
            self.source,
            self.source_sidecar,
            self.seed,
            self.seed_sidecar,
        ) = check_release_assets.expected_assets(self.version)

    def write_asset(self, name: str, payload: bytes) -> None:
        (self.directory / name).write_bytes(payload)

    def write_sidecar(self, name: str, digest: str, target: str) -> None:
        (self.directory / name).write_text(f"{digest}  {target}\n", encoding="ascii")

    def publish_complete_release(self) -> None:
        for name, payload in ((self.source, b"source"), (self.seed, b"seed")):
            self.write_asset(name, payload)
            digest = hashlib.sha256(payload).hexdigest()
            self.write_sidecar(f"{name}.sha256", digest, name)

    def test_expected_assets_are_four_files(self):
        self.assertEqual(
            check_release_assets.expected_assets("1.2.3"),
            [
                "MCP_CREO_MechDog-1.2.3-source.zip",
                "MCP_CREO_MechDog-1.2.3-source.zip.sha256",
                "MCP_CREO_MechDog-1.2.3-seed-library.zip",
                "MCP_CREO_MechDog-1.2.3-seed-library.zip.sha256",
            ],
        )

    def test_complete_release_has_no_problems(self):
        self.publish_complete_release()
        self.assertEqual(check_release_assets.validate_directory(self.directory, self.version), [])

    def test_missing_source_sidecar_is_reported(self):
        self.publish_complete_release()
        (self.directory / self.source_sidecar).unlink()
        problems = check_release_assets.validate_directory(self.directory, self.version)
        self.assertIn(f"missing release asset: {self.source_sidecar}", problems)

    def test_missing_seed_sidecar_is_reported(self):
        self.publish_complete_release()
        (self.directory / self.seed_sidecar).unlink()
        problems = check_release_assets.validate_directory(self.directory, self.version)
        self.assertIn(f"missing release asset: {self.seed_sidecar}", problems)

    def test_digest_mismatch_is_reported(self):
        self.publish_complete_release()
        self.write_sidecar(self.source_sidecar, "0" * 64, self.source)
        problems = check_release_assets.validate_directory(self.directory, self.version)
        self.assertTrue(any("differs from" in problem for problem in problems))

    def test_sidecar_target_name_mismatch_is_reported(self):
        self.publish_complete_release()
        digest = hashlib.sha256(b"source").hexdigest()
        self.write_sidecar(self.source_sidecar, digest, self.seed)
        problems = check_release_assets.validate_directory(self.directory, self.version)
        self.assertIn(
            f"{self.source_sidecar}: sidecar names {self.seed}, expected {self.source}",
            problems,
        )

    def test_extra_asset_is_reported(self):
        self.publish_complete_release()
        self.write_asset("MCP_CREO_MechDog-9.9.9-extra.zip", b"extra")
        problems = check_release_assets.validate_directory(self.directory, self.version)
        self.assertIn("unexpected release asset: MCP_CREO_MechDog-9.9.9-extra.zip", problems)

    def test_sidecar_with_two_lines_is_rejected(self):
        self.publish_complete_release()
        digest = hashlib.sha256(b"source").hexdigest()
        (self.directory / self.source_sidecar).write_text(
            f"{digest}  {self.source}\n{digest}  {self.source}\n", encoding="ascii"
        )
        problems = check_release_assets.validate_directory(self.directory, self.version)
        self.assertTrue(any("exactly one non-empty line" in problem for problem in problems))

    def test_cli_reports_failure_when_a_sidecar_is_missing(self):
        self.publish_complete_release()
        (self.directory / self.seed_sidecar).unlink()
        code = check_release_assets.main(
            ["--tag", f"v{self.version}", "--dir", str(self.directory)]
        )
        self.assertEqual(code, 1)

    def test_cli_reports_success_for_a_complete_release(self):
        self.publish_complete_release()
        code = check_release_assets.main(
            ["--tag", f"v{self.version}", "--dir", str(self.directory)]
        )
        self.assertEqual(code, 0)

    def test_cli_local_success_says_local_verified(self):
        self.publish_complete_release()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = check_release_assets.main(
                ["--tag", f"v{self.version}", "--dir", str(self.directory)]
            )
        self.assertEqual(code, 0)
        self.assertIn("local_verified", output.getvalue())
        self.assertNotIn("downloaded", output.getvalue())

    def test_directory_with_a_stray_temporary_file_is_rejected(self):
        self.publish_complete_release()
        (self.directory / "upload.tmp").write_bytes(b"leftover")
        problems = check_release_assets.validate_directory(self.directory, self.version)
        self.assertIn("unexpected release asset: upload.tmp", problems)

    def test_four_paths_in_different_directories_are_accepted(self):
        paths = []
        for index, name in enumerate(
            (self.source, self.source_sidecar, self.seed, self.seed_sidecar)
        ):
            directory = self.directory / f"asset-{index}"
            directory.mkdir()
            payload = b"source" if index < 2 else b"seed"
            target = self.source if index < 2 else self.seed
            path = directory / name
            if name.endswith(".sha256"):
                path.write_bytes(
                    f"{hashlib.sha256(payload).hexdigest()}  {target}\n".encode("ascii")
                )
            else:
                path.write_bytes(payload)
            paths.append(path)
        self.assertEqual(release_integrity.validate_asset_paths(paths, self.version), [])

    def test_four_paths_in_different_directories_report_a_stray_file(self):
        paths = []
        for index, name in enumerate(
            (self.source, self.source_sidecar, self.seed, self.seed_sidecar)
        ):
            directory = self.directory / f"asset-{index}"
            directory.mkdir()
            payload = b"source" if index < 2 else b"seed"
            target = self.source if index < 2 else self.seed
            path = directory / name
            if name.endswith(".sha256"):
                path.write_bytes(
                    f"{hashlib.sha256(payload).hexdigest()}  {target}\n".encode("ascii")
                )
            else:
                path.write_bytes(payload)
            paths.append(path)
        stray = self.directory / "asset-0" / "notes.txt"
        stray.write_bytes(b"stray")
        problems = release_integrity.validate_asset_paths([*paths, stray], self.version)
        self.assertEqual(problems, ["unexpected release asset: notes.txt"])

    def test_validate_asset_paths_rejects_a_different_version(self):
        self.publish_complete_release()
        paths = [self.directory / name for name in (self.source, self.source_sidecar)]
        paths += [self.directory / name for name in (self.seed, self.seed_sidecar)]
        problems = release_integrity.validate_asset_paths(paths, "9.9.8")
        for name in check_release_assets.expected_assets("9.9.8"):
            self.assertIn(f"missing release asset: {name}", problems)
        for name in check_release_assets.expected_assets(self.version):
            self.assertIn(f"unexpected release asset: {name}", problems)

    def test_generated_sidecar_is_ascii_with_lf_endings(self):
        sidecar = self.directory / self.source_sidecar
        digest = hashlib.sha256(b"source").hexdigest()
        release_integrity.write_sidecar(sidecar, digest, self.source)
        payload = sidecar.read_bytes()
        self.assertNotIn(b"\r", payload)
        self.assertTrue(payload.endswith(b"\n"))
        self.assertEqual(payload, f"{digest}  {self.source}\n".encode("ascii"))

    def test_legacy_crlf_sidecar_is_still_accepted(self):
        for name, payload in ((self.source, b"source"), (self.seed, b"seed")):
            (self.directory / name).write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            (self.directory / f"{name}.sha256").write_bytes(f"{digest}  {name}\r\n".encode("ascii"))
        self.assertEqual(check_release_assets.validate_directory(self.directory, self.version), [])


class ReleaseAssetFallbackTests(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = check_release_assets.main(argv)
        return code, output.getvalue(), error.getvalue()

    def test_missing_gh_suggests_the_dir_fallback(self):
        with (
            patch.object(
                release_download.subprocess,
                "run",
                side_effect=FileNotFoundError(2, "not found", "gh"),
            ),
            patch.object(release_download, "urlopen", side_effect=OSError("API unavailable")),
        ):
            code, output, error = self.run_cli(["--tag", "v9.9.9"])
        self.assertNotEqual(code, 0)
        self.assertIn("gh release download failed", error)
        self.assertIn("GitHub API fallback failed", error)
        self.assertIn("--dir", error)
        self.assertIn("v9.9.9", error)
        self.assertNotIn("local_verified", output)

    def test_failed_download_suggests_the_dir_fallback(self):
        failure = SimpleNamespace(returncode=1, stdout="", stderr="release not found")
        with (
            patch.object(release_download.subprocess, "run", return_value=failure),
            patch.object(release_download, "urlopen", side_effect=OSError("API unavailable")),
        ):
            code, output, error = self.run_cli(["--tag", "v9.9.9"])
        self.assertNotEqual(code, 0)
        self.assertIn("gh release download failed for v9.9.9", error)
        self.assertIn("--dir", error)
        self.assertNotIn("local_verified", output)

    def test_malformed_api_release_keeps_both_errors_and_dir_hint(self):
        for payload in ([], None, 7, "invalid"):
            with self.subTest(payload=payload):
                with (
                    patch.object(
                        release_download.subprocess,
                        "run",
                        side_effect=FileNotFoundError("gh"),
                    ),
                    patch.object(
                        release_download,
                        "urlopen",
                        return_value=io.BytesIO(json.dumps(payload).encode()),
                    ),
                ):
                    code, output, error = self.run_cli(["--tag", "v9.9.9"])
                self.assertEqual(code, 2)
                self.assertIn("gh release download failed", error)
                self.assertIn(
                    "GitHub API fallback failed: GitHub API returned an invalid release object",
                    error,
                )
                self.assertIn("--dir", error)
                self.assertNotIn("local_verified", output)

    def test_copy_permission_error_reports_dir_hint(self):
        with (
            patch.object(
                release_download.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0, stderr="", stdout=""),
            ),
            patch.object(release_download, "_check"),
            patch.object(
                release_download.shutil, "copy2", side_effect=PermissionError("read only")
            ),
        ):
            code, _, error = self.run_cli(["--tag", "v9.9.9"])
        self.assertEqual(code, 2)
        self.assertIn("read only", error)
        self.assertIn("--dir", error)


class SourcePackageAssetGateTests(unittest.TestCase):
    """DEV-070: the source packager gates the four real output paths."""

    def setUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.version = "9.9.9"
        self.root = self.temp / "source"
        self.root.mkdir()
        (self.root / "version.py").write_text(f'VERSION = "{self.version}"\n', encoding="utf-8")
        self.seed = self.temp / f"MCP_CREO_MechDog-{self.version}-seed-library.zip"
        self.seed.write_bytes(b"seed")
        self.output = self.temp / f"MCP_CREO_MechDog-{self.version}-source.zip"
        self.summary = {
            "seed_archive": str(self.seed),
            "seed_count": 9,
            "seed_archive_sha256": hashlib.sha256(b"seed").hexdigest(),
        }

    @property
    def seed_sidecar(self) -> Path:
        return self.seed.with_suffix(".zip.sha256")

    def run_package(self) -> tuple[int, str, str]:
        output, error = io.StringIO(), io.StringIO()
        with (
            patch.object(package, "VERSION", self.version),
            patch.object(package, "ROOT", self.root),
            patch.object(package, "source_files", lambda: [self.root / "version.py"]),
            patch.object(package, "validate_release_inputs", lambda root, seed: self.summary),
            patch.object(
                sys,
                "argv",
                [
                    "package.py",
                    "--seed-archive",
                    str(self.seed),
                    "--output",
                    str(self.output),
                ],
            ),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(error),
        ):
            code = package.main()
        return code, output.getvalue(), error.getvalue()

    def test_complete_four_assets_pass_the_gate(self):
        release_integrity.write_sidecar(
            self.seed_sidecar, hashlib.sha256(b"seed").hexdigest(), self.seed.name
        )
        code, output, error = self.run_package()
        self.assertEqual(code, 0, error)
        self.assertTrue(self.output.is_file())
        self.assertNotIn(b"\r", self.output.with_suffix(".zip.sha256").read_bytes())
        self.assertIn("Release asset gate: four assets present", output)

    def test_missing_seed_sidecar_fails_packaging(self):
        code, _, error = self.run_package()
        self.assertNotEqual(code, 0)
        self.assertIn("missing seed checksum sidecar", error)
        self.assertIn("tools/package_seeds.py", error)
        self.assertFalse(self.seed_sidecar.exists())

    def test_mismatched_seed_sidecar_fails_packaging(self):
        self.seed_sidecar.write_bytes(f"{'0' * 64}  {self.seed.name}\n".encode("ascii"))
        code, _, error = self.run_package()
        self.assertNotEqual(code, 0)
        self.assertIn("differs from", error)


if __name__ == "__main__":
    unittest.main()
