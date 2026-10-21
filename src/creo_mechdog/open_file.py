"""Read-only retrieval and display of an existing on-disk native model.

The selected file is retrieved into the connected Creo session and displayed.
Nothing is saved, erased, renamed or adopted: a successful open creates no
managed model (model_id stays null) and the source file is only read. File
identity is recorded at submit and at completion so in-flight changes are
reported instead of trusted.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path, PureWindowsPath

import bridge

WORKER_SECONDS = 115
KIND_BY_EXTENSION = {"prt": "part", "asm": "assembly"}


def _registry() -> Path:
    return bridge.ROOT / "open_file"


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _key(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", value):
        raise ValueError(
            "idempotency_key must contain 8-80 letters, digits, underscores or hyphens"
        )


def _read(file: Path) -> dict | None:
    if file.is_file() and file.stat().st_size > 1024 * 1024:
        raise ValueError("Open-file metadata exceeds the 1 MiB read budget")
    return bridge.read_json(file) if file.is_file() else None


def _identity(file: Path) -> dict:
    """Streaming read-only identity; unlike recovery evidence, parents may be links."""
    stat_before = file.stat()
    sha = hashlib.sha256()
    with file.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            sha.update(chunk)
    stat_after = file.stat()
    return {
        "path": str(file),
        "size_bytes": stat_after.st_size,
        "sha256": sha.hexdigest(),
        "modified_epoch": stat_after.st_mtime,
        "stable_during_hash": (stat_before.st_size, stat_before.st_mtime_ns)
        == (stat_after.st_size, stat_after.st_mtime_ns),
    }


def _exact_entry(directory: Path, name: str) -> Path:
    """Case-insensitive exact lookup; multiple distinct spellings are ambiguous."""
    wanted = name.lower()
    matches = [entry for entry in os.listdir(directory) if entry.lower() == wanted]
    if not matches:
        raise ValueError(f"File not found: {directory / name}. Check the path; no job was created")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous file entries for {name!r} in {directory}: {matches}; refusing to pick one"
        )
    return directory / matches[0]


def select_file(raw: str) -> tuple[Path, str, int | None]:
    """Resolve an explicit version or the highest numeric version on disk."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("file_path must be a non-empty Windows absolute path")
    path = Path(PureWindowsPath(raw))
    if not path.is_absolute():
        raise ValueError("file_path must be a Windows absolute path")
    name = path.name
    directory = path.parent
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Directory does not exist: {directory}; no job was created")

    versioned = re.fullmatch(r"(?i)(.+)\.(prt|asm)\.(\d+)", name)
    if versioned:
        stem, extension, digits = (
            versioned.group(1),
            versioned.group(2).lower(),
            int(versioned.group(3)),
        )
        if not stem or digits < 1:
            raise ValueError("Explicit version numbers start at 1")
        selected = _exact_entry(directory, name)
        return selected, KIND_BY_EXTENSION[extension], digits

    plain = re.fullmatch(r"(?i)(.+)\.(prt|asm)", name)
    if not plain or not plain.group(1):
        raise ValueError(
            "file_path must end with .prt or .asm, optionally with an explicit "
            "numeric version such as .prt.3"
        )
    extension = plain.group(2).lower()
    prefix = f"{plain.group(1)}.{extension}.".lower()
    versions: dict[int, list[str]] = {}
    for entry in os.listdir(directory):
        lowered = entry.lower()
        if not lowered.startswith(prefix):
            continue
        tail = lowered[len(prefix) :]
        if tail.isdigit() and int(tail) >= 1:
            versions.setdefault(int(tail), []).append(entry)
    if versions:
        newest = max(versions)
        candidates = versions[newest]
        if len(candidates) > 1:
            raise ValueError(
                f"Ambiguous highest version {newest} for {name!r} in {directory}: "
                f"{candidates}; pass the exact entry instead"
            )
        return directory / candidates[0], KIND_BY_EXTENSION[extension], None
    selected = _exact_entry(directory, name)
    return selected, KIND_BY_EXTENSION[extension], None


def _native_request(choice: dict) -> dict:
    return {
        "new": False,
        "model": {
            "model_id": None,
            "model_name": "open_file_request",
            "aliases": {},
            "output_directory": str(bridge.job_path(choice["job_id"]) / "output"),
            "part_file": None,
        },
        "operations": [],
        "readonly": True,
        "template_file": "",
        "components": {},
        "open_file": {key: value for key, value in choice.items() if key != "job_id"},
    }


def open_file(file_path: str, idempotency_key: str) -> dict:
    """Submit one read-only open; poll the returned job_id with creo_get_job."""
    _key(idempotency_key)
    selected, kind, version = select_file(file_path)
    arguments = {
        "file_path": file_path,
        "selected_file": str(selected),
        "model_kind": kind,
    }
    registry = _registry()
    registry.mkdir(exist_ok=True)
    pointer = registry / f"intent-{digest(idempotency_key)}.json"
    with bridge.toolkit_lock(operation="submit_open_file"):
        existing = _read(pointer)
        if existing:
            if existing["arguments"] != arguments:
                raise ValueError("Idempotency key already belongs to another open-file request")
            return bridge.get_job(existing["job_id"], "compact")
        before = _identity(selected)
        job_id = uuid.uuid4().hex
        directory = bridge.job_path(job_id)
        manifest = {
            "job_id": job_id,
            "kind": "open_file",
            "model_id": None,
            "status": "queued",
            "readonly": True,
            "idempotency_key": idempotency_key,
            "created_at": bridge.now(),
            "stage": "intent_persisted",
            "message": "Open-file request accepted; poll this job_id",
        }
        choice = {
            "job_id": job_id,
            "requested_path": file_path,
            "selected_file": str(selected),
            "model_kind": kind,
            "explicit_version": version,
            "identity_before": before,
        }
        try:
            (directory / "output").mkdir(parents=True)
            bridge.write_json(directory / "request.json", _native_request(choice), durable=True)
            bridge.write_json(directory / "job.json", manifest, durable=True)
            bridge.write_json(
                pointer,
                {
                    "job_id": job_id,
                    "arguments": arguments,
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
                manifest["launch_failed"] = True
                bridge.write_json(directory / "job.json", manifest, durable=True)
            raise
        return manifest


def run(job_id: str, manifest: dict) -> None:
    directory = bridge.job_path(job_id)
    worker_started = False
    try:
        with bridge.toolkit_lock(operation="open_file", job_id=job_id):
            manifest.update(status="running", stage="building_worker", started_at=bridge.now())
            bridge.write_json(directory / "job.json", manifest, durable=True)
            exe = bridge.build_native()
            manifest.update(stage="opening_native_model")
            manifest["worker_started"] = True
            worker_started = True
            bridge.write_json(directory / "job.json", manifest, durable=True)
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
            result = _read(directory / "native_result.json")
            if result:
                manifest["result"] = result
            if (
                not result
                or result.get("delivery_complete") is not True
                or result.get("disconnect_code") != 0
            ):
                manifest.update(
                    status="unknown_outcome",
                    message=(
                        "Open-file outcome is unconfirmed (missing/incomplete native "
                        "result); the model may be in the session. Inspect this job's "
                        "native.log and creo_list_session_models; do not resubmit blindly"
                    ),
                    recovery_required=True,
                )
            elif proc.returncode != 0 or not result.get("success"):
                manifest.update(
                    status="failed",
                    message=result.get("message", "Native open failed; inspect native.log"),
                )
            else:
                _finalize_identity(manifest, result)
                manifest.update(
                    status="succeeded",
                    stage="opened_and_displayed",
                    revision=None,
                    message=(
                        "Model retrieved into the session and displayed read-only; "
                        "no managed model was created and the source file was not modified"
                    ),
                )
                # This open changed the session content; record it for the
                # session inventory (FEAT-043). Written under the channel lock.
                try:
                    from creo_mechdog.session_models import record_session_change

                    report = result.get("open_file", {})
                    record_session_change(
                        "creo_open_file",
                        f"displayed {report.get('model_name') or report.get('selected_file')}",
                        {"model_type": report.get("model_type")},
                    )
                except (OSError, ValueError):
                    pass  # Informational only; never fail a successful open.
    except subprocess.TimeoutExpired:
        manifest.update(
            status="unknown_outcome",
            message=(
                "Native open timed out and was stopped; the model may be in the "
                "session. Inspect this job's native.log and creo_list_session_models; "
                "do not resubmit blindly"
            ),
            recovery_required=True,
        )
    except Exception as error:
        manifest.update(
            status="unknown_outcome" if worker_started else "failed",
            message=str(error),
        )
        if worker_started:
            manifest["recovery_required"] = True
    manifest["finished_at"] = bridge.now()
    bridge.write_json(directory / "job.json", manifest, durable=True)


def _finalize_identity(manifest: dict, result: dict) -> None:
    """Record the post-open source identity; a change is reported, never trusted."""
    choice = bridge.read_json(bridge.job_path(manifest["job_id"]) / "request.json")["open_file"]
    before = choice.get("identity_before")
    report = result.get("open_file", {})
    report["identity_before"] = before
    try:
        after = _identity(Path(choice["selected_file"]))
    except OSError:
        after = None
    report["identity_after"] = after
    report["source_file_changed_during_open"] = bool(
        before and after and before.get("sha256") != after.get("sha256")
    )
    observation = report.get("opened_session_model")
    if isinstance(observation, dict):
        # The native side observes the opened handle right after display; this
        # closeout stamps the observation time next to the job's own timestamps.
        observation.setdefault("observed_at", bridge.now())
        observation["observed_at_source"] = "python_closeout"
        report["opened_session_model"] = observation
    result["open_file"] = report
    result["model_id"] = None
    result["adopted"] = False
