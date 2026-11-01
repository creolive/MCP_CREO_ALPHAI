"""BUG-096 (Q03/E): safety policy for cleaning up failed new-model orphans.

A failed ``new=true`` job leaves an unsaved session object that blocks the
next same-name model (``New model name already exists in the Creo session``).
Cleanup erases at most one object: the session model proven to be created by
the failed job itself. Everything else is kept and reported.

Native receipt (``native/generic.cpp`` failure tail, mirrored here):

    failed_model_cleanup = {
        "attempted": bool,
        "status": "erased" | "skipped" | "failed" | "unknown",
        "reason": str,
        "erase_code": int | None,
        "absence_verified": bool,
    }

Rules (the reason shapes in :data:`RECEIPT_SHAPES` are the contract):

- Only a candidate proven job-created, still identical, never saved, not in a
  window, not user-modified and unreferenced may be erased (see
  :func:`evaluate_candidate`). Any unproven or vetoed candidate is kept.
- ``absence_verified`` is True only when the absence queries really ran and
  confirmed absence. A receipt without that confirmation never claims it.
- ``erase_code`` carries the raw ``ProMdlErase`` code only when an erase was
  attempted; veto/skip receipts carry ``None``.
- This block is NOT restore-from-checkpoint. ``rollback_*`` keeps its old
  meaning (see the BUG-012 backlog row, cross-referenced only); the two
  coexist and are never derived from each other. Unknown-outcome recovery
  protection (FEAT-018) is likewise never cleared by this module.
- Never erase_all, never clear unknown/recovery protection, never adopt an
  arbitrary unsaved object, never retry unconditionally.

The native executor mirrors this vocabulary; unit tests drive this module
with isolated stubs and never touch Creo or any real object.
"""

from __future__ import annotations

from typing import Any

RECEIPT_KEYS = ("attempted", "status", "reason", "erase_code", "absence_verified")
RECEIPT_STATUSES = ("erased", "skipped", "failed", "unknown")

REASON_CLEANED = "cleaned"
REASON_ERASE_FAILED = "erase_failed"
REASON_ERASE_UNCONFIRMED = "erase_unconfirmed"
REASON_PREEXISTING_SAME_NAME = "preexisting_same_name"
REASON_IDENTITY_CHANGED = "identity_changed"
REASON_SAVED_SINCE_CREATION = "saved_since_creation"
REASON_WINDOW_OPEN = "window_open"
REASON_USER_MODIFIED = "user_modified"
REASON_REFERENCED_BY_OTHER = "referenced_by_other"
REASON_SAFETY_QUERY_FAILED = "safety_query_failed"
REASON_ORPHAN_ALREADY_ABSENT = "orphan_already_absent"
REASON_NO_ORPHAN_CREATED = "no_orphan_created"
REASON_NOT_NEW_MODEL_JOB = "not_new_model_job"
REASON_NO_SESSION_LOOKUP = "no_session_lookup"
REASON_UNKNOWN_OUTCOME = "unknown_outcome"
REASON_NOT_REPORTED = "not_reported"
REASON_INVALID_RECEIPT = "invalid_receipt"

# reason -> the only shape the contract accepts. erase_code is either the
# literal zero (the erase call returned no error), a nonzero-error marker, or
# None (no erase call was attempted).
RECEIPT_SHAPES: dict[str, dict[str, Any]] = {
    REASON_CLEANED: {
        "attempted": True,
        "status": "erased",
        "erase_code": 0,
        "absence_verified": True,
    },
    REASON_ERASE_FAILED: {
        "attempted": True,
        "status": "failed",
        "erase_code": "nonzero",
        "absence_verified": False,
    },
    REASON_ERASE_UNCONFIRMED: {
        "attempted": True,
        "status": "unknown",
        "erase_code": 0,
        "absence_verified": False,
    },
    REASON_PREEXISTING_SAME_NAME: {
        "attempted": True,
        "status": "skipped",
        "erase_code": None,
        "absence_verified": False,
    },
    REASON_IDENTITY_CHANGED: {
        "attempted": True,
        "status": "skipped",
        "erase_code": None,
        "absence_verified": False,
    },
    REASON_SAVED_SINCE_CREATION: {
        "attempted": True,
        "status": "skipped",
        "erase_code": None,
        "absence_verified": False,
    },
    REASON_WINDOW_OPEN: {
        "attempted": True,
        "status": "skipped",
        "erase_code": None,
        "absence_verified": False,
    },
    REASON_USER_MODIFIED: {
        "attempted": True,
        "status": "skipped",
        "erase_code": None,
        "absence_verified": False,
    },
    REASON_REFERENCED_BY_OTHER: {
        "attempted": True,
        "status": "skipped",
        "erase_code": None,
        "absence_verified": False,
    },
    REASON_SAFETY_QUERY_FAILED: {
        "attempted": True,
        "status": "skipped",
        "erase_code": None,
        "absence_verified": False,
    },
    REASON_ORPHAN_ALREADY_ABSENT: {
        "attempted": True,
        "status": "skipped",
        "erase_code": None,
        "absence_verified": True,
    },
    REASON_NO_ORPHAN_CREATED: {
        "attempted": True,
        "status": "skipped",
        "erase_code": None,
        "absence_verified": True,
    },
    REASON_NOT_NEW_MODEL_JOB: {
        "attempted": False,
        "status": "skipped",
        "erase_code": None,
        "absence_verified": False,
    },
    REASON_NO_SESSION_LOOKUP: {
        "attempted": False,
        "status": "skipped",
        "erase_code": None,
        "absence_verified": False,
    },
    REASON_UNKNOWN_OUTCOME: {
        "attempted": False,
        "status": "unknown",
        "erase_code": None,
        "absence_verified": False,
    },
    REASON_NOT_REPORTED: {
        "attempted": False,
        "status": "unknown",
        "erase_code": None,
        "absence_verified": False,
    },
    REASON_INVALID_RECEIPT: {
        "attempted": False,
        "status": "unknown",
        "erase_code": None,
        "absence_verified": False,
    },
}

# The seven probe results a stub (or the native executor) must describe. All
# must be present and boolean: a probe that never ran is not a probe that
# returned "safe".
CANDIDATE_KEYS = (
    "created_by_job",
    "identity_matches",
    "never_saved",
    "window_open",
    "user_modified",
    "referenced_by_other",
    "safety_query_failed",
)


def receipt_unknown_outcome() -> dict:
    """Synthesized receipt when the job outcome is unknown (no native block)."""
    return {
        "attempted": False,
        "status": "unknown",
        "reason": REASON_UNKNOWN_OUTCOME,
        "erase_code": None,
        "absence_verified": False,
    }


def receipt_not_reported() -> dict:
    """Synthesized receipt when a result exists but carries no native block."""
    return {
        "attempted": False,
        "status": "unknown",
        "reason": REASON_NOT_REPORTED,
        "erase_code": None,
        "absence_verified": False,
    }


def evaluate_candidate(evidence: dict) -> dict:
    """Decide for one candidate from its stubbed probe evidence.

    Returns ``{"action": "erase"|"keep", "reason": <reason code>}``. The veto
    order is fixed: not job-created, probe failure, identity change, saved
    since creation, window open, user modified, referenced elsewhere. Only a
    fully proven orphan reaches ``{"action": "erase", "reason": "cleaned"}``.
    """
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be an object of probe results")
    missing = [key for key in CANDIDATE_KEYS if key not in evidence]
    if missing:
        raise ValueError(f"evidence is missing probe results: {missing}")
    for key in CANDIDATE_KEYS:
        if type(evidence[key]) is not bool:
            raise ValueError(f"probe result {key} must be a boolean")
    if not evidence["created_by_job"]:
        return {"action": "keep", "reason": REASON_PREEXISTING_SAME_NAME}
    if evidence["safety_query_failed"]:
        return {"action": "keep", "reason": REASON_SAFETY_QUERY_FAILED}
    if not evidence["identity_matches"]:
        return {"action": "keep", "reason": REASON_IDENTITY_CHANGED}
    if not evidence["never_saved"]:
        return {"action": "keep", "reason": REASON_SAVED_SINCE_CREATION}
    if evidence["window_open"]:
        return {"action": "keep", "reason": REASON_WINDOW_OPEN}
    if evidence["user_modified"]:
        return {"action": "keep", "reason": REASON_USER_MODIFIED}
    if evidence["referenced_by_other"]:
        return {"action": "keep", "reason": REASON_REFERENCED_BY_OTHER}
    return {"action": "erase", "reason": REASON_CLEANED}


def validate_receipt(raw: Any) -> dict:
    """Validate one native receipt against :data:`RECEIPT_SHAPES`; ValueError otherwise."""
    if not isinstance(raw, dict):
        raise ValueError("failed_model_cleanup must be an object")
    if set(raw) != set(RECEIPT_KEYS):
        raise ValueError(f"failed_model_cleanup must contain exactly {list(RECEIPT_KEYS)}")
    if type(raw["attempted"]) is not bool:
        raise ValueError("attempted must be a boolean")
    if raw["status"] not in RECEIPT_STATUSES:
        raise ValueError(f"status must be one of {list(RECEIPT_STATUSES)}")
    reason = raw["reason"]
    if not isinstance(reason, str) or reason not in RECEIPT_SHAPES:
        raise ValueError("reason is not a documented cleanup reason")
    erase_code = raw["erase_code"]
    if erase_code is not None and type(erase_code) is not int:
        raise ValueError("erase_code must be an integer or null")
    if type(raw["absence_verified"]) is not bool:
        raise ValueError("absence_verified must be a boolean")
    shape = RECEIPT_SHAPES[reason]
    if raw["attempted"] is not shape["attempted"]:
        raise ValueError(f"reason {reason} does not match attempted={raw['attempted']}")
    if raw["status"] != shape["status"]:
        raise ValueError(f"reason {reason} does not match status={raw['status']}")
    if raw["absence_verified"] is not shape["absence_verified"]:
        raise ValueError(
            "absence_verified may only be true after the absence queries ran and "
            f"confirmed absence; reason {reason} never claims it"
        )
    rule = shape["erase_code"]
    if rule is None and erase_code is not None:
        raise ValueError(f"reason {reason} never attempted an erase; erase_code must be null")
    if rule == 0 and erase_code != 0:
        raise ValueError(f"reason {reason} requires erase_code 0")
    if rule == "nonzero" and (erase_code == 0):
        raise ValueError(f"reason {reason} requires the raw nonzero erase_code")
    return dict(raw)


def normalize_receipt(raw: Any) -> dict:
    """Like :func:`validate_receipt` but never raises.

    A contract break degrades to an honest ``invalid_receipt`` unknown block
    (``absence_verified`` False); it is never upgraded to a success claim.
    """
    try:
        return validate_receipt(raw)
    except ValueError:
        return {
            "attempted": False,
            "status": "unknown",
            "reason": REASON_INVALID_RECEIPT,
            "erase_code": None,
            "absence_verified": False,
        }


def ensure_terminal_receipt(manifest: dict) -> None:
    """Register an honest ``failed_model_cleanup`` block on a terminal job.

    Runs at terminal-state readout (``bridge.get_job``) for failed and
    unknown-outcome generic jobs: a delivered native block is validated in
    place; a missing block is synthesized as ``unknown_outcome`` (no result at
    all) or ``not_reported`` (result without the block). Succeeded and running
    jobs are never touched.
    """
    if manifest.get("status") not in ("failed", "unknown_outcome"):
        return
    result = manifest.get("result")
    if isinstance(result, dict) and "failed_model_cleanup" in result:
        result["failed_model_cleanup"] = normalize_receipt(result["failed_model_cleanup"])
        return
    if not isinstance(result, dict):
        manifest["result"] = {"failed_model_cleanup": receipt_unknown_outcome()}
        return
    result["failed_model_cleanup"] = receipt_not_reported()
