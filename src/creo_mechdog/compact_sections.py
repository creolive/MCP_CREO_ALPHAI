"""FEAT-023/FEAT-008 (Q06/R04): selectable compact result blocks for job polls.

``creo_get_job(detail="compact")`` and ``creo_list_jobs(detail="compact")``
inline the whole bounded result of a job (operation records, preview, geometry
deviation, inspections, recolor receipts and so on). A caller that only polls
for one block still pays for every block. This module owns the optional
``sections`` selector:

- ``sections`` names result blocks (``preview``, ``operations``,
  ``geometry_deviation``) or per-operation blocks (``extrude_depth``,
  ``profile``). Named blocks are kept and unnamed blocks are dropped;
- outcome and recovery evidence is never selected away: ``status``,
  ``revision``, ``message``, ``code``/``toolkit_code``, rollback and
  save/reload fields, plus each operation's identity and failure evidence
  stay visible so a projected poll still identifies the terminal state;
- the response carries ``sections_applied`` (the normalized request) and
  ``omitted_sections`` (the present blocks that were dropped);
- the projection runs before the shared 32 KiB budget enforcement, so it
  never bypasses ``operation_results.enforce_compact_budget``.

Naming ``operations`` keeps complete compact operation records (the pre-feature
shape); naming only per-operation blocks keeps the operations list with each
record reduced to identity, failure evidence and the named blocks. An empty
array selects nothing and leaves only outcome evidence.
"""

from __future__ import annotations

from typing import Any

from creo_mechdog.operation_results import FAILED_EVIDENCE_KEYS, PROTECTED_OPERATION_KEYS

#: Result-level keys of the compact result, in projection order. The
#: ``PROTECTED_RESULT_KEYS`` subset is always carried; the rest are selectable
#: blocks named by ``sections``.
RESULT_KEYS = (
    "success",
    "seed_load_evidence",
    "planar_wall",
    "loft_seed_feature",
    "creo_release_numeric",
    "creo_release_query_code",
    "code",
    "toolkit_code",
    "message",
    "part_file",
    "sha256",
    "saved_file_reloaded_and_verified",
    "rollback_succeeded",
    "rollback_status",
    "model_unchanged",
    "rollback_message",
    "rollback_code",
    # BUG-113: the failed-save call/code and the bounded restored-vs-baseline
    # difference. Both are failure evidence, never a selectable detail block.
    "save_failure",
    "rollback_difference",
    "preview_file",
    "preview_status",
    "preview_code",
    "preview",
    "connected",
    "volume_mm3",
    "expected_volume_mm3",
    "extrude_count",
    "round_count",
    "hole_count",
    "failed_stage",
    "failed_toolkit_call",
    "failed_operation_index",
    # FEAT-012/FEAT-008: the bounded failure context (index, operation, stage,
    # names, raw Toolkit code, bounded message and the echoed placement matrix).
    "failed_operation",
    "inspection_source",
    "adoption",
    "adopted",
    "open_file",
    "session_erase",
    "loaded",
    "session_fingerprint",
    "feature_tombstones",
    "suppressed_features",
    "inspection_warnings",
    "geometry_deviation",
    "failed_model_cleanup",
    # BUG-114: the scoped terminal-effect verdicts (managed model / component
    # bindings / external outputs) ride every failed terminal result.
    "terminal_effect",
    "feature_errors",
    "verify_stages",
    "failed_transform",
)

#: Outcome/evidence fields that ``sections`` never removes (failure reason,
#: revision evidence, rollback and save/reload proof, and geometry counts).
PROTECTED_RESULT_KEYS = (
    "success",
    "creo_release_numeric",
    "creo_release_query_code",
    "code",
    "toolkit_code",
    "message",
    "part_file",
    "sha256",
    "saved_file_reloaded_and_verified",
    "rollback_succeeded",
    "rollback_status",
    "model_unchanged",
    "rollback_message",
    "rollback_code",
    # BUG-113: the failed-save call/code and the bounded restored-vs-baseline
    # difference. Both are failure evidence, never a selectable detail block.
    "save_failure",
    "rollback_difference",
    "preview_file",
    "preview_status",
    "preview_code",
    "connected",
    "volume_mm3",
    "expected_volume_mm3",
    "extrude_count",
    "round_count",
    "hole_count",
    "failed_stage",
    "failed_toolkit_call",
    "failed_operation_index",
    # FEAT-012/FEAT-008: the bounded failure context (index, operation, stage,
    # names, raw Toolkit code, bounded message and the echoed placement matrix).
    "failed_operation",
    "inspection_source",
    "adopted",
    # BUG-114: the scoped terminal-effect verdicts are outcome evidence and are
    # never removed by a ``sections`` selection.
    "terminal_effect",
    # Population markers the compact projection already publishes for the
    # operations list; they stay even when the records themselves are filtered.
    "operations_total",
    "operations_truncated",
)

#: Selectable result-level blocks. ``inspection*``, ``live``, ``recolor``,
#: ``alias_count`` and ``operations`` are added dynamically by ``compact_job``
#: and are selectable here too.
RESULT_SECTIONS = (
    "seed_load_evidence",
    "planar_wall",
    "loft_seed_feature",
    "preview",
    "inspection",
    "inspection_summary",
    "inspection_ref",
    "aliases_ref",
    "alias_count",
    "live",
    "recolor",
    "operations",
    "geometry_deviation",
    "feature_errors",
    "failed_model_cleanup",
    "verify_stages",
    "failed_transform",
    "inspection_warnings",
    "feature_tombstones",
    "suppressed_features",
    "adoption",
    "open_file",
    "session_erase",
    "loaded",
    "session_fingerprint",
)

#: Per-operation keys of a compact result, in projection order.
OPERATION_KEYS = (
    "op",
    "index",
    "label",
    "succeeded",
    "execution_status",
    "effect_status",
    "unchanged",
    "native_geometry_verified",
    "size",
    "file",
    "feature_id",
    "preserved_feature_id",
    "reordered",
    "sheet",
    "parameters",
    "metadata",
    "material_removed_mm3",
    "volume_before_mm3",
    "volume_after_mm3",
    "material_delta_mm3",
    "material_measurement",
    "draft_geometry",
    "extrude_depth",
    "reference_application",
    "surface_id",
    "origin",
    "normal",
    "u_axis",
    "v_axis",
    "datum_axes",
    "axes_query_code",
    "length_unit",
    "profile",
    "native_section",
    "preview_code",
    "preview",
    "feature_state",
    "targets",
    "target_count",
    "requested_target_count",
    "targets_complete",
    "elapsed_seconds",
    "message",
    "geometry_deviation",
    "sketch_shifted",
    "solver",
    "miter_cuts",
    "adjacent_bend_ends_allowed",
    "feature_errors",
    "failed_model_cleanup",
    "edge_geometry_diagnostic",
    "depth_basis",
    "depth_scheme_code",
    "depth_scheme_query",
    "thread_metadata",
    "thread_metadata_verified",
    "thread_readback",
    "requested_flip",
    "effective_flip",
    "draft_failure",
)

#: Selectable per-operation blocks; identity, status, message and failure
#: evidence always remain on each record.
OPERATION_SECTIONS = tuple(
    key
    for key in OPERATION_KEYS
    if key not in PROTECTED_OPERATION_KEYS and key not in FAILED_EVIDENCE_KEYS
)

_KNOWN_SECTIONS = frozenset(RESULT_SECTIONS) | frozenset(OPERATION_SECTIONS)
_KNOWN_MESSAGE = f"known compact sections: {sorted(_KNOWN_SECTIONS)}"


def resolve_sections(sections: Any) -> list[str]:
    """Validate and normalize a ``sections`` request; raise ValueError on bad names.

    Duplicates are removed while the request order is preserved. The error text
    always names the rejected value and lists every known block.
    """
    if isinstance(sections, str) or not isinstance(sections, (list, tuple)):
        raise ValueError("sections must be an array of compact block names; " + _KNOWN_MESSAGE)
    normalized: list[str] = []
    for item in sections:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("sections entries must be non-empty block names; " + _KNOWN_MESSAGE)
        name = item.strip()
        if name not in _KNOWN_SECTIONS:
            raise ValueError(f"Unknown compact section {name!r}; {_KNOWN_MESSAGE}")
        if name not in normalized:
            normalized.append(name)
    return normalized


def known_sections() -> list[str]:
    """Every valid ``sections`` name, sorted."""
    return sorted(_KNOWN_SECTIONS)


def apply_sections(summary: dict[str, Any], sections: list[str]) -> dict[str, Any]:
    """Return a copy of one compact summary projected onto the named blocks.

    ``summary`` is the default compact shape (already bounded by
    ``bounded_summary``); this function only removes unnamed blocks, adds no
    data, and never mutates the input. The caller still runs
    ``enforce_compact_budget`` afterwards.
    """
    selected = set(sections)
    projected = dict(summary)
    result = summary.get("result")
    omitted: set[str] = set()
    if not isinstance(result, dict):
        projected["sections_applied"] = list(sections)
        projected["omitted_sections"] = []
        return projected
    operations = result.get("operations")
    records = (
        [record for record in operations if isinstance(record, dict)]
        if isinstance(operations, list)
        else []
    )
    keep_full_operations = "operations" in selected
    operation_selected = [name for name in sections if name in OPERATION_SECTIONS]
    kept: dict[str, Any] = {}
    for key, value in result.items():
        if key == "operations":
            continue
        if key in PROTECTED_RESULT_KEYS or key in selected:
            kept[key] = value
        elif key in _KNOWN_SECTIONS:
            omitted.add(key)
    if keep_full_operations:
        kept["operations"] = list(operations) if isinstance(operations, list) else []
    elif operation_selected:
        kept["operations"] = [
            {
                key: value
                for key, value in record.items()
                if key in PROTECTED_OPERATION_KEYS or key in FAILED_EVIDENCE_KEYS or key in selected
            }
            for record in records
        ]
        for name in OPERATION_SECTIONS:
            if name not in selected and any(name in record for record in records):
                omitted.add(name)
    elif isinstance(operations, list) and operations:
        omitted.add("operations")
    projected["result"] = kept
    projected["sections_applied"] = list(sections)
    projected["omitted_sections"] = sorted(omitted)
    return projected
