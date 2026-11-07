"""FEAT-057: normalize the native mass-properties reading.

The native executor measures the geometry and reports which density it used
(``model_material``, ``request`` or ``none``). This module only shapes that
reading for the public receipt and refuses combinations that cannot be true, so
a missing mass is never filled in from an assumed density.
"""

from __future__ import annotations

from math import isfinite
from typing import Any

DENSITY_SOURCES = ("model_material", "request", "none")

#: Why a reading carries no mass. The native executor names the broken link so
#: the receipt does not repeat "assign a material" when a material already
#: exists but its unit (or density) cannot be used.
MASS_UNAVAILABLE_REASONS = (
    "no_density",
    "unsupported_mass_unit",
    "material_density_unavailable",
    "material_query_failed",
    "volume_unavailable",
)


def normalize_mass_properties(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Return the public receipt for one native ``mass_properties`` block."""
    if not isinstance(raw, dict):
        raise ValueError("Mass properties reading is missing")

    volume = _number_or_none(raw.get("volume_mm3"), "volume_mm3")
    mass = _number_or_none(raw.get("mass_g"), "mass_g")
    density = _number_or_none(raw.get("density_g_cm3"), "density_g_cm3")
    source = raw.get("density_source")
    if source not in DENSITY_SOURCES:
        raise ValueError(f"Unknown density source: {source!r}")
    reason = raw.get("mass_unavailable_reason")
    if reason is not None and reason not in MASS_UNAVAILABLE_REASONS:
        raise ValueError(f"Unknown mass unavailable reason: {reason!r}")
    if source != "none" and reason is not None:
        raise ValueError("A mass reading with a density source cannot carry an unavailable reason")

    if source == "none":
        if mass is not None or density is not None:
            raise ValueError("A reading without a density source cannot carry mass or density")
    else:
        if volume is None or volume <= 0:
            raise ValueError("A mass reading needs a positive volume")
        if mass is None or density is None:
            raise ValueError("A mass reading with a density source must carry mass and density")
        product = volume * density
        if not isfinite(product):
            raise ValueError("volume_mm3 * density_g_cm3 must be finite for mass_g consistency")
        expected = product / 1000.0
        difference = expected - mass
        if not isfinite(difference):
            raise ValueError("mass_g difference from volume_mm3 * density_g_cm3 must be finite")
        if abs(difference) > max(1e-9, abs(expected) * 1e-9):
            raise ValueError(f"Mass {mass} g does not match volume {volume} mm3 at {density} g/cm3")

    return {
        "volume_mm3": volume,
        "mass_g": mass,
        "density_g_cm3": density,
        "density_source": source,
        "mass_unavailable_reason": reason,
        "center_of_mass_mm": _triple_or_none(raw.get("center_of_mass_mm")),
        "material_assigned": bool(raw.get("material_assigned")),
        "mass_unit": raw.get("mass_unit"),
        "hint": raw.get("hint"),
        "query_codes": {
            "volume": raw.get("volume_query_code"),
            "mass": raw.get("mass_query_code"),
            "units": raw.get("units_query_code"),
        },
    }


def _number_or_none(value: Any, field: str) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return _finite_number(value, field)


def _finite_number(value: int | float, field: str) -> float:
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"{field} cannot be represented as a finite float") from exc
    if not isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _triple_or_none(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        return None
    return [_finite_number(item, f"center_of_mass_mm[{index}]") for index, item in enumerate(value)]
