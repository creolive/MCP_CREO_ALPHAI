"""Check that a GitHub Release carries both ZIPs and both SHA256 sidecars.

DEV-045/C01: 0.11.7 and 0.12.0 shipped only the two ZIPs, so upgrade users had no
sidecar to verify. ``tools/package.py`` and ``tools/package_seeds.py`` already write
``<zip>.sha256``; this gate checks the remote Release instead of regenerating them.

DEV-070: the validation itself lives in ``creo_mechdog.release_integrity`` so the
source packager can gate the same four paths even when they live in two directories.
"""

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from creo_mechdog.release_download import download
from creo_mechdog.release_integrity import (
    expected_assets,
    read_sidecar,
    validate_asset_paths,
    validate_directory,
)

__all__ = [
    "download",
    "expected_assets",
    "main",
    "read_sidecar",
    "validate_asset_paths",
    "validate_directory",
]


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
        help="Verify an existing download directory instead of downloading the Release",
    )
    args = parser.parse_args(argv)
    version = args.version or args.tag.removeprefix("v")
    if args.dir:
        problems = validate_directory(args.dir.resolve(), version)
    else:
        with tempfile.TemporaryDirectory() as temp:
            try:
                download(args.tag, Path(temp))
            except (RuntimeError, OSError) as error:
                fallback = ROOT / "build/release-assets" / args.tag
                print(f"{args.tag}: {error}", file=sys.stderr)
                print("The remote Release was not checked.", file=sys.stderr)
                print(
                    "Download the four assets and both sidecars into one directory, then run:",
                    file=sys.stderr,
                )
                print(
                    f"  python tools/check_release_assets.py --tag {args.tag} "
                    f'--version {version} --dir "{fallback}"',
                    file=sys.stderr,
                )
                return 2
            problems = validate_directory(Path(temp), version)
    if problems:
        print(f"{args.tag}: release assets are incomplete or inconsistent", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    if args.dir:
        print(f"local_verified: four assets present; both sidecars match (version {version})")
    else:
        print(f"{args.tag}: four assets downloaded and verified; both sidecars match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
