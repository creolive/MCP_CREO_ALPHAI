"""C1/F09: frozen design contract for configurable raster previews.

Status: ``designed_not_implemented``. Nothing in the public MCP surface reads
this module yet. B5 must import these constants as its single source of truth
instead of redefining parameter names, error codes or the limitation text.

Design decisions (full rationale in the SDD C1-F09 contract note):

* Defaults reproduce today's behaviour exactly: the fixed isometric matrix
  (``native/preview.h:31-38``) and the single ``ProWindowRefit`` call
  (``:407-412``). ``preview_mode=None`` means "do not set a display style",
  which is what the current native path does; changing the default to shaded
  would silently change every existing client's preview.
* The same options apply to the automatic job preview (``creo_execute_plan``)
  and the explicit JPEG export (``creo_export_model(format="jpeg")``), because
  DEV-047 T07 / BUG-066 deliberately route both through ``capture_preview``.
* This machine's Toolkit SDK has no model-window display-style readback
  (``docs/work-items/DEV-047.md:156``, ``BUG-066.md:57``). ``shaded``,
  ``shaded_with_edges`` and non-isometric views are therefore marked
  ``native_validation_required``; `applied_mode` must come from a session
  option readback, never from the request.
* ``PreviewDatumDisplayGuard`` (``preview.h:199-301``) hides datum options for
  assemblies only and never hides sketches. Report P9 asks for sketches,
  datum planes, axes and coordinate systems to be hidden by default, so this
  is a native change, not a documentation claim.
* A written file is not a readable image. ``preview.py:170-180`` currently
  calls a preview successful when the raster code is 0 and the file is
  non-empty; ``readability`` therefore defaults to ``"unverified"`` and may
  only become ``"verified"`` after real-model screenshot comparison.
"""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "C1.F09.design-1"
STATUS = "designed_not_implemented"

FIELDS = ("preview_mode", "view", "fit_all")
ALLOWED_KEYS = FIELDS
PREVIEW_MODES = ("wireframe", "shaded", "shaded_with_edges")
VIEWS = ("iso", "front", "top", "right")
DEFAULTS = {"preview_mode": None, "view": "iso", "fit_all": True}
EXISTING_VIEW = "iso"
EXISTING_FIT_ALL = True
OPERATION_SURFACES = ("creo_execute_plan", "creo_export_model")

#: Values whose behaviour cannot be claimed without real-model screenshots.
NATIVE_VALIDATION_REQUIRED = (
    "shaded",
    "shaded_with_edges",
    "front",
    "top",
    "right",
)

SUBMISSION_ERROR_CODES = (
    "F09_PREVIEW_INVALID_OPTIONS",
    "F09_PREVIEW_INVALID_MODE",
    "F09_PREVIEW_INVALID_VIEW",
    "F09_PREVIEW_INVALID_FIT_ALL",
)
NATIVE_ERROR_CODES = (
    "F09_PREVIEW_DISPLAY_STYLE_UNAVAILABLE",
    "F09_PREVIEW_DATUM_HIDE_FAILED",
    "F09_PREVIEW_VIEW_MATRIX_MISMATCH",
    "F09_PREVIEW_CAPTURE_FAILED",
)
ERROR_CODES = SUBMISSION_ERROR_CODES + NATIVE_ERROR_CODES
MAX_ERROR_MESSAGE_CHARS = 600

ERROR_MESSAGES = {
    "F09_PREVIEW_INVALID_OPTIONS": (
        "preview options must be an object containing only preview_mode, view "
        "and fit_all; see creo_capabilities known_limitations.preview_appearance"
    ),
    "F09_PREVIEW_INVALID_MODE": (
        "preview_mode must be wireframe, shaded, shaded_with_edges or null to "
        "keep the current session display style"
    ),
    "F09_PREVIEW_INVALID_VIEW": (
        "view must be iso, front, top or right; other orientations need their "
        "own native view matrix"
    ),
    "F09_PREVIEW_INVALID_FIT_ALL": (
        "fit_all must be a boolean; true keeps today's ProWindowRefit call"
    ),
    "F09_PREVIEW_DISPLAY_STYLE_UNAVAILABLE": (
        "the native executor could not set or read back the requested display "
        "style; no shading claim is made"
    ),
    "F09_PREVIEW_DATUM_HIDE_FAILED": (
        "the native executor could not hide sketch or datum annotations; the "
        "preview may still contain overlays"
    ),
    "F09_PREVIEW_VIEW_MATRIX_MISMATCH": (
        "the requested view matrix did not match the readback; the preview "
        "orientation is not confirmed"
    ),
    "F09_PREVIEW_CAPTURE_FAILED": (
        "raster capture failed; preview_status and preview_code carry the raw Toolkit codes"
    ),
}

LIMITATION_ID = "preview_appearance"
LIMITATION_NOTE = (
    "preview appearance is unverified without real-model screenshot comparison; "
    "file written does not mean shaded or readable; datum hide is assembly-only"
)

APPEARANCE_RECEIPT_FIELDS = (
    "requested_mode",
    "applied_mode",
    "mode_source",
    "requested_view",
    "view_matrix_matches",
    "fit_all_applied",
    "annotations_hidden",
    "readability",
)
READABILITY_DEFAULT = "unverified"
MODE_SOURCE_UNAVAILABLE = "unavailable"
COMPACT_RESULT_KEYS = ("preview_appearance",)
PUBLIC_DOCUMENTATION_TARGETS = (
    "preview_mode",
    "view",
    "fit_all",
    "preview_appearance",
)

_FALLBACK_MESSAGE = (
    "invalid preview options; see creo_capabilities known_limitations.preview_appearance"
)


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


def validate_preview_options(payload: Any) -> dict[str, Any]:
    """Validate optional preview parameters before any job is submitted.

    Returns a bounded receipt: ``accepted``, ``code``, normalized ``options``,
    ``defaulted`` and ``native_validation_required``. ``defaulted`` is true only
    when the whole options object was omitted; ``native_validation_required``
    is true for any value that needs a real-model screenshot before it can be
    claimed to work (shading, a non-isometric view or disabling the refit).
    Rejection receipts never echo malformed values; this function never changes
    existing preview behaviour, never writes a file and never claims an image
    is readable.
    """
    if not isinstance(payload, dict) or set(payload) - set(ALLOWED_KEYS):
        return _reject("F09_PREVIEW_INVALID_OPTIONS")
    options = dict(DEFAULTS)
    defaulted = not bool(payload)
    if "preview_mode" in payload:
        mode = payload["preview_mode"]
        if mode is not None and mode not in PREVIEW_MODES:
            return _reject("F09_PREVIEW_INVALID_MODE")
        options["preview_mode"] = mode
    if "view" in payload:
        view = payload["view"]
        if view not in VIEWS:
            return _reject("F09_PREVIEW_INVALID_VIEW")
        options["view"] = view
    if "fit_all" in payload:
        fit_all = payload["fit_all"]
        if type(fit_all) is not bool:
            return _reject("F09_PREVIEW_INVALID_FIT_ALL")
        options["fit_all"] = fit_all
    requested = (options["preview_mode"], options["view"])
    required = (
        any(value in NATIVE_VALIDATION_REQUIRED for value in requested if value is not None)
        or options["fit_all"] is False
    )
    return _verdict(
        True,
        code=None,
        options=options,
        defaulted=defaulted,
        native_validation_required=required,
    )
