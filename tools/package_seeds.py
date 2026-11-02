"""Build the versioned MIT seed ZIP from the public source allowlist."""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from creo_mechdog.release_integrity import (
    TRUSTED_RECORD,
    assert_repo_record_matches,
    read_version,
    seed_library_files,
)
from creo_mechdog.seed_distribution import seed_file_bytes
from version import VERSION


def build_seed_archive(root: Path, archive: Path) -> str:
    """Build the seed archive of the source tree at ``root``; return its SHA256."""
    root = Path(root)
    library = root / "seed_library"
    manifest = json.loads((library / "seed_manifest.json").read_text(encoding="utf-8"))
    if manifest != json.loads((root / "docs/seed_manifest.json").read_text(encoding="utf-8")):
        raise ValueError("Seed manifests differ: seed_library and docs")
    if manifest["compatible_server_version"] != read_version(root):
        raise ValueError("Seed manifest version differs from version.py")
    if seed_file_bytes(library / "LICENSE") != seed_file_bytes(root / "LICENSE"):
        raise ValueError("Seed library must retain the project MIT license")
    files = seed_library_files(root)
    for entry in manifest["seeds"]:
        path = (library / entry["relative_path"]).resolve()
        if not path.is_relative_to(library.resolve()):
            raise ValueError(f"Seed manifest path escapes the library: {entry['relative_path']}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Seed file differs from the published SHA256: {entry['name']}")
    prefix = f"MCP_CREO_MechDog-{read_version(root)}-seed-library/"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for path in files:
            entry = zipfile.ZipInfo(
                prefix + path.relative_to(library).as_posix(), (1980, 1, 1, 0, 0, 0)
            )
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            output.writestr(entry, seed_file_bytes(path))
    return hashlib.sha256(archive.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="New archive path; existing files are never overwritten"
    )
    parser.add_argument(
        "--allow-record-mismatch",
        action="store_true",
        help=(
            "Keep the built archive but skip the repository record check; only for preparing a "
            "backfill. Never use it to publish."
        ),
    )
    args = parser.parse_args(argv)
    archive = (
        args.output or ROOT.parent / f"MCP_CREO_MechDog-{VERSION}-seed-library.zip"
    ).resolve()
    if archive.exists():
        raise ValueError("Archive already exists; choose a new output path")
    digest = build_seed_archive(ROOT, archive)
    manifest = json.loads((ROOT / "seed_library/seed_manifest.json").read_text(encoding="utf-8"))
    print(
        f"Seed archive: {archive}; {len(seed_library_files(ROOT))} files; "
        f"{len(manifest['seeds'])} seeds; SHA256 {digest}"
    )
    if args.allow_record_mismatch:
        print(
            f"WARNING: {TRUSTED_RECORD} was not checked (--allow-record-mismatch). "
            "Backfill the digest and rebuild before packaging."
        )
        return 0
    try:
        assert_repo_record_matches(ROOT, archive)
    except ValueError as error:
        print(f"ERROR: {error}")
        print(
            f"The archive was kept at {archive} so the digest can be backfilled into "
            f"{TRUSTED_RECORD}; nothing was published."
        )
        return 2
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(f"{TRUSTED_RECORD} matches this rebuild; safe to package the source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
