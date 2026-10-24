"""FEAT-012 offline production assembly-pose harness with the local C++ compiler.

Uses the production SDK-independent pose helper, without Toolkit libraries. Does
not connect Creo, create models, or establish physical modeling evidence.
Run from the editable installation:
.venv\\Scripts\\python.exe tools\\test_assembly_pose.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone

from creo_mechdog.build_support import compiler_setup_script, validate_local_path
from creo_mechdog.paths import SOURCE_PATHS


def main() -> int:
    root = SOURCE_PATHS.resource_root
    settings = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
    directory = root / "build/assembly_pose_test"
    directory.mkdir(parents=True, exist_ok=True)
    sources = {
        "assembly_pose_test": root / "tests/native/test_assembly_pose.cpp",
    }
    executables = {name: directory / f"{name}.exe" for name in sources}
    for path in (directory, root / "native", *sources.values()):
        validate_local_path(str(path), "assembly pose test path")
    lines = ["@echo off", compiler_setup_script(settings)]
    for name, source in sources.items():
        lines.append(
            f'cl /nologo /std:c++17 /EHsc /W3 /I "{root / "native"}" '
            + f'/Fo:"{directory / (name + ".obj")}" /Fe:"{executables[name]}" "{source}"'
        )
        lines.append("if errorlevel 1 exit /b %errorlevel%")
    lines.append("exit /b 0")
    batch = directory / "build.cmd"
    batch.write_text("\n".join(lines) + "\n", encoding="utf-8")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (directory / "build.log").open("wb") as log:
        built = subprocess.run(
            ["cmd.exe", "/d", "/c", str(batch)],
            cwd=directory,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=120,
            creationflags=flags,
        )
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "build_exit_code": built.returncode,
        "compiler_setup": settings["vcvars64"],
        "source_sha256": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                *sources.values(),
                root / "native/assembly_pose.h",
                root / "native/third_party/json.hpp",
            )
        },
        "toolkit_calls": "none; production math only; no Creo connection",
        "success": False,
    }
    if built.returncode == 0:
        runs = {}
        success = True
        for name, executable in executables.items():
            result = subprocess.run(
                [str(executable)], capture_output=True, timeout=10, creationflags=flags
            )
            runs[name] = {
                "exit_code": result.returncode,
                "stdout": result.stdout.decode("utf-8", errors="replace"),
                "stderr": result.stderr.decode("utf-8", errors="replace"),
            }
            success = success and result.returncode == 0
        report.update(runs=runs, success=success)
    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
