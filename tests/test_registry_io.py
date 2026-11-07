"""BUG-002: atomic snapshots, bounded failures and registry state transitions."""

import contextlib
import errno
import json
import os
import stat
import subprocess
import tempfile
import threading
import time
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge
import generic_bridge


def windows_error(code: int) -> OSError:
    error = PermissionError(errno.EACCES, "injected registry failure")
    error.winerror = code
    return error


class Clock:
    def __init__(self):
        self.elapsed = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.elapsed += seconds


class RegistryFixture:
    def setUp(self):
        parent = (bridge.ROOT / ".tmp").resolve()
        parent.mkdir(exist_ok=True)
        self.assertTrue(parent.is_relative_to(bridge.ROOT))
        self.fixture = tempfile.TemporaryDirectory(prefix="bug002_unit_", dir=parent)
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name)
        self.path = self.root / "job.json"
        self.old = {"text": "原始登记", "revision": 2}
        bridge.write_json(self.path, self.old)

    def assert_preserved(self):
        self.assertEqual(bridge.read_json(self.path), self.old)
        self.assertEqual(list(self.root.glob("*.tmp")), [])


class RegistryIO(RegistryFixture, unittest.TestCase):
    def test_unicode_paths_and_initial_creation_leave_only_the_target(self):
        directory = self.root / "中文目录"
        directory.mkdir()
        path = directory / "模型登记.json"
        bridge.write_json(path, self.old)
        self.assertEqual(bridge.read_json(path), self.old)
        bridge.write_json(path, {"revision": 3})
        self.assertEqual(bridge.read_json(path), {"revision": 3})
        self.assertEqual(list(directory.iterdir()), [path])

    def test_utf8_bom_and_array_callers_remain_compatible(self):
        self.path.write_text(json.dumps(self.old, ensure_ascii=False), encoding="utf-8-sig")
        self.assertEqual(bridge.read_json(self.path), self.old)
        bridge.write_json(self.path, self.old)
        self.assertFalse(self.path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.path.write_text('[1, "中文"]', encoding="utf-8")
        self.assertEqual(bridge.read_json(self.path), [1, "中文"])

    def test_missing_invalid_and_read_io_errors_propagate_without_retry(self):
        with self.assertRaises(FileNotFoundError):
            bridge.read_json(self.root / "missing.json")
        self.path.write_text("{", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            bridge.read_json(self.path)
        with patch.object(bridge, "_open_json_reader", side_effect=windows_error(5)) as opened:
            with self.assertRaises(PermissionError):
                bridge.read_json(self.path)
            self.assertEqual(opened.call_count, 1)

    @unittest.skipUnless(os.name == "nt", "Windows shared-delete handles")
    def test_open_reader_survives_replace_and_keeps_old_snapshot(self):
        with bridge._open_json_reader(self.path) as old_reader:
            bridge.write_json(self.path, {"revision": 3})
            self.assertEqual(json.load(old_reader), self.old)
            self.assertEqual(bridge.read_json(self.path), {"revision": 3})
        self.assertTrue(old_reader.closed)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    @unittest.skipUnless(os.name == "nt", "Windows sharing errors")
    def test_each_retryable_error_fails_then_succeeds(self):
        real_replace = bridge._atomic_replace
        for code in (5, 32, 33):
            with self.subTest(winerror=code):
                clock = Clock()
                calls = []

                def replace(source, target):
                    calls.append(source)
                    self.assertTrue(Path(target).is_file())
                    if len(calls) <= 2:
                        raise windows_error(code)
                    real_replace(source, target)

                with (
                    patch.object(bridge, "_atomic_replace", side_effect=replace),
                    patch.object(bridge.time, "monotonic", side_effect=clock.monotonic),
                    patch.object(bridge.time, "sleep", side_effect=clock.sleep),
                ):
                    bridge.write_json(self.path, self.old)
                self.assertEqual(len(calls), 3)
                self.assertEqual(len(set(calls)), 1)
                self.assertEqual(clock.sleeps, [0.005, 0.01])
                self.assert_preserved()

    def test_nonretryable_errors_are_immediate_and_keep_exact_old_bytes(self):
        old_bytes = self.path.read_bytes()
        for error in (
            windows_error(19),
            OSError(errno.ENOSPC, "disk full"),
            PermissionError("plain permission"),
        ):
            with (
                self.subTest(error=error),
                patch.object(bridge, "_atomic_replace", side_effect=error) as replace,
                patch.object(bridge.time, "sleep") as sleep,
            ):
                with self.assertRaises(OSError) as caught:
                    bridge.write_json(self.path, {"revision": 9})
                self.assertIs(caught.exception, error)
                self.assertEqual(replace.call_count, 1)
                sleep.assert_not_called()
                self.assertEqual(self.path.read_bytes(), old_bytes)
                self.assert_preserved()

    @unittest.skipUnless(os.name == "nt", "Windows bounded retry")
    def test_persistent_failure_uses_budget_and_preserves_other_writers_temp(self):
        clock = Clock()
        foreign = self.path.with_suffix(".json.foreign.tmp")
        foreign.write_bytes(b"other writer")
        old_bytes = self.path.read_bytes()
        with (
            patch.object(bridge, "_atomic_replace", side_effect=windows_error(5)) as replace,
            patch.object(bridge.time, "monotonic", side_effect=clock.monotonic),
            patch.object(bridge.time, "sleep", side_effect=clock.sleep),
        ):
            with self.assertRaises(PermissionError) as caught:
                bridge.write_json(self.path, {"revision": 99})
        self.assertGreater(replace.call_count, 1)
        self.assertLessEqual(replace.call_count, bridge.JSON_REPLACE_MAX_ATTEMPTS)
        self.assertAlmostEqual(clock.elapsed, bridge.JSON_REPLACE_TIMEOUT)
        self.assertLessEqual(max(clock.sleeps), 0.05)
        self.assertTrue(any("attempts=" in note for note in caught.exception.__notes__))
        self.assertEqual(self.path.read_bytes(), old_bytes)
        self.assertEqual(list(self.root.glob("*.tmp")), [foreign])
        self.assertEqual(foreign.read_bytes(), b"other writer")

    @unittest.skipUnless(os.name == "nt", "Windows attempt limit")
    def test_attempt_limit_also_bounds_a_stationary_clock(self):
        with (
            patch.object(bridge, "_atomic_replace", side_effect=windows_error(32)) as replace,
            patch.object(bridge.time, "monotonic", return_value=0),
            patch.object(bridge.time, "sleep"),
        ):
            with self.assertRaises(PermissionError):
                bridge.write_json(self.path, {})
        self.assertEqual(replace.call_count, bridge.JSON_REPLACE_MAX_ATTEMPTS)
        self.assert_preserved()

    @unittest.skipUnless(os.name == "nt", "Windows read-only attributes")
    def test_real_readonly_target_is_not_retried(self):
        self.path.chmod(stat.S_IREAD)
        try:
            with patch.object(bridge.time, "sleep") as sleep:
                with self.assertRaises(PermissionError):
                    bridge.write_json(self.path, {"revision": 99})
                sleep.assert_not_called()
            self.assert_preserved()
        finally:
            self.path.chmod(stat.S_IWRITE | stat.S_IREAD)

    def test_temp_creation_write_and_serialization_failures_preserve_target(self):
        with patch.object(Path, "open", side_effect=OSError(errno.ENOSPC, "temp create failed")):
            with self.assertRaises(OSError):
                bridge.write_json(self.path, {})
        self.assert_preserved()
        real_open = Path.open

        class BrokenStream:
            def __enter__(inner):
                inner.stream = real_open(inner.path, "x", encoding="utf-8")
                return inner

            def write(inner, content):
                inner.stream.write(content[:5])
                raise OSError(errno.ENOSPC, "partial temp write")

            def __exit__(inner, *args):
                inner.stream.close()

        def broken_open(path, *args, **kwargs):
            stream = BrokenStream()
            stream.path = path
            return stream

        with patch.object(Path, "open", new=broken_open):
            with self.assertRaises(OSError):
                bridge.write_json(self.path, {"text": "new"})
        self.assert_preserved()
        with self.assertRaises(TypeError):
            bridge.write_json(self.path, {"bad": object()})
        self.assert_preserved()

    def test_uuid_collision_does_not_remove_unowned_file(self):
        foreign = self.path.with_suffix(".json.collision.tmp")
        foreign.write_bytes(b"foreign")
        with patch.object(bridge.uuid, "uuid4") as uuid:
            uuid.return_value.hex = "collision"
            with self.assertRaises(FileExistsError):
                bridge.write_json(self.path, {})
        self.assertEqual(foreign.read_bytes(), b"foreign")
        self.assertEqual(bridge.read_json(self.path), self.old)

    def test_cleanup_failure_retains_primary_exception_and_diagnostic(self):
        error = windows_error(19)
        with (
            patch.object(bridge, "_atomic_replace", side_effect=error),
            patch.object(Path, "unlink", side_effect=PermissionError("cleanup blocked")),
        ):
            with self.assertRaises(OSError) as caught:
                bridge.write_json(self.path, {})
        self.assertIs(caught.exception, error)
        self.assertTrue(any("temporary file" in note for note in error.__notes__))

    @unittest.skipUnless(os.name == "nt", "Windows handle ownership")
    def test_reader_setup_failures_close_exactly_one_owner(self):
        with (
            patch.object(bridge.msvcrt, "open_osfhandle", side_effect=OSError("fd allocation")),
            patch.object(bridge, "_close_handle", wraps=bridge._close_handle) as close,
        ):
            with self.assertRaises(OSError):
                bridge.read_json(self.path)
            self.assertEqual(close.call_count, 1)
        with (
            patch.object(bridge.os, "fdopen", side_effect=OSError("stream allocation")),
            patch.object(bridge.os, "close", wraps=bridge.os.close) as close,
        ):
            with self.assertRaises(OSError):
                bridge.read_json(self.path)
            self.assertEqual(close.call_count, 1)
        bridge.write_json(self.path, self.old)

    @unittest.skipUnless(os.name == "nt", "Windows extended rename")
    def test_unsupported_extended_rename_falls_back_to_atomic_os_replace(self):
        def unsupported(*args):
            bridge.ctypes.set_last_error(87)
            return False

        with (
            patch.object(bridge, "_set_file_information", side_effect=unsupported),
            patch.object(bridge.os, "replace", wraps=bridge.os.replace) as replace,
        ):
            bridge.write_json(self.path, {"revision": 3})
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(bridge.read_json(self.path), {"revision": 3})
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    @unittest.skipUnless(os.name == "nt", "Windows extended rename")
    def test_native_rename_failure_closes_handle_and_keeps_old_target(self):
        def rejected(*args):
            bridge.ctypes.set_last_error(19)
            return False

        with (
            patch.object(bridge, "_set_file_information", side_effect=rejected),
            patch.object(bridge, "_close_handle", wraps=bridge._close_handle) as close,
        ):
            with self.assertRaises(OSError) as error:
                bridge.write_json(self.path, {"revision": 3})
            self.assertEqual(error.exception.winerror, 19)
            self.assertEqual(close.call_count, 1)
        self.assert_preserved()


class RegistryJobs(RegistryFixture, unittest.TestCase):
    # Keep base I/O tests in one suite; job-specific tests use the same fixture.
    def setUp(self):
        super().setUp()
        self.jobs = self.root / "jobs"
        self.models = self.root / "models"
        templates = self.root / "Common Files/templates"
        templates.mkdir(parents=True)
        (templates / "mmns_part_solid_abs.prt").write_bytes(b"template")
        stack = self.enterContext(contextlib.ExitStack())
        self.checkout = bridge.ROOT
        stack.enter_context(patch.object(bridge, "ROOT", self.root))
        stack.enter_context(patch.object(bridge, "JOBS", self.jobs))
        stack.enter_context(patch.object(generic_bridge, "MODELS", self.models))
        stack.enter_context(
            patch.object(
                bridge,
                "config",
                return_value={"creo_root": str(self.root), "native_timeout_seconds": 1},
            )
        )
        stack.enter_context(
            patch.object(
                bridge, "toolkit_lock", side_effect=lambda **kwargs: contextlib.nullcontext()
            )
        )
        stack.enter_context(
            patch.object(bridge, "build_native", return_value=self.root / "worker.exe")
        )
        stack.enter_context(patch.object(bridge, "native_environment", return_value={}))
        self.launch = stack.enter_context(patch.object(bridge.subprocess, "Popen"))

    def submit(self, **kwargs):
        return generic_bridge.submit([{"op": "set_parameters", "values": {"SIZE": 18}}], **kwargs)

    def test_simulated_native_failure_keeps_checkout_channel_health_unchanged(self):
        health = self.checkout / "build/toolkit_health.json"
        before = health.read_bytes() if health.exists() else None
        created = self.submit()
        with patch.object(
            bridge.subprocess, "run", side_effect=self.worker(created, success=False, missing=True)
        ):
            bridge.run_job(created["job_id"])
        recorded = bridge.read_json(self.root / "build/toolkit_health.json")
        self.assertFalse(recorded["connected"])
        self.assertEqual(recorded["job_id"], created["job_id"])
        self.assertEqual(health.read_bytes() if health.exists() else None, before)

    def worker(self, created, success=True, rollback=False, readonly=False, missing=False):
        def run(*args, **kwargs):
            directory = bridge.job_path(created["job_id"])
            model = generic_bridge.model_info(created["model_id"])
            part = Path(model["output_directory"]) / f"{model['model_name']}.prt.1"
            part.write_bytes(b"native model evidence")
            result = {
                "success": success,
                "part_file": str(part),
                "saved_file_reloaded_and_verified": not readonly,
                "rollback_succeeded": rollback,
                "inspection": {"healthy": True, "volume_mm3": 10},
                "aliases": {},
                "message": "native outcome",
            }
            if not missing:
                bridge.write_json(directory / "native_result.json", result)
            time.sleep(0.01)
            return subprocess.CompletedProcess(args[0], 0 if success else 1)

        return run

    def test_generic_queue_progress_terminal_and_polling_with_retry(self):
        real_replace = bridge._atomic_replace
        sources = set()
        retries = []

        def replace(source, target):
            if Path(target).name in ("job.json", "model.json") and source not in sources:
                sources.add(source)
                retries.append(target)
                raise windows_error(32)
            real_replace(source, target)

        with patch.object(bridge, "_atomic_replace", side_effect=replace):
            created = self.submit()
            model = generic_bridge.model_info(created["model_id"])
            self.assertEqual(model["pending_job"], created["job_id"])
            self.assertEqual(model["revision"], 0)
            errors = []
            reads = []
            stop = threading.Event()
            ready = threading.Event()

            def poll():
                ready.set()
                while not stop.is_set():
                    try:
                        reads.append(bridge.get_job(created["job_id"], detail="compact"))
                        bridge.list_jobs(detail="full")
                        generic_bridge.model_info(created["model_id"])
                        generic_bridge.list_models()
                    except Exception as exc:
                        errors.append(exc)

            thread = threading.Thread(target=poll)
            thread.start()
            ready.wait(timeout=2)
            try:
                with patch.object(
                    bridge.subprocess, "run", side_effect=self.worker(created)
                ) as run:
                    bridge.run_job(created["job_id"])
                self.assertEqual(run.call_count, 1)
            finally:
                stop.set()
                thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertTrue(reads)
            model = generic_bridge.model_info(created["model_id"])
            job = bridge.get_job(created["job_id"])
            self.assertEqual(model["revision"], 1)
            self.assertIsNone(model["pending_job"])
            self.assertEqual(model["last_job"], created["job_id"])
            self.assertEqual(job["status"], "succeeded")
            self.assertEqual(job["revision"], 1)
            self.assertTrue(job["result"]["saved_file_reloaded_and_verified"])
            self.assertGreaterEqual(len(retries), 5)
            self.assertEqual(list(self.root.rglob("*.tmp")), [])

    def test_modify_readonly_failure_and_unknown_preserve_revision_contract(self):
        created = self.submit()
        with patch.object(bridge.subprocess, "run", side_effect=self.worker(created)):
            bridge.run_job(created["job_id"])
        mid = created["model_id"]
        with self.assertRaisesRegex(
            ValueError,
            rf"Stale revision: model_id={mid} current_revision=1 "
            r"expected_revision=0; no job was created",
        ):
            self.submit(model_id=mid, expected_revision=0)
        for readonly, success, rollback, missing, expected_status in (
            (False, True, False, False, "succeeded"),
            (True, True, False, False, "succeeded"),
            (False, False, True, False, "failed"),
            (False, False, False, True, "unknown_outcome"),
        ):
            with self.subTest(readonly=readonly, status=expected_status):
                before = generic_bridge.model_info(mid)
                if readonly:
                    queued = generic_bridge.submit(
                        [{"op": "dump_tree", "feature": 1}], model_id=mid, readonly=True
                    )
                else:
                    queued = self.submit(model_id=mid, expected_revision=before["revision"])
                with patch.object(
                    bridge.subprocess,
                    "run",
                    side_effect=self.worker(queued, success, rollback, readonly, missing),
                ):
                    bridge.run_job(queued["job_id"])
                after = generic_bridge.model_info(mid)
                self.assertEqual(
                    after["revision"],
                    before["revision"] + int(success and not readonly and not missing),
                )
                self.assertEqual(
                    after["pending_job"],
                    queued["job_id"] if expected_status == "unknown_outcome" else None,
                )
                self.assertEqual(after["last_job"], queued["job_id"])
                self.assertEqual(bridge.get_job(queued["job_id"])["status"], expected_status)

    def test_terminal_model_failure_preserves_native_result_and_pending(self):
        created = self.submit()
        old_model = (generic_bridge.model_path(created["model_id"]) / "model.json").read_bytes()
        real_replace = bridge._atomic_replace

        def replace(source, target):
            if Path(target).name == "model.json":
                raise windows_error(19)
            real_replace(source, target)

        with (
            patch.object(bridge, "_atomic_replace", side_effect=replace),
            patch.object(bridge.subprocess, "run", side_effect=self.worker(created)) as run,
        ):
            with self.assertRaises(OSError) as error:
                bridge.run_job(created["job_id"])
        self.assertEqual(run.call_count, 1)
        self.assertTrue(any("model.json" in note for note in error.exception.__notes__))
        self.assertIn(
            "JSON atomic replace failed", "".join(traceback.format_exception(error.exception))
        )
        path = generic_bridge.model_path(created["model_id"]) / "model.json"
        self.assertEqual(path.read_bytes(), old_model)
        job = bridge.get_job(created["job_id"])
        self.assertEqual(job["status"], "running")
        native = bridge.read_json(bridge.job_path(created["job_id"]) / "native_result.json")
        self.assertTrue(native["success"])
        self.assertTrue(native["saved_file_reloaded_and_verified"])
        self.assertEqual(list(self.root.rglob("*.tmp")), [])

    def test_progress_write_failure_does_not_start_native_worker(self):
        created = self.submit()
        real_replace = bridge._atomic_replace

        def replace(source, target):
            if (
                Path(target).name == "job.json"
                and bridge.read_json(Path(source))["status"] == "running"
            ):
                raise windows_error(19)
            real_replace(source, target)

        with (
            patch.object(bridge, "_atomic_replace", side_effect=replace),
            patch.object(bridge.subprocess, "run") as run,
        ):
            bridge.run_job(created["job_id"])
        run.assert_not_called()
        job = bridge.get_job(created["job_id"])
        model = generic_bridge.model_info(created["model_id"])
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["result"]["failed_model_cleanup"]["status"], "unknown")
        self.assertFalse(job["result"]["failed_model_cleanup"]["attempted"])
        self.assertEqual(model["revision"], 0)
        self.assertIsNone(model["pending_job"])

    def test_terminal_job_failure_keeps_completed_model_and_native_evidence(self):
        created = self.submit()
        real_replace = bridge._atomic_replace

        def replace(source, target):
            if (
                Path(target).name == "job.json"
                and bridge.read_json(Path(source))["status"] == "succeeded"
            ):
                raise windows_error(19)
            real_replace(source, target)

        with (
            patch.object(bridge, "_atomic_replace", side_effect=replace),
            patch.object(bridge.subprocess, "run", side_effect=self.worker(created)) as run,
        ):
            with self.assertRaises(OSError):
                bridge.run_job(created["job_id"])
        self.assertEqual(run.call_count, 1)
        model = generic_bridge.model_info(created["model_id"])
        self.assertEqual(model["revision"], 1)
        self.assertIsNone(model["pending_job"])
        self.assertEqual(bridge.get_job(created["job_id"])["status"], "running")
        self.assertTrue((bridge.job_path(created["job_id"]) / "native_result.json").is_file())

    def test_legacy_job_queue_and_terminal_use_atomic_writer(self):
        created = bridge.create_job(bridge.validate_spec(20, 10, 2, 0, []))
        directory = bridge.job_path(created["job_id"])

        def run(*args, **kwargs):
            part = directory / "output/plate.prt.1"
            part.write_bytes(b"legacy native evidence")
            bridge.write_json(
                directory / "native_result.json",
                {
                    "success": True,
                    "saved_file_reloaded_and_verified": True,
                    "part_file": str(part),
                    "preview_code": 0,
                },
            )
            return subprocess.CompletedProcess(args[0], 0)

        with patch.object(bridge.subprocess, "run", side_effect=run):
            bridge.run_job(created["job_id"])
        self.assertEqual(bridge.get_job(created["job_id"])["status"], "succeeded")
        self.assertEqual(list(self.root.rglob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
