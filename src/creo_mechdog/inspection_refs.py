"""Controlled references that keep full inspection payloads out of metadata.

BUG-076 splits small control metadata (results, tokens, requests, registries)
from full inspection payloads. Control files store an ``inspection_summary``
plus an ``inspection_ref`` — ``{"file", "sha256", "bytes"}`` bound to a file
inside this service's own directories — while the native full baseline stays
on disk next to its job. Loading verifies size and SHA256, so a tampered,
truncated or replaced reference is refused instead of trusted. Legacy records
that inlined a full ``inspection`` dict keep working through the same helpers.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import bridge
from creo_mechdog.model_queries import inspection_summary

REF_KEYS = ("file", "sha256", "bytes")


class InspectionRefInvalid(ValueError):
    """A controlled inspection reference is missing, stale or tampered."""


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


def content_digest(value: dict) -> str:
    """The digest :func:`make_ref` would compute for this payload.

    Shared so a record's content can be compared across storage forms:
    an inline payload and its written sidecar produce the same digest.
    """
    content = json.dumps(value, ensure_ascii=False, indent=2)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def make_ref(value: dict, directory: Path, stem: str, *, prefix: str = "inspection") -> dict:
    """Write a full inspection payload as a controlled sidecar file.

    The sidecar keeps the native full baseline bytes intact; only its identity
    (path, size, SHA256) enters control metadata. The name is content
    addressed, so a new payload never overwrites a reference an earlier
    record still points to. ``prefix`` names the payload family (BUG-077
    reuses this for registry detail sidecars such as aliases).
    """
    directory.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, indent=2)
    data = content.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    file = directory / f"{prefix}-{stem}-{digest[:16]}.json"
    if not file.is_file() or file.stat().st_size != len(data):
        temp = directory / f"{prefix}-{stem}-{digest[:16]}.{os.getpid()}.tmp"
        temp.write_bytes(data)
        os.replace(temp, file)
    return {"file": str(file), "sha256": digest, "bytes": len(data)}


def load_ref(ref: object) -> dict:
    """Load and verify a controlled inspection reference."""
    if not isinstance(ref, dict) or any(key not in ref for key in REF_KEYS):
        raise InspectionRefInvalid("Inspection reference is incomplete")
    path = _service_file(ref["file"])
    if not path.is_file():
        raise InspectionRefInvalid(
            f"Inspection reference file is missing: {path.name}; inspect again"
        )
    size = path.stat().st_size
    if isinstance(ref["bytes"], int) and size != ref["bytes"]:
        raise InspectionRefInvalid(
            f"Inspection reference file size changed (expected {ref['bytes']}, found {size}); "
            "the reference is stale; inspect again"
        )
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != ref["sha256"]:
        raise InspectionRefInvalid(
            "Inspection reference file hash changed; the reference is tampered or stale; "
            "inspect again"
        )
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
