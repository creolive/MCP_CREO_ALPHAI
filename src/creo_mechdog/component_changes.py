"""Bounded component change summary for assembly jobs (FEAT-008, batch 2 stage 2).

A job that targets assembly components reports which component changes were
actually committed. Every value comes from the native operation results, the
managed aliases or the last verified inspection; this module never simulates
geometry. Three statuses keep failure modes honest:

* ``committed`` — the job succeeded; entries carry the real native feature
  identities from the verified result.
* ``rolled_back`` — the job failed after rollback; entries list the requested
  component operations only, and nothing is reported as effective.
* ``unknown_outcome`` — the result is unconfirmed; no change is reported and
  the note points at the retained protection.

The output rides on the existing job result next to ``preview_file``; no new
batch-assembly tool is introduced.
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


def _transform_of(feature_id: Any, inspection: dict | None) -> Any:
    if not inspection:
        return None
    for component in inspection.get("components") or []:
        if component.get("feature_id") == feature_id:
            return component.get("transform")
    return None


def summarize(
    operations: list[dict],
    *,
    job_status: str,
    prior_aliases: dict | None = None,
    prior_inspection: dict | None = None,
    result_aliases: dict | None = None,
    result_inspection: dict | None = None,
) -> dict | None:
    """Build the bounded change summary, or None when no component was targeted."""
    targeted = [op for op in operations if op.get("op") in CHANGE_OPS]
    if not targeted:
        return None
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
    prior_aliases = prior_aliases or {}
    result_aliases = result_aliases or {}
    if job_status != "succeeded":
        return {
            "status": "rolled_back",
            "changes": [
                {
                    "op": CHANGE_OPS[op["op"]],
                    "label": op.get("label")
                    if op["op"] == "assemble_component"
                    else _label_of(op.get("component"), prior_aliases),
                }
                for op in targeted
            ],
            "note": "The job failed and rolled back; none of these changes took effect.",
        }
    changes = []
    for op in targeted:
        kind = CHANGE_OPS[op["op"]]
        if op["op"] == "assemble_component":
            label = op.get("label")
            entry = result_aliases.get(label) or {}
            change = {
                "op": kind,
                "label": label,
                "feature_id": entry.get("feature_id"),
                "source_model_id": op.get("source_model_id"),
                "source_revision": entry.get("source_revision"),
            }
        else:
            label = _label_of(op.get("component"), prior_aliases)
            feature_id = prior_aliases.get(label, {}).get("feature_id") if label else None
            change = {"op": kind, "label": label, "feature_id": feature_id}
            if kind == "moved":
                change["from"] = _transform_of(feature_id, prior_inspection)
                change["to"] = _transform_of(feature_id, result_inspection)
        changes.append(change)
    return {"status": "committed", "changes": changes}
