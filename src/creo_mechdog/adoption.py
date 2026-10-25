"""Explicit adoption of the user's current Creo model as a managed copy.

The source model and its file are never modified, erased or renamed: adoption
copies the current in-memory state into a new managed output directory and
verifies the copy exactly like any other save. Identity comes from the session
model origin, the on-disk file hash and a live inspection snapshot; display
names are never trusted as identity.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import bridge
import generic_bridge as general
from creo_mechdog import inspection_refs, model_registry
from creo_mechdog.model_queries import inspection_summary
from creo_mechdog.reconciliation import identity, owned_file

SUPPORTED_TYPES = ("part", "sheetmetal")
TOKEN_SECONDS = 600
WORKER_SECONDS = 115


class AdoptionRefused(ValueError):
    """An adoption evidence check failed at a known execution boundary."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


BUDGET_BYTES = 16 * 1024 * 1024

# The four metadata kinds this module reads under one budget (BUG-076): the
# native worker result, the managed-model registry, published evidence tokens
# and the durable commit journal. The kind identifies which read path hit the
# budget; it is diagnostic data, never a remediation by itself.
METADATA_KINDS = ("native_result", "model_registry", "evidence_token", "commit_journal")


class AdoptionMetadataBudgetExceeded(ValueError):
    """A metadata read exceeded the adoption budget; the error text is JSON."""

    def __init__(
        self,
        *,
        metadata_kind: str,
        file: Path,
        failed_stage: str,
        job_id: str | None = None,
        model_id: str | None = None,
    ):
        actual = file.stat().st_size if file.is_file() else None
        try:
            shown = str(file.resolve().relative_to(bridge.ROOT))
        except (OSError, ValueError):
            shown = str(file)
        self.payload = {
            "reason_code": "ADOPTION_METADATA_BUDGET_EXCEEDED",
            "metadata_kind": metadata_kind,
            "path": shown,
            "actual_bytes": actual,
            "budget_bytes": BUDGET_BYTES,
            "failed_stage": failed_stage,
            "job_id": job_id,
            "model_id": model_id,
            "recovery": (
                "Keep the oversized file unchanged for diagnosis; report "
                "metadata_kind, actual_bytes, path, job_id and the deployment "
                "identity (server version, Creo release) so the read path can be "
                "refined. Do not delete the file, rerun native execution, or "
                "raise the budget to hide the error"
            ),
        }
        super().__init__(json.dumps(self.payload, ensure_ascii=False))


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _read(
    file: Path,
    *,
    metadata_kind: str,
    failed_stage: str,
    job_id: str | None = None,
    model_id: str | None = None,
) -> dict | None:
    if file.is_file() and file.stat().st_size > BUDGET_BYTES:
        raise AdoptionMetadataBudgetExceeded(
            metadata_kind=metadata_kind,
            file=file,
            failed_stage=failed_stage,
            job_id=job_id,
            model_id=model_id,
        )
    return bridge.read_json(file) if file.is_file() else None


def _directory(model_id: str) -> Path:
    directory = general.model_path(model_id) / "adoption"
    if directory.is_symlink() or directory.is_junction():
        raise ValueError("Adoption directory cannot be a link")
    directory.mkdir(exist_ok=True)
    return directory


def _journal(model_id: str, key: str) -> Path:
    return _directory(model_id) / f"intent-{digest(key)}.json"


def _native_request(model: dict, choice: dict) -> dict:
    return {
        "new": False,
        "model": model,
        "operations": [],
        "readonly": True,
        "template_file": "",
        "components": {},
        "adoption": choice,
    }


def _split_result(result: dict, directory: Path) -> dict:
    """Keep full inspection payloads out of control metadata (BUG-076).

    The native side already writes controlled references; this closeout also
    splits a legacy inline payload (older executor binary) into a sidecar so
    every consumer downstream — evidence tokens, requests, registries and the
    job manifest — only ever carries a summary plus a reference.
    """
    live = result.get("live")
    if isinstance(live, dict):
        inspection_refs.split(live, directory, "live")
    if isinstance(result.get("inspection"), dict) and result["inspection"]:
        inspection_refs.split(result, directory, "verified")
    return result


def _native(directory: Path, manifest: dict) -> dict:
    manifest["worker_started"] = False
    exe = bridge.build_native()
    manifest.update(stage="adopting_native_model", status="running")
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
    result = _read(
        directory / "native_result.json",
        metadata_kind="native_result",
        failed_stage="adopting_native_model",
        job_id=manifest.get("job_id"),
        model_id=manifest.get("model_id"),
    )
    if result:
        _split_result(result, directory)
        manifest["result"] = result
    if (
        not result
        or result.get("delivery_complete") is not True
        or result.get("disconnect_code") != 0
    ):
        raise RuntimeError(
            "Adoption outcome is unconfirmed; reservation retained; inspect native checkpoint"
        )
    if proc.returncode != 0 or not result.get("success"):
        # Path adoption distinguishes a delivered pre-copy refusal from an
        # uncertain copy. Delivery/disconnect were independently confirmed above.
        if result.get("path_source_checked") and result.get("path_copy_started") is False:
            message = result.get("message", "Path source refused")
            raise AdoptionRefused(message.partition(":")[0], message)
        raise RuntimeError(result.get("message", "Native adoption failed; reservation retained"))
    return result


def _origin_conflict(origin: Path, exclude: str | None = None) -> dict | None:
    """One managed identity per source file; a second adoption is a clear refusal.

    The scan reads control records only (BUG-077): a migrated registry keeps
    ownership fields small, and an entry that cannot be read — oversized or
    corrupt — is a structured refusal pointing at migration, never a silent
    skip that would hide a real historical registration.
    """
    try:
        resolved = origin.resolve()
    except OSError:
        return None
    if not general.MODELS.is_dir():
        return None
    for directory in sorted(general.MODELS.iterdir()):
        if exclude and directory.name == exclude:
            continue
        file = directory / "model.json"
        if not file.is_file():
            continue
        if file.stat().st_size > BUDGET_BYTES:
            raise AdoptionMetadataBudgetExceeded(
                metadata_kind="model_registry",
                file=file,
                failed_stage="origin_conflict_scan",
            )
        try:
            model = bridge.read_json(file)
        except (OSError, ValueError) as error:
            raise AdoptionRefused(
                "registry_entry_unreadable",
                f"A model registry entry could not be read during the conflict scan: "
                f"{error}; run creo_registry_health and creo_migrate_registry before "
                "adopting",
            ) from error
        if not isinstance(model, dict) or not model.get("model_id"):
            continue
        output = model.get("output_directory")
        if output:
            try:
                output_path = Path(output).resolve()
            except OSError:
                output_path = None
            if output_path and (resolved.parent == output_path or output_path in resolved.parents):
                return {
                    "model_id": model["model_id"],
                    "status": model.get("status"),
                    "reason": "managed_output",
                    "message": (
                        "The current model already belongs to this service; "
                        f"use model_id {model['model_id']} instead of adopting it again"
                    ),
                }
        adopted = model.get("adopted_from") or {}
        if adopted.get("origin"):
            try:
                same = Path(adopted["origin"]).resolve() == resolved
            except OSError:
                same = False
            # A dangling inspect that was never applied does not block a fresh
            # adoption; resolve it later with creo_reconcile_model abandon_new.
            blocking = model.get("status") == "ready" or model.get("pending_job")
            if same and blocking:
                return {
                    "model_id": model["model_id"],
                    "status": model.get("status"),
                    "reason": "already_adopted",
                    "message": (
                        "This source file was already adopted; "
                        f"continue with model_id {model['model_id']}"
                    ),
                }
    return None


def _refusal_reason(live: dict) -> tuple[str, str] | None:
    """Stable machine-readable code plus human text; None when eligible."""
    if live.get("model_type") not in SUPPORTED_TYPES:
        return (
            "unsupported_model_type",
            "Only independent part or sheetmetal models can be adopted",
        )
    if not live.get("millimeter_units"):
        return ("non_millimeter_units", "Adoption requires millimeter model units")
    if not live.get("dependency_free"):
        return (
            "external_dependencies",
            "External dependencies require separate ownership verification",
        )
    if not live.get("healthy"):
        return ("unhealthy_features", "The model has failed, suppressed or incomplete features")
    return None


# Maximum unhealthy-feature entries propagated into control metadata. The
# native scan already bounds its own list; this cap only defends against a
# substituted or future executor that returns more than the documented bound.
_HEALTH_ITEM_LIMIT = 50


def _unhealthy_features(live: dict) -> dict | None:
    """Bounded per-feature diagnosis supplied by the native health scan.

    Returns the verified payload, or None when the executor did not provide a
    usable one (older binary, malformed data); the caller then falls back to
    the combined unknown-marker wording instead of guessing.
    """
    details = live.get("health_details")
    if not isinstance(details, dict):
        return None
    total = details.get("unhealthy_total")
    items = details.get("items")
    if type(total) is not int or total < 0 or not isinstance(items, list):
        return None
    kept = []
    for item in items[:_HEALTH_ITEM_LIMIT]:
        if not isinstance(item, dict) or type(item.get("id")) is not int:
            return None
        kept.append(
            {
                "id": item["id"],
                "name": item.get("name") if isinstance(item.get("name"), str) else "",
                "type_name": (
                    item.get("type_name") if isinstance(item.get("type_name"), str) else ""
                ),
                "status_code": item.get("status_code")
                if type(item.get("status_code")) is int
                else None,
                "status": item.get("status") if isinstance(item.get("status"), str) else None,
                "incomplete": item.get("incomplete") is True,
            }
        )
    truncated = details.get("truncated") is True or len(items) > len(kept)
    return {
        "unhealthy_total": total,
        "returned": len(kept),
        "truncated": truncated,
        "items": kept,
    }


def _refusal_details(live: dict) -> dict:
    """Report what is reliably known; mark unavailable details as unknown."""
    inspection = live.get("inspection") or {}
    units = inspection.get("units")
    units_known = isinstance(units, str) and bool(units)
    details = {
        "actual_units": units if units_known else None,
        "actual_units_known": units_known,
        "units_query_code": inspection.get("units_query_code"),
        "dependency_inventory": "unknown",
        "dependency_inventory_note": (
            "Toolkit exposes no reliable dependency list here; the boolean "
            "dependency_free check is all that is provable"
        ),
    }
    unhealthy = _unhealthy_features(live)
    if unhealthy is not None:
        breakdown = (
            f"per-feature diagnosis from the native health scan: "
            f"{unhealthy['unhealthy_total']} unhealthy feature(s), "
            f"{unhealthy['returned']} listed"
        )
        if unhealthy["truncated"]:
            breakdown += "; list truncated, the full inventory stays with the inspection sidecar"
        details["health_breakdown"] = breakdown
        details["unhealthy_features"] = unhealthy
    else:
        details["health_breakdown"] = (
            "combined failed/suppressed/incomplete feature check; per-feature "
            "reasons are unavailable"
        )
    return details


# Stable reason codes the native executor prefixes onto adoption refusals that
# fire before a live summary exists (e.g. an assembly current window, or no
# current model at all; NO_CURRENT_MODEL keeps its native spelling).
_NATIVE_REFUSAL_CODES = frozenset(
    {
        "unsupported_model_type",
        "non_millimeter_units",
        "external_dependencies",
        "unhealthy_features",
        "NO_CURRENT_MODEL",
    }
)


def _native_refusal(message: str) -> dict | None:
    """Shape a native-level stable-prefix refusal as a structured refusal."""
    code, _, _ = message.partition(":")
    if code not in _NATIVE_REFUSAL_CODES:
        return None
    return {
        "available": False,
        "reason": message,
        "reason_code": code,
        "available_modes": [],
        "conflict": None,
        "current_model": None,
        "refusal_details": {
            "actual_units": None,
            "actual_units_known": False,
            "units_query_code": None,
            "dependency_inventory": "unknown",
            "dependency_inventory_note": (
                "the native executor refused before a live summary was available; "
                "units/dependency/health values were not queried"
            ),
            "health_breakdown": "unavailable for the same reason",
        },
        "file": None,
        "source_kind": "unknown",
        "model_id": None,
        "evidence_token": None,
    }


def _new_model(model_id: str, model_name: str | None = None) -> dict:
    path = general.model_path(model_id)
    return {
        "model_id": model_id,
        "model_name": model_name or f"adopt_{model_id[:8]}",
        "revision": 0,
        "created_at": bridge.now(),
        "status": "adopt_pending",
        "aliases": {},
        "model_type": "part",
        "output_directory": str(path / "output"),
        "part_file": None,
    }


def _evidence(model: dict, live: dict, file: dict, *, snapshot: bool = False) -> dict:
    token = uuid.uuid4().hex
    record = {
        "live": live,
        "file": file,
        "model": model,
        "created": time.time(),
        "token": token,
        "snapshot": snapshot,
    }
    bridge.write_json(
        _directory(model["model_id"]) / f"evidence-{token}.json", record, durable=True
    )
    return {
        "model_id": model["model_id"],
        "status": model["status"],
        "available": True,
        "reason": None,
        "conflict": None,
        "current_model": _summary_only(record),
        "file": file,
        "default_model_name": model["model_name"],
        "evidence_token": token,
        "expires_in_seconds": TOKEN_SECONDS,
        "source_kind": "session_snapshot" if snapshot else "file",
        "contract": (
            "apply confirms the frozen prepared snapshot; later source edits are excluded"
            if snapshot
            else "apply copies the inspected current session state; the source is untouched"
        ),
    }


def inspect(model_id: str | None = None) -> dict:
    """Inspect the current source, or renew evidence for an existing frozen snapshot."""
    if model_id is not None:
        with bridge.toolkit_lock(operation="inspect_adoption_snapshot", model_id=model_id):
            model = general.model_info(model_id)
            snapshot = _prepared(model)
            return _evidence(model, snapshot["live"], snapshot["file"], snapshot=True)
    model_id = uuid.uuid4().hex
    path = general.model_path(model_id)
    model = _new_model(model_id)
    try:
        (path / "output").mkdir(parents=True)
        with bridge.toolkit_lock(operation="adoption_preflight"):
            manifest = {
                "job_id": uuid.uuid4().hex,
                "kind": "adoption_preflight",
                "model_id": model_id,
                "status": "running",
                "created_at": bridge.now(),
            }
            probe = bridge.job_path(manifest["job_id"])
            (probe / "output").mkdir(parents=True)
            bridge.write_json(probe / "request.json", _native_request(model, {"action": "inspect"}))
            try:
                live = _native(probe, manifest)["live"]
                # Defense in depth: split even when the executor boundary was
                # substituted or predates reference splitting (BUG-076).
                inspection_refs.split(live, probe, "live")
                manifest["status"] = "succeeded"
            except RuntimeError as error:
                manifest["status"] = "failed"
                # A native stable-prefix refusal (e.g. an assembly current window)
                # is a structured refusal, not an unknown failure; the failed
                # preflight job stays as evidence.
                structured = _native_refusal(str(error))
                if structured is not None:
                    shutil.rmtree(path, ignore_errors=True)
                    return structured
                raise
            except AdoptionMetadataBudgetExceeded as error:
                manifest["status"] = "failed"
                manifest["reason"] = "ADOPTION_METADATA_BUDGET_EXCEEDED"
                manifest["reason_details"] = error.payload
                raise
            except Exception:
                manifest["status"] = "failed"
                raise
            finally:
                manifest["finished_at"] = bridge.now()
                bridge.write_json(probe / "job.json", manifest, durable=True)
            # Keep identity checks and token publication inside the cleanup boundary
            # and the same channel lock (BUG-071). Each post-native stage stays
            # observable on the preflight job: a failure here never leaves the
            # probe reporting success without its stage (FEAT-006/008).
            origin = live.get("origin")
            refusal = _refusal_reason(live)
            if not isinstance(origin, str):
                raise ValueError("Source origin could not be determined; no adoption accepted")
            failed_stage = "identity_verification"
            try:
                file = identity(Path(origin)) if origin else None
                failed_stage = "conflict_scan"
                conflict = _origin_conflict(Path(origin), exclude=model_id) if origin else None
                if conflict:
                    reason, reason_code = conflict["message"], conflict["reason"]
                elif refusal:
                    reason, reason_code = refusal[1], refusal[0]
                elif not origin:
                    reason, reason_code = None, "snapshot_required"
                else:
                    reason, reason_code = None, None
                if reason or not origin:
                    shutil.rmtree(path)
                    return {
                        "available": False,
                        "reason": reason or "snapshot_required: use mode=prepare",
                        "reason_code": reason_code,
                        "available_modes": [] if reason else ["prepare"],
                        "conflict": conflict,
                        "current_model": _summary_only({"live": live}),
                        "refusal_details": _refusal_details(live),
                        "file": file,
                        "source_kind": "file" if origin else "session_only",
                        "model_id": None,
                        "evidence_token": None,
                    }
                failed_stage = "token_publication"
                model.update(
                    model_type=live["model_type"],
                    adopted_from={
                        "origin": file["path"],
                        "origin_sha256": file["sha256"],
                        "source_kind": "file",
                        "state": "pending",
                        "inspected_at": bridge.now(),
                    },
                )
                evidence = _evidence(model, live, file)
                # Publish the registry last: source/hash/token failures cannot leave
                # a visible model even if cleanup of staging files is unavailable.
                model_registry.write_model(path, model)
                return evidence
            except AdoptionMetadataBudgetExceeded as error:
                manifest.update(
                    status="failed",
                    reason="ADOPTION_METADATA_BUDGET_EXCEEDED",
                    reason_details=error.payload,
                    message=str(error),
                    finished_at=bridge.now(),
                )
                raise
            except Exception as error:
                manifest.update(
                    status="failed",
                    reason="preflight_stage_failed",
                    failed_stage=failed_stage,
                    message=str(error),
                    finished_at=bridge.now(),
                )
                raise
    except Exception:
        # This path never mutates the source. Do not leave a registration without
        # published evidence, including on hashing/conflict/token-write failures.
        shutil.rmtree(path, ignore_errors=True)
        raise


def _prepared(model: dict) -> dict:
    if (
        model.get("status") != "adopt_pending"
        or model.get("pending_job")
        or model.get("recovery_pending")
    ):
        raise ValueError("Prepared snapshot is not available; poll its job or reconcile first")
    snapshot = model.get("prepared_snapshot")
    if not snapshot:
        raise ValueError("This model has no prepared snapshot")
    if identity(owned_file(model, snapshot["file"]["path"])) != snapshot["file"]:
        raise ValueError("Prepared snapshot changed; preserve evidence and prepare a new snapshot")
    return snapshot


def _validate_evidence(model_id: str, evidence_token: str) -> tuple[dict, dict]:
    if not bridge.JOB_ID.fullmatch(evidence_token or ""):
        raise ValueError("Invalid evidence_token")
    model = general.model_info(model_id)
    if model.get("status") != "adopt_pending":
        raise ValueError(
            f"Model status is {model.get('status')!r}; only adopt_pending models can be applied"
        )
    if model.get("pending_job"):
        raise bridge.ToolkitBusy(
            "Adoption already has a pending job",
            holder={"job_id": model["pending_job"], "model_id": model_id, "operation": "adoption"},
        )
    record = _read(
        _directory(model_id) / f"evidence-{evidence_token}.json",
        metadata_kind="evidence_token",
        failed_stage="validate_evidence",
        model_id=model_id,
    )
    if not record or time.time() - record["created"] > TOKEN_SECONDS:
        raise ValueError("Evidence token is missing or expired; inspect again")
    if record["model"]["model_id"] != model_id or record["model"]["status"] != "adopt_pending":
        raise ValueError("Evidence token does not belong to this adopt-pending model")
    if record.get("snapshot"):
        snapshot = _prepared(model)
        if record["file"] != snapshot["file"]:
            raise ValueError("Evidence does not belong to the prepared snapshot")
        return model, record
    if _refusal_reason(record["live"]):
        raise ValueError("Source preflight refused adoption")
    if identity(Path(record["file"]["path"])) != record["file"]:
        raise ValueError("Source file changed since inspect; inspect again")
    conflict = _origin_conflict(Path(record["file"]["path"]), exclude=model_id)
    if conflict:
        raise ValueError(conflict["message"])
    return model, record


def _key(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", value):
        raise ValueError(
            "idempotency_key must contain 8-80 letters, digits, underscores or hyphens"
        )


def prepare(model_name: str | None, idempotency_key: str) -> dict:
    """Freeze a never-saved current model once; only apply can publish it as ready."""
    _key(idempotency_key)
    if model_name is not None:
        model_name = bridge.normalize_model_name(model_name)
    # The key deterministically locates the durable intent even when the caller
    # lost the initial response. It is unrelated to the source object's identity.
    model_id = digest([str(general.MODELS.resolve()), "prepare", idempotency_key])[:32]
    path = general.model_path(model_id)
    file = path / "adoption" / f"intent-{digest(idempotency_key)}.json"
    arguments = {"mode": "prepare", "model_name": model_name, "idempotency_key": idempotency_key}
    with bridge.toolkit_lock(operation="submit_adoption_prepare", model_id=model_id):
        existing = _read(
            file,
            metadata_kind="commit_journal",
            failed_stage="submit_adoption_prepare",
            model_id=model_id,
        )
        if existing:
            if existing["arguments"] != arguments:
                raise ValueError("Idempotency key already belongs to another adoption request")
            return bridge.get_job(existing["job_id"], "compact")
        if path.exists():
            raise ValueError(
                f"Incomplete preparation exists; inspect/reconcile model_id {model_id}"
            )
        model = _new_model(model_id, model_name)
        job_id = uuid.uuid4().hex
        directory = bridge.job_path(job_id)
        manifest = {
            "job_id": job_id,
            "kind": "adoption",
            "adoption_action": "prepare",
            "model_id": model_id,
            "status": "queued",
            "revision": 0,
            "idempotency_key": idempotency_key,
            "created_at": bridge.now(),
            "stage": "snapshot_intent_persisted",
            "message": "Snapshot preparation accepted; poll this job_id",
        }
        try:
            (path / "output").mkdir(parents=True)
            model_registry.write_model(path, model)
            (directory / "output").mkdir(parents=True)
            bridge.write_json(
                directory / "request.json",
                _native_request(model, {"action": "prepare"}),
                durable=True,
            )
            bridge.write_json(directory / "job.json", manifest, durable=True)
            bridge.write_json(
                file if file.parent.exists() else _journal(model_id, idempotency_key),
                {
                    "state": "intent",
                    "model_id": model_id,
                    "job_id": job_id,
                    "arguments": arguments,
                    "created_at": bridge.now(),
                },
                durable=True,
            )
            model.update(pending_job=job_id, last_job=job_id)
            model_registry.write_model(path, model)
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
            # No native execution was launched by a failed Popen. Keep an audited
            # failed job usable by abandon_new; never publish ready without proof.
            if (directory / "job.json").is_file():
                _record_failure(job_id, manifest, file, error, locked=True)
                bridge.write_json(directory / "job.json", manifest, durable=True)
            else:
                shutil.rmtree(path, ignore_errors=True)
            raise
        return manifest


def apply(
    model_id: str, evidence_token: str, model_name: str | None = None, idempotency_key: str = ""
) -> dict:
    if not bridge.JOB_ID.fullmatch(model_id or ""):
        raise ValueError("Invalid model_id")
    _key(idempotency_key)
    if model_name is not None:
        model_name = bridge.normalize_model_name(model_name)
    arguments = {
        "model_id": model_id,
        "evidence_token": evidence_token,
        "model_name": model_name,
        "idempotency_key": idempotency_key,
    }
    file = _journal(model_id, idempotency_key)
    existing = _read(
        file,
        metadata_kind="commit_journal",
        failed_stage="submit_adoption_apply",
        model_id=model_id,
    )
    if existing:
        if existing["arguments"] != arguments:
            raise ValueError("Idempotency key already belongs to another adoption request")
        resume_committed(existing["job_id"])
        return bridge.get_job(existing["job_id"], "compact")
    launch_error = None
    manifest = None
    directory = None
    try:
        with bridge.toolkit_lock(operation="submit_adoption", model_id=model_id):
            if file.exists():
                raise bridge.ToolkitBusy("Adoption request was concurrently accepted; poll its job")
            model, record = _validate_evidence(model_id, evidence_token)
            chosen = model_name or model["model_name"]
            if record.get("snapshot") and chosen != model["model_name"]:
                raise ValueError(
                    "A prepared snapshot cannot be renamed; use its prepared model_name"
                )
            model = {**model, "model_name": chosen}
            job_id = uuid.uuid4().hex
            directory = bridge.job_path(job_id)
            (directory / "output").mkdir(parents=True)
            choice = {
                "action": "apply",
                "origin": record["file"]["path"],
                "origin_sha256": record["file"]["sha256"],
                "session_fingerprint": record["live"]["session_fingerprint"],
            }
            choice.update(inspection_refs.request_field(record["live"], "live_inspection"))
            if record.get("snapshot"):
                choice = {
                    "action": "confirm_snapshot",
                    "source_file": record["file"]["path"],
                    "source_identity": record["file"],
                }
                choice.update(
                    inspection_refs.request_field(model["prepared_snapshot"], "source_inspection")
                )
            if record["live"].get("display_name"):
                choice["display_name"] = record["live"]["display_name"]
            manifest = {
                "job_id": job_id,
                "kind": "adoption",
                "model_id": model_id,
                "status": "queued",
                "idempotency_key": idempotency_key,
                "created_at": bridge.now(),
                "stage": "intent_persisted",
                "revision": model["revision"],
                "message": "Adoption accepted; poll this job_id",
            }
            bridge.write_json(
                directory / "request.json", _native_request(model, choice), durable=True
            )
            bridge.write_json(directory / "job.json", manifest, durable=True)
            bridge.write_json(
                file,
                {
                    "state": "intent",
                    "model_id": model_id,
                    "job_id": job_id,
                    "arguments": arguments,
                    "evidence": {"live": _summary_only(record), "file": record["file"]},
                    "created_at": bridge.now(),
                },
                durable=True,
            )
            reserved = general.model_info(model_id)
            reserved["model_name"] = chosen
            reserved["pending_job"] = job_id
            reserved["last_job"] = job_id
            model_registry.write_model(general.model_path(model_id), reserved)
            with (directory / "runner.log").open("ab") as log:
                try:
                    subprocess.Popen(
                        [sys.executable, str(bridge.ROOT / "bridge.py"), "run-job", job_id],
                        cwd=bridge.ROOT,
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        creationflags=bridge.HIDDEN,
                        close_fds=True,
                    )
                except OSError as error:
                    _record_failure(job_id, manifest, file, error, locked=True)
                    launch_error = error
            if launch_error is None:
                return manifest
    except Exception as error:
        if launch_error is None:
            raise
        manifest["channel_finalization_error"] = str(error)
    bridge.write_json(directory / "job.json", manifest, durable=True)
    raise launch_error


def _summary_only(record: dict) -> dict:
    live = dict(record.get("live") or {})
    inline = live.pop("inspection", None)
    if inline is not None:
        live.setdefault("inspection_summary", inspection_summary(inline))
    # A split record already carries inspection_summary plus the small
    # controlled inspection_ref; both stay visible to the caller.
    return live


def _finish(record: dict) -> dict:
    """Materialize a durable commit; never invoke Toolkit or overwrite later edits."""
    model = general.model_info(record["model_id"])
    after = record["model_after"]
    if model.get("pending_job") == record["job_id"]:
        if (
            identity(bridge.job_path(record["job_id"]) / "native_result.json")
            != record["result_identity"]
        ):
            raise ValueError("Committed native evidence changed; keep adoption protection")
        expected_output = record.get("output_identity")
        if (
            expected_output
            and identity(owned_file(after, expected_output["path"])) != expected_output
        ):
            raise ValueError("Committed snapshot file changed; keep adoption protection")
        model_registry.write_model(general.model_path(record["model_id"]), after)
    elif (
        model.get("adopted_from", {}).get("adoption_id") != record["job_id"]
        and model.get("prepared_snapshot", {}).get("prepare_job_id") != record["job_id"]
    ):
        raise ValueError("Committed adoption conflicts with current registry; preserve audit")
    return record["job_after"]


def resume_committed(job_id: str) -> dict | None:
    """Polling may finish a committed metadata transaction, never native execution."""
    manifest = bridge.read_json(bridge.job_path(job_id) / "job.json")
    if manifest.get("kind") != "adoption" or manifest.get("status") == "succeeded":
        return None
    try:
        record = _read(
            _journal(manifest["model_id"], manifest["idempotency_key"]),
            metadata_kind="commit_journal",
            failed_stage="finish_adoption_commit",
            job_id=job_id,
            model_id=manifest.get("model_id"),
        )
    except AdoptionMetadataBudgetExceeded as error:
        # A journal that cannot be read under the budget must not break polling:
        # the durable manifest keeps the recorded terminal diagnosis and the
        # budget hit is only an annotation on it.
        return {**manifest, "commit_read_budget_exceeded": error.payload}
    if not record or record.get("state") != "committed":
        return None
    try:
        with bridge.toolkit_lock(
            operation="finish_adoption_commit", job_id=job_id, model_id=manifest["model_id"]
        ):
            terminal = _finish(record)
    except bridge.ToolkitBusy:
        return {
            **manifest,
            "commit_pending": True,
            "message": "Durable adoption commit awaits metadata materialization; poll this job",
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


def run(job_id: str, manifest: dict) -> None:
    directory = bridge.job_path(job_id)
    file = _journal(manifest["model_id"], manifest["idempotency_key"])
    failure_recorded = False
    try:
        with bridge.toolkit_lock(
            operation="adoption_apply", job_id=job_id, model_id=manifest["model_id"]
        ):
            try:
                manifest = _run_locked(job_id, manifest, file)
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


def _run_locked(job_id: str, manifest: dict, file: Path) -> dict:
    intent = bridge.read_json(file)
    if intent.get("state") == "committed":
        return _finish(intent)
    directory = bridge.job_path(job_id)
    current = general.model_info(manifest["model_id"])
    if current.get("pending_job") != job_id or current.get("status") != "adopt_pending":
        raise AdoptionRefused(
            "reservation_changed", "Adoption reservation no longer belongs to this intent"
        )
    request = bridge.read_json(directory / "request.json")
    if request["adoption"]["action"] == "apply":
        expected_source = intent["evidence"]["file"]
        if identity(Path(expected_source["path"])) != expected_source:
            raise AdoptionRefused("source_changed", "Source file changed before native dispatch")
    if request["adoption"]["action"] == "confirm_snapshot":
        expected = request["adoption"]["source_identity"]
        if identity(owned_file(current, expected["path"])) != expected:
            raise AdoptionRefused(
                "snapshot_changed", "Prepared snapshot changed before native dispatch"
            )
    result = _native(directory, manifest)
    if request["adoption"].get("path_source"):
        expected_source = intent["evidence"]["file"]
        if identity(Path(expected_source["path"])) != expected_source:
            raise RuntimeError("Path source changed during copying; protection retained")
        if result.get("source_unchanged") is not True or result.get("window_unchanged") is not True:
            raise RuntimeError("Path source/window verification missing; protection retained")
    # Defense in depth for substituted/older executor boundaries: every
    # downstream consumer (registry, journal, manifest) sees references only.
    _split_result(result, directory)
    current = general.model_info(manifest["model_id"])
    if current.get("pending_job") != job_id:
        raise AdoptionRefused("reservation_changed", "Adoption reservation changed during apply")
    if result.get("saved_file_reloaded_and_verified") is not True:
        raise RuntimeError("Native snapshot lacks save/reload verification; protection retained")
    if request["adoption"]["action"] == "prepare":
        return _commit_prepared(job_id, manifest, file, intent, current, result)
    after = {**current}
    file_identity = identity(owned_file(after, result["part_file"]))
    if (
        request["adoption"]["action"] == "confirm_snapshot"
        and file_identity != request["adoption"]["source_identity"]
    ):
        raise RuntimeError(
            "Prepared snapshot file changed during confirmation; protection retained"
        )
    result["sha256"] = file_identity["sha256"]
    after.update(
        status="ready",
        revision=1,
        part_file=result["part_file"],
        part_sha256=file_identity["sha256"],
        aliases=result.get("aliases", {}),
        pending_job=None,
        updated_at=bridge.now(),
        adopted_from={
            **current.get("adopted_from", {}),
            "adoption_id": job_id,
            "state": "completed",
            "source_display_name": request["adoption"].get("display_name"),
            "adopted_at": bridge.now(),
        },
    )
    # The registry keeps only the summary plus the controlled reference; the
    # full baseline stays in the job directory bound by SHA256 (BUG-076).
    after.update(
        {
            key: result[key]
            for key in ("inspection_ref", "inspection_summary", "inspection")
            if key in result
        }
    )
    manifest.update(
        status="succeeded",
        stage="adoption_committed",
        result=result,
        revision=after["revision"],
        finished_at=bridge.now(),
        message="Adoption committed as a managed copy; the source model was never modified",
    )
    intent.update(
        state="verified",
        model_after=after,
        job_after=manifest,
        result_identity=identity(directory / "native_result.json"),
        output_identity=file_identity,
        request=request,
    )
    bridge.write_json(file, intent, durable=True)
    intent["state"] = "committed"  # Durable decision precedes materialization.
    bridge.write_json(file, intent, durable=True)
    _finish(intent)
    if not request["adoption"].get("path_source"):
        _record_session_change(job_id, manifest)
    return manifest


def _record_session_change(job_id: str, manifest: dict) -> None:
    """Adoption displayed a managed copy; keep the session record accurate."""
    try:
        from creo_mechdog.session_models import record_session_change

        record_session_change(
            "creo_adopt_current_model",
            f"displayed managed copy {manifest.get('model_id')}",
            {"job_id": job_id, "model_id": manifest.get("model_id")},
        )
    except (OSError, ValueError):
        pass  # Informational only; never fail a committed adoption.


def _commit_prepared(
    job_id: str, manifest: dict, file: Path, intent: dict, current: dict, result: dict
) -> dict:
    live = result["live"]
    if live.get("origin") != "" or _refusal_reason(live):
        raise RuntimeError("Native preparation did not prove a healthy never-saved source")
    snapshot_file = identity(owned_file(current, result["part_file"]))
    snapshot = {
        "prepare_job_id": job_id,
        "file": snapshot_file,
        "live": live,
        "aliases": result.get("aliases", {}),
    }
    snapshot.update(
        {
            key: result[key]
            for key in ("inspection_ref", "inspection_summary", "inspection")
            if key in result
        }
    )
    after = {
        **current,
        "model_type": live["model_type"],
        "prepared_snapshot": snapshot,
        "pending_job": None,
        "revision": 0,
        "last_job": job_id,
        "updated_at": bridge.now(),
        "adopted_from": {
            "source_kind": "session_snapshot",
            "origin": None,
            "source_display_name": live.get("display_name"),
            "state": "prepared",
        },
    }
    evidence = _evidence(after, live, snapshot_file, snapshot=True)
    # Keep the native evidence immutable; the public token belongs to the
    # metadata transaction and is also retained in compact polling responses.
    manifest.update(
        status="succeeded",
        stage="snapshot_prepared",
        revision=0,
        result={**result, "adopted": False, "adoption": evidence},
        finished_at=bridge.now(),
        message="Frozen snapshot prepared; review evidence then apply or abandon_new",
    )
    intent.update(
        state="verified",
        model_after=after,
        job_after=manifest,
        result_identity=identity(bridge.job_path(job_id) / "native_result.json"),
        output_identity=snapshot_file,
    )
    bridge.write_json(file, intent, durable=True)
    intent["state"] = "committed"
    bridge.write_json(file, intent, durable=True)
    _finish(intent)
    return manifest


def _record_failure(
    job_id: str, manifest: dict, file: Path, error: Exception, *, locked: bool
) -> bool:
    # A committed decision is recoverable by polling; do not replace it. A
    # second budget hit while reading the journal must never override the
    # original diagnosis: record it as a note and continue the closeout.
    try:
        persisted = (
            _read(
                file,
                metadata_kind="commit_journal",
                failed_stage="record_failure",
                job_id=job_id,
                model_id=manifest.get("model_id"),
            )
            or {}
        )
    except AdoptionMetadataBudgetExceeded as budget_error:
        persisted = {}
        manifest["failure_read_budget_exceeded"] = budget_error.payload
    if persisted.get("state") == "committed":
        return False
    started = bool(manifest.get("worker_started"))
    refused = isinstance(error, AdoptionRefused) and not started
    manifest.update(
        status="unknown_outcome" if started else "failed",
        stage="adoption_refused" if refused else "adoption_unconfirmed",
        reason=error.reason
        if isinstance(error, AdoptionRefused)
        else "native_outcome_unconfirmed"
        if started
        else "adoption_execution_failed",
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
            "adoption outcome is not confirmed; protection retained; "
            "resolve with creo_reconcile_model abandon_new once the worker has stopped"
        )
    elif locked:
        try:
            model = general.model_info(manifest["model_id"])
            if model.get("pending_job") == job_id:
                model["pending_job"] = None
                model["last_job"] = job_id
                model_registry.write_model(general.model_path(manifest["model_id"]), model)
                manifest["recovery_pending_released"] = True
        except (OSError, ValueError) as cleanup_error:
            manifest["recovery_pending_cleanup_error"] = str(cleanup_error)
    if isinstance(error, bridge.ToolkitBusy):
        manifest["busy"] = error.payload
    if isinstance(error, AdoptionMetadataBudgetExceeded):
        manifest["reason"] = "ADOPTION_METADATA_BUDGET_EXCEEDED"
        manifest["reason_details"] = error.payload
    return True


def adopt(
    mode: str = "inspect",
    model_id: str | None = None,
    evidence_token: str | None = None,
    model_name: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    if mode == "inspect":
        if any(value is not None for value in (evidence_token, model_name, idempotency_key)):
            raise ValueError("Inspect takes no parameters; apply requires the inspect results")
        return inspect(model_id)
    if mode == "prepare":
        if model_id is not None or evidence_token is not None or not idempotency_key:
            raise ValueError(
                "prepare requires idempotency_key, optional model_name; no model_id/token"
            )
        return prepare(model_name, idempotency_key)
    if mode != "apply" or not model_id or not evidence_token or not idempotency_key:
        raise ValueError("apply requires model_id, evidence_token and idempotency_key")
    return apply(model_id, evidence_token, model_name, idempotency_key)


def run_item_locked(job_id: str, manifest: dict, journal: Path) -> dict:
    """Execute one reserved path-adoption item under its parent's channel lock.

    The item has a real durable journal and native directory, but no separately
    submitted runner. The parent alone controls scheduling and unknown stop.
    """
    return _run_locked(job_id, manifest, journal)


def finish_item_commit(record: dict) -> dict:
    """Materialize a known durable item decision without invoking native code."""
    return _finish(record)
