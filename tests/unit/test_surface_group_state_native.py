"""Execute production group-state logic with measured-value stand-ins, no SDK."""

import json
import os
import subprocess
import unittest
from pathlib import Path

from creo_mechdog.build_support import compiler_setup_script

ROOT = Path(__file__).resolve().parents[2]


class SurfaceGroupStateNative(unittest.TestCase):
    def test_loft_metadata_distinguishes_registration_from_sdk_availability(self):
        from creo_mechdog.capabilities import families

        loft = families()["surface_loft"]
        self.assertEqual(loft["availability"], "sdk_conditional")
        self.assertEqual(loft["sdk_requirements"], ["Probbl.h"])
        self.assertIn("not verification", loft["enabled_semantics"])

    def test_actual_decision_function_keeps_state_and_reason_consistent(self):
        if os.name != "nt" or not (ROOT / "config.json").exists():
            self.skipTest("local Windows compiler configuration not available")
        source = (ROOT / "native/surface_group.cpp").read_text(encoding="utf-8")
        start = source.index("static void group_state_decide(")
        end = source.index("// Project the measurement", start)
        directory = ROOT / "build/surface_group_state_test"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "group_state_under_test.inc").write_text(source[start:end], encoding="utf-8")
        settings = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
        exe = directory / "state.exe"
        batch = directory / "build.cmd"
        batch.write_text(
            "@echo off\n"
            + compiler_setup_script(settings)
            + f'\ncl /nologo /std:c++17 /EHsc /I "{directory}" '
            + f'/Fo:"{directory / "state.obj"}" /Fe:"{exe}" '
            + f'"{ROOT / "tests/native/test_surface_group_state.cpp"}"\nexit /b %errorlevel%\n',
            encoding="utf-8",
        )
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(batch)],
            cwd=directory,
            capture_output=True,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(
            result.returncode, 0, (result.stdout + result.stderr).decode(errors="replace")
        )
        result = subprocess.run(
            [str(exe)], capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW
        )
        self.assertEqual(result.returncode, 0, "production state decision case failed")
