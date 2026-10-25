"""Tool-specific reference contracts and compatibility for angular pattern axes."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BeforeValidator, WithJsonSchema

AXIS_DESCRIPTION = (
    "Bare axis selection: {kind:'axis',id:N} from model inspection, or "
    "{kind:'datum_axis_feature',label:'axis_label'}. In axis_pattern only, "
    "{kind:'datum_feature',label:'axis_label'} is a compatibility alias for "
    "datum_axis_feature. A plane normal such as {kind:'datum_plane',axis:'z'} "
    "is not a rotation axis. Do not wrap this selection in reference/edge."
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
    face = {"kind": "surface", "id": 11}
    edge = {"kind": "edge", "id": 12}
    axis = {"kind": "axis", "id": 83}
    axis_label = {"kind": "datum_axis_feature", "label": "axis_label"}
    return {
        "datum_plane": plane,
        "planar_solid_face": {"kind": "plane", "normal": [0, 0, 1], "offset": 10},
        "raw_face": face,
        "raw_edge": edge,
        "datum_label": {"kind": "datum_feature", "label": "plane_label"},
        "raw_axis": axis,
        "axis_label": axis_label,
        "syntax": {
            "single_selection": "A bare {kind:...} object, passed directly to the named parameter",
            "geometry_id": "Model geometry ID from inspection, not a feature ID",
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
            "creo_datum_plane": {"reference": plane, "axis": axis},
            "creo_datum_axis": {
                "references": [{"kind": "datum_plane", "axis": "x"}, plane],
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
            "creo_sheetmetal_flange": {
                "edge": edge,
                "requires": "Bare edge selection; pass edge={kind:'edge',id:N}, without an extra reference/edge wrapper",
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
                "alternative": "XY/XZ/YZ string for a principal plane",
                "requires": "For a dictionary plane, put the support selection under reference; origin/u_axis are optional frame fields",
            },
        },
    }
