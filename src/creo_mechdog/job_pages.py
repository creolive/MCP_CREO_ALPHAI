"""Bounded full-detail pages for job results (FEAT-008 / BUG-088, Q13).

``detail=full`` keeps the whole-manifest view whenever it fits the shared
32 KiB response budget, so existing small-job consumers see the same shape as
before. Larger jobs page through fixed sections with the project's standard
query cursor (``model_queries.encode_cursor``/``decode_cursor``), so the
request input echo is never returned unbounded and a missing page can be
fetched later: terminal job manifests are immutable, so their cursors stay
valid while a running job's manifest change correctly invalidates them.

Sections in stream order:

- ``operations_input``: the requested input operations (the plan echo), one
  raw record per input.
- ``operations_result``: the terminal operation result records.
- ``result_entries``: every remaining manifest/result value as
  ``{"path", "value"}`` leaf records (lists indexed), so oversized receipts
  such as per-component readbacks stay retrievable page by page. A single
  leaf above the entry budget is returned as an oversize marker instead of
  being cut, and an empty container is kept as one value record.
"""

from __future__ import annotations

from typing import Any

from creo_mechdog.model_queries import (
    RESPONSE_BUDGET,
    decode_cursor,
    encode_cursor,
    fingerprint,
    serialized_size,
)

SECTIONS = ("operations_input", "operations_result", "result_entries")
SECTION_DESCRIPTIONS = {
    "operations_input": "requested input operations (the plan echo), one raw record per input",
    "operations_result": "terminal operation result records, one raw record per input",
    "result_entries": "remaining manifest/result values as {path, value} leaf records",
}
_CURSOR_KIND = "job"
PAGE_LIMIT_MAX = 200
ENTRY_BUDGET = RESPONSE_BUDGET - 2048

#: Outcome scalars carried on every page so a page alone still identifies the
#: job terminal state (failure reason and revision included).
_SUMMARY_KEYS = (
    "job_id",
    "kind",
    "model_id",
    "status",
    "stage",
    "revision",
    "readonly",
    "created_at",
    "started_at",
    "finished_at",
    "message",
    "reason",
    "reason_details",
    "failure_phase",
    "recovery_required",
)


def _summary(manifest: dict[str, Any]) -> dict[str, Any]:
    summary = {key: manifest[key] for key in _SUMMARY_KEYS if key in manifest}
    summary["operation_count"] = len(manifest.get("operations", []))
    result = manifest.get("result")
    operations = result.get("operations") if isinstance(result, dict) else None
    summary["operation_result_count"] = len(operations) if isinstance(operations, list) else 0
    return summary


def _leaf_records(value: Any, path: str) -> list[dict[str, Any]]:
    """Flatten one container into ``{path, value}`` leaf records."""
    if isinstance(value, dict):
        if not value:
            return [{"path": path, "value": {}}]
        records: list[dict[str, Any]] = []
        for key, item in value.items():
            records.extend(_leaf_records(item, f"{path}.{key}" if path else str(key)))
        return records
    if isinstance(value, list):
        if not value:
            return [{"path": path, "value": []}]
        records = []
        for index, item in enumerate(value):
            records.extend(_leaf_records(item, f"{path}[{index}]"))
        return records
    return [{"path": path, "value": value}]


def section_records(manifest: dict[str, Any], section: str) -> list[Any] | None:
    """Return the raw records of one section, or ``None`` when unavailable."""
    if section not in SECTIONS:
        return None
    if section == "operations_input":
        operations = manifest.get("operations")
        return operations if isinstance(operations, list) else []
    result = manifest.get("result")
    result = result if isinstance(result, dict) else {}
    if section == "operations_result":
        operations = result.get("operations")
        return operations if isinstance(operations, list) else []
    records: list[dict[str, Any]] = []
    for key, value in manifest.items():
        if key in ("operations", "result"):
            continue
        records.extend(_leaf_records(value, key))
    for key, value in result.items():
        if key == "operations":
            continue
        records.extend(_leaf_records(value, f"result.{key}"))
    return records


def section_counts(manifest: dict[str, Any]) -> dict[str, int]:
    return {
        name: len(records)
        for name in SECTIONS
        for records in [section_records(manifest, name) or []]
    }


def _oversize_record(path: Any, encoded: int) -> dict[str, Any]:
    return {
        "path": path,
        "oversize": True,
        "size_hint_bytes": encoded,
        "hint": (
            "this single record exceeds the page budget; its source stays in the "
            "job directory (job.json / native_result.json) instead of the page"
        ),
    }


def job_page(
    manifest: dict[str, Any],
    *,
    section: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Build one bounded ``detail=full`` view of a job manifest."""
    if not type(limit) is int or not 1 <= limit <= PAGE_LIMIT_MAX:
        raise ValueError(f"limit must be 1-{PAGE_LIMIT_MAX}")
    if section is not None and section not in SECTIONS:
        raise ValueError(f"Unknown section {section!r}; choose one of {list(SECTIONS)}")
    token = decode_cursor(cursor)
    identity = {
        "job_id": manifest.get("job_id"),
        "snapshot_hash": fingerprint(manifest),
        "section": section,
    }
    if token is not None and any(token.get(key) != value for key, value in identity.items()):
        raise ValueError("Snapshot or query changed; restart the job query without cursor")
    if section is None and token is None:
        # Small jobs keep the whole inline view (existing semantics). The gate
        # is the response budget only: paging exists to bound large payloads,
        # not to reshape jobs that already fit.
        whole = {
            **manifest,
            "detail": "full",
            "complete": True,
            "next_cursor": None,
            "sections_available": list(SECTIONS),
            "section_counts": section_counts(manifest),
        }
        if serialized_size(whole) <= RESPONSE_BUDGET:
            return whole
    names = [section] if section is not None else list(SECTIONS)
    records = [
        (name, record) for name in names for record in (section_records(manifest, name) or [])
    ]
    start = token["offset"] if token else 0
    if start > len(records):
        raise ValueError("Invalid query cursor offset")
    response = {
        **_summary(manifest),
        "detail": "full",
        "section": section,
        "sections_available": list(SECTIONS),
        "section_counts": section_counts(manifest),
        "data": {name: [] for name in names},
        "offset": start,
        "returned_count": 0,
        "total": len(records),
        "complete": False,
        "next_cursor": None,
        "response_budget_bytes": RESPONSE_BUDGET,
    }
    end = start
    while end < len(records) and end - start < limit:
        name, record = records[end]
        encoded = serialized_size(record)
        if encoded > ENTRY_BUDGET:
            response["data"][name].append(_oversize_record(_record_path(record, end), encoded))
        else:
            response["data"][name].append(record)
        if serialized_size(response) > RESPONSE_BUDGET:
            response["data"][name].pop()
            if end == start:
                raise ValueError(
                    f"Single {name} record exceeds the response budget; request a narrower section"
                )
            break
        end += 1
    response["next_cursor"] = (
        encode_cursor({**identity, "offset": end}) if end < len(records) else None
    )
    response["complete"] = end == len(records)
    response["returned_count"] = end - start
    if serialized_size(response) > RESPONSE_BUDGET:
        raise ValueError("Query metadata exceeds response budget")
    return response


def _record_path(record: Any, index: int) -> Any:
    if isinstance(record, dict) and "path" in record:
        return record["path"]
    return index
