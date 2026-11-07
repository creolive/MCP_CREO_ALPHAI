"""Download and verify the four assets of an exact GitHub Release tag."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from creo_mechdog.release_integrity import expected_assets, validate_directory

REPOSITORY = "wudahua/MCP_CREO_MechDog"
TIMEOUT_SECONDS = 30


def _version(tag: str) -> str:
    if not tag or tag in {".", ".."} or any(char in tag for char in "/\\\r\n"):
        raise RuntimeError(f"invalid release tag: {tag!r}")
    return tag.removeprefix("v")


def _check(directory: Path, version: str) -> None:
    problems = validate_directory(directory, version)
    if problems:
        raise RuntimeError("; ".join(problems))


def _download_api(tag: str, directory: Path, repo: str, version: str) -> None:
    if repo != REPOSITORY:
        raise RuntimeError(f"unsupported release repository: {repo}")
    api_url = f"https://api.github.com/repos/{repo}/releases/tags/{quote(tag, safe='')}"
    request = Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MCP_CREO_MechDog-release-check",
        },
    )
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        release = json.load(response)
    if not isinstance(release, dict):
        raise RuntimeError("GitHub API returned an invalid release object")
    if release.get("tag_name") != tag:
        raise RuntimeError("GitHub API returned a different release tag")
    names = expected_assets(version)
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("GitHub API returned no asset list")
    found = {}
    for asset in assets:
        if not isinstance(asset, dict) or asset.get("name") not in names:
            raise RuntimeError(f"unexpected release asset: {asset!r}")
        name = asset["name"]
        if name in found:
            raise RuntimeError(f"duplicate release asset: {name}")
        found[name] = asset
    missing = set(names) - found.keys()
    if missing:
        raise RuntimeError(f"missing release assets: {', '.join(sorted(missing))}")
    for name in names:
        url = found[name].get("browser_download_url")
        parsed = urlparse(url) if isinstance(url, str) else None
        expected_path = f"/{repo}/releases/download/{quote(tag, safe='')}/{quote(name, safe='')}"
        if (
            not parsed
            or parsed.scheme != "https"
            or parsed.netloc != "github.com"
            or parsed.path != expected_path
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError(f"unsafe download address for {name}: {url!r}")
        request = Request(url, headers={"User-Agent": "MCP_CREO_MechDog-release-check"})
        with (
            urlopen(request, timeout=TIMEOUT_SECONDS) as response,
            (directory / name).open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
    _check(directory, version)


def _copy_verified_assets(stage: Path, directory: Path, version: str) -> None:
    """Copy verified files; a destination write failure may leave a partial set."""
    try:
        for name in expected_assets(version):
            shutil.copy2(stage / name, directory / name)
    except OSError as error:
        raise RuntimeError(f"could not copy verified release assets: {error}") from None


def download(tag: str, directory: Path, repo: str = REPOSITORY) -> None:
    """Prefer gh; use the official GitHub API if gh cannot supply a valid set."""
    version = _version(tag)
    if repo != REPOSITORY:
        raise RuntimeError(f"unsupported release repository: {repo}")
    directory = Path(directory)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise RuntimeError(f"could not prepare release directory: {error}") from None
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        try:
            result = subprocess.run(
                [
                    "gh",
                    "release",
                    "download",
                    tag,
                    "--repo",
                    repo,
                    "--dir",
                    str(stage),
                    "--clobber",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=TIMEOUT_SECONDS,
            )
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "no output")
            _check(stage, version)
        except (FileNotFoundError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            gh_error = f"gh release download failed for {tag}: {error}"
            with tempfile.TemporaryDirectory() as api_temp:
                stage = Path(api_temp)
                try:
                    _download_api(tag, stage, repo, version)
                except (OSError, ValueError, KeyError, TypeError, RuntimeError) as api_error:
                    raise RuntimeError(
                        f"{gh_error}; GitHub API fallback failed: {api_error}"
                    ) from None
                _copy_verified_assets(stage, directory, version)
            return
        _copy_verified_assets(stage, directory, version)
