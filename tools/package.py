"""Build the public MIT source release from an explicit allowlist."""

import argparse
import hashlib
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from creo_mechdog.release_integrity import (
    seed_library_files,
    validate_asset_paths,
    validate_release_inputs,
    write_sidecar,
)
from version import VERSION

NAME = "MCP_CREO_MechDog"


def source_files():
    names = (
        "README.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "server.py",
        "bridge.py",
        "creo_startup.py",
        "seeds.py",
        "airfoil.py",
        "profile_checks.py",
        "generic_bridge.py",
        "schema.py",
        "version.py",
        "capabilities.py",
        "config.example.json",
        "client-config.example.json",
        "requirements.txt",
        "requirements.lock.txt",
        "requirements-dev.txt",
        "setup.ps1",
        ".gitignore",
        ".gitattributes",
        "AGENTS.md",
        "pyproject.toml",
        ".clang-format",
        ".editorconfig",
        "tools/test_result_delivery.cpp",
        "tools/test_recovery_deadline.cpp",
        "docs/validation/DEV-028-WorkBuddy-report-20261016.txt",
        "docs/validation/track-feedback-2026-10-16/track-modeling-rev2.txt",
        "docs/validation/bug-001-repro-2026-10-16/g0_driver.py",
        "tools/test_callback_payload.cpp",
        "tests/native/test_assembly_pose.cpp",
        "tests/native/test_adoption_source.cpp",
        "tests/native/test_constraint_names.cpp",
        "tests/native/test_constraint_compare.cpp",
    )
    files = [ROOT / name for name in names]
    for directory, extensions in {
        "src/creo_mechdog": {".py"},
        "native": {".cpp", ".hpp", ".h"},
        "tools": {".py"},
        "tests": {".py"},
        "examples": {".json"},
        "docs": {".md", ".json"},
    }.items():
        files.extend(
            p
            for p in (ROOT / directory).rglob("*")
            if p.is_file() and p.suffix in extensions and "__pycache__" not in p.parts
        )
    files.append(ROOT / "native/third_party/LICENSE.nlohmann-json")
    files.extend(
        p
        for p in (ROOT / ".github").rglob("*")
        if p.is_file() and p.suffix in {".md", ".yml", ".yaml"}
    )
    files.extend(seed_library_files(ROOT))
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing source file or unexpected symlink: {path}")
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed-archive",
        type=Path,
        required=True,
        help="Seed library ZIP published with this release; its digest must match the "
        "trusted seed package record",
    )
    parser.add_argument(
        "--stage", type=Path, help="Also copy public files into a new empty upload directory"
    )
    parser.add_argument(
        "--output", type=Path, help="New ZIP path; refuses to overwrite an existing archive"
    )
    args = parser.parse_args()
    try:
        summary = validate_release_inputs(ROOT, args.seed_archive.resolve())
    except ValueError as error:
        print(f"Source package refused: {error}", file=sys.stderr)
        raise SystemExit(2) from None
    files = source_files()
    if args.stage:
        stage = args.stage.resolve()
        if stage == ROOT or ROOT in stage.parents or stage in ROOT.parents:
            raise ValueError("Upload directory must be separate from the working project")
        if stage.exists() and (not stage.is_dir() or any(stage.iterdir())):
            raise ValueError(
                "Upload directory must be new or empty; existing files are never deleted"
            )
        stage.mkdir(parents=True, exist_ok=True)
        for source in files:
            destination = stage / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    archive = args.output.resolve() if args.output else ROOT.parent / f"{NAME}-{VERSION}-source.zip"
    if args.output and archive.exists():
        raise ValueError("Explicit output archive already exists; choose a new path")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for source in files:
            output.write(source, f"{NAME}/" + source.relative_to(ROOT).as_posix())
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    sidecar = archive.with_suffix(".zip.sha256")
    write_sidecar(sidecar, checksum, archive.name)
    seed_archive = Path(summary["seed_archive"])
    seed_sidecar = seed_archive.with_suffix(".zip.sha256")
    print(f"Public source: {archive}; {len(files)} files; SHA256 {checksum}")
    print(
        f"Seed archive: {summary['seed_archive']}; "
        f"{summary['seed_count']} seeds; SHA256 {summary['seed_archive_sha256']}"
    )
    print("Release assets (upload all four; never a *.zip glob):")
    for path in (archive, sidecar, seed_archive, seed_sidecar):
        print(f"  {path}")
    if args.stage:
        print(f"GitHub upload directory: {args.stage.resolve()}")
    if not seed_sidecar.is_file():
        print(f"ERROR: missing seed checksum sidecar: {seed_sidecar}", file=sys.stderr)
        print(
            "Rebuild the seed archive first: python tools/package_seeds.py --output "
            f'"{seed_archive}"',
            file=sys.stderr,
        )
        return 2
    problems = validate_asset_paths([archive, sidecar, seed_archive, seed_sidecar], VERSION)
    if problems:
        print("Release asset gate rejected this package:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("Release asset gate: four assets present; both sidecars match their ZIP digests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
