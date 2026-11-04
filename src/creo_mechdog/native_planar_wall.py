"""FEAT-058: native rectangular planar (first) wall contract.

Creo Toolkit builds the primary sheetmetal wall as the *unattached planar wall*:
the Fill feature (``PRO_FEAT_DATUM_SURF`` + ``PRO_FLAT``) carrying the sheetmetal
branch (``PRO_E_IS_UNATTACHED_WALL``, ``PRO_E_BODY_USE=PRO_BODY_USE_NEW``,
``PRO_E_SMT_NEW_BODY_LINKED``). Measurements on Creo 12.4.0.0 (2026-11-04,
``docs/work-items/FEAT-058.md``) fixed three consequences that this module
freezes:

* only a sheetmetal part can host the tree - the same tree in a solid part is
  created but fails regeneration - and the wall is the *first* wall, so the part
  must still be empty;
* the wall keeps its feature identity when the rectangle is resized, because the
  resize drives the driving sketch's coordinate dimensions instead of rebuilding
  the wall;
* length runs along the sketch u axis, width along v and thickness along the
  signed sketch normal, so the envelope must be reported in that frame. A sorted
  world bounding box cannot prove the axes, which is why every judgement here
  works on signed frame coordinates.

This module is admission and judgement only: geometry, thickness read-back and
the envelope come from the native executor, and nothing here re-derives a
measurement it did not receive.
"""

from __future__ import annotations

from typing import Any

PLANAR_WALL_OP = "sheetmetal_planar_wall"
PLANAR_WALL_RESIZE_OP = "resize_sheetmetal_planar_wall"
SKETCH_SUFFIX = "_sk"
# A rectangle is four lines with four corners; fewer point dimensions leave the
# section under-constrained and must never be reported as a verified wall.
MIN_RECTANGLE_DIMENSIONS = 4
ENVELOPE_TOLERANCE_MM = 1e-6


def sketch_label(label: str) -> str:
    """Driving sketch label for a planar wall (a real Creo feature name)."""
    return f"{label}{SKETCH_SUFFIX}"


def create_problem(model: dict[str, Any] | None) -> str | None:
    """Why a new planar wall cannot be created here, or None when it may be."""
    if model is None:
        return None
    if model.get("model_type") != "sheetmetal":
        return (
            "sheetmetal_planar_wall requires an MCP sheetmetal model: the native "
            "unattached planar wall only regenerates in a sheetmetal part"
        )
    summary = model.get("inspection_summary") or {}
    if summary.get("has_solid"):
        return (
            "sheetmetal_planar_wall creates the first wall; this model already has "
            "geometry. Create a new sheetmetal model with the native planar template"
        )
    return None


def resize_problem(
    model: dict[str, Any] | None,
    operation: dict[str, Any],
    aliases: dict[str, Any] | None = None,
    features: list[dict[str, Any]] | None = None,
) -> str | None:
    """Why this planar wall cannot be resized, or None when it may be.

    ``features`` is the saved inspection list; when it is supplied a recorded
    child means a downstream feature depends on the wall and the in-place resize
    is refused instead of being attempted.
    """
    if model is not None and model.get("model_type") != "sheetmetal":
        return "resizing a planar wall requires an MCP sheetmetal model"
    label = operation.get("feature")
    entry = (aliases or {}).get(label) if isinstance(label, str) else None
    if not isinstance(entry, dict):
        return f"Unknown planar wall label: {label!r}"
    if entry.get("op") != PLANAR_WALL_OP:
        return (
            f"Feature {label!r} was created by {entry.get('op')!r}; only walls created "
            f"by {PLANAR_WALL_OP} can be resized in place"
        )
    feature_id = entry.get("feature_id")
    children = _children_of(features, feature_id)
    if children:
        return (
            f"Feature {label!r} has downstream dependencies ({children}); the in-place "
            "resize is refused so those features are not silently rebuilt"
        )
    return None


def _children_of(features: list[dict[str, Any]] | None, feature_id: Any) -> list[int]:
    if not isinstance(features, list) or not isinstance(feature_id, int):
        return []
    for feature in features:
        if not isinstance(feature, dict) or feature.get("id") != feature_id:
            continue
        children = feature.get("child_ids")
        if isinstance(children, list):
            return [child for child in children if isinstance(child, int)]
        return []
    return []


def validate_plan(
    model: dict[str, Any] | None,
    operations: list[dict[str, Any]],
    aliases: dict[str, Any] | None = None,
    features: list[dict[str, Any]] | None = None,
) -> None:
    """Raise ValueError before a job exists when a planar-wall plan is inadmissible."""
    for operation in operations:
        kind = operation.get("op")
        problem: str | None = None
        if kind == PLANAR_WALL_OP:
            problem = create_problem(model)
        elif kind == PLANAR_WALL_RESIZE_OP:
            problem = resize_problem(model, operation, aliases, features)
        if problem:
            raise ValueError(problem)


# --- signed frame envelope ---------------------------------------------------


def signed_extents(frame: dict[str, Any], bounds: list[list[float]]) -> dict[str, dict[str, float]]:
    """Signed extents of an axis-aligned box measured along the sketch frame.

    Used as the independent Python oracle for the native envelope. Every corner
    is projected onto u/v/n and the minimum/maximum are kept *with their signs*,
    so a swapped or sorted box cannot pass.
    """
    origin = _vector(frame, "origin")
    axes = _frame_axes(frame)
    low, high = bounds
    extents: dict[str, dict[str, float]] = {}
    for name, axis in axes.items():
        values = []
        for corner in _corners(low, high):
            offset = [corner[i] - origin[i] for i in range(3)]
            values.append(sum(offset[i] * axis[i] for i in range(3)))
        extents[name] = {"min": min(values), "max": max(values)}
    return extents


def _frame_axes(frame: dict[str, Any]) -> dict[str, list[float]]:
    return {
        "u": _vector(frame, "u_axis"),
        "v": _vector(frame, "v_axis"),
        "n": _vector(frame, "normal"),
    }


def _corners(low: list[float], high: list[float]) -> list[list[float]]:
    return [
        [
            low[0] if i & 1 == 0 else high[0],
            low[1] if i & 2 == 0 else high[1],
            low[2] if i & 4 == 0 else high[2],
        ]
        for i in range(8)
    ]


def _vector(frame: dict[str, Any], key: str) -> list[float]:
    value = frame.get(key)
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"planar wall frame is missing a three-element {key}")
    return [float(component) for component in value]


def envelope_problem(
    frame: dict[str, Any] | None,
    envelope: dict[str, Any] | None,
    length: float,
    width: float,
    thickness: float,
    tolerance: float = ENVELOPE_TOLERANCE_MM,
) -> str | None:
    """Why the reported frame envelope does not prove the requested rectangle."""
    if not isinstance(frame, dict):
        return "the planar wall result carries no sketch frame"
    if not isinstance(envelope, dict):
        return "the planar wall result carries no frame envelope"
    expected = {"u": length, "v": width, "n": thickness}
    for axis, requested in expected.items():
        entry = envelope.get(axis)
        if not isinstance(entry, dict) or "min" not in entry or "max" not in entry:
            return f"envelope is missing the {axis} extent"
        low, high = entry["min"], entry["max"]
        if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
            return f"envelope {axis} extent is not numeric"
        if low > high:
            return f"envelope {axis} extent is not a signed interval ({low} > {high})"
        measured = high - low
        if abs(measured - requested) > max(tolerance, abs(requested) * tolerance):
            return (
                f"envelope {axis} extent {measured:.9f} mm does not match the requested "
                f"{requested:.9f} mm"
            )
    axes = _frame_axes(frame)
    for name, axis in axes.items():
        norm = sum(component * component for component in axis) ** 0.5
        if abs(norm - 1) > 1e-6:
            return f"frame {name} is not a unit vector (|{name}|={norm:.9f})"
    for first, second in (("u", "v"), ("u", "n"), ("v", "n")):
        dot = sum(axes[first][i] * axes[second][i] for i in range(3))
        if abs(dot) > 1e-6:
            return f"frame {first} and {second} are not orthogonal (dot={dot:.9f})"
    return None


def result_projection(result: dict[str, Any]) -> dict[str, Any]:
    """Public view of a native planar wall result, with its own verdict.

    ``verified`` is true only when the native result carries the feature, the
    four rectangle dimensions, the frame and an envelope that matches the
    requested size. A square wall is reported as such instead of being merged
    into one dimension.
    """
    length = _number(result, "length")
    width = _number(result, "width")
    thickness = _number(result, "thickness")
    projection: dict[str, Any] = {
        "op": result.get("op"),
        "feature": result.get("feature"),
        "feature_id": result.get("feature_id"),
        "sketch": result.get("sketch"),
        "length": length,
        "width": width,
        "thickness": thickness,
        "square": bool(length is not None and width is not None and abs(length - width) <= 1e-9),
        "dimension_count": result.get("dimension_count"),
        "volume_mm3": result.get("volume_mm3"),
        "frame": result.get("frame"),
        "envelope": result.get("envelope"),
        "sheetmetal_body": result.get("sheetmetal_body"),
        "thickness_source": result.get("thickness_source"),
    }
    if result.get("op") == PLANAR_WALL_RESIZE_OP:
        projection["feature_id_unchanged"] = result.get("feature_id_before") == result.get(
            "feature_id"
        )
    problems: list[str] = []
    if not isinstance(projection["feature_id"], int):
        problems.append("the native result carries no feature id")
    dimensions = projection["dimension_count"]
    if not isinstance(dimensions, int) or dimensions < MIN_RECTANGLE_DIMENSIONS:
        problems.append(
            "the rectangle is not fully dimensioned "
            f"({dimensions!r} < {MIN_RECTANGLE_DIMENSIONS} point dimensions)"
        )
    if result.get("op") == PLANAR_WALL_RESIZE_OP and not projection["feature_id_unchanged"]:
        problems.append("the resize changed the wall feature identity")
    if length is not None and width is not None and thickness is not None:
        envelope = envelope_problem(
            projection["frame"], projection["envelope"], length, width, thickness
        )
        if envelope:
            problems.append(envelope)
    projection["problems"] = problems
    projection["verified"] = not problems
    return projection


def annotate_result(result: dict[str, Any]) -> None:
    """Attach the planar wall verdict to a job result in place.

    The MCP tools return the queued job, so the verdict has to travel with the
    result the client polls on creo_get_job. A failed wall publishes its
    problems instead of hiding them behind the job status.
    """
    if not isinstance(result, dict):
        return
    operations = result.get("operations")
    if not isinstance(operations, list):
        return
    for item in operations:
        if isinstance(item, dict) and item.get("op") in (PLANAR_WALL_OP, PLANAR_WALL_RESIZE_OP):
            result["planar_wall"] = result_projection(item)
            return


def _number(result: dict[str, Any], key: str) -> float | None:
    value = result.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
