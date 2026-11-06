"""FEAT-019 configuration, readiness, startup reservation and coordination guards."""

import asyncio
import contextlib
import ctypes
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import bridge
import creo_startup
import server
from creo_mechdog import capability_pages

ROOT = Path(__file__).resolve().parents[1]
ABSENT = {"connected": False, "connection_state": "not_found_or_unreadable", "toolkit_code": -4}
READY = {"connected": True, "connection_state": "connected", "toolkit_code": 0}


class WaitClock:
    def __init__(self):
        self.elapsed = 0.0

    def monotonic(self):
        return self.elapsed

    def is_set(self):
        return False

    def wait(self, seconds):
        self.elapsed += seconds


class CreoStartupTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".tmp"
        parent.mkdir(exist_ok=True)
        self.fixture = tempfile.TemporaryDirectory(prefix="feat019_unit_", dir=parent)
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name)
        self.assertTrue(self.root.resolve().is_relative_to(ROOT))
        self.creo = self.root / "Creo with spaces"
        executable = self.creo / "Parametric/bin/parametric.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"fixture")
        psf = executable.with_suffix(".psf")
        psf.write_text("fixture; never executed", encoding="utf-8")
        self.config = {
            "creo_root": str(self.creo),
            "creo_session_id": "",
            "creo_startup_timeout_seconds": 10,
        }
        self.coordinator = self.root / "coordinator"
        self.coordinator.mkdir()
        self.startup = creo_startup.CreoStartup(self.coordinator)
        self.startup._directory = self.coordinator
        self.clock = WaitClock()
        self.startup._stop = self.clock
        stack = self.enterContext(contextlib.ExitStack())
        stack.enter_context(patch.object(bridge, "config", side_effect=lambda: dict(self.config)))
        stack.enter_context(patch.object(bridge, "channel_health", return_value={}))
        stack.enter_context(
            patch.object(
                bridge, "toolkit_lock", side_effect=lambda **kwargs: contextlib.nullcontext()
            )
        )
        self.build = stack.enter_context(patch.object(bridge, "build_native"))
        self.probe = stack.enter_context(patch.object(bridge, "session_status", return_value=READY))
        self.inventory = stack.enter_context(
            patch.object(
                creo_startup, "inventory", return_value={"processes": [], "uncertain": False}
            )
        )
        stack.enter_context(
            patch.object(
                bridge, "native_environment", return_value={"SECRET_TEST": "private-value"}
            )
        )
        stack.enter_context(
            patch.object(creo_startup.time, "monotonic", side_effect=self.clock.monotonic)
        )
        self.process = Mock(returncode=0)
        self.process.poll.return_value = None
        self.launch = stack.enter_context(
            patch.object(creo_startup, "launch_creo", return_value=self.process)
        )

    def drive(self, retry=False):
        self.startup._phase_deadline = None
        self.startup._expired = False
        self.startup._drive(creo_startup.Settings.load(), retry, self.clock.elapsed + 10)
        return self.startup.status()

    def existing(self):
        return {
            "processes": [{"pid": 1, "created": 10, "image": "fixture", "matches": True}],
            "uncertain": False,
        }

    def test_capabilities_identifies_running_source(self):
        capability_pages.reset_snapshot()
        page = asyncio.run(server.creo_capabilities(detail="full", section="runtime"))
        runtime = {entry["key"]: entry["value"] for entry in page["entries"]}
        self.assertEqual(Path(runtime["server_entry"]), ROOT / "server.py")
        self.assertEqual(Path(runtime["code_root"]), ROOT)
        self.assertEqual(Path(runtime["python_executable"]), Path(os.sys.executable))
        self.assertFalse(runtime["source_changed_since_startup"])
        self.assertIn("creo_startup.py", runtime["source_fingerprints_at_startup"])

    def test_capabilities_detects_source_change_without_relabeling_loaded_code(self):
        loaded = dict(server._LOADED_FINGERPRINTS)
        changed = {**loaded, "server.py": "changed-on-disk"}
        with patch.object(server, "_source_fingerprints", return_value=changed):
            # Drop the frozen capabilities snapshot so the patched detector runs.
            capability_pages.reset_snapshot()
            page = asyncio.run(server.creo_capabilities(detail="full", section="runtime"))
            runtime = {entry["key"]: entry["value"] for entry in page["entries"]}
        self.assertTrue(runtime["source_changed_since_startup"])
        self.assertEqual(runtime["source_fingerprints_at_startup"], loaded)

    def test_defaults_and_strict_configuration(self):
        self.config.pop("creo_startup_timeout_seconds")
        settings = creo_startup.Settings.load()
        self.assertTrue(settings.auto_start)
        self.assertEqual(settings.timeout, 120)
        for key, invalid in (
            ("auto_start_creo", "false"),
            ("auto_start_creo", 1),
            ("creo_startup_timeout_seconds", True),
            ("creo_startup_timeout_seconds", 9),
            ("creo_startup_timeout_seconds", 601),
            ("creo_startup_timeout_seconds", 10.0),
            ("creo_startup_psf", 2),
            ("creo_startup_psf", "relative.psf"),
            ("creo_session_id", "private\nvalue"),
        ):
            with self.subTest(key=key, invalid=invalid), patch.dict(self.config, {key: invalid}):
                with self.assertRaises(ValueError):
                    creo_startup.Settings.load()

    def test_existing_session_is_verified_and_reused(self):
        self.inventory.return_value = self.existing()
        state = self.drive()
        self.assertEqual(state["state"], "ready")
        self.assertTrue(state["connected"])
        self.assertFalse(state["launched_by_coordinator"])
        self.launch.assert_not_called()
        self.startup.require_ready()

    def test_cold_start_uses_argument_list_psf_and_single_reservation(self):
        self.probe.side_effect = [ABSENT, READY]

        def launch_after_inventory_only(*args):
            self.probe.assert_not_called()
            return self.process

        self.launch.side_effect = launch_after_inventory_only
        state = self.drive()
        self.assertEqual(state["state"], "ready")
        self.assertTrue(state["launched_by_coordinator"])
        self.assertFalse(state["launch_reserved"])
        self.assertEqual(state["launch_attempt"], 1)
        self.assertEqual(self.launch.call_count, 1)
        args, kwargs = self.launch.call_args
        self.assertEqual(args[0].executable, self.creo / "Parametric/bin/parametric.exe")
        self.assertEqual(args[0].psf, self.creo / "Parametric/bin/parametric.psf")
        self.assertEqual(args[1], ROOT / "build/creo_session")
        self.assertEqual(kwargs, {})
        log = (self.coordinator / "startup.log").read_text(encoding="utf-8")
        self.assertIn("state=starting", log)
        self.assertNotIn("private-value", log)

    def test_process_appearing_before_launch_prevents_launch(self):
        self.probe.return_value = READY
        self.inventory.side_effect = [
            {"processes": [], "uncertain": False},
            {"processes": [], "uncertain": False},
            self.existing(),
            self.existing(),
        ]
        self.assertEqual(self.drive()["state"], "ready")
        self.launch.assert_not_called()

    def test_cold_start_creates_working_directory_in_a_clean_checkout(self):
        checkout = self.root / "clean_checkout"
        checkout.mkdir()
        with patch.object(bridge, "ROOT", checkout):
            self.assertEqual(self.drive()["state"], "ready")
        self.assertTrue((checkout / "build/creo_session").is_dir())
        self.assertEqual(self.launch.call_args.args[1], checkout / "build/creo_session")

    def test_disabled_then_manually_opened_session_can_be_reused(self):
        self.config["auto_start_creo"] = False
        self.assertEqual(self.drive()["state"], "disabled")
        self.build.assert_not_called()
        self.launch.assert_not_called()
        self.inventory.return_value = self.existing()
        self.assertEqual(self.drive(retry=True)["state"], "ready")
        self.launch.assert_not_called()

    def test_running_or_manual_confirmation_timeout_never_duplicates_launch(self):
        self.inventory.return_value = self.existing()
        self.probe.return_value = ABSENT
        state = self.drive()
        self.assertEqual(state["state"], "timeout")
        self.assertEqual(self.clock.elapsed, 10)
        self.assertFalse(state["connected"])
        self.launch.assert_not_called()

    def test_new_launch_waits_then_times_out_once_and_retains_reservation(self):
        self.probe.return_value = ABSENT
        state = self.drive()
        self.assertEqual(state["state"], "timeout")
        self.assertEqual(self.launch.call_count, 1)
        self.assertTrue(state["launch_reserved"])
        self.assertEqual(self.clock.elapsed, 10)
        self.assertEqual(self.drive()["state"], "timeout")
        self.assertEqual(self.launch.call_count, 1)
        self.probe.side_effect = [ABSENT, READY]
        self.assertEqual(self.drive(retry=True)["state"], "ready")
        self.assertEqual(self.launch.call_count, 2)
        self.assertEqual(self.startup.status()["launch_attempt"], 2)

    def test_retry_with_existing_process_only_waits_without_relaunch(self):
        bridge.write_json(
            self.coordinator / "state.json",
            {"state": "timeout", "launch_reserved": True, "launch_attempt": 1},
        )
        self.inventory.return_value = self.existing()
        self.probe.return_value = ABSENT
        self.assertEqual(self.drive(retry=True)["state"], "timeout")
        self.launch.assert_not_called()

    def test_retry_requested_during_initial_check_is_not_dropped(self):
        bridge.write_json(
            self.coordinator / "state.json",
            {"state": "timeout", "launch_reserved": True, "launch_attempt": 1},
        )
        fake_thread = Mock()
        fake_thread.is_alive.return_value = True
        self.startup._thread = fake_thread
        self.startup.start(retry=True)
        self.assertTrue(self.startup._retry_requested)
        self.probe.side_effect = [ABSENT, READY]
        self.assertEqual(self.drive()["state"], "ready")
        self.assertEqual(self.launch.call_count, 1)

    def test_waiter_retry_for_older_attempt_cannot_repeat_newer_failed_launch(self):
        bridge.write_json(
            self.coordinator / "state.json",
            {"state": "timeout", "launch_reserved": True, "launch_attempt": 2},
        )
        self.startup._retry_requested = True
        self.startup._retry_for_attempt = 1
        self.probe.return_value = ABSENT
        self.assertEqual(self.drive(retry=True)["state"], "timeout")
        self.launch.assert_not_called()

    def test_reservation_is_durable_before_launch_and_preserved_on_build_failure(self):
        self.probe.return_value = ABSENT

        def launched(*args, **kwargs):
            saved = bridge.read_json(self.coordinator / "state.json")
            self.assertTrue(saved["launch_reserved"])
            self.assertEqual(saved["state"], "starting")
            raise OSError("launch rejected")

        self.launch.side_effect = launched
        self.assertEqual(self.drive()["state"], "launch_failed")
        self.build.side_effect = RuntimeError("build unavailable")
        with self.assertRaises(RuntimeError):
            self.drive()
        self.assertTrue(bridge.read_json(self.coordinator / "state.json")["launch_reserved"])

    def test_multiple_sessions_and_stale_selected_id_are_rejected(self):
        self.inventory.return_value = self.existing()
        self.probe.return_value = {
            "connected": False,
            "connection_state": "ambiguous",
            "toolkit_code": -36,
        }
        self.assertEqual(self.drive()["state"], "selection_required")
        self.config["creo_session_id"] = "private-selected-session"
        self.probe.return_value = ABSENT
        state = self.drive()
        self.assertEqual(state["state"], "selection_required")
        self.assertNotIn("private-selected-session", json.dumps(state))
        self.launch.assert_not_called()
        self.probe.return_value = READY
        self.assertEqual(self.drive()["state"], "ready")

    def test_uncertain_or_other_installation_does_not_probe_or_launch(self):
        for value in (
            {"processes": [], "uncertain": True},
            {"processes": [{"matches": False}], "uncertain": False},
        ):
            self.inventory.return_value = value
            self.assertEqual(self.drive()["state"], "selection_required")
        self.launch.assert_not_called()
        self.probe.assert_not_called()

    def test_connection_failure_and_missing_launch_files_do_not_claim_ready(self):
        self.probe.return_value = {
            "connected": False,
            "connection_state": "connection_failed",
            "toolkit_code": -1,
        }
        self.assertEqual(self.drive()["state"], "timeout")
        self.probe.return_value = ABSENT
        (self.creo / "Parametric/bin/parametric.psf").unlink()
        self.assertEqual(self.drive(retry=True)["state"], "configuration_error")
        self.assertEqual(self.launch.call_count, 1)
        with self.assertRaisesRegex(RuntimeError, "No modeling job was queued"):
            self.startup.require_ready()

    def test_launcher_nonzero_exit_is_bounded_and_reported(self):
        self.probe.return_value = ABSENT
        self.process.poll.return_value = 17
        self.process.returncode = 17
        state = self.drive()
        self.assertEqual(state["state"], "launch_failed")
        self.assertIn("17", state["message"])
        self.assertEqual(self.launch.call_count, 1)

    def test_readiness_gate_leaves_inspection_and_protocol_available(self):
        with patch.object(server, "startup", self.startup):
            with self.assertRaisesRegex(server.ToolError, "not ready"):
                asyncio.run(server.invoke(bridge.create_job, {}))
            self.launch.assert_not_called()
            with patch.object(bridge, "get_job", return_value={"status": "running"}) as read:
                self.assertEqual(asyncio.run(server.invoke(read))["status"], "running")

    def test_background_configuration_failure_is_terminal_and_fast(self):
        self.startup._stop = threading.Event()
        self.config["auto_start_creo"] = "invalid"
        began = time.perf_counter()
        self.startup.start()
        self.startup._thread.join(timeout=2)
        self.assertLess(time.perf_counter() - began, 2)
        self.assertEqual(self.startup.status()["state"], "configuration_error")
        self.assertIn("auto_start_creo", self.startup.status()["message"])

    def test_session_status_keeps_native_fields_while_ready_thread_is_finishing(self):
        self.startup._thread = Mock()
        self.startup._thread.is_alive.return_value = True
        self.startup._publish(
            "ready", "verified", shared=False, native={**READY, "current_model": "existing_part"}
        )
        value = self.startup.session_status()
        self.assertTrue(value["connected"])
        self.assertEqual(value["toolkit_code"], 0)
        self.assertEqual(value["current_model"], "existing_part")
        self.probe.assert_not_called()

    def test_session_status_detects_manual_open_and_loss_without_implicit_restart(self):
        self.startup._publish("disabled", "manual startup", shared=False)
        with patch.object(self.startup, "start") as start:
            self.probe.return_value = READY
            self.assertTrue(self.startup.session_status()["connected"])
            self.probe.return_value = ABSENT
            value = self.startup.session_status()
            self.assertFalse(value["connected"])
            self.assertEqual(value["startup"]["state"], "timeout")
            self.assertTrue(value["startup"]["retry_allowed"])
            start.assert_not_called()
            self.launch.assert_not_called()
        self.assertEqual(value["mode"], "explicit_live")
        self.assertTrue(value["live_probe"]["performed"])
        self.assertEqual(value["channel_policy"], "single_channel_busy_rejects_immediately")

    def test_session_status_reports_busy_probe_without_queueing_a_second_channel(self):
        self.probe.side_effect = bridge.ToolkitBusy(
            holder={"job_id": "job" * 8, "model_id": "model_busy", "operation": "execute_plan"}
        )
        value = self.startup.session_status()
        self.assertFalse(value["connected"])
        self.assertEqual(value["connection_state"], "busy")
        self.assertEqual(value["mode"], "explicit_live")
        self.assertTrue(value["live_probe"]["busy"])
        self.assertFalse(value["live_probe"]["queued"])
        self.assertFalse(value["live_probe"]["second_channel_opened"])
        self.assertEqual(value["channel_policy"], "busy_rejects_immediately")
        self.launch.assert_not_called()

    def test_reused_session_keeps_launch_attempt_and_reports_attempt_identity(self):
        bridge.write_json(
            self.coordinator / "state.json",
            {"state": "timeout", "launch_reserved": True, "launch_attempt": 17},
        )
        self.inventory.return_value = self.existing()
        state = self.drive(retry=True)
        self.assertEqual(state["state"], "ready")
        self.assertEqual(state["launch_attempt"], 17)
        self.launch.assert_not_called()
        self.assertEqual(state["phase"], "ready")
        self.assertTrue(state["retry_id"])
        datetime.fromisoformat(state["started_at"])
        self.assertIsNone(state["failure_code"])
        self.assertIsNone(state["terminal_reason"])
        self.assertEqual(state["budget_scope"], "total")
        self.assertEqual(state["phase_budget_scope"], "phase")
        self.assertIsNone(state["next_allowed_retry_at"])
        self.assertIn("No retry is needed", state["next_allowed_retry_reason"])

    def test_status_polling_never_starts_another_retry(self):
        fake_thread = Mock()
        fake_thread.is_alive.return_value = True
        self.startup._thread = fake_thread
        first = self.startup.start(retry=True)
        with patch.object(creo_startup.threading, "Thread") as thread:
            second = self.startup.start(retry=True)
            third = self.startup.start(retry=False)
            thread.assert_not_called()
        self.assertEqual(first["retry_id"], second["retry_id"])
        self.assertEqual(second["retry_id"], third["retry_id"])
        self.launch.assert_not_called()
        self.probe.assert_not_called()

    def test_status_during_a_toolkit_probe_reports_phase_and_blocks_retry(self):
        self.inventory.return_value = self.existing()
        seen = {}

        def probe(**kwargs):
            seen.update(self.startup.status())
            return READY

        self.probe.side_effect = probe
        self.assertEqual(self.drive(retry=True)["state"], "ready")
        self.assertEqual(seen["state"], "waiting_for_connection")
        self.assertEqual(seen["phase"], "waiting_for_connection")
        self.assertFalse(seen["retry_allowed"])
        self.assertEqual(seen["retry_blocked_by"], "startup_in_progress")
        self.assertIsNone(seen["next_allowed_retry_at"])
        self.assertIn("No retry time can be guaranteed", seen["next_allowed_retry_reason"])
        self.assertTrue(seen["retry_id"])

    def test_busy_toolkit_probe_times_out_with_busy_evidence(self):
        self.inventory.return_value = self.existing()
        self.probe.side_effect = bridge.ToolkitBusy(
            holder={"job_id": "job" * 8, "model_id": "model_busy", "operation": "execute_plan"}
        )
        state = self.drive(retry=True)
        self.assertEqual(state["state"], "timeout")
        self.assertEqual(state["busy"]["blocking_job_id"], "job" * 8)
        self.assertEqual(state["busy"]["blocking_operation"], "execute_plan")
        self.assertEqual(state["failure_code"], "startup_timeout")
        self.assertTrue(state["retry_allowed"])
        self.assertEqual(state["launch_attempt"], 0)
        self.launch.assert_not_called()

    def test_process_with_unreadable_ipc_times_out_with_an_explicit_receipt(self):
        self.inventory.return_value = self.existing()
        self.probe.return_value = ABSENT
        self.startup._attempt_deadline = self.clock.elapsed + 10
        state = self.drive()
        self.assertEqual(state["state"], "timeout")
        self.assertEqual(state["phase"], "waiting_for_connection")
        self.assertEqual(state["failure_code"], "startup_timeout")
        self.assertEqual(state["terminal_reason"], state["message"])
        self.assertEqual(state["budget_scope"], "total")
        self.assertEqual(state["phase_budget_scope"], "phase")
        self.assertEqual(state["launch_attempt"], 0)
        self.assertTrue(state["retry_id"])
        datetime.fromisoformat(state["started_at"])
        datetime.fromisoformat(state["deadline_at"])
        datetime.fromisoformat(state["phase_deadline_at"])
        self.launch.assert_not_called()

    def test_no_process_with_automatic_start_disabled_is_explained_without_probe(self):
        self.config["auto_start_creo"] = False
        state = self.drive()
        self.assertEqual(state["state"], "disabled")
        self.assertEqual(state["failure_code"], "automatic_startup_disabled")
        self.assertTrue(state["retry_allowed"])
        self.assertEqual(state["launch_attempt"], 0)
        self.assertIsNone(state["retry_blocked_by"])
        self.probe.assert_not_called()
        self.launch.assert_not_called()

    def test_status_reports_both_budget_scopes_while_running(self):
        fake_thread = Mock()
        fake_thread.is_alive.return_value = True
        self.startup._thread = fake_thread
        self.startup._attempt_deadline = 12.0
        self.startup._phase_deadline = 5.0
        self.startup._publish("waiting_for_connection", "waiting", shared=False)
        self.clock.elapsed = 2.0
        state = self.startup.status()
        self.assertEqual(state["remaining_budget_seconds"], 10)
        self.assertEqual(state["phase_remaining_budget_seconds"], 3)
        self.assertEqual(state["budget_scope"], "total")
        self.assertEqual(state["phase_budget_scope"], "phase")
        self.assertTrue(state["budget_active"])
        self.assertEqual(state["retry_blocked_by"], "coordinator_running")
        self.assertIn("No retry time can be guaranteed", state["next_allowed_retry_reason"])

    def test_expired_budget_is_terminal_but_cannot_allow_a_second_retry(self):
        fake_thread = Mock()
        fake_thread.is_alive.return_value = True
        self.startup._thread = fake_thread
        self.startup._attempt_deadline = 10.0
        self.startup._phase_deadline = 10.0
        self.startup._publish("waiting_for_connection", "waiting", shared=False)
        self.clock.elapsed = 10.0
        state = self.startup.status()
        self.assertEqual(state["state"], "timeout")
        self.assertEqual(state["phase"], "waiting_for_connection")
        self.assertEqual(state["failure_code"], "startup_timeout")
        self.assertEqual(state["remaining_budget_seconds"], 0)
        self.assertEqual(state["phase_remaining_budget_seconds"], 0)
        self.assertFalse(state["retry_allowed"])
        self.assertEqual(state["retry_blocked_by"], "coordinator_running")
        self.assertIsNone(state["next_allowed_retry_at"])
        self.launch.assert_not_called()

    def test_window_observation_reports_unreadable_title_without_activation(self):
        from creo_mechdog import window_observations as windows

        with patch.object(windows, "_enumerate_windows", return_value=[(1, True, True)]):
            value = windows.window_observations({1})
        row = value[1]
        self.assertEqual(row["state"], "visible")
        self.assertTrue(row["visible_hung_window_observed"])
        self.assertFalse(row["hung_implies_modal"])
        self.assertIsNone(row["window_title"])
        self.assertIn("not read", row["window_title_unavailable_reason"])


class WindowsCoordinationTests(unittest.TestCase):
    def test_windows_prerequisites_restore_only_allowed_defaults_and_preserve_host(self):
        import win32profile
        import win32security

        token = Mock()
        with (
            patch.dict(
                os.environ,
                {"SYSTEMROOT": "C:/Windows", "TEMP": "C:/HostTemp", "PATH": "host-path"},
                clear=True,
            ),
            patch.object(win32security, "OpenProcessToken", return_value=token),
            patch.object(
                win32profile,
                "CreateEnvironmentBlock",
                return_value={
                    "COMPUTERNAME": "fixture-host",
                    "USERDOMAIN": "fixture-domain",
                    "TMP": "C:/RegistryTemp",
                    "PATH": "registry-path",
                    "PRIVATE_TOKEN": "must-not-import",
                    "PTC_D_LICENSE_FILE": "must-not-import",
                },
            ),
        ):
            env = bridge.windows_process_environment()
        self.assertEqual(env["COMPUTERNAME"], "fixture-host")
        self.assertEqual(env["USERDOMAIN"], "fixture-domain")
        self.assertEqual(env["PATH"], "host-path")
        self.assertEqual(env["TMP"], "C:/HostTemp")
        self.assertNotIn("PRIVATE_TOKEN", env)
        self.assertNotIn("PTC_D_LICENSE_FILE", env)
        token.Close.assert_called_once()

    def test_inherited_session_id_cannot_select_an_unconfigured_target(self):
        with (
            patch.object(
                bridge, "config", return_value={"creo_root": "C:/Creo", "creo_session_id": ""}
            ),
            patch.object(
                bridge,
                "windows_process_environment",
                return_value={"PATH": "host", "MECHDOG_CREO_SESSION_ID": "inherited-private-id"},
            ),
            patch.object(bridge, "resolve_license_environment", return_value=("", {})),
        ):
            env = bridge.native_environment()
        self.assertNotIn("MECHDOG_CREO_SESSION_ID", env)

    def test_empty_toolkit_lock_excludes_another_process(self):
        parent = ROOT / ".tmp"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="feat019_empty_lock_", dir=parent) as directory:
            target = Path(directory)
            with patch.object(bridge, "ROOT", target), bridge.toolkit_lock():
                self.assertEqual((target / "toolkit.lock").stat().st_size, 0)
                script = """
import bridge,sys
from pathlib import Path
bridge.ROOT=Path(sys.argv[1])
try:
 with bridge.toolkit_lock():raise AssertionError('another process entered the lock')
except bridge.ToolkitBusy:print('busy')
"""
                result = subprocess.run(
                    [os.sys.executable, "-c", script, directory],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=bridge.HIDDEN,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "busy")

    def test_desktop_launcher_checks_owner_and_sends_psf_as_one_argument(self):
        settings = creo_startup.Settings(
            Path("C:/Creo with spaces/parametric.exe"),
            Path("C:/Creo with spaces/start.psf"),
            True,
            120,
            False,
        )
        desktop = Mock()
        desktop.HWND = 42

        def session(pid, out):
            ctypes.cast(out, ctypes.POINTER(creo_startup.wintypes.DWORD))[0] = 7
            return True

        with (
            patch.dict(os.environ, {"SYSTEMROOT": "C:/Windows"}),
            patch.object(creo_startup.pythoncom, "CoInitialize") as initialize,
            patch.object(creo_startup.pythoncom, "CoUninitialize") as uninitialize,
            patch.object(creo_startup.win32com.client, "Dispatch") as dispatch,
            patch.object(
                creo_startup.win32process, "GetWindowThreadProcessId", return_value=(1, 55)
            ),
            patch.object(creo_startup, "_session", side_effect=session),
            patch.object(creo_startup, "windows_session", return_value=7),
            patch.object(
                creo_startup,
                "process_identity",
                return_value={"image": str(Path("C:/Windows/explorer.exe"))},
            ),
            patch.object(creo_startup, "_open", return_value=111),
            patch.object(creo_startup, "_user_sid", return_value="same-owner"),
            patch.object(creo_startup, "_close") as close,
        ):
            dispatch.return_value.Windows.return_value.FindWindowSW.return_value = desktop
            process = creo_startup.launch_creo(settings, Path("C:/working"))
            self.assertIsNone(process.poll())
            desktop.Document.Application.ShellExecute.assert_called_once_with(
                str(settings.executable),
                '"C:\\Creo with spaces\\start.psf"',
                str(Path("C:/working")),
                "open",
                1,
            )
            initialize.assert_called_once()
            uninitialize.assert_called_once()
            close.assert_called_once_with(111)

    def test_desktop_launcher_failure_uninitializes_without_launching(self):
        settings = creo_startup.Settings(
            Path("C:/Creo/parametric.exe"), Path("C:/Creo/start.psf"), True, 120, False
        )
        with (
            patch.object(creo_startup.pythoncom, "CoInitialize"),
            patch.object(creo_startup.pythoncom, "CoUninitialize") as uninitialize,
            patch.object(creo_startup.win32com.client, "Dispatch") as dispatch,
        ):
            dispatch.return_value.Windows.return_value.FindWindowSW.return_value = None
            with self.assertRaisesRegex(RuntimeError, "desktop is unavailable"):
                creo_startup.launch_creo(settings, Path("C:/working"))
            uninitialize.assert_called_once()

    def test_desktop_launcher_rejects_a_different_owner_and_closes_process_handle(self):
        settings = creo_startup.Settings(
            Path("C:/Creo/parametric.exe"), Path("C:/Creo/start.psf"), True, 120, False
        )
        desktop = Mock()
        desktop.HWND = 42

        def session(pid, out):
            ctypes.cast(out, ctypes.POINTER(creo_startup.wintypes.DWORD))[0] = 7
            return True

        with (
            patch.dict(os.environ, {"SYSTEMROOT": "C:/Windows"}),
            patch.object(creo_startup.pythoncom, "CoInitialize"),
            patch.object(creo_startup.pythoncom, "CoUninitialize") as uninitialize,
            patch.object(creo_startup.win32com.client, "Dispatch") as dispatch,
            patch.object(
                creo_startup.win32process, "GetWindowThreadProcessId", return_value=(1, 55)
            ),
            patch.object(creo_startup, "_session", side_effect=session),
            patch.object(creo_startup, "windows_session", return_value=7),
            patch.object(
                creo_startup,
                "process_identity",
                return_value={"image": str(Path("C:/Windows/explorer.exe"))},
            ),
            patch.object(creo_startup, "_open", return_value=111),
            patch.object(creo_startup, "_user_sid", side_effect=["other-owner", "caller-owner"]),
            patch.object(creo_startup, "_close") as close,
        ):
            dispatch.return_value.Windows.return_value.FindWindowSW.return_value = desktop
            with self.assertRaisesRegex(RuntimeError, "another user"):
                creo_startup.launch_creo(settings, Path("C:/working"))
            desktop.Document.Application.ShellExecute.assert_not_called()
            close.assert_called_once_with(111)
            uninitialize.assert_called_once()

    def test_parent_token_is_closed_after_sid_query(self):
        token = Mock()
        with (
            patch.object(creo_startup.win32security, "OpenProcessToken", return_value=token),
            patch.object(
                creo_startup.win32security,
                "GetTokenInformation",
                side_effect=RuntimeError("token query failed"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                creo_startup._user_sid(1)
        token.Close.assert_called_once()

    def test_real_process_inventory_and_identity_are_read_only(self):
        identity = creo_startup.process_identity(os.getpid())
        self.assertEqual(identity["pid"], os.getpid())
        self.assertGreater(identity["created"], 0)
        self.assertTrue(Path(identity["image"]).is_file())
        self.assertIsInstance(creo_startup.windows_session(), int)

    def test_two_processes_coordinate_one_controlled_launch(self):
        parent = ROOT / ".tmp"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="feat019_coord_", dir=parent) as directory:
            fixture = Path(directory)
            self.assertTrue(fixture.resolve().is_relative_to(ROOT))
            executable = fixture / "Creo with spaces/Parametric/bin/parametric.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"fixture")
            executable.with_suffix(".psf").write_bytes(b"fixture")
            script = """
import contextlib,json,sys,time
from pathlib import Path
from unittest.mock import patch,Mock
import bridge,creo_startup
root=Path(sys.argv[1]); flag=root/'launch-count.txt'
controller=creo_startup.CreoStartup(root/'shared')
def inventory(settings):
 return {'processes':[{'matches':True}] if flag.exists() else [],'uncertain':False}
def probe(**kwargs):
 assert flag.exists(), 'Toolkit must not start a name service in the cold MCP job'
 time.sleep(.1)
 return {'connected':flag.exists(),'connection_state':'connected' if flag.exists() else 'not_found_or_unreadable'}
def launch(*args,**kwargs):
 with flag.open('a') as f:f.write('launch\\n')
 p=Mock();p.poll.return_value=None;return p
with patch.object(bridge,'config',return_value={'creo_root':str(root/'Creo with spaces'),'creo_startup_timeout_seconds':10}),patch.object(bridge,'toolkit_lock',side_effect=lambda **kw:contextlib.nullcontext()),patch.object(bridge,'build_native'),patch.object(bridge,'native_environment',return_value={}),patch.object(bridge,'session_status',side_effect=probe),patch.object(creo_startup,'inventory',side_effect=inventory),patch.object(creo_startup,'launch_creo',side_effect=launch):
 controller.start();controller._thread.join(10)
 assert not controller._thread.is_alive()
 print(json.dumps(controller.status()))
"""
            processes = [
                subprocess.Popen(
                    [os.sys.executable, "-c", script, str(fixture)],
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    creationflags=bridge.HIDDEN,
                )
                for _ in range(2)
            ]
            try:
                results = [process.communicate(timeout=15) for process in processes]
                for process, (stdout, stderr) in zip(processes, results):
                    self.assertEqual(process.returncode, 0, stderr)
                    self.assertEqual(json.loads(stdout)["state"], "ready", (stdout, stderr))
                self.assertEqual(
                    (fixture / "launch-count.txt").read_text().splitlines(), ["launch"]
                )
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
