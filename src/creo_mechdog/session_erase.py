"""FEAT-046: explicit, evidence-bound erasure of selected session models.

``inspect(targets)`` proves a manifest and publishes a 600-second evidence
token; ``apply(evidence_token, idempotency_key)`` executes exactly that token's
manifest under one Toolkit channel lock and returns a job_id to poll. Nothing
is saved and no disk file is deleted; only saved, unmodified, unmanaged
session objects qualify, assemblies erase before their components, and every
item is re-verified and confirmed absent before success is reported.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import bridge
import generic_bridge as general

TOKEN_SECONDS = 600
WORKER_SECONDS = 115
TARGET_TYPES = ("part", "sheetmetal", "assembly")
TARGET_LIMIT = 50


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _key(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", value):
        raise ValueError(
            "idempotency_key must contain 8-80 letters, digits, underscores or hyphens"
        )


def _registry() -> Path:
    return bridge.ROOT / "session_erase"


def _validate_targets(targets: object) -> list[dict]:
    if not isinstance(targets, list) or not 1 <= len(targets) <= TARGET_LIMIT:
        raise ValueError(f"targets must be a list of 1-{TARGET_LIMIT} entries")
    checked = []
    seen = set()
    for index, target in enumerate(targets):
        if not isinstance(target, dict) or set(target) != {"name", "model_type"}:
            raise ValueError(
                f"Target {index} requires exactly name and model_type "
                f"(one of {', '.join(TARGET_TYPES)})"
            )
        name, model_type = target["name"], target["model_type"]
        if not isinstance(name, str) or not name or len(name) > 128:
            raise ValueError(f"Target {index} has an invalid name")
        if model_type not in TARGET_TYPES:
            raise ValueError(f"Target {index} has an unsupported model_type")
        key = (name.casefold(), "part" if model_type in ("part", "sheetmetal") else "assembly")
        if key in seen:
            raise ValueError("Duplicate targets are not accepted")
        seen.add(key)
        checked.append({"name": name, "model_type": model_type})
    return checked


def _native_request(choice: dict) -> dict:
    return {
        "new": False,
        "model": {
            "model_id": None,
            "model_name": "session_erase_request",
            "aliases": {},
            "output_directory": str(bridge.job_path(choice["job_id"]) / "output"),
            "part_file": None,
        },
        "operations": [],
        "readonly": False,
        "template_file": "",
        "components": {},
        "session_erase": {key: value for key, value in choice.items() if key != "job_id"},
    }


def _probe(directory: Path, manifest: dict) -> dict:
    exe = bridge.build_native()
    with (directory / "worker.log").open("wb") as log:
        proc = subprocess.run(
            [str(exe), "generic", str(directory)],
            cwd=directory,
            env=bridge.native_environment(),
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=WORKER_SECONDS,
            creationflags=bridge.HIDDEN,
        )
    result = bridge.read_json(directory / "native_result.json")
    if (
        proc.returncode
        or result.get("delivery_complete") is not True
        or result.get("disconnect_code") != 0
        or result.get("success") is not True
    ):
        raise RuntimeError(result.get("message", "Session erase could not be confirmed"))
    return result


def erase_session_models(
    mode: str = "inspect",
    targets: list[dict] | None = None,
    evidence_token: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    if mode == "inspect":
        if evidence_token is not None or idempotency_key is not None:
            raise ValueError("Inspect takes targets only; apply takes token and key")
        return _inspect(_validate_targets(targets))
    if mode != "apply":
        raise ValueError("mode must be inspect or apply")
    if targets is not None or not evidence_token or not idempotency_key:
        raise ValueError("apply requires evidence_token and idempotency_key, not targets")
    return _apply(evidence_token, idempotency_key)


def _inspect(targets: list[dict]) -> dict:
    registry = _registry()
    registry.mkdir(exist_ok=True)
    with bridge.toolkit_lock(operation="session_erase_inspect"):
        job_id = uuid.uuid4().hex
        directory = bridge.job_path(job_id)
        (directory / "output").mkdir(parents=True)
        manifest = {
            "job_id": job_id,
            "kind": "session_erase",
            "session_erase_action": "inspect",
            "model_id": None,
            "status": "running",
            "created_at": bridge.now(),
        }
        bridge.write_json(
            directory / "request.json",
            _native_request(
                {
                    "job_id": job_id,
                    "action": "inspect",
                    "targets": targets,
                    "managed_roots": [str(general.MODELS.resolve())],
                }
            ),
            durable=True,
        )
        bridge.write_json(directory / "job.json", manifest, durable=True)
        try:
            result = _probe(directory, manifest)
            summary = result["session_erase"]
            manifest.update(
                status="succeeded", result={"session_erase": summary}, finished_at=bridge.now()
            )
        except Exception as error:
            manifest.update(status="failed", message=str(error), finished_at=bridge.now())
            bridge.write_json(directory / "job.json", manifest, durable=True)
            raise
        token = None
        expires = None
        if summary.get("available") is True:
            # The token freezes exactly the verified manifest; apply may never
            # widen it. Tampering, replacement or expiry refuses at apply time.
            token = uuid.uuid4().hex
            record = {
                "created": time.time(),
                "token": token,
                "targets": targets,
                "erase_order": summary["erase_order"],
                "result_digest": digest(summary),
                "job_id": job_id,
            }
            bridge.write_json(registry / f"evidence-{token}.json", record, durable=True)
            expires = TOKEN_SECONDS
        bridge.write_json(directory / "job.json", manifest, durable=True)
        return {
            "session_erase": summary,
            "job_id": job_id,
            "evidence_token": token,
            "expires_in_seconds": expires,
            "apply": (
                "apply executes exactly this manifest: pass evidence_token and a fresh "
                "idempotency_key, then poll the returned job_id"
                if token
                else None
            ),
        }


def _apply(evidence_token: str, idempotency_key: str) -> dict:
    _key(idempotency_key)
    if not bridge.JOB_ID.fullmatch(evidence_token or ""):
        raise ValueError("Invalid evidence_token")
    registry = _registry()
    registry.mkdir(exist_ok=True)
    pointer = registry / f"intent-{digest(idempotency_key)}.json"
    with bridge.toolkit_lock(operation="submit_session_erase", model_id=None):
        existing = None
        if pointer.is_file() and pointer.stat().st_size <= 1024 * 1024:
            try:
                existing = bridge.read_json(pointer)
            except (OSError, ValueError):
                existing = None
        if existing:
            if existing.get("evidence_token") != evidence_token:
                raise ValueError("Idempotency key already belongs to another erase request")
            return bridge.get_job(existing["job_id"], "compact")
        record_file = registry / f"evidence-{evidence_token}.json"
        if not record_file.is_file():
            raise ValueError("Evidence token is missing; inspect again")
        if record_file.stat().st_size > 1024 * 1024:
            raise ValueError("Evidence token is unreadable; inspect again")
        record = bridge.read_json(record_file)
        if time.time() - record["created"] > TOKEN_SECONDS:
            raise ValueError("Evidence token expired; inspect again")
        job_id = uuid.uuid4().hex
        directory = bridge.job_path(job_id)
        manifest = {
            "job_id": job_id,
            "kind": "session_erase",
            "session_erase_action": "apply",
            "model_id": None,
            "status": "queued",
            "readonly": False,
            "idempotency_key": idempotency_key,
            "created_at": bridge.now(),
            "stage": "intent_persisted",
            "message": "Session erase accepted; poll this job_id",
        }
        try:
            (directory / "output").mkdir(parents=True)
            bridge.write_json(
                directory / "request.json",
                _native_request(
                    {
                        "job_id": job_id,
                        "action": "apply",
                        "targets": record["targets"],
                        "erase_order": record["erase_order"],
                        "managed_roots": [str(general.MODELS.resolve())],
                    }
                ),
                durable=True,
            )
            bridge.write_json(directory / "job.json", manifest, durable=True)
            bridge.write_json(
                pointer,
                {
                    "job_id": job_id,
                    "evidence_token": evidence_token,
                    "targets": record["targets"],
                    "created_at": bridge.now(),
                },
                durable=True,
            )
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
            manifest.update(status="failed", message=str(error), finished_at=bridge.now())
            if (directory / "job.json").is_file():
                bridge.write_json(directory / "job.json", manifest, durable=True)
            raise
        return manifest


def run(job_id: str, manifest: dict) -> None:
    directory = bridge.job_path(job_id)
    worker_started = False
    try:
        with bridge.toolkit_lock(operation="session_erase", job_id=job_id):
            manifest.update(status="running", stage="building_worker", started_at=bridge.now())
            bridge.write_json(directory / "job.json", manifest, durable=True)
            bridge.build_native()  # _probe builds/reuses the executor itself.
            manifest.update(stage="erasing_session_models")
            manifest["worker_started"] = True
            worker_started = True
            bridge.write_json(directory / "job.json", manifest, durable=True)
            try:
                result = _probe(directory, manifest)
            except RuntimeError as error:
                manifest.update(status="failed", message=str(error))
            else:
                summary = result["session_erase"]
                manifest.update(
                    status="succeeded",
                    stage="session_models_erased",
                    revision=None,
                    result={"session_erase": summary},
                    finished_at=bridge.now(),
                    message=summary.get(
                        "message", "Session models erased; nothing was saved or deleted on disk"
                    ),
                )
                try:
                    from creo_mechdog.session_models import record_session_change

                    erased = [
                        f"{item['name']} ({item['model_type']})"
                        for item in summary.get("erased", [])
                    ]
                    record_session_change(
                        "creo_erase_session_models",
                        "erased " + ", ".join(erased) if erased else "erased nothing",
                        {"job_id": job_id},
                    )
                except (OSError, ValueError):
                    pass  # Informational only.
    except Exception as error:
        manifest.update(
            status="unknown_outcome" if worker_started else "failed",
            message=str(error),
        )
        if worker_started:
            manifest["recovery_required"] = True
            manifest["message"] += (
                "; the native worker may have started erasing; inspect "
                "creo_list_session_models before resubmitting"
            )
    manifest["finished_at"] = bridge.now()
    bridge.write_json(directory / "job.json", manifest, durable=True)
