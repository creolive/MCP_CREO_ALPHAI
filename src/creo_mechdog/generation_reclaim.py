"""DEV-027 / T11: explicit, evidence-bound reclamation of build generations.

``inspect`` classifies exactly the selected loader/payload generations with the
existing generation inventory's reference classification (current, local
registration, runtime evidence and unknown records), proves each path is inside
this project's own generation roots and free of links, and publishes a
600-second evidence token bound to the targets, their directory content digests
and the reference evidence. ``apply`` takes the common channel lock that builds
and generation publication already hold, re-verifies the frozen evidence, then
re-checks each directory immediately before deleting it. Nothing runs
automatically, no DLL is loaded and no Toolkit connection is made; deletion is
never rolled back, so every item reports its real outcome.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bridge
from creo_mechdog.blend_callback import generation_inventory

TOKEN_SECONDS = 600
SELECTION_LIMIT = 50
REPLAY_LIMIT_BYTES = 1024 * 1024
LOADER_ROOT = "blend_loader"
PAYLOAD_ROOT = "blend_callback"
ROOTS = (LOADER_ROOT, PAYLOAD_ROOT)
KEYS = {
    LOADER_ROOT: re.compile(r"[0-9a-f]{64}(?:-[0-9a-f]{12})?\Z"),
    PAYLOAD_ROOT: re.compile(r"[0-9a-f]{64}\Z"),
}
KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]{8,80}\Z")
MODULE_FILE = {LOADER_ROOT: "loader.dll", PAYLOAD_ROOT: "callback.dll"}
# A generation directory is flat and this project owns every name in it. An
# unexpected entry keeps the generation instead of guessing it is disposable.
OWNED_FILES = {
    LOADER_ROOT: frozenset({"loader.dll", "protk.dat", "deployment.json", "callback_result.json"}),
    PAYLOAD_ROOT: frozenset(
        {"callback.dll", "callback_bootstrap.json", "protk.dat", "callback_result.json"}
    ),
}
# A resident DLL image is re-checked per item at apply time, so the lock state
# is deliberately not frozen into the evidence token.
LOCK_EVIDENCE = "file_locked"


def _registry() -> Path:
    return bridge.ROOT / "generation_reclaim"


def _digest_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def _is_link(path: Path) -> bool | None:
    """A symlink, junction or other reparse point is never reclaimed."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError:
        return True  # Unreadable is treated as unsafe.
    if path.is_symlink():
        return True
    return bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _read_record(path: Path, label: str) -> dict:
    if not path.is_file():
        raise ValueError(f"{label} is missing; inspect again")
    if path.stat().st_size > REPLAY_LIMIT_BYTES:
        raise ValueError(f"{label} is unreadable; inspect again")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise ValueError(f"{label} is unreadable; inspect again: {error}") from None
    if not isinstance(value, dict):
        raise ValueError(f"{label} is unreadable; inspect again")
    return value


def _selection(generation_keys: object) -> list[dict]:
    """Validate the explicit loader/payload target list before touching the disk."""
    if not isinstance(generation_keys, list) or not 1 <= len(generation_keys) <= SELECTION_LIMIT:
        raise ValueError(f"generation_keys must be a list of 1-{SELECTION_LIMIT} entries")
    checked: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for index, entry in enumerate(generation_keys):
        if not isinstance(entry, dict) or set(entry) != {"root", "key"}:
            raise ValueError(
                f"generation_keys[{index}] requires exactly root (blend_loader|blend_callback) "
                "and key"
            )
        root, key = entry["root"], entry["key"]
        if root not in ROOTS:
            raise ValueError(f"generation_keys[{index}] has an unsupported root")
        if not isinstance(key, str) or not KEYS[root].fullmatch(key):
            raise ValueError(
                f"generation_keys[{index}] has an invalid {root} generation key; only the "
                "hexadecimal generation directory names are accepted, never paths, drives or '..'"
            )
        if (root, key) in seen:
            raise ValueError("Duplicate generation_keys entries are not accepted")
        seen.add((root, key))
        checked.append({"root": root, "key": key})
    return checked


def _inventory(build: Path) -> dict:
    try:
        return generation_inventory(build)
    except OSError as error:
        raise ValueError(f"Generation inventory is unavailable: {error}") from None


def _entry(inventory: dict, root: str, key: str) -> dict | None:
    field = "generation_key" if root == LOADER_ROOT else "payload_sha256"
    group = "generations" if root == LOADER_ROOT else "payload_generations"
    for entry in inventory.get(group, []):
        if entry.get(field) == key:
            return entry
    return None


def _binding(entry: dict, root: str) -> dict:
    """The reference evidence a token freezes; occupancy is re-checked per item."""
    runtime = [item for item in entry.get("runtime_evidence", []) if item != LOCK_EVIDENCE]
    if root == LOADER_ROOT:
        return {
            "current": entry.get("current"),
            "registered_by": entry.get("registered_by", []),
            "review_reasons": entry.get("review_reasons", []),
            "deployment_dll_sha256": entry.get("deployment_dll_sha256"),
            "runtime_evidence": runtime,
        }
    return {
        "current": entry.get("current"),
        "review_reasons": entry.get("review_reasons", []),
        "referenced_by_loader_generations": entry.get("referenced_by_loader_generations", []),
        "runtime_evidence": runtime,
    }


def _retained_keys(build: Path, inventory: dict) -> dict[str, str | None]:
    """Keep the newest non-current generation of each root as the rollback target.

    Older generations stay available for an explicit rollback; retaining the
    immediately previous deployment keeps that path usable after a bad upgrade
    without keeping the whole history.
    """
    retained: dict[str, str | None] = {}
    for root in ROOTS:
        group = "generations" if root == LOADER_ROOT else "payload_generations"
        field = "generation_key" if root == LOADER_ROOT else "payload_sha256"
        ranked: list[tuple[float, str]] = []
        for entry in inventory.get(group, []):
            if entry.get("current") or entry.get("registered_by"):
                continue
            key = entry.get(field)
            try:
                stamp = (build / root / key).stat().st_mtime
            except (OSError, TypeError):
                continue
            ranked.append((stamp, key))
        retained[root] = max(ranked)[1] if ranked else None
    return retained


def _empty_scan() -> dict:
    return {
        "content_sha256": None,
        "file_count": 0,
        "bytes": 0,
        "problems": [],
        "unexpected": [],
        "names": [],
    }


def _scan(directory: Path, root: str) -> dict:
    """Hash one flat generation directory and report content it does not own."""
    problems: list[str] = []
    unexpected: list[str] = []
    entries: list[tuple[str, str]] = []
    total = 0
    try:
        children = sorted(os.scandir(directory), key=lambda item: item.name)
    except OSError:
        return {**_empty_scan(), "problems": ["content_unreadable"]}
    for child in children:
        attributes = getattr(child.stat(follow_symlinks=False), "st_file_attributes", 0)
        if child.is_symlink() or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            problems.append("reparse_point")
            unexpected.append(child.name)
            continue
        if not child.is_file():
            unexpected.append(child.name)
            continue
        if child.name not in OWNED_FILES[root]:
            unexpected.append(child.name)
        try:
            digest = _digest_path(Path(child.path))
            size = child.stat().st_size
        except OSError:
            problems.append("content_unreadable")
            continue
        entries.append((child.name, digest))
        total += size
    if unexpected:
        problems.append("unexpected_content")
    payload = "\n".join(f"{name} {digest}" for name, digest in entries).encode()
    return {
        "content_sha256": hashlib.sha256(payload).hexdigest() if entries else None,
        "file_count": len(entries),
        "bytes": total,
        "problems": problems,
        "unexpected": unexpected,
        "names": [name for name, _ in entries],
    }


def _locked_files(directory: Path, names: list[str]) -> list[str]:
    """An exclusive write open detects a resident image without loading anything."""
    locked: list[str] = []
    for name in names:
        try:
            handle = open(directory / name, "r+b")
        except FileNotFoundError:
            continue
        except OSError:
            locked.append(name)
            continue
        handle.close()
    return locked


def _audit(build: Path, inventory: dict, target: dict, retained: dict) -> dict:
    """Classify one generation; anything unproven keeps the directory."""
    root, key = target["root"], target["key"]
    root_dir = build / root
    directory = root_dir / key
    reasons: list[str] = []
    entry = _entry(inventory, root, key)

    if _is_link(root_dir):
        reasons.append("generation_root_is_link")
    try:
        resolved_root = root_dir.resolve(strict=True)
    except OSError:
        reasons.append("generation_root_missing")
        resolved_root = None
    resolved = None
    if resolved_root is not None:
        try:
            resolved = directory.resolve(strict=True)
        except FileNotFoundError:
            reasons.append("generation_missing")
        except OSError:
            reasons.append("path_unresolvable")
    if resolved is not None:
        if not resolved.is_relative_to(resolved_root):
            reasons.append("outside_generation_root")
        elif resolved.name != key:
            reasons.append("path_redirected")
        if _is_link(directory):
            reasons.append("reparse_point")

    scanned = _scan(directory, root) if resolved is not None else _empty_scan()
    reasons.extend(scanned["problems"])
    if resolved is not None and MODULE_FILE[root] not in scanned["names"]:
        reasons.append("not_a_generation")
    locked = _locked_files(directory, scanned["names"]) if resolved is not None else []
    if locked:
        reasons.append(LOCK_EVIDENCE)

    if entry is None:
        reasons.append("inventory_unaudited")
        binding = None
    else:
        binding = _binding(entry, root)
        if entry.get("current"):
            reasons.append("current")
        if entry.get("registered_by"):
            reasons.append("registered")
        if root == PAYLOAD_ROOT and entry.get("referenced_by_loader_generations"):
            reasons.append("referenced_by_loader_generation")
        reasons.extend(f"runtime_{item}" for item in binding["runtime_evidence"])
        reasons.extend(entry.get("review_reasons", []))
        if entry.get("referenced") and not reasons:
            reasons.append("referenced")
    if retained.get(root) == key:
        reasons.append("rollback_retention")

    unique = list(dict.fromkeys(reasons))
    return {
        "root": root,
        "generation_key": key,
        "path": str(directory),
        "status": "kept" if unique else "reclaimable",
        "reasons": unique,
        "content_sha256": scanned["content_sha256"],
        "file_count": scanned["file_count"],
        "bytes": scanned["bytes"],
        "unexpected_entries": scanned["unexpected"],
        "locked_files": locked,
        "current": bool(entry.get("current")) if entry else None,
        "registered_by": entry.get("registered_by", []) if entry else None,
        "runtime_evidence": entry.get("runtime_evidence", []) if entry else None,
        "review_reasons": entry.get("review_reasons", []) if entry else None,
        "rollback_retained": retained.get(root) == key,
        "reference_evidence": binding,
    }


def _inspect(selection: list[dict]) -> dict:
    build = bridge.ROOT / "build"
    inventory = _inventory(build)
    retained = _retained_keys(build, inventory)
    items = [_audit(build, inventory, target, retained) for target in selection]
    reclaimable = [item for item in items if item["status"] == "reclaimable"]
    token = None
    expires_at = None
    if reclaimable:
        token = uuid.uuid4().hex
        created = time.time()
        record = {
            "created": created,
            "token": token,
            "selection": selection,
            "inventory": {
                "records_status": inventory["records_status"],
                "records_definitive": inventory["records_definitive"],
                "record_conflict": inventory["record_conflict"],
                "current_generation_key": inventory["current_generation_key"],
                "retained": retained,
            },
            "items": [
                {
                    "root": item["root"],
                    "generation_key": item["generation_key"],
                    "authorized": item["status"] == "reclaimable",
                    "content_sha256": item["content_sha256"],
                    "reference_evidence": item["reference_evidence"],
                }
                for item in items
            ],
        }
        registry = _registry()
        registry.mkdir(parents=True, exist_ok=True)
        bridge.write_json(registry / f"evidence-{token}.json", record, durable=True)
        expires_at = datetime.fromtimestamp(created + TOKEN_SECONDS, timezone.utc).isoformat()
    return {
        "mode": "inspect",
        "read_only": True,
        "deletes": 0,
        "toolkit_connections": 0,
        "dll_loaded": False,
        "generation_roots": {root: str(build / root) for root in ROOTS},
        "inventory": {
            "records_status": inventory["records_status"],
            "records_definitive": inventory["records_definitive"],
            "record_conflict": inventory["record_conflict"],
            "current_generation_key": inventory["current_generation_key"],
            "generation_count": inventory["generation_count"],
            "payload_generation_count": inventory["payload_generation_count"],
            "reclaim_candidates": inventory["reclaim_candidates"],
            "reclaim_candidates_payload": inventory["reclaim_candidates_payload"],
            "needs_review": inventory["needs_review"],
            "needs_review_payload": inventory["needs_review_payload"],
        },
        "rollback_retained": retained,
        "items": items,
        "reclaimable": [
            {"root": item["root"], "generation_key": item["generation_key"]} for item in reclaimable
        ],
        "kept": [
            {
                "root": item["root"],
                "generation_key": item["generation_key"],
                "reasons": item["reasons"],
            }
            for item in items
            if item["status"] != "reclaimable"
        ],
        "counts": {
            "requested": len(items),
            "reclaimable": len(reclaimable),
            "kept": len(items) - len(reclaimable),
        },
        "evidence_token": token,
        "expires_in_seconds": TOKEN_SECONDS if token else None,
        "expires_at": expires_at,
        "apply": (
            "apply executes exactly these authorized generations: pass evidence_token and a "
            "fresh idempotency_key; nothing outside the token is deleted"
            if token
            else None
        ),
        "note": (
            "Current, locally registered, runtime-referenced, rollback-retained and "
            "unprovable generations are kept; 'not current' or 'no record found' never "
            "authorizes deletion. Nothing is deleted by inspect"
        ),
    }


def _delete(directory: Path, names: list[str]) -> dict:
    """Delete one verified flat generation; report exactly how far it got."""
    removed = 0
    try:
        for name in sorted(names):
            (directory / name).unlink()
            removed += 1
        directory.rmdir()
    except OSError as error:
        return {
            "state": "failed",
            "removed": removed,
            "residual_entries": _residual(directory),
            "error": f"{type(error).__name__}: {error}",
        }
    try:
        os.lstat(directory)
    except FileNotFoundError:
        return {"state": "reclaimed", "removed": removed}
    except OSError as error:
        return {
            "state": "unknown",
            "removed": removed,
            "residual_entries": _residual(directory),
            "error": f"{type(error).__name__}: {error}",
        }
    return {"state": "failed", "removed": removed, "residual_entries": _residual(directory)}


def _residual(directory: Path) -> int | None:
    try:
        return len(list(os.scandir(directory)))
    except OSError:
        return None


def _execute(audit: dict) -> dict:
    """Re-check one item immediately before deleting it."""
    # The audit was taken at apply time; empty reasons is the reclaimable state.
    if audit["reasons"]:
        return {**audit, "status": "kept"}
    directory = Path(audit["path"])
    try:
        names = [child.name for child in os.scandir(directory) if child.is_file()]
    except OSError as error:
        return {
            **audit,
            "status": "failed",
            "reasons": ["delete_failed"],
            "error": f"{type(error).__name__}: {error}",
        }
    outcome = _delete(directory, names)
    item = {**audit, "status": outcome["state"], "deleted_files": outcome["removed"]}
    if outcome["state"] != "reclaimed":
        item["reasons"] = [f"delete_{outcome['state']}"]
        item["residual_entries"] = outcome.get("residual_entries")
        if outcome.get("error"):
            item["error"] = outcome["error"]
    return item


def _tally(items: list[dict]) -> dict:
    names = ("reclaimed", "kept", "failed", "unknown")
    groups: dict[str, list[dict]] = {name: [] for name in names}
    for item in items:
        status = item.get("status")
        if status in groups:
            groups[status].append(
                {
                    "root": item["root"],
                    "generation_key": item["generation_key"],
                    "reasons": item.get("reasons", []),
                }
            )
    return {
        **groups,
        "counts": {name: len(values) for name, values in groups.items()},
        "complete": not groups["failed"] and not groups["unknown"],
        "note": (
            "Deletion is per item and is not rolled back: a failed or unknown item may be "
            "partially deleted. Inspect again before retrying and never resubmit an "
            "unconfirmed item"
        ),
    }


def _apply(evidence_token: str, idempotency_key: str) -> dict:
    registry = _registry()
    record = _read_record(registry / f"evidence-{evidence_token}.json", "Evidence token")
    if record.get("token") != evidence_token:
        raise ValueError("Evidence token does not match its record; inspect again")
    try:
        created = float(record.get("created"))
    except (TypeError, ValueError):
        raise ValueError("Evidence token is unreadable; inspect again") from None
    age = time.time() - created
    if age > TOKEN_SECONDS or age < 0:
        raise ValueError(f"Evidence token expired after {TOKEN_SECONDS} seconds; inspect again")

    pointer = registry / f"intent-{_key_digest(idempotency_key)}.json"
    if pointer.is_file():
        intent = _read_record(pointer, "Reclaim intent")
        if intent.get("evidence_token") != evidence_token:
            raise ValueError("Idempotency key already belongs to another reclaim request")
        items = intent.get("items", [])
        for item in items:
            if item.get("status") == "pending":
                item["status"] = "unknown"
                item["reasons"] = ["interrupted"]
        return {
            **intent,
            "mode": "apply",
            "replayed": True,
            "items": items,
            **_tally(items),
        }

    build = bridge.ROOT / "build"
    inventory = _inventory(build)
    retained = _retained_keys(build, inventory)
    selection = record.get("selection", [])
    frozen = record.get("items", [])
    if len(selection) != len(frozen):
        raise ValueError("Evidence token does not match its targets; inspect again")
    items: list[dict] = []
    for target, planned in zip(selection, frozen):
        audit = _audit(build, inventory, target, retained)
        if not planned.get("authorized"):
            item = {**audit, "status": "kept"}
            if audit["status"] == "reclaimable":
                item["reasons"] = ["not_authorized_by_evidence"]
            items.append(item)
            continue
        changed = [
            code
            for code, current, expected in (
                ("content_changed", audit["content_sha256"], planned.get("content_sha256")),
                (
                    "reference_changed",
                    audit["reference_evidence"],
                    planned.get("reference_evidence"),
                ),
            )
            if current != expected
        ]
        if changed:
            raise ValueError(
                f"Generation {target['root']}:{target['key']} changed since inspect "
                f"({', '.join(changed)}); inspect again before reclaiming"
            )
        items.append({**audit, "status": "pending"})

    intent = {
        "mode": "apply",
        "state": "in_progress",
        "idempotency_key_sha256": _key_digest(idempotency_key),
        "evidence_token": evidence_token,
        "started_at": bridge.now(),
        "toolkit_connections": 0,
        "dll_loaded": False,
        "items": items,
    }
    bridge.write_json(pointer, intent, durable=True)

    for index, item in enumerate(items):
        if item["status"] != "pending":
            continue
        items[index] = _execute(item)
        intent["items"] = items
        bridge.write_json(pointer, intent, durable=True)

    result = {
        **intent,
        "state": "completed",
        "replayed": False,
        "completed_at": bridge.now(),
        "bytes_reclaimed": sum(
            item.get("bytes", 0) for item in items if item.get("status") == "reclaimed"
        ),
        **_tally(items),
    }
    bridge.write_json(pointer, result, durable=True)
    return result


def reclaim_generations(
    mode: str = "inspect",
    generation_keys: list[dict] | None = None,
    evidence_token: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Inspect or reclaim explicitly selected loader/payload generations (DEV-027)."""
    if mode == "inspect":
        if evidence_token is not None or idempotency_key is not None:
            raise ValueError("Inspect takes generation_keys only; apply takes token and key")
        selection = _selection(generation_keys)
        with bridge.toolkit_lock(operation="reclaim_generations_inspect"):
            return _inspect(selection)
    if mode != "apply":
        raise ValueError("mode must be inspect or apply")
    if generation_keys is not None or not evidence_token or not idempotency_key:
        raise ValueError("apply requires evidence_token and idempotency_key, not generation_keys")
    if not KEY_PATTERN.fullmatch(idempotency_key):
        raise ValueError(
            "idempotency_key must contain 8-80 letters, digits, underscores or hyphens"
        )
    if not bridge.JOB_ID.fullmatch(evidence_token):
        raise ValueError("Invalid evidence_token")
    with bridge.toolkit_lock(operation="reclaim_generations"):
        return _apply(evidence_token, idempotency_key)
