"""BUG-086 regression: PowerShell 5.1 must not fail setup on redirected pip stderr."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import bridge

ROOT = Path(__file__).resolve().parents[2]

ORIGINAL_ERROR = "Could not find a version that satisfies the requirement fixture-missing"
PIP_EXIT_CODE = 3
FORMS = ("direct", "stderr_redirect", "merge")

FAKE_PIP = r"""
import os
import sys

step = "editable" if "--editable" in sys.argv else "requirements"
mode = os.environ.get("DEV049_FAKE_PIP_MODE", "notice")
failing = {"fail-requirements": "requirements", "fail-editable": "editable"}
sys.stderr.write("fixture pip step " + step + "\n")
sys.stderr.write("[notice] A new release of pip is available: 24.0 -> 25.2\n")
sys.stderr.flush()
if failing.get(mode) == step:
    sys.stderr.write(
        "ERROR: Could not find a version that satisfies the requirement fixture-missing\n"
    )
    sys.stderr.flush()
    raise SystemExit(3)
print("Successfully installed fixture-package-1.0")
"""

# Flat batch structure on purpose: inside nested parenthesized blocks this
# environment drops the 'exit /b' code and the stub would fake a clean exit.
FAKE_PYTHON = r"""@echo off
if not "%~1"=="-c" goto venv
if /I "%DEV049_FAKE_PROBE_MODE%"=="notice" echo fixture probe notice 1>&2
if /I "%DEV049_FAKE_PROBE_MODE%"=="fail" echo fixture probe failure 1>&2
if /I "%DEV049_FAKE_PROBE_MODE%"=="fail" exit /b 7
echo {"version":[3,12,0],"bits":64}
exit /b 0
:venv
if not "%~2"=="venv" exit /b 1
if /I "%DEV049_FAKE_VENV_MODE%"=="notice" echo fixture venv notice 1>&2
if /I "%DEV049_FAKE_VENV_MODE%"=="fail" echo fixture venv failure 1>&2
if /I "%DEV049_FAKE_VENV_MODE%"=="fail" exit /b 5
if /I "%DEV049_FAKE_VENV%"=="break" del /q "%~3\Scripts\python.exe" >nul 2>nul
exit /b 0
"""

SDK_FILES = [
    "Parametric/bin/parametric.exe",
    "Common Files/protoolkit/includes/ProToolkit.h",
    "Common Files/x86e_win64/obj/pro_comm_msg.exe",
    "Common Files/templates/mmns_part_solid_abs.prt",
    "Common Files/templates/mmns_asm_design_abs.asm",
    *[
        "Common Files/protoolkit/x86e_win64/obj/" + name
        for name in (
            "ptasyncmd.lib",
            "protkmd_NU.lib",
            "protk_dllmd_NU.lib",
            "ucore.lib",
            "udata.lib",
        )
    ],
]


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def decode(data):
    """PowerShell 5.1 writes redirected streams as UTF-16LE, console output as UTF-8."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in data[:400]:
        return data.decode("utf-16", "replace")
    return data.decode("utf-8", "replace")


def completed_stages(output):
    marker = "Completed: "
    if marker not in output:
        return ""
    return output.split(marker, 1)[1].split(".", 1)[0]


@unittest.skipUnless(os.name == "nt", "Windows PowerShell 5.1 installer")
class SetupNativeStderrTests(unittest.TestCase):
    """Both pip stages must judge the real exit code, not PowerShell 5.1 stderr records."""

    @classmethod
    def setUpClass(cls):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        template = tempfile.TemporaryDirectory(dir=ROOT / ".tmp")
        cls.addClassCleanup(template.cleanup)
        cls.template_venv = Path(template.name) / "venv"
        subprocess.run(
            [sys._base_executable, "-m", "venv", "--without-pip", str(cls.template_venv)],
            check=True,
            timeout=180,
            creationflags=bridge.HIDDEN,
        )

    def fixture(self):
        """Build one isolated install tree that never reaches PyPI or Creo."""
        temporary = tempfile.TemporaryDirectory(dir=ROOT / ".tmp")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "install"
        root.mkdir()
        for name in (
            "setup.ps1",
            "pyproject.toml",
            "bridge.py",
            "capabilities.py",
            "version.py",
            "seeds.py",
            "schema.py",
            "airfoil.py",
            "profile_checks.py",
            "LICENSE",
        ):
            shutil.copy2(ROOT / name, root / name)
        shutil.copytree(
            ROOT / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info")
        )
        (root / "docs").mkdir()
        shutil.copy2(ROOT / "docs/seed_manifest.json", root / "docs/seed_manifest.json")
        shutil.copytree(ROOT / "seed_library", root / "seed_library")
        (root / "tools").mkdir()
        for name in ("generate_constants.py", "compiler_preflight.py"):
            shutil.copy2(ROOT / "tools" / name, root / "tools" / name)
        (root / "requirements.lock.txt").write_text("")
        creo = root / "Creo with spaces"
        (root / "config.json").write_text(
            json.dumps({"creo_root": str(creo), "vcvars64": str(root / "vcvars64.bat")}),
            encoding="utf-8",
        )
        (root / "vcvars64.bat").write_text("@echo off\nexit /b 0\n")
        for relative in SDK_FILES:
            target = creo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
        shutil.copytree(self.template_venv, root / ".venv")
        fake_site = root / "fake_site"
        (fake_site / "pip").mkdir(parents=True)
        (fake_site / "pip/__main__.py").write_text(FAKE_PIP, encoding="utf-8")
        (root / "python.cmd").write_text(FAKE_PYTHON, encoding="utf-8")
        return root

    def run_setup(
        self, root, form, *, mode="notice", break_venv=False, probe_mode="", venv_mode=""
    ):
        error_file = root / "native-stderr.txt"
        if error_file.exists():
            error_file.unlink()
        setup = str(root / "setup.ps1")
        shim = str(root / "python.cmd")
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass"]
        if form == "direct":
            command += ["-File", setup, "-Python", shim]
        else:
            script = f"& {quote(setup)} -Python {quote(shim)}"
            if form == "stderr_redirect":
                script += f" 2> {quote(error_file)}"
            else:
                script += " 2>&1"
            command += ["-EncodedCommand", base64.b64encode(script.encode("utf-16-le")).decode()]
        environment = dict(os.environ)
        environment.update(
            INCLUDE="",
            LIB="",
            DEV049_FAKE_PIP_MODE=mode,
            DEV049_FAKE_VENV="break" if break_venv else "",
            DEV049_FAKE_PROBE_MODE=probe_mode,
            DEV049_FAKE_VENV_MODE=venv_mode,
            PYTHONPATH=os.pathsep.join([str(root / "fake_site"), str(root / "src")]),
        )
        result = subprocess.run(
            command,
            env=environment,
            capture_output=True,
            timeout=120,
            creationflags=bridge.HIDDEN,
        )
        captured = [decode(result.stdout), decode(result.stderr)]
        if error_file.exists():
            captured.append(decode(error_file.read_bytes()))
        return result, "".join(captured)

    def test_notice_on_stderr_keeps_both_pip_stages(self):
        for form in FORMS:
            with self.subTest(form=form):
                root = self.fixture()
                result, output = self.run_setup(root, form)
                stages = completed_stages(output)
                self.assertIn("Python dependencies", stages, output)
                self.assertIn("Python source package", stages, output)
                self.assertNotIn("failed at Python dependencies", output)
                self.assertIn("[notice]", output, "pip stderr must stay visible")

    def test_requirements_failure_keeps_original_error_and_exit_code(self):
        for form in FORMS:
            with self.subTest(form=form):
                root = self.fixture()
                result, output = self.run_setup(root, form, mode="fail-requirements")
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn("INSTALL_INCOMPLETE: failed at Python dependencies", output)
                self.assertIn(ORIGINAL_ERROR, output)
                self.assertIn(f"exited with code {PIP_EXIT_CODE}", output)
                self.assertNotIn("Python dependencies", completed_stages(output))

    def test_editable_failure_keeps_original_error_and_exit_code(self):
        for form in FORMS:
            with self.subTest(form=form):
                root = self.fixture()
                result, output = self.run_setup(root, form, mode="fail-editable")
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn("INSTALL_INCOMPLETE: failed at Python source package", output)
                self.assertIn(ORIGINAL_ERROR, output)
                self.assertIn(f"exited with code {PIP_EXIT_CODE}", output)
                self.assertIn("Python dependencies", completed_stages(output))

    def test_launch_failure_fails_without_a_stale_exit_code(self):
        for form in FORMS:
            with self.subTest(form=form):
                root = self.fixture()
                result, output = self.run_setup(root, form, break_venv=True)
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn("INSTALL_INCOMPLETE: failed at Python dependencies", output)
                self.assertIn("Could not start", output)
                self.assertNotIn("exited with code", output)

    def test_probe_stderr_notice_does_not_fail_prerequisites(self):
        for form in FORMS:
            with self.subTest(form=form):
                root = self.fixture()
                result, output = self.run_setup(root, form, probe_mode="notice")
                self.assertIn("Prerequisites found", output, output)
                self.assertNotIn("Cannot run Python", output, output)
                self.assertIn("fixture probe notice", output, "probe stderr must stay visible")

    def test_probe_failure_reports_the_real_exit_code(self):
        for form in FORMS:
            with self.subTest(form=form):
                root = self.fixture()
                result, output = self.run_setup(root, form, probe_mode="fail")
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn("Cannot run Python", output)
                self.assertIn("exited with code 7", output)
                self.assertIn("fixture probe failure", output, "probe stderr must stay visible")
                self.assertNotIn("INSTALL_INCOMPLETE", output)

    def test_venv_stderr_notice_completes_the_stage(self):
        for form in FORMS:
            with self.subTest(form=form):
                root = self.fixture()
                result, output = self.run_setup(root, form, venv_mode="notice")
                self.assertIn("Python virtual environment", completed_stages(output), output)
                self.assertNotIn("failed at Python virtual environment", output)
                self.assertIn("fixture venv notice", output, "venv stderr must stay visible")

    def test_venv_failure_reports_install_incomplete_with_the_exit_code(self):
        for form in FORMS:
            with self.subTest(form=form):
                root = self.fixture()
                result, output = self.run_setup(root, form, venv_mode="fail")
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn("INSTALL_INCOMPLETE: failed at Python virtual environment", output)
                self.assertIn("exited with code 5", output)
                self.assertIn("fixture venv failure", output, "venv stderr must stay visible")
                self.assertNotIn("Python virtual environment", completed_stages(output))

    def test_setup_scopes_the_tolerated_preference_to_the_external_helper(self):
        source = (ROOT / "setup.ps1").read_text(encoding="utf-8")
        self.assertEqual(source.count("$ErrorActionPreference = 'Stop'"), 1)
        self.assertEqual(source.count("$ErrorActionPreference = 'Continue'"), 1)
        self.assertEqual(source.count("$ErrorActionPreference = $previousPreference"), 1)
        self.assertNotIn("Invoke-PipStep", source)
        helper = source.index("function Invoke-ExternalStep")
        continue_at = source.index("$ErrorActionPreference = 'Continue'")
        restore_at = source.index("$ErrorActionPreference = $previousPreference")
        self.assertLess(helper, continue_at)
        self.assertLess(continue_at, restore_at)
        self.assertLess(restore_at, source.index("$stage = 'local configuration'"))
        # Every external call goes through the helper; only the helper launches processes.
        self.assertEqual(source.count("Invoke-ExternalStep -Executable"), 8)
        self.assertEqual(source.count("& $Executable @Arguments"), 2)


if __name__ == "__main__":
    unittest.main()
