"""Public support and local release summaries for capability responses."""

from __future__ import annotations

from typing import Any

from creo_mechdog.update_check import SemanticVersion


def release_status(version: str) -> str:
    """Describe the installed version, independent of remote update discovery."""
    try:
        parsed = SemanticVersion(version)
    except ValueError:
        return "unknown"
    return "pre-release" if parsed.pre else "stable"


def support_status(capability_families: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Keep the short public boundaries tied to the registered family modes."""

    def family_entry(name: str, status: str, summary: str) -> dict[str, Any]:
        family = capability_families[name]
        entry: dict[str, Any] = {
            "status": status if family.get("enabled") is True else "not_available",
            "summary": summary,
        }
        for key in ("tool", "tools", "actions", "maximum_paths", "evidence_seconds"):
            if key in family:
                entry[key] = family[key]
        return entry

    return {
        "disk_open": family_entry(
            "disk_open",
            "supported",
            "read-only retrieval and display of existing on-disk .prt/.asm "
            "(explicit or highest numeric version); never saves, erases, renames "
            "or adopts, and creates no managed model",
        ),
        "session_enumeration": family_entry(
            "session_models",
            "supported",
            "read-only session inventory with frozen pagination; no loading or activation",
        ),
        "adoption": family_entry(
            "model_adoption",
            "supported_limited",
            "explicit managed-copy adoption of part/sheetmetal only: inspect, "
            "prepare a verified snapshot, then apply; millimeter units, no external "
            "dependencies, healthy features; assembly/drawing and repeat adoption "
            "of the same file are refused",
        ),
        "file_adoption": family_entry(
            "file_adoption",
            "supported_limited",
            "inspect then apply up to 20 explicitly ordered file paths in one request; "
            "healthy independent millimeter part/sheetmetal sources only, with "
            "independent commits and no display/window switching",
        ),
        "session_erase": family_entry(
            "session_erase",
            "supported_limited",
            "inspect selected eligible session models, then apply with evidence; "
            "no disk file deletion, global erase or implicit managed-model recovery",
        ),
        "generation_reclaim": family_entry(
            "generation_reclaim",
            "supported_limited",
            "inspect explicit loader/payload generation directories, then apply with "
            "600-second evidence and an idempotency key; current, registered, "
            "runtime-referenced, rollback-retained and unprovable generations are kept; "
            "no Toolkit connection, no DLL load and no automatic cleanup",
        ),
        "registry_maintenance": family_entry(
            "registry_maintenance",
            "supported_limited",
            "creo_registry_health is read-only; creo_migrate_registry provides "
            "explicit inspect/apply for owned registry records without Toolkit connection",
        ),
        "assembly_checks": {
            **family_entry(
                "session_assembly",
                "supported_limited",
                "read-only inspection of a resident session assembly: tree-order "
                "components, per-constraint snapshots and unit-aware 4x4 transforms "
                "(millimeter-normalized plus raw matrices; unknown units stay null); "
                "nested sub-assemblies, repeated instances, suppressed and missing "
                "components are reported per node and were not live-triggered on the "
                "reference machine. No write path: no loading, activation, save, "
                "adoption or managed revision; assembly adoption/reconcile stays "
                "refused",
            ),
            "tracking": "FEAT-045",
        },
        "assembly_replay": {
            **family_entry(
                "assembly_replay",
                "supported_limited",
                "read-only planning of a single-level assembly rebuild from a frozen "
                "snapshot: explicit occurrence and reference mappings produce ordered "
                "insert then constraint operations for creo_execute_plan; fixed/default "
                "placements keep their real semantics and source revision/digest "
                "bindings are re-checked at submission; native acceptance pending",
            ),
            "tracking": "FEAT-049",
        },
        "external_file_managed_edit": {
            "status": "not_supported_through_open",
            "summary": "creo_open_file never modifies external files; adopt the opened model "
            "with creo_adopt_current_model first if managed editing is required",
        },
    }
