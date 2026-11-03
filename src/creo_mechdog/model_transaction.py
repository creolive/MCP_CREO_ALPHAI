"""FEAT-059 shared multi-model transaction journal.

B01 owns this module: B02 (dimension links) and C04 (rename/derive) depend on
these two entry points, so the shape is frozen here before any of them write
code.

What it is: a project journal for a native operation that touches several
models at once. It is **not** a filesystem transaction and it does not add a
task queue state. The stages are:

``prepared`` -> ``native_saved`` -> ``registry_committed``
                                  -> ``recovered``          (failure, restore proven for every model)
                                  -> ``recovery_required``  (failure, at least one model unproven)

Two rules never bend:

* A checkpoint is only replaced after the whole transaction succeeded, so an
  interrupted run cannot destroy the state needed to recover.
* A model whose restore is not verified is reported as unproven, never as
  rolled back.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from creo_mechdog.paths import SOURCE_PATHS

SCHEMA_VERSION = 1
STAGES = ("prepared", "native_saved", "registry_committed", "recovered", "recovery_required")
TERMINAL_STAGES = ("registry_committed", "recovered", "recovery_required")
JOURNAL_DIR_NAME = "transactions"


class TransactionError(ValueError):
    """A transaction request that must be refused before anything is written."""


def journal_root(root: Path | None = None) -> Path:
    return (root or SOURCE_PATHS.data_root) / JOURNAL_DIR_NAME


def _journal_path(transaction_id: str, root: Path | None) -> Path:
    if (
        not transaction_id
        or "/" in transaction_id
        or "\\" in transaction_id
        or ".." in transaction_id
    ):
        raise TransactionError(f"invalid transaction id: {transaction_id!r}")
    return journal_root(root) / f"{transaction_id}.json"


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    os.replace(temporary, path)


def _check_revision(model_id: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TransactionError(f"expected_revisions[{model_id!r}] must be an integer revision")
    if value < 0:
        raise TransactionError(f"expected_revisions[{model_id!r}] must not be negative")
    return value


def prepare_model_transaction(
    model_ids: list[str], expected_revisions: dict[str, int], *, root: Path | None = None
) -> dict:
    """Validate and journal the intent to modify several models together."""
    if not isinstance(model_ids, list) or not model_ids:
        raise TransactionError("model_ids must be a non-empty list")
    seen: list[str] = []
    for model_id in model_ids:
        if not isinstance(model_id, str) or not model_id.strip():
            raise TransactionError("every model id must be a non-empty string")
        if model_id in seen:
            raise TransactionError(f"model {model_id!r} is listed twice")
        seen.append(model_id)
    if not isinstance(expected_revisions, dict):
        raise TransactionError("expected_revisions must be a mapping of model id to revision")
    missing = [model_id for model_id in seen if model_id not in expected_revisions]
    if missing:
        raise TransactionError("missing expected revisions for: " + ", ".join(missing))
    extra = [model_id for model_id in expected_revisions if model_id not in seen]
    if extra:
        raise TransactionError("expected revisions for models outside the set: " + ", ".join(extra))

    transaction_id = uuid.uuid4().hex
    record = {
        "schema_version": SCHEMA_VERSION,
        "transaction_id": transaction_id,
        "stage": "prepared",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "models": {
            model_id: {
                "expected_revision": _check_revision(model_id, expected_revisions[model_id]),
                "checkpoint": None,
                "saved": False,
                "verified": False,
                "revision_after": None,
                "rollback": "not_attempted",
            }
            for model_id in seen
        },
        "recovery": None,
        "published": False,
    }
    _write_atomic(_journal_path(transaction_id, root), record)
    return record


def load_transaction(transaction_id: str, *, root: Path | None = None) -> dict:
    path = _journal_path(transaction_id, root)
    if not path.is_file():
        raise TransactionError(f"unknown transaction: {transaction_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _model_reports(native_result: dict) -> dict:
    reports = native_result.get("models") if isinstance(native_result, dict) else None
    if not isinstance(reports, dict):
        raise TransactionError(
            "native_result.models must map model id to its saved/verified report"
        )
    return reports


def finish_model_transaction(
    transaction_id: str, native_result: dict, *, root: Path | None = None
) -> dict:
    """Close a prepared transaction with the native outcome.

    Failure never invents success and never rewrites a checkpoint: either the
    restore is proven for every model (``recovered``) or the whole set stays
    protected (``recovery_required``).
    """
    record = load_transaction(transaction_id, root=root)
    if record.get("stage") in TERMINAL_STAGES:
        # Repeating the finish must not duplicate a child model or a commit.
        record["idempotent"] = True
        return record

    reports = _model_reports(native_result)
    model_ids = list(record["models"])
    unknown = [model_id for model_id in model_ids if model_id not in reports]
    if unknown:
        raise TransactionError("native_result is missing reports for: " + ", ".join(unknown))

    for model_id in model_ids:
        report = reports[model_id]
        entry = record["models"][model_id]
        entry["saved"] = bool(report.get("saved"))
        entry["verified"] = bool(report.get("verified"))
        revision = report.get("revision")
        entry["revision_after"] = (
            revision if isinstance(revision, int) and not isinstance(revision, bool) else None
        )
        checkpoint = report.get("checkpoint")
        if isinstance(checkpoint, str) and checkpoint:
            entry["checkpoint"] = checkpoint

    rollback = native_result.get("rollback") or {}
    proven = {value for value in rollback.get("verified_models", []) if isinstance(value, str)}
    unproven = {value for value in rollback.get("unproven_models", []) if isinstance(value, str)}
    complete = all(entry["saved"] and entry["verified"] for entry in record["models"].values())
    for model_id in model_ids:
        entry = record["models"][model_id]
        if complete:
            # Every model saved and verified: there is nothing to restore.
            entry["rollback"] = "not_needed"
        elif model_id in unproven:
            entry["rollback"] = "unproven"
        elif model_id in proven:
            entry["rollback"] = "verified"
        else:
            entry["rollback"] = "not_attempted"

    registry = native_result.get("registry") or {}
    published = bool(registry.get("published"))

    record["stage"] = "native_saved"
    if complete and published:
        record["stage"] = "registry_committed"
        record["published"] = True
        record["recovery"] = None
    elif complete:
        record["stage"] = "recovery_required"
        record["recovery"] = {
            "reason": "registry_publish_failed",
            "registry_error": registry.get("error") or "unknown",
            "verified_models": [],
            "unproven_models": model_ids,
        }
    else:
        recovered = all(entry["rollback"] == "verified" for entry in record["models"].values())
        record["stage"] = "recovered" if recovered else "recovery_required"
        if recovered:
            proven_models, pending_models = list(model_ids), []
        else:
            # A model counts as restored only when the native side proved it;
            # everything else stays pending, never "rolled back".
            proven_models = sorted(
                model_id
                for model_id in model_ids
                if model_id in proven and model_id not in unproven
            )
            pending_models = [model_id for model_id in model_ids if model_id not in proven_models]
        record["recovery"] = {
            "reason": "native_save_failed",
            "registry_error": None,
            "verified_models": proven_models,
            "unproven_models": pending_models,
        }

    if record["stage"] in ("registry_committed", "recovered"):
        record["protected_models"] = []
    else:
        record["protected_models"] = [
            model_id
            for model_id in model_ids
            if record["models"][model_id]["rollback"] != "verified"
        ]
    record["success"] = record["stage"] == "registry_committed"
    _write_atomic(_journal_path(transaction_id, root), record)
    return record
