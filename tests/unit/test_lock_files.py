"""BUG-057: unified lock-file open discipline and startup coordination classes."""

import errno
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import creo_mechdog.lock_files as lock_files


def _os_error(winerror: int) -> OSError:
    error = OSError(winerror, f"simulated winerror {winerror}")
    error.winerror = winerror
    return error


@unittest.skipIf(os.name != "nt", "Windows lock discipline")
class OpenLockFile(unittest.TestCase):
    def test_absent_file_created_with_create_new(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "startup.lock"
            stream = lock_files.open_lock_file(path)
            with stream:
                self.assertTrue(path.is_file())

    def test_existing_file_opened_without_recreate(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "toolkit.lock"
            path.write_bytes(b"\0")
            before = path.stat().st_ino
            stream = lock_files.open_lock_file(path)
            with stream:
                self.assertEqual(path.stat().st_ino, before)
                self.assertEqual(path.read_bytes(), b"\0")

    def test_first_create_collision_falls_back_once_to_shared_open(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "toolkit.lock"
            dispositions = []

            def fake_open_once(target, disposition):
                dispositions.append(disposition)
                if disposition == lock_files._OPEN_EXISTING:
                    if len(dispositions) == 1:
                        raise _os_error(lock_files._ERROR_FILE_NOT_FOUND)
                    return "handle-after-fallback"
                if disposition == lock_files._CREATE_NEW:
                    # The parallel winner created the file between our checks.
                    raise _os_error(lock_files._ERROR_FILE_EXISTS)
                raise AssertionError(disposition)

            with (
                patch.object(lock_files, "_open_once", side_effect=fake_open_once),
                patch.object(lock_files, "_descriptor", return_value=object()) as descriptor,
            ):
                stream = lock_files.open_lock_file(path)
            self.assertIs(stream, descriptor.return_value)
            self.assertEqual(
                dispositions,
                [
                    lock_files._OPEN_EXISTING,
                    lock_files._CREATE_NEW,
                    lock_files._OPEN_EXISTING,
                ],
            )

    def test_fallback_failure_keeps_original_create_phase_error(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "startup.lock"
            dispositions = []

            def fake_open_once(target, disposition):
                dispositions.append(disposition)
                if disposition == lock_files._OPEN_EXISTING:
                    if len(dispositions) == 1:
                        raise _os_error(lock_files._ERROR_FILE_NOT_FOUND)
                    # The single shared-open fallback also fails.
                    raise _os_error(lock_files._ERROR_ACCESS_DENIED)
                # First-create access denial triggers the fallback.
                raise _os_error(lock_files._ERROR_ACCESS_DENIED)

            with patch.object(lock_files, "_open_once", side_effect=fake_open_once):
                with self.assertRaises(OSError) as raised:
                    lock_files.open_lock_file(path)
            self.assertEqual(
                dispositions,
                [
                    lock_files._OPEN_EXISTING,
                    lock_files._CREATE_NEW,
                    lock_files._OPEN_EXISTING,
                ],
            )
            # The original create-phase code is kept; the fallback failure does
            # not mask it.
            self.assertEqual(raised.exception.winerror, lock_files._ERROR_ACCESS_DENIED)

    def test_existing_file_acl_error_is_raised_without_fallback(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "toolkit.lock"
            path.write_bytes(b"")
            dispositions = []

            def fake_open_once(target, disposition):
                dispositions.append(disposition)
                raise _os_error(lock_files._ERROR_ACCESS_DENIED)

            with patch.object(lock_files, "_open_once", side_effect=fake_open_once):
                with self.assertRaises(OSError) as raised:
                    lock_files.open_lock_file(path)
            self.assertEqual(dispositions, [lock_files._OPEN_EXISTING])
            self.assertEqual(raised.exception.winerror, lock_files._ERROR_ACCESS_DENIED)

    def test_create_non_collision_error_is_raised(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "startup.lock"

            def fake_open_once(target, disposition):
                if disposition == lock_files._OPEN_EXISTING:
                    raise _os_error(lock_files._ERROR_FILE_NOT_FOUND)
                raise _os_error(32)  # sharing violation during create

            with patch.object(lock_files, "_open_once", side_effect=fake_open_once):
                with self.assertRaises(OSError) as raised:
                    lock_files.open_lock_file(path)
            self.assertEqual(raised.exception.winerror, 32)

    def test_opened_stream_shares_read_write_without_delete(self):
        # Another reader/writer must stay able to open the same lock file while
        # a contender holds it open; only the byte lock means busy.
        import msvcrt

        with TemporaryDirectory() as directory:
            path = Path(directory) / "toolkit.lock"
            first = lock_files.open_lock_file(path)
            with first:
                first.seek(0)
                msvcrt.locking(first.fileno(), msvcrt.LK_NBLCK, 1)
                try:
                    second = lock_files.open_lock_file(path)
                    with second:
                        second.seek(0)
                        with self.assertRaises(OSError) as raised:
                            msvcrt.locking(second.fileno(), msvcrt.LK_NBLCK, 1)
                        self.assertIn(
                            raised.exception.errno,
                            (errno.EACCES, errno.EAGAIN, errno.EDEADLK),
                        )
                finally:
                    first.seek(0)
                    msvcrt.locking(first.fileno(), msvcrt.LK_UNLCK, 1)


@unittest.skipIf(os.name != "nt", "Windows startup coordination")
class CoordinatorLockClassification(unittest.TestCase):
    def test_open_failure_is_lock_access_error_not_busy_or_config(self):
        import creo_startup

        with TemporaryDirectory() as directory:
            target = Path(directory)
            # A directory named startup.lock makes every open fail with access
            # denied, which must surface as CoordinatorLockError.
            (target / "startup.lock").mkdir()
            with self.assertRaises(creo_startup.CoordinatorLockError) as raised:
                with creo_startup.coordination_lock(target):
                    pass
            payload = raised.exception.payload
            self.assertEqual(payload["kind"], "lock_access_error")
            self.assertEqual(payload["phase"], "open")
            self.assertIsNotNone(payload["winerror"])

    def test_byte_lock_contention_stays_coordinator_busy(self):
        import msvcrt

        import creo_startup

        with TemporaryDirectory() as directory:
            target = Path(directory)
            holder = creo_startup.open_lock_file(target / "startup.lock")
            with holder:
                holder.seek(0)
                msvcrt.locking(holder.fileno(), msvcrt.LK_NBLCK, 1)
                try:
                    with self.assertRaises(creo_startup.CoordinatorBusy):
                        with creo_startup.coordination_lock(target):
                            pass
                finally:
                    holder.seek(0)
                    msvcrt.locking(holder.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    unittest.main()
