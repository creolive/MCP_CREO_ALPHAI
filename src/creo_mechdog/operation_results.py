"""Terminal operation result projection shared by native and job views (T02).

The native executor publishes one terminal record per requested operation with
a zero-based ``index``, an ``execution_status`` and an ``effect_status``. This
module keeps the persisted job result on the same contract: it only fills the
two status fields for records that predate the native change (legacy jobs and
synthetic fixtures) and never invents records or upgrades unknown outcomes.

Existing ``succeeded`` stays a report of the execution fact. It never implies
that the transaction committed; ``effect_status`` carries that meaning.
"""

from __future__ import annotations

import math
from typing import Any

EXECUTION_STATUSES = ("succeeded", "failed", "not_executed", "unknown")
EFFECT_STATUSES = ("committed", "rolled_back", "no_effect", "unknown")

# ---------------------------------------------------------------------------
# FEAT-008 / BUG-088 (Q13): one bounded-summary contract for compact results.
# ---------------------------------------------------------------------------

#: Sample cap shared with the existing diagnostics contract (Q02
#: ``geometry_deviation`` and Q06 ``feature_errors`` both cap samples at 20).
SAMPLE_LIMIT = 20

#: Status fields kept on every compact operation record. The budget trim in
#: ``enforce_compact_budget`` never removes them, so a failure keeps its
#: reason beside the terminal state.
PROTECTED_OPERATION_KEYS = (
    "op",
    "index",
    "label",
    "succeeded",
    "execution_status",
    "effect_status",
    "unchanged",
    "message",
)

#: Failure diagnostics kept in full on the failed record itself.
FAILED_EVIDENCE_KEYS = ("feature_errors", "failed_stage", "failed_toolkit_call")


def bounded_entries(items: list, *, limit: int = SAMPLE_LIMIT) -> dict[str, Any]:
    """Project a list as the unified ``{total, truncated, sample}`` summary."""
    return {
        "total": len(items),
        "truncated": len(items) > limit,
        "sample": list(items[:limit]),
    }


def _bounded_block(block: dict[str, Any], limit: int) -> dict[str, Any]:
    """Re-cap an existing diagnostics block without inventing missing facts.

    The producer's ``total`` is preserved; ``truncated`` only ever turns true,
    and a missing total stays missing when the producer never reported one.
    """
    out = dict(block)
    raw = block.get("sample")
    if isinstance(raw, list) and len(raw) > limit:
        out["sample"] = list(raw[:limit])
        out["truncated"] = True
    return out


def bounded_summary(value: Any, *, limit: int = SAMPLE_LIMIT) -> Any:
    """Project any compact value through the shared bounded-summary contract.

    - lists longer than ``limit`` become ``{total, truncated, sample}`` blocks;
    - dicts already carrying a ``sample`` list (``geometry_deviation``,
      ``feature_errors``, ``failed_model_cleanup`` detail and future
      color/surface receipts) keep their shape and are only re-capped
      defensively;
    - other containers get the same treatment for nested lists;
    - scalars and lists at or below the limit pass through unchanged, so
      existing compact shapes stay byte-identical until a sample overflows.

    Failure reasons, revision, rollback and save/reload evidence are scalars
    and are never touched here.
    """
    if isinstance(value, list):
        return bounded_entries(value, limit=limit) if len(value) > limit else list(value)
    if isinstance(value, dict):
        if isinstance(value.get("sample"), list):
            return _bounded_block(value, limit)
        return {key: bounded_summary(item, limit=limit) for key, item in value.items()}
    return value


def _execution_counts(operations: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for operation in operations:
        status = (
            str(operation.get("execution_status")) if isinstance(operation, dict) else "unknown"
        )
        counts[status] = counts.get(status, 0) + 1
    return counts


def _status_core(record: dict[str, Any], *, failed: bool) -> dict[str, Any]:
    keys = PROTECTED_OPERATION_KEYS + (FAILED_EVIDENCE_KEYS if failed else ())
    core = {key: record[key] for key in keys if key in record}
    core["detail_truncated"] = True
    return core


def enforce_compact_budget(summary: dict[str, Any], *, budget: int | None = None) -> dict[str, Any]:
    """Bound one compact job summary to the shared response budget.

    A summary that already fits is returned untouched. Over budget the
    optional detail is removed in stages and every cut carries its markers:

    1. the operation records are capped at ``SAMPLE_LIMIT`` plus the failed
       record (``operations_total`` / ``operations_truncated`` /
       ``operations_status_counts`` record the population);
    2. optional detail fields are dropped from the kept records, the failed
       record last (``detail_truncated`` marks each stripped record).

    Failure reasons, revision, rollback and save/reload evidence are never
    cut. If that evidence alone still exceeds the budget the summary reports
    the real sizes in ``result_budget`` instead of hiding it.
    """
    from creo_mechdog.model_queries import RESPONSE_BUDGET, serialized_size

    limit = RESPONSE_BUDGET if budget is None else budget
    if serialized_size(summary) <= limit:
        return summary
    result = summary.get("result")
    operations = result.get("operations") if isinstance(result, dict) else None
    if not isinstance(operations, list) or not operations:
        # Everything list-shaped is already sample-bounded; whatever is left
        # is protected evidence or a single oversized block. Report honestly.
        if isinstance(result, dict):
            result["result_budget"] = {
                "budget_bytes": limit,
                "serialized_bytes": serialized_size(summary),
                "exceeded": True,
                "note": (
                    "protected failure/rollback/save evidence or one oversized block "
                    "kept in full; use detail=full sections for the rest"
                ),
            }
        return summary
    failed_index = result.get("failed_operation_index")
    failed_index = failed_index if isinstance(failed_index, int) else None
    if failed_index is not None and not 0 <= failed_index < len(operations):
        failed_index = None
    # Stage 1: cap the detailed records at SAMPLE_LIMIT plus the failed record.
    keep = list(operations[:SAMPLE_LIMIT])
    if failed_index is not None and failed_index >= SAMPLE_LIMIT:
        keep.append(operations[failed_index])
    result["operations_total"] = len(operations)
    result["operations_truncated"] = len(keep) < len(operations)
    result["operations_status_counts"] = _execution_counts(operations)
    result["operations"] = keep
    if serialized_size(summary) <= limit:
        return summary
    # Stage 2: drop optional detail from the kept records, failed record last.
    for position in range(len(keep) - 1, -1, -1):
        record = keep[position]
        if not isinstance(record, dict):
            continue
        if all(key in PROTECTED_OPERATION_KEYS for key in record):
            continue
        is_failed = failed_index is not None and operations[failed_index] is record
        keep[position] = _status_core(record, failed=is_failed)
        if serialized_size(summary) <= limit:
            return summary
    # Stage 3: protected evidence alone exceeds the budget. Keep it whole.
    result["result_budget"] = {
        "budget_bytes": limit,
        "serialized_bytes": serialized_size(summary),
        "exceeded": True,
        "note": (
            "protected failure/rollback/save evidence kept in full; "
            "use detail=full sections for the rest"
        ),
    }
    return summary


def _execution_status(op: dict[str, Any], job_status: str, failed_index: int | None) -> str:
    if op.get("execution_status") in EXECUTION_STATUSES:
        return str(op["execution_status"])
    # Legacy record: derive only what the retained evidence states. A failed
    # operation index marks exactly that input; everything else stays unknown
    # unless the whole job succeeded.
    index = op.get("index")
    if op.get("succeeded") is True:
        return "succeeded"
    if isinstance(index, int) and failed_index is not None and index == failed_index:
        return "failed"
    if job_status == "succeeded":
        return "succeeded"
    return "unknown"


def _effect_status(
    op: dict[str, Any],
    execution: str,
    job_status: str,
    rollback_confirmed: bool,
    readonly: bool,
) -> str:
    if op.get("effect_status") in EFFECT_STATUSES:
        return str(op["effect_status"])
    if execution == "not_executed":
        return "no_effect"
    if job_status == "succeeded" and execution == "succeeded":
        # A successful writable plan saved, reloaded and advanced one revision;
        # a read-only plan confirms that the model itself was not written.
        return "no_effect" if readonly else "committed"
    if rollback_confirmed and execution in ("succeeded", "failed"):
        return "rolled_back"
    return "unknown"


def normalize_operations(
    operations: Any,
    *,
    job_status: str,
    rollback_confirmed: bool = False,
    readonly: bool = False,
    failed_index: int | None = None,
) -> list[dict[str, Any]]:
    """Fill index and the two status fields without fabricating outcomes.

    ``operations`` must already be the native record list. The function never
    adds or drops records, so a job that never produced operation results keeps
    an empty list rather than a synthetic success trail.
    """
    if not isinstance(operations, list):
        return []
    normalized: list[dict[str, Any]] = []
    for position, raw in enumerate(operations):
        op = dict(raw) if isinstance(raw, dict) else {}
        if not isinstance(op.get("index"), int):
            op["index"] = position
        execution = _execution_status(op, job_status, failed_index)
        op["execution_status"] = execution
        op["effect_status"] = _effect_status(
            op, execution, job_status, rollback_confirmed, readonly
        )
        normalized.append(op)
    return normalized


def annotate_native_result(
    result: dict[str, Any], *, readonly: bool, inputs: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Normalize an accepted native result before it is persisted on the job."""
    operations = result.get("operations")
    if not isinstance(operations, list):
        # No operation record exists (for example the worker never delivered a
        # result). Do not synthesize executed outcomes; leave the field absent.
        return result
    failed_index = result.get("failed_operation_index")
    result["operations"] = normalize_operations(
        operations,
        job_status="succeeded" if result.get("success") else "failed",
        rollback_confirmed=result.get("rollback_succeeded") is True,
        readonly=readonly,
        failed_index=failed_index if isinstance(failed_index, int) else None,
    )
    annotate_revolve_axis(result)
    if inputs is not None:
        annotate_profiles(result, inputs)
        annotate_arc_geometry(result, inputs)
        annotate_feature_state(result, inputs)
    return result


def annotate_feature_state(result: dict[str, Any], inputs: list[dict[str, Any]]) -> dict[str, Any]:
    """Project each feature_state input's target detail onto its own record.

    T02 keeps one terminal record per input; the per-target before/after list
    is a specialized field of that single record. The native executor owns the
    detail, so a missing list stays missing and is never fabricated here.
    """
    from creo_mechdog import feature_state

    operations = result.get("operations")
    if not isinstance(operations, list) or not isinstance(inputs, list):
        return result
    for position, operation in enumerate(operations):
        if not isinstance(operation, dict) or operation.get("op") != "feature_state":
            continue
        source = inputs[position] if position < len(inputs) else None
        if not (isinstance(source, dict) and source.get("op") == "feature_state"):
            continue
        targets = source.get("targets")
        if isinstance(targets, list):
            feature_state.project_operation(operation, targets)
    return result


def _profile_summary(entities: list[dict[str, Any]]) -> dict[str, Any]:
    from creo_mechdog.profile_diagnostics import analyze_profile

    report = analyze_profile(entities)
    near = report["categories"]["near_tolerance"]
    # BUG-049/N03: keep bounded endpoint-gap observability in the public
    # projection. The items list is already capped and truncated by the
    # analyzer; the total count and the truncation flag survive the projection
    # so a bounded sample never hides the population size.
    return {
        "source": "input",
        "analysis": report["analysis"],
        "arc_geometry": report.get("arc_geometry", []),
        "entity_count": report["entity_count"],
        "contour_count": report["contour_count"],
        "closed_contour_count": report["closed_contour_count"],
        "open_contour_count": report["open_contour_count"],
        "material_area_mm2": report["material_area_mm2"],
        "categories": {name: entry["count"] for name, entry in report["categories"].items()},
        "closure_tolerance_mm": report["closure_tolerance_mm"],
        "max_endpoint_gap_mm": max(
            (contour["max_join_gap_mm"] for contour in report["contours"]), default=0.0
        ),
        "near_tolerance_pairs": {
            "total": near["count"],
            "truncated": near["truncated"],
            "sample": [
                {"entities": item["entities"], "gap_mm": item["gap_mm"]} for item in near["items"]
            ],
        },
    }


def _source_for(
    operation: dict[str, Any], inputs: list[dict[str, Any]], position: int
) -> dict[str, Any] | None:
    """Locate the input record behind one operation result, if it is unambiguous."""

    def same_label(item: dict[str, Any]) -> bool:
        # Geometry updates carry no label on either side while the native
        # record reports the empty string (FEAT-034/T02).
        return str(item.get("label") or "") == str(operation.get("label") or "")

    source = inputs[position] if position < len(inputs) else None
    if not (
        isinstance(source, dict) and source.get("op") == operation.get("op") and same_label(source)
    ):
        matches = [
            item
            for item in inputs
            if isinstance(item, dict) and item.get("op") == operation.get("op") and same_label(item)
        ]
        source = matches[0] if len(matches) == 1 else None
    return source if isinstance(source, dict) else None


def annotate_profiles(result: dict[str, Any], inputs: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach the analytic input contour report to every sketch result (T06).

    The native section summary is a separate field supplied by the executor;
    this report describes the supplied coordinates and never replaces it.
    """
    operations = result.get("operations")
    if not isinstance(operations, list) or not isinstance(inputs, list):
        return result
    for position, operation in enumerate(operations):
        if not isinstance(operation, dict) or operation.get("op") != "sketch":
            continue
        source = _source_for(operation, inputs, position)
        entities = source.get("entities") if isinstance(source, dict) else None
        if not isinstance(entities, list) or not entities:
            continue
        try:
            operation["profile"] = _profile_summary(entities)
        except (KeyError, TypeError, ValueError):
            # Diagnostics must never turn a delivered native result into a
            # failure; record that the input report is unavailable instead.
            operation["profile"] = {"source": "input", "analysis": "unavailable"}
    return result


_ARC_ACTUAL_FIELDS = (
    "query_code",
    "frame",
    "start_uv",
    "end_uv",
    "center_uv",
    "radius_mm",
    "start_tangent_uv",
    "end_tangent_uv",
    "dir",
    "sweep_deg",
)
_ARC_MEASURED_FIELDS = (
    "start_uv",
    "end_uv",
    "start_tangent_uv",
    "end_tangent_uv",
    "dir",
    "sweep_deg",
)


def _unknown_arc_actual(query_code: Any = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"source": "unknown", "query_code": query_code, "frame": None}
    entry.update({key: None for key in _ARC_ACTUAL_FIELDS if key not in entry})
    return entry


def project_arc_echo(entities: list[dict[str, Any]], measured: Any) -> list[dict[str, Any]]:
    """Project the executor's measured arc geometry onto the input arcs (FEAT-034).

    Reported values are only ever the executor's own query result (``source=
    "native"``) or explicitly unknown with the raw query code. Requested input
    values are never echoed here as measured geometry.
    """
    by_name: dict[str, dict[str, Any]] = {}
    if isinstance(measured, list):
        for item in measured:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                by_name[item["name"]] = item
    projection: list[dict[str, Any]] = []
    for entity in entities:
        if not isinstance(entity, dict) or entity.get("type") != "arc":
            continue
        name = str(entity.get("name"))
        record = by_name.get(name)
        if isinstance(record, dict) and record.get("source") in ("native", "unknown"):
            entry = {"name": name, "source": record["source"]}
            entry.update({key: record.get(key) for key in _ARC_ACTUAL_FIELDS})
            if entry["source"] == "native" and any(
                entry[key] is None for key in _ARC_MEASURED_FIELDS
            ):
                entry = {"name": name, **_unknown_arc_actual(record.get("query_code"))}
            projection.append(entry)
        else:
            projection.append({"name": name, **_unknown_arc_actual()})
    return projection


_REVOLVE_AXIS_SOURCES = ("explicit", "internal_centerline", "unknown")
_REVOLVE_AXIS_KINDS = ("datum_axis", "surface", "section_centerline", "unknown")
_REVOLVE_AXIS_FRAMES = ("model", "sketch_local")
_REVOLVE_AXIS_RESOLUTION_FIELDS = (
    "feature_axis_query_code",
    "axis_item_query_code",
    "axis_surface_query_code",
    "section_centerline_count",
    "section_query_code",
)


def _finite_vector(value: Any, size: int) -> list[float] | None:
    if not isinstance(value, list) or len(value) != size:
        return None
    if any(type(item) not in (int, float) or not math.isfinite(item) for item in value):
        return None
    return [float(item) for item in value]


def _axis_code(value: Any) -> int | None:
    return value if type(value) is int else None


def _unknown_revolve_axis() -> dict[str, Any]:
    return {
        "source": "unknown",
        "kind": "unknown",
        "id": None,
        "frame": None,
        "origin": None,
        "direction": None,
        "length_unit": None,
        "geometry_known": False,
        "query_code": None,
        "resolution": {key: None for key in _REVOLVE_AXIS_RESOLUTION_FIELDS},
    }


def normalize_revolve_axis(block: Any) -> dict[str, Any] | None:
    """Validate the executor's resolved revolve-axis report (FEAT-008/T09B).

    Values are only ever the executor's own query results; request parameters
    are never echoed as measured geometry. A record whose measured fields
    cannot be trusted degrades to explicit unknown (null values plus the raw
    query codes) instead of keeping numbers of unclear provenance. A missing
    block stays missing (legacy jobs) and is never fabricated from inputs.
    """
    if not isinstance(block, dict):
        return _unknown_revolve_axis()
    source = block.get("source")
    kind = block.get("kind")
    frame = block.get("frame")
    entry = _unknown_revolve_axis()
    entry["source"] = source if source in _REVOLVE_AXIS_SOURCES else "unknown"
    entry["kind"] = kind if kind in _REVOLVE_AXIS_KINDS else "unknown"
    feature_id = block.get("id")
    entry["id"] = feature_id if type(feature_id) is int and feature_id >= 0 else None
    entry["length_unit"] = (
        block.get("length_unit") if isinstance(block.get("length_unit"), dict) else None
    )
    entry["query_code"] = _axis_code(block.get("query_code"))
    resolution = block.get("resolution")
    if isinstance(resolution, dict):
        for key in _REVOLVE_AXIS_RESOLUTION_FIELDS:
            entry["resolution"][key] = _axis_code(resolution.get(key))
    frame_ok = frame in _REVOLVE_AXIS_FRAMES
    size = 3 if frame == "model" else 2
    origin = _finite_vector(block.get("origin"), size) if frame_ok else None
    direction = _finite_vector(block.get("direction"), size) if frame_ok else None
    known = block.get("geometry_known") is True
    if known and frame_ok and origin is not None and direction is not None:
        entry["frame"] = frame
        entry["origin"] = origin
        entry["direction"] = direction
        entry["geometry_known"] = True
    return entry


def annotate_revolve_axis(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize the revolve_axis block on each revolve operation record.

    The request's axis is never read here: an unreported or uninterpretable
    axis stays unknown rather than being backfilled from the request.
    """
    operations = result.get("operations")
    if not isinstance(operations, list):
        return result
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") != "revolve":
            continue
        if "revolve_axis" not in operation:
            continue
        operation["revolve_axis"] = normalize_revolve_axis(operation.get("revolve_axis"))
    return result


def annotate_arc_geometry(result: dict[str, Any], inputs: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach the measured arc echo to sketch creation and update records."""
    operations = result.get("operations")
    if not isinstance(operations, list) or not isinstance(inputs, list):
        return result
    for position, operation in enumerate(operations):
        if not isinstance(operation, dict) or operation.get("op") not in (
            "sketch",
            "update_sketch_geometry",
        ):
            continue
        source = _source_for(operation, inputs, position)
        entities = source.get("entities") if isinstance(source, dict) else None
        if not isinstance(entities, list) or not entities:
            continue
        operation["arc_geometry"] = project_arc_echo(entities, operation.get("arc_geometry"))
    return result
