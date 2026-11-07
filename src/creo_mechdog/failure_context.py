"""FEAT-012 / FEAT-008: one bounded failure context for failed jobs.

The native executor publishes ``failed_operation`` beside
``failed_operation_index`` with only reported facts: the failing input's index,
operation kind, stage, names, the failing Toolkit call and its raw ``ProError``
(or an explicit null plus a provenance ``source``), a length-bounded message,
and — for placement failures — the caller's own 4x4 row-vector matrix with its
determinant and orthogonality residual. The matrix is echoed, never
orthonormalized, normalized or transposed, and the batch rollback stays atomic.

This module keeps persisted job results on that frozen contract. Legacy
executors that only published an index are backfilled from fields the result
already carries (``failed_stage``, ``failed_toolkit_call`` and the requested
operations); no Toolkit code is ever fabricated.
"""

from __future__ import annotations

import math
from typing import Any

from creo_mechdog.rotation_admission import PRECISION_ADVICE

#: The raw message is cut to this many characters (the native producer cuts at
#: the same byte budget). ``message_truncated`` records that a cut happened.
FAILED_OPERATION_MESSAGE_LIMIT = 512

#: Operations that place a component with a caller-supplied pose. Only these
#: carry the echoed 4x4 matrix, determinant and orthogonality residual.
PLACEMENT_OPERATIONS = ("assemble_component", "component_placement")

PRO_ERROR_SOURCES = ("toolkit", "unsupported")

_MATRIX_FIELDS = (
    "input_matrix",
    "matrix_source",
    "determinant",
    "orthogonality_residual",
    # BUG-045/FEAT-012: the numerical class of the admitted pose plus an
    # actionable note. Advice never claims a cause for a kernel rejection.
    "precision_class",
    "precision_advice",
)


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _integer(value: Any) -> int | None:
    # A Toolkit code may be negative; only its type matters.
    return value if type(value) is int and not isinstance(value, bool) else None


def _number(value: Any) -> float | None:
    if type(value) not in (int, float) or isinstance(value, bool):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _vector3(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 3:
        return None
    numbers: list[float] = []
    for item in value:
        number = _number(item)
        if number is None:
            return None
        numbers.append(number)
    return numbers


def bounded_message(value: Any) -> tuple[str | None, bool]:
    """Return the raw message cut to the fixed bound, plus the cut flag."""
    if not isinstance(value, str) or not value:
        return None, False
    if len(value) <= FAILED_OPERATION_MESSAGE_LIMIT:
        return value, False
    return value[:FAILED_OPERATION_MESSAGE_LIMIT], True


def _determinant(rotation: list[list[float]]) -> float:
    return (
        rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
        - rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
        + rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0])
    )


def _orthogonality_residual(rotation: list[list[float]]) -> float:
    residual = 0.0
    for left in range(3):
        for right in range(3):
            dot = sum(rotation[left][k] * rotation[right][k] for k in range(3))
            residual = max(residual, abs(dot - (1.0 if left == right else 0.0)))
    return residual


def _euler_rows(euler: list[float]) -> list[list[float]]:
    """Mirror of native/assembly_pose.h: row vectors, transposed Rz Ry Rx."""
    radians = math.pi / 180
    x, y, z = (component * radians for component in euler)
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    columns = (
        [cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
        [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
        [-sy, cy * sx, cy * cx],
    )
    return [[columns[column][row] for column in range(3)] for row in range(3)]


def _precision(residual: float) -> dict[str, Any]:
    """Classify the admitted rotation; advice is a numerical fact, not a cause."""
    if residual <= 1e-9:
        return {"precision_class": "strict", "precision_advice": None}
    if residual <= 1e-6:
        return {
            "precision_class": "near_orthonormal",
            "precision_advice": PRECISION_ADVICE.format(residual=residual),
        }
    return {"precision_class": "invalid", "precision_advice": None}


def _matrix_block(
    rotation: list[list[float]], translation: list[float], source: str
) -> dict[str, Any]:
    determinant = _determinant(rotation)
    residual = _orthogonality_residual(rotation)
    if not math.isfinite(determinant) or not math.isfinite(residual):
        return {}
    matrix = [[float(rotation[row][column]) for column in range(3)] + [0.0] for row in range(3)]
    matrix.append([float(value) for value in translation] + [1.0])
    return {
        "input_matrix": matrix,
        "matrix_source": source,
        "determinant": determinant,
        "orthogonality_residual": residual,
        **_precision(residual),
    }


def placement_matrix(operation: Any) -> dict[str, Any]:
    """Echo the requested pose as the 4x4 row-vector matrix the kernel receives.

    A ``rotation_matrix`` input is echoed verbatim (no repair or transpose); a
    three-angle ``rotation`` input is expanded with the same row-vector
    convention the native side uses and tagged ``matrix_source: "euler"``.
    Unusable input leaves every matrix field null.
    """
    if not isinstance(operation, dict):
        return {}
    translation = operation.get("translation")
    translation = [0.0, 0.0, 0.0] if translation is None else _vector3(translation)
    if translation is None:
        return {}
    raw_matrix = operation.get("rotation_matrix")
    if raw_matrix is not None:
        if not isinstance(raw_matrix, list) or len(raw_matrix) != 3:
            return {}
        rotation: list[list[float]] = []
        for row in raw_matrix:
            numbers = _vector3(row)
            if numbers is None:
                return {}
            rotation.append(numbers)
        return _matrix_block(rotation, translation, "rotation_matrix")
    euler = operation.get("rotation")
    euler = [0.0, 0.0, 0.0] if euler is None else _vector3(euler)
    if euler is None:
        return {}
    return _matrix_block(_euler_rows(euler), translation, "euler")


def _vector4(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    numbers: list[float] = []
    for item in value:
        number = _number(item)
        if number is None:
            return None
        numbers.append(number)
    return numbers


def _native_matrix(block: dict[str, Any]) -> dict[str, Any]:
    """Project a native matrix echo, recomputing only arithmetic on that echo."""
    matrix = block.get("input_matrix")
    if not isinstance(matrix, list) or len(matrix) != 4:
        return {}
    rows: list[list[float]] = []
    for row in matrix:
        numbers = _vector4(row)
        if numbers is None:
            return {}
        rows.append(numbers)
    rotation = rows[:3]
    determinant = _number(block.get("determinant"))
    residual = _number(block.get("orthogonality_residual"))
    residual = residual if residual is not None else _orthogonality_residual(rotation)
    return {
        "input_matrix": rows,
        "matrix_source": _text(block.get("matrix_source")),
        "determinant": determinant if determinant is not None else _determinant(rotation),
        "orthogonality_residual": residual,
        **_precision(residual),
    }


def annotate_failed_operation(result: dict[str, Any], inputs: Any = None) -> dict[str, Any]:
    """Publish one bounded ``failed_operation`` block on a failed result.

    Successful results never carry the block. On failure every key is present
    and stable; a value the result cannot support stays ``null`` and
    ``pro_error_source`` says whether the code came from a real Toolkit call
    (``toolkit``) or was unavailable (``unsupported``).
    """
    if not isinstance(result, dict):
        return result
    if result.get("success") is True:
        result.pop("failed_operation", None)
        return result
    operations = inputs if isinstance(inputs, list) else None
    native = result.get("failed_operation")
    native = native if isinstance(native, dict) else {}
    index = _integer(native.get("index"))
    if index is None:
        index = _integer(result.get("failed_operation_index"))
    failing = None
    if operations is not None and index is not None and 0 <= index < len(operations):
        candidate = operations[index]
        failing = candidate if isinstance(candidate, dict) else None
    operation = _text(native.get("operation"))
    if operation is None and failing is not None:
        operation = _text(failing.get("op"))
    block: dict[str, Any] = {
        "index": index,
        "operation": operation,
        "stage": _text(native.get("stage")) or _text(result.get("failed_stage")),
        "feature_label": (
            _text(native.get("feature_label"))
            or _text(failing.get("label") if failing is not None else None)
        ),
        "sketch_name": (
            _text(native.get("sketch_name"))
            or _text(failing.get("sketch") if failing is not None else None)
        ),
        "toolkit_call": (
            _text(native.get("toolkit_call")) or _text(result.get("failed_toolkit_call"))
        ),
    }
    if "pro_error" in native or "pro_error_source" in native:
        pro_error = _integer(native.get("pro_error"))
        source = _text(native.get("pro_error_source"))
        source = (
            source
            if source in PRO_ERROR_SOURCES
            else ("toolkit" if pro_error is not None else "unsupported")
        )
    else:
        code = _integer(result.get("toolkit_code"))
        if block["toolkit_call"] and code is not None:
            pro_error, source = code, "toolkit"
        else:
            pro_error, source = None, "unsupported"
    raw_message = native.get("message")
    if isinstance(native.get("solver"), dict):
        from creo_mechdog.geometry_deviation import normalize_solver_receipt

        block["solver"] = normalize_solver_receipt(native["solver"])
    # Feature status is a separate observation, never a raw ProError. Keep
    # bounded pre-rollback ids/states already reported by the native health gate.
    features = result.get("failed_features")
    if isinstance(features, list) and features:
        sample = []
        for feature in features[:20]:
            if not isinstance(feature, dict):
                continue
            sample.append(
                {
                    "id": _integer(feature.get("id")),
                    "name": (_text(feature.get("name")) or "")[:128] or None,
                    "type": _integer(feature.get("type")),
                    "status": _integer(feature.get("status")),
                }
            )
        block["failed_features"] = {
            "total": len(features),
            "sample": sample,
            "truncated": len(features) > len(sample),
        }
    if not isinstance(raw_message, str) or not raw_message:
        raw_message = result.get("message")
    message, truncated = bounded_message(raw_message)
    if native.get("message_truncated") is True:
        truncated = True
    placement: dict[str, Any] = {}
    if block["operation"] in PLACEMENT_OPERATIONS:
        placement = _native_matrix(native) or placement_matrix(failing)
    block.update(
        {
            "pro_error": pro_error,
            "pro_error_source": source,
            "message": message,
            "message_truncated": truncated,
            **{field: placement.get(field) for field in _MATRIX_FIELDS},
        }
    )
    result["failed_operation"] = block
    return result
