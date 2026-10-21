"""Bounded, read-only native session inventory with frozen pagination."""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path

import bridge
import generic_bridge as general
from creo_mechdog.model_queries import decode_cursor, encode_cursor, fingerprint
from creo_mechdog.reconciliation import identity, owned_file

SNAPSHOT_SECONDS = 600
PAGE_BYTES = 32 * 1024
ACTIVITY_LIMIT = 50
REFRESH_GUIDANCE = (
    "Omit cursor to re-collect the live session inventory; a query carrying a "
    "cursor keeps reading its frozen snapshot and never reflects later session "
    "changes. service_session_changes lists only changes this service caused "
    "since the snapshot; manual GUI changes are not re-checked in real time"
)


def record_session_change(tool: str, summary: str, detail: dict | None = None) -> None:
    """Record a session-content change this service caused (FEAT-043).

    Cross-process, bounded, and only written under the Toolkit channel lock by
    callers, so one writer at a time. Purely informational: entries never
    authorize anything and never replace a fresh live inventory.
    """
    file = bridge.ROOT / "session_activity.json"
    try:
        activity = bridge.read_json(file)
    except (OSError, ValueError):
        activity = {"entries": []}
    entries = activity.get("entries")
    if not isinstance(entries, list):
        entries = []
    entries.append({"at": bridge.now(), "tool": tool, "summary": summary, "detail": detail or {}})
    bridge.write_json(file, {"entries": entries[-ACTIVITY_LIMIT:]}, durable=True)


def _activity_since(created: float) -> list[dict]:
    """Bounded entries recorded after a snapshot was created (never a proof)."""
    try:
        activity = bridge.read_json(bridge.ROOT / "session_activity.json")
    except (OSError, ValueError):
        return []
    entries = activity.get("entries")
    if not isinstance(entries, list):
        return []
    selected = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        recorded = entry.get("at")
        if not isinstance(recorded, str) or recorded <= "":
            continue
        try:
            from datetime import datetime, timezone

            moment = datetime.fromisoformat(recorded)
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            if moment.timestamp() >= created:
                selected.append(entry)
        except ValueError:
            continue
    return selected[-10:]


def _selection() -> str:
    config = bridge.config()
    return fingerprint({key: config.get(key) for key in ("creo_root", "creo_session_id")})


def _probe(directory: Path, manifest: dict) -> dict:
    exe = bridge.build_native()
    with (directory / "worker.log").open("wb") as log:
        proc = subprocess.run(
            [str(exe), "generic", str(directory)],
            cwd=directory,
            env=bridge.native_environment(),
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=115,
            creationflags=bridge.HIDDEN,
        )
    result = bridge.read_json(directory / "native_result.json")
    if (
        proc.returncode
        or result.get("delivery_complete") is not True
        or result.get("disconnect_code") != 0
        or result.get("success") is not True
    ):
        raise RuntimeError(result.get("message", "Session inventory could not be confirmed"))
    return result


def _associations(items: list[dict]) -> None:
    # Origin plus verified file identity proves a relationship. Display names
    # and transient integer model IDs never establish managed ownership.
    records: dict[str, list[tuple[str, str, str]]] = {}
    deadline = time.monotonic() + 5
    for path in general.MODELS.glob("*/model.json"):
        if time.monotonic() > deadline:
            break
        try:
            model = bridge.read_json(path)
            if model.get("status") == "abandoned":
                continue
            snapshot = model.get("prepared_snapshot", {})
            file = model.get("part_file") or snapshot.get("file", {}).get("path")
            sha = model.get("part_sha256") or snapshot.get("file", {}).get("sha256")
            if file and sha:
                owned = owned_file(model, file)
                records.setdefault(str(owned.resolve()), []).append(
                    ("model_id", model["model_id"], sha)
                )
            source = model.get("adopted_from", {})
            if (
                model.get("status") == "ready"
                and source.get("origin")
                and source.get("origin_sha256")
            ):
                records.setdefault(str(Path(source["origin"]).resolve()), []).append(
                    ("adopted_copy_model_id", model["model_id"], source["origin_sha256"])
                )
        except (OSError, ValueError, KeyError):
            continue
    for item in items:
        item.update(model_id=None, adopted_copy_model_id=None)
        if not item.get("origin") or time.monotonic() > deadline:
            continue
        try:
            origin = Path(item["origin"])
            matches = records.get(str(origin.resolve()), [])
            if matches:
                actual = identity(origin, deadline)["sha256"]
                for field in ("model_id", "adopted_copy_model_id"):
                    proven = {mid for name, mid, sha in matches if name == field and sha == actual}
                    if len(proven) == 1:
                        item[field] = proven.pop()
        except (OSError, ValueError):
            continue


def list_session_models(limit: int = 20, cursor: str | None = None) -> dict:
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit must be 1-50")
    page = decode_cursor(cursor)
    if page is None:
        with bridge.toolkit_lock(operation="list_session_models"):
            job_id = uuid.uuid4().hex
            directory = bridge.job_path(job_id)
            (directory / "output").mkdir(parents=True)
            model = {
                "model_id": None,
                "model_name": "session_inventory",
                "aliases": {},
                "output_directory": str(directory / "output"),
                "part_file": None,
            }
            request = {
                "model": model,
                "new": False,
                "operations": [],
                "readonly": True,
                "template_file": "",
                "components": {},
                "session_models": True,
            }
            manifest = {
                "job_id": job_id,
                "kind": "session_models_query",
                "status": "running",
                "created_at": bridge.now(),
            }
            bridge.write_json(directory / "request.json", request)
            bridge.write_json(directory / "job.json", manifest)
            try:
                selection = _selection()
                result = _probe(directory, manifest)
                items = result["models"]
                _associations(items)
                snapshot = {
                    "models": items,
                    "created": time.time(),
                    "checked_at": bridge.now(),
                    "session_fingerprint": result["session_fingerprint"],
                    "selection": selection,
                    "complete": result.get("complete", False),
                    "type_errors": result.get("type_errors", []),
                    "truncated": result.get("truncated", False),
                }
                bridge.write_json(directory / "session_models.json", snapshot, durable=True)
                manifest["status"] = "succeeded"
            except Exception as error:
                manifest.update(status="failed", message=str(error))
                raise
            finally:
                manifest["finished_at"] = bridge.now()
                bridge.write_json(directory / "job.json", manifest, durable=True)
        offset = 0
    else:
        if page.get("kind") != "session_models" or not bridge.JOB_ID.fullmatch(
            page.get("snapshot", "")
        ):
            raise ValueError("Invalid session model cursor")
        job_id = page["snapshot"]
        file = bridge.job_path(job_id) / "session_models.json"
        if not file.is_file() or file.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("Session model snapshot is unavailable; list again without cursor")
        snapshot = bridge.read_json(file)
        if (
            time.time() - snapshot["created"] > SNAPSHOT_SECONDS
            or snapshot["selection"] != _selection()
        ):
            raise ValueError(
                "Session model snapshot expired or session selection changed; list again"
            )
        if page.get("fingerprint") != fingerprint(snapshot):
            raise ValueError("Session model snapshot changed; list again")
        offset = page["offset"]
    models = snapshot["models"]
    if offset > len(models):
        raise ValueError("Invalid session model cursor offset")
    response = {
        "models": [],
        "total": len(models),
        "checked_at": snapshot["checked_at"],
        "session_fingerprint": snapshot["session_fingerprint"],
        "snapshot_id": job_id,
        "complete": snapshot["complete"],
        "truncated": snapshot["truncated"],
        "type_errors": snapshot["type_errors"],
        "next_cursor": None,
        "snapshot_only": True,
        "snapshot_age_seconds": max(0, int(time.time() - snapshot["created"])),
        "expires_in_seconds": max(0, int(SNAPSHOT_SECONDS - (time.time() - snapshot["created"]))),
        "refresh_guidance": REFRESH_GUIDANCE,
        "service_session_changes": _activity_since(snapshot["created"]),
        "service_session_changes_note": (
            "changes this service recorded since the snapshot; GUI changes are "
            "not re-checked in real time"
        ),
    }
    for item in models[offset : offset + limit]:
        response["models"].append(item)
        if len(json.dumps(response, ensure_ascii=False).encode("utf-8")) > PAGE_BYTES - 1024:
            response["models"].pop()
            if not response["models"]:
                raise ValueError("One session model exceeds the response byte budget")
            break
    next_offset = offset + len(response["models"])
    if next_offset < len(models):
        response["next_cursor"] = encode_cursor(
            {
                "kind": "session_models",
                "snapshot": job_id,
                "offset": next_offset,
                "fingerprint": fingerprint(snapshot),
            }
        )
    return response
