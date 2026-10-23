"""Portable, hash-checked discovery of the project's MIT native Blend seeds."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
import zipfile
from pathlib import Path, PurePosixPath

import bridge
from creo_mechdog.seed_compatibility import metadata
from creo_mechdog.seed_distribution import seed_file_bytes

REGISTRY_NAME = "seed_registry.json"


def manifest() -> dict:
    return bridge.read_json(bridge.ROOT / "docs/seed_manifest.json")


def library_directories() -> list[Path]:
    roots = [bridge.ROOT / "seed_library"]
    config_file = bridge.ROOT / "config.json"
    configured = (
        bridge.read_json(config_file).get("seed_library_directory")
        if config_file.is_file()
        else None
    )
    if configured:
        roots.insert(0, Path(configured).expanduser())
    registry = bridge.ROOT / REGISTRY_NAME
    if registry.is_file():
        roots.extend(Path(p) for p in bridge.read_json(registry).get("directories", []))
    result = []
    for root in roots:
        if not root.is_absolute():
            root = bridge.ROOT / root
        root = root.resolve()
        if root not in result:
            result.append(root)
    return result


def _checked_seed(root: Path, entry: dict) -> dict:
    relative = PurePosixPath(entry["relative_path"])
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not re.fullmatch(r"[A-Za-z0-9_]{1,31}\.prt(?:\.\d+)?", relative.name, re.I)
    ):
        raise ValueError("Invalid relative path in seed manifest")
    path = root.joinpath(*relative.parts).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Seed path escapes its library directory")
    result = {
        **entry,
        **metadata(entry),
        "seed_file": str(path),
        "seed_feature_id": entry["seed_feature_id"],
        "required_section_count": entry["section_count"],
        "available": False,
    }
    if not path.is_file():
        result["reason"] = (
            "Seed file is missing; install the packaged seed_library or register its directory"
        )
        return result
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    result["actual_sha256"] = digest
    result["available"] = digest == entry["sha256"]
    result["reason"] = (
        "Hash matches the verified seed manifest"
        if result["available"]
        else "Seed SHA256 mismatch; the saved native ID is not trusted"
    )
    return result


def list_seeds() -> dict:
    entries = []
    roots = library_directories()
    for entry in manifest()["seeds"]:
        candidates = [_checked_seed(root, entry) for root in roots]
        entries.append(next((row for row in candidates if row["available"]), candidates[0]))
    return {
        "seeds": entries,
        "available_count": sum(s["available"] for s in entries),
        "library_directories": [str(p) for p in roots],
        "validation": "SHA256 and published metadata; native type/count/mode are checked during creation",
    }


def select_seed(section_count: int, interpolation: str, seed_name: str | None = None) -> dict:
    candidates = list_seeds()["seeds"]
    matching = [
        s
        for s in candidates
        if s["section_count"] == section_count
        and s["interpolation"] == interpolation
        and (seed_name is None or s["name"] == seed_name)
    ]
    available = next((s for s in matching if s["available"]), None)
    if available is None:
        supported = ", ".join(
            f"{s['name']} ({s['section_count']}/{s['interpolation']}, available={s['available']})"
            for s in candidates
        )
        raise ValueError(
            f"No verified local seed matches {section_count} sections/{interpolation}. Installed choices: {supported}. Use creo_install_seed_library or supply an explicit compatible seed."
        )
    return available


def validate_seed(seed_name: str) -> dict:
    selected = next((s for s in list_seeds()["seeds"] if s["name"] == seed_name), None)
    if selected is None:
        raise ValueError("Unknown seed_name; call creo_list_seeds")
    return {
        **selected,
        "native_validation": "Performed on an isolated owned copy when creo_new_loft_part creates the model",
    }


def install_seed_library(directory: str | None = None, archive_file: str | None = None) -> dict:
    """Register a checked directory, or safely install the matching current-version nine-seed ZIP."""
    if directory and archive_file:
        raise ValueError("Specify directory or archive_file, not both")
    destination = bridge.ROOT / "seed_library"
    if archive_file:
        source = Path(archive_file).expanduser()
        if not source.is_absolute() or not source.is_file():
            raise ValueError("archive_file must be an existing absolute local ZIP path")
        # Accept only the published library, not arbitrary executable ZIP contents.
        expected_digest = "77f099533a5e27914c619021fa00ed7f5a3339112982f7b46c2a22c998c599a8"
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected_digest:
            raise ValueError("Archive SHA256 differs from the published MIT seed library")
        if destination.exists():
            raise ValueError(
                "seed_library already exists; register/validate it instead of overwriting"
            )
        temporary = bridge.ROOT / ".tmp" / ("seed_install_" + uuid.uuid4().hex)
        temporary.mkdir(parents=True)
        with zipfile.ZipFile(source) as archive:
            if archive.testzip() is not None:
                raise ValueError("Seed ZIP CRC check failed")
            for member in archive.infolist():
                if member.is_dir():
                    continue
                parts = PurePosixPath(member.filename)
                if (
                    parts.is_absolute()
                    or ".." in parts.parts
                    or len(parts.parts) < 2
                    or "\\" in member.filename
                ):
                    raise ValueError("Unsafe seed ZIP path")
                target = temporary.joinpath(*parts.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
        _validate_library(temporary)
        temporary.rename(destination)
        directory = str(destination)
    root = Path(directory).expanduser() if directory else destination
    if not root.is_absolute() or not root.is_dir():
        raise ValueError(
            "Seed library directory must be an existing absolute path containing seed_manifest.json"
        )
    root = root.resolve()
    _validate_library(root)
    registry_path = bridge.ROOT / REGISTRY_NAME
    registry = bridge.read_json(registry_path) if registry_path.is_file() else {"directories": []}
    directories = registry.setdefault("directories", [])
    if str(root) not in directories:
        directories.append(str(root))
        bridge.write_json(registry_path, registry)
    return {"installed": True, "directory": str(root), **list_seeds()}


def _validate_library(root: Path) -> None:
    if bridge.read_json(root / "seed_manifest.json") != manifest():
        raise ValueError("Library manifest differs from the published compatible seed manifest")
    if seed_file_bytes(root / "LICENSE") != seed_file_bytes(bridge.ROOT / "LICENSE"):
        raise ValueError("Seed library must retain the project MIT license")
    if not all(_checked_seed(root, entry)["available"] for entry in manifest()["seeds"]):
        raise ValueError("One or more seed files are missing or fail SHA256 validation")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--archive-file")
    parser.add_argument("--directory")
    args = parser.parse_args()
    result = (
        install_seed_library(args.directory, args.archive_file) if args.install else list_seeds()
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
