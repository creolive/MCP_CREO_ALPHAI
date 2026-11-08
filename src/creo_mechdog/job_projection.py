"""R04 (FEAT-023/FEAT-039): bounded compact projections for job polls.

``detail=compact`` is the polling view, so it must stay small *and* keep the
measurements that decide whether an operation actually did what was asked.
This module is a pure projection: it copies only keys the native executor
already produced, never computes or backfills a value, and keeps ``null`` and
``reason`` exactly as reported. A missing measurement stays absent; it never
becomes ``0``.

Three projections:

- ``compact_operation``: the operation whitelist. It starts from the shared
  compact operation keys and adds the per-operation criteria of the surface
  chain (``surface_trim`` area before/after, ``surface_offset`` source area and
  measured distance, ``project_curve`` length/endpoints/route evidence and the
  ``solidify`` closure);
- ``compact_progress``: the worker progress receipt (stage, timings,
  availability) without log text;
- ``compact_job_list_item``: the list-view item. A list entry only carries the
  identity, state, times and a short message; full result context is fetched
  through ``creo_get_job`` so a bounded message never hides the failure.

Ordering in ``bridge.compact_job``: the optional ``sections`` selection runs
first, then this projection, then the shared sampling and 32 KiB budget.
"""

from __future__ import annotations

from typing import Any

from creo_mechdog.compact_sections import OPERATION_KEYS
from creo_mechdog.operation_results import FAILED_EVIDENCE_KEYS, PROTECTED_OPERATION_KEYS

#: Identity, status and failure evidence that never leaves a compact record.
OPERATION_EVIDENCE_KEYS = tuple(
    dict.fromkeys(
        (
            *PROTECTED_OPERATION_KEYS,
            *FAILED_EVIDENCE_KEYS,
            "failed_operation",
            "detail_truncated",
        )
    )
)

#: Keys produced by native/surface_trim.cpp (``area_fields_json`` plus the
#: §4.5 kept-side basis). The status blocks and the null centroids are kept as
#: reported so a rejected or unmeasured side stays visible.
SURFACE_TRIM_KEYS = (
    "target_quilt_id",
    "area_before_mm2",
    "area_before_status",
    "area_after_mm2",
    "area_after_status",
    "keep_side",
    "offset_mm",
    "offset_side",
    "kept_quilt_id",
    "kept_quilt_source",
    "kept_quilt_visit_code",
    "kept_side_basis",
    "regeneration",
)

#: Keys produced by native/surfaces.cpp::generic_surface_offset (BUG-112
#: source-area receipt plus the measured distance).
SURFACE_OFFSET_KEYS = (
    "target_quilt_id",
    "source_area_mm2",
    "source_area_status",
    "offset_distance_mm",
    "measured_offset_distance_mm",
    "offset_distance_status",
    "direction",
    "offset_method",
    "volume_before_mm3",
    "volume_after_mm3",
)

#: Keys produced by native/project_curve.cpp: the source measurement, the
#: direction route and the resulting curve/endpoint measurement.
PROJECT_CURVE_KEYS = (
    "source_curve_id",
    "source_length_mm",
    "source_length_status",
    "target_quilt_id",
    "side",
    "direction",
    "direction_basis",
    "direction_length",
    "target_bounds_known",
    "target_bounds_code",
    "target_bounds_mm",
    "route",
    "source_owner_feature_id",
    "helper_feature_id",
    "helper_sweep_depth",
    "helper_sweep_depth_mm",
    "helper_visit_code",
    "helper_surfaces",
    "helper_swept_face_ids",
    "curve_feature_id",
    "feature_status",
    "curve_ids",
    "curve_visit_code",
    "edge_ids",
    "edge_visit_code",
    "curve_id",
    "curve_length_mm",
    "curve_length_status",
    "endpoints_mm",
    "endpoints_status",
    "curve_candidates",
    "curve_count",
    "simple_curve_count",
)

#: Keys produced by native/surface_loft.cpp: the created quilt id, the measured
#: area and whether it is open/closed, plus the element-tree evidence that a
#: failed boundary-blend regeneration needs.
SURFACE_LOFT_KEYS = (
    "sections",
    "section_curve_ids",
    "interpolation",
    "route",
    "create_code",
    "create_element_errors",
    "extract_code",
    "extracted_tree",
    "feature_id",
    "feature_type",
    "feature_status",
    "surface_type",
    "quilt_visit_code",
    "quilt_count",
    "quilt_ids",
    "quilt_id",
    "quilt_init_code",
    "surface_area_mm2",
    "surface_area_status",
    "quilt_closed_native",
    "closure",
    "surface_group",
    "has_solid",
)

#: Keys produced by native/surface_boundary_fill.cpp (DEV-074/H09): the echoed
#: ordered chain, the sameness/order evidence, the created quilt id, the
#: measured face count/area/closure and the boundary edge count. The
#: ``surface_group`` block carries the group measurement used for
#: ``boundary_edges``; every measurement keeps its own status.
SURFACE_BOUNDARY_FILL_KEYS = (
    "boundary",
    "boundary_curve_ids",
    "boundary_edges",
    "boundary_closed",
    "boundary_tolerance_mm",
    "chain_gap_max_mm",
    "route",
    "add_closed",
    "create_code",
    "create_element_errors",
    "extract_code",
    "tree_elements_read",
    "feature_id",
    "feature_type",
    "feature_status",
    "surface_type",
    "quilt_visit_code",
    "quilt_count",
    "quilt_ids",
    "quilt_id",
    "quilt_init_code",
    "surface_area_mm2",
    "surface_area_status",
    "quilt_closed_native",
    "closure",
    "face_count",
    "face_count_status",
    "surface_group",
    "has_solid",
    "solid_surface_count",
)

#: Keys produced by native/surface_round.cpp (DEV-074/H08): the result quilt id,
#: the measured face counts/areas before and after, closure, radius and the
#: solid-face evidence. Every measurement keeps its own status, so a compact
#: poll can tell a measured value from an unmeasured one.
SURFACE_ROUND_KEYS = (
    "quilt_id",
    "face_ids",
    "radius",
    "feature_id",
    "feature_status",
    "feature_type",
    "face_count_before",
    "face_count_before_status",
    "face_count",
    "face_count_status",
    "area_before_mm2",
    "area_before_status",
    "area_mm2",
    "area_status",
    "closed_before",
    "closed",
    "closed_status",
    "quilt_closed_native",
    "has_solid",
    "solid_surface_count",
)

#: Keys produced by native/surface_group.cpp (FEAT-039/H04). The whole group
#: block is kept together: every value carries its own status, so a compact
#: poll can still tell a measured zero from an unmeasured seam.
SURFACE_GROUP_KEYS = (
    "unit_name",
    "length_scale_to_mm",
    "tolerance_mm",
    "gap_search_mm",
    "group",
)

#: Keys produced by native/surface_curvature.cpp (DEV-074/H08). The face blocks,
#: the aggregate summary and the G1 block each keep their own status, so a
#: compact poll can tell a measured zero curvature from an unmeasured sample.
SURFACE_CURVATURE_KEYS = (
    "unit_name",
    "length_scale_to_mm",
    "curvature_unit",
    "radius_unit",
    "quilt_id",
    "samples_per_direction",
    "faces",
    "summary",
    "g1_max_angle_deg",
    "g1_status",
    "g1_threshold_deg",
    "within_g1",
    "g1_points",
)

#: Keys produced by native/surfaces.cpp::generic_surface_solid. ``closure`` is
#: the measured ProQuiltVolumeEval receipt (available/query_code/reason).
SOLIDIFY_KEYS = (
    "target_quilt_id",
    "closure",
    "side",
    "volume_before_mm3",
    "volume_after_mm3",
)

#: R05 (BUG-045/FEAT-012): the placement receipt from
#: ``native/advanced.cpp::assembly_pose_receipt``. ``rotation_convention`` names
#: the published row-vector mapping; ``transform``, ``transform_source``,
#: ``transform_code`` and ``length_unit`` are the pose read back from the
#: kernel. A failed readback keeps ``transform=null`` with its raw query code,
#: so compact never turns "unread" into a copied request pose.
ASSEMBLY_POSE_KEYS = (
    "rotation_convention",
    "transform",
    "transform_source",
    "transform_code",
    "length_unit",
)

#: FEAT-014: the miter request echo and the adjacency evidence that it released.
#: Both are the flange's own judgement fields, so a compact poll keeps them
#: instead of silently dropping the only record of the guard decision.
FLANGE_MITER_KEYS = (
    "miter_cuts",
    "adjacent_bend_ends_allowed",
)

_OPERATION_CRITERIA: dict[str, tuple[str, ...]] = {
    "assemble_component": ASSEMBLY_POSE_KEYS,
    "component_placement": ASSEMBLY_POSE_KEYS,
    "surface_trim": SURFACE_TRIM_KEYS,
    "surface_loft": SURFACE_LOFT_KEYS,
    "surface_boundary_fill": SURFACE_BOUNDARY_FILL_KEYS,
    "surface_round": SURFACE_ROUND_KEYS,
    "surface_group_measure": SURFACE_GROUP_KEYS,
    "surface_curvature": SURFACE_CURVATURE_KEYS,
    "surface_offset": SURFACE_OFFSET_KEYS,
    "project_curve": PROJECT_CURVE_KEYS,
    "solidify": SOLIDIFY_KEYS,
    "sheetmetal_flange": FLANGE_MITER_KEYS,
}

#: Progress receipt keys from ``native_stage.stall_report``. Log text and any
#: other nested value are not part of the polling projection.
PROGRESS_KEYS = (
    "readable",
    "log_bytes",
    "tail_bytes",
    "truncated",
    "stage",
    "sub_stage",
    "elapsed_ms",
    "since_start_ms",
    "idle_seconds",
    "stages_seen",
    "reason",
)

#: List-view identity and state. ``job_id`` is the detail entry: the caller
#: reads the result with ``creo_get_job(job_id, detail=...)``.
LIST_ITEM_KEYS = (
    "job_id",
    "model_id",
    "status",
    "stage",
    "created_at",
    "started_at",
    "finished_at",
)

#: Success/failure classification of the manifest status.
OUTCOMES = {
    "succeeded": "success",
    "failed": "failure",
    "unknown_outcome": "unknown",
    "queued": "pending",
    "running": "pending",
}

#: A single list item stays at or below this serialized size. The 640 B target
#: leaves room for the list framing, so 50 items stay inside 32768 B.
LIST_ITEM_BUDGET = 620
#: A list message is cut to this many characters first, then to the item budget.
LIST_MESSAGE_MAX_CHARS = 200

#: Compact points at the paginated full view with the exact parameters.
FULL_DETAIL_HINT = (
    "Compact omits raw logs and unnamed blocks. Use creo_get_job(job_id, "
    'detail="full", section="operations_result", limit=50, cursor=<next_cursor>) '
    "for every operation record; omit section for the whole view, or use "
    "section=operations_input/result_entries for the other pages."
)


def operation_keys(operation: dict[str, Any]) -> tuple[str, ...]:
    """Every key ``compact_operation`` may copy for one operation record."""
    criteria = _OPERATION_CRITERIA.get(operation.get("op"), ())
    return tuple(dict.fromkeys((*OPERATION_KEYS, *OPERATION_EVIDENCE_KEYS, *criteria)))


def compact_operation(operation: dict[str, Any]) -> dict[str, Any]:
    """Project one native operation record onto its compact whitelist.

    Only keys already present on the record are copied; values (including
    ``null`` and nested ``reason`` fields) are never rewritten, measured or
    defaulted.
    """
    if not isinstance(operation, dict):
        return {}
    return {key: operation[key] for key in operation_keys(operation) if key in operation}


def compact_progress(progress: dict[str, Any]) -> dict[str, Any]:
    """Project a progress receipt onto its stage/timing keys, dropping log text."""
    if not isinstance(progress, dict):
        return {}
    return {key: progress[key] for key in PROGRESS_KEYS if key in progress}


def _fit_message(item: dict[str, Any], text: str) -> None:
    """Bound one list message by characters and then by the item byte budget."""
    from creo_mechdog.model_queries import serialized_size

    prefix = text[:LIST_MESSAGE_MAX_CHARS]
    truncated = len(text) > LIST_MESSAGE_MAX_CHARS
    while True:
        item["message"] = prefix + ("…" if truncated else "")
        if truncated:
            item["message_truncated"] = True
        else:
            item.pop("message_truncated", None)
        if serialized_size(item) <= LIST_ITEM_BUDGET or not prefix:
            return
        prefix = prefix[:-1]
        truncated = True


def compact_job_list_item(manifest: dict[str, Any]) -> dict[str, Any]:
    """Project one job manifest onto the bounded list item.

    The item carries identity, status, times, the success/failure
    classification and a bounded ``message``. The result, revision, rollback
    and failure context stay on ``creo_get_job``; the ``job_id`` is the entry.
    """
    if not isinstance(manifest, dict):
        return {}
    item = {key: manifest[key] for key in LIST_ITEM_KEYS if key in manifest}
    item["outcome"] = OUTCOMES.get(manifest.get("status"), "unknown")
    message = manifest.get("message")
    if isinstance(message, str) and message:
        _fit_message(item, message)
    return item
