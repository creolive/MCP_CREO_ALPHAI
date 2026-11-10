"""C1/F08: frozen design contract for a selective extrusion cut scope.

Status: ``implemented`` for the first native pass (B4, 2026-11-10). The
namespace, error codes and limitation text below are the single source of
truth for ``ExtrudeOp.scope``, ``creo_extrude(scope=...)`` and the native
executor.

Design decisions (see the SDD C1 contract note for the full rationale):

* ``scope`` is deliberately **not** named ``targets`` and does not reuse
  ``BooleanOp.targets``. That field is a required, body-only reference list for
  ``boolean_bodies``; a cut scope is optional and must keep the current global
  ``PRO_BODY_USE_ALL`` behaviour when omitted.
* Only positive body IDs are supported. Feature labels, surface references and
  negative IDs from inspection are out of scope for the first native pass.
* One target body per cut: the Creo 12 Toolkit extrude body branch has a single
  ``PRO_E_BODY_SELECT`` selection element (``ProBodyOpts.h``), so ``body_ids``
  is limited to one entry and several targets become several cut operations.
  This is the 2026-11-10 amendment to the original 100-body design.
* ``through_all`` and ``new_body`` combinations are refused until a real-model
  test proves the selected-body element tree interacts correctly with them.
* Applied scope evidence must come from the created feature's element tree,
  never from the request (FEAT-051 ``reference_application`` precedent).
* An explicit ``scope=None`` means "no scope requested" and is accepted for any
  operation; only a non-null scope is restricted to extrude cuts.
"""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "C1.F08.design-2"
STATUS = "implemented"

FIELD = "scope"
DEFAULT = None
OPERATIONS = ("extrude",)
MODE = "cut"
SUPPORTED_KIND = "bodies"
SCOPE_ALLOWED_KEYS = ("kind", "body_ids")
MIN_BODY_ID = 1
#: B4 pre-implementation check (2026-11-10): the Creo 12 Toolkit extrude body
#: branch exposes only ``PRO_E_BODY_USE`` + ``PRO_E_BODY_SELECT``, and that
#: element is a single ``PRO_VALUE_TYPE_SELECTION`` (``ProBodyOpts.h``). A cut
#: therefore names exactly one target body; several targets need several cut
#: operations. The list shape is kept for forward compatibility.
MAX_BODY_IDS = 1

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
NATIVE_ERROR_CODES = (
    "F08_SCOPE_RESOLVE_FAILED",
    "F08_SCOPE_NON_TARGET_CHANGED",
)
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
        "scope.body_ids names exactly one target body per cut; the native body branch "
        "has a single body selection, so split several targets into separate cut operations"
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
    "F08_SCOPE_NON_TARGET_CHANGED": (
        "a body outside scope.body_ids changed; the cut was rolled back because it "
        "touched geometry it was told to leave alone"
    ),
}

LIMITATION_ID = "cut_scope"
LIMITATION_NOTE = (
    "extrude cut scope takes one positive body ID per cut; feature-label scope, "
    "revolve cuts, through_all and several targets per cut are unsupported"
)

APPLIED_RECEIPT_FIELDS = (
    "requested_body_ids",
    "applied_body_ids",
    "source",
    "query_code",
    "non_target_bodies_unchanged",
)
APPLIED_RECEIPT_SOURCE = "feature_tree"
#: ``scope_rejection`` is reserved for an operation record that carries its own
#: refusal. Shape rejections happen before a job exists, so they surface as
#: tool errors today and no operation record produces this key yet.
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
    if any(type(value) is not int or value < MIN_BODY_ID for value in body_ids):
        return _reject("F08_SCOPE_INVALID_BODY_ID")
    # Duplicates are reported before the count rule so [12, 12] explains the
    # repeat instead of only complaining about two entries.
    if len(set(body_ids)) != len(body_ids):
        return _reject("F08_SCOPE_DUPLICATE_BODY_ID")
    if len(body_ids) > MAX_BODY_IDS:
        return _reject("F08_SCOPE_TOO_MANY_BODIES")
    if operation.get("depth_type") == "through_all":
        return _reject("F08_SCOPE_THROUGH_ALL_UNSUPPORTED")
    if operation.get("new_body") is True:
        return _reject("F08_SCOPE_NEW_BODY_UNSUPPORTED")
    return _verdict(True, defaulted=False, body_ids=list(body_ids), code=None)
