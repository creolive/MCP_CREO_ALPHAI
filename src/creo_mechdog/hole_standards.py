"""FEAT-035 standard threaded holes: frozen series/size table and resolution.

Offline scope. The source data is a small ISO metric coarse table, not a parser
for the installed Creo hole charts (``.hol``): the chart format and the native
thread element tree are not verified on this machine yet, so
``HoleOp.standard`` validates against this table and then refuses submission
with an actionable error instead of silently creating a plain hole.

When the live probe lands, ``resolve_standard_hole`` keeps this signature and
the table digest keeps identifying exactly which rows were used.
"""

from __future__ import annotations

import hashlib
import json

SERIES_ISO_METRIC_COARSE = "ISO"
TABLE_ID = "iso_metric_coarse@1"

# Nominal diameter, pitch and the tap drill for ISO metric coarse threads.
# ``thread_depth_limit_mm`` is the deepest usable thread for the size; it is a
# table value, never derived from the requested depth.
_ISO_METRIC_COARSE: dict[str, dict[str, float]] = {
    "M3": {
        "nominal_diameter_mm": 3.0,
        "pitch_mm": 0.5,
        "tap_drill_mm": 2.5,
        "thread_depth_limit_mm": 6.0,
    },
    "M4": {
        "nominal_diameter_mm": 4.0,
        "pitch_mm": 0.7,
        "tap_drill_mm": 3.3,
        "thread_depth_limit_mm": 8.0,
    },
    "M5": {
        "nominal_diameter_mm": 5.0,
        "pitch_mm": 0.8,
        "tap_drill_mm": 4.2,
        "thread_depth_limit_mm": 10.0,
    },
    "M6": {
        "nominal_diameter_mm": 6.0,
        "pitch_mm": 1.0,
        "tap_drill_mm": 5.0,
        "thread_depth_limit_mm": 12.0,
    },
    "M8": {
        "nominal_diameter_mm": 8.0,
        "pitch_mm": 1.25,
        "tap_drill_mm": 6.8,
        "thread_depth_limit_mm": 16.0,
    },
    "M10": {
        "nominal_diameter_mm": 10.0,
        "pitch_mm": 1.5,
        "tap_drill_mm": 8.5,
        "thread_depth_limit_mm": 20.0,
    },
    "M12": {
        "nominal_diameter_mm": 12.0,
        "pitch_mm": 1.75,
        "tap_drill_mm": 10.2,
        "thread_depth_limit_mm": 24.0,
    },
}

_TABLES = {SERIES_ISO_METRIC_COARSE: _ISO_METRIC_COARSE}

NOT_VERIFIED = (
    "standard threaded holes are frozen offline but not enabled: the native thread element "
    "tree and the installed hole chart were not verified on a live session, so submitting "
    "would risk a plain hole that only looks threaded; submit diameter with a tip depth for "
    "now, or re-run after the live probe is recorded in FEAT-035"
)


def table_digest(series: str) -> str:
    """SHA256 over the frozen rows, so a receipt can name the exact table."""
    rows = _TABLES[series]
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _check_identifier(kind: str, value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"standard hole {kind} must not be empty")
    if text in {".", ".."} or "/" in text or "\\" in text or ":" in text:
        raise ValueError(f"standard hole {kind} must be a table name, not a path: {value!r}")
    return text


def resolve_standard_hole(series: str, size: str) -> dict:
    """Resolve one frozen table row; never reads a caller-supplied path."""
    series_name = _check_identifier("series", series)
    size_name = _check_identifier("size", size)
    if series_name not in _TABLES:
        raise ValueError(
            f"unknown standard hole series {series_name!r}; frozen series: "
            + ", ".join(sorted(_TABLES))
        )
    rows = _TABLES[series_name]
    if size_name not in rows:
        raise ValueError(
            f"standard hole size {size_name!r} is not in {series_name} {TABLE_ID}; "
            "frozen sizes: " + ", ".join(sorted(rows))
        )
    row = rows[size_name]
    return {
        "series": series_name,
        "size": size_name,
        "table_id": TABLE_ID,
        "table_sha256": table_digest(series_name),
        "nominal_diameter_mm": row["nominal_diameter_mm"],
        "pitch_mm": row["pitch_mm"],
        "tap_drill_diameter_mm": row["tap_drill_mm"],
        "thread_depth_limit_mm": row["thread_depth_limit_mm"],
    }


def require_native_support() -> None:
    """Raise the frozen, actionable refusal until the native probe is recorded."""
    raise ValueError(NOT_VERIFIED)
