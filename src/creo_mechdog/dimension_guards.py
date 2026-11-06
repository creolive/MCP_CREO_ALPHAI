"""FEAT-004 dimension guards: refuse an edit aimed at a changed dimension.

A regeneration can shift dimension IDs, so a plan built from an older snapshot
can silently move the wrong dimension. Callers may pin what they observed:

    {"id": 12, "value": 20, "expected_value": 25, "expected_symbol": "d12",
     "expected_owner": "boss_base"}

The native executor reads every target before writing the first value and
applies the same contract; this module is the shared, testable copy of that
judgement. A pin that cannot be verified (unknown symbol, unknown owner, unknown
value) is refused instead of being treated as a match.
"""

from __future__ import annotations

from typing import Any

ABSOLUTE_TOLERANCE = 1e-8
RELATIVE_TOLERANCE = 1e-8

GUARD_FIELDS = ("expected_value", "expected_symbol", "expected_owner")


def value_tolerance(expected: float) -> float:
    """Absolute tolerance allowed for a pinned dimension value."""
    return max(ABSOLUTE_TOLERANCE, abs(expected) * RELATIVE_TOLERANCE)


def has_guard(requested: dict[str, Any]) -> bool:
    """True when the entry pins at least one observed attribute."""
    return any(requested.get(field) is not None for field in GUARD_FIELDS)


def owner_text(current: dict[str, Any]) -> str:
    """Human-readable owner for error messages; ``unknown`` when unmeasured."""
    name = current.get("owner_feature_name")
    owner_id = current.get("owner_feature_id")
    if name is None and owner_id is None:
        return "unknown"
    return f"{name} (id {owner_id})"


def check_dimension_guard(current: dict[str, Any], requested: dict[str, Any]) -> None:
    """Raise ``ValueError`` when the live dimension no longer matches the pins.

    ``current`` uses the inspection field names (``value``, ``symbol``,
    ``relation_driven``, ``owner_feature_id``, ``owner_feature_name``);
    ``requested`` uses the ``expected_*`` pins. Entries without pins behave
    exactly as before.
    """
    dimension_id = requested.get("id")
    if current.get("relation_driven") is True:
        raise ValueError(
            f"Dimension {dimension_id} is controlled by relations; "
            "edit its driving parameter or relation instead"
        )

    expected = requested.get("expected_value")
    if expected is not None:
        actual = current.get("value")
        if actual is None:
            raise ValueError(
                f"Dimension {dimension_id} guard failed on value: expected {expected} but the "
                f"current value is unknown, owner {owner_text(current)}; "
                "re-read the model and resubmit with the current value"
            )
        if abs(float(expected) - float(actual)) > value_tolerance(float(expected)):
            raise ValueError(
                f"Dimension {dimension_id} guard failed on value: expected {expected}, "
                f"current {actual}, owner {owner_text(current)}; "
                "re-read the model and resubmit with the current value"
            )

    expected_symbol = requested.get("expected_symbol")
    if expected_symbol is not None:
        actual_symbol = current.get("symbol")
        if actual_symbol is None:
            raise ValueError(
                f'Dimension {dimension_id} guard failed on symbol: expected "{expected_symbol}" '
                f"but the dimension symbol is unknown, owner {owner_text(current)}; "
                "re-read the model and resubmit with the current symbol"
            )
        if str(expected_symbol) != str(actual_symbol):
            raise ValueError(
                f'Dimension {dimension_id} guard failed on symbol: expected "{expected_symbol}", '
                f'current "{actual_symbol}", owner {owner_text(current)}; '
                "re-read the model and resubmit with the current symbol"
            )

    expected_owner = requested.get("expected_owner")
    if expected_owner is not None:
        owner_name = current.get("owner_feature_name")
        owner_id = current.get("owner_feature_id")
        if owner_name is None and owner_id is None:
            raise ValueError(
                f"Dimension {dimension_id} guard failed on owner: the owning feature is unknown; "
                "re-read the model and resubmit with the current owner"
            )
        if isinstance(expected_owner, bool):
            raise ValueError(
                f"Dimension {dimension_id} guard failed on owner: {expected_owner!r} is not a "
                "feature id or label"
            )
        if isinstance(expected_owner, int):
            if owner_id != expected_owner:
                raise ValueError(
                    f"Dimension {dimension_id} guard failed on owner: expected feature id "
                    f"{expected_owner}, current {owner_text(current)}; "
                    "re-read the model and resubmit with the current owner"
                )
        elif str(expected_owner) != str(owner_name):
            raise ValueError(
                f'Dimension {dimension_id} guard failed on owner: expected "{expected_owner}", '
                f"current {owner_text(current)}; "
                "re-read the model and resubmit with the current owner"
            )
