"""Build the public MIT source release from an explicit allowlist."""

import argparse
import hashlib
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
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
    files.extend(
        p
        for p in (ROOT / "seed_library").rglob("*")
        if p.is_file()
        and (
            p.suffix in {".md", ".json", ".py"}
            or p.name == "LICENSE"
            or re.fullmatch(r"[A-Za-z0-9_]{1,31}\.prt\.\d+", p.name)
        )
    )
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing source file or unexpected symlink: {path}")
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", type=Path, help="Also copy public files into a new empty upload directory"
    )
    parser.add_argument(
        "--output", type=Path, help="New ZIP path; refuses to overwrite an existing archive"
    )
    args = parser.parse_args()
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
    archive.with_suffix(".zip.sha256").write_text(f"{checksum}  {archive.name}\n", encoding="ascii")
    print(f"Public source: {archive}; {len(files)} files; SHA256 {checksum}")
    if args.stage:
        print(f"GitHub upload directory: {args.stage.resolve()}")


if __name__ == "__main__":
    main()
