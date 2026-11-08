"""Tool-specific reference contracts and compatibility for angular pattern axes."""

from __future__ import annotations

import re
from typing import Annotated, Any

from pydantic import BeforeValidator, WithJsonSchema

from creo_mechdog.capabilities import SURFACE_TRIM_OFFSET_LIMIT

AXIS_DESCRIPTION = (
    "Bare axis selection: {kind:'axis',id:N} from model inspection, or "
    "{kind:'datum_axis_feature',label:'axis_label'}. In axis_pattern only, "
    "{kind:'datum_feature',label:'axis_label'} is a compatibility alias for "
    "datum_axis_feature. A plane normal such as {kind:'datum_plane',axis:'z'} "
    "is not a rotation axis. Do not wrap this selection in reference/edge."
)

PLANE_REFERENCE_DESCRIPTION = (
    "XY/XZ/YZ, or a dictionary with reference selecting "
    "{kind:'datum_plane',id:N} (geometry ID from datum_planes), "
    "{kind:'plane',id:N} (verified planar geometry), {kind:'surface',id:N} "
    "(planar support), or {kind:'datum_feature',label:'plane_label'}. "
    "The dictionary requires the reference container; origin/u_axis are optional "
    "frame fields. A plane/datum_plane id "
    "cannot be combined with axis, normal or offset in the same reference object."
)


def normalize_pattern_axis(value: Any) -> dict[str, Any]:
    """Convert the reported generic datum label to the existing native axis selector."""
    error = "Pattern requires an axis reference. " + AXIS_DESCRIPTION
    if not isinstance(value, dict):
        raise ValueError(error)
    kind = value.get("kind")
    if kind == "axis":
        if type(value.get("id")) is not int or value["id"] < 0:
            raise ValueError(error)
    elif kind in ("datum_axis_feature", "datum_feature"):
        if not isinstance(value.get("label"), str) or not value["label"]:
            raise ValueError(error)
    else:
        raise ValueError(error)
    normalized = dict(value)
    if kind == "datum_feature":
        normalized["kind"] = "datum_axis_feature"
    return normalized


_AXIS_SCHEMA = {
    "description": AXIS_DESCRIPTION,
    "oneOf": [
        {
            "type": "object",
            "properties": {"kind": {"const": "axis"}, "id": {"type": "integer", "minimum": 0}},
            "required": ["kind", "id"],
        },
        *[
            {
                "type": "object",
                "properties": {
                    "kind": {"const": kind},
                    "label": {"type": "string", "minLength": 1},
                },
                "required": ["kind", "label"],
            }
            for kind in ("datum_axis_feature", "datum_feature")
        ],
    ],
}

PatternAxis = Annotated[
    dict[str, Any], BeforeValidator(normalize_pattern_axis), WithJsonSchema(_AXIS_SCHEMA)
]


REVOLVE_AXIS_DESCRIPTION = (
    "Bare axis selection: {kind:'datum_axis_feature',label:'axis_label'} referencing a datum "
    "axis feature created earlier in the same model, or {kind:'axis',id:N} from model "
    "inspection. Omit axis (or pass null) to revolve about the sketch's own construction "
    "centerline; that sketch must contain exactly one centerline. Objects without a kind key "
    "(including {entity:'ax'}), empty objects, non-axis kinds and missing id/label are rejected. "
    "The axis_pattern-only datum_feature alias does not apply here; do not wrap the selection "
    "in reference/entity/edge containers."
)


def normalize_revolve_axis(value: Any) -> dict[str, Any]:
    """Reject malformed or non-axis revolve.axis selections before native dispatch (BUG-083)."""
    error = ValueError(
        "Revolve axis is not a valid explicit axis reference. " + REVOLVE_AXIS_DESCRIPTION
    )
    if not isinstance(value, dict) or not value:
        raise error
    kind = value.get("kind")
    if not isinstance(kind, str):
        raise error
    if kind == "axis":
        if type(value.get("id")) is not int or value["id"] < 0:
            raise error
    elif kind == "datum_axis_feature":
        if not isinstance(value.get("label"), str) or not value["label"]:
            raise error
    else:
        raise error
    return dict(value)


def validate_planar_reference(value: dict[str, Any], path: str) -> None:
    """Validate geometry-ID selection without changing legacy geometric filters."""
    if "id" in value:
        if any(key in value for key in ("axis", "normal", "offset")):
            raise ValueError(f"{path}: id cannot be combined with axis, normal or offset")
        if type(value["id"]) is not int or not 0 <= value["id"] <= 2147483647:
            raise ValueError(f"{path}.id must be a nonnegative 32-bit integer geometry ID")
        return
    if "normal" in value:
        normal = value["normal"]
        if (
            not isinstance(normal, list)
            or len(normal) != 3
            or any(type(item) not in (int, float) for item in normal)
            or sum(item * item for item in normal) < 1e-12
        ):
            raise ValueError(f"{path}.normal requires a nonzero 3D vector")
    elif value.get("axis", "z") not in ("x", "y", "z"):
        raise ValueError(f"{path}.axis must be x, y or z")


DATUM_PLANE_REFERENCE_KIND_DESCRIPTION = (
    "A datum_plane reference requires an explicit {kind:...} plane selection: "
    "{kind:'datum_plane',id:N}, an axis/normal filter such as "
    "{kind:'datum_plane',axis:'z'}, {kind:'plane',id:N}, {kind:'surface',id:N}, "
    "{kind:'datum_feature',label:'plane_label'} or the three-point form "
    "{kind:'through_points',points:[label_a,label_b,label_c]}. A dictionary "
    "without a string kind is rejected before a job is dispatched instead of "
    "failing inside the executor as a missing JSON key. The executor-internal "
    "{kind:'datum_point_feature',label:...} selection and the external "
    "{thru_points:[...]} spelling are not datum_plane references and are "
    "rejected before a job is dispatched; convert them to the through_points form. "
    "Only {kind:'datum_feature'} honours a label; the id/axis/normal forms are "
    "geometric and refuse one."
)

# Kinds the executor resolves geometrically (by id, axis or normal). A label on
# one of them used to be dropped silently: the 2026-11-04 trim probe submitted
# {kind:'datum_plane',label:'RIGHT'} and the default axis filter (axis z,
# offset 0) selected TOP, so the trim plane landed 20 mm away from the intended
# one and the feature never regenerated.
GEOMETRIC_PLANE_REFERENCE_KINDS = frozenset({"datum_plane", "plane", "surface"})

GEOMETRIC_PLANE_LABEL_DESCRIPTION = (
    "is a geometric plane reference and does not honour a label; the label would be "
    "dropped and the plane chosen by id/axis/normal filter. Use "
    "{kind:'datum_feature',label:'plane_label'} for a feature label, or keep the "
    "geometric form without the label"
)

THROUGH_POINTS_DESCRIPTION = (
    "The three-point form {kind:'through_points',points:[label_a,label_b,label_c]} "
    "takes exactly three distinct datum_points feature labels; each label must be "
    "created by a datum_points operation earlier in the same plan and define a "
    "single point. It cannot be combined with angle, axis or a nonzero offset."
)

# Mirrors schema.Label; kept local so this module stays importable by schema
# without a cycle (the same pattern as feature_state/assembly_replay).
_LABEL_PATTERN = r"^[a-z][a-z0-9_]{0,27}$"

DATUM_PLANE_REFERENCE_KINDS = frozenset(
    {"datum_plane", "plane", "surface", "datum_feature", "through_points"}
)


def validate_datum_plane_through_points(value: Any, path: str) -> None:
    """Validate the three-point reference shape before dispatch (FEAT-053).

    Three distinct datum_points feature labels only: no four-point fitting and
    no guessing a first point out of a multi-point feature. Whether each label
    really is an earlier single-point datum_points producer is checked at plan
    level in ``schema.validate_operations``.
    """
    error = f"{path}.points: " + THROUGH_POINTS_DESCRIPTION
    points = value.get("points")
    if not isinstance(points, list) or len(points) != 3:
        raise ValueError(error)
    for index, label in enumerate(points):
        if not isinstance(label, str) or not re.fullmatch(_LABEL_PATTERN, label):
            raise ValueError(
                f"{path}.points[{index}] must be a feature label string (lowercase start, "
                "[a-z0-9_], at most 28 characters); " + THROUGH_POINTS_DESCRIPTION
            )
    if len(set(points)) != 3:
        raise ValueError(
            f"{path}.points: three distinct labels are required; " + THROUGH_POINTS_DESCRIPTION
        )


def validate_datum_plane_reference_kind(value: Any, path: str) -> None:
    """Reject kindless or unknown datum_plane references before dispatch (BUG-094).

    The generic reference walk only inspects dictionaries that carry a kind, so a
    kindless reference used to reach the native executor and surface as a JSON
    missing-key error. FEAT-053 adds the through_points form and refuses the
    external/internal spellings that must go through explicit conversion first.
    A label on a geometric kind is refused rather than dropped (2026-11-04).
    """
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str) or not value["kind"]:
        raise ValueError(f"{path}: " + DATUM_PLANE_REFERENCE_KIND_DESCRIPTION)
    kind = value["kind"]
    if kind == "datum_point_feature":
        raise ValueError(
            f"{path}: {{kind:'datum_point_feature',label:...}} is the executor-internal "
            "single-point resolution target, not a datum_plane reference; convert it to "
            "{kind:'through_points',points:[label_a,label_b,label_c]}"
        )
    if kind not in DATUM_PLANE_REFERENCE_KINDS:
        raise ValueError(
            f"{path}: unsupported datum_plane reference kind '{kind}'; "
            + DATUM_PLANE_REFERENCE_KIND_DESCRIPTION
        )
    if kind in GEOMETRIC_PLANE_REFERENCE_KINDS and "label" in value:
        raise ValueError(f"{path}: {{kind:'{kind}',label:...}} {GEOMETRIC_PLANE_LABEL_DESCRIPTION}")
    if kind == "through_points":
        validate_datum_plane_through_points(value, path)


DATUM_PLANE_AXIS_DESCRIPTION = (
    "A datum_plane angle axis requires {kind:'axis',id:N} from model inspection or "
    "{kind:'datum_axis_feature',label:'axis_label'} created earlier in the same "
    "model. A plane reference such as {kind:'datum_plane',axis:'z'} and a "
    "datum_feature plane label are not rotation axes; the axis_pattern-only "
    "datum_feature alias does not apply here."
)


def validate_datum_plane_axis(value: Any, path: str) -> None:
    """Reject plane-like or malformed datum_plane angle axes before dispatch (BUG-094).

    The native executor resolves datum_feature to a plane surface, so accepting it
    here would silently angle the plane about a face instead of the intended axis.
    """
    error = f"{path}: " + DATUM_PLANE_AXIS_DESCRIPTION
    if not isinstance(value, dict):
        raise ValueError(error)
    kind = value.get("kind")
    if kind == "axis":
        if type(value.get("id")) is not int or value["id"] < 0:
            raise ValueError(error)
    elif kind == "datum_axis_feature":
        if not isinstance(value.get("label"), str) or not value["label"]:
            raise ValueError(error)
    else:
        raise ValueError(error)


def validate_sketch_plane_frame(value: dict[str, Any], path: str) -> None:
    """Check the dictionary wrapper and numeric frame before native resolution."""
    reference = value.get("reference")
    if not isinstance(reference, dict) or not isinstance(reference.get("kind"), str):
        raise ValueError(f"{path}.reference requires a {{kind:...}} support selection")
    for key in ("origin", "u_axis"):
        if key not in value:
            continue
        vector = value[key]
        if (
            not isinstance(vector, list)
            or len(vector) != 3
            or any(type(item) not in (int, float) for item in vector)
        ):
            raise ValueError(f"{path}.{key} requires a numeric 3D vector")
        if key == "u_axis" and sum(item * item for item in vector) < 1e-18:
            raise ValueError(f"{path}.u_axis must be a nonzero direction vector")


_REVOLVE_AXIS_SCHEMA = {
    "description": REVOLVE_AXIS_DESCRIPTION,
    "oneOf": [
        {
            "type": "object",
            "properties": {"kind": {"const": "axis"}, "id": {"type": "integer", "minimum": 0}},
            "required": ["kind", "id"],
        },
        {
            "type": "object",
            "properties": {
                "kind": {"const": "datum_axis_feature"},
                "label": {"type": "string", "minLength": 1},
            },
            "required": ["kind", "label"],
        },
    ],
}

RevolveAxis = Annotated[
    dict[str, Any], BeforeValidator(normalize_revolve_axis), WithJsonSchema(_REVOLVE_AXIS_SCHEMA)
]


def reference_capabilities() -> dict[str, Any]:
    """Keep the legacy example keys while spelling out each parameter's full shape."""
    plane = {"kind": "datum_plane", "axis": "z", "offset": 0}
    datum_plane_id = {"kind": "datum_plane", "id": 163}
    plane_id = {"kind": "plane", "id": 163}
    face = {"kind": "surface", "id": 11}
    edge = {"kind": "edge", "id": 12}
    axis = {"kind": "axis", "id": 83}
    axis_label = {"kind": "datum_axis_feature", "label": "axis_label"}
    return {
        "datum_plane": plane,
        "datum_plane_id": datum_plane_id,
        "plane_id": plane_id,
        "planar_solid_face": {"kind": "plane", "normal": [0, 0, 1], "offset": 10},
        "raw_face": face,
        "raw_edge": edge,
        "datum_label": {"kind": "datum_feature", "label": "plane_label"},
        "raw_axis": axis,
        "axis_label": axis_label,
        "syntax": {
            "single_selection": "A bare {kind:...} object, passed directly to the named parameter",
            "geometry_id": "Model geometry ID from inspection, not a feature ID",
            "plane_id": "datum_plane.id comes from datum_planes; plane.id must resolve to planar geometry. id excludes axis/normal/offset in that same reference object",
            "feature_label": "An MCP feature alias; use the geometry-specific kind",
            "datum_feature": "Normally a datum plane label; axis_pattern.axis accepts it as an axis-label compatibility alias",
            "example_ids": "IDs below are illustrative. Inspect the actual model and replace them; labels must exist in that model",
            "collection_vs_selection": "Round/chamfer sets and sketch supports contain selections; they are not interchangeable with a single selection",
        },
        "by_tool": {
            "creo_axis_pattern": {
                "axis": axis,
                "axis_label": axis_label,
                "compatibility_axis_label": {"kind": "datum_feature", "label": "axis_label"},
                "compatibility_normalized_to": "datum_axis_feature",
                "requires": "A geometric axis, preceding the leader. A plane's axis/normal does not define a rotation axis",
            },
            "creo_datum_plane": {
                "reference": plane,
                "reference_by_id": datum_plane_id,
                "axis": axis,
            },
            "creo_datum_axis": {
                "references": [{"kind": "datum_plane", "axis": "x"}, plane],
                "references_by_id": [datum_plane_id, {"kind": "datum_plane", "id": 164}],
                "alternative": "A cylindrical face, straight edge or existing axis, subject to actual geometry",
            },
            "creo_datum_csys": {"reference": {"kind": "default_csys"}},
            "creo_datum_points": {"reference": {"kind": "default_csys"}},
            "creo_revolve": {
                "axis": axis_label,
                "axis_geometry_id": axis,
                "omitted_or_null": "Revolve about the sketch's construction centerline; "
                "the sketch must contain exactly one centerline",
                "requires": "A bare axis selection when supplied; the axis_pattern "
                "datum_feature alias does not apply, and structures without kind "
                "(including {entity:'ax'}) are rejected before a job is dispatched",
            },
            "creo_hole": {
                "placement": face,
                "reference1": {"kind": "datum_plane", "axis": "x"},
                "reference2": {"kind": "datum_plane", "axis": "y"},
            },
            "creo_draft": {"surfaces": [face], "neutral_plane": plane, "pull_direction": axis},
            "creo_boolean_bodies": {
                "targets": [{"kind": "body", "id": 1}],
                "tools": [{"kind": "body", "id": 2}],
                "requires": "Explicit distinct body IDs, not feature IDs",
            },
            "creo_solidify": {
                "reference": plane,
                "example_mode": "cut",
                "quilt_reference": {"kind": "quilt_feature", "label": "fill_label"},
                "limits": "Quilt add/cut still requires actual geometry and installation-specific acceptance",
            },
            "creo_surface_fill": {
                "sketch": "closed_profile",
                "requires": "Sketch feature label or feature ID, not a {kind:...} selection object",
            },
            "creo_thicken": {"reference": {"kind": "quilt_feature", "label": "fill_label"}},
            "creo_surface_trim": {
                "target": {"kind": "quilt", "id": 21},
                "target_by_label": {"kind": "quilt_feature", "label": "blade_quilt"},
                "tool_quilt": {"kind": "quilt", "id": 22},
                "tool_quilt_by_label": {"kind": "quilt_feature", "label": "trim_fill"},
                "tool_datum_plane": {"kind": "datum_plane", "label": "FRONT"},
                "tool_curve": {"kind": "curve", "id": 41},
                "keep_side": {
                    "values": ["one", "two"],
                    "meaning": (
                        "one/two name the retained region, not a GUI view; the receipt's "
                        "kept_side_basis.side_reference is 'tool_plane_normal' for a quilt "
                        "or datum-plane tool and 'curve_direction' for a curve tool, where "
                        "reversing the curve swaps the retained region. tool_normal is a "
                        "real vector only for a datum-plane tool"
                    ),
                },
                "requires": (
                    "one quilt target and one tool: a quilt ({kind:'quilt',id:N} or "
                    "{kind:'quilt_feature',label:...}), a datum plane by label only, or a "
                    "curve geometry id; target and tool must differ, and one tool only"
                ),
                "rejected": {
                    "labels_on_geometry_kinds": (
                        "geometry kinds take no label: {kind:'quilt',label:...} and "
                        "{kind:'curve',label:...} are refused; use quilt_feature for a "
                        "quilt label and the curve geometry id for a curve"
                    ),
                    "datum_plane_id": (
                        "{kind:'datum_plane',id:N} is refused for tool: a datum-plane tool "
                        "requires a label"
                    ),
                    "plane_surface_body_kinds": (
                        "{kind:'plane'}, {kind:'surface'} and {kind:'body'} are not quilts "
                        "and are refused as target or tool"
                    ),
                    "tool_lists": "a list of tools is refused; trim takes exactly one tool",
                    "execute_plan_offset_mm": SURFACE_TRIM_OFFSET_LIMIT,
                },
            },
            "creo_project_curve": {
                "target": {"kind": "quilt", "id": 21},
                "target_by_label": {"kind": "quilt_feature", "label": "blade_quilt"},
                "source": {"kind": "curve", "id": 7},
                "direction_plane_label": {"kind": "datum_feature", "label": "TOP"},
                "direction_axis_label": {"kind": "datum_axis_feature", "label": "axis_label"},
                "direction_curve": {"kind": "curve", "id": 8},
                "side": {
                    "values": ["positive", "negative"],
                    "meaning": (
                        "flips the vector read from direction_ref; the reported basis is "
                        "measured, not named after a GUI view"
                    ),
                },
                "construction": (
                    "the projection is built as a real sweep of the source sketch along "
                    "the direction plus the documented intersect curve, so the model also "
                    "gains a helper surface feature reported as helper_feature_id; the "
                    "direction must be parallel to the source sketch plane normal, the "
                    "target must lie on the requested side, and the source curve must "
                    "belong to a curve feature"
                ),
                "requires": (
                    "one quilt target ({kind:'quilt',id:N} or "
                    "{kind:'quilt_feature',label:...}), one source curve geometry id, and "
                    "one direction reference that yields a real vector"
                ),
                "rejected": {
                    "source_label": (
                        "{kind:'curve',label:...} is refused: a sketch feature may own "
                        "several curves, so the source must be one curve geometry id"
                    ),
                    "edge_or_axis_source": (
                        "{kind:'edge',id:N} and {kind:'axis',id:N} are not projection "
                        "sources; source accepts only {kind:'curve',id:N}"
                    ),
                    "direction_datum_plane": (
                        "{kind:'datum_plane',label:...} is refused for direction_ref: that "
                        "resolver drops the label and picks the default plane; use "
                        "{kind:'datum_feature',label:...} for a plane feature"
                    ),
                    "raw_vector": (
                        "a bare [x,y,z] vector or an unsupported kind is refused; the "
                        "direction must come from a datum plane/axis label or a curve id"
                    ),
                    "target_surface_kind": (
                        "{kind:'surface'}, {kind:'plane'} and {kind:'body'} are not quilts "
                        "and are refused as target"
                    ),
                },
            },
            "creo_surface_offset": {
                "reference": {"kind": "quilt", "id": 21},
                "reference_by_label": {"kind": "quilt_feature", "label": "fill_label"},
                "distance": 5.0,
                "side": {
                    "values": ["positive", "negative"],
                    "meaning": (
                        "explicit offset side; the receipt echoes the requested side, and "
                        "the geometric z sign is not read back"
                    ),
                },
                "result": (
                    "an offset wall that can add solid volume, not a standalone offset quilt. "
                    "target_quilt_id identifies the source quilt, not a new downstream quilt. "
                    "The distance is measured from volume/area only for a single planar source "
                    "in an initially empty model; other cases return null with "
                    "offset_distance_status. Use creo_thicken / creo_solidify for their "
                    "separate quilt-to-solid operations"
                ),
                "requires": "one quilt reference; a closed quilt is not required",
                "rejected": {
                    "labels_on_geometry_kinds": (
                        "{kind:'quilt',label:...} is refused; use "
                        "{kind:'quilt_feature',label:...} for a feature label"
                    ),
                    "body_datum_plane_surface_kinds": (
                        "{kind:'body'}, {kind:'datum_plane'}, {kind:'plane'} and "
                        "{kind:'surface'} are not quilts and are refused"
                    ),
                    "offset_mm": (
                        "offset_mm is not a creo_surface_offset parameter; this tool takes "
                        "distance. surface_trim's offset_mm is a different, gated route: "
                        + SURFACE_TRIM_OFFSET_LIMIT
                    ),
                },
            },
            "creo_surface_round": {
                "target": {"kind": "quilt", "id": 21},
                "target_by_label": {"kind": "quilt_feature", "label": "fill_label"},
                "references": [
                    {"surfaces": [{"kind": "surface", "id": 68}, {"kind": "surface", "id": 66}]}
                ],
                "radius": 3.0,
                "requires": (
                    "one quilt target and exactly one reference set holding exactly two "
                    "distinct member faces of that quilt; each face is "
                    "{kind:'surface',id:N} with a geometry id from creo_inspect_model, and "
                    "the radius is one finite constant greater than zero"
                ),
                "rejected": {
                    "multiple_sets": "a second set or a second radius is refused before a job",
                    "edge_chain": (
                        "{'edge':...} and PRO_ROUND_REF_EDGE chains are refused; there is no "
                        "quilt edge id channel in creo_inspect_model, whose edges enumerate "
                        "solid faces only"
                    ),
                    "variable_or_named_radius": (
                        "variable radius, full/chordal/through-curve radius and custom "
                        "transitions have no field on this operation"
                    ),
                    "solid_or_other_quilt_face": (
                        "a face that the target quilt does not own (a solid face or another "
                        "quilt's face) is refused natively before the feature is created"
                    ),
                },
                "adjacency": (
                    "the two faces must share one edge, and the kernel decides it: the "
                    "2026-11-08 H08 probe measured a non-adjacent pair failing regeneration "
                    "and rolling back instead of being accepted"
                ),
                "result": (
                    "the round stays on the same quilt (quilt_id unchanged, open by nature); "
                    "the receipt carries measured face counts and areas before/after with "
                    "their statuses, closure, radius and the solid-face evidence"
                ),
            },
            "creo_loft": {
                "sections": ["section_a", 42],
                "mode": {"values": ["add"], "meaning": "cut and surface are refused before a job"},
                "surface_mode": (
                    "not available: mode='surface' is refused together with 'cut' and "
                    "new_body=true by capabilities.require_available; there is no "
                    "creo_surface_loft tool and no surface_loft registered operation, and "
                    "multi-section/boundary-blend surfaces stay unpublished"
                ),
                "requires": (
                    "sketch labels or integer feature IDs ordered by increasing Z, plus the "
                    "resolved Blend callback registration"
                ),
            },
            "creo_sheetmetal_flange": {
                "edge": edge,
                "requires": (
                    "Edge selection: {kind:'edge',id:N} with the current id from "
                    "creo_inspect_model, or {kind:'edge_geometry',endpoints_mm:"
                    "[[x,y,z],[x,y,z]],tolerance_mm:1e-6} matching exactly one straight "
                    "model edge; no extra reference/edge wrapper"
                ),
            },
            "creo_round": {
                "references": [{"edge": edge}],
                "surface_pair_alternative": [{"surfaces": [face, {"kind": "surface", "id": 13}]}],
                "requires": "A list of sets: each set contains edge or two surfaces. A list of bare edge selections is not a set list",
            },
            "creo_chamfer": {
                "references": [{"edge": edge}],
                "surface_pair_alternative": [{"surfaces": [face, {"kind": "surface", "id": 13}]}],
                "requires": "Same set structure as creo_round",
            },
            "creo_create_sketch": {
                "plane": {"reference": plane, "origin": [0, 0, 0], "u_axis": [1, 0, 0]},
                "plane_by_datum_id": {"reference": datum_plane_id, "u_axis": [0, 0, 1]},
                "plane_by_geometry_id": {"reference": plane_id, "u_axis": [0, 0, 1]},
                "plane_by_label": {
                    "reference": {"kind": "datum_feature", "label": "plane_label"},
                    "u_axis": [0, 0, 1],
                },
                "alternative": "XY/XZ/YZ string for a principal plane",
                "requires": "For a dictionary plane, put the support selection under reference; origin/u_axis are optional frame fields. Use geometry IDs from inspection, not feature IDs; id excludes axis/normal/offset in the same selection",
            },
        },
    }
