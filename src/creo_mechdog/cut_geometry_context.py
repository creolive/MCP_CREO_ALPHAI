"""B2/F11: project the native zero-material-cut geometry receipt.

The executor measures the sketch frame, the created feature's effective depth
and the volume before/after regeneration. This module only validates that
receipt: it never reads the request, never backfills a missing measurement and
marks a self-contradictory interval as unavailable instead of publishing it as
recomputable geometry.
"""

from __future__ import annotations

import math
from typing import Any

NO_MATERIAL_REMOVED = "no_material_removed"
OPERATIONS = ("extrude", "revolve")
DIRECTIONS = ("positive", "negative", "symmetric")
DEPTH_TYPES = ("blind", "symmetric", "through_all")
FRAME_SOURCES = ("sketch_alias", "unavailable")
INTERVAL_SOURCES = ("feature_tree_and_sketch_alias", "unavailable")
TOLERANCE_MM = 1e-6

_FRAME_FIELDS = (
    "origin_mm",
    "normal",
    "u_axis",
    "v_axis",
    "surface_id",
    "section_normal_sign",
)
_INTERVAL_FIELDS = (
    "axis",
    "origin_mm",
    "start_offset_mm",
    "end_offset_mm",
    "start_point_mm",
    "end_point_mm",
    "effective_depth_type",
    "effective_depth_mm",
    "direction_sign",
)
_VOLUME_FIELDS = ("before", "after", "removed", "zero_material_threshold")


def _scalar(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _vector(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    parts = [_scalar(item) for item in value]
    return parts if all(part is not None for part in parts) else None


def _sign(value: Any) -> int | None:
    return value if type(value) is int and value in (1, -1) else None


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _choice(value: Any, allowed: tuple[str, ...]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


def _close(left: float, right: float) -> bool:
    return abs(left - right) <= TOLERANCE_MM


def _vectors_close(left: list[float] | None, right: list[float] | None) -> bool:
    if left is None or right is None:
        return False
    return all(_close(a, b) for a, b in zip(left, right))


def _length(vector: list[float] | None) -> float | None:
    return math.sqrt(sum(part * part for part in vector)) if vector else None


def _translate(origin: list[float], axis: list[float], offset: float) -> list[float]:
    return [origin[i] + axis[i] * offset for i in range(3)]


def _empty_frame(reason: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"available": False, "source": None, "reason": reason}
    entry.update({key: None for key in _FRAME_FIELDS})
    return entry


def _empty_interval(reason: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"available": False, "source": None, "reason": reason}
    entry.update({key: None for key in _INTERVAL_FIELDS})
    return entry


def _empty_volume() -> dict[str, Any]:
    return {key: None for key in _VOLUME_FIELDS}


def _normalize_frame(block: Any) -> dict[str, Any]:
    if not isinstance(block, dict):
        return _empty_frame("sketch_frame_missing")
    frame = _empty_frame(_text(block.get("reason")))
    frame["source"] = _choice(block.get("source"), FRAME_SOURCES)
    for key in ("origin_mm", "normal", "u_axis", "v_axis"):
        frame[key] = _vector(block.get(key))
    surface_id = block.get("surface_id")
    frame["surface_id"] = surface_id if type(surface_id) is int else None
    frame["section_normal_sign"] = _sign(block.get("section_normal_sign"))
    if block.get("available") is not True:
        frame["reason"] = frame["reason"] or "sketch_frame_unavailable"
        return frame
    normal_length = _length(frame["normal"])
    if frame["origin_mm"] is None or normal_length is None or not _close(normal_length, 1.0):
        frame["reason"] = "sketch_frame_inconsistent"
        return frame
    frame["available"] = True
    frame["reason"] = None
    return frame


def _interval_is_recomputable(
    interval: dict[str, Any], frame: dict[str, Any], direction_sign: int | None
) -> bool:
    depth = interval["effective_depth_mm"]
    start = interval["start_offset_mm"]
    end = interval["end_offset_mm"]
    axis = interval["axis"]
    if depth is None or depth <= 0 or start is None or end is None or axis is None:
        return False
    if not _close(end - start, depth) or not all(
        math.isfinite(part) for part in interval["origin_mm"] or []
    ):
        return False
    axis_length = _length(axis)
    if axis_length is None or not _close(axis_length, 1.0):
        return False
    sign = interval["direction_sign"]
    if sign is None or (direction_sign is not None and sign != direction_sign):
        return False
    if not frame["available"] or not _vectors_close(
        axis, [part * sign for part in frame["normal"]]
    ):
        return False
    origin = interval["origin_mm"]
    if origin is None or not _vectors_close(origin, frame["origin_mm"]):
        return False
    return _vectors_close(
        interval["start_point_mm"], _translate(origin, axis, start)
    ) and _vectors_close(interval["end_point_mm"], _translate(origin, axis, end))


def _normalize_interval(
    block: Any, frame: dict[str, Any], direction_sign: int | None
) -> dict[str, Any]:
    if not isinstance(block, dict):
        return _empty_interval("depth_interval_missing")
    interval = _empty_interval(_text(block.get("reason")))
    interval["source"] = _choice(block.get("source"), INTERVAL_SOURCES)
    for key in ("axis", "origin_mm", "start_point_mm", "end_point_mm"):
        interval[key] = _vector(block.get(key))
    for key in ("start_offset_mm", "end_offset_mm", "effective_depth_mm"):
        interval[key] = _scalar(block.get(key))
    interval["effective_depth_type"] = _choice(block.get("effective_depth_type"), DEPTH_TYPES)
    interval["direction_sign"] = _sign(block.get("direction_sign"))
    if block.get("available") is not True:
        interval["reason"] = interval["reason"] or "depth_interval_unavailable"
        return interval
    if not _interval_is_recomputable(interval, frame, direction_sign):
        interval["reason"] = "depth_interval_inconsistent"
        return interval
    interval["available"] = True
    interval["reason"] = None
    return interval


def _normalize_volume(block: Any) -> dict[str, Any]:
    volume = _empty_volume()
    if isinstance(block, dict):
        for key in _VOLUME_FIELDS:
            volume[key] = _scalar(block.get(key))
    return volume


def normalize_cut_geometry_context(block: Any) -> dict[str, Any]:
    """Validate the executor's zero-material-cut receipt without inventing data."""
    entry: dict[str, Any] = {
        "available": False,
        "reason": "cut_geometry_context_missing",
        "status": None,
        "operation": None,
        "mode": None,
        "direction": None,
        "direction_sign": None,
        "sketch_frame": _empty_frame(),
        "depth_interval_mm": _empty_interval(),
        "volume_mm3": _empty_volume(),
        "note": None,
    }
    if not isinstance(block, dict) or not block:
        return entry
    entry["status"] = _text(block.get("status"))
    entry["operation"] = _choice(block.get("operation"), OPERATIONS)
    entry["mode"] = _choice(block.get("mode"), ("cut",))
    entry["direction"] = _choice(block.get("direction"), DIRECTIONS)
    entry["direction_sign"] = _sign(block.get("direction_sign"))
    entry["note"] = _text(block.get("note"))
    entry["sketch_frame"] = _normalize_frame(block.get("sketch_frame"))
    entry["depth_interval_mm"] = _normalize_interval(
        block.get("depth_interval_mm"), entry["sketch_frame"], entry["direction_sign"]
    )
    entry["volume_mm3"] = _normalize_volume(block.get("volume_mm3"))
    if entry["status"] == NO_MATERIAL_REMOVED:
        entry["available"] = True
        entry["reason"] = None
    else:
        entry["reason"] = "unexpected_status"
    return entry


def annotate_cut_geometry_context(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize any extrude/revolve record that carries the block.

    The executor only stages this receipt on a zero-material cut, but the
    projection keys off the block itself rather than an execution status so a
    legacy or synthetic record is never reclassified. A record without the block
    stays without it, and a malformed block degrades to an explicit unavailable
    state with a reason instead of zeros.
    """
    operations = result.get("operations")
    if not isinstance(operations, list):
        return result
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") not in OPERATIONS:
            continue
        if "cut_geometry_context" not in operation:
            continue
        operation["cut_geometry_context"] = normalize_cut_geometry_context(
            operation.get("cut_geometry_context")
        )
    return result
