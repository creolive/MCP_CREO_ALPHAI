"""Compile the actual missing-header branch; never link or call Toolkit."""

import json
import os
import subprocess
import unittest
from pathlib import Path

from creo_mechdog.build_support import compiler_setup_script

ROOT = Path(__file__).resolve().parents[2]


class OptionalLoftHeaderTests(unittest.TestCase):
    def test_missing_header_branch_compiles_and_refuses_the_operation(self):
        config = ROOT / "config.json"
        if os.name != "nt" or not config.is_file():
            self.skipTest("local Windows compiler configuration not available")
        settings = json.loads(config.read_text(encoding="utf-8-sig"))
        directory = ROOT / "build/optional_loft_header_test"
        directory.mkdir(parents=True, exist_ok=True)
        exe = directory / "header_gate.exe"
        source = ROOT / "tests/native/test_surface_loft_header_gate.cpp"
        batch = directory / "build.cmd"
        batch.write_text(
            "@echo off\n"
            + compiler_setup_script(settings)
            + f'\ncl /nologo /std:c++17 /EHsc /W3 /I "{ROOT / "native"}" '
            + f'/Fo:"{directory / "header_gate.obj"}" /Fe:"{exe}" "{source}"\n'
            + "exit /b %errorlevel%\n",
            encoding="utf-8",
        )
        built = subprocess.run(
            ["cmd.exe", "/d", "/c", str(batch)],
            cwd=directory,
            capture_output=True,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        (directory / "build.log").write_bytes(built.stdout + built.stderr)
        self.assertEqual(
            built.returncode, 0, (built.stdout + built.stderr).decode(errors="replace")[-4000:]
        )
        result = subprocess.run(
            [str(exe)], capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn(b"SURFACE_LOFT_SDK_UNAVAILABLE", result.stdout)

    def test_optional_include_is_gated_in_the_handwritten_source(self):
        text = (ROOT / "native/surface_loft.cpp").read_text(encoding="utf-8")
        self.assertLess(
            text.index("#if MECHDOG_HAS_PROBBL_HEADER"), text.index("#include <Probbl.h>")
        )
