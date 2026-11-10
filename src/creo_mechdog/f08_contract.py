"""C1/F08: frozen design contract for a selective extrusion cut scope.

Status: ``designed_not_implemented``. Nothing in the public MCP surface reads
this module yet. B4 must import these constants as its single source of truth
instead of redefining field names, error codes or the limitation text; only
then may ``ExtrudeOp`` / ``creo_extrude`` / the native executor change.

Design decisions (see the SDD C1 contract note for the full rationale):

* ``scope`` is deliberately **not** named ``targets`` and does not reuse
  ``BooleanOp.targets``. That field is a required, body-only reference list for
  ``boolean_bodies``; a cut scope is optional and must keep the current global
  ``PRO_BODY_USE_ALL`` behaviour when omitted.
* Only positive body IDs are supported. Feature labels, surface references and
  negative IDs from inspection are out of scope for the first native pass.
* ``through_all`` and ``new_body`` combinations are refused until a real-model
  test proves the selected-body element tree interacts correctly with them.
* Applied scope evidence must come from the created feature's element tree,
  never from the request (FEAT-051 ``reference_application`` precedent).
* An explicit ``scope=None`` means "no scope requested" and is accepted for any
  operation; only a non-null scope is restricted to extrude cuts.
"""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "C1.F08.design-1"
STATUS = "designed_not_implemented"

FIELD = "scope"
DEFAULT = None
OPERATIONS = ("extrude",)
MODE = "cut"
SUPPORTED_KIND = "bodies"
SCOPE_ALLOWED_KEYS = ("kind", "body_ids")
MIN_BODY_ID = 1
MAX_BODY_IDS = 100

SUBMISSION_ERROR_CODES = (
    "F08_SCOPE_INVALID_SHAPE",
    "F08_SCOPE_UNSUPPORTED_KIND",
    "F08_SCOPE_INVALID_BODY_ID",
    "F08_SCOPE_DUPLICATE_BODY_ID",
    "F08_SCOPE_TOO_MANY_BODIES",
    "F08_SCOPE_MODE_UNSUPPORTED",
    "F08_SCOPE_THROUGH_ALL_UNSUPPORTED",
    "F08_SCOPE_NEW_BODY_UNSUPPORTED",
)
NATIVE_ERROR_CODES = ("F08_SCOPE_RESOLVE_FAILED",)
ERROR_CODES = SUBMISSION_ERROR_CODES + NATIVE_ERROR_CODES
MAX_ERROR_MESSAGE_CHARS = 600

ERROR_MESSAGES = {
    "F08_SCOPE_INVALID_SHAPE": (
        "scope must be an object with kind='bodies' and a non-empty body_ids list; "
        "remove target_labels/feature_labels and see creo_capabilities "
        "known_limitations.cut_scope"
    ),
    "F08_SCOPE_UNSUPPORTED_KIND": (
        "scope.kind must be 'bodies'; feature-label and surface scopes are not "
        "supported by the native executor"
    ),
    "F08_SCOPE_INVALID_BODY_ID": (
        "scope.body_ids must contain positive integer body IDs; negative IDs from "
        "inspection are unsupported, see creo_capabilities known_limitations.cut_scope"
    ),
    "F08_SCOPE_DUPLICATE_BODY_ID": (
        "scope.body_ids must not repeat a body ID; submit each target body once"
    ),
    "F08_SCOPE_TOO_MANY_BODIES": (
        "scope.body_ids supports at most 100 bodies; split the cut into separate operations"
    ),
    "F08_SCOPE_MODE_UNSUPPORTED": (
        "scope applies only to extrude cuts; remove scope from other operations "
        "and see creo_capabilities known_limitations.cut_scope"
    ),
    "F08_SCOPE_THROUGH_ALL_UNSUPPORTED": (
        "scope with through_all is not yet validated against the native executor; "
        "use blind depth or omit scope"
    ),
    "F08_SCOPE_NEW_BODY_UNSUPPORTED": (
        "scope cannot be combined with new_body; a scoped cut does not create a new body"
    ),
    "F08_SCOPE_RESOLVE_FAILED": (
        "the native executor could not resolve the requested scope body IDs from "
        "the created feature; no geometry claim is made"
    ),
}

LIMITATION_ID = "cut_scope"
LIMITATION_NOTE = (
    "extrude cut scope takes positive body IDs only; feature-label scope, revolve "
    "cuts and through_all are unverified; non-target bodies need native proof"
)

APPLIED_RECEIPT_FIELDS = (
    "requested_body_ids",
    "applied_body_ids",
    "source",
    "query_code",
    "non_target_bodies_unchanged",
)
APPLIED_RECEIPT_SOURCE = "feature_tree"
COMPACT_OPERATION_KEYS = ("scope_applied", "scope_rejection")
PUBLIC_DOCUMENTATION_TARGETS = (
    "scope",
    "scope_applied",
    "cut_scope",
)

_FALLBACK_MESSAGE = "invalid extrude cut scope; see creo_capabilities known_limitations.cut_scope"


def error_message(code: str) -> str:
    """Bounded, input-free guidance for one contract error code."""
    return ERROR_MESSAGES.get(code, _FALLBACK_MESSAGE)


def _verdict(accepted: bool, *, defaulted: bool, body_ids: list[int] | None, code: str | None):
    return {
        "accepted": accepted,
        "defaulted": defaulted,
        "body_ids": body_ids,
        "code": code,
    }


def _reject(code: str):
    return _verdict(False, defaulted=False, body_ids=None, code=code)


def validate_scope(operation: dict[str, Any]) -> dict[str, Any]:
    """Validate an optional cut scope before any job is submitted.

    Returns a bounded receipt only: ``accepted``, ``defaulted``, ``body_ids``
    and ``code``. Rejection receipts never echo the malformed value; an accepted
    receipt returns only the normalized body IDs. It never mutates the
    operation and never claims that any geometry was produced. ``defaulted``
    distinguishes an omitted scope (the existing global cut) from an explicit
    one, and must not enter ``defaulted_fields`` in the native receipt.
    """
    if not isinstance(operation, dict):
        return _reject("F08_SCOPE_INVALID_SHAPE")
    scope = operation.get(FIELD)
    if scope is None:
        return _verdict(
            True,
            defaulted=FIELD not in operation,
            body_ids=None,
            code=None,
        )
    if operation.get("op") not in OPERATIONS or operation.get("mode") != MODE:
        return _reject("F08_SCOPE_MODE_UNSUPPORTED")
    if (
        not isinstance(scope, dict)
        or set(scope) - set(SCOPE_ALLOWED_KEYS)
        or not set(SCOPE_ALLOWED_KEYS) <= set(scope)
    ):
        return _reject("F08_SCOPE_INVALID_SHAPE")
    if scope.get("kind") != SUPPORTED_KIND:
        return _reject("F08_SCOPE_UNSUPPORTED_KIND")
    body_ids = scope.get("body_ids")
    if not isinstance(body_ids, list) or not body_ids:
        return _reject("F08_SCOPE_INVALID_SHAPE")
    if len(body_ids) > MAX_BODY_IDS:
        return _reject("F08_SCOPE_TOO_MANY_BODIES")
    if any(type(value) is not int or value < MIN_BODY_ID for value in body_ids):
        return _reject("F08_SCOPE_INVALID_BODY_ID")
    if len(set(body_ids)) != len(body_ids):
        return _reject("F08_SCOPE_DUPLICATE_BODY_ID")
    if operation.get("depth_type") == "through_all":
        return _reject("F08_SCOPE_THROUGH_ALL_UNSUPPORTED")
    if operation.get("new_body") is True:
        return _reject("F08_SCOPE_NEW_BODY_UNSUPPORTED")
    return _verdict(True, defaulted=False, body_ids=list(body_ids), code=None)
