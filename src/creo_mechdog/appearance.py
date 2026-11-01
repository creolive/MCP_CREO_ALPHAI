"""Assembly recolor by part family (FEAT-052).

Paints the components of an MCP-managed single-level assembly at the assembly
component level; source part files keep their exact bytes. Two grouping modes
share one validation path (``creo_recolor_assembly`` and the
``recolor_assembly`` plan operation of ``creo_execute_plan``):

* automatic — omit ``families``: components are grouped by the unique
  ``source_model_id`` of their component binding and the palette keys are
  those source model ids. A component whose binding is missing or ambiguous
  (same label with several sources, or no determinate binding) refuses the
  request and asks for an explicit family table; nothing is ever guessed from
  traversal order or copy names.
* explicit — ``families={family_name: [component label or feature ID]}``:
  family names follow the project label rule. The table must assign every
  checkpoint component exactly once — duplicated or omitted components are
  refused with their identities listed. A table entry that matches no
  component is reported as ``unmatched`` instead of being invented; in plan
  jobs an entry naming a component the same plan creates with
  ``assemble_component`` is refused (only components that already exist
  before the plan runs may be painted).

Colors are RGB triples of finite numbers in 0..1; booleans are refused even
inside lists. Execution (``dry_run=false``) requires a palette covering every
family exactly (extra, missing and unknown keys refuse); a preview
(``dry_run=true``) may omit the palette or use a partial one.

``dry_run`` previews read only persisted registry data — the component
bindings and the verified checkpoint of ``models/<id>/model.json`` — and never
take the Toolkit channel lock, never create a job and never advance the
revision. Preview pages (``limit`` 1-50) fit the 32 KiB response budget and
carry a cursor bound to the revision and the request content (families and
palette fingerprints); registry, revision or request changes invalidate old
cursors. Insufficient persisted state (non-assembly model, missing/pending
checkpoint, no components) refuses with guidance instead of touching Toolkit.

Execution goes through the existing job channel: one job (``job_id`` /
``model_id``), the single Toolkit channel with immediate busy rejection, an
always-saved model and a revision that advances by exactly one on success.
The op payload sent to the native executor is fixed by the FEAT-052
contract::

    {"op": "recolor_assembly",
     "assignments": [{"label": ..., "family": ..., "rgb": [r,g,b]}, ...],
     "families": ["family_name", ...]}

with one resolved assignment per checkpoint component. The native
``recolor`` result block (``painted``, ``unmatched``, ``family_counts``,
``readback_before_save``, ``readback_after_reload``, ``readback_tolerance``,
``readback_all_within_tolerance``, ``component_appearance_baseline``) is
projected here: missing fields stay unknown (null) and are never fabricated.
"""

from __future__ import annotations

import math
from typing import Any

from creo_mechdog import component_identity, model_registry
from creo_mechdog.model_queries import (
    RESPONSE_BUDGET,
    decode_cursor,
    encode_cursor,
    fingerprint,
    serialized_size,
)
from creo_mechdog.schema import validate_recolor_shape

RECOLOR_OP = "recolor_assembly"
PREVIEW_LIMIT_MAX = 50
UNMATCHED_LIMIT = 50
APPEARANCE_STATES = ("present", "absent", "query_failed")
READBACK_FIELDS = ("label", "family", "rgb_requested", "rgb_read", "abs_err", "query_code")
CHECKPOINT_GUIDANCE = (
    "run creo_save_model on the assembly to establish and verify a new checkpoint, then recolor"
)
BASELINE_NOTE = (
    "execution requires a component appearance baseline on every checkpoint component; "
    + CHECKPOINT_GUIDANCE
)
READONLY_NOTE = (
    "dry_run preview only: reads persisted registry data (component bindings and the "
    "verified checkpoint); no Toolkit connection, no job and no revision change. "
    "Executing always saves once and advances the revision by exactly one"
)


# ---------------------------------------------------------------------------
# Persisted registry state: the verified checkpoint and its component bindings.
# ---------------------------------------------------------------------------


def _load_model(model_id: str) -> dict:
    import generic_bridge as general

    return model_registry.read_control(general.model_path(model_id))


def checkpoint_records(model: Any, *, require_baseline: bool) -> list[dict[str, Any]]:
    """Gate and return the verified checkpoint's identity-decorated components.

    Everything is read from persisted registry data only. ``require_baseline``
    additionally refuses checkpoints whose component snapshot predates the
    FEAT-052 ``appearance`` field (execute/plan paths).
    """
    if not isinstance(model, dict) or not model.get("model_id"):
        raise ValueError(
            "creo_recolor_assembly needs an existing MCP-managed assembly model; "
            "create and save the assembly first. No job was created"
        )
    if model.get("model_type", "part") != "assembly":
        raise ValueError(
            "creo_recolor_assembly paints MCP-managed single-level assemblies only; "
            f"this model is a {model.get('model_type', 'part')}. No job was created"
        )
    if model.get("pending_job") or model.get("recovery_pending"):
        raise ValueError(
            "The verified checkpoint is not usable while a job is pending or recovery is "
            "outstanding (pending_job/recovery_pending); poll creo_get_job or finish "
            "creo_reconcile_model first. No job was created"
        )
    if model.get("status") != "ready":
        raise ValueError(
            f"Model status is {model.get('status')!r}, not 'ready'; inspect its last job "
            "with creo_get_job or creo_reconcile_model before recoloring. No job was created"
        )
    if not model.get("part_file"):
        raise ValueError(
            "No verified saved checkpoint exists for this assembly (no saved file); "
            + CHECKPOINT_GUIDANCE
            + ". No job was created"
        )
    inspection = model_registry.inspection_of(model)
    components = (inspection or {}).get("components")
    if not isinstance(components, list) or not components:
        raise ValueError(
            "The verified checkpoint lists no assembly components; "
            + CHECKPOINT_GUIDANCE
            + " on an assembly with components. No job was created"
        )
    ids = [
        record.get("feature_id")
        for record in components
        if isinstance(record, dict) and type(record.get("feature_id")) is int
    ]
    if len(ids) != len(set(ids)):
        raise ValueError(
            "The verified checkpoint lists duplicated component feature_ids; "
            + CHECKPOINT_GUIDANCE
            + ". No job was created"
        )
    aliases = model_registry.aliases_of(model)
    decorated = component_identity.decorate_component_records(model, components, aliases)
    if require_baseline:
        missing = [record for record in decorated if "appearance" not in record]
        if missing:
            identities = [
                record.get("label") or record.get("feature_id") for record in missing[:20]
            ]
            raise ValueError(
                "The registered checkpoint predates component appearance baselines (its "
                f"component snapshot has no appearance field on {len(missing)} component(s): "
                f"{identities}); " + CHECKPOINT_GUIDANCE + ". No job was created"
            )
    return decorated


def appearance_baseline_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Informational baseline view for previews; execution enforces it separately."""
    missing = [record for record in records if "appearance" not in record]
    return {
        "present": not missing,
        "missing_count": len(missing),
        "missing_labels": [
            record.get("label") or record.get("feature_id") for record in missing[:UNMATCHED_LIMIT]
        ],
        "note": BASELINE_NOTE if missing else "every checkpoint component carries a baseline",
    }


# ---------------------------------------------------------------------------
# Grouping: automatic by source_model_id, or one explicit family table.
# ---------------------------------------------------------------------------


def _unique_source(record: dict[str, Any]) -> str | None:
    """The single source_model_id every binding of this component agrees on.

    A component with several labels still groups automatically when all of its
    bindings name the same non-null source; missing or conflicting sources are
    indeterminate and never guessed.
    """
    bindings = [entry for entry in (record.get("bindings") or []) if isinstance(entry, dict)]
    sources = {entry.get("source_model_id") for entry in bindings}
    if len(sources) == 1:
        (source,) = sources
        return source if isinstance(source, str) else None
    return None


def _member_label(record: dict[str, Any]) -> Any:
    label = record.get("label")
    if isinstance(label, str):
        return label
    labels = sorted(record.get("labels") or [])
    return labels[0] if labels else None


def resolve_grouping(
    records: list[dict[str, Any]],
    *,
    families: dict[str, list[str | int]] | None,
    palette: dict[str, list[float]] | None,
    writing: bool,
    plan_created: frozenset[str] | set[str] = frozenset(),
) -> dict[str, Any]:
    """Group checkpoint components into families and build the native payload.

    ``families``/``palette`` must already be shape-validated. ``writing``
    enforces the complete-palette rule; a preview may omit or partially fill
    the palette. ``plan_created`` holds labels created by ``assemble_component``
    operations of the same plan and can never be selected.
    """
    unmatched: list[dict[str, Any]] = []
    if families is None:
        mode = "auto"
        problems = [
            {
                "feature_id": record.get("feature_id"),
                "labels": record.get("labels"),
                "label_state": record.get("label_state"),
                "source_model_id": record.get("source_model_id"),
            }
            for record in records
            if _unique_source(record) is None
        ]
        if problems:
            shown = "; ".join(
                f"feature {p['feature_id']} labels={p['labels']} state={p['label_state']}"
                for p in problems[:20]
            )
            raise ValueError(
                "Automatic family grouping needs one unique source_model_id across each "
                f"component's bindings; {len(problems)} component(s) have missing or "
                f"conflicting sources: {shown}. Pass an explicit families table instead; "
                "groups are never guessed from traversal order or copy names"
            )
        grouped: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            grouped.setdefault(_unique_source(record), []).append(record)
        family_keys = sorted(grouped)
        matched_by = {record["feature_id"]: _member_label(record) for record in records}
    else:
        mode = "explicit"
        family_keys = list(families)
        by_id: dict[Any, dict[str, Any]] = {}
        by_label: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            by_id.setdefault(record.get("feature_id"), record)
            for label in record.get("labels") or []:
                by_label.setdefault(label, []).append(record)
        grouped = {name: [] for name in family_keys}
        matched_by = {}
        owners: dict[Any, str] = {}
        for name in family_keys:
            for ref in families[name]:
                if isinstance(ref, int):
                    record = by_id.get(ref)
                else:
                    hits = by_label.get(ref, [])
                    if len(hits) > 1:
                        raise ValueError(
                            f"family {name!r} entry {ref!r} matches {len(hits)} components "
                            f"(feature IDs {sorted(h.get('feature_id') for h in hits)}); a "
                            "label is not identity here - select these components by feature ID"
                        )
                    record = hits[0] if hits else None
                if record is None:
                    if ref in plan_created:
                        raise ValueError(
                            "recolor_assembly only selects components that already exist "
                            f"before the plan runs; {ref!r} is created by an "
                            "assemble_component operation inside the same plan"
                        )
                    unmatched.append({"family": name, "ref": ref})
                    continue
                feature_id = record.get("feature_id")
                if feature_id in owners:
                    raise ValueError(
                        "family table assigns one component to several families: feature "
                        f"{feature_id} appears in {owners[feature_id]!r} and {name!r}; "
                        "duplicated components are refused"
                    )
                owners[feature_id] = name
                matched_by[feature_id] = ref
                grouped[name].append(record)
        missing = [record for record in records if record.get("feature_id") not in owners]
        if missing:
            shown = "; ".join(
                f"feature {record.get('feature_id')} labels={record.get('labels')}"
                for record in missing[:20]
            )
            raise ValueError(
                f"family table omits {len(missing)} component(s): {shown}; the table must "
                "cover every checkpoint component exactly once"
            )
    family_counts = {name: len(grouped[name]) for name in family_keys}
    if palette is not None:
        unknown = [key for key in palette if key not in set(family_keys)]
        if unknown:
            raise ValueError(
                f"palette keys do not name any family: {sorted(unknown)}; "
                f"known families: {family_keys}"
            )
        if writing:
            missing_colors = [name for name in family_keys if name not in palette]
            if missing_colors:
                raise ValueError(
                    "Executing requires a palette covering every family exactly; "
                    f"missing colors for: {missing_colors}"
                )
    elif writing:
        raise ValueError(
            "Executing recolor_assembly requires a palette covering every family exactly; "
            "dry_run=true may omit it"
        )
    rows = []
    assignments = []
    for name in family_keys:
        members = []
        for record in grouped[name]:
            feature_id = record.get("feature_id")
            ref = matched_by[feature_id]
            members.append(
                {
                    "label": _member_label(record),
                    "feature_id": feature_id,
                    "source_model_id": _unique_source(record),
                    "matched_by": ref,
                }
            )
            assignments.append(
                {
                    "label": ref,
                    "family": name,
                    "rgb": palette[name] if palette is not None else None,
                    "feature_id": feature_id,
                }
            )
        rows.append(
            {
                "family": name,
                "count": len(members),
                "rgb": palette[name] if palette is not None else None,
                "members": members,
            }
        )
    return {
        "mode": mode,
        "family_keys": family_keys,
        "family_counts": family_counts,
        "groups": rows,
        "unmatched": unmatched,
        "unmatched_count": len(unmatched),
        "assignments": assignments,
    }


# ---------------------------------------------------------------------------
# Preview (dry_run): registry-only, paginated, no Toolkit and no job.
# ---------------------------------------------------------------------------


def preview_recolor(
    model_id: str,
    expected_revision: int,
    palette: dict[str, Any] | None = None,
    families: dict[str, Any] | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Read-only grouping preview over persisted registry data; no job is created."""
    if isinstance(limit, bool) or type(limit) is not int or not 1 <= limit <= PREVIEW_LIMIT_MAX:
        raise ValueError("limit must be 1-50")
    if isinstance(expected_revision, bool) or type(expected_revision) is not int:
        raise ValueError("expected_revision must be a nonnegative integer")
    families, palette = validate_recolor_shape(families, palette)
    page = decode_cursor(cursor)
    model = _load_model(model_id)
    revision = model.get("revision")
    if expected_revision != revision:
        raise ValueError(f"Stale revision: current model revision is {revision}")
    records = checkpoint_records(model, require_baseline=False)
    grouping = resolve_grouping(records, families=families, palette=palette, writing=False)
    rows = grouping["groups"]
    unmatched = grouping["unmatched"]
    identity = {
        "kind": "recolor_preview",
        "model_id": model_id,
        "revision": revision,
        "request": fingerprint({"families": families, "palette": palette}),
        "snapshot": fingerprint(
            {
                "rows": rows,
                "family_counts": grouping["family_counts"],
                "unmatched": unmatched,
            }
        ),
    }
    if page is not None:
        for key, value in identity.items():
            if page.get(key) != value:
                raise ValueError(
                    "Preview state changed (revision, registry data or request content); "
                    "restart without cursor"
                )
        offset = page["offset"]
    else:
        offset = 0
    if type(offset) is not int or offset < 0 or offset > len(rows):
        raise ValueError("Invalid preview cursor offset")
    window = rows[offset : offset + limit]
    response = {
        "model_id": model_id,
        "revision": revision,
        "expected_revision": expected_revision,
        "mode": grouping["mode"],
        "dry_run": True,
        "component_total": len(records),
        "families_total": len(rows),
        "family_counts": grouping["family_counts"],
        "unmatched_count": grouping["unmatched_count"],
        "unmatched_truncated": grouping["unmatched_count"] > UNMATCHED_LIMIT,
        "unmatched": unmatched[:UNMATCHED_LIMIT],
        "appearance_baseline": appearance_baseline_report(records),
        "groups": window,
        "limit": limit,
        "offset": offset,
        "returned_count": 0,
        "complete": False,
        "next_cursor": None,
        "response_budget_bytes": RESPONSE_BUDGET,
        "readonly_note": READONLY_NOTE,
    }

    def refresh() -> None:
        more = offset + len(window) < len(rows)
        response["returned_count"] = len(window)
        response["complete"] = not more
        response["next_cursor"] = (
            encode_cursor({**identity, "offset": offset + len(window)}) if more else None
        )

    refresh()
    while serialized_size(response) > RESPONSE_BUDGET:
        if len(window) > 1:
            window.pop()
            refresh()
        else:
            raise ValueError(
                "One family group exceeds the 32 KiB preview page budget; preview a "
                "narrower families subset"
            )
    return response


# ---------------------------------------------------------------------------
# Execution: shared admission under the channel lock, then the job channel.
# ---------------------------------------------------------------------------


def submit_recolor(
    model_id: str,
    expected_revision: int,
    palette: dict[str, Any] | None = None,
    families: dict[str, Any] | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Submit one recolor job through the existing job channel.

    Pagination parameters belong to dry_run previews only and are refused
    here. The returned manifest carries job_id/model_id; poll with
    ``creo_get_job``. Busy contention rejects immediately and never queues.
    """
    if cursor is not None:
        raise ValueError("cursor is only for dry_run previews; drop it to execute")
    if limit != 50:
        raise ValueError("limit is only for dry_run previews; drop it to execute")
    families, palette = validate_recolor_shape(families, palette)
    if palette is None:
        raise ValueError(
            "Executing recolor_assembly requires a palette covering every family exactly; "
            "dry_run=true may omit it"
        )
    import generic_bridge as general

    return general.submit(
        [{"op": RECOLOR_OP, "palette": palette, "families": families}],
        model_id=model_id,
        expected_revision=expected_revision,
    )


def prepare_recolor_operations(
    model: dict[str, Any] | None, operations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validate and rewrite every recolor op into its native payload.

    Called by ``generic_bridge.submit`` under the Toolkit channel lock before
    a job exists (the same admission slot as ``feature_state.validate_plan``),
    so the standalone tool and ``creo_execute_plan`` share one validation.
    A refusal creates no job and no model change. Each recolor operation
    becomes ``{"op", "assignments", "families"}`` per the FEAT-052 contract.
    """
    recolor_ops = [
        (index, operation)
        for index, operation in enumerate(operations)
        if isinstance(operation, dict) and operation.get("op") == RECOLOR_OP
    ]
    if not recolor_ops:
        return operations
    plan_created = {
        operation.get("label")
        for operation in operations
        if isinstance(operation, dict) and operation.get("op") == "assemble_component"
    }
    records = checkpoint_records(model, require_baseline=True)
    for index, operation in recolor_ops:
        families, palette = validate_recolor_shape(
            operation.get("families"), operation.get("palette")
        )
        if palette is None:
            raise ValueError(
                f"operations[{index}]: recolor_assembly requires a palette covering every "
                "family exactly; dry_run=true may omit it"
            )
        grouping = resolve_grouping(
            records, families=families, palette=palette, writing=True, plan_created=plan_created
        )
        operations[index] = {
            "op": RECOLOR_OP,
            "assignments": grouping["assignments"],
            "families": grouping["family_keys"],
        }
    return operations


# ---------------------------------------------------------------------------
# Result projection: full block and compact counts/verification summary.
# ---------------------------------------------------------------------------


def _identity_value(value: Any) -> Any:
    return value if isinstance(value, (str, int)) and not isinstance(value, bool) else None


def _finite_rgb(value: Any) -> list[float] | None:
    if (
        isinstance(value, list)
        and len(value) == 3
        and all(type(item) in (int, float) and math.isfinite(item) for item in value)
    ):
        return [float(item) for item in value]
    return None


def _unknown_recolor() -> dict[str, Any]:
    return {
        "painted": None,
        "unmatched": None,
        "family_counts": None,
        "readback_before_save": None,
        "readback_after_reload": None,
        "readback_tolerance": None,
        "readback_all_within_tolerance": None,
        "component_appearance_baseline": None,
    }


def _readback_entry(entry: Any) -> dict[str, Any]:
    source = entry if isinstance(entry, dict) else {}
    row: dict[str, Any] = {}
    for field in READBACK_FIELDS:
        value = source.get(field)
        if field in ("rgb_requested", "rgb_read"):
            row[field] = _finite_rgb(value)
        elif field == "abs_err":
            row[field] = (
                float(value) if type(value) in (int, float) and math.isfinite(value) else None
            )
        elif field == "query_code":
            row[field] = value if type(value) is int else None
        else:
            row[field] = _identity_value(value)
    return row


def _baseline_entry(entry: Any) -> dict[str, Any]:
    source = entry if isinstance(entry, dict) else {}
    appearance = source.get("appearance")
    appearance = appearance if isinstance(appearance, dict) else {}
    state = appearance.get("state")
    query_code = appearance.get("query_code")
    return {
        "label": _identity_value(source.get("label")),
        "appearance": {
            "state": state if state in APPEARANCE_STATES else None,
            "rgb": _finite_rgb(appearance.get("rgb")),
            "query_code": query_code if type(query_code) is int else None,
        },
    }


def project_recolor(block: Any) -> dict[str, Any]:
    """Normalize the native ``recolor`` block; missing fields stay unknown.

    Values are only ever the executor's own report: a missing field is
    projected as null (unknown) and never backfilled from the request or
    recomputed from other fields.
    """
    if not isinstance(block, dict):
        return _unknown_recolor()
    out = _unknown_recolor()
    painted = block.get("painted")
    out["painted"] = painted if type(painted) is int and painted >= 0 else None
    unmatched = block.get("unmatched")
    out["unmatched"] = list(unmatched) if isinstance(unmatched, list) else None
    counts = block.get("family_counts")
    out["family_counts"] = dict(counts) if isinstance(counts, dict) else None
    for field in ("readback_before_save", "readback_after_reload"):
        entries = block.get(field)
        out[field] = (
            [_readback_entry(entry) for entry in entries] if isinstance(entries, list) else None
        )
    tolerance = block.get("readback_tolerance")
    out["readback_tolerance"] = (
        float(tolerance) if type(tolerance) in (int, float) and math.isfinite(tolerance) else None
    )
    within = block.get("readback_all_within_tolerance")
    out["readback_all_within_tolerance"] = within if isinstance(within, bool) else None
    baseline = block.get("component_appearance_baseline")
    out["component_appearance_baseline"] = (
        [_baseline_entry(entry) for entry in baseline] if isinstance(baseline, list) else None
    )
    return out


def annotate_recolor(result: dict[str, Any]) -> dict[str, Any]:
    """Project the ``recolor`` block on an accepted native result (T02 style).

    A result without a recolor block keeps it absent; nothing is fabricated.
    """
    if isinstance(result, dict) and "recolor" in result:
        result["recolor"] = project_recolor(result["recolor"])
    return result


def compact_recolor(block: Any) -> dict[str, Any]:
    """Counts and verification status only (compact job projection)."""

    def count(key: str) -> int | None:
        value = block.get(key) if isinstance(block, dict) else None
        return len(value) if isinstance(value, list) else None

    source = block if isinstance(block, dict) else {}
    unmatched = source.get("unmatched")
    counts = source.get("family_counts")
    return {
        "painted": source.get("painted"),
        "unmatched_count": len(unmatched) if isinstance(unmatched, list) else None,
        "family_counts": dict(counts) if isinstance(counts, dict) else None,
        "readback_before_save_count": count("readback_before_save"),
        "readback_after_reload_count": count("readback_after_reload"),
        "readback_tolerance": source.get("readback_tolerance"),
        "readback_all_within_tolerance": source.get("readback_all_within_tolerance"),
        "component_appearance_baseline_count": count("component_appearance_baseline"),
    }
