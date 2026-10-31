"""Bounded self-exit for the stdio MCP server once its client is gone (BUG-092).

Reproduced offline (``tests/unit/test_stdio_lifecycle.py``): when the client
stops consuming stdout/stderr, the transport's wire writer ends up blocked in
``WriteFile`` on the full stdout pipe. The ``stdio_server`` task group can then
never join, ``mcp.run()`` never returns, and the server keeps both pipe ends
while every outer harness hangs. Thread dumps locate the holder precisely: one
non-daemon AnyIO worker thread stuck in the blocking write, with the asyncio
main loop merely idle — so daemon-thread cleanup cannot unwind it and the
natural exit path is stuck behind an unstoppable pipe write.

``StdioExitGuard`` closes that gap at the server's lifecycle boundary. It dups
the wire stdin handle before the transport claims fd 0 and watches it without
consuming data (``PeekNamedPipe``). Once the client side is gone (EOF: closed
stdin, crashed client, or an abruptly killed driver), the guard:

1. grants a short grace so in-flight submission bookkeeping (accepted job
   registration) and any natural teardown can finish;
2. cancels pending pipe I/O of the transport's worker threads so a stuck
   write fails fast and the natural exit path may run;
3. force-exits this process after a bounded window if it is still alive.

It never terminates child processes and never walks the Python process tree:
accepted modelling jobs run as independent ``bridge.py run-job`` runner
processes and must keep running to record their own terminal state after this
server is gone. Nothing is written at force-exit time — a blocked stdio pipe
would make even a final log line hang the exit.
"""

from __future__ import annotations

import ctypes
import os
import threading

#: Grace after wire-EOF before unblocking stuck I/O (seconds).
EOF_GRACE_SECONDS = 1.5

#: Extra bounded window after unblocking before force-exit (seconds).
FORCE_EXIT_SECONDS = 2.0

#: Wire-stdin EOF poll interval (seconds).
POLL_INTERVAL_SECONDS = 0.2

if os.name == "nt":  # pragma: no branch - this project targets Windows
    import msvcrt
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _peek_named_pipe = _kernel32.PeekNamedPipe
    _peek_named_pipe.argtypes = (
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    )
    _peek_named_pipe.restype = wintypes.BOOL
    _open_thread = _kernel32.OpenThread
    _open_thread.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _open_thread.restype = wintypes.HANDLE
    _cancel_sync_io = _kernel32.CancelSynchronousIo
    _cancel_sync_io.argtypes = (wintypes.HANDLE,)
    _cancel_sync_io.restype = wintypes.BOOL
    _close_handle = _kernel32.CloseHandle
    _close_handle.argtypes = (wintypes.HANDLE,)
    _close_handle.restype = wintypes.BOOL

_THREAD_TERMINATE = 0x0001
_ERROR_BROKEN_PIPE = 109
_ERROR_PIPE_NOT_CONNECTED = 233
_ERROR_INVALID_FUNCTION = 1
_ERROR_INVALID_HANDLE = 6
_ERROR_NOT_FOUND = 1168


def stdin_write_end_closed(fd: int) -> bool | None:
    """Whether the pipe behind ``fd`` has no live writer and no pending data.

    ``True`` only when the peer closed and the buffered bytes were consumed
    (the transport's reader drains the wire), ``False`` while the pipe is
    alive, and ``None`` when ``fd`` is not a peekable pipe (console or file
    stdin — force-exit then stays inactive and only natural exit applies).
    """
    if os.name != "nt":  # pragma: no cover - Windows-only project
        return None
    try:
        handle = msvcrt.get_osfhandle(fd)
    except (OSError, ValueError):
        return None
    available = wintypes.DWORD()
    if _peek_named_pipe(handle, None, 0, None, ctypes.byref(available), None):
        return False
    error = ctypes.get_last_error()
    if error in (_ERROR_BROKEN_PIPE, _ERROR_PIPE_NOT_CONNECTED):
        return True
    if error in (_ERROR_INVALID_FUNCTION, _ERROR_INVALID_HANDLE):
        return None
    return False


def cancel_synchronous_io() -> int:
    """Cancel pending pipe I/O of the transport's worker threads.

    Only AnyIO worker threads (``anyio.wrap_file`` runs the wire writes there)
    are targeted: business writes run on other threads and must never be cut
    off mid-write. Idle threads report ``ERROR_NOT_FOUND`` and are unaffected;
    this never terminates any thread or process. Returns the number of thread
    handles targeted.
    """
    if os.name != "nt":  # pragma: no cover - Windows-only project
        return 0
    targeted = 0
    for thread in threading.enumerate():
        ident = thread.ident
        if ident is None or not thread.name.startswith("AnyIO worker thread"):
            continue
        handle = _open_thread(_THREAD_TERMINATE, False, ident)
        if not handle:
            continue
        try:
            if _cancel_sync_io(handle):
                targeted += 1
            else:
                ctypes.get_last_error()  # ERROR_NOT_FOUND: no pending sync I/O
        finally:
            _close_handle(handle)
    return targeted


class StdioExitGuard:
    """Watches wire-stdin EOF and bounds the server's self-exit after it."""

    def __init__(
        self,
        *,
        grace_seconds: float = EOF_GRACE_SECONDS,
        force_seconds: float = FORCE_EXIT_SECONDS,
        poll_seconds: float = POLL_INTERVAL_SECONDS,
    ) -> None:
        self._grace_seconds = grace_seconds
        self._force_seconds = force_seconds
        self._poll_seconds = poll_seconds
        self._wire_stdin: int | None = None
        self._thread: threading.Thread | None = None

    @property
    def active(self) -> bool:
        """Whether EOF watching is active (stdin is a peekable pipe)."""
        return self._wire_stdin is not None

    def install(self) -> bool:
        """Duplicate the wire stdin and start the daemon watcher.

        Must run before the transport claims fd 0. Returns ``False`` (guard
        inactive) when stdin is not a peekable pipe or cannot be duplicated.
        """
        if self._thread is not None:
            return self.active
        try:
            wire = os.dup(0)
        except OSError:
            return False
        self._wire_stdin = wire
        if stdin_write_end_closed(wire) is None:
            os.close(wire)
            self._wire_stdin = None
            return False
        self._thread = threading.Thread(target=self._watch, name="stdio-exit-guard", daemon=True)
        self._thread.start()
        return True

    def _watch(self) -> None:
        wire = self._wire_stdin
        if wire is None:  # pragma: no cover - install() guards this
            return
        while True:
            state = stdin_write_end_closed(wire)
            if state is None:  # pragma: no cover - re-check after install
                return
            if state:
                break
            self._sleep(self._poll_seconds)
        # Client gone: allow in-flight bookkeeping and natural teardown first.
        self._sleep(self._grace_seconds)
        cancel_synchronous_io()
        self._sleep(self._force_seconds)
        # Last resort: a stuck worker thread (blocked pipe write) can keep the
        # interpreter alive forever. Only this process ends; child processes
        # (accepted job runners) keep running and record their terminal state.
        os._exit(0)

    @staticmethod
    def _sleep(seconds: float) -> None:
        # Interruptible sleep; the guard thread is daemon, so process exit is
        # never blocked by it.
        threading.Event().wait(seconds)
