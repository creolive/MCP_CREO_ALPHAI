"""BUG-080/FEAT-045 offline C++ unit-scale/normalization check with installed
SDK declarations.

Links substituted unit/conversion queries instead of Toolkit libraries. Does
not connect Creo, create models, or establish physical modeling evidence.
Run from the editable installation:
.venv\\Scripts\\python.exe tools\\test_assembly_units.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from creo_mechdog.build_support import compiler_setup_script, validate_local_path
from creo_mechdog.paths import SOURCE_PATHS


def main() -> int:
    root = SOURCE_PATHS.resource_root
    settings = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
    sdk = Path(settings["creo_root"]) / "Common Files/protoolkit/includes"
    directory = root / "build/assembly_units_test"
    directory.mkdir(parents=True, exist_ok=True)
    source = root / "tests/native/test_assembly_units.cpp"
    executable = directory / "assembly_units_test.exe"
    for path in (sdk, directory, root / "native", source):
        validate_local_path(str(path), "assembly unit test path")
    batch = directory / "build.cmd"
    batch.write_text(
        "@echo off\n"
        + compiler_setup_script(settings)
        + f'\ncl /nologo /std:c++17 /EHsc /W3 /I "{sdk}" /I "{root / "native"}" '
        + f'/Fo:"{directory / "assembly_units_test.obj"}" /Fe:"{executable}" "{source}"\n'
        + "exit /b %errorlevel%\n",
        encoding="utf-8",
    )
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
        "sdk_header_sha256": hashlib.sha256((sdk / "ProMdlUnits.h").read_bytes()).hexdigest(),
        "source_sha256": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                source,
                root / "native/assembly_units.h",
                root / "native/inspection_units.h",
            )
        },
        "toolkit_calls": "substituted; no Creo connection",
        "success": False,
    }
    if built.returncode == 0:
        result = subprocess.run(
            [str(executable)], capture_output=True, timeout=10, creationflags=flags
        )
        report.update(
            exit_code=result.returncode,
            stdout=result.stdout.decode("utf-8", errors="replace"),
            stderr=result.stderr.decode("utf-8", errors="replace"),
            success=result.returncode == 0,
        )
    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
