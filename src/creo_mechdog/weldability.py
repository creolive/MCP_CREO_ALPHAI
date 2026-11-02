"""BUG-101: report whether a closed sketch contour can be welded by the kernel.

Contour closure is judged at 1e-4 mm, but the kernel does not weld everything
that closes at that tolerance: the 2026-10-31 feedback measured a 10-ring/40-arc
profile with an 8.215e-7 mm endpoint gap rejected by extrude while the same
geometry snapped to 7.83e-13 mm succeeded (volume 1849.8028532376422 mm3).

``WELD_TOLERANCE_MM`` is therefore the already published native sketch epsilon
(1e-9 mm, the value coordinate dimensioning solves with - see
``profile_diagnostics.EXACT_TOLERANCE_MM``), the only existing constant that
falls between those two observations. This module never derives the threshold
from a request and never invents a value: a caller may pass an explicit
tolerance to force a stricter or looser gate, and the report says which source
it used.
"""

from __future__ import annotations

import math
from typing import Any

from creo_mechdog.profile_diagnostics import EXACT_TOLERANCE_MM

WELD_TOLERANCE_MM = EXACT_TOLERANCE_MM
SAMPLE_LIMIT = 20
# "weldable" is a risk flag, not a verdict. The 2026-11-02 live check on Creo
# 12.4 extruded a profile with an 8.215e-7 mm endpoint gap successfully, i.e.
# the kernel welded a gap eight hundred times above this bound, so "false" only
# means "not proven safe" and must never be read as "will fail".
GUARANTEE_SCOPE = "endpoint_risk_flag"


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _requested_tolerance(value: Any) -> float | None:
    if value is None:
        return None
    number = _finite(value)
    if number is None or number <= 0.0:
        raise ValueError("weld_tolerance_mm must be a finite number greater than 0")
    return number


def _max_gap(contours: Any) -> float | None:
    if not isinstance(contours, list):
        return None
    gaps = [
        gap
        for gap in (_finite(item.get("max_join_gap_mm")) for item in contours)
        if gap is not None
    ]
    return max(gaps) if gaps else None


def weldability_from_report(
    report: Any,
    *,
    weld_tolerance_mm: float | None = None,
    sample_limit: int = SAMPLE_LIMIT,
) -> dict[str, Any]:
    """Project one analytic profile report onto a bounded weldability verdict.

    ``weldable`` is None whenever the evidence cannot decide it (unavailable or
    partial analysis, no contour gap, non-finite gap). An open contour is a real
    "no" rather than an unknown, because no welding can close a missing edge.
    """
    tolerance = _requested_tolerance(weld_tolerance_mm)
    source = "request" if tolerance is not None else "measured_constant"
    if tolerance is None:
        tolerance = WELD_TOLERANCE_MM
    entry: dict[str, Any] = {
        "available": False,
        "weldable": None,
        "max_endpoint_gap_mm": None,
        "weld_tolerance_mm": tolerance,
        "tolerance_source": source,
        "guarantee_scope": GUARANTEE_SCOPE,
        "exceeding_pairs": {"total": None, "truncated": None, "sample": []},
        "note": "profile analysis unavailable; weldability not determined",
    }
    if not isinstance(report, dict):
        return entry
    analysis = report.get("analysis")
    if not isinstance(analysis, str) or analysis == "unavailable":
        return entry
    entry["available"] = True
    gap = _max_gap(report.get("contours"))
    entry["max_endpoint_gap_mm"] = gap

    near = (report.get("categories") or {}).get("near_tolerance")
    near = near if isinstance(near, dict) else {}
    items = near.get("items") if isinstance(near.get("items"), list) else []
    pairs = [
        {"entities": list(item.get("entities") or []), "gap_mm": _finite(item.get("gap_mm"))}
        for item in items
        if isinstance(item, dict) and (_finite(item.get("gap_mm")) or 0.0) > tolerance
    ]
    raw_count = near.get("count")
    raw_count = (
        raw_count if isinstance(raw_count, int) and not isinstance(raw_count, bool) else None
    )
    if raw_count is not None and raw_count == len(pairs):
        total: int | None = raw_count
    elif not near.get("truncated"):
        total = len(pairs)
    else:
        # Truncated items filtered by the tolerance cannot bound the population.
        total = None
    entry["exceeding_pairs"] = {
        "total": total,
        "truncated": bool(near.get("truncated")) if near else None,
        "sample": pairs[: max(1, sample_limit)],
    }

    if analysis != "complete":
        entry["note"] = f"analysis {analysis}; weldability not determined"
        return entry
    open_count = report.get("open_contour_count")
    closed_count = report.get("closed_contour_count")
    if (isinstance(open_count, int) and open_count > 0) or (
        isinstance(closed_count, int) and closed_count == 0
    ):
        entry["weldable"] = False
        entry["note"] = (
            "profile is not closed; no endpoint welding can close a missing edge "
            f"(open_contour_count={open_count}, closed_contour_count={closed_count})"
        )
        return entry
    if gap is None:
        entry["note"] = "no contour endpoint gap available; weldability not determined"
        return entry
    if gap <= tolerance:
        entry["weldable"] = True
        entry["note"] = (
            f"max endpoint gap {gap:.6g} mm is within the {tolerance:g} mm weld tolerance "
            "(endpoint welding only; the feature can still fail for other reasons)"
        )
        return entry
    entry["weldable"] = False
    count = "unknown" if total is None else str(total)
    entry["note"] = (
        f"max endpoint gap {gap:.6g} mm exceeds the measured safe bound of {tolerance:g} mm; "
        f"{count} endpoint pair(s) are joined only by the closure tolerance. This is a risk "
        "flag, not a prediction: Creo 12.4 extruded an 8.215e-7 mm gap successfully on "
        "2026-11-02, so the kernel may still weld it. Snap the endpoints if you need the "
        "stronger guarantee"
    )
    return entry
