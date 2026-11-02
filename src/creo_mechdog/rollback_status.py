"""BUG-096 tail note: explicit rollback outcome for failed terminal jobs.

Failed jobs used to carry only ``rollback_succeeded`` (a boolean).
``false`` covered "never attempted" and "attempted and failed" alike, so a
new model without a checkpoint read exactly like a restore that failed
(BUG-012). This module adds one explicit terminal field and never derives
success from anything but native evidence::

    rollback_status = "not_attempted" | "succeeded" | "failed" | "unconfirmed"

Rules:

- Only failed and unknown-outcome jobs get the field; succeeded, running and
  queued jobs are never touched.
- ``succeeded`` requires ``rollback_succeeded`` to be exactly ``True`` (the
  native tail sets it only after the restored file was regenerated and
  verified against its saved baseline).
- ``failed`` requires a native rollback error (``rollback_code`` or
  ``rollback_message``). The load/verify failure is real evidence, so it is
  not downgraded to "unconfirmed".
- ``not_attempted`` is reported when native recorded no restore at all: the
  job never mutated a checkpointed model, so there was nothing to roll back.
- Everything else - including an unrecognized vocabulary value - is
  ``unconfirmed``. An unreadable outcome is never upgraded to success.

``rollback_succeeded`` keeps its old meaning and is never rewritten here
(BUG-012 stays closed; this module only adds a field), and the field is not
derived from ``failed_model_cleanup``: checkpoint restore and failed-new-model
cleanup are separate domains.
"""

from __future__ import annotations

from typing import Any

ROLLBACK_NOT_ATTEMPTED = "not_attempted"
ROLLBACK_SUCCEEDED = "succeeded"
ROLLBACK_FAILED = "failed"
ROLLBACK_UNCONFIRMED = "unconfirmed"

ROLLBACK_STATUSES = (
    ROLLBACK_NOT_ATTEMPTED,
    ROLLBACK_SUCCEEDED,
    ROLLBACK_FAILED,
    ROLLBACK_UNCONFIRMED,
)

TERMINAL_STATUSES = ("failed", "unknown_outcome")


def derive_rollback_status(result: Any) -> str:
    """Map the native rollback evidence onto the explicit vocabulary."""
    if not isinstance(result, dict):
        return ROLLBACK_UNCONFIRMED
    if result.get("rollback_succeeded") is True:
        return ROLLBACK_SUCCEEDED
    if result.get("rollback_code") is not None or result.get("rollback_message"):
        return ROLLBACK_FAILED
    if result.get("rollback_succeeded") is False:
        return ROLLBACK_NOT_ATTEMPTED
    return ROLLBACK_UNCONFIRMED


def ensure_rollback_status(manifest: dict) -> None:
    """Stamp ``rollback_status`` on a failed or unknown-outcome job result.

    A delivered value is kept when it is in the documented vocabulary and
    replaced with ``unconfirmed`` otherwise, so a malformed receipt can never
    read as a successful restore. Jobs without a result are left alone: there
    is no failure tail to describe.
    """
    if manifest.get("status") not in TERMINAL_STATUSES:
        return
    result = manifest.get("result")
    if not isinstance(result, dict):
        return
    delivered = result.get("rollback_status")
    if delivered in ROLLBACK_STATUSES:
        return
    result["rollback_status"] = (
        derive_rollback_status(result) if delivered is None else ROLLBACK_UNCONFIRMED
    )
