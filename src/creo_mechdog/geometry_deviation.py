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
        raise ValueError(
            "geometry_tolerance_mm must be a finite positive number of millimeters"
        )
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
        "max_deviation_mm": _finite_non_negative(raw.get("max_deviation_mm")) if available else None,
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
        "stages": {},
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
    if available and max_deviation is None and not any(
        stage["available"] for stage in stages.values()
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
            max_deviation > threshold if max_deviation is not None and threshold is not None else None
        ),
        "total": _optional_int(block.get("total")),
        "sample": sample,
        "truncated": bool(block.get("truncated")) or sample_truncated,
        "enforced": block.get("enforced") if isinstance(block.get("enforced"), bool) else None,
        "tolerance_source": tolerance_source,
        "stages": stages,
    }
