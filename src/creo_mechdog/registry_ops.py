"""Registry maintenance: read-only health report and explicit migration.

FEAT-047 (``creo_registry_health``) reports per-entry sizes, budget usage,
corruption and migration state without touching Toolkit. BUG-077
(``creo_migrate_registry``) is the explicit migration flow that splits legacy
inline registry records and their job-evidence manifests into detail sidecars:
original bytes are backed up first, details are persisted before the control
record is published atomically, every action is appended to a migration log,
and reruns are idempotent so an interrupted migration can be resumed. The
unified read budget is never raised; model identity, revision and history
conclusions stay unchanged.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import bridge
import generic_bridge as general
from creo_mechdog import model_queries, model_registry

WARNING_RATIO = 0.8
PROBLEM_LIMIT = 50
MIGRATION_LOG = "registry-migration.jsonl"
MODEL_BACKUP = "model.json.pre-split-bak"
JOB_BACKUP_SUFFIX = ".pre-split-bak"
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


def _read_object(file: Path) -> dict:
    """Maintenance may read oversized legacy files, but never follow links."""
    if file.is_symlink() or file.is_junction():
        raise ValueError("Registry maintenance files cannot be links")
    if bridge.ROOT.resolve() not in file.resolve().parents:
        raise ValueError("Registry maintenance file is outside this service")
    value = bridge.read_json(file)
    if not isinstance(value, dict):
        raise ValueError("Registry maintenance file must contain an object")
    return value


def _model_directory(model_id: str) -> Path:
    if not isinstance(model_id, str):
        raise ValueError("targets must contain model_ids")
    directory = general.model_path(model_id)
    if directory.resolve().parent != general.MODELS.resolve() or not directory.is_dir():
        raise ValueError("Migration target must be an existing direct model directory")
    for file in (directory / "model.json", directory / "details"):
        if file.is_symlink() or file.is_junction():
            raise ValueError("Migration target files and detail directories cannot be links")
    return directory


def _page(
    report: dict, key: str, rows: list[dict], limit: int, cursor: str | None, scope: str
) -> dict:
    """Fit the entire serialized response, including problem previews, in 32 KiB."""
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit must be 1–50")
    snapshot = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    position = model_queries.decode_cursor(cursor)
    if position and (position.get("scope") != scope or position.get("snapshot") != snapshot):
        raise ValueError(
            "Registry report changed or cursor belongs elsewhere; restart without cursor"
        )
    offset = position["offset"] if position else 0
    if offset > len(rows):
        raise ValueError("Invalid registry cursor offset")
    window = rows[offset : offset + limit]
    result = {**report, key: window, "entry_offset": offset, "limit": limit}
    result["response_budget_bytes"] = model_queries.RESPONSE_BUDGET

    def update_cursor() -> None:
        more = offset + len(window) < len(rows)
        result["has_more"] = more
        result["next_cursor"] = (
            model_queries.encode_cursor(
                {"offset": offset + len(window), "scope": scope, "snapshot": snapshot}
            )
            if more
            else None
        )

    update_cursor()
    while model_queries.serialized_size(result) > model_queries.RESPONSE_BUDGET:
        previews = [
            result[name]
            for name in ("over_budget", "warning", "corrupt")
            if isinstance(result.get(name), dict) and result[name].get("entries")
        ]
        if previews:
            preview = max(previews, key=lambda item: len(item["entries"]))
            preview["entries"].pop()
            preview["complete"] = False
        elif len(window) > 1:
            window.pop()
            update_cursor()
        elif window:
            row = window[0]
            window[0] = {
                name: str(row[name])[:128]
                for name in ("model_id", "job_id", "state", "result", "file")
                if name in row
            }
            window[0]["details_omitted"] = (
                "Entry exceeds the response budget; inspect local evidence"
            )
            if model_queries.serialized_size(result) > model_queries.RESPONSE_BUDGET:
                raise ValueError("Registry response metadata exceeds the response budget")
        else:
            raise ValueError("Registry response metadata exceeds the response budget")
    return result


def _job_chain(model: dict) -> list[str]:
    """Jobs the recovery channel reads for this model: pending/recovery/last
    plus the successful-output history chain _baseline_hash walks."""
    chain: list[str] = []
    current = model
    seen: set[str] = set()
    for key in ("recovery_pending", "pending_job", "last_job"):
        job_id = model.get(key)
        if job_id and job_id not in chain:
            chain.append(job_id)
    for _ in range(16):
        job_id = current.get("last_job")
        if not job_id or job_id in seen:
            break
        seen.add(job_id)
        if job_id not in chain:
            chain.append(job_id)
        directory = bridge.job_path(job_id)
        try:
            request = _read_object(directory / "request.json")
            current = request.get("model", {}) if isinstance(request, dict) else {}
        except (OSError, ValueError):
            break
    return chain


def _entry_state(model: dict | None, size: int) -> tuple[str, str | None]:
    if model is None:
        return "corrupt", None
    if size > model_registry.BUDGET_BYTES:
        return "over_budget", None
    if model_registry.inline_detail_bytes(model):
        return "legacy_inline", None
    if size >= int(model_registry.BUDGET_BYTES * WARNING_RATIO):
        return "warning", None
    return "ok", None


def _entry(directory: Path) -> dict:
    file = directory / "model.json"
    size = file.stat().st_size if file.is_file() else None
    model = None
    error = None
    if file.is_file():
        try:
            model = _read_object(file)
            if not isinstance(model, dict):
                model, error = None, "entry is not a JSON object"
        except (OSError, ValueError) as exc:
            error = str(exc)
    state, _ = _entry_state(model, size or 0)
    entry = {
        "model_id": directory.name,
        "model_name": (model or {}).get("model_name"),
        "status": (model or {}).get("status"),
        "revision": (model or {}).get("revision"),
        "model_json_bytes": size,
        "budget_bytes": model_registry.BUDGET_BYTES,
        "usage_ratio": round((size or 0) / model_registry.BUDGET_BYTES, 4),
        "state": state,
    }
    if error:
        entry["error"] = error
    details = {}
    model = model or {}
    for key in model_registry.DETAIL_KEYS:
        inline = model.get(key)
        ref = model.get(f"{key}_ref")
        details[key] = (
            {"form": "inline", "bytes": len(json.dumps(inline).encode("utf-8"))}
            if isinstance(inline, dict) and inline
            else {"form": "reference", "bytes": ref.get("bytes")}
            if isinstance(ref, dict)
            else {"form": "absent"}
        )
    entry["details"] = details
    return entry


def health(limit: int = 20, cursor: str | None = None) -> dict:
    """Read-only whole-registry report; one broken entry never ends the scan.

    Problem lists (over-budget, near-budget, corrupt) are reported in full up
    to a bounded cap; the per-entry listing is paginated so a large registry
    never produces an unbounded response (BUG-077).
    """
    if not 1 <= limit <= 50:
        raise ValueError("limit must be 1–50")
    entries = []
    over = warning = corrupt = legacy = 0
    total = 0
    if general.MODELS.is_dir():
        for directory in sorted(general.MODELS.iterdir()):
            if not directory.is_dir() or not (directory / "model.json").is_file():
                continue
            try:
                entry = _entry(directory)
            except (OSError, ValueError) as exc:  # one unreadable stat must not end the report
                entry = {
                    "model_id": directory.name,
                    "state": "corrupt",
                    "error": str(exc),
                    "model_json_bytes": None,
                    "budget_bytes": model_registry.BUDGET_BYTES,
                }
            entries.append(entry)
            total += entry.get("model_json_bytes") or 0
            state = entry["state"]
            over += state == "over_budget"
            warning += state == "warning"
            corrupt += state == "corrupt"
            legacy += state == "legacy_inline"

    def _problems(state: str) -> dict:
        rows = [e for e in entries if e["state"] == state]
        return {
            "count": len(rows),
            "entries": rows[:PROBLEM_LIMIT],
            "complete": len(rows) <= PROBLEM_LIMIT,
        }

    report = {
        "entry_count": len(entries),
        "total_model_json_bytes": total,
        "budget_bytes": model_registry.BUDGET_BYTES,
        "warning_ratio": WARNING_RATIO,
        "summary": {
            "ok": sum(e["state"] == "ok" for e in entries),
            "warning": warning,
            "legacy_inline": legacy,
            "over_budget": over,
            "corrupt": corrupt,
        },
        "over_budget": _problems("over_budget"),
        "warning": _problems("warning"),
        "corrupt": _problems("corrupt"),
        "legacy_inline_count": legacy,
        "migration": {
            "needed": over + legacy,
            "tool": "creo_migrate_registry",
            "usage": "inspect first, then apply with an idempotency_key",
        },
        "generated_at": bridge.now(),
    }
    return _page(report, "entries", entries, limit, cursor, "registry_health")


def _log(action: dict) -> None:
    path = general.MODELS / MIGRATION_LOG
    path.parent.mkdir(exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({**action, "ts": bridge.now()}, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _backup(file: Path) -> str | None:
    """Preserve original bytes once; keep the first backup on reruns."""
    backup = file.with_name(file.name + JOB_BACKUP_SUFFIX)
    if file.name == "model.json":
        backup = file.with_name(MODEL_BACKUP)
    if backup.is_symlink() or backup.is_junction():
        raise ValueError("Migration backup cannot be a link")
    if backup.is_file():
        _read_object(backup)
        return None
    data = file.read_bytes()
    temporary = backup.with_name(backup.name + ".tmp")
    if temporary.is_symlink() or temporary.is_junction():
        raise ValueError("Migration temporary backup cannot be a link")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, backup)
    return hashlib.sha256(data).hexdigest()


def _split_request(request: dict, job_dir: Path) -> bool:
    """Split a stored request's inline model/component details; True if changed."""
    changed = False
    for holder in [request.get("model"), *(request.get("components") or {}).values()]:
        if isinstance(holder, dict) and model_registry.inline_detail_bytes(holder):
            model_registry.split_details(holder, job_dir / "details")
            changed = True
    return changed


def _migrate_entry(directory: Path, report: list) -> None:
    file = directory / "model.json"
    if not file.is_file():
        report.append({"model_id": directory.name, "result": "skipped", "reason": "no entry"})
        return
    raw = file.read_bytes()
    try:
        model = json.loads(raw)
        if not isinstance(model, dict):
            raise ValueError("not an object")
    except (OSError, ValueError) as exc:
        report.append(
            {"model_id": directory.name, "result": "refused", "reason": f"unreadable: {exc}"}
        )
        return
    if not model_registry.inline_detail_bytes(model):
        report.append({"model_id": directory.name, "result": "already_migrated"})
        return
    backup_sha = _backup(file)
    if backup_sha is None:
        backup_sha = hashlib.sha256(
            (
                file.with_name(MODEL_BACKUP).read_bytes()
                if file.with_name(MODEL_BACKUP).is_file()
                else raw
            )
        ).hexdigest()
    # Details persist first; the control record publishes atomically after.
    model_registry.write_model(directory, model)
    report.append(
        {
            "model_id": directory.name,
            "result": "migrated",
            "backup": MODEL_BACKUP,
            "backup_sha256": backup_sha,
            "control_sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
        }
    )


def _migrate_job(job_id: str, report: list) -> None:
    directory = bridge.job_path(job_id)
    for name in ("job.json", "request.json"):
        file = directory / name
        if not file.is_file():
            continue
        try:
            document = _read_object(file)
        except (OSError, ValueError):
            continue  # Foreign or corrupt evidence is never rewritten.
        changed = False
        if name == "job.json" and isinstance(document.get("result"), dict):
            result = document["result"]
            if model_registry.inline_detail_bytes(result) or isinstance(
                result.get("aliases"), dict
            ):
                model_registry.split_job_result(result, directory)
                changed = True
        if name == "request.json" and isinstance(document, dict):
            changed = _split_request(document, directory) or changed
        if not changed:
            continue
        backup_sha = _backup(file)
        bridge.write_json(file, document, durable=True)
        report.append(
            {
                "job_id": job_id,
                "result": "job_file_split",
                "file": name,
                "backup": file.name + JOB_BACKUP_SUFFIX,
                "backup_sha256": backup_sha,
            }
        )


def _pending(directories: list[Path]) -> list[dict]:
    pending = []
    for directory in directories:
        file = directory / "model.json"
        try:
            model = _read_object(file)
        except (OSError, ValueError):
            pending.append({"model_id": directory.name, "state": "corrupt", "action": "refused"})
            continue
        if model.get("model_id") != directory.name:
            raise ValueError("Migration record identity does not match its model directory")
        if model_registry.inline_detail_bytes(model):
            pending.append(
                {
                    "model_id": directory.name,
                    "model_json_bytes": file.stat().st_size,
                    "inline_details": sorted(model_registry.inline_detail_bytes(model)),
                    "job_chain": _job_chain(model),
                }
            )
    return pending


def _check_owners(pending: list[dict]) -> None:
    """The OS lock excludes workers; reservations also exclude runners about to start."""
    from creo_mechdog import reconciliation

    for item in pending:
        if item.get("state") == "corrupt":
            continue
        model_id = item["model_id"]
        model = _read_object(_model_directory(model_id) / "model.json")
        protected = {model.get("pending_job"), model.get("recovery_pending")} - {None}
        for job_id in item["job_chain"]:
            directory = bridge.job_path(job_id)
            for name in ("details", "details/details"):
                if (directory / name).is_symlink() or (directory / name).is_junction():
                    raise ValueError("Job detail directories cannot be links")
            manifest_file = directory / "job.json"
            job = _read_object(manifest_file) if manifest_file.is_file() else {}
            if job.get("model_id", model_id) != model_id:
                raise ValueError("Migration job belongs to a different model")
            request_file = directory / "request.json"
            if request_file.is_file():
                request = _read_object(request_file)
                if request.get("model", {}).get("model_id") != model_id:
                    raise ValueError("Migration request belongs to a different model")
            # A reserved/queued runner can start as soon as this lock is released;
            # migration is not permission to rewrite its captured request.
            active = job.get("status") in ("queued", "waiting_for_channel", "running")
            identities = [job.get("runner_identity")]
            owner_file = directory / "native_owner.json"
            if owner_file.is_file():
                identities.append(_read_object(owner_file))
            owner_uncertain = any(
                identity is not None and not reconciliation._stopped(identity)["stopped"]
                for identity in identities
            )
            if active or owner_uncertain:
                raise bridge.ToolkitBusy(
                    "Registry migration cannot rewrite an active or unproven job",
                    holder={"job_id": job_id, "model_id": model_id, "operation": "registry_owner"},
                )
            if job_id in protected:
                evidence = reconciliation._owners(job_id, read_metadata=_read_object)
                if not evidence["stopped"]:
                    raise bridge.ToolkitBusy(
                        "Registry migration requires proof that protected owners stopped",
                        holder={
                            "job_id": job_id,
                            "model_id": model_id,
                            "operation": "registry_owner",
                        },
                    )


def migrate(
    mode: str = "inspect",
    targets: list[str] | None = None,
    idempotency_key: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
) -> dict:
    """Inspect or apply the registry migration (BUG-077).

    Migration targets are entries that still inline detail payloads (including
    over-budget ones). Apply requires an idempotency key; the same key replays
    the recorded result instead of rerunning.
    """
    if mode not in ("inspect", "apply"):
        raise ValueError("mode must be inspect or apply")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit must be 1–50")
    if targets is not None and (not isinstance(targets, list) or not targets):
        raise ValueError("targets must be a non-empty list of existing model_ids")
    if targets is not None:
        for target in targets:
            _model_directory(target)
        targets = sorted(set(targets))
    if mode == "apply":
        if not idempotency_key or not KEY_PATTERN.fullmatch(idempotency_key):
            raise ValueError("apply requires an idempotency_key of 8-80 letters/digits/_/-")
        with bridge.toolkit_lock(operation="migrate_registry"):
            return _apply(targets, idempotency_key, limit, cursor)
    directories = _directories(targets)
    pending = _pending(directories)
    return _page(
        {
            "mode": "inspect",
            "entries_needing_migration": len(pending),
            "apply_usage": "rerun with mode=apply, the same targets (or none) and a fresh idempotency_key",
            "budget_bytes": model_registry.BUDGET_BYTES,
        },
        "entries",
        pending,
        limit,
        cursor,
        "registry_migration_inspect:" + hashlib.sha256(json.dumps(targets).encode()).hexdigest(),
    )


def _directories(targets: list[str] | None) -> list[Path]:
    if targets is not None:
        return [_model_directory(target) for target in targets]
    if not general.MODELS.is_dir():
        return []
    return [
        _model_directory(d.name)
        for d in sorted(general.MODELS.iterdir())
        if (d / "model.json").is_file()
    ]


def _apply(targets: list[str] | None, idempotency_key: str, limit: int, cursor: str | None) -> dict:
    fingerprint = hashlib.sha256(
        json.dumps({"targets": targets}, sort_keys=True).encode()
    ).hexdigest()[:16]
    key = hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]
    record_file = general.MODELS / f"registry-migration-{key}.json"
    scope = "registry_migration_apply:" + key
    if record_file.is_file():
        record = _read_object(record_file)
        if record.get("fingerprint") != fingerprint:
            raise ValueError(
                "This idempotency_key was used for a different target set; use a new key"
            )
        return _page(
            {**record, "replayed": True}, "actions", record["actions"], limit, cursor, scope
        )
    if cursor is not None:
        raise ValueError(
            "Apply cursors require an existing idempotent result; start without cursor"
        )
    pending = _pending(_directories(targets))
    _check_owners(pending)
    report: list[dict] = []
    jobs_done: set[str] = set()
    for item in pending:
        directory = _model_directory(item["model_id"])
        if item.get("state") == "corrupt":
            report.append({"model_id": item["model_id"], "result": "refused", "reason": "corrupt"})
            continue
        for job_id in item.get("job_chain", []):
            if job_id not in jobs_done:
                jobs_done.add(job_id)
                _migrate_job(job_id, report)
        _migrate_entry(directory, report)
        _log({"action": "migrate", "model_id": item["model_id"], "mode": "apply"})
    result = {
        "mode": "apply",
        "migrated": sum(r.get("result") == "migrated" for r in report),
        "job_files_split": sum(r.get("result") == "job_file_split" for r in report),
        "already_migrated": sum(r.get("result") == "already_migrated" for r in report),
        "refused": sum(r.get("result") == "refused" for r in report),
        "actions": report,
        "migration_log": str(general.MODELS / MIGRATION_LOG),
        "completed_at": bridge.now(),
    }
    bridge.write_json(record_file, {**result, "fingerprint": fingerprint}, durable=True)
    return _page({**result, "replayed": False}, "actions", report, limit, None, scope)
