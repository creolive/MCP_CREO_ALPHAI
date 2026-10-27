"""BUG-078: read-only session health evidence for public status responses.

The summary is derived only from execution results that already exist on disk:
job manifests that recorded what the native worker observed (connection, save,
reload verification, unknown outcome) plus the last persisted Toolkit probe
result. It never opens a Toolkit connection or channel lock, never saves,
never probes Creo, never writes a file and never clears a protection, so a
status route that must not disturb the session can always call it.

``no_failure_observed`` is an evidence label, not a health guarantee: it only
means that no save failure was recorded for the currently observed session
inside the freshness window. A successful connection does not prove that the
next Backup will succeed.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import bridge

FRESHNESS_SECONDS = 600
JOB_LIMIT = 120
JOB_FILE_BYTES = 2 * 1024 * 1024
JOB_TOTAL_BYTES = 8 * 1024 * 1024
CACHE_SECONDS = 5.0
DAMAGE_LIMIT = 5
SAVE_CALLS = ("ProMdlnameBackup", "ProMdlSave", "ProMdlfileTypeLoad")
NON_WRITE_KINDS = {"session_erase", "open_file", "adoption_file"}
TERMINAL = {"succeeded", "failed", "unknown_outcome", "abandoned"}
UNKNOWN = "unknown"
DAMAGE = "suspected_damage"
OBSERVED = "no_failure_observed"

_CACHE: dict[str, dict] = {}


def _moment(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _age(record: dict, now: datetime) -> float:
    return max(0.0, (now - record["at"]).total_seconds())


def _save_related(result: dict) -> bool:
    stage = str(result.get("failed_stage") or "").lower()
    call = str(result.get("failed_toolkit_call") or "")
    message = str(result.get("message") or "").lower()
    return "save" in stage or "reload" in stage or call in SAVE_CALLS or "backup" in message


def _save_record(manifest: dict, at: datetime) -> dict | None:
    """A save fact for this job, or None when it never attempted a save."""
    status = manifest.get("status")
    readonly = bool(manifest.get("readonly"))
    if readonly or status not in TERMINAL:
        return None
    result = manifest.get("result") if isinstance(manifest.get("result"), dict) else {}
    kind = str(manifest.get("kind") or "plate")
    capable = (
        "saved_file_reloaded_and_verified" in result
        or "part_file" in result
        or (status == "failed" and _save_related(result))
        or (status == "unknown_outcome" and kind not in NON_WRITE_KINDS)
    )
    if not capable:
        return None
    verified = result.get("saved_file_reloaded_and_verified")
    if status == "succeeded":
        outcome = "succeeded" if verified is True else "unknown"
    elif status == "unknown_outcome":
        outcome = "unknown"
    elif status == "failed":
        outcome = "failed" if _save_related(result) else "not_attempted"
    else:
        outcome = "unknown"
    damage = None
    if outcome == "failed":
        damage = "save_failure"
    elif outcome == "unknown" and status == "unknown_outcome":
        damage = "unknown_outcome_protection"
    return {
        "kind": "save",
        "outcome": outcome,
        "at": at,
        "job_id": manifest.get("job_id"),
        "model_id": manifest.get("model_id"),
        "session": None,
        "session_source": None,
        "damage": damage,
        "detail": {
            "job_status": status,
            "job_kind": kind,
            "connected": result.get("connected"),
            "connection_state": result.get("connection_state"),
            "saved_file_reloaded_and_verified": verified,
            "failed_stage": result.get("failed_stage"),
            "failed_toolkit_call": result.get("failed_toolkit_call"),
            "rollback_succeeded": result.get("rollback_succeeded"),
            "part_file": result.get("part_file"),
        },
    }


def _connection_record(manifest: dict, at: datetime) -> dict | None:
    """A connection fact for a read-only execution result that reached Creo."""
    if not manifest.get("readonly"):
        return None
    result = manifest.get("result") if isinstance(manifest.get("result"), dict) else {}
    connected = result.get("connected")
    if connected is None:
        return None
    return {
        "kind": "connection",
        "outcome": "connected" if connected is True else "failed",
        "at": at,
        "job_id": manifest.get("job_id"),
        "model_id": manifest.get("model_id"),
        "session": None,
        "session_source": None,
        "damage": None,
        "detail": {
            "job_status": manifest.get("status"),
            "job_kind": str(manifest.get("kind") or "plate"),
            "connected": connected,
            "connection_state": result.get("connection_state"),
            "disconnect_code": result.get("disconnect_code"),
        },
    }


def _job_record(manifest: dict) -> dict | None:
    if manifest.get("status") not in TERMINAL:
        return None
    at = _moment(manifest.get("finished_at")) or _moment(manifest.get("created_at"))
    if at is None:
        return None
    result = manifest.get("result") if isinstance(manifest.get("result"), dict) else {}
    record = _save_record(manifest, at) or _connection_record(manifest, at)
    if record is None:
        return None
    session = result.get("session_fingerprint")
    if isinstance(session, str) and session:
        record["session"] = session
        record["session_source"] = "recorded"
    return record


def _probe_record(root: Path, stats: dict) -> dict | None:
    path = root / "build" / "toolkit_health.json"
    try:
        value = bridge.read_json(path)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        stats["unreadable"] += 1
        stats["problems"].append(f"toolkit_health_unreadable:{type(exc).__name__}")
        return None
    if not isinstance(value, dict) or not isinstance(value.get("connected"), bool):
        return None
    at = _moment(value.get("checked_at"))
    if at is None:
        return None
    return {
        "kind": "connection",
        "outcome": "connected" if value["connected"] else "failed",
        "at": at,
        "job_id": value.get("job_id"),
        "model_id": value.get("model_id"),
        "session": None,
        "session_source": None,
        "damage": None,
        "detail": {
            "connected": value["connected"],
            "connection_state": value.get("connection_state"),
            "source": "toolkit_probe",
        },
    }


def _candidates(jobs: Path, stats: dict) -> list[tuple[float, str, Path]]:
    found = []
    try:
        with os.scandir(jobs) as entries:
            for entry in entries:
                try:
                    if not entry.is_dir():
                        continue
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue
                found.append((mtime, entry.name, Path(entry.path) / "job.json"))
    except FileNotFoundError:
        stats["problems"].append("jobs_directory_missing")
        return []
    except OSError as exc:
        stats["unreadable"] += 1
        stats["problems"].append(f"jobs_directory_unreadable:{type(exc).__name__}")
        return []
    found.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return found


def _attribute(records: list[dict]) -> None:
    """Bind unlabelled facts to the session observed at or before their time.

    A plate job or a bare probe records no session fingerprint. Such a fact is
    attributed to the newest recorded session at or before its timestamp and
    labelled ``attributed`` so callers can tell it apart from a recorded one.
    """
    anchors = sorted(
        (record for record in records if record["session_source"] == "recorded"),
        key=lambda record: record["at"],
    )
    for record in records:
        if record["session"]:
            continue
        match = None
        for candidate in anchors:
            if candidate["at"] <= record["at"]:
                match = candidate
            else:
                break
        if match is not None:
            record["session"] = match["session"]
            record["session_source"] = "attributed"


def _collect(root: Path) -> dict:
    stats = {"jobs_scanned": 0, "jobs_unreadable": 0, "jobs_skipped": 0, "unreadable": 0}
    stats["problems"] = []
    records: list[dict] = []
    total = 0
    for _mtime, _name, path in _candidates(root / "jobs", stats)[:JOB_LIMIT]:
        try:
            size = path.stat().st_size
        except OSError:
            stats["jobs_unreadable"] += 1
            continue
        if size > JOB_FILE_BYTES:
            stats["jobs_skipped"] += 1
            continue
        total += size
        if total > JOB_TOTAL_BYTES:
            break
        try:
            manifest = bridge.read_json(path)
        except (OSError, ValueError):
            stats["jobs_unreadable"] += 1
            continue
        if not isinstance(manifest, dict):
            stats["jobs_unreadable"] += 1
            continue
        stats["jobs_scanned"] += 1
        record = _job_record(manifest)
        if record is not None:
            records.append(record)
    probe = _probe_record(root, stats)
    if probe is not None:
        records.append(probe)
    records.sort(key=lambda item: item["at"], reverse=True)
    _attribute(records)
    stats["sources"] = []
    if stats["jobs_scanned"]:
        stats["sources"].append("jobs/*/job.json")
    if probe is not None:
        stats["sources"].append("build/toolkit_health.json")
    return {"records": records, "stats": stats}


def _channel(root: Path) -> dict:
    """Read the recorded channel owner without taking the lock.

    The owner record is written for the duration of a call and removed on
    release, so a record normally means a call is in flight. A record left by
    a crashed process cannot be distinguished from a live owner here; that is
    why this is reported as an observation and never rewrites the status.
    """
    try:
        value = bridge.read_json(root / "toolkit-owner.lock")
    except (OSError, ValueError):
        return {"busy": False, "owner": None, "source": "owner_record"}
    if not isinstance(value, dict):
        return {"busy": False, "owner": None, "source": "owner_record"}
    owner = {
        key: value[key] for key in ("job_id", "model_id", "operation", "since") if key in value
    }
    return {
        "busy": bool(owner),
        "owner": owner or None,
        "source": "owner_record",
        "note": (
            "A recorded owner normally means another call holds the channel; a record left "
            "by a crashed process cannot be told apart here, and this summary never tests "
            "the OS lock because that could reject a real submission."
        ),
    }


def _connection_fact(records: list[dict], now: datetime) -> dict | None:
    for record in records:
        if record["kind"] != "connection" and record["detail"].get("connected") is None:
            continue
        connected = record["detail"].get("connected")
        return {
            "outcome": record["outcome"]
            if record["kind"] == "connection"
            else ("connected" if connected else "failed"),
            "at": record["at"].isoformat(),
            "age_seconds": int(_age(record, now)),
            "job_id": record.get("job_id"),
            "model_id": record.get("model_id"),
            "connection_state": record["detail"].get("connection_state"),
            "source": record["detail"].get("source", "execution_result"),
        }
    return None


def _save_fact(record: dict, now: datetime, current: str | None) -> dict:
    detail = record["detail"]
    return {
        "outcome": record["outcome"],
        "at": record["at"].isoformat(),
        "age_seconds": int(_age(record, now)),
        "job_id": record.get("job_id"),
        "model_id": record.get("model_id"),
        "job_status": detail.get("job_status"),
        "job_kind": detail.get("job_kind"),
        "saved_file_reloaded_and_verified": detail.get("saved_file_reloaded_and_verified"),
        "failed_stage": detail.get("failed_stage"),
        "failed_toolkit_call": detail.get("failed_toolkit_call"),
        "session_source": record["session_source"],
        "current_session": record["session"] == current,
    }


def _damage_signal(record: dict, now: datetime, current: bool) -> dict:
    return {
        "kind": record["damage"],
        "at": record["at"].isoformat(),
        "age_seconds": int(_age(record, now)),
        "job_id": record.get("job_id"),
        "model_id": record.get("model_id"),
        "job_status": record["detail"].get("job_status"),
        "failed_stage": record["detail"].get("failed_stage"),
        "failed_toolkit_call": record["detail"].get("failed_toolkit_call"),
        "session_source": record["session_source"],
        "current_session": current,
    }


def _next_steps(status: str, reason: str, busy: bool) -> list[dict]:
    steps: list[dict] = []
    if busy:
        steps.append(
            {
                "step": "wait",
                "action": "Wait for the occupying operation instead of resubmitting",
                "tool": "creo_get_job",
                "detail": (
                    "Another call holds the Toolkit channel, so no newer evidence can appear "
                    "until it finishes. Poll the occupying job_id; nothing was queued."
                ),
            }
        )
    preserve = {
        "step": "preserve",
        "action": "Keep the original job, model record and diagnostics",
        "detail": (
            "Do not resubmit the plan, edit model.json, delete a reservation, or clear an "
            "unknown protection; the job result, native log and evidence are the only "
            "recovery proof."
        ),
    }
    operator = {
        "step": "operator",
        "action": "Have an operator confirm a session rebuild",
        "detail": (
            "If read-only observations keep failing, a human decides whether Creo must be "
            "closed and reopened. This service never restarts Creo and never erases the "
            "session."
        ),
    }
    if status == DAMAGE:
        steps += [
            preserve,
            {
                "step": "inspect",
                "action": "Persist a read-only recovery inspection before any action",
                "tool": "creo_reconcile_model",
                "mode": "inspect",
                "detail": (
                    "The inspection does not need Creo and returns each action's "
                    "available/reason plus a ten-minute evidence_token; a live precheck "
                    "requires an explicit live=true and a usable session."
                ),
            },
            {
                "step": "choose",
                "action": "Choose one action from this inspection's available/reason",
                "detail": (
                    "accept_saved/accept_live adopt recorded work, restore_baseline discards "
                    "the session copy, abandon_new drops an unregistered new part. Never "
                    "replay the original plan and never apply an older token."
                ),
            },
            operator,
            {
                "step": "reobserve",
                "action": "After a rebuild, re-observe before the next save",
                "detail": (
                    "A rebuilt session invalidates earlier evidence; the next observation "
                    "restarts the evidence window and an earlier success is not reused."
                ),
            },
        ]
        return steps
    recovery = {
        "step": "recover",
        "action": "If a job is unconfirmed, follow its recorded recovery evidence",
        "tool": "creo_get_job",
        "detail": (
            "Read status, failure_phase and recovery first, then inspect the model with "
            "creo_reconcile_model. Do not replay an unknown_outcome job."
        ),
    }
    if status == OBSERVED:
        return steps + [
            {
                "step": "keep-evidence",
                "action": "Keep the job record until the saved model is verified",
                "detail": (
                    "Poll the accepted job; saved_file_reloaded_and_verified is the proof of "
                    "a save, not the job status alone."
                ),
            },
            {
                "step": "verify-next-save",
                "action": "Treat the next save as unproven",
                "detail": (
                    "A successful connection or an earlier save never proves the next Backup "
                    "succeeds. This label only reports that no save failure was recorded for "
                    f"the observed session in the last {FRESHNESS_SECONDS // 60} minutes."
                ),
            },
            recovery,
            {
                "step": "escalate",
                "action": "If a save now fails, stop and preserve the scene",
                "detail": (
                    "Do not retry, delay or switch save paths; record the job, native log and "
                    "evidence for BUG-078, then use the recovery inspection."
                ),
            },
        ]
    return steps + [
        preserve,
        {
            "step": "observe",
            "action": "Obtain a fresh read-only observation",
            "tool": "creo_session_status",
            "detail": (
                "A completed probe records the session identity and connection result. A busy "
                "channel returns its occupying job and this request is not queued or retried."
            ),
        },
        recovery,
        operator,
    ]


def _caveats(status: str) -> list[str]:
    shared = [
        "This summary is built from already recorded execution results; it opens no Toolkit "
        "connection and runs no probe.",
        "Absence of a recorded failure is not a health guarantee and never authorizes clearing "
        "an unknown protection.",
    ]
    if status == OBSERVED:
        shared.append(
            "A verified save or a successful connection does not prove that the next save or "
            "Backup will succeed."
        )
    if status == DAMAGE:
        shared.append(
            "A damaged session can still answer connection probes; only the recorded save and "
            "reload facts are reported here."
        )
    return shared


def _evaluate(records: list[dict], stats: dict, now: datetime) -> dict:
    if not records:
        reason = "evidence_unreadable" if stats["unreadable"] else "no_evidence"
        return {"status": UNKNOWN, "reason": reason}
    if _age(records[0], now) > FRESHNESS_SECONDS:
        return {"status": UNKNOWN, "reason": "evidence_expired"}
    anchor = next((r for r in records if r["session_source"] == "recorded"), None)
    if anchor is None:
        return {"status": UNKNOWN, "reason": "session_identity_unknown"}
    if _age(anchor, now) > FRESHNESS_SECONDS:
        return {"status": UNKNOWN, "reason": "session_identity_stale"}
    current = anchor["session"]
    scoped = [r for r in records if r["session"] == current and _age(r, now) <= FRESHNESS_SECONDS]
    damage = next((r for r in scoped if r["damage"]), None)
    if damage is not None:
        return {"status": DAMAGE, "reason": damage["damage"]}
    if any(r["kind"] == "save" and r["outcome"] == "succeeded" for r in scoped):
        return {"status": OBSERVED, "reason": "recent_verified_save"}
    return {"status": UNKNOWN, "reason": "no_recent_verified_save"}


def snapshot(
    root: Path | None = None, *, now: datetime | None = None, refresh: bool = False
) -> dict:
    """Return the read-only session health evidence summary.

    ``root`` defaults to the service root. ``now`` is injectable for tests and
    ``refresh`` bypasses the short evidence cache used by polling routes.
    """
    base = Path(root) if root is not None else bridge.ROOT
    moment = now or datetime.now(timezone.utc)
    key = str(base)
    cached = _CACHE.get(key)
    if refresh or cached is None or time.monotonic() - cached["at"] > CACHE_SECONDS:
        cached = {"at": time.monotonic(), **_collect(base)}
        _CACHE[key] = cached
    records = cached["records"]
    stats = cached["stats"]
    channel = _channel(base)
    decision = _evaluate(records, stats, moment)
    anchor = next((r for r in records if r["session_source"] == "recorded"), None)
    current = anchor["session"] if anchor else None
    scoped = [
        r
        for r in records
        if current is not None and r["session"] == current and _age(r, moment) <= FRESHNESS_SECONDS
    ]
    damage = [r for r in scoped if r["damage"]]
    historic = [r for r in records if r["damage"] and r["session"] != current]
    saves = [r for r in scoped if r["kind"] == "save"]
    newest_save = next((r for r in records if r["kind"] == "save"), None)
    sessions = sorted({r["session"] for r in records if r["session"]})
    observed_at = records[0]["at"] if records else None
    return {
        "status": decision["status"],
        "reason": decision["reason"],
        "evaluated_at": moment.isoformat(),
        "observed_at": observed_at.isoformat() if observed_at else None,
        "evidence_age_seconds": int(_age(records[0], moment)) if records else None,
        "freshness_window_seconds": FRESHNESS_SECONDS,
        "session": {
            "identity": current,
            "identity_source": anchor["session_source"] if anchor else None,
            "identity_observed_at": anchor["at"].isoformat() if anchor else None,
            "changed": len(sessions) > 1,
            "sessions_observed": len(sessions),
        },
        "facts": {
            "last_connection": _connection_fact(records, moment),
            "last_save": _save_fact(newest_save, moment, current)
            if newest_save is not None
            else None,
            "recent_saves": {
                "succeeded": sum(1 for r in saves if r["outcome"] == "succeeded"),
                "failed": sum(1 for r in saves if r["outcome"] == "failed"),
                "unknown": sum(1 for r in saves if r["outcome"] == "unknown"),
                "not_attempted": sum(1 for r in saves if r["outcome"] == "not_attempted"),
            },
            "channel": channel,
        },
        "damage_signals": [_damage_signal(r, moment, True) for r in damage[:DAMAGE_LIMIT]],
        "historic_damage_signals": [
            _damage_signal(r, moment, False) for r in historic[:DAMAGE_LIMIT]
        ],
        "next_steps": _next_steps(decision["status"], decision["reason"], channel["busy"]),
        "caveats": _caveats(decision["status"]),
        "evidence": {
            "jobs_scanned": stats["jobs_scanned"],
            "jobs_unreadable": stats["jobs_unreadable"],
            "jobs_skipped": stats["jobs_skipped"],
            "sources": list(stats["sources"]),
            "problems": list(stats["problems"]),
        },
        "read_only": True,
        "toolkit_connections": 0,
        "guarantee": "evidence_only",
    }


__all__ = ["FRESHNESS_SECONDS", "snapshot"]
