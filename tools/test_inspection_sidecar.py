"""DEV-048 offline check of the shared inspection sidecar helper.

Compiles tests/native/test_inspection_sidecar.cpp with MSVC and runs it. The
helper uses plain file I/O and SHA256 only, so no Toolkit library is linked and
no Creo session is touched.
Run from the editable installation:
    .venv\\Scripts\\python.exe tools\\test_inspection_sidecar.py
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
    directory = root / "build/inspection_sidecar_test"
    directory.mkdir(parents=True, exist_ok=True)
    source = root / "tests/native/test_inspection_sidecar.cpp"
    executable = directory / "inspection_sidecar_test.exe"
    for path in (directory, root / "native", source):
        validate_local_path(str(path), "inspection sidecar test path")
    batch = directory / "build.cmd"
    batch.write_text(
        "@echo off\n"
        + compiler_setup_script(settings)
        + f'\ncl /nologo /std:c++17 /EHsc /W3 /I "{root / "native"}" '
        + f'/Fo:"{directory / "inspection_sidecar_test.obj"}" /Fe:"{executable}" "{source}"\n',
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
    sources = (
        source,
        root / "native/inspection_sidecar.h",
        root / "native/callback_identity.h",
        root / "native/third_party/json.hpp",
    )
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "build_exit_code": built.returncode,
        "source_sha256": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources
        },
        "toolkit_calls": "none; the helper is plain file I/O plus SHA256",
        "success": False,
    }
    if built.returncode == 0:
        result = subprocess.run(
            [str(executable)], capture_output=True, timeout=30, creationflags=flags
        )
        report.update(
            exit_code=result.returncode,
            stdout=result.stdout.decode("utf-8", errors="replace"),
            stderr=result.stderr.decode("utf-8", errors="replace"),
            success=result.returncode == 0,
        )
    else:
        report["build_log_tail"] = (directory / "build.log").read_text(
            encoding="utf-8", errors="replace"
        )[-4000:]
    (directory / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
