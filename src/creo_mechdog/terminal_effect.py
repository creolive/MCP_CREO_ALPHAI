"""BUG-114: one scoped terminal-effect decision shared by every consumer.

A failed job used to report ``effect_status=unknown`` on every executed record
and ``component_changes.status=unknown_outcome`` even when the executor had
already proven that the only object it created (a new, never-saved model) was
erased and absent. The proof existed in ``failed_model_cleanup``; nothing
joined the two.

This module joins them without widening any proof:

    classify_terminal_effect(result, *, job_status, is_new_model,
                             checkpoint_present, operations, effect_scope)
        -> {"effect", "status", "reason", "scope"}

Decision table (first match wins, evaluated for a failed job):

====================================================  ================  ==========
evidence                                              effect            status
====================================================  ================  ==========
``model_unchanged is True`` (preflight refused)       ``no_effect``     confirmed
verified checkpoint restore                           ``rolled_back``   confirmed
trusted new-model cleanup (see below)                 ``no_effect``     confirmed
anything else (missing/partial/untrusted evidence)    ``unknown``       unconfirmed
====================================================  ================  ==========

``effect_scope`` separates domains that cleanup cannot cover:

* ``managed_model`` / ``component_bindings`` — the job's own unsaved model
  object. A confirmed cleanup erases exactly that object, so its net effect is
  ``no_effect``.
* ``external_outputs`` — files written outside the managed model (``export``,
  ``dump_tree``). Erasing the session model does not remove them and a
  checkpoint restore does not either. Only a request without executed external
  operations may be ``no_effect``; otherwise the scope stays ``unknown``.
* anything else (including an unknown scope name) — ``unknown``.

Trusted cleanup requires ALL of:

* ``is_new_model`` is True;
* the normalized receipt is exactly ``attempted=True, status="erased",
  reason="cleaned", erase_code=0, absence_verified=True`` (a bare
  ``ProMdlErase`` zero or a single absence flag is never enough);
* ``operations`` is the complete trusted request list and the terminal result
  carries exactly one record per input (same ``op`` at the same index, one of
  the documented execution statuses). A partial or missing result never
  upgrades.

The legacy ``rollback_succeeded`` boolean and the ``rollback_status`` field
keep their meaning (checkpoint restore, not cleanup); this module never
rewrites them and never derives one domain from the other. A genuinely
``unknown_outcome`` job stays unknown here and is never rewritten by a read
projection.
"""

from __future__ import annotations

from typing import Any

from creo_mechdog.operation_results import EXECUTION_STATUSES, EXTERNAL_OUTPUT_OPS

EFFECTS = ("committed", "rolled_back", "no_effect", "unknown")
STATUSES = ("confirmed", "unconfirmed", "unknown")
SCOPES = ("managed_model", "component_bindings", "external_outputs", "unknown")

REASON_JOB_SUCCEEDED = "job_succeeded"
REASON_READONLY = "readonly_no_write"
REASON_UNKNOWN_OUTCOME = "unknown_outcome"
REASON_NOT_TERMINAL = "not_terminal"
REASON_UNKNOWN_SCOPE = "unknown_effect_scope"
REASON_MODEL_UNCHANGED = "no_mutation_before_modeling"
REASON_CHECKPOINT_RESTORED = "checkpoint_restored"
REASON_CHECKPOINT_KEEPS_EXTERNAL = "checkpoint_restore_keeps_external_outputs"
REASON_CLEANUP_CONFIRMED = "new_model_cleanup_confirmed"
REASON_CLEANUP_KEEPS_EXTERNAL = "external_outputs_retained_after_cleanup"
REASON_EXTERNAL_NOT_EXECUTED = "external_outputs_not_executed"
REASON_NO_EXTERNAL_REQUESTED = "no_external_outputs_requested"
REASON_ROLLBACK_UNCONFIRMED = "rollback_unconfirmed"
REASON_ROLLBACK_WITHOUT_CHECKPOINT = "rollback_evidence_without_checkpoint"
REASON_CLEANUP_UNTRUSTED = "cleanup_receipt_untrusted"
REASON_NOT_NEW_MODEL_JOB = "not_new_model_job"
REASON_OPERATIONS_UNTRUSTED = "terminal_operations_untrusted"


def _verdict(effect: str, status: str, reason: str, scope: str) -> dict[str, str]:
    return {"effect": effect, "status": status, "reason": reason, "scope": scope}


def _operations_trusted(operations: Any, result: dict) -> bool:
    """One terminal record per input, in order, with a documented status."""
    if not isinstance(operations, list) or not operations:
        return False
    records = result.get("operations")
    if not isinstance(records, list) or len(records) != len(operations):
        return False
    for position, (source, record) in enumerate(zip(operations, records)):
        if not isinstance(source, dict) or not isinstance(record, dict):
            return False
        if source.get("op") != record.get("op"):
            return False
        if record.get("execution_status") not in EXECUTION_STATUSES:
            return False
        index = record.get("index")
        if index is not None and index != position:
            return False
    return True


def cleanup_is_trusted(result: dict, *, is_new_model: bool) -> bool:
    """The exact cleanup shape that may clear the managed-model effect."""
    if not is_new_model:
        return False
    receipt = result.get("failed_model_cleanup")
    if not isinstance(receipt, dict):
        return False
    erase_code = receipt.get("erase_code")
    return (
        receipt.get("attempted") is True
        and receipt.get("status") == "erased"
        and receipt.get("reason") == "cleaned"
        and type(erase_code) is int
        and erase_code == 0
        and receipt.get("absence_verified") is True
    )


def _external_operations(operations: Any, result: dict) -> tuple[bool, bool]:
    """Return ``(requested, executed)`` for external-output operations.

    ``executed`` counts a record whose execution status is ``succeeded`` or
    ``failed``; ``not_executed`` proves the file was never written.
    """
    if not isinstance(operations, list):
        return False, False
    records = result.get("operations")
    if not isinstance(records, list) or len(records) != len(operations):
        return False, False
    requested = False
    executed = False
    for source, record in zip(operations, records):
        if not isinstance(source, dict) or source.get("op") not in EXTERNAL_OUTPUT_OPS:
            continue
        requested = True
        if isinstance(record, dict) and record.get("execution_status") in (
            "succeeded",
            "failed",
        ):
            executed = True
    return requested, executed


def _external_scope(effect: str, reason: str, operations: Any, result: dict) -> dict[str, str]:
    """Apply the external-output rule to an otherwise model-level verdict."""
    requested, executed = _external_operations(operations, result)
    if not requested:
        return _verdict("no_effect", "confirmed", REASON_NO_EXTERNAL_REQUESTED, "external_outputs")
    if not executed:
        return _verdict("no_effect", "confirmed", REASON_EXTERNAL_NOT_EXECUTED, "external_outputs")
    # A model-level release never withdraws an already written external file.
    if effect == "rolled_back":
        reason = REASON_CHECKPOINT_KEEPS_EXTERNAL
    elif effect == "no_effect":
        reason = REASON_CLEANUP_KEEPS_EXTERNAL
    else:
        reason = REASON_ROLLBACK_UNCONFIRMED
    return _verdict("unknown", "unconfirmed", reason, "external_outputs")


def _failure_reason(result: dict) -> str:
    receipt = result.get("failed_model_cleanup")
    if isinstance(receipt, dict):
        reason = receipt.get("reason")
        if isinstance(reason, str) and reason:
            return reason
    return REASON_ROLLBACK_UNCONFIRMED


def classify_terminal_effect(
    result: Any,
    *,
    job_status: str,
    is_new_model: bool = False,
    checkpoint_present: bool | None = None,
    operations: Any = None,
    effect_scope: str = "managed_model",
) -> dict[str, str]:
    """Classify one scope of a terminal job; never upgrades unproven evidence."""
    scope = effect_scope if effect_scope in SCOPES else "unknown"
    if scope == "unknown":
        return _verdict("unknown", "unknown", REASON_UNKNOWN_SCOPE, "unknown")
    evidence = result if isinstance(result, dict) else {}
    if job_status == "succeeded":
        effect = "no_effect" if evidence.get("readonly") is True else "committed"
        return _verdict(effect, "confirmed", REASON_JOB_SUCCEEDED, scope)
    if job_status == "unknown_outcome":
        return _verdict("unknown", "unknown", REASON_UNKNOWN_OUTCOME, scope)
    if job_status != "failed":
        return _verdict("unknown", "unknown", REASON_NOT_TERMINAL, scope)
    if evidence.get("model_unchanged") is True:
        effect, reason = "no_effect", REASON_MODEL_UNCHANGED
    elif evidence.get("rollback_succeeded") is True:
        if checkpoint_present is False:
            return _verdict("unknown", "unconfirmed", REASON_ROLLBACK_WITHOUT_CHECKPOINT, scope)
        effect, reason = "rolled_back", REASON_CHECKPOINT_RESTORED
    elif cleanup_is_trusted(evidence, is_new_model=is_new_model):
        # The cleanup release additionally requires the complete per-operation
        # terminal trail; a partial result never upgrades.
        if not _operations_trusted(operations, evidence):
            return _verdict("unknown", "unconfirmed", REASON_OPERATIONS_UNTRUSTED, scope)
        effect, reason = "no_effect", REASON_CLEANUP_CONFIRMED
    else:
        # A perfectly cleaned receipt on a job that did not create its target
        # is not evidence about this model; name the veto explicitly.
        if not is_new_model and cleanup_is_trusted(evidence, is_new_model=True):
            return _verdict("unknown", "unconfirmed", REASON_NOT_NEW_MODEL_JOB, scope)
        return _verdict("unknown", "unconfirmed", _failure_reason(evidence), scope)
    if scope == "external_outputs":
        return _external_scope(effect, reason, operations, evidence)
    return _verdict(effect, "confirmed", reason, scope)


def apply_to_result(
    result: dict,
    *,
    job_status: str,
    is_new_model: bool = False,
    checkpoint_present: bool | None = None,
    operations: Any = None,
) -> dict:
    """Attach the three scoped verdicts to a terminal native result.

    Only failed and unknown-outcome results get the block: a succeeded job has
    no ambiguity to explain, and legacy results are never given a synthetic
    verdict.
    """
    if not isinstance(result, dict) or job_status not in ("failed", "unknown_outcome"):
        return result
    result["terminal_effect"] = {
        scope: classify_terminal_effect(
            result,
            job_status=job_status,
            is_new_model=is_new_model,
            checkpoint_present=checkpoint_present,
            operations=operations,
            effect_scope=scope,
        )
        for scope in ("managed_model", "component_bindings", "external_outputs")
    }
    return result
