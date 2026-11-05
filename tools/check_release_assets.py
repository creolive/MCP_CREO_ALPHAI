"""Check that a GitHub Release carries both ZIPs and both SHA256 sidecars.

DEV-045/C01: 0.11.7 and 0.12.0 shipped only the two ZIPs, so upgrade users had no
sidecar to verify. ``tools/package.py`` and ``tools/package_seeds.py`` already write
``<zip>.sha256``; this gate checks the remote Release instead of regenerating them.
"""

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

NAME = "MCP_CREO_MechDog"
HEX = set("0123456789abcdefABCDEF")


def expected_assets(version: str) -> list[str]:
    """Return the four asset names a release of ``version`` must publish."""
    source = f"{NAME}-{version}-source.zip"
    seed = f"{NAME}-{version}-seed-library.zip"
    return [source, f"{source}.sha256", seed, f"{seed}.sha256"]


def read_sidecar(path: Path) -> tuple[str, str]:
    """Return ``(digest, zip_name)`` from a one-line ``sha256sum`` style sidecar."""
    try:
        text = path.read_text(encoding="ascii")
    except UnicodeDecodeError as error:
        raise ValueError(f"{path.name}: sidecar is not ASCII text ({error.reason})") from None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError(f"{path.name}: sidecar must contain exactly one non-empty line")
    parts = lines[0].split()
    if len(parts) != 2:
        raise ValueError(f"{path.name}: expected '<64-hex SHA256>  <file name>'")
    digest, target = parts
    if len(digest) != 64 or not set(digest) <= HEX:
        raise ValueError(f"{path.name}: sidecar digest is not a 64-character SHA256")
    return digest.lower(), target


def validate_directory(directory: Path, version: str) -> list[str]:
    """Return every problem that makes ``directory`` unusable as release assets."""
    expected = expected_assets(version)
    present = (
        {path.name for path in directory.iterdir() if path.is_file()}
        if directory.is_dir()
        else set()
    )
    problems = [f"missing release asset: {name}" for name in expected if name not in present]
    problems.extend(f"unexpected release asset: {name}" for name in sorted(present - set(expected)))
    for name in expected:
        if not name.endswith(".sha256") or name not in present:
            continue
        zip_name = name[: -len(".sha256")]
        if zip_name not in present:
            continue
        try:
            digest, target = read_sidecar(directory / name)
        except ValueError as error:
            problems.append(str(error))
            continue
        if target != zip_name:
            problems.append(f"{name}: sidecar names {target}, expected {zip_name}")
        actual = hashlib.sha256((directory / zip_name).read_bytes()).hexdigest()
        if actual != digest:
            problems.append(f"{name}: sidecar {digest} differs from {zip_name} {actual}")
    return problems


def download(tag: str, directory: Path) -> None:
    result = subprocess.run(
        ["gh", "release", "download", tag, "--dir", str(directory), "--clobber"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"gh release download failed for {tag}: {result.stderr.strip()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Release tag, for example v0.12.0")
    parser.add_argument(
        "--version",
        help="Release version; defaults to the tag without a leading 'v'",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        help="Verify an existing download directory instead of calling gh",
    )
    args = parser.parse_args(argv)
    version = args.version or args.tag.removeprefix("v")
    if args.dir:
        problems = validate_directory(args.dir.resolve(), version)
    else:
        with tempfile.TemporaryDirectory() as temp:
            download(args.tag, Path(temp))
            problems = validate_directory(Path(temp), version)
    if problems:
        print(f"{args.tag}: release assets are incomplete or inconsistent", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"{args.tag}: four assets present; both sidecars match their ZIP digests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
