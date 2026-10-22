"""Bounded saved-model queries; partial pages never pretend to be full snapshots."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable
from typing import Any

RESPONSE_BUDGET = 32 * 1024
COUNT_KEYS = ("features", "surfaces", "edges", "bodies", "components")
SECTIONS = (
    "features",
    "dimensions",
    "surfaces",
    "edges",
    "bodies",
    "datum_planes",
    "parameters",
    "aliases",
    "components",
    "feature_geometry",
    "sketch_dimensions",
    "sheets",
    "views",
    "notes",
    "tables",
    "models",
    "shown_dimensions",
    "metadata",
)


def serialized_size(value: Any) -> int:
    # Include indentation and ASCII escaping used by MCP text renderers.
    return len(json.dumps(value, ensure_ascii=True, indent=2).encode("utf-8"))


def summary_of_model(model: dict[str, Any]) -> dict[str, Any]:
    # Deferred import: inspection_refs reads this module for the summary shape.
    from creo_mechdog.inspection_refs import summary_of

    return summary_of(model)


def full_inspection_of_model(model: dict[str, Any]) -> dict[str, Any]:
    """Adopted models may carry a controlled reference instead of an inline
    payload (BUG-076); both resolve here, tampered references refuse."""
    from creo_mechdog.inspection_refs import full_inspection

    return full_inspection(model) or {}


def inspection_summary(inspection: Any) -> dict[str, Any]:
    state = inspection if isinstance(inspection, dict) else {}
    supplied = state.get("counts") or {}
    counts = {}
    for key in COUNT_KEYS:
        value = supplied.get(key)
        counts[key] = (
            len(state[key])
            if isinstance(state.get(key), list)
            else value
            if type(value) is int and value >= 0
            else None
        )
    return {
        **{
            key: state[key]
            for key in (
                "healthy",
                "has_solid",
                "units",
                "units_query_code",
                "model_type",
                "volume_mm3",
                "volume_query_code",
                "inspection_source",
                "inspection_available",
                "verified_feature_counts",
            )
            if key in state
        },
        "counts": counts,
        "inspection_available": bool(state) and state.get("inspection_available", True),
    }


def model_summary(model: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: model[key]
        for key in (
            "model_id",
            "model_name",
            "model_type",
            "status",
            "revision",
            "created_at",
            "updated_at",
            "pending_job",
            "recovery_pending",
            "reconciliation",
            "part_sha256",
            "last_job",
            "last_query_at",
            "part_file",
        )
        if key in model
    }
    result["inspection"] = summary_of_model(model)
    saved = bool(model.get("inspection") or model.get("inspection_ref")) and bool(
        model.get("part_file")
    )
    result["snapshot"] = {
        "source": "saved_verified" if saved else "unavailable",
        "revision": model.get("revision"),
        "at": model.get("updated_at"),
        "live_state_verified": False,
        "mutation_pending": bool(model.get("pending_job") or model.get("recovery_pending")),
    }
    result["detail_available"] = True
    source = model.get("adopted_from")
    result["adopted"] = bool(source and source.get("state") == "completed")
    result["source_kind"] = (source or {}).get("source_kind", "file" if source else "created")
    return result


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def encode_cursor(value: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode()


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if cursor is None:
        return None
    if len(cursor) > 4096:
        raise ValueError("Invalid query cursor")
    try:
        value = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid query cursor") from exc
    if not isinstance(value, dict) or type(value.get("offset")) is not int or value["offset"] < 0:
        raise ValueError("Invalid query cursor")
    return value


def section_records(model: dict[str, Any], section: str) -> list[Any] | None:
    state = full_inspection_of_model(model)
    if section == "metadata":
        excluded = set(SECTIONS) | set(inspection_summary(state)) | {"counts"}
        return [{"name": key, "value": val} for key, val in state.items() if key not in excluded]
    if section in ("aliases", "parameters"):
        if section == "aliases":
            # Split registry records keep aliases in a controlled sidecar
            # (BUG-077); resolve on demand, never inline into every page read.
            from creo_mechdog.model_registry import aliases_of

            values = aliases_of(model)
        else:
            values = full_inspection_of_model(model).get("parameters")
        return (
            [{"name": key, "value": val} for key, val in (values or {}).items()]
            if isinstance(values, dict)
            else None
        )
    if section in ("dimensions", "feature_geometry", "sketch_dimensions"):
        features = state.get("features")
        if not isinstance(features, list):
            return None
        field = {
            "dimensions": "dimensions",
            "feature_geometry": "geometry_items",
            "sketch_dimensions": "sketch_dimensions",
        }[section]
        return [{"feature_id": f["id"], **entry} for f in features for entry in f.get(field, [])]
    values = state.get(section)
    if not isinstance(values, list):
        return None
    if section == "features":
        # Large nested collections have their own independently paginated sections.
        return [
            {
                key: val
                for key, val in f.items()
                if key not in ("dimensions", "geometry_items", "sketch_dimensions")
            }
            for f in values
        ]
    return values


def inspect_page(
    model: dict[str, Any],
    detail: str = "compact",
    section: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    if detail not in ("compact", "full"):
        raise ValueError("detail must be compact or full")
    if not 1 <= limit <= 200:
        raise ValueError("limit must be 1–200")
    if section is not None and section not in SECTIONS:
        raise ValueError("Unknown section; use " + ", ".join(SECTIONS))
    if detail == "compact" and (section is not None or cursor is not None):
        raise ValueError("section/cursor require detail=full")
    response = model_summary(model)
    response.update(detail=detail, sections_available=list(SECTIONS), complete=detail == "compact")
    if detail == "compact":
        if serialized_size(response) > RESPONSE_BUDGET:
            raise ValueError("Model summary exceeds response budget")
        return response
    token = decode_cursor(cursor)
    identity = {
        "model_id": model["model_id"],
        "revision": model["revision"],
        "snapshot_hash": fingerprint(model),
        "section": section,
    }
    if token and any(token.get(key) != value for key, value in identity.items()):
        raise ValueError("Snapshot or query changed; restart inspection without cursor")
    # Small legacy full snapshots remain available without collection reshaping.
    if section is None and token is None:
        whole = {
            **model,
            **{
                "detail": "full",
                "complete": True,
                "next_cursor": None,
                "snapshot": response["snapshot"],
            },
        }
        if (
            serialized_size(whole) <= RESPONSE_BUDGET
            and max((len(section_records(model, name) or []) for name in SECTIONS), default=0)
            <= limit
        ):
            return whole
    names = [section] if section is not None else list(SECTIONS)
    records = [(name, record) for name in names for record in (section_records(model, name) or [])]
    start = token["offset"] if token else 0
    if start > len(records):
        raise ValueError("Invalid query cursor offset")
    response.update(
        data={name: [] for name in names},
        complete=False,
        next_cursor=None,
        offset=start,
        section=section,
        unavailable_sections=[name for name in names if section_records(model, name) is None],
        returned_count=0,
    )
    end = start
    while end < len(records) and end - start < limit:
        name, record = records[end]
        response["data"][name].append(record)
        response["next_cursor"] = (
            encode_cursor({**identity, "offset": end + 1}) if end + 1 < len(records) else None
        )
        response["complete"] = end + 1 == len(records)
        response["returned_count"] = end + 1 - start
        if serialized_size(response) > RESPONSE_BUDGET:
            response["data"][name].pop()
            if end == start:
                raise ValueError(
                    f"Single {name} record exceeds 32 KiB; request dimensions/feature_geometry/sketch_dimensions separately or inspect a narrower section"
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


def list_page(
    models: list[dict[str, Any]],
    loader: Callable[[str], dict[str, Any]],
    detail: str = "compact",
    limit: int = 10,
    cursor: str | None = None,
) -> dict[str, Any]:
    if detail not in ("compact", "full") or not 1 <= limit <= 50:
        raise ValueError("detail must be compact/full and limit must be 1–50")
    identity = {"detail": detail, "snapshot_hash": fingerprint(models)}
    token = decode_cursor(cursor)
    if token and any(token.get(key) != value for key, value in identity.items()):
        raise ValueError("Model list changed; restart listing without cursor")
    start = token["offset"] if token else 0
    if start > len(models):
        raise ValueError("Invalid query cursor offset")
    response = {"models": [], "detail": detail, "complete": False, "next_cursor": None}
    end = start
    while end < len(models) and end - start < limit:
        model = models[end]
        if detail == "full":
            current = loader(model["model_id"])
            if model_summary(current) != model:
                raise ValueError("Model list changed; restart listing without cursor")
            item = inspect_page(current, "full")
        else:
            item = model
        # full lists may include a first detail page; each model exposes its own cursor.
        response["models"].append(item)
        response["next_cursor"] = (
            encode_cursor({**identity, "offset": end + 1}) if end + 1 < len(models) else None
        )
        if serialized_size(response) > RESPONSE_BUDGET:
            response["models"].pop()
            if end == start:
                raise ValueError(
                    "Single model exceeds list budget; use detail=compact then creo_inspect_model"
                )
            break
        end += 1
    response["complete"] = end == len(models)
    response["next_cursor"] = (
        encode_cursor({**identity, "offset": end}) if end < len(models) else None
    )
    return response
