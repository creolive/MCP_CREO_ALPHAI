"""Frozen in-process snapshot pagination for creo_capabilities (FEAT-023).

The default response is a compact summary page. detail=full splits the payload
into bounded per-section pages; each page carries pagination metadata, never
silently truncates, and oversized single entries are reported as oversize
markers instead of being cut. Snapshots are process-local, expire after
SNAPSHOT_SECONDS and are invalidated by any payload change, so cursors from a
previous process or an expired snapshot are rejected with a clear message.
"""

from __future__ import annotations

import threading
import time
import uuid

from creo_mechdog.model_queries import decode_cursor, encode_cursor, fingerprint

SNAPSHOT_SECONDS = 600
PAGE_BYTES = 32 * 1024
ENTRY_BUDGET = PAGE_BYTES - 2048
SECTIONS = (
    "overview",
    "tools",
    "families",
    "references",
    "seeds",
    "evidence",
    "runtime",
    "known_limitations",
    "plan_examples",
)
_CURSOR_KIND = "capabilities"

_SECTION_BY_KEY = {
    "families": "families",
    "references": "references",
    "seed_library": "seeds",
    "verified_evidence": "evidence",
    "runtime": "runtime",
    "tools": "tools",
    "known_limitations": "known_limitations",
    "plan_examples": "plan_examples",
}
_SECTION_DESCRIPTIONS = {
    "overview": "top-level contract fields (units, scheduling, workflow, support status, operations)",
    "tools": "registered tool names and descriptions",
    "families": "capability families with scope, native tests and limits",
    "references": "per-tool reference syntax and container shapes",
    "seeds": "bundled seed library listing",
    "evidence": "validation evidence summaries",
    "runtime": "runtime identity and source fingerprints",
    "known_limitations": "structured limitation entries with condition, release, evidence and configurability",
    "plan_examples": "small validated operation lists for common plans",
}

_lock = threading.Lock()
_snapshot: dict | None = None


def _get_snapshot(build_payload) -> dict:
    global _snapshot
    with _lock:
        if _snapshot is None or time.monotonic() - _snapshot["created"] > SNAPSHOT_SECONDS:
            payload = build_payload()
            _snapshot = {
                "created": time.monotonic(),
                "payload": payload,
                # The instance id makes cursors die with the snapshot that
                # issued them even when rebuilt content is byte-identical.
                "snapshot_id": uuid.uuid4().hex,
                "fingerprint": fingerprint(payload),
            }
        return _snapshot


def _snapshot_age(snapshot: dict) -> float:
    return max(0.0, SNAPSHOT_SECONDS - (time.monotonic() - snapshot["created"]))


def _section_entries(payload: dict, section: str) -> list[tuple[str, object]]:
    if section == "overview":
        return [
            (key, value)
            for key, value in payload.items()
            if key not in _SECTION_BY_KEY and not key.startswith("pagination_")
        ]
    key = next(k for k, v in _SECTION_BY_KEY.items() if v == section)
    value = payload.get(key)
    if isinstance(value, dict):
        return [(name, item) for name, item in value.items()]
    if isinstance(value, list):
        return [(str(index), item) for index, item in enumerate(value)]
    return [(key, value)]


def _section_summary(payload: dict) -> dict:
    families = payload.get("families", {})
    return {
        name: {
            "enabled": family.get("enabled") if isinstance(family, dict) else None,
            **({"tool": family["tool"]} if isinstance(family, dict) and "tool" in family else {}),
        }
        for name, family in families.items()
    }


def _metadata(snapshot: dict) -> dict:
    return {
        "sections": dict(_SECTION_DESCRIPTIONS),
        "section_counts": {
            section: len(_section_entries(snapshot["payload"], section)) for section in SECTIONS
        },
        "snapshot_fingerprint": snapshot["fingerprint"],
        "snapshot_expires_in_seconds": int(_snapshot_age(snapshot)),
        "page_bytes": PAGE_BYTES,
    }


def _compact(snapshot: dict) -> dict:
    overview = dict(_section_entries(snapshot["payload"], "overview"))
    limitations = snapshot["payload"].get("known_limitations")
    examples = snapshot["payload"].get("plan_examples")
    limitation_hint = (
        {
            "count": len(limitations),
            "section": "known_limitations",
            "hint": "detail=full with section=known_limitations pages the structured entries",
        }
        if isinstance(limitations, list)
        else None
    )
    example_hint = (
        {
            "count": len(examples),
            "section": "plan_examples",
            "hint": "detail=full with section=plan_examples pages validated examples",
        }
        if isinstance(examples, list)
        else None
    )
    overview.update(
        {
            "detail": "compact",
            "families": _section_summary(snapshot["payload"]),
            **({"known_limitations": limitation_hint} if limitation_hint else {}),
            **({"plan_examples": example_hint} if example_hint else {}),
            "pagination": {
                "default": "this single compact summary page",
                "detail_sections": "call detail=full with section=<name> and follow next_cursor",
                "sections": dict(_SECTION_DESCRIPTIONS),
                "snapshot_expires_in_seconds": int(_snapshot_age(snapshot)),
            },
        }
    )
    return overview


def capabilities_response(
    build_payload,
    *,
    detail: str = "compact",
    section: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict:
    """Build the public capabilities response from a frozen payload snapshot."""
    if detail not in ("compact", "full"):
        raise ValueError("detail must be compact or full")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("limit must be 1-200")
    snapshot = _get_snapshot(build_payload)
    if detail == "compact":
        if section is not None or cursor is not None:
            raise ValueError(
                "compact returns a single summary page; use detail=full with section/cursor"
            )
        return _compact(snapshot)

    if section not in SECTIONS:
        raise ValueError(f"Unknown section {section!r}; choose one of {list(SECTIONS)}")
    page = decode_cursor(cursor)
    if page is None:
        offset = 0
    else:
        if (
            page.get("kind") != _CURSOR_KIND
            or page.get("section") != section
            or page.get("snapshot_id") != snapshot["snapshot_id"]
            or page.get("fingerprint") != snapshot["fingerprint"]
        ):
            raise ValueError(
                "Capabilities cursor is invalid or the snapshot changed/expired; "
                "query again without cursor"
            )
        offset = page["offset"]
    entries = _section_entries(snapshot["payload"], section)
    if offset > len(entries):
        raise ValueError("Capabilities cursor offset is out of range; query again")
    selected: list[dict] = []
    size = 0
    index = offset
    while index < len(entries) and len(selected) < limit:
        key, value = entries[index]
        entry = {"key": key, "value": value}
        encoded = len(repr(entry).encode("utf-8", errors="replace"))
        if encoded > ENTRY_BUDGET:
            entry = {
                "key": key,
                "oversize": True,
                "size_hint_bytes": encoded,
                "hint": (
                    "this single entry exceeds the page budget; inspect it through its "
                    "own tool or evidence file instead of the capabilities page"
                ),
            }
            encoded = len(repr(entry).encode("utf-8", errors="replace"))
        if selected and size + encoded > ENTRY_BUDGET:
            break
        selected.append(entry)
        size += encoded
        index += 1
    response = {
        "detail": "full",
        "section": section,
        **_metadata(snapshot),
        "offset": offset,
        "returned": len(selected),
        "total": len(entries),
        "complete": index >= len(entries),
        "entries": selected,
    }
    if index < len(entries):
        response["next_cursor"] = encode_cursor(
            {
                "kind": _CURSOR_KIND,
                "section": section,
                "offset": index,
                "snapshot_id": snapshot["snapshot_id"],
                "fingerprint": snapshot["fingerprint"],
            }
        )
    return response


def reset_snapshot() -> None:
    """Drop the cached snapshot (tests and explicit invalidation)."""
    global _snapshot
    with _lock:
        _snapshot = None
