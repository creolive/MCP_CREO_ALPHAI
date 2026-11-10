"""C1/F10: frozen design contract for a one-step tapered extrusion.

Status: ``designed_not_implemented``. Nothing in the public MCP surface reads
this module yet. B6 must import these constants as its single source of truth
instead of redefining parameter names, error codes or the limitation text.

Why this contract exists at all is B6's falsification result (recorded in the
SDD B6 evidence note), because the 0.19.0 report's own wording was only an
inference:

* ``creo_draft`` is a real, enabled tool that compiles (``ProDraft.h`` is
  included by ``native/generic.cpp``; ``capabilities.py`` publishes
  ``draft.enabled``), and this repository already recorded successful
  real-model runs. FEAT-051 run2 (2026-10-31) measured both flip directions and
  matched the analytic deltas to about 3e-10; BUG-102 (2026-11-05, re-run
  2026-11-07) measured +352.044362 / -353.263560 mm3, which proves the two
  directions act oppositely (0.35% apart) but does not reconcile each value
  analytically. The claim "draft cannot be used" is therefore refuted.
* ``creo_draft`` does require per-surface references: ``DraftOp.surfaces`` is
  a non-empty list (``schema.py``) and the native side builds one
  ``PRO_SURFCOLL_SINGLE_SURF`` instruction per item (``native/advanced.cpp``).
  The claim "draft needs face-by-face references" is therefore confirmed.
* Surface ids only exist after the body exists and have to be read back with
  ``creo_inspect_model``, so a taper cannot be produced by the same plan that
  creates the body. That is the real F10 gap: no single-step taper entry, not
  a missing draft tool.

Consequently this contract adds taper options to ``extrude`` and leaves
``creo_draft`` semantics untouched. Every taper value needs a real-model
volume/geometry check before it can be claimed to work, because BUG-102 proved
that the stored element flip does not equal the requested direction.
"""

from __future__ import annotations

import math
from typing import Any

CONTRACT_VERSION = "C1.F10.design-1"
STATUS = "designed_not_implemented"

FIELDS = ("draft_angle", "top_scale")
ALLOWED_KEYS = FIELDS
DEFAULTS = {"draft_angle": None, "top_scale": None}

#: Exclusive bounds, the same domain as ``DraftOp.angle`` (``gt=-85, lt=85`` plus
#: a nonzero guard), so one angle rule covers both the two-step ``creo_draft``
#: route and the one-step taper.
ANGLE_LIMIT_DEG = 85.0
MIN_MAGNITUDE = 1e-9
#: ``top_scale`` is multiplicatively symmetric: 100x narrower and 100x wider.
#: ``1.0`` is refused within ``MIN_MAGNITUDE`` because it is not a taper.
TOP_SCALE_MIN = 0.01
TOP_SCALE_MAX = 100.0
TOP_SCALE_ONE = 1.0

#: Only operation/mode combinations with one unambiguous neutral plane.
SUPPORTED_OPERATIONS = ("extrude",)
SUPPORTED_MODES = ("add",)
SUPPORTED_DIRECTIONS = ("positive", "negative")
SUPPORTED_DEPTH_TYPES = ("blind",)
NEUTRAL_PLANE = "sketch_plane"
#: A new body does not move the neutral plane, so it stays allowed.
NEW_BODY_ALLOWED = True

#: ``top_scale`` is only defined where a scale factor and an angle agree
#: exactly: one closed circular profile. Regular polygons are a plausible
#: extension but are not claimed here (open item in the SDD contract note).
TOP_SCALE_PROFILE = "one closed circular profile"

#: Values whose behaviour cannot be claimed without a real-model volume check.
NATIVE_VALIDATION_REQUIRED = FIELDS

#: The route that already exists today and must not be re-documented as new
#: capability: a two-step extrude-then-draft with face ids read back after the
#: extrude. Kept as executable text so B6 cannot drift from the falsification.
DRAFT_TOOL_ROUTE = {
    "tool": "creo_draft",
    "requires": (
        "one or more bare surface references (per face, PRO_SURFCOLL_SINGLE_SURF), "
        "a neutral plane and a nonzero angle"
    ),
    "surface_source": "creo_inspect_model surfaces[].id after the body exists",
    "surface_selector": "none: no body-, feature- or wildcard-level surface selector",
    "evidence": "FEAT-051 run2 2026-10-31 and BUG-102 2026-11-07, Creo 12.4.0.0",
}

#: A shape whose two ends differ by more than one constant angle (the report's
#: 3x3 m to 1.6x1.2 m frustum) has no single angle and no single scale. It stays
#: with the two-section loft family instead of being approximated here.
NON_UNIFORM_TAPER_ROUTE = {
    "requirement": "two closed sections whose walls are not all at one constant angle",
    "route": "F01/B1 two-section loft family",
    "status": "not_designed_here",
}

SUBMISSION_ERROR_CODES = (
    "F10_TAPER_INVALID_OPTIONS",
    "F10_TAPER_INVALID_ANGLE",
    "F10_TAPER_INVALID_TOP_SCALE",
    "F10_TAPER_AMBIGUOUS_INPUT",
    "F10_TAPER_UNSUPPORTED_OPERATION",
)
NATIVE_ERROR_CODES = (
    "F10_TAPER_PROFILE_UNSUPPORTED",
    "F10_TAPER_ELEMENT_UNAVAILABLE",
    "F10_TAPER_CREATE_FAILED",
    "F10_TAPER_DIRECTION_MISMATCH",
    "F10_TAPER_NO_MATERIAL_CHANGE",
)
ERROR_CODES = SUBMISSION_ERROR_CODES + NATIVE_ERROR_CODES
MAX_ERROR_MESSAGE_CHARS = 600

ERROR_MESSAGES = {
    "F10_TAPER_INVALID_OPTIONS": (
        "taper options must be an object containing only draft_angle and top_scale; "
        "see creo_capabilities known_limitations.extrude_taper"
    ),
    "F10_TAPER_INVALID_ANGLE": (
        "draft_angle must be a nonzero number of degrees strictly between -85 and 85"
    ),
    "F10_TAPER_INVALID_TOP_SCALE": (
        "top_scale must be a number above 0 and at most 10 that is not 1; it is "
        "defined only for one closed circular profile"
    ),
    "F10_TAPER_AMBIGUOUS_INPUT": (
        "give either draft_angle or top_scale, not both; the two describe the same taper"
    ),
    "F10_TAPER_UNSUPPORTED_OPERATION": (
        "taper is supported only for extrude with mode=add, direction=positive or "
        "negative, depth_type=blind and no thin wall"
    ),
    "F10_TAPER_PROFILE_UNSUPPORTED": (
        "top_scale needs exactly one closed circular profile; use draft_angle for "
        "other profiles instead of an approximated scale"
    ),
    "F10_TAPER_ELEMENT_UNAVAILABLE": (
        "the native executor could not apply the draft element to this extrude; no "
        "taper is claimed and the straight extrude is rolled back"
    ),
    "F10_TAPER_CREATE_FAILED": (
        "the kernel rejected the tapered extrude; the raw Toolkit code and the "
        "bounded element diagnosis carry the reason and the model is rolled back"
    ),
    "F10_TAPER_DIRECTION_MISMATCH": (
        "the measured taper went the opposite way from the request; read "
        "taper.taper_direction and correct the sign before relying on the geometry"
    ),
    "F10_TAPER_NO_MATERIAL_CHANGE": (
        "the taper produced no measurable material change; the angle is accepted by "
        "the kernel but the geometry did not move"
    ),
}

LIMITATION_ID = "extrude_taper"
LIMITATION_NOTE = (
    "one-step taper needs the native draft element plus a measured volume check; "
    "creo_draft still needs per-surface ids from creo_inspect_model"
)

TAPER_RECEIPT_FIELDS = (
    "requested_angle_deg",
    "requested_top_scale",
    "effective_angle_deg",
    "angle_source",
    "neutral_plane",
    "taper_direction",
    "volume_delta_mm3",
    "query_code",
)
TAPER_DIRECTIONS = ("inward", "outward")
ANGLE_SOURCE_FEATURE_TREE = "feature_tree"
ANGLE_SOURCE_UNAVAILABLE = "unavailable"
COMPACT_RESULT_KEYS = ("taper",)
PUBLIC_DOCUMENTATION_TARGETS = (
    "draft_angle",
    "top_scale",
    "taper",
)

_FALLBACK_MESSAGE = "invalid taper options; see creo_capabilities known_limitations.extrude_taper"


def error_message(code: str) -> str:
    """Bounded, input-free guidance for one contract error code."""
    return ERROR_MESSAGES.get(code, _FALLBACK_MESSAGE)


def _verdict(
    accepted: bool,
    *,
    code: str | None,
    options: dict[str, Any] | None,
    defaulted: bool,
    native_validation_required: bool,
):
    return {
        "accepted": accepted,
        "code": code,
        "options": options,
        "defaulted": defaulted,
        "native_validation_required": native_validation_required,
    }


def _reject(code: str):
    return _verdict(
        False,
        code=code,
        options=None,
        defaulted=False,
        native_validation_required=False,
    )


def _number(value: Any) -> float | None:
    """Finite float or None.

    Booleans are not numbers. Only ``int``/``float`` are accepted because the
    public entry parses JSON; a ``Decimal`` or numpy scalar reaching this
    function would be a caller-side defect, not a taper value.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def implied_angle_deg(radius_mm: float, depth_mm: float, top_scale: float) -> float:
    """Angle that ``top_scale`` implies on one closed circular profile.

    ``tan(angle) = radius * (1 - top_scale) / depth``: a scale below 1 narrows
    the far section, so the value is positive for an inward taper and negative
    for an outward one. This is the only exact scale-to-angle mapping the
    contract claims; it is why ``top_scale`` is limited to circles.
    """
    return math.degrees(math.atan(radius_mm * (1.0 - top_scale) / depth_mm))


def validate_taper_options(
    payload: Any,
    *,
    operation: str = "extrude",
    mode: str = "add",
    direction: str = "positive",
    depth_type: str = "blind",
    thin: Any = None,
    radius_mm: float | None = None,
    depth_mm: float | None = None,
) -> dict[str, Any]:
    """Validate optional taper parameters before any job is submitted.

    Returns a bounded receipt: ``accepted``, ``code``, normalized ``options``,
    ``defaulted`` and ``native_validation_required``. ``defaulted`` is true only
    when the whole options object was omitted. Every accepted value is marked
    ``native_validation_required``: no taper is claimed to work before a
    real-model volume/geometry check, and the stored element flip is not
    evidence of the requested direction (BUG-102).

    No taper requested means no new restriction: the current straight extrude,
    cut, symmetric, through-all and thin combinations stay accepted. The
    operation/mode gate only applies once a taper is actually asked for.

    When ``radius_mm`` and ``depth_mm`` are known (the referenced sketch circle
    is visible to the caller), ``top_scale`` is also checked against the same
    ``ANGLE_LIMIT_DEG`` domain through :func:`implied_angle_deg`. A pre-existing
    sketch is checked natively and reuses ``F10_TAPER_INVALID_TOP_SCALE``,
    because that is a caller-value error rather than a kernel error.

    This function never changes existing extrude behaviour, never creates a
    feature and never claims that ``creo_draft`` can replace a taper.
    """
    if not isinstance(payload, dict) or set(payload) - set(ALLOWED_KEYS):
        return _reject("F10_TAPER_INVALID_OPTIONS")
    options = dict(DEFAULTS)
    defaulted = not bool(payload)
    angle = payload.get("draft_angle")
    scale = payload.get("top_scale")
    if angle is not None and scale is not None:
        return _reject("F10_TAPER_AMBIGUOUS_INPUT")
    if "draft_angle" in payload and angle is not None:
        number = _number(angle)
        if number is None:
            return _reject("F10_TAPER_INVALID_ANGLE")
        if abs(number) < MIN_MAGNITUDE or abs(number) >= ANGLE_LIMIT_DEG:
            return _reject("F10_TAPER_INVALID_ANGLE")
        options["draft_angle"] = number
    if "top_scale" in payload and scale is not None:
        number = _number(scale)
        if number is None:
            return _reject("F10_TAPER_INVALID_TOP_SCALE")
        if (
            number < TOP_SCALE_MIN
            or number > TOP_SCALE_MAX
            or abs(number - TOP_SCALE_ONE) < MIN_MAGNITUDE
        ):
            return _reject("F10_TAPER_INVALID_TOP_SCALE")
        if radius_mm is not None and depth_mm is not None:
            try:
                implied = implied_angle_deg(float(radius_mm), float(depth_mm), number)
            except (TypeError, ValueError, ZeroDivisionError):
                return _reject("F10_TAPER_INVALID_TOP_SCALE")
            if not math.isfinite(implied) or abs(implied) >= ANGLE_LIMIT_DEG:
                return _reject("F10_TAPER_INVALID_TOP_SCALE")
        options["top_scale"] = number
    requested = any(options[field] is not None for field in NATIVE_VALIDATION_REQUIRED)
    if not requested:
        return _verdict(
            True,
            code=None,
            options=options,
            defaulted=defaulted,
            native_validation_required=False,
        )
    if (
        operation not in SUPPORTED_OPERATIONS
        or mode not in SUPPORTED_MODES
        or direction not in SUPPORTED_DIRECTIONS
        or depth_type not in SUPPORTED_DEPTH_TYPES
        or thin is not None
    ):
        return _reject("F10_TAPER_UNSUPPORTED_OPERATION")
    return _verdict(
        True,
        code=None,
        options=options,
        defaulted=defaulted,
        native_validation_required=True,
    )
