"""FEAT-035 standard threaded holes: frozen series/size table and resolution.

The source data is a small ISO metric coarse table, not a parser for the
installed Creo hole charts (``.hol``). The table names each row by the chart's
own fastener id, and the native side still asks the installed chart through
``ProElementHoleScrewSizeSet``: a row the chart does not have fails there with
``PRO_TK_INVALID_NAME`` instead of degrading to a plain hole.

Only the rows listed here are offered; availability on another machine is
decided by its own chart, never assumed from this table.
"""

from __future__ import annotations

import hashlib
import json
import math

SERIES_ISO_METRIC_COARSE = "ISO"
TABLE_ID = "iso_metric_coarse@1"

# Nominal diameter, pitch and the tap drill for ISO metric coarse threads.
# ``thread_depth_limit_mm`` is the deepest usable thread for the size; it is a
# table value, never derived from the requested depth. ``fastener_id`` is the
# name the installed ISO hole chart uses for the same row: the chart keys sizes
# by fastener id ("M6x1"), and "M6" alone is rejected by the native
# thread-size setter with PRO_TK_INVALID_NAME.
_ISO_METRIC_COARSE: dict[str, dict[str, float | str]] = {
    "M3": {
        "fastener_id": "M3x.5",
        "nominal_diameter_mm": 3.0,
        "pitch_mm": 0.5,
        "tap_drill_mm": 2.5,
        "thread_depth_limit_mm": 6.0,
    },
    "M4": {
        "fastener_id": "M4x.7",
        "nominal_diameter_mm": 4.0,
        "pitch_mm": 0.7,
        "tap_drill_mm": 3.3,
        "thread_depth_limit_mm": 8.0,
    },
    "M5": {
        "fastener_id": "M5x.8",
        "nominal_diameter_mm": 5.0,
        "pitch_mm": 0.8,
        "tap_drill_mm": 4.2,
        "thread_depth_limit_mm": 10.0,
    },
    "M6": {
        "fastener_id": "M6x1",
        "nominal_diameter_mm": 6.0,
        "pitch_mm": 1.0,
        "tap_drill_mm": 5.0,
        "thread_depth_limit_mm": 12.0,
    },
    "M8": {
        "fastener_id": "M8x1.25",
        "nominal_diameter_mm": 8.0,
        "pitch_mm": 1.25,
        "tap_drill_mm": 6.8,
        "thread_depth_limit_mm": 16.0,
    },
    "M10": {
        "fastener_id": "M10x1.5",
        "nominal_diameter_mm": 10.0,
        "pitch_mm": 1.5,
        "tap_drill_mm": 8.5,
        "thread_depth_limit_mm": 20.0,
    },
    "M12": {
        "fastener_id": "M12x1.75",
        "nominal_diameter_mm": 12.0,
        "pitch_mm": 1.75,
        "tap_drill_mm": 10.2,
        "thread_depth_limit_mm": 24.0,
    },
}

_TABLES = {SERIES_ISO_METRIC_COARSE: _ISO_METRIC_COARSE}

# The native standard hole drills with this point angle (see
# native/generic.cpp::standard_hole_elements). Validation needs the same number to
# bound the usable thread by the real tip depth instead of the shoulder.
DRILL_TIP_ANGLE_DEG = 118.0


def tip_cone_height_mm(tap_drill_diameter_mm: float) -> float:
    """Cone height below the drill shoulder for the native point angle."""
    return (tap_drill_diameter_mm / 2.0) / math.tan(math.radians(DRILL_TIP_ANGLE_DEG / 2.0))


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
        "fastener_id": row["fastener_id"],
        "table_id": TABLE_ID,
        "table_sha256": table_digest(series_name),
        "nominal_diameter_mm": row["nominal_diameter_mm"],
        "pitch_mm": row["pitch_mm"],
        "tap_drill_diameter_mm": row["tap_drill_mm"],
        "thread_depth_limit_mm": row["thread_depth_limit_mm"],
    }


def prepare(operations: list[dict]) -> list[dict]:
    """Attach the frozen row's values to every standard hole before native.

    Native must not derive a fastener id or a tap drill on its own: it receives
    exactly the row the validator already accepted, and the installed chart
    still gets the final say through its own setter.
    """
    prepared: list[dict] = []
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") != "hole":
            prepared.append(operation)
            continue
        standard = operation.get("standard")
        if not isinstance(standard, dict):
            prepared.append(operation)
            continue
        row = resolve_standard_hole(str(standard.get("series")), str(standard.get("size")))
        prepared.append(
            {
                **operation,
                "standard": {
                    **standard,
                    "fastener_id": row["fastener_id"],
                    "nominal_diameter_mm": row["nominal_diameter_mm"],
                    "tap_drill_mm": row["tap_drill_diameter_mm"],
                    "thread_depth_limit_mm": row["thread_depth_limit_mm"],
                },
            }
        )
    return prepared
