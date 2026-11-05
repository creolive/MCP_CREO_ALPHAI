"""DEV-045/C01: a release must publish both ZIPs and both SHA256 sidecars."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from tools import check_release_assets


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


if __name__ == "__main__":
    unittest.main()
