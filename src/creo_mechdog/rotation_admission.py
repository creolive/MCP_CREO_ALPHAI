"""BUG-045/FEAT-012: one admissions rule for caller-supplied rotation matrices.

Row-vector local-to-parent poses are accepted only when the 3x3 block is
orthonormal and has determinant +1 within the **published** ``1e-6`` tolerance.
The numbers are computed here (and mirrored by ``native/assembly_pose.h``) so a
rejection can quote the caller's own matrix, its orthogonality residual and its
determinant instead of only naming a tolerance.

``NEAR_ORTHONORMAL_TOLERANCE`` is not an admission limit and not a known Creo
threshold. It only classifies an accepted matrix as ``strict`` or as
``near_orthonormal`` (a truncated decimal literal, for example). A
near-orthonormal pose is sent verbatim — never repaired, Gram-Schmidt'd or
transposed — and its class is echoed in the failure context so a kernel
placement rejection stays actionable. Tightening the admission limit itself
requires the live perturbation sweep (1e-12 … 1e-7) recorded in the plan.
"""

from __future__ import annotations

import math
from typing import Any

#: The published admission tolerance. Both layers use this exact value.
ADMISSION_TOLERANCE = 1e-6

#: Classification only: at or below this residual the matrix is ``strict``.
NEAR_ORTHONORMAL_TOLERANCE = 1e-9

PRECISION_CLASSES = ("strict", "near_orthonormal", "invalid")

PRECISION_ADVICE = (
    "The pose passed admission within 1e-6 but is not strictly orthonormal "
    "(max |R*R^T-I| = {residual:.3g}). It was sent verbatim, not repaired. If the "
    "kernel rejected the placement, rebuild the matrix from exact orthonormal values "
    "(for example rotation angles in degrees); near-orthonormality alone is not a "
    "confirmed cause."
)


def orthogonality_residual(rotation: list[list[float]]) -> float:
    residual = 0.0
    try:
        for left in range(3):
            for right in range(3):
                dot = sum(rotation[left][k] * rotation[right][k] for k in range(3))
                residual = max(residual, abs(float(dot) - (1.0 if left == right else 0.0)))
    except (OverflowError, TypeError, ValueError):
        return math.inf
    return residual


def determinant(rotation: list[list[float]]) -> float:
    try:
        a, b, c = rotation
        return (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        )
    except (OverflowError, TypeError, ValueError):
        return math.nan


def admission_status(rotation: list[list[float]]) -> dict[str, Any]:
    """Return the admission numbers and the caller-facing classification."""
    residual = orthogonality_residual(rotation)
    try:
        det = float(determinant(rotation))
    except (OverflowError, TypeError, ValueError):
        det = math.nan
    accepted = (
        math.isfinite(residual)
        and math.isfinite(det)
        and residual <= ADMISSION_TOLERANCE
        and abs(det - 1.0) <= ADMISSION_TOLERANCE
    )
    if not accepted:
        precision = "invalid"
    elif residual <= NEAR_ORTHONORMAL_TOLERANCE:
        precision = "strict"
    else:
        precision = "near_orthonormal"
    return {
        "accepted": accepted,
        "orthogonality_residual": residual,
        "determinant": det,
        "determinant_error": abs(det - 1.0) if math.isfinite(det) else None,
        "tolerance": ADMISSION_TOLERANCE,
        "precision": precision,
        "advice": PRECISION_ADVICE.format(residual=residual)
        if precision == "near_orthonormal"
        else None,
    }
