"""MCP_CREO_MechDog: Creo 10 native-feature server. stdout is reserved for MCP messages."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

import bridge
import creo_startup
import generic_bridge as general
import seeds
from capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS, families
from creo_mechdog import update_check
from creo_mechdog.adoption import adopt
from creo_mechdog.blend_callback import callback_setup_status, unknown_readiness
from creo_mechdog.capability_pages import capabilities_response
from creo_mechdog.open_file import open_file as submit_open_file
from creo_mechdog.paths import SOURCE_PATHS
from creo_mechdog.reconciliation import reconcile
from creo_mechdog.references import PatternAxis, reference_capabilities
from creo_mechdog.registry_ops import health as registry_health
from creo_mechdog.registry_ops import migrate as registry_migrate
from creo_mechdog.schema import (
    AirfoilProfile,
    AirfoilSketchOp,
    AirfoilStation,
    AirfoilValues,
    Entity,
    Operation,
    SketchConstraint,
    SketchDimension,
    SketchOp,
)
from creo_mechdog.session_erase import erase_session_models
from creo_mechdog.session_models import list_session_models
from version import VERSION

logging.basicConfig(level=logging.WARNING)
startup = creo_startup.CreoStartup()
updates = update_check.UpdateChecker()
_CODE_ROOT = Path(__file__).resolve().parent
if SOURCE_PATHS.resource_root != _CODE_ROOT:
    raise RuntimeError(
        "Python package belongs to another source checkout; run this installation's "
        "python -m pip install --no-deps -e <source directory> before starting server.py"
    )
_SOURCE_NAMES = (
    "server.py",
    "bridge.py",
    "creo_startup.py",
    "src/creo_mechdog/__init__.py",
    "src/creo_mechdog/paths.py",
    "src/creo_mechdog/references.py",
    "src/creo_mechdog/update_check.py",
    "src/creo_mechdog/blend_callback.py",
    "src/creo_mechdog/build_support.py",
    "src/creo_mechdog/seed_distribution.py",
    "src/creo_mechdog/seed_compatibility.py",
    "seeds.py",
    "src/creo_mechdog/recovery.py",
    "src/creo_mechdog/reconciliation.py",
    "src/creo_mechdog/legacy_recovery.py",
    "src/creo_mechdog/adoption.py",
    "src/creo_mechdog/inspection_refs.py",
    "src/creo_mechdog/lock_files.py",
    "src/creo_mechdog/session_models.py",
    "src/creo_mechdog/session_erase.py",
    "src/creo_mechdog/model_registry.py",
    "src/creo_mechdog/registry_ops.py",
    "src/creo_mechdog/open_file.py",
    "src/creo_mechdog/capability_pages.py",
    "src/creo_mechdog/model_queries.py",
    "src/creo_mechdog/startup_state.py",
    "src/creo_mechdog/windows_boot.py",
    "src/creo_mechdog/window_observations.py",
    "src/creo_mechdog/schema.py",
    "src/creo_mechdog/profile_checks.py",
    "src/creo_mechdog/airfoil.py",
    "version.py",
    "generic_bridge.py",
    "schema.py",
    "profile_checks.py",
    "airfoil.py",
    "native/worker.cpp",
    "native/geometry.cpp",
    "tools/generate_constants.py",
    "native/generic.cpp",
    "native/loft_seed.cpp",
    "native/advanced.cpp",
    "native/component_transform.h",
    "native/inspection_units.h",
    "native/drawing.cpp",
    "native/result_delivery.h",
    "native/recovery_deadline.h",
    "native/blend_sync.cpp",
    "native/blend_loader.cpp",
    "native/blend_create.cpp",
    "native/callback_identity.h",
    "native/callback_api.h",
    "native/callback_runtime.h",
)


def _source_fingerprints() -> dict[str, str]:
    return {
        name: hashlib.sha256((_CODE_ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in _SOURCE_NAMES
    }


_LOADED_FINGERPRINTS = _source_fingerprints()


@asynccontextmanager
async def server_lifespan(app):
    startup.start()
    updates.start()
    try:
        yield {}
    finally:
        await updates.stop()
        startup.stop()


mcp = MCPServer(
    "MCP_CREO_MechDog",
    version=VERSION,
    lifespan=server_lifespan,
    instructions="General native parametric modeling in Creo 10. Use mm and degrees. Create parts with creo_new_part "
    "or a complete creo_execute_plan, create independent sketches, then reference them by feature label "
    "for extrude/revolve/add/cut, and append subsequent native features. "
    "Mutation tools return a job_id: poll creo_get_job with detail=compact, then use its model_id and latest revision. "
    "Inspect surfaces/edges/dimensions before choosing raw references. Always provide expected_revision "
    "when modifying an existing MCP model. Models and native files persist across clients. "
    "creo_capabilities defaults to a compact summary page including support_status; "
    "use detail=full with section=references and follow next_cursor for each "
    "parameter's kind and container shape. "
    "Open existing on-disk .prt/.asm read-only with creo_open_file (no managed model); adopt before managed editing. "
    "Success requires status=succeeded and saved_file_reloaded_and_verified=true for mutations. "
    "Busy errors mean this request was not accepted; inspect blocking_job_id, blocking_model_id "
    "and retry_guidance. Poll accepted jobs instead of resubmitting them. "
    "Create sheetmetal/assembly models with the corresponding new-model tools or model_type in execute_plan. "
    "Use creo_capabilities for enabled and tested operations; reserved unavailable tools reject before native mutation. "
    "Creo startup detection runs in the background; poll creo_startup_status until ready before modeling. "
    "Use creo_startup_status(retry=true) to recheck a failed/manual startup; no session is automatically closed. "
    "On first use call creo_check_update and inspect update in capabilities/startup status. "
    "If status=update_available and stale=false, tell the user the current/latest versions, prerelease flag, "
    "release_url and download_url and the manual upgrade steps in message. "
    "Remind only once per latest_version in the current client session; do not interrupt modeling. "
    "Failed/unknown/checking/stale update information never proves the installation is up to date. "
    "Do not retry unknown_outcome without inspection.",
)
READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
CREATE = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)
NETWORK_READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
)


class Hole(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    x: float = Field(description="Hole center X in mm, relative to plate center")
    y: float = Field(description="Hole center Y in mm, relative to plate center")
    diameter: float = Field(gt=0, description="Through-hole diameter in mm")


async def invoke(fn, *args, **kwargs):
    try:
        if fn in (bridge.create_job, general.submit, general.new_loft_part, submit_open_file):
            startup.require_ready()
        return await asyncio.to_thread(fn, *args, **kwargs)
    except bridge.ToolkitBusy as exc:
        return CallToolResult(
            is_error=True,
            content=[TextContent(type="text", text=json.dumps(exc.payload, ensure_ascii=False))],
            structured_content=exc.payload,
        )
    except (ValueError, RuntimeError, OSError) as exc:
        # A structured payload (e.g. AdoptionMetadataBudgetExceeded) keeps the
        # same JSON text and structuredContent contract as busy errors.
        payload = getattr(exc, "payload", None)
        if isinstance(payload, dict) and str(exc) == json.dumps(payload, ensure_ascii=False):
            return CallToolResult(
                is_error=True,
                content=[TextContent(type="text", text=str(exc))],
                structured_content=payload,
            )
        raise ToolError(str(exc)) from None


@mcp.tool(annotations=READ)
async def creo_check_environment() -> dict[str, Any]:
    """Check Creo executable, Toolkit SDK, metric template and compiler. License presence does not prove usability."""
    return await invoke(bridge.check_environment)


@mcp.tool(annotations=READ)
async def creo_session_status() -> dict[str, Any]:
    """Check the configured/unique Creo session through Toolkit (9 second probe budget, no rebuild). Every return branch carries server_version. Busy returns its occupying job; probe_timeout returns recovery guidance. During startup return its snapshot promptly. connected=true requires verification; ambiguous/stale session selections never fall back to a random session. Includes a read-only creo_process_snapshot (pid/name/created_at/matches) so a failed probe can distinguish a dead IPC endpoint from an exited Creo process."""
    result = await invoke(startup.session_status)
    return {**result, "server_version": VERSION}


@mcp.tool(annotations=READ)
async def creo_callback_status() -> dict[str, Any]:
    """Read resident Blend readiness without building, loading a DLL, launching Creo or changing models. The native probe has a 9-second budget and verifies a fresh nonce, module/loader hashes, protocol, command and resource root. Returns ready/not_loaded/version_mismatch/unknown with identities, checked_at and next steps. not_loaded is provable (never loaded, or registered but not running) and its instruction leads with the one-time registration entry; unknown means the loaded state cannot be confirmed. GUI registration stays unknown; busy, unreachable and timeout never imply unregistered. Old protocol-2 registration requires a one-time migration; stable loader upgrades normally require a Creo restart and starting the same registration. Do not replay unknown_outcome."""
    state = startup.status()
    if state.get("coordinator_running"):
        return unknown_readiness(
            callback_setup_status(bridge.ROOT / "build"), "startup_in_progress", startup=state
        )
    result = await invoke(bridge.callback_status)
    result["service"] = {
        "version": VERSION,
        "resource_root": str(SOURCE_PATHS.resource_root),
        "source_fingerprints_at_startup": dict(_LOADED_FINGERPRINTS),
        "source_changed_since_startup": _source_fingerprints() != _LOADED_FINGERPRINTS,
    }
    try:
        from creo_mechdog.blend_callback import generation_inventory

        result["generation_inventory"] = generation_inventory(bridge.ROOT / "build")
    except (OSError, ValueError) as error:
        result["generation_inventory"] = {"available": False, "reason": str(error)}
    if result["service"]["source_changed_since_startup"]:
        result.update(
            readiness="unknown",
            reason="service_source_changed",
            instruction="Restart this MCP service to load the deployed code, then query again. Preserve unknown jobs/models.",
        )
    return result


@mcp.tool(annotations=CREATE)
async def creo_startup_status(retry: bool = False) -> dict[str, Any]:
    """Read a background snapshot with verified_at, verification_age_seconds and stale. retry=true rechecks the channel within 180s preparation plus configured startup budget; overlapping retries share coordination. Unreadable startup history can be archived/rebuilt only when it predates a verified Windows reboot, both recovery locks are held and no Creo session exists; startup_recovery identifies the backup. Same-boot/unverified history requires manual reconciliation. waiting_for_channel includes busy details. Never closes Creo, clears unknown job/model reservations or replays jobs. Poll until ready; inspect recovery guidance otherwise."""
    result = await invoke(startup.start, retry=True) if retry else await invoke(startup.status)
    return {**result, "update": updates.snapshot()}


@mcp.tool(annotations=NETWORK_READ)
async def creo_check_update(force: bool = False) -> dict[str, Any]:
    """Check public GitHub Releases, including prereleases, against the running version.

    Returns the same update object as capabilities.update and startup_status.update:
    status (not_checked/checking/update_available/up_to_date/failed/unknown),
    current_version/latest_version/is_prerelease/release_url/download_url,
    checked_at/last_success_at/from_cache/stale/message/error. Times are UTC ISO 8601.
    Uses a process-local 24-hour cache; force=true refreshes it, except during the
    15-minute failure/unknown cooldown. Concurrent checks share one request. A fresh
    check has a 5-second total network budget across all pages; other tools never wait
    for it. Failed checks may retain previous successful links with stale=true.
    Only accesses the public GitHub API; never downloads, installs or changes files.
    """
    return await updates.check(force)


@mcp.tool(annotations=CREATE)
async def creo_create_plate(
    length: float,
    width: float,
    thickness: float,
    corner_radius: float = 0,
    holes: list[Hole] | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    """Create a NEW native Creo part in mm. Origin is plate XY center at bottom Z=0.

    A dimensioned rectangular sketch drives extrusion to thickness. corner_radius rounds
    the four vertical corners. holes specifies independent native through-hole features.
    Return a job_id immediately; poll creo_get_job for the saved PRT and verification.
    Does not overwrite existing parts. Omit model_name to generate a unique name.
    Example: 80x60x20, R5; holes (±30,±20) diameter 8 and (0,0) diameter 10.
    """
    spec = await invoke(
        bridge.validate_spec,
        length,
        width,
        thickness,
        corner_radius,
        [h.model_dump() for h in holes or []],
        model_name,
    )
    return await invoke(bridge.create_job, spec)


@mcp.tool(annotations=READ)
async def creo_get_job(job_id: str, detail: Literal["compact", "full"] = "full") -> dict[str, Any]:
    """Read modeling progress/result. Use detail=compact for polling: status/revision/files/hash/volume/counts/operation outcomes; full includes complete geometry, aliases and validation. Full remains the compatibility default. Recovery failures may include reason, failure_phase and recovery_pending_released; success normally omits failure_phase, so use status and the public server version to interpret absent fields."""
    return await invoke(bridge.get_job, job_id, detail)


@mcp.tool(annotations=CREATE)
async def creo_reconcile_model(
    model_id: str,
    mode: Literal["inspect", "apply"] = "inspect",
    live: bool = False,
    action: Literal["restore_baseline", "accept_saved", "accept_live", "abandon_new"] | None = None,
    expected_revision: int | None = Field(
        default=None, description="Apply only: the revision returned by this inspect."
    ),
    expected_pending_job_id: str | None = Field(
        default=None,
        description=(
            "Apply only: the pending_job value returned by this inspect. Send JSON null "
            "(or omit the parameter) when inspect returned pending_job=null; "
            "never send an empty string."
        ),
    ),
    evidence_token: str | None = Field(
        default=None, description="Apply only: the evidence_token returned by this inspect."
    ),
    idempotency_key: str | None = Field(
        default=None,
        description="Apply only: unique 8-80 letters, digits, underscores or hyphens.",
    ),
) -> dict[str, Any]:
    """Inspect uncertain owned models without requiring Creo. live=true performs a bounded read-only session preflight. Apply an explicitly selected available action with the returned token, revision, pending_job (null when absent) and a unique 8–80 character idempotency_key. Poll its independent recovery job; never replay the original plan. Execution failures expose reason and failure_phase: before_native refusals release only their own recovery reservation under the channel lock; native_worker_started means dispatch may have begun and unknown_outcome protection remains. restore_baseline keeps revision; accept_saved/live increments once; abandon_new preserves files and archives the model. accept_live requires live preflight. Unsupported/unproven ownership is rejected; no Creo restart or user file deletion."""
    return await invoke(
        reconcile,
        model_id,
        mode,
        live,
        action,
        expected_revision,
        expected_pending_job_id,
        evidence_token,
        idempotency_key,
    )


@mcp.tool(annotations=CREATE)
async def creo_adopt_current_model(
    mode: Literal["inspect", "prepare", "apply"] = "inspect",
    model_id: str | None = Field(
        default=None,
        description="Apply: pending model_id. Inspect with model_id renews prepared-snapshot evidence without copying.",
    ),
    evidence_token: str | None = Field(
        default=None, description="Apply only: the evidence_token returned by inspect."
    ),
    model_name: str | None = Field(
        default=None,
        description=(
            "Prepare or file-source apply: managed copy name (1-31 chars of lowercase letters/digits/underscores, "
            "letter or digit first; uppercase input is normalized to lowercase); defaults to the "
            "inspect default_model_name and must not exist in the Creo session."
        ),
    ),
    idempotency_key: str | None = Field(
        default=None,
        description="Prepare/apply: unique 8-80 letters, digits, underscores or hyphens; use different keys for the two steps.",
    ),
) -> dict[str, Any]:
    """Explicitly adopt the current window model as a managed copy; the original is never saved, erased or renamed. File sources use read-only inspect then evidence-bound apply. A never-saved model requires prepare with an idempotency_key: poll its job and review result.adoption, then apply that model_id/evidence_token with a new key. prepare freezes a copy at native execution time without switching the current window; status stays adopt_pending/revision=0. Confirmation adopts that frozen snapshot at revision=1, displays the managed copy and excludes later edits to the original. inspect(model_id=...) renews ten-minute snapshot evidence without copying. Same-key replay never repeats native execution. Supported: healthy independent part/sheetmetal, millimeters, no external dependencies. Poll accepted jobs only; uncertain outcomes keep protection and resolve through reconcile abandon_new. Upgrade source code then restart the MCP connector and verify runtime identity/tool list before using new modes."""
    return await invoke(adopt, mode, model_id, evidence_token, model_name, idempotency_key)


@mcp.tool(annotations=READ)
async def creo_list_session_models(
    limit: int = Field(default=20, ge=1, le=50), cursor: str | None = None
) -> dict[str, Any]:
    """List models already in the connected Creo session without loading, saving, activating or adopting them. Returns names/types/current model, origin, has_saved_origin, modified and proven managed IDs; unknown fields are null with query codes. First page uses the single Toolkit channel (busy rejects immediately); cursor pages read the same frozen ten-minute snapshot. Integer session IDs are transient discovery hints, never adoption identities; they may legitimately be 0 or duplicated across model types, so locate models by name plus model_type. session_fingerprint identifies the connection/process session and does not change when session contents change. Partial type queries report complete=false. Switch to the desired model in Creo before adopting it."""
    return await invoke(list_session_models, limit, cursor)


@mcp.tool(annotations=CREATE)
async def creo_open_file(
    file_path: str,
    idempotency_key: str,
) -> dict[str, Any]:
    """Retrieve an existing on-disk .prt/.asm into the connected Creo session and display it, read-only. file_path is a Windows absolute path; append an explicit numeric version (e.g. .prt.3) to open exactly that file, otherwise the highest numeric version in the directory is selected and only the extension-only file is used when no numeric version exists. idempotency_key (8-80 letters/digits/underscores/hyphens) replays the same job for the same path and rejects a different path. Submission returns a job_id; poll creo_get_job. The file is never saved, erased, renamed or adopted: a successful open returns model_id=null/adopted=false and creates no managed revision. Same-name/same-type session models cause rejection, and assemblies additionally require a session without parts/assemblies; both checks and the retrieval share one Toolkit channel. An incomplete assembly fails with any residual session objects reported and missing components marked unknown; a display failure is reported separately from retrieval. Source-file identity is recorded at submit and after the job. Opened models are not MCP-managed: adopt with creo_adopt_current_model first if managed editing is needed."""
    return await invoke(submit_open_file, file_path, idempotency_key)


@mcp.tool(annotations=CREATE)
async def creo_erase_session_models(
    mode: Literal["inspect", "apply"] = "inspect",
    targets: list[dict[str, Any]] | None = None,
    evidence_token: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Explicitly erase selected models from the connected Creo session (FEAT-046). Never saves models and never deletes disk files. inspect(targets=[{name, model_type}]) verifies a manifest and returns per-target identity, blocking reasons, the assembly-before-components erase order, the expected remaining session objects and a 600-second evidence_token; targets qualify only when saved (has origin), unmodified, not MCP-managed, not referenced by session models outside the manifest and free of manifest dependency cycles; incomplete session enumeration refuses. apply(evidence_token, idempotency_key) executes exactly the token's manifest under one Toolkit channel lock and returns a job_id; poll creo_get_job. Each item re-verifies identity, modification state and origin before ProMdlErase, and absence is confirmed through two independent queries; a mid-manifest failure stops remaining items and reports erased, unconfirmed and remaining lists without resubmitting. The currently displayed model may be erased when it qualifies. Managed models stay with creo_reconcile_model; pass a session inventory from creo_list_session_models to choose targets."""
    return await invoke(erase_session_models, mode, targets, evidence_token, idempotency_key)


@mcp.tool(annotations=READ)
async def creo_registry_health() -> dict[str, Any]:
    """Report the managed-model registry's health without connecting Toolkit (FEAT-047). Lists every models/<id>/model.json entry with its byte size, share of the 16 MiB read budget, revision/status, per-detail form (inline/reference/absent for aliases, inspection, last_live_inspection) and state: ok, warning (>=80% of budget), over_budget, corrupt or legacy_inline. Single-entry errors never end the report. Summaries count each state, oversized/near-budget/corrupt entries are listed separately, and the migration section says how many entries still need creo_migrate_registry. Read-only: no file is modified and no Creo connection is made."""
    return await invoke(registry_health)


@mcp.tool(annotations=CREATE)
async def creo_migrate_registry(
    mode: Literal["inspect", "apply"] = "inspect",
    targets: list[str] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Split legacy inline registry records into small control records plus content-addressed detail sidecars (BUG-077). inspect (no side effects) lists entries that still inline aliases/inspection payloads — including over-budget ones — with their sizes, inline detail keys and the job-evidence chain that will be migrated with them. apply requires a fresh idempotency_key (8-80 letters/digits/underscores/hyphens; the same key replays the recorded result, a different target set with the same key is refused) and for each entry: preserves original bytes as model.json.pre-split-bak (job files as *.pre-split-bak), persists detail sidecars first, then publishes the control record atomically, and appends every action to models/registry-migration.jsonl. job.json result payloads and request.json model/component details on the entry's evidence chain are split the same way, so recovery reads stay inside the 16 MiB budget. Reruns are idempotent and interrupted migrations resume; model identity, revision and history conclusions never change; the read budget is never raised; nothing is deleted and raw native results stay untouched on disk. targets optionally narrows the migration to specific model_ids; omit it for the whole registry."""
    return await invoke(registry_migrate, mode, targets, idempotency_key)


@mcp.tool(annotations=READ)
async def creo_list_jobs(
    limit: int = 10, detail: Literal["compact", "full"] = "compact"
) -> dict[str, Any]:
    """List recent jobs, including jobs that continue after their MCP client disconnects."""
    return {"jobs": await invoke(bridge.list_jobs, limit, detail)}


def _support_status() -> dict[str, Any]:
    """Explicit capability boundaries so callers need not infer them (FEAT-008)."""
    return {
        "disk_open": {
            "status": "supported",
            "tool": "creo_open_file",
            "summary": (
                "read-only retrieval and display of existing on-disk .prt/.asm "
                "(explicit or highest numeric version); never saves, erases, renames "
                "or adopts, and creates no managed model"
            ),
        },
        "session_enumeration": {
            "status": "supported",
            "tool": "creo_list_session_models",
            "summary": "read-only session inventory with frozen pagination; no loading or activation",
        },
        "adoption": {
            "status": "supported_limited",
            "tool": "creo_adopt_current_model",
            "summary": (
                "explicit managed-copy adoption of part/sheetmetal only (millimeter "
                "units, no external dependencies, healthy features); assembly/drawing "
                "and repeat adoption of the same file are refused"
            ),
        },
        "assembly_checks": {
            "status": "planned",
            "tracking": "FEAT-045",
            "summary": (
                "read-only external assembly inspection (component tree, transforms) is "
                "not available yet; assemblies open for display only"
            ),
        },
        "external_file_managed_edit": {
            "status": "not_supported_through_open",
            "summary": (
                "creo_open_file never modifies external files; adopt the opened model "
                "with creo_adopt_current_model first if managed editing is required"
            ),
        },
    }


def _capabilities_payload(tool_entries: list[dict[str, Any]]) -> dict[str, Any]:
    local_evidence = bridge.ROOT / "build/capability_evidence.json"
    evidence = (
        local_evidence
        if local_evidence.is_file()
        else bridge.ROOT / "docs/validation_development.json"
    )
    verified = bridge.read_json(evidence) if evidence.is_file() else {}
    if not verified:
        verified = {"status": "No historical feature summary installed"}
    loft_evidence = bridge.ROOT / "docs/validation_loft_seed.json"
    smooth_evidence = bridge.ROOT / "docs/validation_loft_smooth.json"
    multisection_evidence = bridge.ROOT / "docs/validation_multisection.json"
    portable_evidence = bridge.ROOT / "docs/validation_portable_modeling.json"
    increment_evidence = bridge.ROOT / "docs/validation_increment_025.json"
    verified = {
        "scope": "v0.2.5 selected-item acceptance is separate from historical feature suites; full Creo coverage is not claimed",
        "portable_modeling": bridge.read_json(portable_evidence)
        if portable_evidence.is_file()
        else {"status": "No portable modeling summary yet"},
        "development_025": bridge.read_json(increment_evidence)
        if increment_evidence.is_file()
        else {"status": "No v0.2.5 acceptance summary installed"},
        "historical_features": verified,
        "loft_seed": bridge.read_json(loft_evidence)
        if loft_evidence.is_file()
        else {"status": "No loft integration summary yet"},
        "loft_smooth": bridge.read_json(smooth_evidence)
        if smooth_evidence.is_file()
        else {"status": "No smooth Blend integration summary yet"},
        "loft_multisection": bridge.read_json(multisection_evidence)
        if multisection_evidence.is_file()
        else {"status": "No multisection Blend integration summary yet"},
    }
    return {
        "name": "MCP_CREO_MechDog",
        "version": VERSION,
        "server_version": VERSION,
        "update": updates.snapshot(),
        "runtime": {
            "python_executable": sys.executable,
            "server_entry": str(Path(__file__).resolve()),
            "code_root": str(_CODE_ROOT),
            "python_package_root": str(SOURCE_PATHS.code_root),
            "resource_root": str(SOURCE_PATHS.resource_root),
            "data_root": str(SOURCE_PATHS.data_root),
            "job_root": str(bridge.JOBS),
            "model_root": str(general.MODELS),
            "source_fingerprints_at_startup": dict(_LOADED_FINGERPRINTS),
            "source_changed_since_startup": _source_fingerprints() != _LOADED_FINGERPRINTS,
        },
        "unit": "mm",
        "angle_unit": "degrees",
        "scheduling": {
            "native_channels": 1,
            "admission": "reject_busy_without_creating_a_job",
            "busy_error": "isError=true with matching JSON text and structuredContent",
            "owner_fields": ["blocking_job_id", "blocking_model_id", "blocking_operation"],
            "retry_after_seconds": 1,
            "retry_interval_is_completion_estimate": False,
            "terminal_contract": "Model finalized under channel lock; job terminal published after release. Another caller may then occupy the channel.",
            "runner_channel_wait_seconds": 120,
            "unknown_outcome": "Reservation retained; inspect job.recovery. Explicit startup retry only rechecks the channel and never commits/replays an unknown job.",
            "disconnect_watchdog_seconds": 20,
            "queue_guarantees": "No public FIFO, capacity or admission-wait guarantee",
            "non_native_queries": [
                "creo_get_job",
                "creo_list_jobs",
                "creo_inspect_model",
                "creo_list_models",
                "creo_reconcile_model (inspect without live)",
            ],
        },
        "tool_count": len(tool_entries),
        "enabled_tool_count": len(tool_entries),
        "disabled_tools_hidden": True,
        "startup": {
            "automatic_by_default": True,
            "status_tool": "creo_startup_status",
            "readiness": "Toolkit connection verified before modeling admission",
            "config": ["auto_start_creo", "creo_startup_timeout_seconds", "creo_startup_psf"],
            "existing_sessions": "Reuse selected/unique session; never close Creo automatically",
            "unreadable_history": "Archive/rebuild only verified previous-boot startup history, with no existing session and under startup/Toolkit locks; preserve unknown job/model reservations",
            "boot_verification_budget_seconds": 5,
        },
        "unavailable_tools": ["creo_" + name for name in UNAVAILABLE_OPERATIONS],
        "modeling": "Composable native Creo features; geometry is not restricted to a plate recipe",
        "entities": [
            "line",
            "centerline",
            "circle",
            "arc",
            "polyline",
            "rectangle",
            "spline",
            "ellipse",
        ],
        "operations": [op for op in REGISTERED_OPERATIONS if op not in UNAVAILABLE_OPERATIONS],
        "registered_operations": list(REGISTERED_OPERATIONS),
        "extrude_modes": ["add", "cut", "surface"],
        "extrude_depths": ["blind", "through_all_cut", "symmetric"],
        "revolve_modes": ["add", "cut", "surface"],
        "thin_features": True,
        "frames": {
            "XY": "u=+X,v=+Y,normal=+Z",
            "XZ": "u=+X,v=+Z,normal=-Y",
            "YZ": "u=+Y,v=+Z,normal=+X",
        },
        "tools": tool_entries,
        "references": reference_capabilities(),
        "arbitrary_planar_support": "plane={reference:{kind:surface,id:...},origin:[x,y,z],u_axis:[x,y,z]}",
        "workflow": "submit once -> poll get_job -> inspect model -> choose references -> append using expected_revision",
        "scope": "MCP-owned native part, sheetmetal, assembly and drawing models; plus read-only retrieval/display of existing on-disk models via creo_open_file. Tool availability does not prove every option or Creo operation is supported; consult validation evidence and coverage documentation.",
        "support_status": _support_status(),
        "complete_creo_coverage": False,
        "seed_library": seeds.list_seeds(),
        "direct_blend_callback": callback_setup_status(bridge.ROOT / "build"),
        "release_status": "pre-release candidate; requested complete coverage has not been achieved",
        "families": families(),
        "unavailable_operations": UNAVAILABLE_OPERATIONS,
        "evidence_directory": str(bridge.ROOT / "build"),
        "verified_evidence": verified,
    }


@mcp.tool(annotations=READ)
async def creo_capabilities(
    detail: Literal["compact", "full"] = "compact",
    section: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Describe capability boundaries, tool families, reference syntax and test evidence. Default detail=compact returns one bounded summary page (name/version/tool_count/scope/support_status/operation list/family index/pagination guide). detail=full pages one section at a time with limit and next_cursor from a frozen in-process snapshot (600 s; cursors from an older snapshot or another process are rejected). Pages stay within 32 KiB; a single oversized entry is reported as an oversize marker instead of being truncated. Migration: before 0.4.2 this tool returned the whole document; page detail=full sections (e.g. references, families, evidence) to rebuild it."""
    tool_entries = [
        {"name": tool.name, "description": tool.description} for tool in await mcp.list_tools()
    ]
    return await invoke(
        capabilities_response,
        lambda: _capabilities_payload(tool_entries),
        detail=detail,
        section=section,
        limit=limit,
        cursor=cursor,
    )


@mcp.tool(annotations=CREATE)
async def creo_new_part(model_name: str | None = None) -> dict[str, Any]:
    """Create a new metric native part with datum planes and coordinate system. Returns model_id and job_id. model_name: 1-31 chars of lowercase letters/digits/underscores, letter or digit first; uppercase input is normalized to lowercase."""
    return await invoke(general.submit, [], None, model_name)


@mcp.tool(annotations=CREATE)
async def creo_new_loft_part(
    sections: Annotated[list[SketchOp | AirfoilSketchOp], Field(min_length=2, max_length=20)],
    seed_file: str | None = None,
    seed_feature_id: int | None = None,
    label: str = "loft",
    model_name: str | None = None,
    assertions: dict[str, Any] | None = None,
    interpolation: Literal["straight", "smooth"] = "straight",
) -> dict[str, Any]:
    """Create a NEW part with a native ordinary Blend by rebinding a saved seed.

    Omit seed_file and seed_feature_id to automatically select a hash-verified
    installed seed matching section count and interpolation. Alternatively supply
    both explicit values for a local .prt/.prt.N containing one solid Blend with exactly the same
    number of independent XY sketch sections, created and selected low Z first,
    plus its native feature ID. interpolation must match the saved seed's
    straight/smooth setting: it validates the mode, never converts the seed.
    Use a dedicated solid seed in mm with one body. The file is
    snapshotted and never edited. sections must contain 2 to 20 sketch ops
    on XY with strictly increasing Z offsets; their geometry and dimensions drive the
    result. Five-section smooth rectangles and spline airfoils have been verified.
    Two-section rectangles, circles and triangles are also supported. This preserves
    a native parametric Blend; it is seed reuse, not direct element-tree creation.
    The native mode is checked after creation, edits and saved-file reload.
    It does not increase the seed's section count. No existing-target insertion, cut/surface modes or
    editable tangency/curvature controls; endpoint settings are inherited.
    Poll the returned job_id and use the resulting model_id for later features.
    """
    return await invoke(
        general.new_loft_part,
        seed_file,
        seed_feature_id,
        [s.model_dump(exclude_none=True) for s in sections],
        label,
        model_name,
        assertions,
        interpolation,
    )


@mcp.tool(annotations=READ)
async def creo_list_seeds() -> dict[str, Any]:
    """Discover bundled/registered native Blend seeds and verify their SHA256. available means matching file bytes, not current Creo compatibility. seed_build_version is null when provenance is unknown; native_compatibility contains bounded historical loads tied to seed SHA256 and native release/session, without connecting Creo. No manual paths/feature IDs are needed for auto-selected lofts."""
    return await invoke(seeds.list_seeds)


@mcp.tool(annotations=READ)
async def creo_validate_seed(seed_name: str) -> dict[str, Any]:
    """Verify a seed's file hash/provenance without connecting Creo. Unknown seed_build_version stays null; native_compatibility observations are historical, never proof of current-session compatibility. Native load/type/count/mode are additionally checked on actual loft creation and reported separately from overall modeling success."""
    return await invoke(seeds.validate_seed, seed_name)


@mcp.tool(annotations=CREATE)
async def creo_install_seed_library(
    directory: str | None = None, archive_file: str | None = None
) -> dict[str, Any]:
    """Register a local verified library, install its original ZIP, or verify the bundled library. Preserves existing files; never downloads or executes code."""
    return await invoke(seeds.install_seed_library, directory, archive_file)


@mcp.tool(annotations=CREATE)
async def creo_execute_plan(
    operations: list[Operation],
    model_id: str | None = None,
    model_name: str | None = None,
    expected_revision: int | None = None,
    assertions: dict[str, Any] | None = None,
    model_type: Literal["part", "sheetmetal", "assembly", "drawing"] = "part",
) -> dict[str, Any]:
    """Execute an ordered general feature plan. Omit model_id to create a new part.

    Sketch/extrude/revolve and later features reference earlier feature labels.
    Existing models require expected_revision. Stops at first error; existing models
    roll back to their saved checkpoint. assertions supports require_solid and volume_mm3.
    round/chamfer use `size` (mm); as a standalone-tool alias they also accept
    radius (round) or distance (chamfer), but providing the alias together with
    size is rejected instead of silently preferring one.
    """
    return await invoke(
        general.submit,
        [op.model_dump(exclude_none=True) for op in operations],
        model_id,
        model_name,
        expected_revision,
        assertions,
        model_type=model_type,
    )


@mcp.tool(annotations=CREATE)
async def creo_create_airfoil_section(
    model_id: str,
    expected_revision: int,
    label: str,
    profile: AirfoilProfile,
    plane: Literal["XY", "XZ", "YZ"] | dict[str, Any] = "XY",
    offset: float = 0,
) -> dict[str, Any]:
    """Create a native symmetric NACA 00xx spline sketch. chord/origin are mm, twist is degrees about pivot_fraction of chord; finite trailing edge. Parameters can later be updated in place."""
    return await invoke(
        general.submit,
        [
            dict(
                op="airfoil_sketch",
                label=label,
                plane=plane,
                offset=offset,
                profile=profile.model_dump(),
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_new_airfoil_blade(
    stations: Annotated[list[AirfoilStation], Field(min_length=2, max_length=20)],
    model_name: str | None = None,
    label: str = "blade_blend",
    interpolation: Literal["straight", "smooth"] = "smooth",
) -> dict[str, Any]:
    """Create a new native Blend from varying chord/thickness/twist NACA 00xx sections. Offset is span along +Z, sections lie on XY. Automatically selects a verified matching seed; 2 straight/smooth and 5 smooth are packaged."""
    sections = []
    for index, station in enumerate(stations):
        profile = station.model_dump()
        offset = profile.pop("offset")
        sections.append(
            dict(
                op="airfoil_sketch",
                label=f"blade_section_{index + 1}",
                plane="XY",
                offset=offset,
                profile=profile,
            )
        )
    return await invoke(
        general.new_loft_part,
        None,
        None,
        sections,
        label,
        model_name,
        {"require_solid": True},
        interpolation,
    )


@mcp.tool(annotations=CREATE)
async def creo_set_airfoil_parameters(
    model_id: str, expected_revision: int, sketch: str, values: AirfoilValues
) -> dict[str, Any]:
    """Update an existing airfoil's chord, thickness_ratio, twist_deg, origin or pivot_fraction. Redefines the original native sketch and regenerates its dependents; does not recreate the Blend."""
    return await invoke(
        general.submit,
        [dict(op="update_airfoil", sketch=sketch, values=values.model_dump(exclude_none=True))],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_update_sketch_geometry(
    model_id: str,
    expected_revision: int,
    sketch: str,
    entities: list[Entity],
    dimensioning: Literal["auto", "autodim", "coordinates"] = "auto",
) -> dict[str, Any]:
    """Replace native sketch geometry in place, preserving sketch feature ID. Expanded entity names/types must match. Clears old named dimensions/constraints. Arc and ellipse editing are experimental and need local validation."""
    return await invoke(
        general.submit,
        [
            dict(
                op="update_sketch_geometry",
                sketch=sketch,
                entities=[e.model_dump() for e in entities],
                dimensioning=dimensioning,
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_group_features(
    model_id: str,
    expected_revision: int,
    label: str,
    features: list[str | int],
    include_between: bool = False,
    include_support_planes: bool = True,
) -> dict[str, Any]:
    """Create a native local feature group. Members must be contiguous; include_between explicitly includes intervening features. Can include the selected sketches' automatically created support planes."""
    return await invoke(
        general.submit,
        [
            dict(
                op="feature_group",
                label=label,
                features=features,
                include_between=include_between,
                include_support_planes=include_support_planes,
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_reorder_features(
    model_id: str,
    expected_revision: int,
    features: list[str | int],
    before: str | int | None = None,
    after: str | int | None = None,
) -> dict[str, Any]:
    """Reorder owned native features before or after an anchor; dependency conflicts fail and restore the saved checkpoint."""
    return await invoke(
        general.submit,
        [
            dict(
                op="reorder_features",
                features=features,
                **{k: v for k, v in {"before": before, "after": after}.items() if v is not None},
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_axis_pattern(
    model_id: str,
    expected_revision: int,
    label: str,
    leader: str | int,
    axis: PatternAxis,
    count: int = 2,
    increment_deg: float = 180,
) -> dict[str, Any]:
    """Create a native angular pattern of a feature or MCP feature group.

    axis is a bare {kind:'axis',id:N} geometry selection or
    {kind:'datum_axis_feature',label:'axis_label'}. For compatibility, a
    {kind:'datum_feature',label:'axis_label'} in this parameter means an axis
    and is normalized to datum_axis_feature. A datum_plane or surface cannot
    substitute for an axis. Axis must precede the leader; use an independent
    datum axis and creo_reorder_features if necessary.
    """
    return await invoke(
        general.submit,
        [
            dict(
                op="axis_pattern",
                label=label,
                leader=leader,
                axis=axis,
                count=count,
                increment_deg=increment_deg,
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_transform_geometry(
    model_id: str,
    expected_revision: int,
    label: str,
    references: list[dict[str, Any]],
    translation: list[float] | None = None,
    rotation: list[float] | None = None,
    coordinate_system: dict[str, Any] | None = None,
    keep_original: bool = False,
) -> dict[str, Any]:
    """Create a native rigid transform of whole solid bodies or quilts/datums/curves. Rotation X,Y,Z precedes translation, about fixed supplied csys axes. Body moves use FlexMove and may require Flexible Modeling license. Does not rotate the camera."""
    return await invoke(
        general.submit,
        [
            dict(
                op="geometry_transform",
                label=label,
                references=references,
                translation=[0, 0, 0] if translation is None else translation,
                rotation=[0, 0, 0] if rotation is None else rotation,
                coordinate_system={"kind": "default_csys"}
                if coordinate_system is None
                else coordinate_system,
                keep_original=keep_original,
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_set_geometry_transform(
    model_id: str,
    expected_revision: int,
    feature: str,
    translation: list[float],
    rotation: list[float],
) -> dict[str, Any]:
    """Change a native transform's translation and rotation in place; preserves its feature ID and regenerates downstream geometry."""
    return await invoke(
        general.submit,
        [
            dict(
                op="set_geometry_transform",
                feature=feature,
                translation=translation,
                rotation=rotation,
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_create_sketch(
    model_id: str,
    expected_revision: int,
    label: str,
    entities: list[Entity],
    plane: Annotated[
        Literal["XY", "XZ", "YZ"] | dict[str, Any],
        Field(
            description="XY/XZ/YZ, or {reference:{kind:'surface',id:N},origin:[x,y,z],u_axis:[x,y,z]}; frame fields optional. A dictionary plane requires the reference container."
        ),
    ] = "XY",
    offset: float = 0,
    dimensions: list[SketchDimension] | None = None,
    constraints: list[SketchConstraint] | None = None,
    dimensioning: Literal["auto", "autodim", "coordinates"] = "auto",
) -> dict[str, Any]:
    """Create an independent native dimensioned sketch of arbitrary supported entities.

    Coordinates are in the chosen plane's (u,v) frame. Arc angles are degrees CCW.
    Rectangle/polyline expand to named lines e.g. box_0, box_1. Explicit dimensions
    have names and entity references; automatic dimensioning fills remaining freedoms.
    For revolve include one centerline, or supply an external axis to creo_revolve.
    auto uses complete coordinate dimensions for large/complex supported principal-plane profiles;
    coordinates forces that mode; autodim retains native automatic dimensions. Coordinate mode
    supports lines/polylines/rectangles/circles/arcs and cannot combine explicit dimensions/constraints.
    """
    op = {
        "op": "sketch",
        "label": label,
        "plane": plane,
        "offset": offset,
        "entities": [e.model_dump() for e in entities],
        "dimensions": [d.model_dump() for d in dimensions or []],
        "constraints": [c.model_dump() for c in constraints or []],
        "dimensioning": dimensioning,
    }
    return await invoke(general.submit, [op], model_id, None, expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_extrude(
    model_id: str,
    expected_revision: int,
    label: str,
    sketch: str | int,
    depth: float = 1,
    mode: Literal["add", "cut", "surface"] = "add",
    direction: Literal["positive", "negative", "symmetric"] = "positive",
    depth_type: Literal["blind", "through_all"] = "blind",
    new_body: bool = False,
    thin: float | None = None,
) -> dict[str, Any]:
    """Create native extrusion from a sketch label/ID. Supports protrusion, pocket, through cut, symmetric, surface and thin modes.
    A cut that removes no material (disjoint sketch, wrong direction or already-removed region) fails and rolls back;
    a successful cut reports material_removed_mm3 in its operation details."""
    op = {
        "op": "extrude",
        "label": label,
        "sketch": sketch,
        "depth": depth,
        "mode": mode,
        "direction": direction,
        "depth_type": depth_type,
        "new_body": new_body,
    }
    if thin is not None:
        op["thin"] = thin
    return await invoke(general.submit, [op], model_id, None, expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_revolve(
    model_id: str,
    expected_revision: int,
    label: str,
    sketch: str | int,
    angle: float = 360,
    mode: Literal["add", "cut", "surface"] = "add",
    direction: Literal["positive", "negative", "symmetric"] = "positive",
    axis: dict[str, Any] | None = None,
    new_body: bool = False,
    thin: float | None = None,
) -> dict[str, Any]:
    """Create native revolve/revolved cut from an arbitrary sketch, about its centerline or an external axis.
    A cut that removes no material fails and rolls back; a successful cut reports material_removed_mm3."""
    op = {
        "op": "revolve",
        "label": label,
        "sketch": sketch,
        "angle": angle,
        "mode": mode,
        "direction": direction,
        "new_body": new_body,
    }
    if axis is not None:
        op["axis"] = axis
    if thin is not None:
        op["thin"] = thin
    return await invoke(general.submit, [op], model_id, None, expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_hole(
    model_id: str,
    expected_revision: int,
    label: str,
    diameter: float,
    placement: dict[str, Any],
    reference1: dict[str, Any],
    reference2: dict[str, Any],
    offset1: float = 0,
    offset2: float = 0,
    depth: float | None = None,
    flip: bool = False,
) -> dict[str, Any]:
    """Create a native straight hole on a planar face using two independent planar
    references or coplanar straight edges and signed offsets. For edge references,
    the placement-face center selects the reference side. Omit depth for through-all;
    depth makes a blind hole. flip reverses the native cutting side. A hole that removes
    no material fails and rolls back. Successful operation details include native axes
    and material_removed_mm3.
    """
    op = {
        "op": "hole",
        "label": label,
        "diameter": diameter,
        "placement": placement,
        "reference1": reference1,
        "reference2": reference2,
        "offset1": offset1,
        "offset2": offset2,
        "flip": flip,
    }
    if depth is not None:
        op["depth"] = depth
    return await invoke(general.submit, [op], model_id, None, expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_round(
    model_id: str,
    expected_revision: int,
    label: str,
    radius: float,
    references: Annotated[
        list[dict[str, Any]],
        Field(
            description="Set list: [{edge:{kind:'edge',id:N}}] or [{surfaces:[{kind:'surface',id:A},{kind:'surface',id:B}]}]. Bare edge objects are not sets."
        ),
    ],
) -> dict[str, Any]:
    """Create a native constant-radius fillet on edges or face pairs. Each set is {edge:reference} or {surfaces:[reference,reference]}.

    radius is in mm and maps to the plan-operation field `size` (op="round"):
    the submitted job echoes it as operations[].size, and the finished job's
    result.operations[].size repeats the value the native feature applied.
    """
    return await invoke(
        general.submit,
        [{"op": "round", "label": label, "size": radius, "references": references}],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_chamfer(
    model_id: str,
    expected_revision: int,
    label: str,
    distance: float,
    references: Annotated[
        list[dict[str, Any]],
        Field(
            description="Set list: [{edge:{kind:'edge',id:N}}] or [{surfaces:[{kind:'surface',id:A},{kind:'surface',id:B}]}]. Bare edge objects are not sets."
        ),
    ],
) -> dict[str, Any]:
    """Create equal-distance native chamfer sets on explicit edges or face pairs.

    distance is in mm and maps to the plan-operation field `size` (op="chamfer"):
    the submitted job echoes it as operations[].size, and the finished job's
    result.operations[].size repeats the value the native feature applied.
    """
    return await invoke(
        general.submit,
        [{"op": "chamfer", "label": label, "size": distance, "references": references}],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_datum_plane(
    model_id: str,
    expected_revision: int,
    label: str,
    reference: dict[str, Any],
    offset: float = 0,
    angle: float | None = None,
    axis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create parametric offset datum plane, or angled plane through an axis."""
    op = {"op": "datum_plane", "label": label, "reference": reference, "offset": offset}
    if angle is not None:
        op["angle"] = angle
    if axis is not None:
        op["axis"] = axis
    return await invoke(general.submit, [op], model_id, None, expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_datum_axis(
    model_id: str, expected_revision: int, label: str, references: list[dict[str, Any]]
) -> dict[str, Any]:
    """Create a native datum axis through two planes, a cylindrical face, a straight edge or existing axis."""
    return await invoke(
        general.submit,
        [{"op": "datum_axis", "label": label, "references": references}],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_dimension_pattern(
    model_id: str,
    expected_revision: int,
    label: str,
    feature: str | int,
    dimension_id: int,
    count: int,
    increment: float,
) -> dict[str, Any]:
    """Create a native dimension pattern of a feature. Select a leader dimension ID from inspection, total count and per-member increment."""
    return await invoke(
        general.submit,
        [
            {
                "op": "dimension_pattern",
                "label": label,
                "feature": feature,
                "dimension_id": dimension_id,
                "count": count,
                "increment": increment,
            }
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_shell(
    model_id: str,
    expected_revision: int,
    label: str,
    thickness: float,
    remove_surfaces: list[dict[str, Any]] | None = None,
    outward: bool = False,
) -> dict[str, Any]:
    """Create native constant-thickness shell, optionally removing selected faces."""
    return await invoke(
        general.submit,
        [
            {
                "op": "shell",
                "label": label,
                "thickness": thickness,
                "remove_surfaces": remove_surfaces or [],
                "outward": outward,
            }
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_set_dimensions(
    model_id: str, expected_revision: int, values: list[dict[str, Any]]
) -> dict[str, Any]:
    """Modify native model dimensions by IDs returned in inspection. values=[{id:int,value:float}]. Regenerate, save and verify."""
    return await invoke(
        general.submit,
        [{"op": "set_dimensions", "values": values}],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_mirror(
    model_id: str,
    expected_revision: int,
    label: str,
    plane: dict[str, Any],
    references: list[dict[str, Any]] | None = None,
    keep_original: bool = True,
) -> dict[str, Any]:
    """Create native geometry/whole-part mirror about a planar reference. Omit references for whole part.

    Toolkit geometry references are curves, axes, quilts, points, csys or a part.
    Feature-subtree mirroring is not supported by this API; do not supply feature selections.
    """
    return await invoke(
        general.submit,
        [
            {
                "op": "mirror",
                "label": label,
                "plane": plane,
                "references": references or [],
                "keep_original": keep_original,
            }
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_sweep(
    model_id: str,
    expected_revision: int,
    label: str,
    trajectory: str | int | list[dict[str, Any]],
    profile: list[Entity],
    dimensions: list[SketchDimension] | None = None,
    constraints: list[SketchConstraint] | None = None,
    mode: Literal["add", "cut", "surface"] = "add",
    thin: float | None = None,
    new_body: bool = False,
    capped: bool = False,
) -> dict[str, Any]:
    """Create a native constant-section sweep along sketch curves or selected curve/edge references.

    Profile coordinates are local (u,v) in Creo's generated section frame at the path start.
    Named profile dimensions can be edited using creo_set_sketch_dimensions with this label.
    """
    op = {
        "op": "sweep",
        "label": label,
        "trajectory": trajectory,
        "profile": [e.model_dump() for e in profile],
        "dimensions": [d.model_dump() for d in dimensions or []],
        "constraints": [c.model_dump() for c in constraints or []],
        "mode": mode,
        "new_body": new_body,
        "capped": capped,
    }
    if thin is not None:
        op["thin"] = thin
    return await invoke(general.submit, [op], model_id, None, expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_loft(
    model_id: str,
    expected_revision: int,
    label: str,
    sections: list[str | int],
    mode: Literal["add", "cut", "surface"] = "add",
    interpolation: Literal["straight", "smooth"] = "straight",
    new_body: bool = False,
) -> dict[str, Any]:
    """Append a native solid Blend using independent MCP-owned XY sketches, ordered by increasing Z.

    Straight/smooth, default-body add only. Cut, surface and new_body are rejected.
    Query creo_callback_status before modeling. Register its registry_file once per
    loader/SDK generation and start it manually under every loader policy. Payload
    upgrades normally require restarting Creo and starting the same registration.
    Missing, mismatched or unverified callbacks reject before model mutation with
    BLEND_CALLBACK_SETUP_REQUIRED. MCP never loads DLLs or changes security policy.
    sections accepts sketch labels or integer feature IDs; digit-only strings are
    normalized to feature IDs for public-client compatibility. References must be distinct.
    """
    return await invoke(
        general.submit,
        [
            {
                "op": "loft",
                "label": label,
                "sections": sections,
                "mode": mode,
                "interpolation": interpolation,
                "new_body": new_body,
            }
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_draft(
    model_id: str,
    expected_revision: int,
    label: str,
    surfaces: list[dict[str, Any]],
    neutral_plane: dict[str, Any],
    angle: float,
    pull_direction: dict[str, Any] | None = None,
    flip: bool = False,
    include_tangent: bool = False,
) -> dict[str, Any]:
    """Create a native constant-angle, unsplit draft using selected surfaces and a neutral plane.

    Pull direction defaults to the neutral plane normal; can use a datum plane or axis reference.
    """
    op = {
        "op": "draft",
        "label": label,
        "surfaces": surfaces,
        "neutral_plane": neutral_plane,
        "angle": angle,
        "flip": flip,
        "include_tangent": include_tangent,
    }
    if pull_direction is not None:
        op["pull_direction"] = pull_direction
    return await invoke(general.submit, [op], model_id, None, expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_new_sheetmetal(model_name: str | None = None) -> dict[str, Any]:
    """Prepare a metric part for sheetmetal. The first wall creates its native sheetmetal body by conversion."""
    return await invoke(general.submit, [], None, model_name, model_type="sheetmetal")


@mcp.tool(annotations=CREATE)
async def creo_sheetmetal_wall(
    model_id: str,
    expected_revision: int,
    label: str,
    sketch: str | int,
    depth: float,
    thickness: float,
    direction: Literal["positive", "negative"] = "positive",
) -> dict[str, Any]:
    """Create the first flat sheetmetal wall from an open straight-line sketch, depth and thickness.

    The native tree contains the driving sketch, thin extrusion and sheetmetal conversion.
    Use flange tools for subsequent bent walls. Curved or closed first-wall sketches are not validated.
    """
    return await invoke(
        general.submit,
        [
            {
                "op": "sheetmetal_wall",
                "label": label,
                "sketch": sketch,
                "depth": depth,
                "thickness": thickness,
                "direction": direction,
            }
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_sheetmetal_flange(
    model_id: str,
    expected_revision: int,
    label: str,
    edge: Annotated[
        dict[str, Any],
        Field(
            description="Bare edge selection {kind:'edge',id:N} from model inspection. Do not add a reference/edge wrapper inside this parameter."
        ),
    ],
    height: float,
    angle: float = 90,
    radius: float = 1,
    flip: bool = False,
    y_factor: float = 0.5,
) -> dict[str, Any]:
    """Attach a native bent flange to a sheetmetal edge. The section exposes named height for dimension edits."""
    return await invoke(
        general.submit,
        [
            {
                "op": "sheetmetal_flange",
                "label": label,
                "edge": edge,
                "height": height,
                "angle": angle,
                "radius": radius,
                "flip": flip,
                "y_factor": y_factor,
            }
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_sheetmetal_unbend(
    model_id: str,
    expected_revision: int,
    label: str,
    fixed_surface: dict[str, Any],
    references: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Unbend a native sheetmetal part about a fixed surface. Omit references to unbend all bends."""
    return await invoke(
        general.submit,
        [
            {
                "op": "sheetmetal_unbend",
                "label": label,
                "fixed_surface": fixed_surface,
                "references": references or [],
            }
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_sheetmetal_flat_pattern(
    model_id: str, expected_revision: int, label: str, fixed_surface: dict[str, Any]
) -> dict[str, Any]:
    """Create a native flat-pattern feature about a fixed sheetmetal surface."""
    return await invoke(
        general.submit,
        [
            {
                "op": "sheetmetal_flat_pattern",
                "label": label,
                "fixed_surface": fixed_surface,
                "references": [],
            }
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_sheetmetal_bend_back(
    model_id: str,
    expected_revision: int,
    label: str,
    fixed_surface: dict[str, Any],
    references: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Refold previously unbent sheetmetal about a fixed surface. Omit references to bend back all bends."""
    return await invoke(
        general.submit,
        [
            {
                "op": "sheetmetal_bend_back",
                "label": label,
                "fixed_surface": fixed_surface,
                "references": references or [],
            }
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_new_assembly(model_name: str | None = None) -> dict[str, Any]:
    """Create a native metric assembly with default datum planes from the locally installed template."""
    return await invoke(general.submit, [], None, model_name, model_type="assembly")


@mcp.tool(annotations=CREATE)
async def creo_assemble_component(
    model_id: str,
    expected_revision: int,
    label: str,
    source_model_id: str,
    translation: list[float] | None = None,
    rotation: list[float] | None = None,
    placement: Literal["fixed", "default", "constraints"] = "fixed",
    constraints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Insert a revision snapshot of a verified MCP part/sheetmetal model as a native assembly component.

    Translation is XYZ mm; rotation is XYZ Euler degrees, applied X then Y then Z.
    Sources must be ready and saved; later source edits do not update the component snapshot.
    Native placement can be fixed, default or mate/align/insert/csys constraints. Nested subassemblies are not supported yet.
    """
    return await invoke(
        general.submit,
        [
            {
                "op": "assemble_component",
                "label": label,
                "source_model_id": source_model_id,
                "translation": translation or [0, 0, 0],
                "rotation": rotation or [0, 0, 0],
                "placement": placement,
                "constraints": constraints or [],
            }
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_component_placement(
    model_id: str,
    expected_revision: int,
    component: str | int,
    translation: list[float],
    rotation: list[float] | None = None,
) -> dict[str, Any]:
    """Replace a component's existing placement constraints with fixed placement at the specified rigid transform."""
    return await invoke(
        general.submit,
        [
            {
                "op": "component_placement",
                "component": component,
                "translation": translation,
                "rotation": rotation or [0, 0, 0],
            }
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_component_constraints(
    model_id: str, expected_revision: int, component: str | int, constraints: list[dict[str, Any]]
) -> dict[str, Any]:
    """Replace native component placement with mate/align/offset/insert/csys constraints to assembly references."""
    return await invoke(
        general.submit,
        [{"op": "component_constraints", "component": component, "constraints": constraints}],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False
    )
)
async def creo_remove_component(
    model_id: str, expected_revision: int, component: str | int
) -> dict[str, Any]:
    """Remove a component feature from this MCP assembly, preserving its source model and native file."""
    return await invoke(
        general.submit,
        [{"op": "remove_component", "component": component}],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=READ)
async def creo_list_components(model_id: str) -> dict[str, Any]:
    """Read the last verified assembly component list, native transforms and placement status."""
    from creo_mechdog import model_registry

    model = await invoke(general.model_info, model_id)
    if model.get("model_type") != "assembly":
        raise ToolError("Assembly model required")
    return {
        "model_id": model_id,
        "revision": model["revision"],
        "components": (model_registry.inspection_of(model) or {}).get("components", []),
        "aliases": model_registry.aliases_of(model),
    }


@mcp.tool(annotations=CREATE)
async def creo_set_sketch_dimensions(
    model_id: str, expected_revision: int, sketch: str | int, values: dict[str, float]
) -> dict[str, Any]:
    """Modify named explicit sketch dimensions, or numeric sketch dimension IDs, and regenerate dependent features."""
    return await invoke(
        general.submit,
        [{"op": "set_sketch_dimensions", "sketch": sketch, "values": values}],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_set_parameters(
    model_id: str, expected_revision: int, values: dict[str, float | str | bool | int]
) -> dict[str, Any]:
    """Create/update native part parameters. Supports numbers, booleans and strings."""
    return await invoke(
        general.submit,
        [{"op": "set_parameters", "values": values}],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_set_relations(
    model_id: str, expected_revision: int, lines: list[str]
) -> dict[str, Any]:
    """Set native part relations using simple arithmetic assignments, e.g. d12 = SIZE / 2. Replaces the relation set."""
    return await invoke(
        general.submit, [{"op": "set_relations", "lines": lines}], model_id, None, expected_revision
    )


@mcp.tool(annotations=CREATE)
async def creo_create_feature_tree(
    model_id: str, expected_revision: int, label: str, tree: dict[str, Any]
) -> dict[str, Any]:
    """Advanced native feature creation from Toolkit element tree JSON. Nodes: id, integer/double/string/reference/references, children.

    Element IDs and integer enum values can be symbolic SDK constants. Use creo_lookup_constants.
    Reference existing native sketches/model items. Feature-specific trees must follow installed
    SDK documentation. This low-level route does not automatically supply missing sections/collections.
    """
    return await invoke(
        general.submit,
        [{"op": "feature_tree", "label": label, "tree": tree}],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=READ)
async def creo_lookup_constants(prefix: str, limit: int = 100) -> dict[str, Any]:
    """Look up installed SDK element IDs and feature enum constants for advanced element-tree operations."""
    if not 1 <= limit <= 500:
        raise ToolError("limit must be 1–500")
    path = bridge.ROOT / "build/constants.json"
    if not path.exists():
        raise ToolError("Call creo_session_status to build the native worker first")
    constants = bridge.read_json(path)
    items = {k: v for k, v in constants.items() if k.startswith(prefix)}
    return {"constants": dict(list(items.items())[:limit]), "total_matches": len(items)}


@mcp.tool(annotations=READ)
async def creo_inspect_model(
    model_id: str,
    detail: Literal["compact", "full"] = "compact",
    section: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Read a saved verified snapshot, compact by default (identity/revision/status/volume/counts).

    Use detail=full for geometry; large snapshots return data grouped by section,
    complete=false and next_cursor. Repeat with the same detail/section and cursor.
    Sections: features, dimensions, surfaces, edges, bodies, datum_planes,
    parameters, aliases, components, feature_geometry, sketch_dimensions.
    Drawings also support sheets/views/notes/tables/models/shown_dimensions;
    metadata preserves additional inspection fields.
    Feature sections omit nested collections, available separately. Pages are
    bound to the snapshot and limited to 32 KiB, default 50/max 200 records.
    Model changes invalidate cursors. Use refresh_model for live Creo inspection.
    """
    return await invoke(general.inspect_model, model_id, detail, section, limit, cursor)


@mcp.tool(annotations=READ)
async def creo_refresh_model(model_id: str) -> dict[str, Any]:
    """Query live native model through Toolkit. Returns a job_id; poll get_job for the actual snapshot."""
    return await invoke(general.submit, [], model_id, None, None, None, True)


@mcp.tool(annotations=READ)
async def creo_list_models(
    limit: int = 10,
    detail: Literal["compact", "full"] = "compact",
    cursor: str | None = None,
) -> dict[str, Any]:
    """List owned models, compact by default. Repeat next_cursor with the same detail.

    limit remains 1–50; 32 KiB budget can return fewer models. complete describes
    the list page, while each full model may have its own inspection next_cursor.
    Use inspect_model(detail=full, section=...) for model detail. Model changes
    invalidate the list cursor; snapshots are saved states, not live queries.
    """
    return await invoke(general.list_models, limit, detail, cursor)


@mcp.tool(annotations=CREATE)
async def creo_regenerate(model_id: str, expected_revision: int) -> dict[str, Any]:
    """Regenerate, verify, save and reload a native model."""
    return await invoke(general.submit, [{"op": "regenerate"}], model_id, None, expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_save_model(model_id: str, expected_revision: int) -> dict[str, Any]:
    """Save a new native PRT version to the owned model directory, then reload and verify it."""
    return await invoke(general.submit, [{"op": "save"}], model_id, None, expected_revision)


@mcp.tool(annotations=READ)
async def creo_export_model(
    model_id: str, format: Literal["step", "stl", "iges", "jpeg", "pdf"] = "step"
) -> dict[str, Any]:
    """Export solids to STEP/STL/IGES/JPEG or drawings to PDF/JPEG inside the job output directory."""
    return await invoke(
        general.submit, [{"op": "export", "format": format}], model_id, None, None, None, True
    )


@mcp.tool(annotations=READ)
async def creo_dump_feature_tree(model_id: str, feature: str | int) -> dict[str, Any]:
    """Export a native feature's Toolkit element tree to XML for inspection; returns a job_id."""
    return await invoke(
        general.submit, [{"op": "dump_tree", "feature": feature}], model_id, None, None, None, True
    )


@mcp.tool(annotations=CREATE)
async def creo_new_drawing(
    source_model_id: str, model_name: str | None = None, width: float = 297, height: float = 210
) -> dict[str, Any]:
    """Create a native DRW with an isolated snapshot of an owned part/sheetmetal model.

    Sheet dimensions and all drawing positions use mm from the lower left corner.
    The source snapshot has label 'model'. Add views, notes, tables and shown model
    dimensions, then export PDF. Source model edits do not update this snapshot.
    """
    return await invoke(
        general.submit,
        [
            {"op": "drawing_sheet", "action": "resize", "width": width, "height": height},
            {"op": "drawing_model", "label": "model", "source_model_id": source_model_id},
        ],
        None,
        model_name,
        model_type="drawing",
    )


@mcp.tool(annotations=CREATE)
async def creo_drawing_view(
    model_id: str,
    expected_revision: int,
    label: str,
    position: list[float],
    orientation: Literal["front", "back", "top", "bottom", "left", "right", "isometric"] = "front",
    scale: float = 1,
    sheet: int = 1,
    model: str = "model",
    display: Literal["wireframe", "hidden", "no_hidden", "shaded", "shaded_edges"] = "no_hidden",
) -> dict[str, Any]:
    """Create a native model-associated general drawing view. position is sheet [x,y] in mm."""
    return await invoke(
        general.submit,
        [
            dict(
                op="drawing_view",
                label=label,
                position=position,
                orientation=orientation,
                scale=scale,
                sheet=sheet,
                model=model,
                display=display,
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_drawing_projection(
    model_id: str,
    expected_revision: int,
    label: str,
    parent: str | int,
    position: list[float],
    display: Literal["wireframe", "hidden", "no_hidden", "shaded", "shaded_edges"] = "no_hidden",
) -> dict[str, Any]:
    """Create a native projected view from a drawing view label/ID, on the parent's sheet."""
    return await invoke(
        general.submit,
        [
            dict(
                op="drawing_projection",
                label=label,
                parent=parent,
                position=position,
                display=display,
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_drawing_note(
    model_id: str,
    expected_revision: int,
    label: str,
    lines: list[str],
    position: list[float],
    sheet: int = 1,
    text_height: float = 3.5,
) -> dict[str, Any]:
    """Create a native multiline drawing note. Text is preserved in the saved DRW and PDF."""
    return await invoke(
        general.submit,
        [
            dict(
                op="drawing_note",
                label=label,
                lines=lines,
                position=position,
                sheet=sheet,
                text_height=text_height,
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_drawing_table(
    model_id: str,
    expected_revision: int,
    label: str,
    cells: list[list[str]],
    columns: list[float],
    position: list[float],
    row_height: float = 8,
    sheet: int = 1,
) -> dict[str, Any]:
    """Create an editable native drawing table. Column widths, row height and position use mm."""
    return await invoke(
        general.submit,
        [
            dict(
                op="drawing_table",
                label=label,
                cells=cells,
                columns=columns,
                position=position,
                row_height=row_height,
                sheet=sheet,
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_drawing_dimension(
    model_id: str,
    expected_revision: int,
    label: str,
    view: str | int,
    dimension_id: int,
    position: list[float] | None = None,
) -> dict[str, Any]:
    """Show an existing driving model dimension in a drawing view. Inspect the source snapshot for dimension IDs."""
    op = dict(op="drawing_dimension", label=label, view=view, dimension_id=dimension_id)
    if position is not None:
        op["position"] = position
    return await invoke(general.submit, [op], model_id, None, expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_datum_csys(
    model_id: str,
    expected_revision: int,
    label: str,
    translation: list[float] | None = None,
    rotation: list[float] | None = None,
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an offset native coordinate system. Offsets use mm; rotations use degrees about successive X,Y,Z axes."""
    return await invoke(
        general.submit,
        [
            dict(
                op="datum_csys",
                label=label,
                translation=translation or [0, 0, 0],
                rotation=rotation or [0, 0, 0],
                reference=reference or {"kind": "default_csys"},
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_datum_points(
    model_id: str,
    expected_revision: int,
    label: str,
    points: list[dict[str, Any]],
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create dimensioned datum points: [{name: 'p1', position: [x,y,z]}], relative to a coordinate system."""
    return await invoke(
        general.submit,
        [
            dict(
                op="datum_points",
                label=label,
                points=points,
                reference=reference or {"kind": "default_csys"},
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_surface_fill(
    model_id: str, expected_revision: int, label: str, sketch: str | int
) -> dict[str, Any]:
    """Create a native planar fill surface from a closed sketch. Reference its quilt by {kind:'quilt_feature',label:...}."""
    return await invoke(
        general.submit,
        [dict(op="surface_fill", label=label, sketch=sketch)],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_thicken(
    model_id: str,
    expected_revision: int,
    label: str,
    reference: dict[str, Any],
    thickness: float,
    side: Literal["positive", "negative", "symmetric"] = "symmetric",
    mode: Literal["add", "cut"] = "add",
    new_body: bool = False,
) -> dict[str, Any]:
    """Create a native thicken feature from a quilt. Supports solid addition/cut and symmetric thickness."""
    return await invoke(
        general.submit,
        [
            dict(
                op="thicken",
                label=label,
                reference=reference,
                thickness=thickness,
                side=side,
                mode=mode,
                new_body=new_body,
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_solidify(
    model_id: str,
    expected_revision: int,
    label: str,
    reference: dict[str, Any],
    side: Literal["positive", "negative"] = "positive",
    mode: Literal["add", "cut"] = "add",
    new_body: bool = False,
) -> dict[str, Any]:
    """Create native solidify from a quilt, or trim a solid with a datum plane using mode='cut'."""
    return await invoke(
        general.submit,
        [
            dict(
                op="solidify",
                label=label,
                reference=reference,
                side=side,
                mode=mode,
                new_body=new_body,
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_boolean_bodies(
    model_id: str,
    expected_revision: int,
    label: str,
    method: Literal["union", "subtract", "intersect"],
    targets: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    keep_tools: bool = False,
) -> dict[str, Any]:
    """Create a parametric multi-body Boolean feature. Inspect explicit body IDs; all references use {kind:'body',id:...}."""
    return await invoke(
        general.submit,
        [
            dict(
                op="boolean_bodies",
                label=label,
                method=method,
                targets=targets,
                tools=tools,
                keep_tools=keep_tools,
            )
        ],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_rib(
    model_id: str,
    expected_revision: int,
    label: str,
    sketch: str | int,
    thickness: float,
    side: Literal["positive", "negative", "symmetric"] = "symmetric",
    flip: bool = False,
) -> dict[str, Any]:
    """Create a native profile rib from an open sketch intersecting the target solid. flip changes material side."""
    return await invoke(
        general.submit,
        [dict(op="rib", label=label, sketch=sketch, thickness=thickness, side=side, flip=flip)],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_drawing_sheet(
    model_id: str,
    expected_revision: int,
    action: Literal["add", "resize"],
    width: float,
    height: float,
    sheet: int = 1,
    name: str | None = None,
) -> dict[str, Any]:
    """Add or resize a native drawing sheet; dimensions use mm. add returns the sheet number in operations."""
    op = dict(op="drawing_sheet", action=action, width=width, height=height, sheet=sheet)
    if name is not None:
        op["name"] = name
    return await invoke(general.submit, [op], model_id, None, expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_drawing_view_update(
    model_id: str,
    expected_revision: int,
    view: str | int,
    scale: float | None = None,
    move: list[float] | None = None,
    display: Literal["wireframe", "hidden", "no_hidden", "shaded", "shaded_edges"] | None = None,
) -> dict[str, Any]:
    """Change view scale/style or move it by a sheet-space [dx,dy] vector in mm."""
    op = dict(op="drawing_view_update", view=view)
    for key, value in dict(scale=scale, move=move, display=display).items():
        if value is not None:
            op[key] = value
    return await invoke(general.submit, [op], model_id, None, expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_drawing_note_update(
    model_id: str,
    expected_revision: int,
    note: str | int,
    lines: list[str] | None = None,
    position: list[float] | None = None,
    text_height: float | None = None,
) -> dict[str, Any]:
    """Edit the text, absolute position or text height of an existing native drawing note."""
    op = dict(op="drawing_note_update", note=note)
    for key, value in dict(lines=lines, position=position, text_height=text_height).items():
        if value is not None:
            op[key] = value
    return await invoke(general.submit, [op], model_id, None, expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_drawing_table_cell(
    model_id: str, expected_revision: int, table: str | int, row: int, column: int, text: str
) -> dict[str, Any]:
    """Edit one native table cell. Row and column numbers start at one."""
    return await invoke(
        general.submit,
        [dict(op="drawing_table_cell", table=table, row=row, column=column, text=text)],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=CREATE)
async def creo_drawing_delete(
    model_id: str,
    expected_revision: int,
    kind: Literal["view", "note", "table", "dimension"],
    target: str | int,
) -> dict[str, Any]:
    """Delete a drawing item. dimension erases its display only; use its label. Remove dependent views/dimensions before parent views."""
    return await invoke(
        general.submit,
        [dict(op="drawing_delete", kind=kind, target=target)],
        model_id,
        None,
        expected_revision,
    )


@mcp.tool(annotations=READ)
async def creo_inspect_udf(
    model_id: str, file_path: str, instance: str | None = None
) -> dict[str, Any]:
    """Read a local Creo UDF (.gph) reference prompts and variable dimensions. Returns a job; inspect operations[].metadata.

    The library is copied into the job directory. It is not bundled with this server.
    """
    op = dict(op="udf_inspect", file_path=file_path)
    if instance is not None:
        op["instance"] = instance
    return await invoke(general.submit, [op], model_id, None, None, None, True)


@mcp.tool(annotations=CREATE)
async def creo_create_udf(
    model_id: str,
    expected_revision: int,
    label: str,
    file_path: str,
    references: dict[str, dict[str, Any]],
    dimensions: dict[str, float] | None = None,
    instance: str | None = None,
) -> dict[str, Any]:
    """Place a native independent UDF group, preserving editable features. First inspect the library.

    references maps each exact prompt to a native reference; dimensions maps variable names (e.g. d11)
    to values in target model units. Interactive placement and missing-reference dialogs are disabled.
    """
    op = dict(
        op="udf_create",
        label=label,
        file_path=file_path,
        references=references,
        dimensions=dimensions or {},
    )
    if instance is not None:
        op["instance"] = instance
    return await invoke(general.submit, [op], model_id, None, expected_revision)


for _unavailable in UNAVAILABLE_OPERATIONS:
    mcp.remove_tool("creo_" + _unavailable)

if __name__ == "__main__":
    mcp.run(transport="stdio")
