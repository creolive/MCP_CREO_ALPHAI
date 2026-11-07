"""Source evidence for offline development drivers, including extracted releases."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Iterable


def local_provenance(root: Path, extra_names: Iterable[str] = ()) -> dict[str, Any]:
    """Hash distributed source without inventing a Git identity when unavailable."""
    from version import VERSION

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout.strip()

    try:
        if Path(git("rev-parse", "--show-toplevel")).resolve() != root.resolve():
            raise ValueError("source directory is not the Git root")
        names = set(
            git("ls-files", "--", "*.py", "native/*.h", "native/*.hpp", "native/*.cpp").splitlines()
        )
        commit = git("rev-parse", "HEAD")
        branch = git("branch", "--show-current")
        dirty = bool(git("status", "--porcelain"))
        git_status = "available"
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        names = {
            path.relative_to(root).as_posix()
            for directory in (root / "src", root / "native", root / "tools", root / "tests")
            if directory.is_dir()
            for path in directory.rglob("*")
            if path.is_file()
            and (
                path.suffix == ".py"
                or directory.name == "native"
                and path.suffix in {".h", ".hpp", ".cpp"}
            )
            and not any(part in {"__pycache__", ".venv", "build"} for part in path.parts)
        }
        names.update(path.name for path in root.glob("*.py"))
        commit = branch = dirty = None
        git_status = "unavailable"
    names.update(extra_names)
    hashes = {
        name: hashlib.sha256((root / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in sorted(names)
    }
    return {
        "version": VERSION,
        "commit": commit,
        "branch": branch,
        "dirty": dirty,
        "git_status": git_status,
        "source_sha256": hashes,
        "source_fingerprint": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "auto_start_creo": False,
        "human_session_confirmation": True,
    }
