"""Compatibility names for the common offline source evidence collector."""

from fnmatch import fnmatchcase
from pathlib import Path

from .source_provenance import local_provenance
from .source_provenance import subprocess as subprocess

DEFAULT_PATTERNS = ("*.py", "native/*.h", "native/*.hpp", "native/*.cpp")


def source_paths(root: Path, patterns: tuple[str, ...] = DEFAULT_PATTERNS) -> tuple[list[str], str]:
    evidence = local_provenance(root)
    names = [
        name
        for name in evidence["source_sha256"]
        if any(fnmatchcase(name, pattern) for pattern in patterns)
    ]
    return names, "git" if evidence["git_status"] == "available" else "filesystem"


def git_facts(root: Path) -> dict:
    evidence = local_provenance(root)
    available = evidence["git_status"] == "available"
    return {
        "commit": evidence["commit"] or "",
        "branch": evidence["branch"] or "",
        "dirty": evidence["dirty"],
        "provenance_mode": "git" if available else "filesystem",
        "git_unavailable": not available,
    }
