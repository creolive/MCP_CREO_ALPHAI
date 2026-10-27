import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
from tools.compiler_preflight import compiler_environment_errors
from tools.generate_constants import HEADERS, generate

ROOT = Path(__file__).resolve().parents[1]


class InstallationValidation(unittest.TestCase):
    def setUp(self):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".tmp")
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to((ROOT / ".tmp").resolve())
        self.addCleanup(self.temp.cleanup)
        self.creo = self.root / "Creo with spaces"
        self.psf = self.creo / "Parametric/bin/parametric.psf"
        self.psf.parent.mkdir(parents=True)
        self.settings = {"creo_root": str(self.creo), "vcvars64": str(self.root / "vcvars64.bat")}

    def license(self, env_value, psf_value):
        self.psf.write_text("ENV=PTC_D_LICENSE_FILE=" + psf_value, encoding="utf-8")
        with (
            patch.object(bridge, "config", return_value=self.settings),
            patch.dict(os.environ, {"PTC_D_LICENSE_FILE": env_value}),
        ):
            return bridge.resolve_license_environment()

    def test_bad_local_license_falls_back_without_exposing_values(self):
        valid = self.root / "test.lic"
        valid.write_text("fixture")
        missing = str(self.root / "missing secret.lic")
        value, diagnostics = self.license(missing, str(valid))
        self.assertEqual(value, str(valid))
        self.assertTrue(diagnostics["fallback_used"])
        self.assertEqual(diagnostics["environment_state"], "missing_local_path")
        self.assertNotIn(missing, json.dumps(diagnostics))
        self.assertNotIn(str(valid), json.dumps(diagnostics))

    def test_server_and_partial_list_are_preserved(self):
        valid = self.root / "test.lic"
        valid.write_text("fixture")
        for env_value in [
            "27000@test-host",
            "@test-host",
            str(valid),
            '"' + str(valid) + '"',
            str(valid) + ";" + str(self.root / "missing.lic"),
        ]:
            value, diagnostics = self.license(env_value, str(valid))
            self.assertEqual(value, env_value)
            self.assertFalse(diagnostics["fallback_used"])
        self.assertEqual(diagnostics["selected_state"], "partially_missing")

    def test_invalid_fallback_is_reported_and_global_env_not_changed(self):
        missing = str(self.root / "missing.lic")
        value, diagnostics = self.license(missing, missing)
        self.assertEqual(value, missing)
        self.assertEqual(diagnostics["selected_state"], "missing_local_path")
        self.assertTrue(diagnostics["warnings"])
        valid = self.root / "valid.lic"
        valid.write_text("fixture")
        self.psf.write_text("ENV=PTC_D_LICENSE_FILE=" + str(valid), encoding="utf-8")
        with (
            patch.object(bridge, "config", return_value=self.settings),
            patch.dict(os.environ, {"PTC_D_LICENSE_FILE": missing}),
        ):
            self.assertEqual(bridge.native_environment()["PTC_D_LICENSE_FILE"], str(valid))
            self.assertEqual(os.environ["PTC_D_LICENSE_FILE"], missing)
            self.assertTrue(bridge.check_environment()["license_diagnostics"]["fallback_used"])

    def sdk(self):
        includes = self.creo / "Common Files/protoolkit/includes"
        includes.mkdir(parents=True)
        for header in HEADERS:
            (includes / header).write_text("// fixture\n", encoding="utf-8")
        (includes / HEADERS[0]).write_text("enum fixture { PRO_E_TEST_ONE = 1 };", encoding="utf-8")
        (self.root / "native").mkdir()
        (self.root / "config.json").write_text(json.dumps(self.settings), encoding="utf-8")
        return includes

    def test_constant_refresh_updates_old_table_and_keeps_unchanged_timestamp(self):
        includes = self.sdk()
        output = self.root / "native/constants.inc"
        output.write_text("stale table")
        generate(self.root)
        self.assertIn("PRO_E_TEST_ONE", output.read_text())
        timestamp = output.stat().st_mtime_ns
        generate(self.root)
        self.assertEqual(timestamp, output.stat().st_mtime_ns)
        (includes / HEADERS[-1]).write_text("enum fixture { PRO_FEAT_TEST_NEW = 7 };")
        generate(self.root)
        self.assertIn("PRO_FEAT_TEST_NEW", output.read_text())

    def test_cached_build_refreshes_constants_before_reusing_worker(self):
        includes = self.sdk()
        calls = []

        def run(command, **kwargs):
            if command[1].endswith("generate_constants.py"):
                calls.append("generate")
                generate(self.root)
            elif command[0] == "cmd.exe":
                calls.append("compile")
                (self.root / "build/creo_worker.exe").write_bytes(b"fixture worker")
                (self.root / "build/creo_blend_sync.dll").write_bytes(b"fixture callback")
                (self.root / "build/creo_blend_loader.dll").write_bytes(b"fixture loader")
            else:
                calls.append("constants")
            return subprocess.CompletedProcess(command, 0, stdout=b"{}")

        with (
            patch.object(bridge, "ROOT", self.root),
            patch.object(bridge, "config", return_value=self.settings),
            patch.object(bridge, "check_environment", return_value={"ready_to_build": True}),
            patch.object(bridge.subprocess, "run", side_effect=run),
        ):
            bridge.build_native()
            bridge.build_native()
            self.assertEqual(calls.count("generate"), 2)
            self.assertEqual(calls.count("compile"), 1)
            (includes / HEADERS[-1]).write_text("enum fixture { PRO_FEAT_TEST_NEW = 7 };")
            bridge.build_native()
            self.assertEqual(calls.count("compile"), 2)
            # A changed SDK numeric value must rebuild even if enum names and
            # generated constants.inc remain exactly the same.
            (includes / HEADERS[-1]).write_text("enum fixture { PRO_FEAT_TEST_NEW = 8 };")
            bridge.build_native()
            self.assertEqual(calls.count("compile"), 3)
            (self.root / "build/creo_blend_sync.dll").unlink()
            bridge.build_native()
            self.assertEqual(calls.count("compile"), 4)

    def test_compiler_preflight_detects_partial_vcvars_success(self):
        include = self.root / "include"
        libraries = self.root / "lib"
        include.mkdir()
        libraries.mkdir()
        env = {"INCLUDE": str(include), "LIB": str(libraries), "PATH": ""}
        with patch("tools.compiler_preflight.shutil.which", return_value="fixture.exe"):
            errors = compiler_environment_errors(env)
            self.assertTrue(any("stdio.h" in error for error in errors))
            self.assertTrue(any("reg.exe" in error for error in errors))
            for filename in ("stdio.h", "windows.h"):
                (include / filename).touch()
            for filename in ("ucrt.lib", "kernel32.lib"):
                (libraries / filename).touch()
            self.assertEqual(compiler_environment_errors(env), [])

    def test_worker_change_reuses_callback_but_tampering_rebuilds_it(self):
        self.sdk()
        (self.root / "native/worker.cpp").write_text("// worker one")
        (self.root / "native/blend_sync.cpp").write_text("// callback")
        builds = []

        def run(command, **kwargs):
            if len(command) > 1 and command[1].endswith("generate_constants.py"):
                generate(self.root)
            elif command[0] == "cmd.exe":
                script = (self.root / "build/build.cmd").read_text()
                callback_compiled = "blend_sync.cpp" in script
                builds.append(callback_compiled)
                if "blend_loader.cpp" in script:
                    (self.root / "build/creo_blend_loader.dll").write_bytes(b"verified loader")
                (self.root / "build/creo_worker.exe").write_bytes(b"worker")
                if callback_compiled:
                    (self.root / "build/creo_blend_sync.dll").write_bytes(b"verified callback")
            return subprocess.CompletedProcess(command, 0, stdout=b"{}")

        with (
            patch.object(bridge, "ROOT", self.root),
            patch.object(bridge, "config", return_value=self.settings),
            patch.object(bridge, "check_environment", return_value={"ready_to_build": True}),
            patch.object(bridge.subprocess, "run", side_effect=run),
        ):
            bridge.build_native()
            (self.root / "native/worker.cpp").write_text("// worker two")
            bridge.build_native()
            self.assertEqual(builds, [True, False])
            (self.root / "build/creo_blend_sync.dll").write_bytes(b"tampered")
            bridge.build_native()
            self.assertEqual(builds, [True, False, True])

    @unittest.skipUnless(os.name == "nt", "Windows installer integration")
    def test_installer_native_failure_leaves_client_config_and_resume_instructions(self):
        self.sdk()
        (self.root / "tools").mkdir()
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
        ):
            shutil.copy2(ROOT / name, self.root / name)
        shutil.copytree(
            ROOT / "src",
            self.root / "src",
            ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"),
        )
        shutil.copy2(ROOT / "LICENSE", self.root / "LICENSE")
        (self.root / "docs").mkdir()
        shutil.copy2(ROOT / "docs/seed_manifest.json", self.root / "docs/seed_manifest.json")
        shutil.copytree(ROOT / "seed_library", self.root / "seed_library")
        for name in ("generate_constants.py", "compiler_preflight.py"):
            shutil.copy2(ROOT / "tools" / name, self.root / "tools" / name)
        (self.root / "requirements.lock.txt").write_text("")
        self.settings.update(
            creo_session_id="fixture-private-session", local_extra={"retained": True}
        )
        (self.root / "config.json").write_text(json.dumps(self.settings))
        (self.root / "vcvars64.bat").write_text("@echo off\nexit /b 0\n")
        for name in [
            "Parametric/bin/parametric.exe",
            "Common Files/protoolkit/includes/ProToolkit.h",
            "Common Files/x86e_win64/obj/pro_comm_msg.exe",
            "Common Files/templates/mmns_part_solid_abs.prt",
            "Common Files/templates/mmns_asm_design_abs.asm",
            *[
                "Common Files/protoolkit/x86e_win64/obj/" + n
                for n in (
                    "ptasyncmd.lib",
                    "protkmd_NU.lib",
                    "protk_dllmd_NU.lib",
                    "ucore.lib",
                    "udata.lib",
                )
            ],
        ]:
            target = self.creo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
        env = dict(os.environ)
        env.update(INCLUDE="", LIB="", PIP_DISABLE_PIP_VERSION_CHECK="1")
        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.root / "setup.ps1"),
            "-Python",
            sys._base_executable,
        ]
        result = subprocess.run(
            command, env=env, capture_output=True, timeout=90, creationflags=bridge.HIDDEN
        )
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("INSTALL_INCOMPLETE: failed at SDK constants and native worker", output)
        self.assertIn("rerun the same setup.ps1 command", output)
        # Both pip stages (BUG-086) still complete on the normal path before the native build fails.
        self.assertIn(
            "Python dependencies, Python source package, native Blend seed library", output
        )
        connection = bridge.read_json(self.root / "client-config.json")
        self.assertTrue(Path(connection["mcpServers"]["MCP_CREO_MechDog"]["command"]).is_file())
        retained = bridge.read_json(self.root / "config.json")
        self.assertEqual(retained["local_extra"], {"retained": True})
        self.assertEqual(retained["creo_session_id"], "fixture-private-session")
        log = (self.root / "build/build.log").read_text(errors="replace")
        self.assertIn("COMPILER_PREFLIGHT: Missing stdio.h", log)
        assembly_template = self.creo / "Common Files/templates/mmns_asm_design_abs.asm"
        assembly_template.unlink()
        check = subprocess.run(
            command + ["-CheckOnly"],
            env=env,
            capture_output=True,
            timeout=30,
            creationflags=bridge.HIDDEN,
        )
        self.assertNotEqual(check.returncode, 0)
        self.assertIn(b"mmns_asm_design_abs.asm", check.stdout + check.stderr)


if __name__ == "__main__":
    unittest.main()
