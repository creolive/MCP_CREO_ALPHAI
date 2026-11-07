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
  works on signed frame coordinates;
* the rectangle starts at the sketch origin and the gauge grows one side of the
  plane, so the accepted interval is signed - u[0,L], v[0,W] and n[0,t] or
  n[-t,0]. A span-only comparison accepted a wall that grew on the opposite side
  at an offset origin (review, 2026-11-04). R10 adds a sketch-local
  ``origin=[u0,v0]`` so the first wall can start at u0,v0: the named-plane frame
  and the growth direction are unchanged and the interval moves with the
  rectangle (u[u0,u0+L], v[v0,v0+W]); a resize keeps the recorded origin;
* the gauge is read back from the wall's own body, and the resize re-reads it
  before editing, so neither the request nor a stored record stands in for a
  measurement. When the SDK declares no body gauge API, the wall's own measured
  material extent along the frame normal is the independent source
  (``geometry_normal_span``) for a unique material body, a pure rectangle and an
  axis-aligned frame; the driving size, signed envelope and volume stay
  cross-checks. A missing API boolean is therefore not required for verification,
  and an API that exists but fails never falls back;
* every operation publishes a gauge receipt (status, source, value, reason and
  context). The resize context follows execution order: a wall created earlier
  in the same plan is ``current_plan``, not ``saved_loaded`` (R03, 2026-11-06).

This module is admission and judgement only: geometry, thickness read-back and
the envelope come from the native executor, and nothing here re-derives a
measurement it did not receive.
"""

from __future__ import annotations

import math
from typing import Any

PLANAR_WALL_OP = "sheetmetal_planar_wall"
PLANAR_WALL_RESIZE_OP = "resize_sheetmetal_planar_wall"
SKETCH_SUFFIX = "_sk"
# A rectangle is four lines with four corners; fewer point dimensions leave the
# section under-constrained and must never be reported as a verified wall.
MIN_RECTANGLE_DIMENSIONS = 4
ENVELOPE_TOLERANCE_MM = 1e-6
VOLUME_TOLERANCE = 1e-6
ABSOLUTE_VOLUME_TOLERANCE_MM3 = 0.01
DIRECTIONS = ("positive", "negative")
#: Gauge receipt vocabulary (FEAT-058/R03). ``status`` says what the evidence
#: supports, ``source`` says where the number came from and ``context`` ties the
#: block to this plan or to the file the resize re-read.
VALIDATION_STATUSES = ("verified", "unverified", "mismatch", "unavailable")
VALIDATION_SOURCES = ("api", "geometry_normal_span", "missing_api", "not_measured")
#: A verified receipt may only come from a source that measured the wall: the
#: body API or, when the SDK declares none, the wall's own measured geometry.
TRUSTED_SOURCES = ("api", "geometry_normal_span")
CONTEXTS = ("current_plan", "saved_loaded")
PLAN_CONTEXT = "current_plan"
SAVED_CONTEXT = "saved_loaded"


def sketch_label(label: str) -> str:
    """Driving sketch label for a planar wall (a real Creo feature name)."""
    return f"{label}{SKETCH_SUFFIX}"


def internal_labels(operation: dict[str, Any]) -> tuple[str, ...]:
    """Feature names this operation creates besides its own label.

    A planar wall creates its driving sketch as ``<label>_sk``. That name is a
    real Creo feature name and enters the managed alias table, so it has to take
    part in duplicate, plan-collision and tombstone protection exactly like the
    label itself.
    """
    if operation.get("op") != PLANAR_WALL_OP:
        return ()
    label = operation.get("label")
    if not isinstance(label, str) or not label:
        return ()
    return (sketch_label(label),)


def declared_names(operations: list[dict[str, Any]]) -> list[str]:
    """Every managed feature name a plan introduces, labels and internal names."""
    names: list[str] = []
    for operation in operations:
        label = operation.get("label")
        if isinstance(label, str):
            names.append(label)
        names.extend(internal_labels(operation))
    return names


def name_conflict(names: list[str], reserved: set[str]) -> list[str]:
    """Names that are already taken, either by an alias or earlier in this plan."""
    conflicts: set[str] = set()
    seen: set[str] = set()
    for name in names:
        if name in reserved or name in seen:
            conflicts.add(name)
        seen.add(name)
    return sorted(conflicts)


def create_problem(
    model: dict[str, Any] | None,
    aliases: dict[str, Any] | None = None,
    operation: dict[str, Any] | None = None,
) -> str | None:
    """Why a new planar wall cannot be created here, or None when it may be."""
    if model is not None:
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
    if operation is not None and aliases is not None:
        label = operation.get("label")
        taken = [name for name in (label, *internal_labels(operation)) if name in aliases]
        if taken:
            return (
                f"sheetmetal_planar_wall would create {sorted(taken)}, but that feature name "
                "already exists in this model; managed labels are never overwritten"
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
    """Raise ValueError before a job exists when a planar-wall plan is inadmissible.

    Operations are walked in order and the labels an earlier operation will
    create are visible to a later one, so ``create -> resize`` inside one plan is
    admitted instead of being refused as an unknown label. Feature ids are not
    known before execution, so a plan-local wall carries only its operation kind.
    """
    known: dict[str, Any] = dict(aliases or {})
    for operation in operations:
        kind = operation.get("op")
        problem: str | None = None
        if kind == PLANAR_WALL_OP:
            problem = create_problem(model, known, operation)
            label = operation.get("label")
            if problem is None and isinstance(label, str):
                known.setdefault(label, {"op": PLANAR_WALL_OP, "plan_local": True})
        elif kind == PLANAR_WALL_RESIZE_OP:
            problem = resize_problem(model, operation, known, features)
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


def expected_intervals(
    length: float,
    width: float,
    thickness: float,
    direction: str,
    origin: tuple[float, float] = (0.0, 0.0),
) -> dict[str, tuple[float, float]]:
    """Signed envelope the wall must occupy, measured along the sketch frame.

    The rectangle starts at the sketch-local ``origin`` and the gauge grows one
    side of the sketch plane, so the accepted interval keeps its sign: comparing
    spans alone accepted a wall that grew on the opposite side.
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"unknown planar wall direction: {direction!r}")
    u0, v0 = float(origin[0]), float(origin[1])
    n_low, n_high = (-thickness, 0.0) if direction == "negative" else (0.0, thickness)
    return {"u": (u0, u0 + length), "v": (v0, v0 + width), "n": (n_low, n_high)}


def envelope_problem(
    frame: dict[str, Any] | None,
    envelope: dict[str, Any] | None,
    length: float,
    width: float,
    thickness: float,
    direction: str = "positive",
    tolerance: float = ENVELOPE_TOLERANCE_MM,
    origin: tuple[float, float] = (0.0, 0.0),
) -> str | None:
    """Why the reported frame envelope does not prove the requested rectangle."""
    if not isinstance(frame, dict):
        return "the planar wall result carries no sketch frame"
    if not isinstance(envelope, dict):
        return "the planar wall result carries no frame envelope"
    if direction not in DIRECTIONS:
        return f"the planar wall result carries no usable direction ({direction!r})"
    for axis, (want_low, want_high) in expected_intervals(
        length, width, thickness, direction, origin
    ).items():
        entry = envelope.get(axis)
        if not isinstance(entry, dict) or "min" not in entry or "max" not in entry:
            return f"envelope is missing the {axis} extent"
        low, high = entry["min"], entry["max"]
        if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
            return f"envelope {axis} extent is not numeric"
        if not (math.isfinite(low) and math.isfinite(high)):
            return f"envelope {axis} extent is not finite [{low!r}, {high!r}]"
        if low > high:
            return f"envelope {axis} extent is not a signed interval ({low} > {high})"
        scale = max(abs(want_high - want_low), 1.0, abs(low) + abs(high))
        allowed = max(tolerance, scale * tolerance)
        if abs(low - want_low) > allowed or abs(high - want_high) > allowed:
            return (
                f"envelope {axis} is [{low:.9f}, {high:.9f}] mm instead of the requested "
                f"[{want_low:.9f}, {want_high:.9f}] mm: the wall grew on the wrong side of the "
                "sketch plane or away from the sketch origin"
            )
    axes = _frame_axes(frame)
    for name, axis in axes.items():
        norm = sum(component * component for component in axis) ** 0.5
        if not math.isfinite(norm):
            return f"frame {name} is not a finite vector (|{name}|={norm!r})"
        if abs(norm - 1) > 1e-6:
            return f"frame {name} is not a unit vector (|{name}|={norm:.9f})"
    for first, second in (("u", "v"), ("u", "n"), ("v", "n")):
        dot = sum(axes[first][i] * axes[second][i] for i in range(3))
        if abs(dot) > 1e-6:
            return f"frame {first} and {second} are not orthogonal (dot={dot:.9f})"
    return None


def gauge_validation(
    result: dict[str, Any], key: str, context: str | None = None
) -> dict[str, Any] | None:
    """Normalized gauge receipt from a native operation, or None when absent.

    Older executors publish no receipt, so none is generated for them. A receipt
    that exists but cannot be read is degraded to ``unavailable`` with a reason
    of its own: it never invents a value, a Toolkit code or a unit, and a
    malformed receipt must not read as a measurement.

    ``context=None`` means the receipt states its own context (R03: a resize of
    a wall created in the same plan is ``current_plan``, not ``saved_loaded``).
    """
    if key not in result:
        return None
    raw = result.get(key)
    if not isinstance(raw, dict):
        return _degraded_validation(context or PLAN_CONTEXT, "thickness_validation_malformed")
    status = raw.get("status")
    if status not in VALIDATION_STATUSES:
        return _degraded_validation(context or PLAN_CONTEXT, "thickness_validation_unknown_status")
    source = raw.get("source")
    if source not in VALIDATION_SOURCES:
        return _degraded_validation(context or PLAN_CONTEXT, "thickness_validation_unknown_source")
    if context is None:
        if raw.get("context") not in CONTEXTS:
            return _degraded_validation(PLAN_CONTEXT, "thickness_validation_context_mismatch")
        context = raw["context"]
    elif raw.get("context") != context:
        return _degraded_validation(context, "thickness_validation_context_mismatch")
    value = raw.get("value_mm")
    if value is not None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return _degraded_validation(context, "thickness_validation_invalid_value")
        value = float(value)
        if not math.isfinite(value):
            return _degraded_validation(context, "thickness_validation_non_finite_value")
    reason = raw.get("reason")
    if reason is not None and not isinstance(reason, str):
        return _degraded_validation(context, "thickness_validation_invalid_reason")
    if status in ("verified", "mismatch") and value is None:
        return _degraded_validation(context, f"thickness_validation_{status}_without_value")
    if status == "verified" and source not in TRUSTED_SOURCES:
        return _degraded_validation(context, "thickness_validation_verified_without_trusted_source")
    if status != "verified" and not reason:
        return _degraded_validation(context, "thickness_validation_missing_reason")
    return {
        "status": status,
        "source": source,
        "value_mm": value,
        "reason": reason,
        "context": context,
    }


def _degraded_validation(context: str, reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "source": "not_measured",
        "value_mm": None,
        "reason": reason,
        "context": context,
    }


def _validation_problems(label: str, block: dict[str, Any], thickness: float) -> list[str]:
    """Why a gauge receipt does not support the requested thickness."""
    status = block.get("status")
    if status != "verified":
        detail = f" ({block['reason']})" if block.get("reason") else ""
        return [f"the {label} gauge validation is {status!r}{detail}"]
    value = block.get("value_mm")
    if isinstance(value, float) and abs(value - thickness) > 1e-6:
        return [
            f"the {label} gauge validation reports {value:.9f} mm instead of the "
            f"requested {thickness:.9f} mm"
        ]
    return []


def _api_explanation(block: dict[str, Any]) -> tuple[str | None, str | None]:
    """Explain the legacy body API fields without turning fallback into an API value."""
    source = block["source"]
    if source == "geometry_normal_span":
        return "thickness_api_unavailable", source
    if source == "missing_api":
        return block["reason"], None
    if source == "api":
        return block["reason"] if block["status"] == "unavailable" else None, None
    if str(block["reason"]).startswith("thickness_validation_"):
        return "unknown", None
    return "not_attempted", None


def result_projection(result: dict[str, Any]) -> dict[str, Any]:
    """Public view of a native planar wall result, with its own verdict.

    ``verified`` is true only when the native result carries the feature, the
    four rectangle dimensions, the frame and an envelope that matches the
    requested size. A square wall is reported as such instead of being merged
    into one dimension. Missing or non-finite evidence is itself a problem: it
    must never remove a check and leave the wall looking verified.

    The gauge receipt is normalized here so a missing SDK declaration, a failed
    call, an ambiguous body, a disagreeing reading and a non-finite value stay
    distinguishable instead of sharing one null. The resize carries both its own
    receipt and the one read from the loaded file, and neither can stand in for
    the other.
    """
    length = _number(result, "length")
    width = _number(result, "width")
    thickness = _number(result, "thickness")
    resize = result.get("op") == PLANAR_WALL_RESIZE_OP
    direction = result.get("direction")
    origin, origin_problem = _origin(result)
    projection: dict[str, Any] = {
        "op": result.get("op"),
        "feature": result.get("feature"),
        "feature_id": result.get("feature_id"),
        "sketch": result.get("sketch"),
        "length": length,
        "width": width,
        "thickness": thickness,
        "direction": direction,
        "origin": origin,
        "square": bool(length is not None and width is not None and abs(length - width) <= 1e-9),
        "dimension_count": result.get("dimension_count"),
        "volume_mm3": _number(result, "volume_mm3"),
        "frame": result.get("frame"),
        "envelope": result.get("envelope"),
        "sheetmetal_body": result.get("sheetmetal_body"),
        "thickness_source": result.get("thickness_source"),
        "thickness_measured_mm": _number(result, "thickness_measured_mm"),
        "thickness_verified": result.get("thickness_verified"),
        "thickness_body_code": result.get("thickness_body_code"),
        "thickness_geometry_span_mm": _number(result, "thickness_geometry_span_mm"),
        "wall_created_this_job": result.get("wall_created_this_job"),
        "body_linked": result.get("body_linked"),
    }
    validation = gauge_validation(result, "thickness_validation", PLAN_CONTEXT)
    if validation is not None:
        projection["thickness_validation"] = validation
        projection["thickness_api_scope"] = "body_api_readback_only"
        api_reason, fallback_source = _api_explanation(validation)
        projection["thickness_api_reason"] = api_reason
        projection["thickness_fallback_source"] = fallback_source
    projection["thickness_verified_effective"] = (
        not _validation_problems("current plan", validation, thickness)
        if validation is not None and thickness is not None
        else None
    )
    loaded_validation = None
    if resize:
        projection["feature_id_before"] = result.get("feature_id_before")
        before, after = result.get("feature_id_before"), result.get("feature_id")
        projection["feature_id_unchanged"] = (
            before == after if isinstance(before, int) and isinstance(after, int) else None
        )
        projection["thickness_loaded_mm"] = _number(result, "thickness_loaded_mm")
        if not isinstance(after, int):
            projection["thickness_loaded_validation"] = None
            projection["thickness_loaded_api_scope"] = None
            projection["thickness_loaded_api_reason"] = None
            projection["thickness_loaded_fallback_source"] = None
            projection["thickness_loaded_verified_effective"] = None
        loaded_validation = gauge_validation(result, "thickness_loaded_validation")
        if loaded_validation is not None:
            # R03: a current-plan receipt is only valid when this job created
            # the wall. Without that execution-order fact, a copied create
            # receipt must not stand in for the loaded read.
            if (
                loaded_validation["context"] == PLAN_CONTEXT
                and result.get("wall_created_this_job") is not True
            ):
                loaded_validation = _degraded_validation(
                    SAVED_CONTEXT, "thickness_validation_current_plan_without_create"
                )
            projection["thickness_loaded_validation"] = loaded_validation
            projection["thickness_loaded_api_scope"] = "body_api_readback_only"
            api_reason, fallback_source = _api_explanation(loaded_validation)
            projection["thickness_loaded_api_reason"] = api_reason
            projection["thickness_loaded_fallback_source"] = fallback_source
            projection["thickness_loaded_verified_effective"] = (
                not _validation_problems("loaded", loaded_validation, thickness)
                if thickness is not None
                else None
            )
    problems: list[str] = []
    if origin_problem:
        problems.append(origin_problem)
    if not isinstance(projection["feature_id"], int):
        problems.append("the native result carries no feature id")
    dimensions = projection["dimension_count"]
    if not isinstance(dimensions, int) or dimensions < MIN_RECTANGLE_DIMENSIONS:
        problems.append(
            "the rectangle is not fully dimensioned "
            f"({dimensions!r} < {MIN_RECTANGLE_DIMENSIONS} point dimensions)"
        )
    if result.get("op") == PLANAR_WALL_RESIZE_OP and projection["feature_id_unchanged"] is False:
        problems.append("the resize changed the wall feature identity")
    if direction not in DIRECTIONS:
        problems.append(f"the native result carries no usable direction ({direction!r})")
    if projection["sheetmetal_body"] is not True:
        problems.append("the result does not report the wall as a sheetmetal body")
    # A missing or non-finite size is a problem of its own. Skipping the size,
    # gauge and envelope checks when one is absent let a result without any
    # measurement be published as verified (review, 2026-11-04).
    missing = [
        name
        for name, value in (("length", length), ("width", width), ("thickness", thickness))
        if value is None
    ]
    if missing:
        problems.append(
            "the native result reports no usable "
            + ", ".join(missing)
            + " for the rectangle, so its size, gauge and envelope cannot be judged"
        )
    else:
        volume = projection["volume_mm3"]
        expected = length * width * thickness
        if volume is None:
            problems.append("the native result carries no measured volume")
        elif abs(float(volume) - expected) > max(
            ABSOLUTE_VOLUME_TOLERANCE_MM3, abs(expected) * VOLUME_TOLERANCE
        ):
            problems.append(
                f"the measured volume {float(volume):.9f} mm3 does not match "
                f"length*width*thickness = {expected:.9f} mm3"
            )
        measured_thickness = projection["thickness_measured_mm"]
        if validation is not None:
            # R03: the receipt's trusted source decides the gauge verdict. The
            # legacy API boolean is deliberately not required: an SDK without
            # the body API can still verify from the wall's measured geometry.
            if measured_thickness is not None and abs(float(measured_thickness) - thickness) > 1e-6:
                problems.append(
                    f"the wall body carries {float(measured_thickness):.9f} mm instead of the "
                    f"requested {thickness:.9f} mm"
                )
        elif projection["thickness_verified"] is not True:
            problems.append(
                "the sheetmetal gauge was not read back from the wall body "
                f"(thickness_body_code={projection['thickness_body_code']!r})"
            )
        elif measured_thickness is None:
            problems.append("the native result claims a verified gauge without a value")
        elif abs(float(measured_thickness) - thickness) > 1e-6:
            problems.append(
                f"the wall body carries {float(measured_thickness):.9f} mm instead of the "
                f"requested {thickness:.9f} mm"
            )
        if resize:
            # The resize re-reads the gauge before editing, so an unreadable
            # gauge must not fall through as a pass. With a receipt the label
            # follows its actual context: a wall created in this plan was never
            # saved and reloaded.
            loaded = projection["thickness_loaded_mm"]
            if loaded_validation is not None:
                if loaded is not None and abs(float(loaded) - thickness) > 1e-6:
                    problems.append(
                        f"the wall carried {float(loaded):.9f} mm before the resize instead of "
                        f"the recorded {thickness:.9f} mm"
                    )
            elif loaded is None:
                problems.append(
                    "the resize result reports no gauge read back from the saved wall "
                    "(thickness_loaded_mm is missing or not finite)"
                )
            elif abs(float(loaded) - thickness) > 1e-6:
                problems.append(
                    f"the saved wall carried {float(loaded):.9f} mm instead of the recorded "
                    f"{thickness:.9f} mm"
                )
        # FEAT-058/R03: a receipt that is present but does not support the
        # request is a finding of its own. A receipt that is absent belongs to an
        # older executor and stays governed by the fields above.
        if validation is not None:
            problems.extend(_validation_problems("current plan", validation, thickness))
        if loaded_validation is not None:
            label = "current plan" if loaded_validation["context"] == PLAN_CONTEXT else "saved wall"
            problems.extend(_validation_problems(label, loaded_validation, thickness))
        envelope = envelope_problem(
            projection["frame"],
            projection["envelope"],
            length,
            width,
            thickness,
            direction if isinstance(direction, str) else "positive",
            origin=tuple(origin) if origin else (0.0, 0.0),
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


def _origin(result: dict[str, Any]) -> tuple[list[float] | None, str | None]:
    """Sketch-local [u0, v0] the wall was created at, or a problem.

    A result without the field comes from an executor older than R10 and starts
    at 0,0; anything else that is not a finite pair is reported instead of being
    silently read as 0,0, which would accept a wall placed somewhere else.
    """
    raw = result.get("origin")
    if raw is None:
        return [0.0, 0.0], None
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return None, "the native result carries no usable [u0, v0] origin"
    values = []
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None, "the native result origin is not numeric"
        number = float(item)
        if not math.isfinite(number):
            return None, "the native result origin is not finite"
        values.append(number)
    return values, None


def _number(result: dict[str, Any], key: str) -> float | None:
    """Reported measurement as a finite float, or None when it cannot be used.

    A NaN or an infinity is not a measurement: both make every comparison
    ``False`` and would otherwise read as agreement (review, 2026-11-04).
    """
    value = result.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None
