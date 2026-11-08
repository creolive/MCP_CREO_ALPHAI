"""DEV-078 offline preparation for routes that still need native evidence.

These helpers never submit jobs, inspect the session, or manufacture seed
files. Analytic expectations are oracles for a later run, not measurements.
"""

from __future__ import annotations

import math
from pathlib import PureWindowsPath
from typing import Any

from pydantic import TypeAdapter

from creo_mechdog.capabilities import require_available
from creo_mechdog.schema import validate_operations
from creo_mechdog.schema_base import Label

_LABEL = TypeAdapter(Label)


def grille_cut_recipe(*, rows: int = 1, columns: int = 1) -> dict[str, Any]:
    """Prepare 6x4 holes on a 100x60x1 native planar wall, in mm.

    Explicit coordinates and a mid-thickness sketch remove dependence on the
    conversion wall's orientation. Start with one hole before the 3x3 case.
    """
    for name, value in (("rows", rows), ("columns", columns)):
        if type(value) is not int or not 1 <= value <= 3:
            raise ValueError(f"{name} must be an integer between 1 and 3")
    entities = []
    for row in range(rows):
        for column in range(columns):
            x, y = 10.0 + 12.0 * column, 10.0 + 10.0 * row
            entities.append(
                {
                    "type": "rectangle",
                    "name": f"slot_{row}_{column}",
                    "min": [x, y],
                    "max": [x + 6.0, y + 4.0],
                }
            )
    operations = [
        {
            "op": "sheetmetal_planar_wall",
            "label": "grille_base",
            "plane": "XY",
            "length": 100.0,
            "width": 60.0,
            "thickness": 1.0,
            "origin": [0.0, 0.0],
        },
        {
            "op": "sketch",
            "label": "grille_sk",
            "plane": "XY",
            "offset": 0.5,
            "dimensioning": "coordinates",
            "entities": entities,
        },
        {
            "op": "extrude",
            "label": "grille_cut",
            "sketch": "grille_sk",
            "mode": "cut",
            "depth_type": "through_all",
            "direction": "symmetric",
        },
    ]
    require_available(validate_operations(operations))
    return {
        "route": "grille_cut",
        "status": "static_only",
        "native_validation": "not_run",
        "preparation": {"tool": "creo_new_sheetmetal", "arguments": {"template": "native_planar"}},
        "operations": operations,
        "oracle": {
            "source": "analytic_expected_not_measured",
            "initial_volume_mm3": 6000.0,
            "expected_removed_volume_mm3": float(rows * columns * 24),
            "expected_final_volume_mm3": float(6000 - rows * columns * 24),
        },
        "acceptance": [
            "actual holes and volume reduction",
            "sheetmetal body and gauge retained",
            "saved_file_reloaded_and_verified=true",
            "failed cut restores revision and volume",
        ],
    }


def reference_route(route: str) -> dict[str, Any]:
    """Describe the real reference specimen required before a UDF can be bound."""
    if route == "standard_quilt_offset":
        acceptance = [
            "source quilt remains unchanged and a separate offset quilt exists",
            "normal distance verified on curved surfaces; e.g. outward R8 sphere +2 gives R10",
            "no solid body created; save/reload and source-edit propagation verified",
            "self-intersection and excessive offset fail with rollback",
        ]
        sample = "Create a successful standard Surface Offset specimen in Creo, then dump its feature tree or save an inspectable UDF."
    elif route == "punch_die_form":
        acceptance = [
            "reference punch/die part and placement coordinate systems are explicit",
            "result remains the intended sheetmetal body with the original gauge",
            "native form flatten/unflatten behavior verified; do not assume ordinary unbend flattens a form",
            "save/reload, tool/source edit propagation and failure rollback verified",
        ]
        sample = "Create a successful Punch/Die reference-tool specimen in Creo; inspect its actual UDF prompts and variable dimensions."
    else:
        raise ValueError(f"Unknown reference route: {route}")
    return {
        "route": route,
        "status": "pending_reference",
        "native_validation": "not_run",
        "operations": [],
        "required_sample": sample,
        "capture": {
            "tool": "creo_dump_feature_tree",
            "feature": "actual successful feature label or id",
        },
        "acceptance": acceptance,
    }


def udf_placement_recipe(
    route: str,
    *,
    file_path: str,
    references: dict[str, dict[str, Any]],
    dimensions: dict[str, float],
) -> dict[str, Any]:
    """Validate a proposed binding; actual UDF file/prompt compatibility is pending.

    Exact prompt/dimension names must come from creo_inspect_udf. This does not
    read a file or assert that it exists, and does not make a native request.
    """
    result = reference_route(route)
    if not isinstance(file_path, str):
        raise ValueError("file_path must be an absolute local Windows .gph path")
    path = PureWindowsPath(file_path)
    if (
        not path.is_absolute()
        or not path.drive.endswith(":")
        or path.suffix.lower() != ".gph"
        or "://" in file_path
        or any(part == ".." for part in path.parts)
    ):
        raise ValueError("file_path must be an absolute local Windows .gph path")
    if not isinstance(references, dict) or not references:
        raise ValueError("references must bind the exact nonempty prompts from creo_inspect_udf")
    for prompt, ref in references.items():
        if not isinstance(prompt, str) or not prompt.strip() or not isinstance(ref, dict):
            raise ValueError("UDF prompt names and reference objects must be explicit")
        kind = ref.get("kind")
        if kind in {
            "quilt",
            "surface",
            "edge",
            "body",
            "csys",
            "point",
            "axis",
            "curve",
            "datum_plane",
        }:
            if (
                set(ref) != {"kind", "id"}
                or type(ref["id"]) is not int
                or not 0 <= ref["id"] < 2**31
            ):
                raise ValueError(
                    "UDF geometry references require kind and a nonnegative 32-bit integer id"
                )
        elif kind in {
            "quilt_feature",
            "datum_feature",
            "datum_csys_feature",
            "datum_point_feature",
        }:
            if (
                set(ref) != {"kind", "label"}
                or not isinstance(ref["label"], str)
                or not ref["label"]
            ):
                raise ValueError("UDF feature references require an explicit label")
            _LABEL.validate_python(ref["label"])
        elif kind == "default_csys":
            if set(ref) != {"kind"}:
                raise ValueError("default_csys reference accepts only kind")
        else:
            raise ValueError(f"Unsupported UDF reference kind: {kind}")
    if not isinstance(dimensions, dict):
        raise ValueError("dimensions must be an object keyed by actual UDF dimension names")
    for name, value in dimensions.items():
        try:
            finite_number = type(value) in (int, float) and math.isfinite(float(value))
        except OverflowError:
            finite_number = False
        if not isinstance(name, str) or not name.strip() or not finite_number:
            raise ValueError("UDF dimensions must have exact names and finite numeric values")
    operations = validate_operations(
        [
            {
                "op": "udf_create",
                "label": "reference_route",
                "file_path": file_path,
                "references": references,
                "dimensions": dimensions,
            }
        ]
    )
    require_available(operations)
    result.update(
        {
            "status": "static_only",
            "operations": operations,
            "file_validation": "not_run",
            "prerequisites": [
                {
                    "tool": "creo_inspect_udf",
                    "arguments": {"file_path": file_path},
                    "must_match": "exact reference prompts, types and variable dimension names",
                }
            ],
        }
    )
    return result
