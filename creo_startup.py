"""Bounded background Creo startup, coordinated across local MCP processes."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import logging
import msvcrt
import os
import subprocess
import threading
import time
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import pythoncom
import pywintypes
import win32com.client
import win32process
import win32security

import bridge
from creo_mechdog.lock_files import open_lock_file
from creo_mechdog.startup_state import StartupStateError, archive_preboot_state, read_startup_state
from creo_mechdog.window_observations import connection_guidance, window_observations
from creo_mechdog.windows_boot import BOOT_QUERY_BUDGET_SECONDS, boot_info

LOG = logging.getLogger(__name__)
ACTIVE = {
    "checking",
    "waiting_for_channel",
    "building_worker",
    "starting",
    "waiting_for_connection",
}
PREPARATION_BUDGET = 180
READY_FRESHNESS_SECONDS = 30


@dataclass(frozen=True)
class Settings:
    executable: Path
    psf: Path
    auto_start: bool
    timeout: int
    selected: bool

    @classmethod
    def load(cls) -> Settings:
        value = bridge.config()
        auto = value.get("auto_start_creo", True)
        timeout = value.get("creo_startup_timeout_seconds", 120)
        if not isinstance(auto, bool):
            raise ValueError("auto_start_creo must be a boolean")
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 10 <= timeout <= 600:
            raise ValueError("creo_startup_timeout_seconds must be an integer from 10 to 600")
        if not isinstance(value.get("creo_root"), str) or not value["creo_root"]:
            raise ValueError("creo_root must be an absolute installation path")
        root = Path(value["creo_root"])
        if not root.is_absolute():
            raise ValueError("creo_root must be absolute")
        executable = root / "Parametric/bin/parametric.exe"
        configured_psf = value.get("creo_startup_psf")
        if configured_psf is not None and not isinstance(configured_psf, str):
            raise ValueError("creo_startup_psf must be an absolute .psf path")
        psf = Path(configured_psf or root / "Parametric/bin/parametric.psf")
        if not psf.is_absolute() or psf.suffix.lower() != ".psf":
            raise ValueError("creo_startup_psf must be an absolute .psf path")
        selected = value.get("creo_session_id", "")
        if not isinstance(selected, str) or any(c in selected for c in "\r\n\0"):
            raise ValueError("creo_session_id must be a string without control characters")
        # Missing launch files do not prevent reuse or manual connection when
        # automatic startup is disabled; validate them immediately before launch.
        return cls(executable.resolve(), psf.resolve(), auto, timeout, bool(selected))


_kernel = ctypes.WinDLL("kernel32", use_last_error=True)


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("usage", wintypes.DWORD),
        ("pid", wintypes.DWORD),
        ("heap", ctypes.c_size_t),
        ("module", wintypes.DWORD),
        ("threads", wintypes.DWORD),
        ("parent", wintypes.DWORD),
        ("priority", wintypes.LONG),
        ("flags", wintypes.DWORD),
        ("name", wintypes.WCHAR * 260),
    ]


def _api(name: str, arguments: tuple, result: type):
    fn = getattr(_kernel, name)
    fn.argtypes = arguments
    fn.restype = result
    return fn


_snapshot = _api("CreateToolhelp32Snapshot", (wintypes.DWORD, wintypes.DWORD), wintypes.HANDLE)
_first = _api("Process32FirstW", (wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)), wintypes.BOOL)
_next = _api("Process32NextW", (wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)), wintypes.BOOL)
_close = _api("CloseHandle", (wintypes.HANDLE,), wintypes.BOOL)
_open = _api("OpenProcess", (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE)
_image = _api(
    "QueryFullProcessImageNameW",
    (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)),
    wintypes.BOOL,
)
_session = _api(
    "ProcessIdToSessionId", (wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)), wintypes.BOOL
)
_times = _api(
    "GetProcessTimes", (wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)), wintypes.BOOL
)


def _user_sid(handle: int) -> str:
    token = win32security.OpenProcessToken(handle, 8)  # TOKEN_QUERY
    try:
        return win32security.ConvertSidToStringSid(
            win32security.GetTokenInformation(token, win32security.TokenUser)[0]
        )
    finally:
        token.Close()


class DesktopLaunch:
    """Explorer does not expose a launcher handle; readiness remains unconfirmed."""

    returncode = None

    def poll(self) -> None:
        return None


def launch_creo(settings: Settings, directory: Path) -> DesktopLaunch:
    """Ask the existing interactive Explorer to launch outside MCP cleanup jobs."""
    pythoncom.CoInitialize()
    desktop = shell = None
    try:
        desktop = (
            win32com.client.Dispatch("Shell.Application").Windows().FindWindowSW(0, 0, 8, 0, 1)
        )
        if desktop is None:
            raise RuntimeError(
                "The interactive Explorer desktop is unavailable; open Creo manually"
            )
        _, pid = win32process.GetWindowThreadProcessId(desktop.HWND)
        session_id = wintypes.DWORD()
        if not _session(pid, ctypes.byref(session_id)) or session_id.value != windows_session():
            raise RuntimeError("Explorer belongs to another Windows session; open Creo manually")
        identity = process_identity(pid)
        expected = Path(os.environ["SYSTEMROOT"]) / "explorer.exe"
        if not identity or os.path.normcase(identity["image"]) != os.path.normcase(str(expected)):
            raise RuntimeError("Cannot verify the interactive Explorer process; open Creo manually")
        handle = _open(0x1000, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if _user_sid(handle) != _user_sid(-1):
                raise RuntimeError("Explorer belongs to another user; open Creo manually")
        finally:
            _close(handle)
        shell = desktop.Document.Application
        # Explorer supplies its normal desktop environment and starts Creo
        # outside the stdio host's KILL_ON_JOB_CLOSE tree. Its installed PSF
        # supplies GUI runtime/license settings; worker-specific DLL paths are
        # kept out of the GUI process. ShellExecute's return is NOT readiness.
        shell.ShellExecute(
            str(settings.executable),
            subprocess.list2cmdline([str(settings.psf)]),
            str(directory),
            "open",
            1,
        )
        return DesktopLaunch()
    except pywintypes.com_error as exc:
        raise RuntimeError(
            f"Explorer launch request failed (HRESULT={exc.hresult}); inspect the desktop"
        ) from None
    finally:
        shell = desktop = None
        pythoncom.CoUninitialize()


def windows_session() -> int:
    value = wintypes.DWORD()
    if not _session(os.getpid(), ctypes.byref(value)):
        raise ctypes.WinError(ctypes.get_last_error())
    return value.value


def process_identity(pid: int) -> dict | None:
    handle = _open(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        if ctypes.get_last_error() in (87, 1168):
            return None
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        name = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(name))
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not _image(handle, 0, name, ctypes.byref(size)) or not _times(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if exited.dwLowDateTime or exited.dwHighDateTime:
            return None
        return {
            "pid": pid,
            "created": created.dwLowDateTime | (created.dwHighDateTime << 32),
            "image": name.value,
        }
    finally:
        _close(handle)


def process_snapshot(settings: Settings, observed: dict | None = None) -> dict:
    """Best-effort read-only Creo process identities for probe reports.

    A failed connection alone cannot distinguish "Creo exited" from "the IPC
    endpoint died while the process survives"; this snapshot makes the
    difference observable without connecting Toolkit."""
    try:
        observed = inventory(settings) if observed is None else observed
    except (OSError, RuntimeError) as exc:
        return {"available": False, "reason": f"inventory_failed_{type(exc).__name__}"}
    windows = window_observations({p["pid"] for p in observed["processes"]})
    processes = []
    for identity in observed["processes"]:
        created = identity.get("created")
        created_at = None
        if isinstance(created, int):
            try:
                created_at = (
                    datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=created / 10)
                ).isoformat()
            except (OverflowError, OSError, ValueError):
                created_at = None
        image = identity.get("image") or ""
        processes.append(
            {
                "pid": identity.get("pid"),
                "name": Path(image).name if image else None,
                "created_at": created_at,
                "created_filetime": created,
                "image": image,
                "matches": identity.get("matches"),
                "windows": windows.get(identity.get("pid"), {"state": "unknown"}),
            }
        )
    return {
        "available": True,
        "observed_at": bridge.now(),
        "uncertain": observed["uncertain"],
        "processes": processes,
    }


def inventory(settings: Settings) -> dict:
    """Check exact executable paths in this Windows session, without WMI/shells."""
    snapshot = _snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    processes = []
    uncertain = False
    session_id = windows_session()
    expected = {
        os.path.normcase(str(settings.executable)),
        os.path.normcase(
            str(settings.executable.parents[2] / "Common Files/x86e_win64/obj/xtop.exe")
        ),
    }
    try:
        entry = _ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        more = _first(snapshot, ctypes.byref(entry))
        while more:
            if entry.name.lower() in ("xtop.exe", "parametric.exe"):
                target_session = wintypes.DWORD()
                if not _session(entry.pid, ctypes.byref(target_session)):
                    uncertain = True
                elif target_session.value == session_id:
                    try:
                        identity = process_identity(entry.pid)
                        if identity:
                            processes.append(
                                {
                                    **identity,
                                    "matches": os.path.normcase(identity["image"]) in expected,
                                }
                            )
                    except OSError:
                        uncertain = True
            more = _next(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() not in (0, 18):  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        _close(snapshot)
    return {"processes": processes, "uncertain": uncertain}


class CoordinatorBusy(RuntimeError):
    pass


class CoordinatorLockError(RuntimeError):
    """The startup lock file could not be opened (BUG-057).

    An open failure is a lock access error, never channel contention and never
    a configuration verdict; ``payload`` keeps the original OS error code.
    """

    def __init__(self, payload: dict):
        super().__init__(
            f"Startup coordination lock could not be opened ({payload.get('phase')}, "
            f"winerror={payload.get('winerror')}); this is a lock access error, not a "
            "configuration error and not another coordinator holding the lock"
        )
        self.payload = payload


@contextmanager
def coordination_lock(directory: Path) -> Iterator[None]:
    directory.mkdir(parents=True, exist_ok=True)
    try:
        stream = open_lock_file(directory / "startup.lock")
    except OSError as exc:
        raise CoordinatorLockError(
            {
                "kind": "lock_access_error",
                "phase": "open",
                "winerror": getattr(exc, "winerror", None),
                "errno": exc.errno,
                "filename": str(directory / "startup.lock"),
                "message": str(exc),
            }
        ) from exc
    with stream:
        # Windows permits locking past EOF. Writing an initial byte before the
        # lock races with another first-time coordinator already holding it.
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise CoordinatorLockError(
                    {
                        "kind": "lock_access_error",
                        "phase": "byte_lock",
                        "winerror": getattr(exc, "winerror", None),
                        "errno": exc.errno,
                        "filename": str(stream.name),
                        "message": str(exc),
                    }
                ) from exc
            raise CoordinatorBusy(
                "Another MCP process is checking/starting this Creo target"
            ) from exc
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


class CreoStartup:
    def __init__(self, directory: Path | None = None):
        self._directory_override = directory
        self._mutex = threading.RLock()
        self._thread: threading.Thread | None = None
        self._retry_requested = False
        self._retry_for_attempt: int | None = None
        self._stop = threading.Event()
        self._directory: Path | None = None
        self._attempt_deadline: float | None = None
        self._attempt_started: float | None = None
        self._phase_deadline: float | None = None
        self._requested_at = bridge.now()
        self._expired = False
        self._state = {
            "state": "checking",
            "connected": False,
            "message": "Startup detection has not completed",
            "retry_allowed": False,
        }

    def _publish(self, state: str, message: str, *, shared: bool = True, **fields) -> dict:
        with self._mutex:
            if any(
                time.monotonic() >= limit
                for limit in (self._attempt_deadline, self._phase_deadline)
                if limit is not None
            ):
                self._expired = True
            if self._expired and (state in ACTIVE or state == "ready"):
                state = "timeout"
                message = "Startup total budget expired; inspect the in-flight phase and occupying job before retrying. Existing Creo and reservations were preserved."
            retained = {
                key: self._state[key]
                for key in (
                    "launch_reserved",
                    "launch_attempt",
                    "auto_start_enabled",
                    "selected_session_configured",
                    "coordination_error",
                    "launch_state_known",
                    "automatic_launch_allowed",
                    "startup_recovery",
                )
                if key in self._state
            }
            if state == "timeout":
                retained.update(
                    {
                        key: self._state[key]
                        for key in ("busy", "native", "in_flight_phase")
                        if key in self._state
                    }
                )
            value = {
                **retained,
                "state": state,
                "connected": state == "ready",
                "message": message,
                "retry_allowed": state not in ACTIVE and state != "ready",
                "updated_at": bridge.now(),
                "coordinator_pid": os.getpid(),
                "phase_deadline_monotonic": self._phase_deadline,
                **fields,
            }
            self._state = value
        if shared and self._directory:
            bridge.write_json(self._directory / "state.json", value, durable=True)
            with (self._directory / "startup.log").open("a", encoding="utf-8") as log:
                log.write(
                    f"{value['updated_at']} state={state} connected={value['connected']} message={message}\n"
                )
        return value

    def status(self) -> dict:
        with self._mutex:
            value = dict(self._state)
            running = bool(self._thread and self._thread.is_alive())
            if running and self._attempt_deadline is not None:
                phase_deadline = self._phase_deadline or value.get("phase_deadline_monotonic")
                effective_deadline = (
                    min(self._attempt_deadline, phase_deadline)
                    if phase_deadline is not None
                    else self._attempt_deadline
                )
                value["remaining_budget_seconds"] = max(
                    0, self._attempt_deadline - time.monotonic()
                )
                if phase_deadline is not None:
                    value["phase_remaining_budget_seconds"] = max(
                        0, phase_deadline - time.monotonic()
                    )
                if time.monotonic() >= effective_deadline:
                    self._expired = True
                    value.update(
                        state="timeout",
                        connected=False,
                        retry_allowed=False,
                        in_flight_phase=self._state.get(
                            "in_flight_phase", self._state.get("state")
                        ),
                        message="Startup phase/total budget expired while the coordinator call is still in flight. No second coordinator or Creo will be started; inspect its phase, occupying job and build logs. Retry after that call returns. If it never returns, preserve jobs/models and restart the MCP connector; do not delete reservations or terminate Creo as automatic recovery.",
                    )
                    self._state = dict(value)
            health = bridge.channel_health()
            verified_at = value.get("verified_at")
            if (
                value.get("connected")
                and health.get("connected") is False
                and health.get("checked_at", "") >= (verified_at or "")
            ):
                value.update(
                    state="timeout",
                    connected=False,
                    retry_allowed=not running,
                    message="Toolkit verification was invalidated by a subsequent failure; inspect channel_health and request explicit retry",
                    channel_health=health,
                )
                self._state = dict(value)
            age = None
            if verified_at:
                age = max(
                    0,
                    (
                        datetime.now(timezone.utc) - datetime.fromisoformat(verified_at)
                    ).total_seconds(),
                )
            value.update(
                snapshot=True,
                verification_age_seconds=age,
                stale=not value.get("connected") or age is None or age > READY_FRESHNESS_SECONDS,
                coordinator_running=running,
            )
            value.pop("phase_deadline_monotonic", None)
            return value

    def start(self, retry: bool = False) -> dict:
        with self._mutex:
            if retry:
                directory = self._directory or self._directory_override
                if directory is None:
                    try:
                        directory = self._target_directory(Settings.load())
                    except (ValueError, OSError):
                        directory = None
                state_path = directory / "state.json" if directory else None
                try:
                    prior = (
                        read_startup_state(state_path, bridge.read_json)
                        if state_path
                        else self._state
                    )
                    self._retry_for_attempt = prior.get("launch_attempt", 0)
                except StartupStateError:
                    # Start a bounded, non-launching recheck instead of throwing
                    # synchronously from the public retry tool. Never authorize
                    # replacing an unknown launch reservation with attempt zero.
                    self._retry_for_attempt = None
            if self._thread and self._thread.is_alive():
                # A client may request retry while startup is still checking a
                # previous reservation. Keep the request instead of dropping it.
                self._retry_requested |= retry
                return self.status()
            self._retry_requested = retry
            self._expired = False
            self._attempt_started = time.monotonic()
            self._requested_at = bridge.now()
            self._attempt_deadline = None
            self._phase_deadline = None
            self._stop.clear()
            self._state = {
                "state": "checking",
                "connected": False,
                "message": "Checking Creo startup and connection",
                "retry_allowed": False,
            }
            self._thread = threading.Thread(
                target=self._run, args=(retry,), name="creo-startup", daemon=True
            )
            self._thread.start()
            return dict(self._state)

    def stop(self) -> None:
        # Do not kill Creo, cancel an in-flight native call, or block MCP shutdown.
        self._stop.set()

    def require_ready(self) -> None:
        value = self.status()
        if not value["connected"]:
            raise RuntimeError(
                f"Creo is not ready ({value['state']}): {value['message']}; poll creo_startup_status. No modeling job was queued."
            )

    def session_status(self) -> dict:
        with self._mutex:
            running = bool(self._thread and self._thread.is_alive())
        if running:
            state = self.status()
            return {**state.get("native", {}), **state, "startup": state}
        try:
            settings = Settings.load()
            snapshot = process_snapshot(settings)
        except (ValueError, OSError) as exc:
            settings = None
            snapshot = {"available": False, "reason": f"configuration_error_{type(exc).__name__}"}
        try:
            native = bridge.session_status(connect_timeout_seconds=2, build_worker=False)
        except bridge.ToolkitBusy as exc:
            return {
                "connected": False,
                "connection_state": "busy",
                **exc.payload,
                "creo_process_snapshot": snapshot,
                "startup": self.status(),
            }
        except (RuntimeError, OSError) as exc:
            native = {
                "connected": False,
                "connection_state": "probe_failed",
                "message": f"Toolkit probe failed ({type(exc).__name__}); inspect the session and worker, then request explicit retry",
            }
        if native.get("connected"):
            self._publish(
                "ready",
                "Toolkit connection verified",
                shared=False,
                native=native,
                verified_at=bridge.now(),
            )
        else:
            native["connection_guidance"] = connection_guidance(snapshot)
            self._publish(
                "timeout",
                "Toolkit connection is no longer available; inspect Creo and request creo_startup_status(retry=true)",
                shared=False,
                native=native,
            )
        # This read-only tool can recognize a manually opened session, but must
        # not turn a failed query into an implicit GUI launch/recovery request.
        return {**native, "creo_process_snapshot": snapshot, "startup": self.status()}

    def _run(self, retry: bool) -> None:
        try:
            settings = Settings.load()
            self._directory = self._target_directory(settings)
            deadline = (
                (self._attempt_started if self._attempt_started is not None else time.monotonic())
                + settings.timeout
                + PREPARATION_BUDGET
            )
            self._attempt_deadline = deadline
            while not self._stop.is_set():
                try:
                    with coordination_lock(self._directory):
                        state_path = self._directory / "state.json"
                        try:
                            shared = read_startup_state(state_path, bridge.read_json)
                        except StartupStateError as exc:
                            if not self._restore_preboot_history(settings, exc, deadline):
                                self._recheck_untrusted_state(settings, exc)
                                return
                            shared = read_startup_state(state_path, bridge.read_json)
                        if (
                            shared.get("state") not in ACTIVE
                            and shared.get("updated_at", "") >= self._requested_at
                        ):
                            with self._mutex:
                                self._state = {**shared, "coordinated": True}
                            return
                        self._drive(settings, retry, deadline)
                    return
                except CoordinatorBusy:
                    state_path = self._directory / "state.json"
                    if state_path.is_file():
                        try:
                            shared = read_startup_state(state_path, bridge.read_json)
                        except StartupStateError as exc:
                            # The active coordinator might be reconciling this
                            # history. Only its lock holder may back up/replace it.
                            self._publish(
                                "checking",
                                "Waiting for the shared coordinator before reconciling unreadable startup history",
                                shared=False,
                                coordination_error=exc.payload,
                            )
                            if time.monotonic() >= deadline:
                                self._publish(
                                    "timeout",
                                    "Shared startup coordinator remained busy; preserve history and retry after it finishes",
                                    shared=False,
                                )
                                return
                            self._stop.wait(0.5)
                            continue
                        with self._mutex:
                            # A pre-retry ready snapshot cannot satisfy a new check.
                            # Otherwise polling can see ready, then regress to building.
                            if (
                                shared.get("state") in ACTIVE
                                or shared.get("updated_at", "") >= self._requested_at
                            ):
                                self._state = {**shared, "coordinated": True}
                            else:
                                self._state.update(
                                    state="checking",
                                    connected=False,
                                    message="Waiting for the shared coordinator; previous ready has not verified this retry",
                                    coordinated=True,
                                )
                        if (
                            shared.get("state") not in ACTIVE
                            and shared.get("updated_at", "") >= self._requested_at
                        ):
                            return
                    if time.monotonic() >= deadline:
                        self._publish(
                            "timeout",
                            "Timed out waiting for the shared startup coordinator; inspect startup status before retrying",
                            shared=False,
                        )
                        return
                    self._stop.wait(0.5)
        except StartupStateError as exc:
            self._recheck_untrusted_state(settings, exc)
        except CoordinatorLockError as exc:
            # A lock access error is neither channel contention nor a
            # configuration verdict; classify it explicitly instead of letting
            # it fall into the generic configuration_error branch (BUG-057).
            LOG.warning("Startup coordination lock access failed")
            self._publish(
                "lock_error",
                "The startup coordination lock could not be opened; this is a "
                "lock access error (check directory permissions and antivirus "
                "locks), not a configuration error. Retry after the lock "
                "becomes accessible; existing Creo and startup history were preserved",
                shared=False,
                coordination_error=exc.payload,
            )
        except subprocess.TimeoutExpired as exc:
            self._publish(
                "timeout",
                "Native build/preparation subprocess exceeded its budget; inspect build logs and retry after preparation has returned. No Creo process was closed.",
                subprocess_budget_seconds=exc.timeout,
                shared=False,
            )
        except Exception as exc:
            # Exceptions may carry local paths; never echo raw launch environment,
            # configured session IDs, process command lines or PSF/license text.
            LOG.warning("Creo startup failed (%s)", type(exc).__name__)
            message = (
                str(exc)
                if isinstance(exc, ValueError)
                else f"Startup preparation failed ({type(exc).__name__}); check installation/configuration and build logs"
            )
            self._publish("configuration_error", message, shared=False)
        finally:
            # Deadlines bound this attempt, not a later explicit live probe.
            with self._mutex:
                self._attempt_deadline = None
                self._phase_deadline = None
                self._state.pop("phase_deadline_monotonic", None)
                if self._state.get("state") not in ACTIVE and self._state.get("state") != "ready":
                    self._state["retry_allowed"] = True

    def _target_directory(self, settings: Settings) -> Path:
        if self._directory_override:
            return self._directory_override
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            raise ValueError("LOCALAPPDATA is required for startup coordination")
        target = f"{windows_session()}\0{os.path.normcase(str(settings.executable))}\0{os.path.normcase(str(settings.psf))}"
        return (
            Path(local)
            / "MCP_CREO_MechDog/startup"
            / hashlib.sha256(target.encode()).hexdigest()[:24]
        )

    def _recheck_untrusted_state(self, settings: Settings, error: StartupStateError) -> None:
        """Only inspect/reconnect; unreadable history cannot authorize a new launch."""
        details = {
            "coordination_error": error.payload,
            "launch_state_known": False,
            "automatic_launch_allowed": False,
            "launch_reserved": True,
        }
        try:
            current = inventory(settings)
        except (OSError, RuntimeError) as exc:
            self._publish(
                "selection_required",
                f"Existing-session inventory failed ({type(exc).__name__}); preserve startup history and inspect Creo manually",
                shared=False,
                **details,
            )
            return
        if (
            current["uncertain"]
            or any(not p["matches"] for p in current["processes"])
            or (not current["processes"] and not settings.selected)
        ):
            self._publish(
                "selection_required", error.payload["recovery_required"], shared=False, **details
            )
            return
        self._publish(
            "waiting_for_connection",
            "Checking the existing session without replacing unknown startup history",
            shared=False,
            **details,
        )
        deadline = min(self._attempt_deadline or float("inf"), time.monotonic() + settings.timeout)
        self._phase_deadline = deadline
        native = None
        try:
            while not self._stop.is_set() and time.monotonic() < deadline:
                try:
                    native = bridge.session_status(connect_timeout_seconds=2, build_worker=False)
                    break
                except bridge.ToolkitBusy as exc:
                    self._publish(
                        "waiting_for_connection",
                        "Waiting for the occupying Toolkit operation before checking the existing session; unknown startup history is preserved",
                        shared=False,
                        busy=exc.payload,
                        **details,
                    )
                    self._stop.wait(0.25)
        except (RuntimeError, OSError) as exc:
            self._publish(
                "selection_required",
                f"Existing-session probe failed ({type(exc).__name__}); preserve startup history and inspect Creo before retrying",
                shared=False,
                **details,
            )
            return
        if native is None:
            if not self._stop.is_set():
                self._publish(
                    "timeout",
                    "Existing-session recheck exceeded its connection budget; inspect the occupying operation and preserve unknown startup history",
                    shared=False,
                    **details,
                )
            return
        if native.get("connected"):
            self._publish(
                "ready",
                "Existing Toolkit connection verified; startup history remains untrusted and automatic replacement is disabled",
                shared=False,
                native=native,
                verified_at=bridge.now(),
                **details,
            )
        else:
            self._publish(
                "selection_required",
                error.payload["recovery_required"],
                shared=False,
                native=native,
                **details,
            )

    def _restore_preboot_history(
        self, settings: Settings, error: StartupStateError, deadline: float
    ) -> bool:
        """Reconcile only a dead previous boot's launch history, under its lock."""

        def blocked(reason: str) -> bool:
            error.payload["automatic_recovery"] = {
                "status": "blocked",
                "reason": reason,
                "boot_query_budget_seconds": BOOT_QUERY_BUDGET_SECONDS,
            }
            return False

        if not settings.auto_start or settings.selected:
            return blocked("Automatic startup is disabled or an explicit session is selected")
        current = inventory(settings)
        if current["uncertain"] or current["processes"]:
            return blocked(
                "An existing or uncertain session must be verified without replacing history"
            )
        self._publish(
            "checking",
            "Verifying whether unreadable startup history predates this Windows boot",
            shared=False,
            coordination_error=error.payload,
        )
        # This phase shares the original preparation/total budget; no reset.
        recovery_deadline = min(deadline, time.monotonic() + PREPARATION_BUDGET)
        self._phase_deadline = recovery_deadline
        boot = boot_info()
        if boot is None:
            return blocked("OS boot time could not be independently verified")
        evidence = None
        while not self._stop.is_set() and time.monotonic() < recovery_deadline:
            try:
                with bridge.toolkit_lock(operation="startup_history_recovery"):
                    current = inventory(settings)
                    if current["uncertain"] or current["processes"]:
                        return blocked("A session appeared while acquiring the recovery locks")
                    evidence = archive_preboot_state(self._directory / "state.json", boot)
                    # Archive and replacement are durable before any GUI launch.
                    # Only startup bookkeeping is reset; jobs/models are untouched.
                    self._publish(
                        "checking",
                        "Previous-boot startup history was archived; checking configured Creo startup",
                        launch_reserved=False,
                        launch_attempt=0,
                        launch_state_known=True,
                        automatic_launch_allowed=True,
                        coordination_error=None,
                        startup_recovery=evidence,
                    )
                    return True
            except bridge.ToolkitBusy as exc:
                self._publish(
                    "waiting_for_channel",
                    "Waiting for the Toolkit owner before reconciling previous-boot startup history",
                    shared=False,
                    busy=exc.payload,
                    coordination_error=error.payload,
                )
                self._stop.wait(0.25)
            except (StartupStateError, OSError) as exc:
                if evidence is not None:
                    with self._mutex:
                        self._state["startup_recovery"] = {
                            **evidence,
                            "status": "archived_replacement_failed",
                        }
                reason = (
                    str(exc)
                    if isinstance(exc, StartupStateError)
                    else (f"Backup or durable startup-state write failed ({type(exc).__name__})")
                )
                return blocked(reason)
        return blocked("Startup-history reconciliation exceeded its budget or was stopped")

    def _drive(self, settings: Settings, retry: bool, deadline: float) -> None:
        state_path = self._directory / "state.json"
        previous = read_startup_state(state_path, bridge.read_json)
        self._publish(
            "checking",
            "Inspecting existing Creo processes",
            auto_start_enabled=settings.auto_start,
            selected_session_configured=settings.selected,
            launch_reserved=previous.get("launch_reserved", False),
            launch_attempt=previous.get("launch_attempt", 0),
            coordination_error=None,
            launch_state_known=True,
            automatic_launch_allowed=settings.auto_start,
        )
        initial = inventory(settings)
        if initial["uncertain"] or any(not p["matches"] for p in initial["processes"]):
            self._publish(
                "selection_required",
                "Creo process identity is uncertain or belongs to another installation; select/close it manually before retrying",
            )
            return
        if not settings.auto_start and not initial["processes"] and not settings.selected:
            self._publish(
                "disabled", "Automatic startup is disabled; open Creo manually and request retry"
            )
            return
        self._publish(
            "waiting_for_channel",
            "Waiting for the single Toolkit channel before native preparation",
            auto_start_enabled=settings.auto_start,
        )
        # Existing build_native has its own bounded subprocess timeouts. This
        # preparation is background work; no MCP handshake is held up by it.
        preparation_deadline = min(
            deadline,
            self._phase_deadline
            if self._phase_deadline is not None
            else time.monotonic() + PREPARATION_BUDGET,
        )
        self._phase_deadline = preparation_deadline
        while not self._stop.is_set():
            if time.monotonic() >= preparation_deadline:
                self._publish(
                    "timeout",
                    "Native preparation budget expired; inspect the occupying operation/build logs before retrying",
                )
                return
            try:
                with bridge.toolkit_lock(operation="startup_build"):
                    self._publish(
                        "building_worker",
                        "Building/verifying the native worker",
                        preparation_budget_seconds=PREPARATION_BUDGET,
                    )
                    bridge.build_native()
                break
            except bridge.ToolkitBusy as exc:
                self._publish(
                    "waiting_for_channel",
                    "Toolkit is busy with an existing task; waiting without launching Creo",
                    busy=exc.payload,
                )
                if time.monotonic() >= preparation_deadline:
                    self._publish(
                        "timeout",
                        "Native preparation stayed busy; finish the existing task and retry",
                    )
                    return
                self._stop.wait(0.5)
        if self._stop.is_set():
            return
        if time.monotonic() >= preparation_deadline:
            self._publish(
                "timeout",
                "Native preparation exceeded its budget; the build returned, but no connection was verified. Inspect build logs and retry.",
            )
            return
        # Connection gets its configured share, never a fresh total retry budget.
        deadline = min(deadline, time.monotonic() + settings.timeout)
        self._phase_deadline = deadline
        launched = False
        process = None
        attempt = previous.get("launch_attempt", 0)
        while not self._stop.is_set() and time.monotonic() < deadline:
            current = inventory(settings)
            if current["uncertain"] or any(not p["matches"] for p in current["processes"]):
                self._publish(
                    "selection_required", "Cannot safely identify the existing Creo startup target"
                )
                return
            try:
                if not current["processes"] and not settings.selected and not launched:
                    # A cold Toolkit probe can create nmsd inside the MCP host's
                    # cleanup Job. Let the desktop launcher start Creo and its
                    # name service first; only a later real probe can mark ready.
                    native = {
                        "connected": False,
                        "connection_state": "no_session",
                        "basis": "no Creo process in this Windows session; Toolkit not yet probed",
                    }
                else:
                    native = bridge.session_status(connect_timeout_seconds=2, build_worker=False)
            except RuntimeError:
                self._publish(
                    "waiting_for_connection",
                    "Native worker is busy or unavailable; startup will not be duplicated",
                    launch_attempt=attempt,
                )
                self._stop.wait(0.5)
                continue
            if native.get("connected"):
                self._publish(
                    "ready",
                    "Toolkit connection verified; modeling is available",
                    native=native,
                    verified_at=bridge.now(),
                    launched_by_coordinator=launched,
                    launch_reserved=False,
                    launch_attempt=attempt,
                )
                return
            if native.get("connection_state") in ("probe_timeout", "worker_unavailable"):
                self._publish("timeout", native["message"], native=native)
                return
            if native.get("connection_state") == "ambiguous":
                self._publish(
                    "selection_required",
                    "Multiple Creo sessions match; configure creo_session_id and retry",
                    native=native,
                )
                return
            if settings.selected:
                self._publish(
                    "selection_required",
                    "Configured session is unavailable or did not match; no replacement session was launched",
                    native=native,
                )
                return
            # Re-snapshot after the probe: another startup could have appeared
            # while Toolkit was checking the name server.
            current = inventory(settings)
            if current["uncertain"] or any(not p["matches"] for p in current["processes"]):
                self._publish(
                    "selection_required",
                    "Creo process identity changed during connection detection",
                )
                return
            if not current["processes"] and not launched:
                if not settings.auto_start:
                    self._publish(
                        "disabled",
                        "Automatic startup is disabled; open Creo manually and retry",
                        native=native,
                    )
                    return
                with self._mutex:
                    retry_authorized = (retry and self._retry_for_attempt is None) or (
                        self._retry_requested
                        and self._retry_for_attempt is not None
                        and self._retry_for_attempt >= attempt
                    )
                if previous.get("launch_reserved") and not retry_authorized:
                    self._publish(
                        "timeout",
                        "A previous startup attempt has no confirmed outcome; explicit retry is required after checking Creo",
                        native=native,
                        launch_reserved=True,
                        launch_attempt=attempt,
                    )
                    return
                if native.get("connection_state") not in ("no_session", "not_found_or_unreadable"):
                    self._publish(
                        "launch_failed",
                        "Toolkit connection failed for a reason other than an absent session; inspect the native code before retrying",
                        native=native,
                    )
                    return
                if not settings.executable.is_file() or not settings.psf.is_file():
                    self._publish(
                        "configuration_error",
                        "Configured Creo executable or startup PSF is missing",
                    )
                    return
                attempt += 1
                # Persist the reservation BEFORE creating a process. If this
                # leader dies in that gap, a successor cannot blindly relaunch.
                self._publish(
                    "starting",
                    "Launching configured Creo with its PSF",
                    launch_reserved=True,
                    launch_attempt=attempt,
                )
                directory = bridge.ROOT / "build/creo_session"
                directory.mkdir(parents=True, exist_ok=True)
                try:
                    process = launch_creo(settings, directory)
                except (OSError, RuntimeError) as exc:
                    reason = (
                        str(exc)
                        if isinstance(exc, RuntimeError)
                        else f"Windows launch error {getattr(exc, 'winerror', None)}; check executable/PSF and desktop permissions"
                    )
                    self._publish(
                        "launch_failed",
                        f"Creo launch failed: {reason}",
                        launch_reserved=True,
                        launch_attempt=attempt,
                    )
                    return
                launched = True
            if process is not None and process.poll() not in (None, 0) and not current["processes"]:
                self._publish(
                    "launch_failed",
                    f"Creo launcher exited {process.returncode}; inspect startup.log and any startup dialog",
                    launch_reserved=True,
                    launch_attempt=attempt,
                )
                return
            observed = process_snapshot(settings, current)
            self._publish(
                "waiting_for_connection",
                "Toolkit has not confirmed readiness. " + connection_guidance(observed),
                native=native,
                creo_process_snapshot=observed,
                launch_reserved=launched or previous.get("launch_reserved", False),
                launch_attempt=attempt,
            )
            self._stop.wait(0.5)
        if not self._stop.is_set():
            self._publish(
                "timeout",
                "Toolkit did not become ready within the startup budget; inspect Creo dialogs/environment, then request retry. Existing Creo processes were preserved",
                launch_reserved=launched or previous.get("launch_reserved", False),
                launch_attempt=attempt,
            )
