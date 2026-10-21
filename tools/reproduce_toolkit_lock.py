"""DEV-040 / BUG-057: isolated Windows file-open and byte-lock diagnostics.

This script uses the standard library and a TemporaryDirectory plus, for the
production path only, ``creo_mechdog.lock_files.open_lock_file``. It reads no
service configuration, jobs, models, or Toolkit data. Each attempt opens once
and locks once; repeated iterations are independent observations, not retries.
The CRT ``open("a+b")`` route stays as a control and the production open route
(OPEN_EXISTING -> CREATE_NEW -> one shared-open fallback, BUG-057) are run and
reported separately. Controlled failures do not establish BUG-057's cause.
"""

import argparse
import ctypes
import json
import os
import platform
import sys
import tempfile
import threading
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creo_mechdog.lock_files import open_lock_file  # noqa: E402

if os.name == "nt":
    import msvcrt
    from ctypes import wintypes


class WindowsErrors:
    """Read the calling thread's UCRT error before another operation replaces it."""

    def __init__(self) -> None:
        self.runtime = ctypes.CDLL("ucrtbase")
        self.get_error = self.runtime._get_doserrno
        self.get_error.argtypes = [ctypes.POINTER(ctypes.c_ulong)]
        self.get_error.restype = ctypes.c_int
        self.set_error = self.runtime._set_doserrno
        self.set_error.argtypes = [ctypes.c_ulong]
        self.set_error.restype = ctypes.c_int

    def reset(self) -> None:
        self.set_error(0)

    def capture(self, exc: OSError, phase: str) -> dict[str, Any]:
        value = ctypes.c_ulong()
        status = self.get_error(ctypes.byref(value))
        return {
            "phase": phase,
            "exception_type": type(exc).__name__,
            "errno": exc.errno,
            "winerror": getattr(exc, "winerror", None),
            "ucrt_doserrno": value.value if status == 0 else None,
            "ucrt_get_status": status,
            "message": str(exc),
        }


class WindowsFiles:
    GENERIC_READ_WRITE = 0x80000000 | 0x40000000
    DELETE = 0x00010000
    SHARE_READ_WRITE = 1 | 2
    SHARE_DELETE = 4
    OPEN_EXISTING = 3
    OPEN_ALWAYS = 4
    NORMAL = 0x80

    def __init__(self) -> None:
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.create = self.kernel.CreateFileW
        self.create.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self.create.restype = wintypes.HANDLE
        self.close = self.kernel.CloseHandle
        self.close.argtypes = [wintypes.HANDLE]
        self.close.restype = wintypes.BOOL
        self.delete = self.kernel.DeleteFileW
        self.delete.argtypes = [wintypes.LPCWSTR]
        self.delete.restype = wintypes.BOOL
        self.set_info = self.kernel.SetFileInformationByHandle
        self.set_info.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        self.set_info.restype = wintypes.BOOL
        self.get_info = self.kernel.GetFileInformationByHandleEx
        self.get_info.argtypes = self.set_info.argtypes
        self.get_info.restype = wintypes.BOOL
        self.invalid = ctypes.c_void_p(-1).value

    @contextmanager
    def handle(self, path: Path, *, sharing: int, delete_access: bool = False) -> Iterator[int]:
        access = self.GENERIC_READ_WRITE | (self.DELETE if delete_access else 0)
        handle = self.create(
            str(path), access, sharing, None, self.OPEN_EXISTING, self.NORMAL, None
        )
        if handle == self.invalid:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield handle
        finally:
            if not self.close(handle):
                raise ctypes.WinError(ctypes.get_last_error())

    def mark_delete_pending(self, handle: int) -> None:
        # FILE_DISPOSITION_INFO has one BOOLEAN; class 4 requests legacy disposition.
        disposition = ctypes.c_ubyte(1)
        if not self.set_info(handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
            raise ctypes.WinError(ctypes.get_last_error())

    def standard_info(self, handle: int) -> dict[str, Any]:
        class StandardInfo(ctypes.Structure):
            _fields_ = [
                ("allocation_size", ctypes.c_longlong),
                ("end_of_file", ctypes.c_longlong),
                ("number_of_links", wintypes.DWORD),
                ("delete_pending", ctypes.c_ubyte),
                ("directory", ctypes.c_ubyte),
            ]

        information = StandardInfo()
        if not self.get_info(handle, 1, ctypes.byref(information), ctypes.sizeof(information)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {
            "api": "GetFileInformationByHandleEx(FileStandardInfo)",
            "delete_pending": bool(information.delete_pending),
            "number_of_links": information.number_of_links,
        }

    def native_open_error(self, path: Path) -> dict[str, Any]:
        """Independent CreateFileW control; its GetLastError is not UCRT doserrno."""
        handle = self.create(
            str(path),
            self.GENERIC_READ_WRITE,
            self.SHARE_READ_WRITE,
            None,
            self.OPEN_ALWAYS,
            self.NORMAL,
            None,
        )
        if handle == self.invalid:
            return {"api": "CreateFileW", "opened": False, "winerror": ctypes.get_last_error()}
        if not self.close(handle):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"api": "CreateFileW", "opened": True, "winerror": None}


def crt_open(path: Path):
    """Control route: the CRT append/create open the pre-0.4.6 code used."""
    return path.open("a+b")


def production_open(path: Path):
    """Production route: the shared lock-file open discipline (BUG-057)."""
    return open_lock_file(path)


def attempt(path: Path, errors: WindowsErrors, opener=crt_open) -> dict[str, Any]:
    """One open and one LK_NBLCK attempt, with no retries."""
    errors.reset()
    try:
        stream = opener(path)
    except OSError as exc:
        return {"outcome": "open_error", "error": errors.capture(exc, "open")}
    with stream:
        stream.seek(0)
        errors.reset()
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            error = errors.capture(exc, "locking")
            # EACCES alone also describes sharing/delete-pending open failures.
            outcome = "lock_busy" if error["ucrt_doserrno"] == 33 else "lock_error"
            return {"outcome": outcome, "error": error}
        try:
            return {"outcome": "acquired"}
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def compete(
    path: Path, errors: WindowsErrors, executor: ThreadPoolExecutor, opener=crt_open
) -> list[dict[str, Any]]:
    start = threading.Barrier(2, timeout=10)
    attempted = threading.Barrier(2, timeout=10)

    def contender(number: int) -> dict[str, Any]:
        stream = None
        acquired = False
        result: dict[str, Any] = {"contender": number}
        try:
            start.wait()
            errors.reset()
            try:
                stream = opener(path)
            except OSError as exc:
                result.update(outcome="open_error", error=errors.capture(exc, "open"))
            if stream is not None:
                stream.seek(0)
                errors.reset()
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    error = errors.capture(exc, "locking")
                    result.update(
                        outcome="lock_busy" if error["ucrt_doserrno"] == 33 else "lock_error",
                        error=error,
                    )
                else:
                    acquired = True
                    result["outcome"] = "acquired"
            # Keep the winner's byte lock until both nonblocking attempts finish.
            attempted.wait()
            return result
        finally:
            if stream is not None:
                try:
                    if acquired:
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                finally:
                    stream.close()

    futures = [executor.submit(contender, number) for number in (1, 2)]
    # The executor is joined before TemporaryDirectory cleanup, including failures.
    return [future.result(timeout=30) for future in futures]


def competition_case(
    root: Path,
    name: str,
    initial: bytes | None,
    iterations: int,
    errors: WindowsErrors,
    opener=crt_open,
    label: str = "crt_a_plus_b",
) -> dict[str, Any]:
    directory = root / f"{name}-{label}"
    directory.mkdir()
    persistent = directory / "toolkit.lock"
    if initial is not None:
        persistent.write_bytes(initial)
    identity = persistent.stat().st_ino if initial is not None else None
    outcomes: Counter[str] = Counter()
    pairs: Counter[str] = Counter()
    failures: dict[str, dict[str, Any]] = {}
    unexpected = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        for iteration in range(iterations):
            path = directory / f"toolkit-{iteration}.lock" if initial is None else persistent
            results = compete(path, errors, executor, opener)
            pair = "+".join(sorted(result["outcome"] for result in results))
            pairs[pair] += 1
            if pair != "acquired+lock_busy":
                unexpected.append({"iteration": iteration, "attempts": results})
            for result in results:
                outcomes[result["outcome"]] += 1
                if "error" not in result:
                    continue
                error = result["error"]
                # Paths vary for absent-file iterations; group by actual error identity.
                signature = json.dumps(
                    {key: value for key, value in error.items() if key != "message"}
                )
                if signature not in failures:
                    failures[signature] = {
                        **error,
                        "count": 0,
                        "first_iteration": iteration,
                        "first_contender": result["contender"],
                    }
                failures[signature]["count"] += 1
    remaining = list(directory.iterdir())
    return {
        "name": name,
        "open_route": label,
        "iterations": iterations,
        "initial_state": "absent" if initial is None else f"existing_{len(initial)}_bytes",
        "outcomes": dict(outcomes),
        "pair_outcomes": dict(pairs),
        "errors": list(failures.values()),
        "unexpected_iterations": unexpected,
        "files_retained_until_cleanup": len(remaining),
        "expected_retained_files": iterations if initial is None else 1,
        "existing_file_identity_preserved": persistent.stat().st_ino == identity
        if initial is not None
        else None,
        "existing_file_bytes_preserved": persistent.read_bytes() == initial
        if initial is not None
        else None,
    }


def controls(root: Path, errors: WindowsErrors) -> dict[str, Any]:
    windows = WindowsFiles()
    locked = root / "held-byte.lock"
    locked.touch()
    with locked.open("a+b") as holder:
        holder.seek(0)
        msvcrt.locking(holder.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                held_byte_crt = executor.submit(attempt, locked, errors).result(timeout=30)
                held_byte_production = executor.submit(
                    attempt, locked, errors, production_open
                ).result(timeout=30)
            errors.reset()
            try:
                locked.unlink()
            except OSError as exc:
                unlink = {"deleted": False, "error": errors.capture(exc, "unlink")}
            else:
                unlink = {"deleted": True}
        finally:
            holder.seek(0)
            msvcrt.locking(holder.fileno(), msvcrt.LK_UNLCK, 1)

    exclusive = root / "exclusive-sharing.lock"
    exclusive.touch()
    with windows.handle(exclusive, sharing=0):
        share_conflict = attempt(exclusive, errors)
        share_conflict_production = attempt(exclusive, errors, production_open)
        native_share = windows.native_open_error(exclusive)

    deleted = root / "deletefile-held-open.lock"
    deleted.touch()
    with windows.handle(
        deleted,
        sharing=windows.SHARE_READ_WRITE | windows.SHARE_DELETE,
        delete_access=True,
    ) as handle:
        if not windows.delete(str(deleted)):
            raise ctypes.WinError(ctypes.get_last_error())
        deletefile_info = windows.standard_info(handle)
        deletefile_attempt = attempt(deleted, errors)
        deletefile_attempt_production = attempt(deleted, errors, production_open)
        native_deletefile = windows.native_open_error(deleted)

    pending = root / "delete-pending.lock"
    pending.touch()
    with windows.handle(
        pending,
        sharing=windows.SHARE_READ_WRITE | windows.SHARE_DELETE,
        delete_access=True,
    ) as handle:
        windows.mark_delete_pending(handle)
        pending_info = windows.standard_info(handle)
        delete_pending = attempt(pending, errors)
        delete_pending_production = attempt(pending, errors, production_open)
        native_pending = windows.native_open_error(pending)
    return {
        "held_byte_lock": {
            "attempt_crt": held_byte_crt,
            "attempt_production": held_byte_production,
            "unlink_while_handle_open": unlink,
            "file_retained_after_release": locked.exists(),
        },
        "controlled_share_conflict": {
            "holder_share_mode": 0,
            "attempt_crt": share_conflict,
            "attempt_production": share_conflict_production,
            "native_open_control": native_share,
            "after_holder_closed": attempt(exclusive, errors),
        },
        "deletefile_with_delete_shared_handle": {
            "marked_by": "DeleteFileW while FILE_SHARE_DELETE handle remains open",
            "original_handle_state": deletefile_info,
            "attempt_crt": deletefile_attempt,
            "attempt_production": deletefile_attempt_production,
            "native_open_control": native_deletefile,
            "path_exists_after_holder_closed": deleted.exists(),
        },
        "controlled_delete_pending": {
            "marked_by": "SetFileInformationByHandle(FileDispositionInfo, DeleteFile=TRUE)",
            "original_handle_state": pending_info,
            "attempt_crt": delete_pending,
            "attempt_production": delete_pending_production,
            "native_open_control": native_pending,
            "file_deleted_after_holder_closed": not pending.exists(),
        },
    }


def positive_integer(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("iterations must be at least 1")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=positive_integer, default=1000)
    parser.add_argument("--output", type=Path, help="optional JSON report destination")
    args = parser.parse_args()
    report: dict[str, Any] = {
        "work_item": "DEV-040 / BUG-057",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version,
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "windows_version": platform.win32_ver(),
            "windows_edition": platform.win32_edition(),
            "architecture": platform.machine(),
        },
        "scope": {
            "filesystem_only": True,
            "service_imported": "production route only (creo_mechdog.lock_files)",
            "toolkit_connected": False,
            "repository_runtime_data_accessed": False,
            "attempts_retried": False,
            "open_routes": (
                "crt_a_plus_b (control) and production_open_lock_file "
                "(OPEN_EXISTING -> CREATE_NEW -> one shared-open fallback) run "
                "separately for every case"
            ),
            "doserrno_source": "ucrtbase._get_doserrno on the failing thread",
            "lock_busy_basis": "locking phase and UCRT doserrno 33 (ERROR_LOCK_VIOLATION)",
        },
        "interpretation": (
            "Controlled sharing/delete-pending failures demonstrate mechanisms only. "
            "They do not prove that either mechanism caused the reported BUG-057 failure."
        ),
    }
    if os.name != "nt":
        report.update(status="unsupported", reason="msvcrt and WinAPI controls require Windows")
        exit_code = 2
    else:
        errors = WindowsErrors()
        with tempfile.TemporaryDirectory(prefix="dev040-lock-") as directory:
            root = Path(directory)
            report["competition"] = [
                competition_case(
                    root, name, initial, args.iterations, errors, opener=opener, label=label
                )
                for name, initial in (("absent", None), ("empty", b""), ("one_byte", b"\0"))
                for label, opener in (("crt_a_plus_b", crt_open), ("production", production_open))
            ]
            report["controls"] = controls(root, errors)
        report["temporary_directory_cleaned_after_all_handles_and_threads_closed"] = True
        reproduced = any(case["outcomes"].get("open_error") for case in report["competition"])
        report["competition_open_error_observed"] = reproduced
        report["status"] = "completed"
        exit_code = 0
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
