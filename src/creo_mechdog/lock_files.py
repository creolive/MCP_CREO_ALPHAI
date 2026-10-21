"""Unified Windows lock-file opening shared by every byte-range lock (BUG-057).

The Toolkit channel lock (``toolkit.lock``) and the startup coordination lock
(``startup.lock``) keep separate paths but one open discipline:

* prefer ``OPEN_EXISTING``; when the file does not exist, create it once with
  ``CREATE_NEW``;
* on a first-create collision (``ERROR_FILE_EXISTS``) or an access denial
  during that first create (``ERROR_ACCESS_DENIED``), fall back exactly once to
  a shared ``OPEN_EXISTING`` open — the parallel winner has usually created the
  file by then;
* any other failure (ACL on an existing file, sharing violation, I/O error)
  keeps its original error code; it is never reported as channel contention.

Lock files are permanent, are never deleted by this service, and are opened
without ``FILE_SHARE_DELETE`` so every contender stays on the same file
identity while any handle is open. Only the non-blocking byte lock taken by the
caller afterwards means "busy"; opening never does.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

if os.name == "nt":
    import msvcrt
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _create_file = _kernel32.CreateFileW
    _create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    _create_file.restype = wintypes.HANDLE
    _close_handle = _kernel32.CloseHandle
    _close_handle.argtypes = (wintypes.HANDLE,)
    _close_handle.restype = wintypes.BOOL

_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_SHARE_READ_WRITE = 0x1 | 0x2  # no FILE_SHARE_DELETE by design
_OPEN_EXISTING = 3
_CREATE_NEW = 1
_ERROR_FILE_NOT_FOUND = 2
_ERROR_ACCESS_DENIED = 5
_ERROR_FILE_EXISTS = 80
_INVALID_HANDLE = ctypes.c_void_p(-1).value


def _open_once(path: Path, disposition: int):
    handle = _create_file(
        str(path), _GENERIC_READ | _GENERIC_WRITE, _SHARE_READ_WRITE, None, disposition, 0x80, None
    )
    if handle == _INVALID_HANDLE:
        error = ctypes.WinError(ctypes.get_last_error())
        error.filename = str(path)
        raise error
    return handle


def _descriptor(handle, path: Path):
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
    except BaseException:
        _close_handle(handle)
        raise
    try:
        return os.fdopen(descriptor, "r+b", buffering=0)
    except BaseException:
        os.close(descriptor)
        raise


def open_lock_file(path: Path):
    """Open a permanent lock file for non-blocking byte locking.

    Returns an unbuffered binary stream positioned at offset 0. Raises OSError
    with the original Windows error code when no open discipline succeeds.
    """
    path = Path(path)
    if os.name != "nt":
        return path.open("a+b", buffering=0)
    try:
        handle = _open_once(path, _OPEN_EXISTING)
    except OSError as existing_error:
        if existing_error.winerror != _ERROR_FILE_NOT_FOUND:
            raise
        try:
            handle = _open_once(path, _CREATE_NEW)
        except OSError as create_error:
            # Only the first-create race qualifies for the single shared-open
            # fallback: a lost CREATE_NEW race (file now exists) or an access
            # denial while the file is being created for the first time.
            if create_error.winerror not in (_ERROR_FILE_EXISTS, _ERROR_ACCESS_DENIED):
                raise
            try:
                handle = _open_once(path, _OPEN_EXISTING)
            except OSError:
                # Keep the original create-phase error code; the fallback's
                # failure would only mask it.
                raise create_error from None
        return _descriptor(handle, path)
    return _descriptor(handle, path)
