"""FEAT-048: ordered path adoption with independent durable item decisions.

Only the parent is submitted. Item job directories are durable execution and
recovery evidence, not separately scheduled jobs. Native calls run serially
inside the parent's single channel lock. Polling never resumes native work.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import bridge
import generic_bridge as general
from creo_mechdog import adoption, inspection_refs, model_registry
from creo_mechdog.open_file import select_file
from creo_mechdog.reconciliation import HASH_SECONDS, identity

MAX_ITEMS = 20


def lifetime_seconds(count: int) -> int:
    """Fixed bound: admission, per-item build/native/hashes, metadata margin."""
    if not 1 <= count <= MAX_ITEMS:
        raise ValueError("Invalid path-adoption item count")
    return 120 + count * (180 + adoption.WORKER_SECONDS + 5 * HASH_SECONDS + 30) + 30


def _store() -> Path:
    directory = bridge.JOBS / "file_adoption"
    if directory.is_symlink() or directory.is_junction():
        raise ValueError("Path adoption storage cannot be a link")
    directory.mkdir(exist_ok=True)
    return directory


def _read(file: Path) -> dict | None:
    return adoption._read(file, metadata_kind="commit_journal", failed_stage="path_adoption")


def _paths(value: str | list[str]) -> list[str]:
    paths = [value] if isinstance(value, str) else value
    if not isinstance(paths, list) or not 1 <= len(paths) <= MAX_ITEMS:
        raise ValueError("file_path must be a path or ordered list of 1–20 paths")
    if any(not isinstance(p, str) or not p.strip() for p in paths):
        raise ValueError("Every file_path must be a non-empty string")
    return paths


def _select(paths: list[str]) -> list[dict]:
    items = []
    seen = {}
    for index, raw in enumerate(paths):
        item = {"index": index, "input_path": raw, "status": "pending"}
        try:
            selected, kind, _ = select_file(raw)
            file = identity(selected)
            item.update(file=file, selected_path=file["path"], model_type=kind)
            origin = str(selected.resolve()).casefold()
            if origin in seen:
                item.update(status="refused", reason="duplicate_source", duplicate_of=seen[origin])
            else:
                seen[origin] = index
                if kind != "part":
                    item.update(status="refused", reason="unsupported_model_type")
        except (OSError, ValueError) as error:
            item.update(status="refused", reason="invalid_source", message=str(error))
        items.append(item)
    return items


def _selection(items: list[dict]) -> list[dict]:
    return [{k: item.get(k) for k in ("input_path", "file", "duplicate_of")} for item in items]


def _publish(job_id: str, manifest: dict) -> None:
    bridge.write_json(bridge.job_path(job_id) / "job.json", manifest, durable=True)


def _refuse(item: dict, reason: str, message: str = "") -> None:
    item.update(status="refused", reason=reason, message=message)


def _check_file(item: dict) -> None:
    try:
        current = identity(Path(item["file"]["path"]))
    except (OSError, ValueError) as error:
        raise adoption.AdoptionRefused("source_unavailable", str(error)) from error
    if current != item["file"]:
        raise adoption.AdoptionRefused("source_changed", "Selected source bytes changed")


def _conflict(item: dict) -> None:
    conflict = adoption._origin_conflict(Path(item["file"]["path"]), exclude=None)
    if conflict:
        item["conflict"] = conflict
        raise adoption.AdoptionRefused(conflict["reason"], conflict["message"])


def _choice(item: dict, action: str) -> dict:
    choice = {
        "action": action,
        "path_source": True,
        "origin": item["file"]["path"],
        "origin_sha256": item["file"]["sha256"],
    }
    if action == "apply":
        live = item["live"]
        choice.update(
            session_fingerprint=live["session_fingerprint"], source_state=live["source_state"]
        )
        choice.update(inspection_refs.request_field(live, "live_inspection"))
    return choice


def inspect(paths: list[str]) -> dict:
    items = _select(paths)
    parent_id = uuid.uuid4().hex
    directory = bridge.job_path(parent_id)
    directory.mkdir()
    manifest = {
        "job_id": parent_id,
        "batch_id": parent_id,
        "kind": "adoption_file_inspect",
        "status": "running",
        "created_at": bridge.now(),
        "items": items,
        "item_count": len(items),
    }
    _publish(parent_id, manifest)
    with bridge.toolkit_lock(operation="inspect_adoption_files", job_id=parent_id):
        stopped = False
        for item in items:
            if stopped:
                item.update(status="not_attempted", reason="previous_unknown_outcome")
                continue
            if item["status"] == "refused":
                continue
            probe = {
                "job_id": uuid.uuid4().hex,
                "parent_job_id": parent_id,
                "kind": "adoption_file_probe",
                "status": "running",
                "created_at": bridge.now(),
            }
            job_dir = bridge.job_path(probe["job_id"])
            (job_dir / "output").mkdir(parents=True)
            item["evidence_job_id"] = probe["job_id"]
            model = adoption._new_model(uuid.uuid4().hex)
            try:
                _check_file(item)
                _conflict(item)
                bridge.write_json(
                    job_dir / "request.json",
                    adoption._native_request(model, _choice(item, "inspect")),
                    durable=True,
                )
                result = adoption._native(job_dir, probe)
                adoption._split_result(result, job_dir)
                live = result["live"]
                item["live"] = live
                _check_file(item)
                if (
                    result.get("source_unchanged") is not True
                    or result.get("window_unchanged") is not True
                ):
                    raise RuntimeError("Native path-source/window evidence is incomplete")
                refusal = adoption._refusal_reason(live)
                if refusal:
                    item["refusal_details"] = adoption._refusal_details(live)
                    raise adoption.AdoptionRefused(*refusal)
                model.update(
                    model_type=live["model_type"],
                    adopted_from={
                        "origin": item["file"]["path"],
                        "origin_sha256": item["file"]["sha256"],
                        "source_kind": "path",
                        "state": "pending",
                        "source_state": live["source_state"],
                    },
                )
                item.update(status="eligible", model_id=model["model_id"], model=model)
                probe["status"] = "succeeded"
            except adoption.AdoptionRefused as error:
                _refuse(item, error.reason, str(error))
                probe.update(status="failed", reason=error.reason, message=str(error))
            except Exception as error:
                # After dispatch an unconfirmed retrieval can leave session residents.
                stopped = bool(probe.get("worker_started"))
                item.update(
                    status="unknown_outcome" if stopped else "refused",
                    reason="inspection_unconfirmed" if stopped else "inspection_failed",
                    message=str(error),
                )
                probe.update(status="unknown_outcome" if stopped else "failed", message=str(error))
            finally:
                if probe.get("result"):
                    item["native_evidence"] = {
                        k: probe["result"][k]
                        for k in (
                            "resident_set_changed",
                            "path_source_state",
                            "message",
                            "failed_stage",
                            "delivery_complete",
                            "disconnect_code",
                        )
                        if k in probe["result"]
                    }
                probe["finished_at"] = bridge.now()
                _publish(probe["job_id"], probe)
        if not stopped:
            token = uuid.uuid4().hex
            record = {"token": token, "created": time.time(), "paths": paths, "items": items}
            bridge.write_json(_store() / f"evidence-{token}.json", record, durable=True)
            manifest.update(evidence_token=token, expires_in_seconds=adoption.TOKEN_SECONDS)
        manifest.update(
            status="unknown_outcome" if stopped else "succeeded",
            finished_at=bridge.now(),
            available=not stopped and any(i["status"] == "eligible" for i in items),
        )
    manifest["items"] = [_public_item(i) for i in items]
    _publish(parent_id, manifest)
    return manifest


def _public_item(item: dict) -> dict:
    return {
        key: value for key, value in item.items() if key not in ("model", "journal", "live")
    } | ({"source": adoption._summary_only({"live": item["live"]})} if "live" in item else {})


def apply(paths: list[str], token: str, key: str) -> dict:
    adoption._key(key)
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("Invalid path-adoption evidence_token")
    selected = _select(paths)
    arguments = {"paths": paths, "selection": _selection(selected), "evidence_token": token}
    pointer = _store() / f"intent-{adoption.digest(key)}.json"
    # Replay is read-only and works while the original parent owns the channel.
    existing = _read(pointer)
    if existing:
        return _replay(existing, arguments)
    with bridge.toolkit_lock(operation="submit_adoption_files"):
        existing = _read(pointer)
        if existing:
            return _replay(existing, arguments, locked=True)
        evidence = _read(_store() / f"evidence-{token}.json")
        if not evidence or time.time() - evidence["created"] > adoption.TOKEN_SECONDS:
            raise ValueError("Path-adoption evidence expired; inspect again")
        if evidence["paths"] != paths or _selection(evidence["items"]) != arguments["selection"]:
            raise ValueError("Ordered paths or selected file identities changed; inspect again")
        job_id = uuid.uuid4().hex
        directory = bridge.job_path(job_id)
        directory.mkdir()
        items = evidence["items"]
        manifest = {
            "job_id": job_id,
            "batch_id": job_id,
            "kind": "adoption_file",
            "status": "queued",
            "created_at": bridge.now(),
            "idempotency_key": key,
            "item_count": len(items),
            "items": [],
            "stage": "intent_persisted",
            "message": "Batch accepted; poll this parent job_id only",
        }
        # The parent intent is durable before reservations. A launch failure is
        # terminal; a repeated key cannot execute it again.
        bridge.write_json(directory / "batch.json", {"items": items}, durable=True)
        manifest["items"] = [_public_item(i) for i in items]
        _publish(job_id, manifest)
        bridge.write_json(pointer, {"job_id": job_id, "arguments": arguments}, durable=True)
        try:
            with (directory / "runner.log").open("ab") as log:
                subprocess.Popen(
                    [sys.executable, str(bridge.ROOT / "bridge.py"), "run-job", job_id],
                    cwd=bridge.ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=bridge.HIDDEN,
                    close_fds=True,
                )
        except Exception as error:
            manifest.update(
                status="failed",
                reason="launch_failed",
                message=str(error),
                finished_at=bridge.now(),
            )
            for item in manifest["items"]:
                if item["status"] == "eligible":
                    item.update(status="not_attempted", reason="launch_failed")
            _publish(job_id, manifest)
            raise
        return manifest


def _replay(existing: dict, arguments: dict, *, locked: bool = False) -> dict:
    if existing["arguments"] != arguments:
        raise ValueError(
            "Idempotency key belongs to different ordered paths, identities or evidence"
        )
    if locked:
        return bridge.read_json(bridge.job_path(existing["job_id"]) / "job.json")
    return bridge.get_job(existing["job_id"], "compact")


def _reserve(parent: dict, item: dict) -> tuple[dict, Path]:
    item_id = uuid.uuid4().hex
    item.update(item_job_id=item_id, status="reserved")
    _publish(parent["job_id"], parent)
    model = item["model"]
    model.update(pending_job=item_id, last_job=item_id, parent_job_id=parent["job_id"])
    path = general.model_path(model["model_id"])
    (path / "output").mkdir(parents=True)
    model_registry.write_model(path, model)
    directory = bridge.job_path(item_id)
    (directory / "output").mkdir(parents=True)
    manifest = {
        "job_id": item_id,
        "parent_job_id": parent["job_id"],
        "kind": "adoption_file_item",
        "model_id": model["model_id"],
        "status": "queued",
        "created_at": bridge.now(),
        "idempotency_key": parent["idempotency_key"],
        "revision": 0,
    }
    journal = adoption._journal(model["model_id"], parent["idempotency_key"])
    bridge.write_json(
        directory / "request.json",
        adoption._native_request(model, _choice(item, "apply")),
        durable=True,
    )
    bridge.write_json(
        journal,
        {
            "state": "intent",
            "job_id": item_id,
            "model_id": model["model_id"],
            "evidence": {"file": item["file"], "live": item["live"]},
        },
        durable=True,
    )
    _publish(item_id, manifest)
    item.update(journal=str(journal), item_job_id=item_id, status="reserved")
    return manifest, journal


def _release(item: dict) -> None:
    model = general.model_info(item["model_id"])
    if model.get("pending_job") == item.get("item_job_id"):
        model["pending_job"] = None
        model_registry.write_model(general.model_path(model["model_id"]), model)


def _terminal(manifest: dict) -> dict:
    items = manifest["items"]
    counts = {
        state: sum(i["status"] == state for i in items)
        for state in ("succeeded", "refused", "unknown_outcome", "not_attempted")
    }
    unknown = counts["unknown_outcome"] > 0
    manifest.update(
        status="unknown_outcome" if unknown else "succeeded" if counts["succeeded"] else "failed",
        item_counts=counts,
        all_adopted=counts["succeeded"] == len(items),
        partial_result=0 < counts["succeeded"] < len(items),
        recovery_required=unknown,
        finished_at=bridge.now(),
        stage="batch_complete",
        message="Each item commits independently; poll this parent only. Unknown items retain protection; no native retry.",
    )
    return manifest


def run(job_id: str, manifest: dict) -> None:
    directory = bridge.job_path(job_id)
    # A runner is single-use, including restart after a crash. Its persisted
    # marker deliberately blocks native replay even before the first item.
    try:
        with bridge.toolkit_lock(wait_seconds=120, operation="adoption_files", job_id=job_id):
            batch = bridge.read_json(directory / "batch.json")
            if batch.get("dispatch_started"):
                return
            batch["dispatch_started"] = True
            bridge.write_json(directory / "batch.json", batch, durable=True)
            items = batch["items"]
            manifest.update(status="running", started_at=bridge.now(), items=items)
            stopped = False
            for item in items:
                if stopped:
                    if item["status"] == "eligible":
                        item.update(status="not_attempted", reason="previous_unknown_outcome")
                    continue
                if item["status"] != "eligible":
                    continue
                child = None
                try:
                    _check_file(item)
                    _conflict(item)
                    child, journal = _reserve(manifest, item)
                    # Persist pointer before dispatch so polling can finish a
                    # durable item commit after a parent crash.
                    _publish(job_id, manifest)
                    terminal = adoption.run_item_locked(child["job_id"], child, journal)
                    _publish(child["job_id"], terminal)
                    item.update(status="succeeded", revision=1, result=terminal["result"])
                except adoption.AdoptionRefused as error:
                    _refuse(item, error.reason, str(error))
                    if child:
                        try:
                            _release(item)
                        except Exception as cleanup_error:
                            item.update(
                                status="unknown_outcome",
                                reason="reservation_closeout_failed",
                                message=str(cleanup_error),
                            )
                            stopped = True
                        child.update(
                            status="unknown_outcome" if stopped else "failed",
                            reason=item["reason"],
                            message=item["message"],
                            finished_at=bridge.now(),
                        )
                        _publish(child["job_id"], child)
                except Exception as error:
                    # A metadata error may have followed a durable commit;
                    # stop here and let polling materialize that decision.
                    item.update(
                        status="unknown_outcome",
                        reason="item_outcome_unconfirmed",
                        message=str(error),
                    )
                    stopped = True
                    if child:
                        child.update(
                            status="unknown_outcome", message=str(error), recovery_required=True
                        )
                        _publish(child["job_id"], child)
                _publish(job_id, manifest)
            manifest["items"] = [_public_item(i) for i in items]
            _terminal(manifest)
    except Exception as error:
        for item in manifest.get("items", []):
            if item["status"] == "eligible":
                item.update(status="not_attempted", reason="parent_interrupted")
            elif item["status"] == "reserved":
                item.update(status="unknown_outcome", reason="parent_interrupted")
        manifest["items"] = [_public_item(i) for i in manifest.get("items", [])]
        _terminal(manifest)
        manifest.update(status="unknown_outcome", recovery_required=True, message=str(error))
    # Terminal is published only after releasing the channel.
    _publish(job_id, manifest)


def resume_committed(job_id: str) -> dict | None:
    manifest = bridge.read_json(bridge.job_path(job_id) / "job.json")
    if manifest.get("kind") != "adoption_file" or manifest.get("status") in ("succeeded", "failed"):
        return None
    try:
        with bridge.toolkit_lock(operation="finish_path_adoption_commits", job_id=job_id):
            # The runner may have published newer siblings between the first
            # read and lock acquisition. Never materialize from that stale view.
            manifest = bridge.read_json(bridge.job_path(job_id) / "job.json")
            if manifest.get("status") in ("succeeded", "failed"):
                return None
            changed = False
            for item in manifest["items"]:
                if item.get("status") not in ("reserved", "unknown_outcome") or not item.get(
                    "model_id"
                ):
                    continue
                record = _read(adoption._journal(item["model_id"], manifest["idempotency_key"]))
                if record and record.get("state") == "committed":
                    terminal = adoption.finish_item_commit(record)
                    _publish(item["item_job_id"], terminal)
                    item.update(status="succeeded", revision=1, result=terminal["result"])
                    changed = True
            if not changed:
                return None
            # Never dispatch the unfinished remainder when recovering metadata.
            for item in manifest["items"]:
                if item["status"] == "eligible":
                    item.update(status="not_attempted", reason="parent_interrupted")
                elif item["status"] == "reserved":
                    item.update(status="unknown_outcome", reason="parent_interrupted")
            _terminal(manifest)
    except bridge.ToolkitBusy:
        return None
    except (OSError, ValueError) as error:
        return {**manifest, "commit_pending": True, "commit_error": str(error)}
    _publish(job_id, manifest)
    return manifest


def adopt_file(
    file_path: str | list[str],
    mode: str = "inspect",
    evidence_token: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    paths = _paths(file_path)
    if mode == "inspect" and evidence_token is None and idempotency_key is None:
        return inspect(paths)
    if mode == "apply" and evidence_token and idempotency_key:
        return apply(paths, evidence_token, idempotency_key)
    raise ValueError("inspect takes paths only; apply requires evidence_token and idempotency_key")
