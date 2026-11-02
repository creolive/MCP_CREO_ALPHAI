"""Post-solve sketch geometry deviation reporting (FEAT-010 / BUG-049).

The native executor measures the solved section against the entities it was
given and reports one ``geometry_deviation`` block per sketch creation and
in-place edit result. This module owns the public contract for that block:

- ``available`` with ``unavailable_reason``: measurement failures are never
  reported as success with zeros; unverifiable geometry stays ``null``.
- ``warning_threshold_mm``: coordinates keeps the current source rejection
  threshold of 1e-5 mm (the feedback text said 1e-4; the source is
  authoritative); autodim warns above 1e-3 mm without rejecting.
- an explicit ``geometry_tolerance_mm`` request forces the threshold for both
  modes and must be a finite, strictly positive number; booleans, NaN, Inf,
  zero and negatives are rejected.
- ``sample`` is bounded (20 entries) and ``truncated`` plus ``total`` keep the
  population size visible.

The module never invents measurements: it validates what the executor
reported and degrades uninterpretable records to an explicit unavailable
state instead of fabricating numbers.
"""

from __future__ import annotations

import math
from typing import Any

#: coordinates keeps the current source rejection threshold (verify_coordinate_plan).
COORDINATES_DEFAULT_TOLERANCE_MM = 1e-5
#: autodim stays creatable and warns above this deviation.
AUTODIM_WARNING_THRESHOLD_MM = 1e-3
#: maximum number of per-entity sample entries in a report.
SAMPLE_LIMIT = 20

_STAGES = ("section_regenerate", "complete_feature")
_TOLERANCE_SOURCES = ("default_coordinates", "default_autodim", "request")
_SAMPLE_ENTRY_FIELDS = ("entity", "kind", "measurement", "deviation_mm", "reason")


def validate_tolerance_mm(value: Any) -> float | None:
    """Validate an explicit ``geometry_tolerance_mm`` request value.

    Returns ``None`` for an omitted value; anything else must be a finite,
    strictly positive real number. Booleans are rejected even though Python
    treats them as integers.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("geometry_tolerance_mm must be a finite positive number of millimeters")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("geometry_tolerance_mm must be a finite positive number of millimeters")
    if number <= 0:
        raise ValueError("geometry_tolerance_mm must be strictly positive")
    return number


def _finite_non_negative(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def _optional_finite_positive(value: Any) -> float | None:
    number = _finite_non_negative(value)
    return number if number is not None and number > 0 else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _normalize_sample(raw: Any) -> tuple[list[dict[str, Any]], bool]:
    entries: list[dict[str, Any]] = []
    truncated = False
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                truncated = True
                continue
            entry: dict[str, Any] = {
                "entity": item.get("entity") if isinstance(item.get("entity"), str) else None,
                "kind": item.get("kind") if isinstance(item.get("kind"), str) else None,
                "measurement": (
                    item.get("measurement") if isinstance(item.get("measurement"), str) else None
                ),
                "deviation_mm": _finite_non_negative(item.get("deviation_mm")),
                "reason": item.get("reason") if isinstance(item.get("reason"), str) else None,
            }
            if len(entries) < SAMPLE_LIMIT:
                entries.append(entry)
            else:
                truncated = True
    elif raw not in (None, []):
        truncated = True
    return entries, truncated


def _normalize_stage(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    available = raw.get("available") is True
    sample, sample_truncated = _normalize_sample(raw.get("sample"))
    return {
        "available": available,
        "max_deviation_mm": _finite_non_negative(raw.get("max_deviation_mm"))
        if available
        else None,
        "total": _optional_int(raw.get("total")),
        "sample": sample,
        "truncated": bool(raw.get("truncated")) or sample_truncated,
        "unavailable_reason": (
            raw.get("unavailable_reason")
            if isinstance(raw.get("unavailable_reason"), str)
            else None
        ),
    }


def unavailable_geometry_deviation(reason: str) -> dict[str, Any]:
    """An explicitly unavailable report; no measurement is ever fabricated."""
    return {
        "available": False,
        "unavailable_reason": reason,
        "measurement_scope": None,
        "warning_threshold_mm": None,
        "max_deviation_mm": None,
        "exceeds_warning": None,
        "total": None,
        "sample": [],
        "truncated": False,
        "enforced": None,
        "tolerance_source": None,
        "shift_detected": None,
        "accepted_by_request": None,
        "stages": {},
    }


def _finite_signed(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _unavailable_sketch_shift(note: str) -> dict[str, Any]:
    """An explicitly unmeasured shift report; no number is ever invented."""
    return {
        "detected": None,
        "rigid": None,
        "translation_mm": None,
        "max_point_mm": None,
        "point_count": None,
        "total": None,
        "sample": [],
        "truncated": False,
        "tolerance_source": None,
        "accepted_by_request": False,
        "measurement_scope": None,
        "note": note,
    }


def _normalize_shift_sample(raw: Any) -> tuple[list[dict[str, Any]], bool]:
    entries: list[dict[str, Any]] = []
    truncated = False
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                truncated = True
                continue
            moved = _finite_non_negative(item.get("moved_mm"))
            if moved is None:
                truncated = True
                continue
            entry = {
                "entity": item.get("entity") if isinstance(item.get("entity"), str) else None,
                "point": item.get("point") if isinstance(item.get("point"), str) else None,
                "axis": _optional_int(item.get("axis")),
                "moved_mm": moved,
            }
            if len(entries) < SAMPLE_LIMIT:
                entries.append(entry)
            else:
                truncated = True
    elif raw not in (None, []):
        truncated = True
    return entries, truncated


def normalize_sketch_shifted(block: Any) -> dict[str, Any]:
    """Validate one native ``sketch_shifted`` block (BUG-108).

    The executor measures the solved section against the supplied geometry and
    decides whether the whole profile moved as a rigid body. This projection
    keeps that verdict, but only echoes numbers the executor actually measured:
    a contradictory or malformed record becomes an explicit unmeasured state,
    and ``accepted_by_request`` is never inferred — a request tolerance that let
    a shifted sketch through is stated, not implied.
    """
    if not isinstance(block, dict):
        return _unavailable_sketch_shift("malformed sketch_shifted record")
    detected = block.get("detected")
    if not isinstance(detected, bool):
        return _unavailable_sketch_shift("malformed sketch_shifted record")
    sample, sample_truncated = _normalize_shift_sample(block.get("sample"))
    total = _optional_int(block.get("total"))
    point_count = _optional_int(block.get("point_count"))
    truncated = bool(block.get("truncated")) or sample_truncated
    measurement_scope = (
        block.get("measurement_scope") if isinstance(block.get("measurement_scope"), str) else None
    )
    tolerance_source = block.get("tolerance_source")
    if tolerance_source not in _TOLERANCE_SOURCES:
        tolerance_source = None
    max_point = _finite_non_negative(block.get("max_point_mm"))
    if not detected:
        report = _unavailable_sketch_shift("no post-solve shift was measured")
        report.update(
            {
                "detected": False,
                "max_point_mm": max_point,
                "point_count": point_count,
                "total": total,
                "sample": sample,
                "truncated": truncated,
                "tolerance_source": tolerance_source,
                "measurement_scope": measurement_scope,
            }
        )
        return report
    if max_point is None:
        return _unavailable_sketch_shift(
            "native report claimed a shift without any usable measurement (contradictory record)"
        )
    rigid = block.get("rigid")
    if not isinstance(rigid, bool):
        return _unavailable_sketch_shift("malformed sketch_shifted record: rigid flag missing")
    translation: dict[str, float] | None = None
    if rigid:
        raw_translation = block.get("translation_mm")
        if not isinstance(raw_translation, dict):
            return _unavailable_sketch_shift(
                "malformed sketch_shifted record: translation vector missing"
            )
        u = _finite_signed(raw_translation.get("u"))
        v = _finite_signed(raw_translation.get("v"))
        if u is None or v is None:
            return _unavailable_sketch_shift(
                "malformed sketch_shifted record: translation vector is not finite"
            )
        translation = {"u": u, "v": v}
    accepted_by_request = block.get("accepted_by_request") is True and tolerance_source == "request"
    if accepted_by_request:
        note = (
            "the solved profile translated as a rigid body; the request tolerance "
            "accepted it, this is not an exact solve"
        )
    elif rigid:
        note = "the solved profile translated as a rigid body"
    else:
        note = "the solved profile deformed; per-point deviations differ"
    return {
        "detected": True,
        "rigid": rigid,
        "translation_mm": translation,
        "max_point_mm": max_point,
        "point_count": point_count,
        "total": total,
        "sample": sample,
        "truncated": truncated,
        "tolerance_source": tolerance_source,
        "accepted_by_request": accepted_by_request,
        "measurement_scope": measurement_scope,
        "note": note,
    }


def normalize_geometry_deviation(block: Any) -> dict[str, Any]:
    """Validate one native ``geometry_deviation`` record.

    A missing or uninterpretable record degrades to an explicit unavailable
    state; numbers are only ever echoed when the executor reported them in a
    well-formed shape.
    """
    if not isinstance(block, dict):
        return unavailable_geometry_deviation("malformed geometry_deviation record")
    reason = (
        block.get("unavailable_reason")
        if isinstance(block.get("unavailable_reason"), str)
        else None
    )
    if block.get("available") is not True and reason is None:
        # Neither a usable report nor an explanation: treat the record itself
        # as malformed instead of inventing an outcome.
        return unavailable_geometry_deviation("malformed geometry_deviation record")
    available = block.get("available") is True
    sample, sample_truncated = _normalize_sample(block.get("sample"))
    max_deviation = _finite_non_negative(block.get("max_deviation_mm")) if available else None
    threshold = _optional_finite_positive(block.get("warning_threshold_mm"))
    tolerance_source = block.get("tolerance_source")
    if tolerance_source not in _TOLERANCE_SOURCES:
        tolerance_source = None
    stages = {
        name: normalized
        for name in _STAGES
        if (normalized := _normalize_stage(block.get("stages", {}).get(name))) is not None
    }
    if (
        available
        and max_deviation is None
        and not any(stage["available"] for stage in stages.values())
    ):
        # "available" without any usable measurement is contradictory; keep
        # the record explicitly unavailable instead of implying success.
        return unavailable_geometry_deviation(
            "native report claimed availability without a usable measurement"
        )
    return {
        "available": available,
        "unavailable_reason": reason,
        "measurement_scope": (
            block.get("measurement_scope")
            if isinstance(block.get("measurement_scope"), str)
            else None
        ),
        "warning_threshold_mm": threshold,
        "max_deviation_mm": max_deviation,
        # Recomputed from the reported values; the executor's own flag is
        # never trusted over the numbers it published.
        "exceeds_warning": (
            max_deviation > threshold
            if max_deviation is not None and threshold is not None
            else None
        ),
        "total": _optional_int(block.get("total")),
        "sample": sample,
        "truncated": bool(block.get("truncated")) or sample_truncated,
        "enforced": block.get("enforced") if isinstance(block.get("enforced"), bool) else None,
        "tolerance_source": tolerance_source,
        # BUG-108: additive only — the shift verdict also lives in the
        # top-level sketch_shifted block; both stay null when unmeasured.
        "shift_detected": (
            block.get("shift_detected") if isinstance(block.get("shift_detected"), bool) else None
        ),
        "accepted_by_request": (
            block.get("accepted_by_request")
            if isinstance(block.get("accepted_by_request"), bool)
            else None
        ),
        "stages": stages,
    }
