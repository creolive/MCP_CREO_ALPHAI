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

#: BUG-097 L2: the native executor caps the element/section error samples; the
#: projection re-applies the same bound defensively and keeps totals visible.
FEATURE_ERROR_SAMPLE_LIMIT = 20
SECTION_ERROR_SAMPLE_LIMIT = 20


def _bounded_count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _bounded_truncated(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def normalize_feature_errors(block: Any) -> dict[str, Any]:
    """Normalize the structured CompleteFeature failure receipt (BUG-097 L2).

    The block carries the failing API, the raw Toolkit code, the failed stage,
    bounded ``element_errors`` (element/type/error triples from the
    ProErrorlist) and the original ``section_errors`` from the section solve.
    Values are only ever the executor's own reports: an uninterpretable block
    degrades to an explicit unavailable state instead of inventing entries, and
    a missing block stays missing (legacy jobs are never fabricated here).
    """
    if not isinstance(block, dict):
        return {
            "api": None,
            "code": None,
            "failed_stage": None,
            "element_errors": {"total": None, "truncated": None, "sample": []},
            "section_errors": {
                "available": False,
                "total": None,
                "truncated": None,
                "sample": [],
                "unavailable_reason": "the executor did not report a structured error block",
            },
        }
    element_sample: list[dict[str, Any]] = []
    raw_elements = block.get("element_errors")
    element_total: int | None = None
    element_truncated: bool | None = None
    if isinstance(raw_elements, dict):
        element_total = _bounded_count(raw_elements.get("total"))
        element_truncated = _bounded_truncated(raw_elements.get("truncated"))
        raw_sample = raw_elements.get("sample")
        if isinstance(raw_sample, list):
            for item in raw_sample:
                if not isinstance(item, dict):
                    element_truncated = True
                    continue
                error = item.get("error")
                entry = {
                    "element": _bounded_count(item.get("element")),
                    "type": _bounded_count(item.get("type")),
                    # A Toolkit error code may be negative; only its type matters.
                    "error": error if type(error) is int else None,
                }
                if len(element_sample) < FEATURE_ERROR_SAMPLE_LIMIT:
                    element_sample.append(entry)
                else:
                    element_truncated = True
    section_sample: list[str] = []
    section_total: int | None = None
    section_truncated: bool | None = None
    section_available = False
    unavailable_reason: str | None = None
    raw_section = block.get("section_errors")
    if isinstance(raw_section, dict):
        section_available = raw_section.get("available") is True
        section_total = _bounded_count(raw_section.get("total"))
        section_truncated = _bounded_truncated(raw_section.get("truncated"))
        raw_messages = raw_section.get("sample")
        if isinstance(raw_messages, list):
            for item in raw_messages:
                if not isinstance(item, str):
                    section_truncated = True
                    continue
                if len(section_sample) < SECTION_ERROR_SAMPLE_LIMIT:
                    section_sample.append(item)
                else:
                    section_truncated = True
        reason = raw_section.get("unavailable_reason")
        unavailable_reason = reason if isinstance(reason, str) else None
    if not section_available and unavailable_reason is None:
        unavailable_reason = "no section error capture accompanied this failure"
    api = block.get("api")
    failed_stage = block.get("failed_stage")
    code = block.get("code")
    return {
        "api": api if isinstance(api, str) and api else None,
        "code": code if type(code) is int else None,
        "failed_stage": failed_stage if isinstance(failed_stage, str) and failed_stage else None,
        "element_errors": {
            "total": element_total,
            "truncated": element_truncated,
            "sample": element_sample,
        },
        "section_errors": {
            "available": section_available,
            "total": section_total,
            "truncated": section_truncated,
            "sample": section_sample,
            "unavailable_reason": unavailable_reason,
        },
    }


def annotate_feature_errors(result: dict[str, Any]) -> dict[str, Any]:
    """Project the bounded CompleteFeature error receipt on a failed result.

    Both the report-level block and each operation record's block share the
    same normalization; records without a block are left untouched so legacy
    results never gain synthetic error entries.
    """
    if "feature_errors" in result:
        result["feature_errors"] = normalize_feature_errors(result.get("feature_errors"))
    operations = result.get("operations")
    if isinstance(operations, list):
        for operation in operations:
            if isinstance(operation, dict) and "feature_errors" in operation:
                operation["feature_errors"] = normalize_feature_errors(
                    operation.get("feature_errors")
                )
    return result


# ---------------------------------------------------------------------------
# BUG-113: save and rollback failure evidence.
# ---------------------------------------------------------------------------

#: A malformed block degrades to explicit nulls plus a reason; a missing block
#: stays missing (legacy executors never gain fabricated evidence).
ROLLBACK_DIFFERENCE_STATUSES = ("mismatch", "unavailable", "matched")


def _text_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _bounded_generic_block(value: Any) -> dict[str, Any] | None:
    """Validate one ``{total, truncated, sample}`` block without inventing facts.

    The producer owns the population and only ever reports entries it observed;
    this re-applies the shared 20-entry cap defensively (the same contract as
    ``bounded_entries``) and keeps the producer's totals.
    """
    if not isinstance(value, dict):
        return None
    sample = value.get("sample")
    if not isinstance(sample, list):
        return None
    total = _bounded_count(value.get("total"))
    truncated = _bounded_truncated(value.get("truncated"))
    items = sample[:SAMPLE_LIMIT]
    if len(sample) > SAMPLE_LIMIT:
        truncated = True
    return {"total": total, "truncated": truncated, "sample": items}


def normalize_save_failure(block: Any) -> dict[str, Any] | None:
    """Validate the executor's ``save_failure`` block (BUG-113).

    The raw Toolkit code and the failing call stay exactly as reported, so a
    failed ``ProMdlnameBackup`` is never confused with a later rollback
    verification failure. A block that cannot be read degrades to nulls instead
    of a fabricated code.
    """
    if not isinstance(block, dict):
        return None
    code = block.get("code")
    files = block.get("candidate_files")
    if isinstance(files, list):
        files = {"total": len(files), "truncated": len(files) > SAMPLE_LIMIT, "sample": files}
    return {
        "call": _text_or_none(block.get("call")),
        "code": code if type(code) is int else None,
        "stage": _text_or_none(block.get("stage")),
        "destination": _text_or_none(block.get("destination")),
        "source_checkpoint": _text_or_none(block.get("source_checkpoint")),
        "candidate_files": _bounded_generic_block(files),
    }


def _normalize_id_block(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    sample = value.get("sample")
    if not isinstance(sample, list) or any(type(item) is not int for item in sample):
        return None
    total = _bounded_count(value.get("total"))
    truncated = _bounded_truncated(value.get("truncated"))
    items = sample[:SAMPLE_LIMIT]
    if len(sample) > SAMPLE_LIMIT:
        truncated = True
    return {"total": total, "truncated": truncated, "sample": items}


def _normalize_collection_difference(value: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "available": False,
        "before": None,
        "after": None,
        "missing_ids": None,
        "added_ids": None,
        "reason": None,
    }
    if not isinstance(value, dict):
        entry["reason"] = "the executor did not report this collection"
        return entry
    before, after = value.get("before"), value.get("after")
    entry["before"] = before if _bounded_count(before) is not None else None
    entry["after"] = after if _bounded_count(after) is not None else None
    entry["reason"] = _text_or_none(value.get("reason"))
    available = value.get("available") is True
    malformed = False
    for key in ("missing_ids", "added_ids"):
        raw = value.get(key)
        if raw is None:
            continue
        normalized = _normalize_id_block(raw)
        if normalized is None:
            malformed = True
            continue
        entry[key] = normalized
    if malformed:
        # An unreadable id list cannot support a "matched" verdict.
        entry["missing_ids"] = None
        entry["added_ids"] = None
        entry["reason"] = "the executor reported malformed id lists"
        available = False
    entry["available"] = available
    if not available and entry["reason"] is None:
        entry["reason"] = "the executor did not report a usable difference"
    return entry


def _normalize_volume_difference(value: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {"available": False, "before": None, "after": None, "reason": None}
    if not isinstance(value, dict):
        entry["reason"] = "the executor did not report volume evidence"
        return entry
    entry["before"] = _finite_number(value.get("before"))
    entry["after"] = _finite_number(value.get("after"))
    entry["available"] = (
        value.get("available") is True
        and entry["before"] is not None
        and entry["after"] is not None
    )
    entry["reason"] = _text_or_none(value.get("reason"))
    if not entry["available"] and entry["reason"] is None:
        entry["reason"] = "volume was not measured on both sides"
    return entry


def normalize_rollback_difference(block: Any) -> dict[str, Any] | None:
    """Validate the executor's ``rollback_difference`` block (BUG-113).

    ``status`` is only the executor's own verdict. When the reported evidence
    cannot be read the block degrades to ``unavailable`` with a reason; it never
    flips a rollback to succeeded and never infers a difference that was not
    measured.
    """
    if not isinstance(block, dict):
        return None
    features = _normalize_collection_difference(block.get("features"))
    bodies = _normalize_collection_difference(block.get("bodies"))
    volume = _normalize_volume_difference(block.get("volume_mm3"))
    available = block.get("available") is True and features["available"] and bodies["available"]
    status = block.get("status")
    if not available or status not in ROLLBACK_DIFFERENCE_STATUSES:
        available = False
        status = "unavailable"
    reason = _text_or_none(block.get("reason"))
    if not available and reason is None:
        reason = "the executor did not report a usable comparison"
    return {
        "available": available,
        "status": status,
        "reason": reason,
        "features": features,
        "bodies": bodies,
        "volume_mm3": volume,
    }


def annotate_save_recovery(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize the save/rollback diagnostics without fabricating missing blocks."""
    if "save_failure" in result:
        result["save_failure"] = normalize_save_failure(result.get("save_failure"))
    if "rollback_difference" in result:
        result["rollback_difference"] = normalize_rollback_difference(
            result.get("rollback_difference")
        )
    return result


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
    # BUG-097 L2: the error receipt is projected even when no operation list
    # exists (a worker-level failure may still carry the structured block).
    annotate_feature_errors(result)
    # BUG-113: the save/rollback diagnostics keep their raw codes and bounded
    # difference visible on the persisted terminal state.
    annotate_save_recovery(result)
    # FEAT-012/FEAT-008: the bounded failure context rides every failed result,
    # including a failure that never reached an operation (index stays null).
    from creo_mechdog.failure_context import annotate_failed_operation

    annotate_failed_operation(result, inputs)
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
    annotate_extrude_depth(result)
    annotate_source_area_status(result)
    annotate_sketch_origin_diagnostics(result)
    annotate_sketch_shifted(result)
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
    from creo_mechdog.weldability import weldability_from_report

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
        # BUG-101: closure at 1e-4 mm is not weldability. Report the measured
        # endpoint-welding verdict (and the bounded pairs behind it) at sketch
        # time so a caller is not surprised by a later extrude -1.
        "weldability": weldability_from_report(report),
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


# W05: frozen receipt of "what the caller asked for" vs "what the created
# feature tree stored". A null request field means the field was omitted (the
# omission is captured before schema defaults are applied); a null effective
# field means the tree did not yield a value. Neither side is backfilled from
# the other, and through_all never gains a fabricated blind depth.
EXTRUDE_DEPTH_FIELDS = (
    "source",
    "query_code",
    "requested_depth_type",
    "requested_depth_mm",
    "effective_depth_type",
    "effective_depth_mm",
    "defaulted_fields",
)
EXTRUDE_DEPTH_TYPES = ("blind", "through_all", "symmetric")
EXTRUDE_DEPTH_SOURCES = ("feature_tree", "unknown")
EXTRUDE_DEPTH_DEFAULTED = ("depth", "depth_type")


def _finite_scalar(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def normalize_extrude_depth(block: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {key: None for key in EXTRUDE_DEPTH_FIELDS}
    entry["source"] = "unknown"
    entry["defaulted_fields"] = []
    if not isinstance(block, dict):
        return entry
    source = block.get("source")
    entry["source"] = source if source in EXTRUDE_DEPTH_SOURCES else "unknown"
    code = block.get("query_code")
    entry["query_code"] = code if type(code) is int else None
    requested_type = block.get("requested_depth_type")
    entry["requested_depth_type"] = (
        requested_type if requested_type in EXTRUDE_DEPTH_TYPES else None
    )
    entry["requested_depth_mm"] = _finite_scalar(block.get("requested_depth_mm"))
    effective_type = block.get("effective_depth_type")
    entry["effective_depth_type"] = (
        effective_type if effective_type in EXTRUDE_DEPTH_TYPES else None
    )
    entry["effective_depth_mm"] = _finite_scalar(block.get("effective_depth_mm"))
    defaulted = block.get("defaulted_fields")
    if isinstance(defaulted, list):
        entry["defaulted_fields"] = [
            field for field in EXTRUDE_DEPTH_DEFAULTED if field in defaulted
        ]
    return entry


def annotate_extrude_depth(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize the extruded feature's depth receipt on its own record.

    A record without the block (legacy jobs or a failed create) is left alone;
    the projection never invents a receipt from the request.
    """
    operations = result.get("operations")
    if not isinstance(operations, list):
        return result
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") != "extrude":
            continue
        if "extrude_depth" not in operation:
            continue
        operation["extrude_depth"] = normalize_extrude_depth(operation.get("extrude_depth"))
    return result


# BUG-112: surface_offset reports the source quilt area beside this receipt.
# ``available`` is only ever the executor's own success flag; a failed Init, a
# successful Init without a handle, or a failed measurement stays unavailable
# with its code and reason. A record with an unavailable area can never keep a
# finite measured offset distance: the two measurements are one claim.
def normalize_source_area_status(block: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "available": False,
        "init_code": None,
        "query_code": None,
        "reason": None,
    }
    if not isinstance(block, dict):
        entry["reason"] = "source_area_status_missing"
        return entry
    init_code = block.get("init_code")
    entry["init_code"] = init_code if type(init_code) is int else None
    query_code = block.get("query_code")
    entry["query_code"] = query_code if type(query_code) is int else None
    reason = block.get("reason")
    entry["reason"] = reason if isinstance(reason, str) and reason else None
    entry["available"] = block.get("available") is True
    if not entry["available"] and entry["reason"] is None:
        entry["reason"] = "source_area_unavailable"
    return entry


def annotate_source_area_status(result: dict[str, Any]) -> dict[str, Any]:
    """Project the surface_offset source-area receipt onto its own record.

    A record without the block stays untouched (legacy jobs are never given a
    synthetic receipt). When the receipt says the area is unavailable, the
    source area and the derived offset distance are nulls: neither may outlive
    the evidence that produced them.
    """
    operations = result.get("operations")
    if not isinstance(operations, list):
        return result
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") != "surface_offset":
            continue
        if "source_area_status" not in operation:
            continue
        status = normalize_source_area_status(operation.get("source_area_status"))
        operation["source_area_status"] = status
        if not status["available"]:
            operation["source_area_mm2"] = None
            operation["measured_offset_distance_mm"] = None
        elif "measured_offset_distance_mm" in operation:
            operation["measured_offset_distance_mm"] = _finite_scalar(
                operation.get("measured_offset_distance_mm")
            )
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


# BUG-095: frozen contract of the executor's sketch-origin rejection evidence.
# Fields are computed by the executor from the actual support plane; this
# projection only validates their shape and never recomputes or backfills them
# from the request.
_SKETCH_ORIGIN_DIAGNOSTIC_FIELDS = (
    "status",
    "distance_to_plane_mm",
    "signed_distance_to_plane_mm",
    "origin_tolerance_mm",
    "support_plane",
    "requested_origin",
    "suggested_origin",
)


def _finite_number(value: Any) -> float | None:
    return float(value) if type(value) in (int, float) and math.isfinite(value) else None


def _unknown_sketch_origin_diagnostics() -> dict[str, Any]:
    entry: dict[str, Any] = {key: None for key in _SKETCH_ORIGIN_DIAGNOSTIC_FIELDS}
    entry["status"] = "unknown"
    return entry


def normalize_sketch_origin_diagnostics(block: Any) -> dict[str, Any]:
    """Validate the executor's sketch-origin rejection evidence (BUG-095).

    Values are only ever the executor's own measurements against the actual
    support plane; the request's origin is never echoed here as evidence. A
    record whose numbers cannot be trusted degrades to explicit unknown (null
    fields plus the raw status) instead of keeping values of unclear
    provenance. A missing block stays missing (legacy jobs) and is never
    fabricated.
    """
    if not isinstance(block, dict):
        return _unknown_sketch_origin_diagnostics()
    status = block.get("status")
    entry: dict[str, Any] = {
        "status": status if isinstance(status, str) and status else "unknown",
        "distance_to_plane_mm": _finite_number(block.get("distance_to_plane_mm")),
        "signed_distance_to_plane_mm": _finite_number(block.get("signed_distance_to_plane_mm")),
        "origin_tolerance_mm": _finite_number(block.get("origin_tolerance_mm")),
        "support_plane": None,
        "requested_origin": _finite_vector(block.get("requested_origin"), 3),
        "suggested_origin": _finite_vector(block.get("suggested_origin"), 3),
    }
    plane = block.get("support_plane")
    if isinstance(plane, dict):
        normal = _finite_vector(plane.get("normal"), 3)
        constant = _finite_number(plane.get("constant_mm"))
        # The executor normalizes the support normal; a non-unit normal means
        # the block cannot be trusted as reported.
        if (
            normal is not None
            and constant is not None
            and abs(sum(item * item for item in normal) - 1) <= 1e-6
        ):
            entry["support_plane"] = {"normal": normal, "constant_mm": constant}
    distance = entry["distance_to_plane_mm"]
    signed = entry["signed_distance_to_plane_mm"]
    if distance is not None and signed is not None and abs(abs(signed) - distance) > 1e-12:
        entry["distance_to_plane_mm"] = None
        entry["signed_distance_to_plane_mm"] = None
    return entry


def annotate_sketch_origin_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize the sketch_origin_diagnostics block on failed sketch records.

    The request's plane/origin are never read here: an unreported or
    uninterpretable block stays absent or degrades to unknown rather than
    being backfilled from the request.
    """
    operations = result.get("operations")
    if not isinstance(operations, list):
        return result
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") not in (
            "sketch",
            "airfoil_sketch",
        ):
            continue
        if "sketch_origin_diagnostics" not in operation:
            continue
        operation["sketch_origin_diagnostics"] = normalize_sketch_origin_diagnostics(
            operation.get("sketch_origin_diagnostics")
        )
    return result


def annotate_sketch_shifted(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize the top-level post-solve shift block on sketch records (BUG-108).

    A record without the block stays without it (legacy jobs are never
    fabricated), and a malformed block degrades to an explicit unmeasured state.
    """
    from creo_mechdog.geometry_deviation import normalize_sketch_shifted

    operations = result.get("operations")
    if not isinstance(operations, list):
        return result
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") not in (
            "sketch",
            "update_sketch_geometry",
        ):
            continue
        if "sketch_shifted" not in operation:
            continue
        operation["sketch_shifted"] = normalize_sketch_shifted(operation.get("sketch_shifted"))
    return result


def annotate_geometry_deviation(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize the post-solve fidelity block on sketch create/edit records.

    The executor owns the measurement; this projection only validates the
    reported shape. A missing block stays missing (legacy jobs are never
    fabricated), and a malformed or contradictory record degrades to an
    explicit unavailable state with a reason instead of zeros.
    """
    from creo_mechdog.geometry_deviation import normalize_geometry_deviation

    operations = result.get("operations")
    if not isinstance(operations, list):
        return result
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") not in (
            "sketch",
            "update_sketch_geometry",
        ):
            continue
        if "geometry_deviation" not in operation:
            continue
        operation["geometry_deviation"] = normalize_geometry_deviation(
            operation.get("geometry_deviation")
        )
    return result
