"""Explicit owned-model reconciliation. Never replay an uncertain modeling plan."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path

import bridge
import generic_bridge as general
from creo_mechdog import inspection_refs
from creo_mechdog.legacy_recovery import previous_boot_evidence
from creo_mechdog.recovery import process_identity
from creo_mechdog.windows_boot import boot_info

ACTIONS = ("restore_baseline", "accept_saved", "accept_live", "abandon_new")
TOKEN_SECONDS = 600
WORKER_SECONDS = 115
HASH_SECONDS = 8
SNAPSHOT_SECONDS = 12
MAX_FILE_BYTES = 1024**3


class RecoveryRefused(ValueError):
    """A recovery evidence check failed at a known execution boundary."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _binding(snapshot: dict) -> str:
    # Windows can remove an exited process object after the last open handle
    # closes. Both observations prove the same recorded owner has stopped.
    stable = {
        **snapshot,
        "owners": [
            {
                "job_id": owner["job_id"],
                "stopped": owner["stopped"],
                "runner": owner["runner"].get("recorded"),
                "worker": owner["worker"].get("recorded"),
                "stop_evidence": owner.get("stop_evidence"),
            }
            for owner in snapshot["owners"]
        ],
    }
    return digest(stable)


def identity(file: Path, deadline: float | None = None) -> dict:
    """Bounded streaming hash; a missing/unreadable/oversized file is never trusted."""
    deadline = min(deadline or float("inf"), time.monotonic() + HASH_SECONDS)
    if file.is_symlink() or any(p.is_symlink() or p.is_junction() for p in file.parents):
        raise ValueError("Recovery evidence cannot traverse links")
    before = file.stat()
    if before.st_size > MAX_FILE_BYTES:
        raise ValueError("Recovery evidence exceeds the 1 GiB hash budget")
    sha = hashlib.sha256()
    with file.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            if time.monotonic() > deadline:
                raise ValueError("Recovery evidence hash budget exceeded; no action accepted")
            sha.update(chunk)
    after = file.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Recovery evidence changed while hashing")
    return {"path": str(file.resolve()), "size_bytes": after.st_size, "sha256": sha.hexdigest()}


def owned_file(model: dict, value: str) -> Path:
    output = general.model_path(model["model_id"]) / "output"
    file = Path(value)
    if not file.is_absolute() or file.parent.resolve() != output.resolve():
        raise ValueError("Selected source is outside this model's managed output")
    extension = "asm" if model.get("model_type") == "assembly" else "prt"
    if not re.fullmatch(re.escape(model["model_name"]) + rf"\.{extension}\.\d+", file.name, re.I):
        raise ValueError("Selected source does not match the owned native model name")
    return file


def _read(file: Path) -> dict | None:
    if file.is_file() and file.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Recovery metadata exceeds the 16 MiB read budget")
    return bridge.read_json(file) if file.is_file() else None


def _directory(model_id: str) -> Path:
    directory = general.model_path(model_id) / "reconciliation"
    if directory.is_symlink() or directory.is_junction():
        raise ValueError("Reconciliation directory cannot be a link")
    directory.mkdir(exist_ok=True)
    return directory


def _baseline_hash(model: dict) -> str | None:
    """Use recorded successful output, never bless current file bytes as a baseline."""
    if model.get("part_sha256"):
        return model["part_sha256"]
    current = model
    seen = set()
    for _ in range(16):
        job_id = current.get("last_job")
        if not job_id or job_id in seen:
            break
        seen.add(job_id)
        directory = bridge.job_path(job_id)
        job = _read(directory / "job.json") or {}
        result = job.get("result") or {}
        if job.get("status") == "succeeded" and result.get("part_file") == model.get("part_file"):
            return result.get("sha256")
        current = (_read(directory / "request.json") or {}).get("model", {})
    return None


def validate_baseline(model: dict) -> None:
    if not model.get("part_file"):
        raise ValueError(
            "model_reconciliation_required: no verified saved baseline; inspect creo_reconcile_model"
        )
    expected = _baseline_hash(model)
    if not expected or identity(owned_file(model, model["part_file"]))["sha256"] != expected:
        raise ValueError(
            "model_reconciliation_required: saved baseline identity is unverified or changed"
        )


def _stopped(recorded: dict | None) -> dict:
    if (
        not isinstance(recorded, dict)
        or type(recorded.get("pid")) is not int
        or recorded["pid"] <= 0
    ):
        return {"stopped": False, "reason": "No recorded process identity"}
    observed = process_identity(recorded["pid"])
    if observed.get("alive") is False:
        stopped = True
    elif (
        observed.get("alive") is True
        and type(recorded.get("created")) is int
        and recorded["created"] > 0
        and type(observed.get("created")) is int
        and observed["created"] > 0
    ):
        stopped = recorded["created"] != observed["created"]
    else:
        stopped = False
    return {"recorded": recorded, "observed": observed, "stopped": stopped}


def _legacy_identity_incomplete(recorded: dict | None) -> bool:
    """Missing PID/creation fields may use reboot proof; malformed values may not."""
    if recorded is None:
        return True
    if not isinstance(recorded, dict):
        return False
    pid, created = recorded.get("pid"), recorded.get("created")
    missing_pid = pid is None
    missing_created = created is None or (type(created) is int and created == 0)
    return (
        (missing_pid or type(pid) is int and pid > 0)
        and (missing_created or type(created) is int and created > 0)
        and (missing_pid or missing_created)
    )


def _owners(job_id: str, boot_reader: Callable[[], dict | None] | None = None) -> dict:
    directory = bridge.job_path(job_id)
    job = _read(directory / "job.json") or {}
    runner = _stopped(job.get("runner_identity"))
    owner = _read(directory / "native_owner.json")
    checkpoint = _read(directory / "native_checkpoint.json") or {}
    worker_identity = owner or (
        {"pid": checkpoint["native_pid"]} if checkpoint.get("native_pid") else None
    )
    if owner:
        worker = _stopped(owner)
    else:
        if job.get("worker_started") is False and runner["stopped"]:
            worker = {"stopped": True, "reason": "Runner ended before native worker started"}
        elif checkpoint.get("native_pid"):
            worker = _stopped({"pid": checkpoint["native_pid"]})
        else:
            # A runner without native ownership evidence may have died between
            # spawning a legacy worker and persisting its PID. Do not guess.
            worker = {"stopped": False, "reason": "Native owner identity is unavailable"}
    result = {
        "job_id": job_id,
        "runner": runner,
        "worker": worker,
        "stopped": runner["stopped"] and worker["stopped"],
    }
    # A complete but live/unreadable recorded identity never gets a time-based override.
    missing_runner = not runner["stopped"] and _legacy_identity_incomplete(
        job.get("runner_identity")
    )
    missing_worker = not worker["stopped"] and _legacy_identity_incomplete(worker_identity)
    eligible = (runner["stopped"] or missing_runner) and (worker["stopped"] or missing_worker)
    if not result["stopped"] and eligible:
        proof = previous_boot_evidence(directory, job, (boot_reader or boot_info)())
        if proof["stopped"]:
            result["stop_evidence"] = proof
            for missing, value in ((missing_runner, runner), (missing_worker, worker)):
                if missing:
                    value.update(stopped=True, reason="Historical owner predates verified OS boot")
            result["stopped"] = runner["stopped"] and worker["stopped"]
        else:
            result["reason"] = proof["reason"]
            result["guidance"] = (
                "Preserve job/model files. Missing legacy identities require all job records "
                "to predate an independently verified Windows boot. After an operator-controlled "
                "restart, inspect again; no action can bypass uncertain ownership."
            )
    return result


def _deployment(deadline: float) -> str:
    names = (
        "bridge.py",
        "generic_bridge.py",
        "server.py",
        "version.py",
        "src/creo_mechdog/reconciliation.py",
        "src/creo_mechdog/legacy_recovery.py",
        "src/creo_mechdog/windows_boot.py",
        "src/creo_mechdog/adoption.py",
        "native/generic.cpp",
        "native/result_delivery.h",
        "native/recovery_deadline.h",
        "src/creo_mechdog/blend_callback.py",
        "native/worker.cpp",
        "native/blend_create.cpp",
        "native/blend_sync.cpp",
        "native/blend_loader.cpp",
        "native/callback_runtime.h",
        "native/callback_api.h",
        "native/callback_identity.h",
    )
    values = [identity(bridge.ROOT / name, deadline) for name in names]
    setup = bridge.ROOT / "build/blend_callback_setup.json"
    values.append(identity(setup, deadline) if setup.is_file() else {"callback": "not_prepared"})
    worker = bridge.ROOT / "build/creo_worker.exe"
    values.append(identity(worker, deadline) if worker.is_file() else {"worker": "not_built"})
    return digest(values)


def _cached_boot_reader() -> Callable[[], dict | None]:
    observations = []

    def read() -> dict | None:
        if not observations:
            observations.append(boot_info())
        return observations[0]

    return read


def _snapshot(model_id: str) -> dict:
    deadline = time.monotonic() + SNAPSHOT_SECONDS
    model = general.model_info(model_id)
    if (
        Path(model["output_directory"]).resolve()
        != (general.model_path(model_id) / "output").resolve()
    ):
        raise ValueError("Model output registration is not owned")
    job_ids = list(
        dict.fromkeys(
            j
            for j in (
                model.get("recovery_pending"),
                model.get("pending_job"),
                model.get("last_job"),
            )
            if j
        )
    )
    files = []
    owners = []
    candidate = None
    verified_boot = _cached_boot_reader()

    for job_id in job_ids:
        directory = bridge.job_path(job_id)
        job = _read(directory / "job.json") or {}
        request = _read(directory / "request.json") or {}
        if job.get("model_id") != model_id or request.get("model", {}).get("model_id") != model_id:
            raise ValueError("Job evidence is not bound to this model")
        owners.append(_owners(job_id, verified_boot))
        for name in (
            "job.json",
            "request.json",
            "native_checkpoint.json",
            "native_result.json",
            "native_owner.json",
        ):
            file = directory / name
            if file.is_file():
                files.append(identity(file, deadline))
        for name in ("native_result.json", "native_checkpoint.json"):
            result = _read(directory / name) or {}
            if (
                candidate is None
                and result.get("success")
                and result.get("saved_file_reloaded_and_verified")
                and result.get("part_file")
                and (result.get("inspection") or result.get("inspection_ref"))
            ):
                try:
                    file = owned_file(model, result["part_file"])
                    candidate = {
                        "job_id": job_id,
                        "evidence": name,
                        "identity": identity(file, deadline),
                        # New results carry a controlled reference (BUG-076);
                        # legacy results inline the payload. Keep whichever
                        # form exists; consumers resolve both.
                        "inspection": result.get("inspection"),
                        "inspection_ref": result.get("inspection_ref"),
                        "aliases": result.get("aliases", {}),
                    }
                except (OSError, ValueError) as error:
                    candidate = {"error": str(error)}
    baseline = None
    if model.get("part_file"):
        try:
            baseline = {
                "identity": identity(owned_file(model, model["part_file"]), deadline),
                "expected_sha256": _baseline_hash(model),
            }
            baseline["verified"] = baseline["identity"]["sha256"] == baseline["expected_sha256"]
        except (OSError, ValueError) as error:
            baseline = {"verified": False, "error": str(error)}
    if time.monotonic() > deadline:
        raise ValueError("Recovery snapshot exceeded its 12 second budget")
    return {
        "model": model,
        "owners": owners,
        "files": files,
        "baseline": baseline,
        "candidate": candidate,
        "deployment": _deployment(deadline),
        "runtime_selection": digest(
            {key: bridge.config().get(key) for key in ("creo_root", "creo_session_id")}
        ),
    }


def _actions(snapshot: dict, live: dict | None) -> dict:
    model = snapshot["model"]
    stopped = bool(snapshot["owners"]) and all(o["stopped"] for o in snapshot["owners"])
    baseline = snapshot["baseline"] or {}
    candidate = snapshot["candidate"] or {}
    health = inspection_refs.summary_of(live).get("healthy") is True
    supported = model.get("model_type", "part") in ("part", "sheetmetal")
    conditions = {
        "restore_baseline": baseline.get("verified")
        and bool(model.get("inspection") or model.get("inspection_ref")),
        "accept_saved": bool(candidate.get("identity"))
        and candidate.get("identity", {}).get("path") != model.get("part_file"),
        "accept_live": live
        and live.get("loaded")
        and live.get("owned")
        and health
        and live.get("millimeter_units")
        and live.get("dependency_free"),
        "abandon_new": not model.get("part_file") and model.get("revision") == 0,
    }
    if model.get("status") == "adopt_pending":
        # Adoption requires explicit confirmation, not recovery acceptance of
        # its saved candidate (including an uncertain partially prepared copy).
        for action in ("restore_baseline", "accept_saved", "accept_live"):
            conditions[action] = False
    return {
        action: {
            "available": bool(stopped and supported and ok and model.get("status") != "abandoned"),
            "reason": (
                "Previous runner/worker is active or cannot be proven stopped"
                if not stopped
                else "Assembly/drawing reconciliation is not supported; preserve component ownership"
                if not supported
                else "Model is already abandoned"
                if model.get("status") == "abandoned"
                else "Required baseline/candidate/owned healthy live evidence is unavailable"
                if not ok
                else "Explicit apply with matching evidence and idempotency key required"
            ),
        }
        for action, ok in conditions.items()
    }


def _native_request(model: dict, choice: dict) -> dict:
    return {
        "new": False,
        "model": model,
        "operations": [],
        "readonly": True,
        "template_file": "",
        "components": {},
        "reconciliation": choice,
    }


def _native(directory: Path, manifest: dict) -> dict:
    manifest["worker_started"] = False
    exe = bridge.build_native()
    manifest.update(stage="reconciling_native_model", status="running")
    bridge.write_json(directory / "job.json", manifest, durable=True)
    with (directory / "worker.log").open("wb") as log:
        manifest["worker_started"] = True
        bridge.write_json(directory / "job.json", manifest, durable=True)
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
        raise RuntimeError(
            "Recovery outcome is unconfirmed; reservation retained; inspect native checkpoint"
        )
    if proc.returncode != 0 or not result.get("success"):
        raise RuntimeError(result.get("message", "Native recovery failed; reservation retained"))
    return result


def _live(model: dict) -> dict:
    with bridge.toolkit_lock(operation="reconciliation_preflight", model_id=model["model_id"]):
        job_id = uuid.uuid4().hex
        directory = bridge.job_path(job_id)
        (directory / "output").mkdir(parents=True)
        manifest = {
            "job_id": job_id,
            "kind": "reconciliation_preflight",
            "model_id": model["model_id"],
            "status": "running",
            "created_at": bridge.now(),
        }
        bridge.write_json(directory / "request.json", _native_request(model, {"action": "inspect"}))
        try:
            result = _native(directory, manifest)
            manifest.update(status="succeeded", result=result)
            return result["live"]
        except Exception as error:
            manifest.update(status="failed", message=str(error))
            return {"confirmed": False, "reason": str(error)}
        finally:
            manifest["finished_at"] = bridge.now()
            bridge.write_json(directory / "job.json", manifest)


def inspect(model_id: str, live: bool = False) -> dict:
    snapshot = _snapshot(model_id)
    realtime = _live(snapshot["model"]) if live else None
    # A model/worker may have changed while a live query held the channel.
    if _binding(snapshot) != _binding(_snapshot(model_id)):
        raise ValueError("Evidence changed during preflight; inspect again")
    token = uuid.uuid4().hex
    record = {"snapshot": snapshot, "live": realtime, "created": time.time(), "token": token}
    directory = _directory(model_id)
    bridge.write_json(directory / f"evidence-{token}.json", record)
    model = snapshot["model"]
    candidate = snapshot["candidate"]
    if candidate and (candidate.get("inspection") or candidate.get("inspection_ref")):
        candidate = {
            **{
                key: value
                for key, value in candidate.items()
                if key not in ("inspection", "inspection_ref", "aliases")
            },
            "inspection": inspection_refs.summary_of(candidate),
        }
    visible_live = realtime
    if realtime and (realtime.get("inspection") or realtime.get("inspection_ref")):
        # The visible copy is a summary; the evidence record keeps the full
        # payload (or its controlled reference) for a later apply.
        visible_live = {
            **realtime,
            "inspection_summary": inspection_refs.summary_of(realtime),
        }
        visible_live.pop("inspection", None)
    return {
        "model_id": model_id,
        "status": model["status"],
        "revision": model["revision"],
        "pending_job": model.get("pending_job"),
        "recovery_pending": model.get("recovery_pending"),
        "original_job_id": model.get("pending_job") or model.get("last_job"),
        "baseline": snapshot["baseline"],
        "candidate": candidate,
        "owners": snapshot["owners"],
        "live": visible_live,
        "actions": _actions(snapshot, realtime),
        "evidence_token": token,
        "evidence_at": bridge.now(),
        "expires_in_seconds": TOKEN_SECONDS,
        "resolution": model.get("reconciliation"),
        "automatic_replay_allowed": False,
        "budgets": {
            "snapshot_seconds": SNAPSHOT_SECONDS,
            "file_hash_seconds": HASH_SECONDS,
            "native_phase_seconds": 90,
            "disconnect_seconds": 20,
            "outer_seconds": WORKER_SECONDS,
        },
    }


def _journal(model_id: str, key: str) -> Path:
    return _directory(model_id) / f"intent-{digest(key)}.json"


def _finish(record: dict) -> dict:
    """Materialize a durable commit; never invoke Toolkit or overwrite later edits."""
    model = general.model_info(record["model_id"])
    after = record["model_after"]
    if model.get("recovery_pending") == record["job_id"]:
        if (
            identity(bridge.job_path(record["job_id"]) / "native_result.json")
            != record["result_identity"]
        ):
            raise ValueError("Committed native evidence changed; keep recovery protection")
        source = after["reconciliation"].get("source_identity")
        if source and identity(Path(source["path"])) != source:
            raise ValueError("Committed saved model changed; keep recovery protection")
        bridge.write_json(
            general.model_path(record["model_id"]) / "model.json", after, durable=True
        )
    elif (model.get("reconciliation") or {}).get("recovery_id") != record["job_id"]:
        raise ValueError("Committed recovery conflicts with current registry; preserve audit")
    return record["job_after"]


def resume_committed(job_id: str) -> dict | None:
    """Polling may finish a committed metadata transaction, never native execution."""
    manifest = bridge.read_json(bridge.job_path(job_id) / "job.json")
    if manifest.get("kind") != "reconciliation" or manifest.get("status") == "succeeded":
        return None
    file = _journal(manifest["model_id"], manifest["idempotency_key"])
    record = _read(file)
    if not record or record.get("state") != "committed":
        return None
    try:
        with bridge.toolkit_lock(
            operation="finish_reconciliation_commit", job_id=job_id, model_id=manifest["model_id"]
        ):
            terminal = _finish(record)
    except bridge.ToolkitBusy:
        return {
            **manifest,
            "commit_pending": True,
            "message": "Durable recovery commit awaits metadata materialization; poll this job",
        }
    except (OSError, ValueError) as error:
        return {
            **manifest,
            "status": "unknown_outcome",
            "commit_pending": True,
            "recovery_required": True,
            "message": str(error),
        }
    bridge.write_json(bridge.job_path(job_id) / "job.json", terminal, durable=True)
    return terminal


def _validate_evidence(
    model_id: str, token: str, revision: int, pending: str | None, action: str
) -> dict:
    if not bridge.JOB_ID.fullmatch(token):
        raise ValueError("Invalid evidence_token")
    record = _read(_directory(model_id) / f"evidence-{token}.json")
    if not record or time.time() - record["created"] > TOKEN_SECONDS:
        raise ValueError("Evidence token is missing or expired; inspect again")
    current = general.model_info(model_id)
    if current.get("recovery_pending") and current.get("recovery_pending") != record["snapshot"][
        "model"
    ].get("recovery_pending"):
        raise bridge.ToolkitBusy(
            holder={
                "job_id": current["recovery_pending"],
                "model_id": model_id,
                "operation": "reconcile_model",
            }
        )
    snapshot = _snapshot(model_id)
    model = snapshot["model"]
    if model["revision"] != revision:
        raise ValueError(
            f"Stale expected_revision: model revision is {model['revision']}, "
            f"expected {revision}; inspect again"
        )
    if model.get("pending_job") != pending:
        raise ValueError(
            "Stale expected_pending_job_id: model pending_job is "
            f"{model.get('pending_job')!r}, expected {pending!r}; inspect again"
        )
    if _binding(snapshot) != _binding(record["snapshot"]):
        raise ValueError("Stale evidence: registry, files, deployment or process identity changed")
    action_state = _actions(snapshot, record["live"])[action]
    if not action_state["available"]:
        raise ValueError(action_state["reason"])
    return record


def apply(
    model_id: str,
    action: str,
    expected_revision: int,
    expected_pending_job_id: str | None,
    evidence_token: str,
    idempotency_key: str,
) -> dict:
    if (
        action not in ACTIONS
        or isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
    ):
        raise ValueError("Valid action and nonnegative expected_revision are required")
    if expected_pending_job_id is not None and (
        not isinstance(expected_pending_job_id, str)
        or not bridge.JOB_ID.fullmatch(expected_pending_job_id)
    ):
        # An empty or malformed value is a request defect, never model staleness.
        raise ValueError(
            "expected_pending_job_id must be the pending job id returned by inspect, "
            f"or null when inspect returned pending_job=null; received {expected_pending_job_id!r}"
        )
    if not isinstance(idempotency_key, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{8,80}", idempotency_key
    ):
        raise ValueError(
            "idempotency_key must contain 8–80 letters, digits, underscores or hyphens"
        )
    arguments = {
        "model_id": model_id,
        "action": action,
        "expected_revision": expected_revision,
        "expected_pending_job_id": expected_pending_job_id,
        "evidence_token": evidence_token,
    }
    file = _journal(model_id, idempotency_key)
    # A duplicate query does not contend for Toolkit or repeat native work.
    existing = _read(file)
    if existing:
        if existing["arguments"] != arguments:
            raise ValueError("Idempotency key already belongs to another recovery request")
        resume_committed(existing["job_id"])
        return bridge.get_job(existing["job_id"], "compact")
    launch_error = None
    try:
        with bridge.toolkit_lock(operation="submit_reconciliation", model_id=model_id):
            # Check again under the one cross-process admission lock.
            if file.exists():
                raise bridge.ToolkitBusy(
                    "Recovery request was concurrently accepted; poll its recovery job"
                )
            record = _validate_evidence(
                model_id, evidence_token, expected_revision, expected_pending_job_id, action
            )
            model = record["snapshot"]["model"]
            job_id = uuid.uuid4().hex
            directory = bridge.job_path(job_id)
            (directory / "output").mkdir(parents=True)
            choice = {"action": action}
            session = (record.get("live") or {}).get("session_fingerprint")
            if not session:
                session = next(
                    (
                        owner["worker"].get("recorded", {}).get("session_fingerprint")
                        for owner in record["snapshot"]["owners"]
                        if owner["worker"].get("recorded", {}).get("session_fingerprint")
                    ),
                    None,
                )
            if session:
                choice["session_fingerprint"] = session
            if action == "restore_baseline":
                choice.update(source_file=model["part_file"])
                choice.update(inspection_refs.request_field(model, "source_inspection"))
            elif action == "accept_saved":
                candidate = record["snapshot"]["candidate"]
                choice.update(source_file=candidate["identity"]["path"])
                choice.update(inspection_refs.request_field(candidate, "source_inspection"))
                model = {**model, "aliases": candidate["aliases"]}
            elif action == "accept_live":
                choice.update(inspection_refs.request_field(record["live"], "live_inspection"))
            manifest = {
                "job_id": job_id,
                "recovery_id": job_id,
                "kind": "reconciliation",
                "model_id": model_id,
                "status": "queued",
                "action": action,
                "idempotency_key": idempotency_key,
                "created_at": bridge.now(),
                "stage": "intent_persisted",
                "revision": model["revision"],
                "message": "Recovery accepted; poll this job_id; original plan will not be replayed",
            }
            request = _native_request(model, choice)
            intent = {
                "state": "intent",
                "model_id": model_id,
                "job_id": job_id,
                "arguments": arguments,
                "evidence": record,
                "created_at": bridge.now(),
            }
            bridge.write_json(directory / "request.json", request, durable=True)
            bridge.write_json(directory / "job.json", manifest, durable=True)
            bridge.write_json(file, intent, durable=True)
            reserved = general.model_info(model_id)
            reserved["recovery_pending"] = job_id  # Original pending_job remains unchanged.
            bridge.write_json(general.model_path(model_id) / "model.json", reserved, durable=True)
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
                _record_failure(
                    job_id,
                    manifest,
                    file,
                    RecoveryRefused("runner_start_failed", str(error)),
                    locked=True,
                )
                launch_error = error
            if launch_error is None:
                return manifest
    except Exception as error:
        if launch_error is None:
            raise
        manifest["channel_finalization_error"] = str(error)
    bridge.write_json(directory / "job.json", manifest, durable=True)
    raise launch_error


def run(job_id: str, manifest: dict) -> None:
    directory = bridge.job_path(job_id)
    file = _journal(manifest["model_id"], manifest["idempotency_key"])
    intent = bridge.read_json(file)
    failure_recorded = False
    try:
        with bridge.toolkit_lock(
            operation="reconcile_model", job_id=job_id, model_id=manifest["model_id"]
        ):
            try:
                manifest = _run_locked(job_id, manifest, intent, file)
            except Exception as error:
                if not _record_failure(job_id, manifest, file, error, locked=True):
                    return
                failure_recorded = True
    except Exception as error:
        if failure_recorded:
            manifest["channel_finalization_error"] = str(error)
        elif not _record_failure(job_id, manifest, file, error, locked=False):
            return
    bridge.write_json(directory / "job.json", manifest, durable=True)


def _run_locked(job_id: str, manifest: dict, intent: dict, file: Path) -> dict:
    if intent["state"] == "committed":
        return _finish(intent)
    directory = bridge.job_path(job_id)
    # Revalidate every byte after admission, ignoring only our reservation.
    old = intent["evidence"]["snapshot"]
    bridge.build_native()
    current_model = general.model_info(manifest["model_id"])
    if current_model.get("recovery_pending") != job_id:
        raise RecoveryRefused(
            "reservation_changed", "Recovery reservation no longer belongs to this intent"
        )
    # Reconstruct using original job set, not this active runner.
    _check_execution(intent, current_model)
    result = _native(directory, manifest)
    _check_execution(intent, current_model)
    request = bridge.read_json(directory / "request.json")
    after = {**current_model}
    action = manifest["action"]
    source = None
    if action != "abandon_new":
        if not result.get("saved_file_reloaded_and_verified"):
            raise ValueError("Recovery did not verify a saved/reloaded native model")
        source = identity(owned_file(after, result["part_file"]))
        result["sha256"] = source["sha256"]
        if action == "restore_baseline" and source != old["baseline"]["identity"]:
            raise ValueError("Baseline file changed during recovery")
        after.update(
            status="ready",
            part_file=result["part_file"],
            part_sha256=source["sha256"],
            aliases=result["aliases"],
            updated_at=bridge.now(),
        )
        # Registry keeps the summary plus the controlled reference (BUG-076).
        after.update(
            {
                key: result[key]
                for key in ("inspection_ref", "inspection_summary", "inspection")
                if key in result
            }
        )
        if action != "restore_baseline":
            after["revision"] += 1
    else:
        after.update(status="abandoned", abandoned_at=bridge.now())
    after.update(
        pending_job=None,
        recovery_pending=None,
        reconciliation={
            "recovery_id": job_id,
            "action": action,
            "original_job_id": current_model.get("pending_job") or current_model.get("last_job"),
            "original_plan_completion_confirmed": False,
            "source_identity": source,
            "resolved_at": bridge.now(),
        },
    )
    manifest.update(
        status="succeeded",
        stage="reconciliation_committed",
        result=result,
        revision=after["revision"],
        finished_at=bridge.now(),
        message="Explicit recovery committed; original job history preserved",
    )
    # Recovery displayed or erased a model; keep the session record accurate
    # (FEAT-043). Informational only, never a condition of the commit.
    try:
        from creo_mechdog.session_models import record_session_change

        if action == "abandon_new":
            record_session_change(
                "creo_reconcile_model",
                f"abandon_new erased unproven copy {manifest.get('model_id')}",
                {"action": action, "model_id": manifest.get("model_id")},
            )
        else:
            record_session_change(
                "creo_reconcile_model",
                f"{action} displayed {manifest.get('model_id')}",
                {"action": action, "model_id": manifest.get("model_id")},
            )
    except (OSError, ValueError):
        pass
    intent.update(
        state="verified",
        model_after=after,
        job_after=manifest,
        result_identity=identity(directory / "native_result.json"),
        request=request,
    )
    bridge.write_json(file, intent, durable=True)
    intent["state"] = "committed"  # Durable decision precedes materialization.
    bridge.write_json(file, intent, durable=True)
    _finish(intent)
    return manifest


def _record_failure(
    job_id: str, manifest: dict, file: Path, error: Exception, *, locked: bool
) -> bool:
    # A committed decision is recoverable by polling; do not replace it with
    # a contradictory failure or release protection before materialization.
    persisted = _read(file) or {}
    if persisted.get("state") == "committed":
        return False
    started = bool(manifest.get("worker_started"))
    refused = isinstance(error, RecoveryRefused) and not started
    manifest.update(
        status="unknown_outcome" if started else "failed",
        stage="reconciliation_refused" if refused else "reconciliation_unconfirmed",
        reason=error.reason
        if isinstance(error, RecoveryRefused)
        else "native_outcome_unconfirmed"
        if started
        else "recovery_execution_failed",
        failure_phase="native_worker_started"
        if started
        else "before_native"
        if locked
        else "channel_admission",
        message=str(error),
        recovery_required=True,
        recovery_pending_released=False,
        finished_at=bridge.now(),
    )
    if started:
        manifest["message"] += (
            "; native worker dispatch began and may have started; "
            "recovery action outcome is not confirmed; protection retained"
        )
    elif locked:
        try:
            model = general.model_info(manifest["model_id"])
            if model.get("recovery_pending") == job_id:
                model["recovery_pending"] = None
                bridge.write_json(
                    general.model_path(manifest["model_id"]) / "model.json", model, durable=True
                )
                manifest["recovery_pending_released"] = True
        except (OSError, ValueError) as cleanup_error:
            # The failed attempt never authorizes clearing another reservation,
            # and a failed cleanup must remain visible for operator inspection.
            manifest["recovery_pending_cleanup_error"] = str(cleanup_error)
    if isinstance(error, bridge.ToolkitBusy):
        manifest["busy"] = error.payload
    return True


def _check_execution(intent: dict, current: dict) -> None:
    """Re-read original evidence under the channel lock before any native work."""
    original = intent["evidence"]["snapshot"]
    normalized = {**current}
    normalized.pop("recovery_pending", None)
    expected = {**original["model"]}
    expected.pop("recovery_pending", None)
    if normalized != expected:
        raise RecoveryRefused("model_changed", "Model changed after recovery admission")
    if _deployment(time.monotonic() + SNAPSHOT_SECONDS) != original["deployment"]:
        raise RecoveryRefused(
            "deployment_changed", "Deployment changed after recovery admission; inspect again"
        )
    if (
        digest({key: bridge.config().get(key) for key in ("creo_root", "creo_session_id")})
        != original["runtime_selection"]
    ):
        raise RecoveryRefused(
            "session_selection_changed", "Creo session selection changed after recovery admission"
        )
    for file in original["files"]:
        if identity(Path(file["path"])) != file:
            raise RecoveryRefused(
                "job_evidence_changed", "Original job evidence changed after admission"
            )
    verified_boot = _cached_boot_reader()
    for owner in original["owners"]:
        observed = _owners(owner["job_id"], verified_boot)
        if not observed["stopped"]:
            raise RecoveryRefused(
                "original_worker_unconfirmed",
                "Original worker is active or cannot be proven stopped",
            )
        if observed.get("stop_evidence") != owner.get("stop_evidence"):
            raise RecoveryRefused(
                "job_evidence_changed", "Original owner reboot evidence changed after admission"
            )
    for source in (original.get("baseline"), original.get("candidate")):
        if (
            source
            and source.get("identity")
            and identity(Path(source["identity"]["path"])) != source["identity"]
        ):
            raise RecoveryRefused(
                "source_changed", "Selected source changed after recovery admission"
            )


def reconcile(
    model_id: str,
    mode: str = "inspect",
    live: bool = False,
    action: str | None = None,
    expected_revision: int | None = None,
    expected_pending_job_id: str | None = None,
    evidence_token: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    if mode == "inspect":
        if action is not None:
            raise ValueError("Selecting an action requires mode=apply")
        return inspect(model_id, live)
    if (
        mode != "apply"
        or action is None
        or expected_revision is None
        or evidence_token is None
        or idempotency_key is None
    ):
        raise ValueError(
            "apply requires action, expected_revision, evidence_token and idempotency_key; "
            "expected_pending_job_id must equal inspect's pending_job "
            "(null or omitted when inspect returned no pending job)"
        )
    return apply(
        model_id,
        action,
        expected_revision,
        expected_pending_job_id,
        evidence_token,
        idempotency_key,
    )
