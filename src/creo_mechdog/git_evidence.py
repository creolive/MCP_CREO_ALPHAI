"""Source provenance that also works in an official archive without ``.git/``.

The release ``source.zip`` ships no repository metadata, and an installation
machine may have no ``git`` executable. Evidence drivers must still write a
report there, so git is treated as an optional source: when it is unavailable
the file list comes from a filesystem walk and the commit facts are reported as
unknown instead of aborting the run.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

DEFAULT_PATTERNS = ("*.py", "native/*.h", "native/*.hpp", "native/*.cpp")
NATIVE_PATTERNS = ("native/*.h", "native/*.hpp", "native/*.cpp")
PACKAGE_DIRS = ("src", "tools", "tests")


def git_output(root: Path, *args: str, timeout: float = 15) -> str | None:
    """Return stripped git stdout, or ``None`` when git or the repository is missing."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def source_paths(root: Path, patterns: tuple[str, ...] = DEFAULT_PATTERNS) -> tuple[list[str], str]:
    """Return source file names and the mode (``git`` or ``filesystem``) that found them."""
    tracked = git_output(root, "ls-files", "--", *patterns)
    if tracked is not None:
        return sorted(tracked.splitlines()), "git"
    names = {
        path.relative_to(root).as_posix()
        for pattern in NATIVE_PATTERNS
        for path in root.glob(pattern)
    }
    names.update(path.relative_to(root).as_posix() for path in root.glob("*.py"))
    for directory in PACKAGE_DIRS:
        base = root / directory
        if base.is_dir():
            names.update(path.relative_to(root).as_posix() for path in base.rglob("*.py"))
    return sorted(names), "filesystem"


def git_facts(root: Path) -> dict:
    """Return commit/branch/dirty facts with explicit unavailability markers."""
    commit = git_output(root, "rev-parse", "HEAD")
    status = git_output(root, "status", "--porcelain")
    if commit is None or status is None:
        return {
            "commit": "",
            "branch": "",
            "dirty": None,
            "provenance_mode": "filesystem",
            "git_unavailable": True,
        }
    return {
        "commit": commit,
        "branch": git_output(root, "branch", "--show-current") or "",
        "dirty": bool(status),
        "provenance_mode": "git",
        "git_unavailable": False,
    }
