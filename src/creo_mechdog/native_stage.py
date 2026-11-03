"""Bounded attribution of the native worker's last stage (BUG-109).

The 0.11.5 Creo 9 report showed a first-build job stopping after
``PHASE=verify_model`` for about ten minutes with no further log line: one
phase name covered regeneration, inspection, assertions, backup, erase,
reload, comparison and preview, so "still working" and "hung" looked the same
until the 600 s budget expired.

This module only reads the tail of ``native.log`` and never touches the
worker. Sub-stages are emitted by ``native/generic.cpp`` as::

    STAGE name=verify_model_save elapsed_ms=41 since_start_ms=1200 ts=1700000000123

``ts`` is the worker's wall clock in epoch milliseconds, so a caller can tell
how long the last sub-stage has been silent. Logs written before this change
have only ``PHASE=`` lines: they keep working and report
``reason="no_stage_timing"`` instead of inventing timings.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Only the tail is read; polling must not scale with log size.
TAIL_BYTES = 8192
#: Hard bound on parsed lines even if a log line is extremely long.
MAX_SCAN_LINES = 200

_PHASE = re.compile(r"^PHASE=(.+)$")
_STAGE = re.compile(r"^STAGE\s+(.+)$")
_FIELD = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(\S+)")


def _empty() -> dict[str, Any]:
    return {
        "readable": False,
        "log_bytes": None,
        "tail_bytes": TAIL_BYTES,
        "truncated": False,
        "stage": None,
        "sub_stage": None,
        "elapsed_ms": None,
        "since_start_ms": None,
        "idle_seconds": None,
        "stages_seen": 0,
        "reason": None,
    }


def _integer(text: str | None) -> int | None:
    if text is None:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _now_ms(now: datetime | None) -> int:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return int(moment.timestamp() * 1000)


def _read_tail(path: Path, tail_bytes: int) -> tuple[bytes | None, int | None, str | None]:
    """Return ``(tail_bytes_read, total_size, error)`` without raising."""
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return None, None, "native_log_missing"
    except OSError as exc:  # pragma: no cover - platform dependent
        return None, None, f"native_log_unreadable:{type(exc).__name__}"
    try:
        with path.open("rb") as handle:
            start = max(0, size - tail_bytes)
            handle.seek(start)
            return handle.read(), size, None
    except OSError as exc:  # pragma: no cover - platform dependent
        return None, size, f"native_log_unreadable:{type(exc).__name__}"


def _lines(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    # A partially flushed last line must not be read as a completed sub-stage.
    if text and not text.endswith(("\n", "\r")):
        lines = lines[:-1]
    return lines[-MAX_SCAN_LINES:]


def stall_report(
    directory: Path | str,
    *,
    tail_bytes: int = TAIL_BYTES,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Summarise the last phase/sub-stage of ``<directory>/native.log``.

    Returns a bounded, read-only projection. Missing or unreadable logs are
    reported explicitly (``readable=False`` plus ``reason``); nothing is
    inferred from job metadata.
    """
    report = _empty()
    report["tail_bytes"] = tail_bytes
    raw, size, error = _read_tail(Path(directory) / "native.log", tail_bytes)
    report["log_bytes"] = size
    if error:
        report["reason"] = error
        return report
    report["readable"] = True
    if size is not None:
        report["truncated"] = size > tail_bytes

    stage = None
    sub_stage = None
    timing: dict[str, str] = {}
    seen = 0
    for line in _lines(raw or b""):
        phase = _PHASE.match(line)
        if phase:
            stage = phase.group(1).strip() or stage
            continue
        staged = _STAGE.match(line)
        if not staged:
            continue
        seen += 1
        fields = dict(_FIELD.findall(staged.group(1)))
        name = fields.get("name")
        if name:
            sub_stage = name
            timing = fields

    report["stage"] = stage
    report["sub_stage"] = sub_stage
    report["stages_seen"] = seen
    if sub_stage is None:
        report["reason"] = "no_phase_lines" if stage is None else "no_stage_timing"
        return report

    elapsed = _integer(timing.get("elapsed_ms"))
    since_start = _integer(timing.get("since_start_ms"))
    timestamp = _integer(timing.get("ts"))
    report["elapsed_ms"] = elapsed
    report["since_start_ms"] = since_start
    if timestamp is None:
        report["reason"] = "no_stage_timing"
        return report
    report["idle_seconds"] = round(max(0.0, (_now_ms(now) - timestamp) / 1000.0), 3)
    return report
