"""Persistent owned models and composable general feature jobs."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import bridge
from capabilities import require_available
from creo_mechdog import component_changes, model_registry, operation_results
from creo_mechdog.model_queries import inspect_page, list_page, model_summary
from creo_mechdog.schema import Assertions, LoftOp, validate_operations

MODELS = bridge.ROOT / "models"


def model_path(model_id: str) -> Path:
    if not bridge.JOB_ID.fullmatch(model_id):
        raise ValueError("Invalid model_id")
    path = MODELS / model_id
    if path.is_symlink() or path.is_junction():
        raise ValueError("Model directories cannot be links")
    return path


def model_info(model_id: str) -> dict:
    return model_registry.read_control(model_path(model_id))


def list_models(limit: int = 10, detail: str = "compact", cursor: str | None = None) -> dict:
    if not 1 <= limit <= 50:
        raise ValueError("limit must be 1–50")
    paths = sorted(MODELS.glob("*/model.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    models = []
    for path in paths:
        # A single broken entry must not hide the registry listing; show a
        # placeholder pointing at the maintenance tools instead (BUG-077).
        try:
            if path.stat().st_size > model_registry.BUDGET_BYTES:
                raise model_registry.RegistryBudgetExceeded(file=path, failed_stage="list_models")
            model = bridge.read_json(path)
            if not isinstance(model, dict):
                raise ValueError("not an object")
        except (ValueError, OSError) as error:
            model = {
                "model_id": path.parent.name,
                "status": "registry_entry_unreadable",
                "registry_error": str(error),
            }
        models.append(model_summary(model))
    return list_page(models, model_info, detail, limit, cursor)


def inspect_model(
    model_id: str,
    detail: str = "compact",
    section: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict:
    return inspect_page(model_info(model_id), detail, section, limit, cursor)


def component_graph(source: dict, target_id: str, seen: set[str] | None = None) -> dict[str, dict]:
    """Check all assembly descendants before a native job is queued."""
    seen = set() if seen is None else seen
    sid = source["model_id"]
    if sid == target_id:
        raise ValueError("Assembly containment cycle is not allowed")
    if sid in seen:
        return {}
    seen.add(sid)
    if source["status"] != "ready" or source.get("pending_job"):
        raise ValueError("Every component source must be ready with no pending mutation")
    if not source.get("part_file") or not Path(source["part_file"]).is_file():
        raise ValueError("Every component source needs a verified saved native file")
    result = {sid: source}
    for alias in model_registry.aliases_of(source).values():
        child = alias.get("source_model_id")
        if child:
            result.update(component_graph(model_info(child), target_id, seen))
    return result


def _request_view(model: dict) -> dict:
    """The model form sent to the native executor: references over payloads.

    A record with a controlled reference drops its inline payload (native
    resolves the reference); a legacy inline record keeps it, so an empty
    ``aliases`` object always reaches the executor as an object (BUG-077).
    """
    view = dict(model)
    for key in model_registry.DETAIL_KEYS:
        if f"{key}_ref" in view:
            view.pop(key, None)
    return view


def new_loft_part(
    seed_file: str | None,
    seed_feature_id: int | None,
    sections: list[dict],
    label: str = "loft",
    model_name: str | None = None,
    assertions: dict | None = None,
    interpolation: str = "straight",
) -> dict:
    """Create a new part by rebinding a native Blend seed with matching section count."""
    sections = validate_operations(sections)
    if not 2 <= len(sections) <= 20 or any(
        s["op"] not in ("sketch", "airfoil_sketch") for s in sections
    ):
        raise ValueError("Between 2 and 20 sketch operations are required")
    if any(s["plane"] != "XY" for s in sections) or any(
        a["offset"] >= b["offset"] for a, b in zip(sections, sections[1:])
    ):
        raise ValueError("This workflow requires XY sketches with strictly increasing Z offsets")
    from creo_mechdog import airfoil
    from creo_mechdog.profile_checks import closed_profile

    for section in sections:
        entities = (
            airfoil.entities(section["profile"])
            if section["op"] == "airfoil_sketch"
            else section["entities"]
        )
        if not (section.get("dimensions") or section.get("constraints")):
            try:
                closed_profile(entities)
            except ValueError as error:
                raise ValueError(f"Section {section['label']}: {error}") from error
    binding = LoftOp.model_validate(
        {
            "op": "loft",
            "label": label,
            "sections": [s["label"] for s in sections],
            "interpolation": interpolation,
        }
    ).model_dump()
    if label in binding["sections"]:
        raise ValueError("Loft and sketch labels must be distinct")
    if (seed_file is None) != (seed_feature_id is None):
        raise ValueError(
            "Supply both seed_file and seed_feature_id, or omit both for automatic selection"
        )
    if seed_file is None:
        import seeds

        selected = seeds.select_seed(len(sections), interpolation)
        seed_file, seed_feature_id = selected["seed_file"], selected["seed_feature_id"]
    if (
        isinstance(seed_feature_id, bool)
        or not isinstance(seed_feature_id, int)
        or not 0 <= seed_feature_id <= 2147483647
    ):
        raise ValueError("seed_feature_id must be a nonnegative 32-bit native feature ID")
    source = Path(seed_file).expanduser()
    if (
        not source.is_absolute()
        or not source.is_file()
        or not re.fullmatch(r"[A-Za-z0-9_]{1,31}\.prt(?:\.\d+)?", source.name, re.I)
    ):
        raise ValueError("seed_file must be an absolute path to a native .prt or .prt.N file")
    binding = {
        "label": label,
        "sections": binding["sections"],
        "feature_id": seed_feature_id,
        "source_file": str(source.resolve()),
        "interpolation": binding["interpolation"],
    }
    return submit(sections, model_name=model_name, assertions=assertions, loft_seed=binding)


def submit(
    operations: list[dict],
    model_id: str | None = None,
    model_name: str | None = None,
    expected_revision: int | None = None,
    assertions: dict | None = None,
    readonly: bool = False,
    model_type: str = "part",
    loft_seed: dict | None = None,
) -> dict:
    operations = validate_operations(operations)
    require_available(operations)
    assertions = Assertions.model_validate(assertions or {}).model_dump(exclude_none=True)
    if loft_seed and (model_id is not None or readonly or model_type != "part"):
        raise ValueError("Native loft seed initialization is only available for a new part")
    if readonly and any(
        op["op"] not in ("dump_tree", "export", "udf_inspect") for op in operations
    ):
        raise ValueError("Read-only requests may only inspect/export")
    with bridge.toolkit_lock(operation="submit", model_id=model_id):
        new = model_id is None
        if new:
            if model_type not in ("part", "sheetmetal", "assembly", "drawing"):
                raise ValueError("Unsupported model_type")
            if model_name is not None:
                model_name = bridge.normalize_model_name(model_name)
            model_id = uuid.uuid4().hex
            path = model_path(model_id)
            model = {
                "model_id": model_id,
                "model_name": model_name or f"ai_part_{model_id[:12]}",
                "revision": 0,
                "created_at": bridge.now(),
                "status": "new",
                "aliases": {},
                "model_type": model_type,
                "output_directory": str(path / "output"),
                "part_file": None,
            }
            if len(model["output_directory"]) > 220:
                raise ValueError("Project path is too long for Creo Toolkit")
        else:
            path = model_path(model_id)
            model = model_info(model_id)
            if model.get("pending_job") or model.get("recovery_pending"):
                raise bridge.ToolkitBusy(
                    "Model has a pending job",
                    holder={
                        "job_id": model.get("recovery_pending") or model.get("pending_job"),
                        "model_id": model_id,
                        "operation": "pending_job",
                    },
                )
            if model["status"] != "ready":
                raise ValueError("Model is not ready; inspect its last job before recovery")
            if expected_revision is None and not readonly:
                raise ValueError(
                    "Provide expected_revision from creo_inspect_model to prevent stale edits"
                )
            if expected_revision is not None and expected_revision != model["revision"]:
                raise ValueError(f"Stale revision: current model revision is {model['revision']}")
            if not readonly:
                from creo_mechdog.reconciliation import validate_baseline

                validate_baseline(model)
        actual_type = model.get("model_type", "part")
        assembly_ops = {
            "assemble_component",
            "component_placement",
            "component_constraints",
            "remove_component",
        }
        for op in operations:
            if op["op"].startswith("drawing_") and actual_type != "drawing":
                raise ValueError("Drawing operations require an MCP drawing")
            if actual_type == "drawing" and not (
                op["op"].startswith("drawing_") or op["op"] in {"regenerate", "save", "export"}
            ):
                raise ValueError("This operation requires a solid model")
            if op["op"] == "export":
                if actual_type == "drawing" and op["format"] not in {"pdf", "jpeg"}:
                    raise ValueError("Drawing export supports PDF and JPEG")
                if actual_type != "drawing" and op["format"] == "pdf":
                    raise ValueError("PDF export requires a drawing")
            if op["op"] in assembly_ops and actual_type != "assembly":
                raise ValueError("Assembly operations require an MCP assembly model")
            if op["op"].startswith("sheetmetal_") and actual_type != "sheetmetal":
                raise ValueError("Sheetmetal operations require an MCP sheetmetal model")
            if actual_type == "assembly" and op["op"] not in assembly_ops | {
                "datum_plane",
                "datum_axis",
                "datum_csys",
                "datum_points",
                "set_parameters",
                "set_relations",
                "set_dimensions",
                "regenerate",
                "save",
                "export",
                "dump_tree",
                "feature_tree",
            }:
                raise ValueError("This operation requires a part model")
        components = {}
        for op in operations:
            if op["op"] in ("assemble_component", "drawing_model"):
                source = model_info(op["source_model_id"])
                components.update(component_graph(source, model_id))
                if source.get("model_type") in ("assembly", "drawing"):
                    raise ValueError(
                        "Nested assembly copying is not yet supported; insert owned part/sheetmetal models"
                    )
        aliases = model_registry.aliases_of(model) if not new else {}
        duplicate = set(aliases).intersection(op["label"] for op in operations if "label" in op)
        if duplicate:
            raise ValueError(f"Feature labels already exist: {sorted(duplicate)}")
        from creo_mechdog import airfoil

        operations = airfoil.prepare(operations, aliases)
        # Initialize from a solid template. Native first-wall conversion creates
        # the sheetmetal body; the stock empty SMT body breaks attached walls.
        templates = {
            "part": "mmns_part_solid_abs.prt",
            "sheetmetal": "mmns_part_solid_abs.prt",
            "assembly": "mmns_asm_design_abs.asm",
            "drawing": "a4_drawing.drw",
        }
        template = (
            Path(bridge.config()["creo_root"]) / "Common Files/templates" / templates[actual_type]
        )
        if not template.is_file():
            raise ValueError(f"Missing local model template: {templates[actual_type]}")
        udf_files = {}
        for index, op in enumerate(operations):
            if op["op"] in ("udf_inspect", "udf_create"):
                source = Path(op["file_path"]).expanduser()
                if (
                    not source.is_absolute()
                    or not source.is_file()
                    or not re.search(r"\.gph(?:\.\d+)?$", source.name, re.I)
                ):
                    raise ValueError(
                        "UDF file_path must be an absolute path to an existing .gph or .gph.N file"
                    )
                udf_files[index] = source.resolve()
        if new:
            (path / "output").mkdir(parents=True)
        job_id = uuid.uuid4().hex
        directory = bridge.job_path(job_id)
        directory.mkdir(parents=True)
        (directory / "output").mkdir()
        if loft_seed:
            source = Path(loft_seed["source_file"])
            inputs = directory / "input" / "loft_seed"
            inputs.mkdir(parents=True)
            template = inputs / source.name.lower()
            shutil.copyfile(source, template)
            digest = hashlib.sha256(template.read_bytes()).hexdigest()
            # The seed identity travels with the request so a native load failure
            # can name the seed and its bytes (FEAT-030/BUG-034).
            entry = None
            try:
                import seeds

                entry = seeds.manifest_entry_by_digest(digest)
            except (OSError, ValueError):
                entry = None
            loft_seed = {
                **loft_seed,
                "snapshot_sha256": digest,
                "seed_name": entry["name"] if entry else loft_seed.get("seed_name"),
                "seed_manifest_sha256": (
                    entry["sha256"] if entry else loft_seed.get("seed_manifest_sha256")
                ),
                "seed_source": str(source),
            }
        for index, source in udf_files.items():
            inputs = directory / "input" / str(index)
            inputs.mkdir(parents=True)
            snapshot = inputs / "library.gph"
            shutil.copyfile(source, snapshot)
            operations[index]["file_path"] = str(snapshot)
        model["pending_job"] = job_id
        # Splitting at reservation time also lazily migrates a legacy inline
        # record, so request.json never carries an unbounded payload (BUG-077).
        model_registry.write_model(path, model)
        request = {
            "new": new,
            "model": _request_view(model),
            "operations": operations,
            "readonly": readonly,
            "components": {sid: _request_view(source) for sid, source in components.items()},
            "template_file": str(template),
            "assertions": assertions or {},
        }
        if loft_seed:
            request["loft_seed"] = loft_seed
        manifest = {
            "job_id": job_id,
            "kind": "generic",
            "model_id": model_id,
            "status": "queued",
            "readonly": readonly,
            "created_at": bridge.now(),
            "operations": operations,
            "job_directory": str(directory),
            "output_directory": str(directory / "output"),
            "message": "Poll creo_get_job with this job_id; do not resubmit the operation",
        }
        if loft_seed:
            manifest["construction"] = "native_multisection_blend_seed_rebinding"
        bridge.write_json(directory / "request.json", request)
        bridge.write_json(directory / "job.json", manifest)
        try:
            with (directory / "runner.log").open("ab") as log:
                subprocess.Popen(
                    [sys.executable, str(bridge.ROOT / "bridge.py"), "run-job", job_id],
                    cwd=bridge.ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=bridge.HIDDEN,
                    close_fds=True,
                )
        except Exception as exc:
            model.update(status="failed" if new else "ready", pending_job=None)
            model_registry.write_model(path, model)
            manifest.update(status="failed", message=str(exc), finished_at=bridge.now())
            bridge.write_json(directory / "job.json", manifest)
            raise
        return {**manifest, "model_name": model["model_name"], "revision": model["revision"]}


def run_generic_job(job_id: str, manifest: dict):
    directory = bridge.job_path(job_id)
    request = bridge.read_json(directory / "request.json")
    model = request["model"]
    path = model_path(model["model_id"])
    # Pre-job verified state snapshot for the bounded component change
    # summary, captured BEFORE the worker can mutate the control record, and
    # ONLY when the request actually targets components — plain part jobs
    # never touch the alias/inspection sidecars. A read failure is recorded
    # and later degrades the summary to status=unavailable; it never affects
    # the native run or the confirmed terminal state.
    prior_state = {"aliases": None, "inspection": None, "error": None}
    if any(op.get("op") in component_changes.CHANGE_OPS for op in request["operations"]):
        try:
            prior = model_registry.read_control(path)
        except (OSError, ValueError):
            # Seed/recovery fixtures may run without a persisted control
            # record; fall back to the request view (which may carry detail
            # references instead of payloads).
            prior = model
        try:
            prior_state["aliases"] = model_registry.aliases_of(prior)
            prior_state["inspection"] = model_registry.inspection_of(prior)
        except Exception as exc:  # noqa: BLE001 - summary-only read failure
            prior_state["error"] = exc
    result_aliases = None
    result_inspection = None
    result = None
    worker_started = False
    try:
        with bridge.toolkit_lock(
            wait_seconds=120, operation="execute_plan", job_id=job_id, model_id=model["model_id"]
        ):
            try:
                manifest.update(
                    status="running",
                    stage="building_worker",
                    started_at=bridge.now(),
                    worker_started=False,
                )
                bridge.write_json(directory / "job.json", manifest)
                exe = bridge.build_native()
                manifest["stage"] = "executing_feature_plan"
                bridge.write_json(directory / "job.json", manifest)
                with (directory / "worker.log").open("wb") as log:
                    worker_started = True
                    manifest["worker_started"] = True
                    bridge.write_json(directory / "job.json", manifest)
                    proc = subprocess.run(
                        [str(exe), "generic", str(directory)],
                        cwd=directory,
                        env=bridge.native_environment(),
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=bridge.config().get("generic_timeout_seconds", 600),
                        creationflags=bridge.HIDDEN,
                    )
                result_file = directory / "native_result.json"
                if not result_file.exists():
                    manifest.update(
                        status="unknown_outcome",
                        message=f"Native worker exited {proc.returncode} without a result; inspect Creo before retrying",
                    )
                    model["status"] = "unknown_outcome"
                else:
                    result = operation_results.annotate_native_result(
                        bridge.read_json(result_file),
                        readonly=request["readonly"],
                        inputs=request["operations"],
                    )
                    # Shared preview projection (T07): raw capture codes live on
                    # the result, a failed image stays a failed image, and the
                    # model save/revision outcome is never altered by it.
                    from creo_mechdog import preview

                    preview.apply_preview_projection(result, directory=directory)
                    result_aliases = result.get("aliases")
                    result_inspection = result.get("inspection")
                    # Job manifests keep only summaries and controlled references;
                    # a repeated full-payload result would regrow the read budget
                    # problem inside job.json (BUG-077).
                    model_registry.split_job_result(result, directory)
                    manifest["result"] = result
                    if request.get("loft_seed"):
                        from creo_mechdog import seed_compatibility

                        evidence = seed_compatibility.observe_load(request, result, job_id)
                        result["seed_load_evidence"] = evidence
                        if isinstance(evidence, dict) and evidence.get("status") == "load_failed":
                            # Keep the native wording and add the seed identity,
                            # stage and session release behind it.
                            result["native_message"] = result.get("message")
                            result["message"] = seed_compatibility.load_failure_message(result)
                    if (
                        result.get("disconnect_code") not in (None, 0)
                        or result.get("delivery_complete") is False
                    ):
                        manifest.update(
                            status="unknown_outcome",
                            message="Native finalization was not confirmed; preserve saved files and inspect the checkpoint",
                        )
                        model["status"] = "unknown_outcome"
                    elif proc.returncode == 0 and result.get("success"):
                        if not request["readonly"] and not result.get(
                            "saved_file_reloaded_and_verified"
                        ):
                            raise RuntimeError("Saved model was not verified")
                        part = Path(result["part_file"])
                        if (
                            part.parent.resolve() != (path / "output").resolve()
                            or not part.is_file()
                        ):
                            raise RuntimeError("Unexpected native output file")
                        result["sha256"] = hashlib.sha256(part.read_bytes()).hexdigest()
                        if request["readonly"]:
                            model.update(status="ready", last_query_at=bridge.now())
                            # The result was split above; keep whichever live
                            # detail form exists under the last_live_* names.
                            model.pop("last_live_inspection", None)
                            model.pop("last_live_inspection_ref", None)
                            if "inspection" in result:
                                model["last_live_inspection"] = result["inspection"]
                            if "inspection_ref" in result:
                                model["last_live_inspection_ref"] = result["inspection_ref"]
                        else:
                            model["revision"] += 1
                            model.update(
                                status="ready",
                                part_file=result["part_file"],
                                part_sha256=result["sha256"],
                                updated_at=bridge.now(),
                                last_job=job_id,
                            )
                            # Detail references come straight from the split
                            # result; stale legacy inline keys never survive an
                            # edit (BUG-077).
                            for key in model_registry.DETAIL_KEYS:
                                model.pop(key, None)
                                model.pop(f"{key}_ref", None)
                            for key in (
                                "aliases",
                                "aliases_ref",
                                "inspection",
                                "inspection_ref",
                                "inspection_summary",
                            ):
                                if key in result:
                                    model[key] = result[key]
                        manifest.update(
                            status="succeeded",
                            stage="verified",
                            message="General feature plan completed",
                            revision=model["revision"],
                        )
                    else:
                        model["status"] = (
                            "ready"
                            if (
                                request["readonly"]
                                or result.get("rollback_succeeded")
                                or (
                                    result.get("model_unchanged") is True
                                    and result.get("failed_stage") == "callback_preflight"
                                )
                            )
                            and model.get("part_file")
                            else "failed"
                        )
                        manifest.update(
                            status="failed",
                            message=result.get(
                                "message", f"Toolkit code {result.get('toolkit_code')}"
                            ),
                        )
            except subprocess.TimeoutExpired:
                manifest.update(
                    status="unknown_outcome" if worker_started else "failed",
                    message="Native worker timed out; inspect Creo and the native checkpoint before retrying"
                    if worker_started
                    else "Native build exceeded its subprocess budget; inspect build logs. No native modeling worker started.",
                )
                model["status"] = (
                    "unknown_outcome"
                    if worker_started
                    else ("ready" if model.get("part_file") else "failed")
                )
            except Exception as exc:
                manifest.update(
                    status="unknown_outcome" if worker_started else "failed", message=str(exc)
                )
                model["status"] = (
                    "unknown_outcome"
                    if worker_started
                    else ("ready" if model.get("part_file") else "failed")
                )
            # A killed helper or a saved checkpoint is not a confirmed operation outcome.
            model["pending_job"] = job_id if manifest["status"] == "unknown_outcome" else None
            model["last_job"] = job_id
            bridge.note_native_outcome(manifest)
            model_registry.write_model(path, model)
    except bridge.ToolkitBusy as exc:
        # No worker ran. Never rewrite a model while another owner holds the channel.
        manifest.update(
            status="failed",
            message=str(exc),
            busy=exc.payload,
            recovery_required="Model reservation retained; inspect before recovery",
        )
    # The summary is auxiliary: it rides on the confirmed terminal state and
    # native evidence, and a summary failure must never rewrite that state or
    # leave a persisted job stuck in running. All reads that exist ONLY for
    # the summary are failure-isolated; sidecar failures or read-budget
    # errors degrade to component_changes.status=unavailable.
    try:
        summary = _component_summary(
            request,
            manifest,
            result,
            worker_started,
            result_aliases,
            result_inspection,
            prior_state,
        )
    except Exception as exc:  # noqa: BLE001 - auxiliary path, state stays authoritative
        summary = component_changes.unavailable(exc)
    if summary is not None:
        manifest["component_changes"] = summary
    manifest["finished_at"] = bridge.now()
    bridge.write_json(directory / "job.json", manifest)


def _component_summary(
    request: dict,
    manifest: dict,
    result: dict | None,
    worker_started: bool,
    result_aliases: dict | None,
    result_inspection: dict | None,
    prior_state: dict,
) -> dict | None:
    """Build the summary from the pre-job snapshot plus native evidence.

    Returns None (no component_changes key at all) when the request targeted
    no component. A pre-job snapshot read failure is raised only when the
    summary status would actually use the prior state (committed net diff,
    rolled-back label resolution); statuses that never read the prior state
    (busy rejection, preflight refusal, unknown outcome) keep their original
    semantics instead of being masked as unavailable.
    """
    targeted = [op for op in request["operations"] if op.get("op") in component_changes.CHANGE_OPS]
    if not targeted:
        return None
    if prior_state.get("error") is not None:
        uses_prior = manifest["status"] == "succeeded" or (
            isinstance(result, dict) and result.get("rollback_succeeded") is True
        )
        if uses_prior:
            raise prior_state["error"]
    return component_changes.summarize(
        request["operations"],
        job_status=manifest["status"],
        rollback=result,
        executed=worker_started,
        prior_aliases=prior_state.get("aliases"),
        prior_inspection=prior_state.get("inspection"),
        result_aliases=result_aliases,
        result_inspection=result_inspection,
    )
