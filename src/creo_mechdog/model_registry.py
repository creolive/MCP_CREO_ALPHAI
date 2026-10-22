"""Unified model-registry persistence: small control records plus detail sidecars.

BUG-077: the managed-model registry (``models/<id>/model.json``) previously
inlined full ``aliases`` and ``inspection`` payloads on every successful edit,
so one historical entry could grow past the shared 16 MiB metadata read budget
and block every adoption conflict scan and the reconcile recovery channel on
the same file. Registry writes now go through :func:`write_model`, which moves
detail payloads into content-addressed sidecars under ``details/`` and stores
only small references plus summaries; reads go through :func:`read_control`,
which refuses oversized or symlinked control records with a structured budget
error pointing at the registry maintenance tools. Legacy inline records keep
working through the ``*_of`` resolvers until they are migrated.
"""

from __future__ import annotations

import json
from pathlib import Path

import bridge
from creo_mechdog import inspection_refs

BUDGET_BYTES = 16 * 1024 * 1024

# Registry payloads that previously grew without bound on every edit. The
# control record keeps only a summary plus a controlled reference for each.
DETAIL_KEYS = ("aliases", "inspection", "last_live_inspection")

RECOVERY_GUIDANCE = (
    "Keep the oversized file unchanged for diagnosis; run creo_registry_health "
    "to list oversized or unmigrated entries, then creo_migrate_registry "
    "(inspect, then apply) to split legacy inline records into detail sidecars. "
    "Do not delete the file, edit it by hand, or raise the budget to hide the error"
)


class RegistryBudgetExceeded(ValueError):
    """A registry metadata read exceeded its budget; the error text is JSON."""

    def __init__(
        self,
        *,
        file: Path,
        failed_stage: str,
        reason_code: str = "REGISTRY_METADATA_BUDGET_EXCEEDED",
        metadata_kind: str = "model_registry",
        job_id: str | None = None,
        model_id: str | None = None,
    ):
        actual = file.stat().st_size if file.is_file() else None
        try:
            shown = str(file.resolve().relative_to(bridge.ROOT))
        except (OSError, ValueError):
            shown = str(file)
        self.payload = {
            "reason_code": reason_code,
            "metadata_kind": metadata_kind,
            "path": shown,
            "actual_bytes": actual,
            "budget_bytes": BUDGET_BYTES,
            "failed_stage": failed_stage,
            "job_id": job_id,
            "model_id": model_id,
            "recovery": RECOVERY_GUIDANCE,
        }
        super().__init__(json.dumps(self.payload, ensure_ascii=False))


def read_control(
    directory: Path,
    *,
    failed_stage: str = "model_registry_read",
    reason_code: str = "REGISTRY_METADATA_BUDGET_EXCEEDED",
    metadata_kind: str = "model_registry",
    job_id: str | None = None,
    model_id: str | None = None,
) -> dict:
    """Read a model's control record under the shared metadata budget.

    A legacy record that still inlines large detail payloads can exceed the
    budget; it is refused with a structured error pointing at migration, never
    skipped silently and never loaded unbounded on an automatic path.
    """
    file = directory / "model.json"
    if file.is_symlink() or file.is_junction():
        raise ValueError("Model registry entry cannot be a link")
    if not file.is_file():
        raise ValueError("Unknown model_id; use creo_new_part or creo_execute_plan")
    if file.stat().st_size > BUDGET_BYTES:
        raise RegistryBudgetExceeded(
            file=file,
            failed_stage=failed_stage,
            reason_code=reason_code,
            metadata_kind=metadata_kind,
            job_id=job_id,
            model_id=model_id or directory.name,
        )
    model = bridge.read_json(file)
    if not isinstance(model, dict):
        raise ValueError("Model registry entry does not contain an object")
    return model


def split_details(model: dict, directory: Path) -> dict:
    """Move inline detail payloads into sidecars; references replace them.

    ``model`` is mutated in place. Content-addressed sidecar names make the
    operation idempotent: rerunning after an interruption between sidecar
    publication and the atomic control-record replace reuses the same files.
    An already-split record is returned unchanged. The inspection family keeps
    its BUG-076 summary semantics (``inspection_summary`` stays in the record);
    aliases and last-live details reduce to their references.
    """
    details = directory / "details"
    inspection = model.get("inspection")
    if isinstance(inspection, dict) and inspection:
        summary = inspection_refs.summary_of(model)
        model["inspection_ref"] = inspection_refs.make_ref(
            inspection, details, "inspection", prefix="detail"
        )
        model.pop("inspection")
        model["inspection_summary"] = summary
    for key in ("aliases", "last_live_inspection"):
        value = model.get(key)
        if isinstance(value, dict) and value:
            model[f"{key}_ref"] = inspection_refs.make_ref(value, details, key, prefix="detail")
            model.pop(key)
    prepared = model.get("prepared_snapshot")
    if isinstance(prepared, dict):
        # A prepared adoption snapshot carries the same detail families; its
        # sidecars live next to the model's own details.
        split_details(prepared, directory)
    return model


def split_job_result(result: dict, directory: Path) -> dict:
    """Split a native result's detail payloads into job-directory sidecars.

    Job manifests (job.json) store the result; without this closeout every
    successful edit would inline the full aliases and inspection payloads back
    into a control file the recovery channel reads under the same budget
    (BUG-077). Content-addressed sidecars keep the bytes next to their job.
    """
    live = result.get("live")
    if isinstance(live, dict):
        inspection_refs.split(live, directory, "live")
    if isinstance(result.get("inspection"), dict) and result["inspection"]:
        inspection_refs.split(result, directory, "verified")
    aliases = result.get("aliases")
    if isinstance(aliases, dict) and aliases:
        result["aliases_ref"] = inspection_refs.make_ref(
            aliases, directory / "details", "aliases", prefix="detail"
        )
        result.pop("aliases")
    return result


def write_model(directory: Path, model: dict, *, durable: bool = True) -> dict:
    """Persist a model record: details first, then the control record atomically."""
    split_details(model, directory)
    bridge.write_json(directory / "model.json", model, durable=durable)
    return model


def _load_detail(ref: object, kind: str) -> dict:
    try:
        value = inspection_refs.load_ref(ref)
    except inspection_refs.InspectionRefInvalid as error:
        raise inspection_refs.InspectionRefInvalid(
            str(error).replace("Inspection reference", f"{kind} reference")
        ) from error
    if not isinstance(value, dict):
        raise inspection_refs.InspectionRefInvalid(f"{kind} reference does not contain an object")
    return value


def aliases_of(model: dict) -> dict:
    """Resolve a model's aliases: controlled reference first, legacy inline second.

    A missing, stale or tampered reference is refused instead of trusted.
    """
    ref = model.get("aliases_ref")
    if ref is not None:
        return _load_detail(ref, "Aliases")
    value = model.get("aliases")
    return value if isinstance(value, dict) else {}


def inspection_of(model: dict) -> dict | None:
    """Resolve a model's full inspection; None when the model never had one."""
    return inspection_refs.full_inspection(model)


def inline_detail_bytes(model: dict) -> dict[str, int]:
    """Serialized sizes of detail payloads still inlined in a record."""
    sizes = {}
    for key in DETAIL_KEYS:
        value = model.get(key)
        if isinstance(value, dict) and value:
            sizes[key] = len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    prepared = model.get("prepared_snapshot")
    if isinstance(prepared, dict):
        for key, size in inline_detail_bytes(prepared).items():
            sizes[f"prepared_snapshot.{key}"] = size
    return sizes


def detail_digests(model: dict) -> dict[str, str | None]:
    """Content digests of a record's detail payloads, independent of form.

    An inline payload is serialized exactly the way :func:`write_model` writes
    its sidecar, so the same content yields the same digest before and after
    a split/migration. This lets admission checks compare records semantically
    instead of by storage form (BUG-077).
    """
    digests: dict[str, str | None] = {}
    for key in DETAIL_KEYS:
        ref = model.get(f"{key}_ref")
        inline = model.get(key)
        if isinstance(ref, dict) and ref.get("sha256"):
            digests[key] = ref["sha256"]
        elif isinstance(inline, dict) and inline:
            digests[key] = inspection_refs.content_digest(inline)
        else:
            digests[key] = None
    prepared = model.get("prepared_snapshot")
    if isinstance(prepared, dict):
        for key, value in detail_digests(prepared).items():
            digests[f"prepared_snapshot.{key}"] = value
    return digests


def semantic_view(model: dict) -> dict:
    """A record viewed by control fields plus form-independent detail digests."""
    view = dict(model)
    for key in DETAIL_KEYS:
        view.pop(key, None)
        view.pop(f"{key}_ref", None)
        view.pop(f"{key}_summary", None)
    view.pop("prepared_snapshot", None)
    return {**view, "__detail_digests": detail_digests(model)}
