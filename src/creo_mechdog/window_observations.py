"""Read-only top-level window observations; absence never proves a process is dead."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


def _enumerate_windows(pids: set[int]) -> list[tuple[int, bool, bool]]:
    user = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    enumerate_windows = user.EnumWindows
    enumerate_windows.argtypes = (callback_type, wintypes.LPARAM)
    enumerate_windows.restype = wintypes.BOOL
    process_id = user.GetWindowThreadProcessId
    process_id.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    process_id.restype = wintypes.DWORD
    visible = user.IsWindowVisible
    visible.argtypes = (wintypes.HWND,)
    visible.restype = wintypes.BOOL
    hung = user.IsHungAppWindow
    hung.argtypes = (wintypes.HWND,)
    hung.restype = wintypes.BOOL
    rows = []

    @callback_type
    def observe(handle: int, parameter: int) -> bool:
        pid = wintypes.DWORD()
        if process_id(handle, ctypes.byref(pid)) and pid.value in pids:
            rows.append((pid.value, bool(visible(handle)), bool(hung(handle))))
        return True

    if not enumerate_windows(observe, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return rows


def window_observations(pids: set[int]) -> dict[int, dict]:
    """Inspect this desktop only; don't activate windows, read titles, or send messages."""
    if not pids:
        return {}
    try:
        rows = _enumerate_windows(pids)
    except OSError as error:
        return {
            pid: {"state": "unknown", "windows_error": getattr(error, "winerror", None)}
            for pid in pids
        }
    result = {}
    for pid in pids:
        owned = [(visible, hung) for owner, visible, hung in rows if owner == pid]
        count = sum(visible for visible, _ in owned)
        result[pid] = {
            "state": "visible" if count else "hidden_only" if owned else "none_observed",
            "top_level_count": len(owned),
            "visible_count": count,
            "hung_window_observed": any(hung for _, hung in owned),
            "visible_hung_window_observed": any(visible and hung for visible, hung in owned),
            "scope": "current Windows desktop; window absence does not prove process failure",
        }
    return result


_PRECHECKS = (
    "Before any recovery step, confirm the intended Windows session/desktop and target "
    "Creo process, account for unsaved models and unknown or pending jobs, and keep "
    "diagnostics (this snapshot, trail files and worker logs) for later analysis."
)
_OPERATOR_ONLY_ENDING = (
    "Ending a Creo process is an explicit operator recovery choice only: it is never "
    "performed automatically and is never a precondition for retry."
)


def connection_guidance(snapshot: dict) -> str:
    matching = [p for p in snapshot.get("processes", []) if p.get("matches")]
    windows = [p.get("windows", {}) for p in matching]
    states = [w.get("state", "unknown") for w in windows]
    if any(w.get("visible_hung_window_observed") for w in windows):
        return (
            "A visible matching Creo window was observed hung. A hung window is a "
            "different condition from an active feature Dashboard or modal "
            "warning/dialog (those keep the window responsive), and observing it does "
            "not prove the root cause of the connection failure; finish or cancel any "
            "reachable Dashboard or dialog manually. "
            + _PRECHECKS
            + " "
            + _OPERATOR_ONLY_ENDING
            + " This snapshot does not authorize clearing any protection."
        )
    if states and all(s in ("hidden_only", "none_observed") for s in states):
        hidden_hung = (
            " Hung hidden windows were observed on matching processes; hidden launcher "
            "windows are reported separately from visible main windows and do not by "
            "themselves prove the whole Creo session is stuck or its root cause."
            if any(w.get("hung_window_observed") for w in windows)
            else ""
        )
        return (
            "Matching Creo processes have no visible top-level window on this desktop. "
            "Check the intended Windows desktop/session and startup state; this does "
            "not prove a dead process and does not authorize ending it."
            + hidden_hung
            + " "
            + _PRECHECKS
            + " "
            + _OPERATOR_ONLY_ENDING
        )
    if "visible" in states:
        return (
            "Check Creo for an active feature Dashboard or modal warning/dialog "
            "(distinct from a hung window), finish or cancel it manually, then "
            "explicitly recheck readiness; a visible window does not prove Toolkit "
            "readiness. " + _PRECHECKS
        )
    return (
        "Window state is unconfirmed; check the intended Creo session and startup "
        "dialogs before retrying. " + _PRECHECKS
    )
