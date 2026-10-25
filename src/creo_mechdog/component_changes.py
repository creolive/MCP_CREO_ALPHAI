"""Bounded component change summary for assembly jobs (FEAT-008, batch 2).

A job that targets assembly components reports the NET change between the
verified pre-job state and the verified post-job state. Every value comes
from the native operation results, the managed aliases or the last verified
inspection; this module never simulates geometry. Statuses stay honest about
what the native side actually confirmed:

* ``committed`` — the job succeeded; entries are the net verified diff:
  components compared by their real native ``feature_id``. A label present
  only after the job is ``added`` (with the NEW id from the result aliases);
  a label present only before the job is ``removed`` (with the PRIOR id);
  a label on both sides with the SAME id is ``moved``/``constraints_changed``
  only when the queried transforms/constraints actually differ; a label on
  both sides with DIFFERENT ids is a reinsert and reports ``removed`` (old
  id) plus ``added`` (new id) — identities are never fabricated from the
  final aliases of a component that was removed mid-job. Sequences such as
  add-then-move collapse to the single ``added`` entry; add-then-remove
  leaves no net component change. A committed summary without the verified
  result aliases raises, so callers degrade to ``unavailable`` instead of
  guessing.
* ``rolled_back`` — ONLY when the native result confirms ``rollback_succeeded``
  (the saved checkpoint was restored and verified). Entries list the requested
  component operations only, and nothing is reported as effective.
* ``no_effect`` — the job never mutated the model: rejected before execution
  (channel busy, worker not started) or the native preflight refused before
  any mutation (``model_unchanged``). Nothing took effect and no rollback was
  needed or claimed.
* ``unknown_outcome`` — the effect is unconfirmed: either the job outcome
  itself is unconfirmed, or the job failed after native execution without a
  confirmed rollback. No change is reported and the note points at the
  retained protection.

The output rides on the existing job result next to ``preview_file``; no new
batch-assembly tool is introduced. The summary is auxiliary: a summary
failure is reported as ``unavailable`` and must never change the confirmed
terminal state of the job.
"""

from __future__ import annotations

from typing import Any

CHANGE_OPS = {
    "assemble_component": "added",
    "component_placement": "moved",
    "component_constraints": "constraints_changed",
    "remove_component": "removed",
}


def _label_of(component: Any, prior_aliases: dict) -> Any:
    """Resolve a component reference (managed label or feature id)."""
    if isinstance(component, str):
        return component
    for label, alias in prior_aliases.items():
        if alias.get("feature_id") == component:
            return label
    return None


def _status_for(job_status: str, rollback: dict | None, executed: bool) -> tuple[str, str]:
    """Map the terminal state plus native evidence to an honest summary status."""
    if job_status == "succeeded":
        return "committed", "Changes below were committed by the job."
    evidence = rollback if isinstance(rollback, dict) else {}
    if evidence.get("rollback_succeeded") is True:
        return (
            "rolled_back",
            "The job failed after native execution; the saved checkpoint was "
            "restored and verified (rollback_succeeded). None of the requested "
            "changes took effect.",
        )
    if evidence.get("model_unchanged") is True:
        return (
            "no_effect",
            "The job failed before any mutation (model_unchanged); the model is "
            "unchanged and no rollback was needed.",
        )
    if executed:
        return (
            "unknown_outcome",
            "The job failed after native execution but rollback is unconfirmed; "
            "do not treat any requested change as effective. Protection is "
            "retained; inspect before any recovery decision.",
        )
    return (
        "no_effect",
        "The job never executed natively (rejected or worker not started); no "
        "changes were attempted and none took effect.",
    )


def _added_entry(label: Any, result_entry: dict, added_sources: dict) -> dict:
    op = added_sources.get(label, {})
    return {
        "op": "added",
        "label": label,
        "feature_id": result_entry.get("feature_id"),
        "source_model_id": result_entry.get("source_model_id") or op.get("source_model_id"),
        "source_revision": result_entry.get("source_revision"),
    }


def _committed_changes(
    targeted: list[dict],
    prior_aliases: dict | None,
    prior_inspection: dict | None,
    result_aliases: dict | None,
    result_inspection: dict | None,
) -> dict:
    """Net verified diff between the pre-job and post-job component state."""
    prior_aliases = prior_aliases or {}
    if result_aliases is None:
        # The verified post-state is unavailable; identities must never be
        # invented, so the caller degrades the whole summary to unavailable.
        raise ValueError("committed component summary requires the verified result aliases")
    added_sources = {op.get("label"): op for op in targeted if op["op"] == "assemble_component"}
    prior_components = {
        component.get("feature_id"): component
        for component in (prior_inspection or {}).get("components") or []
    }
    result_components = {
        component.get("feature_id"): component
        for component in (result_inspection or {}).get("components") or []
    }
    changes = []
    for label in sorted(set(prior_aliases) | set(result_aliases)):
        prior_entry = prior_aliases.get(label) or {}
        result_entry = result_aliases.get(label) or {}
        prior_id = prior_entry.get("feature_id")
        result_id = result_entry.get("feature_id")
        if result_entry and not prior_entry:
            changes.append(_added_entry(label, result_entry, added_sources))
            continue
        if prior_entry and not result_entry:
            changes.append({"op": "removed", "label": label, "feature_id": prior_id})
            continue
        # Same label on both sides: only a shared real feature id authorizes
        # move/constraint comparison; a different id is a reinsert.
        if prior_id is None or prior_id != result_id:
            changes.append({"op": "removed", "label": label, "feature_id": prior_id})
            changes.append(_added_entry(label, result_entry, added_sources))
            continue
        before = prior_components.get(prior_id) or {}
        after = result_components.get(result_id) or {}
        if before.get("transform") is not None and before.get("transform") != after.get(
            "transform"
        ):
            changes.append(
                {
                    "op": "moved",
                    "label": label,
                    "feature_id": prior_id,
                    "from": before.get("transform"),
                    "to": after.get("transform"),
                }
            )
        if "constraints" in before and before.get("constraints") != after.get("constraints"):
            changes.append({"op": "constraints_changed", "label": label, "feature_id": prior_id})
    return {"status": "committed", "changes": changes}


def summarize(
    operations: list[dict],
    *,
    job_status: str,
    rollback: dict | None = None,
    executed: bool | None = None,
    prior_aliases: dict | None = None,
    prior_inspection: dict | None = None,
    result_aliases: dict | None = None,
    result_inspection: dict | None = None,
) -> dict | None:
    """Build the bounded change summary, or None when no component was targeted."""
    targeted = [op for op in operations if op.get("op") in CHANGE_OPS]
    if not targeted:
        return None
    if executed is None:
        # Callers that predate the evidence plumbing only ever report the
        # terminal succeeded state honestly; anything else stays unconfirmed.
        executed = job_status == "succeeded"
    if job_status == "unknown_outcome":
        return {
            "status": "unknown_outcome",
            "changes": [],
            "note": (
                "Outcome unconfirmed; protection retained. Do not treat any "
                "requested component operation as effective; poll the job and "
                "inspect before any recovery decision."
            ),
        }
    status, note = _status_for(job_status, rollback, executed)
    if status in ("rolled_back",):
        return {
            "status": status,
            "changes": [
                {
                    "op": CHANGE_OPS[op["op"]],
                    "label": op.get("label")
                    if op["op"] == "assemble_component"
                    else _label_of(op.get("component"), prior_aliases or {}),
                }
                for op in targeted
            ],
            "note": note,
        }
    if status != "committed":
        return {"status": status, "changes": [], "note": note}
    return _committed_changes(
        targeted, prior_aliases, prior_inspection, result_aliases, result_inspection
    )


def unavailable(exc: BaseException) -> dict:
    """Explicit diagnostic used when summary construction itself fails.

    The job terminal state (succeeded/failed/unknown_outcome) remains
    authoritative; this marker only says the auxiliary summary could not be
    produced and must never rewrite that state.
    """
    return {
        "status": "unavailable",
        "changes": [],
        "error": f"{type(exc).__name__}: {exc}",
        "note": (
            "Component change summary unavailable; the job terminal state and "
            "native result above remain authoritative."
        ),
    }
