"""Controlled references that keep full inspection payloads out of metadata.

BUG-076 splits small control metadata (results, tokens, requests, registries)
from full inspection payloads. Control files store an ``inspection_summary``
plus an ``inspection_ref`` — ``{"file", "sha256", "bytes"}`` bound to a file
inside this service's own directories — while the native full baseline stays
on disk next to its job. Loading verifies size and SHA256, so a tampered,
truncated or replaced reference is refused instead of trusted. Legacy records
that inlined a full ``inspection`` dict keep working through the same helpers.

DEV-048 hardens the write side: an existing content-addressed file is reused
only when it is this service's own regular file with the same size *and* the
same full SHA256; a same-named file holding other bytes is kept untouched and
the payload is published under a distinct name. Write and publish failures
carry a fixed reason code, and every closeout can publish an
``inspection_warnings`` entry that records the stage and whether the Python
fallback finally produced a verified reference.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

import bridge
from creo_mechdog.model_queries import inspection_summary

REF_KEYS = ("file", "sha256", "bytes")

# Fixed diagnostic vocabulary shared with the native executor (DEV-048).
WARNING_STAGES = ("live", "verified")
WARNING_REASONS = (
    "native_sidecar_write_failed",
    "native_sidecar_publish_failed",
    "inspection_ref_invalid",
    "inspection_ref_removed_after_refusal",
)
WARNING_FALLBACKS = ("verified", "failed", "not_attempted")
MAX_WARNINGS = 4
MAX_MESSAGE_BYTES = 256

_SIDECAR_REASONS = ("native_sidecar_write_failed", "native_sidecar_publish_failed")
_FALLBACK_MESSAGES = {
    "native_sidecar_write_failed": "Native sidecar write failed; Python fallback was verified",
    "native_sidecar_publish_failed": (
        "Native sidecar publish failed; Python fallback was verified"
    ),
}


class InspectionRefInvalid(ValueError):
    """A controlled inspection reference is missing, stale or tampered."""


class SidecarWriteFailed(InspectionRefInvalid):
    """The payload could not be written and verified before publishing."""

    reason_code = "native_sidecar_write_failed"


class SidecarPublishFailed(InspectionRefInvalid):
    """The payload could not be published without replacing another file."""

    reason_code = "native_sidecar_publish_failed"


def _service_file(raw: object) -> Path:
    if not isinstance(raw, str) or not raw:
        raise InspectionRefInvalid("Inspection reference has no file path")
    path = Path(raw)
    try:
        resolved = path.resolve()
        root = bridge.ROOT.resolve()
    except OSError as error:
        raise InspectionRefInvalid(f"Inspection reference path is unusable: {error}") from error
    if resolved != root and root not in resolved.parents:
        raise InspectionRefInvalid(
            "Inspection reference points outside this service's directories; refusing to read it"
        )
    return resolved


def _regular_file(path: Path) -> bool:
    """This service's own plain file; links are never trusted as sidecars."""
    try:
        return path.is_file() and not path.is_symlink()
    except OSError:
        return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _matches(path: Path, size: int, digest: str) -> bool:
    """A reused sidecar must match the payload in size *and* full SHA256."""
    if not _regular_file(path):
        return False
    try:
        return path.stat().st_size == size and _sha256_file(path) == digest
    except OSError:
        return False


def content_digest(value: dict) -> str:
    """The digest :func:`make_ref` would compute for this payload.

    Shared so a record's content can be compared across storage forms:
    an inline payload and its written sidecar produce the same digest.
    """
    content = json.dumps(value, ensure_ascii=False, indent=2)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def bounded_message(message: object) -> str:
    """Bound a diagnostic message to 256 UTF-8 bytes without splitting a code point."""
    text = message if isinstance(message, str) else str(message or "")
    data = text.encode("utf-8")
    if len(data) <= MAX_MESSAGE_BYTES:
        return text
    clipped = data[:MAX_MESSAGE_BYTES].decode("utf-8", errors="ignore")
    suffix = "\u2026"
    while len((clipped + suffix).encode("utf-8")) > MAX_MESSAGE_BYTES:
        clipped = clipped[:-1]
    return clipped + suffix


def _discard(path: Path) -> None:
    """Best-effort removal of a temporary file this call created itself."""
    try:
        path.unlink()
    except OSError:
        pass


def _publish_exclusive(data: bytes, file: Path, digest: str) -> None:
    """Create the target exclusively; never replace a file another writer owns."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(file, flags, 0o600)
    except FileExistsError:
        if not _matches(file, len(data), digest):
            raise SidecarPublishFailed(
                "Another file already occupies the inspection sidecar name; kept it"
            ) from None
        return
    except OSError as error:
        raise SidecarPublishFailed(f"Could not publish the inspection sidecar: {error}") from error
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        # This call created the file exclusively, so removing it cannot delete
        # someone else's bytes.
        _discard(file)
        raise SidecarPublishFailed(f"Could not publish the inspection sidecar: {error}") from error
    if not _matches(file, len(data), digest):
        _discard(file)
        raise SidecarPublishFailed("The published inspection sidecar did not verify")


def _publish(data: bytes, file: Path, digest: str) -> None:
    """Write to a temporary file, verify it, then publish without replacing."""
    temp = file.with_name(f".{file.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with temp.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        _discard(temp)
        raise SidecarWriteFailed(f"Could not write the inspection sidecar: {error}") from error
    if not _matches(temp, len(data), digest):
        _discard(temp)
        raise SidecarWriteFailed("The inspection sidecar did not verify after writing")
    try:
        os.link(temp, file)
    except FileExistsError:
        _discard(temp)
        if not _matches(file, len(data), digest):
            raise SidecarPublishFailed(
                "Another file already occupies the inspection sidecar name; kept it"
            ) from None
        return
    except OSError:
        # Volumes without hard links: create the target exclusively from memory.
        _discard(temp)
        _publish_exclusive(data, file, digest)
        return
    _discard(temp)
    if not _matches(file, len(data), digest):
        raise SidecarPublishFailed("The published inspection sidecar did not verify")


def make_ref(value: dict, directory: Path, stem: str, *, prefix: str = "inspection") -> dict:
    """Write a full inspection payload as a controlled sidecar file.

    The sidecar keeps the native full baseline bytes intact; only its identity
    (path, size, SHA256) enters control metadata. The name is content
    addressed, so a new payload never overwrites a reference an earlier
    record still points to. An existing file is reused only when it is a plain
    file of this service whose size and full SHA256 match; a same-named file
    with other bytes is left in place and the payload is published under its
    full digest instead. ``prefix`` names the payload family (BUG-077 reuses
    this for registry detail sidecars such as aliases).
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise SidecarWriteFailed(
            f"Could not prepare the inspection sidecar directory: {error}"
        ) from error
    content = json.dumps(value, ensure_ascii=False, indent=2)
    data = content.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    names = (
        f"{prefix}-{stem}-{digest[:16]}.json",
        f"{prefix}-{stem}-{digest}.json",
    )
    for name in names:
        file = directory / name
        if file.exists() or file.is_symlink():
            if _matches(file, len(data), digest):
                return {"file": str(file), "sha256": digest, "bytes": len(data)}
            continue
        _publish(data, file, digest)
        return {"file": str(file), "sha256": digest, "bytes": len(data)}
    raise SidecarPublishFailed(
        "Inspection sidecar names are occupied by other content; the existing files were kept"
    )


def _verified_path(ref: object) -> Path:
    if not isinstance(ref, dict) or any(key not in ref for key in REF_KEYS):
        raise InspectionRefInvalid("Inspection reference is incomplete")
    path = _service_file(ref["file"])
    if not _regular_file(path):
        raise InspectionRefInvalid(
            f"Inspection reference file is missing: {path.name}; inspect again"
        )
    size = path.stat().st_size
    if isinstance(ref["bytes"], int) and size != ref["bytes"]:
        raise InspectionRefInvalid(
            f"Inspection reference file size changed (expected {ref['bytes']}, found {size}); "
            "the reference is stale; inspect again"
        )
    try:
        actual = _sha256_file(path)
    except OSError as error:
        raise InspectionRefInvalid(f"Inspection reference file is unreadable: {error}") from error
    if actual != ref["sha256"]:
        raise InspectionRefInvalid(
            "Inspection reference file hash changed; the reference is tampered or stale; "
            "inspect again"
        )
    return path


def verify_ref(ref: object) -> None:
    """Verify a reference without parsing the payload (size and full SHA256)."""
    _verified_path(ref)


def load_ref(ref: object) -> dict:
    """Load and verify a controlled inspection reference."""
    path = _verified_path(ref)
    try:
        value = bridge.read_json(path)
    except (OSError, ValueError) as error:
        raise InspectionRefInvalid(f"Inspection reference file is unreadable: {error}") from error
    if not isinstance(value, dict):
        raise InspectionRefInvalid("Inspection reference file does not contain an object")
    return value


def full_inspection(holder: dict | None) -> dict | None:
    """Resolve the full inspection of a holder dict.

    Prefers a controlled reference (new records); falls back to an inlined
    ``inspection`` dict (legacy records). Returns None when neither exists.
    """
    holder = holder or {}
    ref = holder.get("inspection_ref")
    if ref is not None:
        return load_ref(ref)
    inline = holder.get("inspection")
    return inline if isinstance(inline, dict) and inline else None


def summary_of(holder: dict | None) -> dict:
    """Small summary for a holder dict, with or without a full payload."""
    holder = holder or {}
    stored = holder.get("inspection_summary")
    if isinstance(stored, dict) and stored:
        return stored
    return inspection_summary(full_inspection(holder) or {})


def split(holder: dict, directory: Path, stem: str) -> dict:
    """Split a holder's full inspection into a summary plus a controlled ref.

    ``holder`` is mutated in place: an inlined ``inspection`` is moved into a
    sidecar under ``directory`` and replaced by ``inspection_ref`` plus
    ``inspection_summary``. A holder that already carries only a reference is
    given its summary and returned unchanged otherwise.
    """
    inline = holder.get("inspection")
    if isinstance(inline, dict) and inline:
        ref = make_ref(inline, directory, stem)
        holder["inspection_ref"] = ref
    ref = holder.get("inspection_ref")
    if ref is not None:
        holder.pop("inspection", None)
        holder.setdefault("inspection_summary", summary_of(holder))
    return holder


def request_field(holder: dict | None, key: str) -> dict:
    """The request-side form of a holder's inspection under ``key``.

    New records pass only a controlled reference (``<key>_ref``); a legacy
    record without a reference falls back to inlining so old evidence keeps
    working.
    """
    holder = holder or {}
    ref = holder.get("inspection_ref")
    if ref is not None:
        return {f"{key}_ref": ref}
    inline = holder.get("inspection")
    if isinstance(inline, dict) and inline:
        return {key: inline}
    raise InspectionRefInvalid("This record carries no inspection reference; inspect again")


def add_warning(
    holder: dict,
    *,
    stage: str,
    reason_code: str,
    fallback_status: str,
    message: str,
) -> None:
    """Record one bounded diagnostic on ``holder`` under ``inspection_warnings``.

    Entries are identified by ``(stage, reason_code)``: re-recording the same
    pair replaces its prior status instead of duplicating it. At most
    ``MAX_WARNINGS`` entries are published; the oldest is dropped so the newest
    storage fact survives.
    """
    if not isinstance(holder, dict):
        raise ValueError("A warning holder must be a mapping")
    if stage not in WARNING_STAGES:
        raise ValueError(f"Unknown inspection stage: {stage!r}")
    if reason_code not in WARNING_REASONS:
        raise ValueError(f"Unknown inspection warning reason code: {reason_code!r}")
    if fallback_status not in WARNING_FALLBACKS:
        raise ValueError(f"Unknown inspection fallback status: {fallback_status!r}")
    entries = holder.get("inspection_warnings")
    entries = (
        [dict(entry) for entry in entries if isinstance(entry, dict)]
        if isinstance(entries, list)
        else []
    )
    entry = {
        "stage": stage,
        "reason_code": reason_code,
        "fallback_status": fallback_status,
        "message": bounded_message(message),
    }
    for index, existing in enumerate(entries):
        if existing.get("stage") == stage and existing.get("reason_code") == reason_code:
            entries[index] = entry
            break
    else:
        entries.append(entry)
        while len(entries) > MAX_WARNINGS:
            entries.pop(0)
    holder["inspection_warnings"] = entries


def warnings_of(holder: dict | None) -> list[dict]:
    """The bounded, well-formed diagnostics published on ``holder``."""
    if not isinstance(holder, dict):
        return []
    entries = holder.get("inspection_warnings")
    if not isinstance(entries, list):
        return []
    result = []
    for entry in entries:
        if len(result) >= MAX_WARNINGS:
            break
        if not isinstance(entry, dict):
            continue
        stage = entry.get("stage")
        reason = entry.get("reason_code")
        fallback = entry.get("fallback_status")
        if stage not in WARNING_STAGES:
            continue
        if reason not in WARNING_REASONS or fallback not in WARNING_FALLBACKS:
            continue
        result.append(
            {
                "stage": stage,
                "reason_code": reason,
                "fallback_status": fallback,
                "message": bounded_message(entry.get("message")),
            }
        )
    return result


def _fallback_warning(
    report: dict, stage: str, reason_code: str | None, status: str, error: Exception | None
) -> None:
    """Update the stage's sidecar warning after the Python fallback was tried."""
    previous = next(
        (
            entry
            for entry in warnings_of(report)
            if entry["stage"] == stage and entry["reason_code"] in _SIDECAR_REASONS
        ),
        None,
    )
    if error is None:
        if previous is None:
            # A healthy inline split, including a legacy record, is not a fault.
            return
        add_warning(
            report,
            stage=stage,
            reason_code=previous["reason_code"],
            fallback_status="verified",
            message=_FALLBACK_MESSAGES[previous["reason_code"]],
        )
        return
    if previous is not None:
        add_warning(
            report,
            stage=stage,
            reason_code=previous["reason_code"],
            fallback_status="failed",
            message=f"{previous['message'].rstrip('.')}; Python fallback also failed: {error}",
        )
        return
    add_warning(
        report,
        stage=stage,
        reason_code=reason_code or "native_sidecar_write_failed",
        fallback_status="failed",
        message=f"Python fallback could not store the inspection sidecar: {error}",
    )


def _close_stage(report: dict, holder: dict, directory: Path, stage: str) -> None:
    """Close out one stage independently; a live failure never skips verified."""
    ref = holder.get("inspection_ref")
    if ref is not None:
        try:
            verify_ref(ref)
        except InspectionRefInvalid as error:
            # A reference that cannot be served is not published: the stored
            # bytes are gone, so the diagnostic is the only truthful record.
            holder.pop("inspection_ref", None)
            add_warning(
                report,
                stage=stage,
                reason_code="inspection_ref_invalid",
                fallback_status="not_attempted",
                message=f"Stored inspection reference could not be verified: {error}",
            )
        else:
            # A verified reference still gets its summary beside it, exactly as
            # ``split`` did before the T01 closeout: no new sidecar, no new
            # warning and no fallback change (DEV-048 T02 restores this).
            holder.pop("inspection", None)
            holder.setdefault("inspection_summary", summary_of(holder))
            return
    inline = holder.get("inspection")
    if not isinstance(inline, dict) or not inline:
        return
    try:
        holder["inspection_ref"] = make_ref(inline, directory, stage)
    except SidecarPublishFailed as error:
        _fallback_warning(report, stage, SidecarPublishFailed.reason_code, "failed", error)
        return
    except (SidecarWriteFailed, OSError, ValueError) as error:
        _fallback_warning(report, stage, SidecarWriteFailed.reason_code, "failed", error)
        return
    holder.pop("inspection", None)
    holder.setdefault("inspection_summary", summary_of(holder))
    _fallback_warning(report, stage, None, "verified", None)


def split_result(result: dict, directory: Path) -> dict:
    """Split a native result's full inspections into controlled references.

    Runs the native closeout's two stages independently: ``live`` and
    ``verified`` each end with either a verified reference or a bounded
    ``inspection_warnings`` entry, so a failure in the first stage cannot
    silently skip the second. The result object is returned for convenience.
    """
    if not isinstance(result, dict):
        return result
    live = result.get("live")
    if isinstance(live, dict):
        _close_stage(result, live, directory, "live")
    _close_stage(result, result, directory, "verified")
    return result
