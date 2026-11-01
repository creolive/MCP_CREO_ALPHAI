"""Shared preview projection for job results (DEV-047 T07 / BUG-066).

The native executor captures every raster image through one shared step
(``native/preview.h``) and publishes the raw Toolkit return codes of each step.
This module projects that evidence onto the persisted job result without ever
upgrading an outcome: a capture is only ``written`` when the raster call
returned zero *and* the file on disk is non-empty. The native ``file_check``
block is the filesystem stage that follows the raster call; it is passed
through unchanged so a failed confirmation keeps the real error code instead of
borrowing the raster code (BUG-088).

Preview failure is deliberately independent of the model save. The projection
does not touch ``success``, ``saved_file_reloaded_and_verified``, ``sha256`` or
the revision; a job whose model was saved and verified stays succeeded even
when its preview could not be captured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

PREVIEW_STATUSES = ("written", "failed", "not_attempted", "skipped_no_geometry")
PREVIEW_CODE_KEYS = (
    "display",
    "window_get",
    "window_model_get",
    "current_set",
    "current_get",
    "activate",
    "view_matrix_set",
    "view_matrix_get",
    "refit",
    "refresh",
    "repaint",
    "raster",
)
FILE_CHECK_KEYS = (
    "stage",
    "absolute",
    "parent_exists",
    "exists",
    "is_file",
    "size",
    "error_code",
    "error_category",
    "error_message",
)
# FEAT-008/BUG-088 (H): datum-occlusion diagnostics ride their own block and
# never touch the preview status or the raw codes. The empty-model skip states
# of P11 stay a separate concern, so this is passed through by name only.
DATUM_DISPLAY_KEYS = (
    "model_type",
    "type_query_code",
    "applicable",
    "attempted",
    "hide_status",
    "restore_status",
    "options",
    "config_file_written",
)


def _file_state(path: Path | None) -> tuple[bool, int | None, str | None]:
    """Return (verified, bytes, error type) without turning a probe into an exception.

    The error is kept as its type name only. No numeric code is invented here:
    the real filesystem code comes from the native confirmation stage and must
    stay traceable to the call that produced it.
    """
    if path is None:
        return False, None, None
    try:
        size = path.stat().st_size
    except OSError as exc:
        return False, None, type(exc).__name__
    return size > 0, size, None


def _candidate_path(
    native: dict[str, Any] | None, legacy_file: Any, directory: Path | None
) -> Path | None:
    raw = None
    if isinstance(native, dict) and isinstance(native.get("path"), str):
        raw = native["path"]
    elif isinstance(legacy_file, str) and legacy_file:
        raw = legacy_file
    elif directory is not None:
        raw = str(Path(directory) / "output" / "preview.jpg")
    return Path(raw) if raw else None


def _codes(native: dict[str, Any] | None, legacy_code: int | None) -> dict[str, int | None]:
    codes: dict[str, int | None] = {key: None for key in PREVIEW_CODE_KEYS}
    if isinstance(native, dict) and isinstance(native.get("codes"), dict):
        for key in PREVIEW_CODE_KEYS:
            value = native["codes"].get(key)
            if isinstance(value, int):
                codes[key] = value
    if legacy_code is not None:
        # The legacy field is the raster return code; never replace a native code.
        if codes["raster"] is None:
            codes["raster"] = legacy_code
    return codes


def normalize_preview(
    result: dict[str, Any], *, directory: Path | str | None = None
) -> dict[str, Any] | None:
    """Return the normalized preview block, or ``None`` when nothing was reported.

    The function is total: unknown shapes degrade to ``None`` or to a ``failed``
    status with the evidence that is actually present.
    """
    if not isinstance(result, dict):
        return None
    native = result.get("preview")
    native = native if isinstance(native, dict) else None
    legacy_code = (
        result.get("preview_code") if isinstance(result.get("preview_code"), int) else None
    )
    if native is None and legacy_code is None:
        return None
    folder = Path(directory) if directory is not None else None
    path = _candidate_path(native, result.get("preview_file"), folder)
    reported = native.get("status") if isinstance(native, dict) else None
    skipped = reported == "skipped_no_geometry"
    # The legacy raster field is a placeholder on a skipped native capture.
    # No Toolkit screenshot call or filesystem confirmation occurred.
    codes = _codes(native, None if skipped else legacy_code)
    verified, size, stat_error = (False, None, None) if skipped else _file_state(path)
    file_bytes = native.get("bytes") if isinstance(native, dict) else None
    if not isinstance(file_bytes, int):
        file_bytes = size
    raw_check = native.get("file_check") if isinstance(native, dict) else None
    file_check = (
        {key: raw_check[key] for key in FILE_CHECK_KEYS if key in raw_check}
        if isinstance(raw_check, dict)
        else None
    )
    raw_datums = native.get("datum_display") if isinstance(native, dict) else None
    datum_display = (
        {key: raw_datums[key] for key in DATUM_DISPLAY_KEYS if key in raw_datums}
        if isinstance(raw_datums, dict)
        else None
    )

    failed_step = native.get("failed_step") if isinstance(native, dict) else None
    failed_code = native.get("failed_code") if isinstance(native, dict) else None
    if reported in PREVIEW_STATUSES:
        status = str(reported)
    elif legacy_code == 0:
        status = "written"
    elif legacy_code == -1 and result.get("success") is not True:
        # PRO_TK_GENERAL_ERROR is also the placeholder for "never attempted";
        # a job that failed earlier never reached the capture.
        status = "not_attempted"
    else:
        status = "failed"

    if status == "written" and not verified:
        # A capture is never upgraded from a claimed success. An empty or
        # missing file means the image does not exist for a reviewer.
        status = "failed"
        # A native failed_step is evidence and stays; only a claim without one
        # gets the projection's own verification step name.
        if not isinstance(failed_step, str):
            failed_step = "output_file_verification"
        # The raster code is not a filesystem code; leave failed_code unknown
        # rather than borrowing one (BUG-088). The native file_check block and
        # verification_error carry the real evidence.

    block: dict[str, Any] = {
        "status": status,
        "path": str(path) if path is not None else None,
        "bytes": file_bytes,
        "file_verified": verified,
        "source": "native" if native is not None else "legacy_result",
        "codes": codes,
        "failed_step": failed_step if isinstance(failed_step, str) else None,
        "failed_code": failed_code if isinstance(failed_code, int) else None,
        "file_check": file_check,
        "datum_display": datum_display,
        "verification_error": stat_error,
    }
    for key in (
        "window",
        "window_matches_model",
        "current_window_matches",
        "view_matrix_matches",
    ):
        if isinstance(native, dict) and native.get(key) is not None:
            block[key] = native[key]
    return block


def apply_preview_projection(
    result: dict[str, Any], *, directory: Path | str | None = None
) -> dict[str, Any]:
    """Attach the normalized preview block and the flat compatibility fields."""
    block = normalize_preview(result, directory=directory)
    if block is None:
        return result
    result["preview"] = block
    result["preview_status"] = block["status"]
    result["preview_code"] = block["codes"].get("raster")
    result["preview_file"] = block["path"] if block["status"] == "written" else None
    return result
