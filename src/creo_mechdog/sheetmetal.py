"""First-wall section contract and sheetmetal result projections.

DEV-051 T03 / BUG-032. `creo_sheetmetal_wall` builds the first wall as a thin
extrusion of the sketch section and then converts that body into a native
sheetmetal wall. The conversion re-drives the body from one driving face, so
only one open straight line has a defined depth/thickness geometry:

    volume = line length x thickness x depth

Any other section (closed contour, arc, spline, multi-entity chain) would be
rebuilt from an arbitrary face: the reported closed rectangle kept the same
volume for depth 1 and depth 30, i.e. the depth was silently dropped. Admission
rejects those sections before the native modelling step, and the native
operation enforces the same rule for cross-job sketch references that Python
cannot inspect.

DEV-053 P08 / BUG-032 / FEAT-014: the depth/thickness frame projection and the
bounded wall-contour (candidate edge) projection live here. Both follow the
same three rules as the operation result projections: values are only ever the
executor's own measurements (never request echoes), a missing record stays
missing, and a record whose numbers cannot be trusted degrades to explicit
unknown while keeping the raw query code.
"""

from __future__ import annotations

import math
from typing import Any

_UNSUPPORTED = (
    "closed contours, arcs, splines and multi-entity chains are not supported for the first wall"
)


def first_wall_section_problem(entities: list[dict[str, Any]]) -> str | None:
    """Return why a section cannot drive a first wall, or None when it can."""
    drawing = [
        entity
        for entity in entities
        if entity.get("type") != "centerline" and not entity.get("construction")
    ]
    if len(drawing) != 1:
        return (
            "sheetmetal_wall needs exactly one open straight line as the first wall section; "
            f"got {len(drawing)} drawing entities ({_UNSUPPORTED})"
        )
    kind = drawing[0].get("type")
    if kind != "line":
        return (
            "sheetmetal_wall needs exactly one open straight line as the first wall section; "
            f"got a {kind!r} entity ({_UNSUPPORTED})"
        )
    return None


# BUG-046 / DEV-051 T04: a solid protrusion that merges into an existing
# sheetmetal body is refused by Creo with a bare ProFeatureWithoptionsCreate -1.
# Live isolation on Creo 12.4.0.0 (2026-10-29) measured the three cases that fix
# the boundary: the same add over the sheet and far away from it both return -1
# with no element errors, the same rectangle as a cut removes 100 mm3, and the
# same add with new_body=true succeeds as a separate solid body (+500 mm3, no
# merge). Adding material to the sheet therefore has to go through the wall or
# flange operations; the solid protrusion path cannot feed the sheetmetal body.
SOLID_ADD_UNSUPPORTED = "SHEETMETAL_SOLID_ADD_UNSUPPORTED"


def solid_add_on_sheetmetal_problem(operations: list[dict[str, Any]]) -> str | None:
    """Return why a plan would add solid material into a sheetmetal body."""
    blocked = [
        operation.get("label")
        for operation in operations
        if operation.get("op") == "extrude"
        and operation.get("mode") == "add"
        and operation.get("thin") is None
        and not operation.get("new_body")
    ]
    if not blocked:
        return None
    labels = ", ".join(str(label) for label in blocked)
    return (
        f"{SOLID_ADD_UNSUPPORTED}: Creo rejects an extrude add that merges solid material "
        "into a sheetmetal body (ProFeatureWithoptionsCreate returns -1, measured on Creo "
        "12.4.0.0 with and without overlap). Add material with sheetmetal_wall or "
        "sheetmetal_flange, or request new_body=true to create a separate solid body "
        "(not fused with the sheetmetal body). Cut and surface extrudes are outside "
        "this rule; thin extrude add and revolve add are not blocked here, but their "
        "target body and merge behavior are not verified. "
        f"Blocked operations: {labels}"
    )


# --- P08 depth/thickness frame projection (BUG-032 / FEAT-014 / FEAT-008) ---
#
# Frozen frame semantics (live-anchored, see tools/test_sheetmetal_contract.py):
# depth grows one-sided along the signed sketch normal (direction=positive ->
# +normal, direction=negative -> -normal); thickness is the sheet gauge spread
# centered on the sketch line, in-plane perpendicular to it. wall_contract.echo
# carries the measured frame so a volume-only check can never hide a wrong
# orientation or a swapped depth/thickness pair.

MATERIAL_SIDES = ("opposite_thickness_direction", "along_thickness_direction")
WALL_CONTOUR_STATUSES = ("eligible", "ineligible", "unknown")
# ProSmtedgeContourGet answers these codes (ProSheetmetal.h): PRO_TK_NO_ERROR
# when the edge lies on a green/white wall contour, PRO_TK_BAD_CONTEXT when the
# model is not sheetmetal or the edge is not on a green/white surface, anything
# else is a query failure and stays unknown with its real code preserved.
PRO_TK_NO_ERROR = 0
PRO_TK_BAD_CONTEXT = -8


def _finite_number(value: Any) -> float | None:
    return float(value) if type(value) in (int, float) and math.isfinite(value) else None


def _finite_vector(value: Any, size: int) -> list[float] | None:
    if not isinstance(value, list) or len(value) != size:
        return None
    numbers = [float(item) for item in value if type(item) in (int, float) and math.isfinite(item)]
    return numbers if len(numbers) == size else None


def _unit_vector(value: Any, size: int = 3) -> list[float] | None:
    vector = _finite_vector(value, size)
    if vector is None:
        return None
    norm = math.sqrt(sum(item * item for item in vector))
    return vector if abs(norm - 1) <= 1e-6 else None


def normalize_wall_contract(block: Any) -> dict[str, Any] | None:
    """Validate the frame echo inside a wall_contract record (DEV-053 P08).

    Only the executor's own measurements are kept: a non-unit direction or an
    uninterpretable material side degrades that field to null instead of
    keeping a value of unclear provenance. A missing block stays missing
    (legacy jobs) and is never fabricated from the request.
    """
    if not isinstance(block, dict):
        return None
    entry: dict[str, Any] = {
        "line_length_mm": _finite_number(block.get("line_length_mm")),
        "expected_volume_mm3": _finite_number(block.get("expected_volume_mm3")),
        "measured_volume_mm3": _finite_number(block.get("measured_volume_mm3")),
        "driving_face_id": block.get("driving_face_id")
        if type(block.get("driving_face_id")) is int
        else None,
        "driving_axis": block.get("driving_axis")
        if type(block.get("driving_axis")) is int
        else None,
        "part_thickness_before_mm": _finite_number(block.get("part_thickness_before_mm")),
        "part_thickness_mm": _finite_number(block.get("part_thickness_mm")),
        "part_thickness_synced": block.get("part_thickness_synced")
        if type(block.get("part_thickness_synced")) is bool
        else None,
        "frame": None,
        "wall_face_ids": None,
        "parameter_hint": block.get("parameter_hint")
        if isinstance(block.get("parameter_hint"), str) and block.get("parameter_hint")
        else None,
    }
    frame = block.get("frame")
    if isinstance(frame, dict):
        projected: dict[str, Any] = {
            "sketch_normal": _unit_vector(frame.get("sketch_normal")),
            "sketch_origin": _finite_vector(frame.get("sketch_origin"), 3),
            "depth_direction": _unit_vector(frame.get("depth_direction")),
            "thickness_direction": _unit_vector(frame.get("thickness_direction")),
            "material_side": None,
        }
        side = frame.get("material_side")
        if side in MATERIAL_SIDES:
            projected["material_side"] = side
        entry["frame"] = projected
    face_ids = block.get("wall_face_ids")
    if isinstance(face_ids, list):
        entry["wall_face_ids"] = [item for item in face_ids if type(item) is int]
    return entry


# --- P08 wall-contour (candidate edge) projection (FEAT-014) -----------------
#
# wall_contour_status answers exactly one question: does this edge lie on a
# green/white sheetmetal wall contour, i.e. can it carry a flange attachment at
# all? eligible is NOT a promise that a flange will succeed - the
# adjacent_bend_ends pre-creation rejection and the native geometry checks
# still apply - and the field is deliberately not named "flange_available".
#
# The native inspection keeps its compared `edges` records byte-stable (old
# snapshots must keep reconciling) and reports the bounded query in a separate
# top-level wall_contour_check block keyed by edge id; this projection derives
# the tri-state from the real query codes, joins it onto copies of the edge
# records, and stamps the model revision the check was observed at.


def wall_contour_status_from_code(query_code: Any) -> str | None:
    """Map one real ProSmtedgeContourGet code to the frozen tri-state.

    None means the query never ran for this edge (missing stays missing); any
    non-integer input is malformed and degrades to "unknown" at the projector,
    not here.
    """
    if type(query_code) is not int:
        return None
    if query_code == PRO_TK_NO_ERROR:
        return "eligible"
    if query_code == PRO_TK_BAD_CONTEXT:
        return "ineligible"
    return "unknown"


def project_wall_contour(inspection: Any, revision: Any = None) -> dict[str, Any]:
    """Project the bounded wall-contour check of one inspection snapshot.

    Rules: an edge without a query record gets no status at all; a check record
    whose code is not an integer degrades to status "unknown" while the raw
    value is preserved in wall_contour_query_code; an unknown edge id keeps its
    record but is never joined onto an edge. The summary carries the revision
    the check was observed at (the caller supplies the current model revision -
    the executor does not know it) and null when it is unknown.
    """
    state = inspection if isinstance(inspection, dict) else {}
    check = state.get("wall_contour_check")
    records = check.get("edges") if isinstance(check, dict) else None
    by_edge: dict[Any, dict[str, Any]] = {}
    checked = 0
    counts = {status: 0 for status in WALL_CONTOUR_STATUSES}
    projected_records: list[dict[str, Any]] = []
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, dict):
                continue
            entry = dict(record)
            code = entry.get("wall_contour_query_code")
            if code is None:
                projected_records.append(entry)
                continue
            checked += 1
            status = wall_contour_status_from_code(code)
            if status is None:
                status = "unknown"
            entry["wall_contour_status"] = status
            counts[status] += 1
            projected_records.append(entry)
            if "edge_id" in entry:
                by_edge[entry["edge_id"]] = entry
    edges = []
    for edge in state.get("edges") or []:
        record = dict(edge) if isinstance(edge, dict) else {"raw": edge}
        match = by_edge.get(record.get("id"))
        if match is not None:
            record["wall_contour_query_code"] = match.get("wall_contour_query_code")
            record["wall_contour_status"] = match.get("wall_contour_status")
        edges.append(record)
    summary: dict[str, Any] = {
        "query": "ProSmtedgeContourGet",
        "enabled": check.get("enabled") if isinstance(check, dict) else None,
        "bounded": check.get("bounded") if isinstance(check, dict) else None,
        "budget": check.get("budget") if isinstance(check, dict) else None,
        "revision": revision if type(revision) is int else None,
        "checked_edges": checked,
        "eligible": counts["eligible"],
        "ineligible": counts["ineligible"],
        "unknown": counts["unknown"],
        "meaning": (
            "eligible means the edge lies on a green/white wall contour and can carry a "
            "flange attachment; it does not promise flange creation - adjacent_bend_ends "
            "and native geometry checks still reject at creation time"
        ),
    }
    return {
        "edges": edges,
        "wall_contour_check": summary,
        "wall_contour_records": projected_records,
    }
