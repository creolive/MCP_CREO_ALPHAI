"""Offline tests for the GitHub Release API download fallback."""

import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from creo_mechdog import release_download
from creo_mechdog.release_integrity import expected_assets, validate_directory


class ReleaseDownloadTests(unittest.TestCase):
    tag = "v9.9.9"
    version = "9.9.9"

    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.names = expected_assets(self.version)
        self.payloads = {}
        for name in self.names:
            if name.endswith(".sha256"):
                target = name.removesuffix(".sha256")
                self.payloads[name] = (
                    f"{hashlib.sha256(target.encode()).hexdigest()}  {target}\n".encode()
                )
            else:
                self.payloads[name] = name.encode()

    def release(self):
        return {
            "tag_name": self.tag,
            "assets": [
                {
                    "name": name,
                    "browser_download_url": f"https://github.com/{release_download.REPOSITORY}/releases/download/{self.tag}/{name}",
                }
                for name in self.names
            ],
        }

    def api(self, release=None, payloads=None):
        release = self.release() if release is None else release
        payloads = self.payloads if payloads is None else payloads

        def open_url(request, timeout):
            self.assertEqual(timeout, release_download.TIMEOUT_SECONDS)
            url = request.full_url
            if "api.github.com" in url:
                self.assertEqual(
                    url,
                    f"https://api.github.com/repos/{release_download.REPOSITORY}/releases/tags/{self.tag}",
                )
                return io.BytesIO(json.dumps(release).encode())
            return io.BytesIO(payloads[url.rsplit("/", 1)[-1]])

        return patch.object(release_download, "urlopen", side_effect=open_url)

    def test_missing_gh_uses_api_and_validates(self):
        with (
            patch.object(release_download.subprocess, "run", side_effect=FileNotFoundError("gh")),
            self.api(),
        ):
            release_download.download(self.tag, self.directory)
        self.assertEqual(validate_directory(self.directory, self.version), [])

    def test_complete_gh_skips_api(self):
        def complete(command, **kwargs):
            stage = Path(command[command.index("--dir") + 1])
            for name, payload in self.payloads.items():
                (stage / name).write_bytes(payload)
            return SimpleNamespace(returncode=0, stderr="", stdout="")

        with (
            patch.object(release_download.subprocess, "run", side_effect=complete),
            patch.object(release_download, "urlopen", side_effect=AssertionError("API called")),
        ):
            release_download.download(self.tag, self.directory)
        self.assertEqual(validate_directory(self.directory, self.version), [])

    def test_failed_gh_uses_api(self):
        result = SimpleNamespace(returncode=1, stderr="gh unavailable", stdout="")
        with patch.object(release_download.subprocess, "run", return_value=result), self.api():
            release_download.download(self.tag, self.directory)
        self.assertEqual(validate_directory(self.directory, self.version), [])

    def test_timed_out_gh_uses_api(self):
        with (
            patch.object(
                release_download.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("gh", release_download.TIMEOUT_SECONDS),
            ),
            self.api(),
        ):
            release_download.download(self.tag, self.directory)
        self.assertEqual(validate_directory(self.directory, self.version), [])

    def test_partial_gh_does_not_pollute_api_download(self):
        def partial(command, **kwargs):
            (Path(command[command.index("--dir") + 1]) / "stray.txt").write_text("partial")
            return SimpleNamespace(returncode=1, stderr="partial", stdout="")

        with patch.object(release_download.subprocess, "run", side_effect=partial), self.api():
            release_download.download(self.tag, self.directory)
        self.assertEqual(sorted(path.name for path in self.directory.iterdir()), sorted(self.names))

    def test_api_failure_retains_both_reasons(self):
        with (
            patch.object(release_download.subprocess, "run", side_effect=FileNotFoundError("gh")),
            patch.object(release_download, "urlopen", side_effect=OSError("offline")),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "gh release download failed.*GitHub API fallback failed: offline"
            ):
                release_download.download(self.tag, self.directory)

    def test_api_wrong_tag_fails(self):
        release = self.release()
        release["tag_name"] = "v9.9.8"
        with (
            patch.object(release_download.subprocess, "run", side_effect=FileNotFoundError("gh")),
            self.api(release),
        ):
            with self.assertRaisesRegex(RuntimeError, "different release tag"):
                release_download.download(self.tag, self.directory)

    def test_missing_or_duplicate_asset_fails(self):
        for assets in (self.release()["assets"][:-1], self.release()["assets"] * 2):
            with self.subTest(count=len(assets)):
                release = self.release()
                release["assets"] = assets
                with (
                    patch.object(
                        release_download.subprocess, "run", side_effect=FileNotFoundError("gh")
                    ),
                    self.api(release),
                ):
                    with self.assertRaises(RuntimeError):
                        release_download.download(self.tag, self.directory)
                self.assertEqual(list(self.directory.iterdir()), [])

    def test_extra_or_malformed_asset_fails(self):
        for extra in ({"name": "notes.txt", "browser_download_url": "https://github.com/"}, None):
            with self.subTest(extra=extra):
                release = self.release()
                release["assets"].append(extra)
                with (
                    patch.object(
                        release_download.subprocess, "run", side_effect=FileNotFoundError("gh")
                    ),
                    self.api(release),
                ):
                    with self.assertRaisesRegex(RuntimeError, "unexpected release asset"):
                        release_download.download(self.tag, self.directory)
                self.assertEqual(list(self.directory.iterdir()), [])

    def test_wrong_digest_fails_without_publishing(self):
        payloads = dict(self.payloads)
        payloads[self.names[1]] = f"{'0' * 64}  {self.names[0]}\n".encode()
        with (
            patch.object(release_download.subprocess, "run", side_effect=FileNotFoundError("gh")),
            self.api(payloads=payloads),
        ):
            with self.assertRaisesRegex(RuntimeError, "differs from"):
                release_download.download(self.tag, self.directory)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_unsafe_download_address_fails(self):
        release = self.release()
        release["assets"][0]["browser_download_url"] = "https://evil.example/file"
        with (
            patch.object(release_download.subprocess, "run", side_effect=FileNotFoundError("gh")),
            self.api(release),
        ):
            with self.assertRaisesRegex(RuntimeError, "unsafe download address"):
                release_download.download(self.tag, self.directory)
        self.assertEqual(list(self.directory.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
