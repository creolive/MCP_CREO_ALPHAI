"""Persistent owned models and composable general feature jobs."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import bridge
from creo_mechdog import component_changes, feature_state, model_registry, operation_results
from creo_mechdog.capabilities import require_available
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


MASS_PROPERTIES_TIMEOUT_SECONDS = 120.0
_MASS_PROPERTIES_TERMINAL = (
    "succeeded",
    "failed",
    "aborted",
    "cancelled",
    "unknown_outcome",
)


def get_mass_properties(model_id: str, density_g_cm3: float | None = None) -> dict:
    """FEAT-057: read the model's mass properties through a read-only job.

    Synchronous on purpose: the query writes nothing, so the caller gets the
    normalized receipt instead of a job id it would have to poll. The material
    density decides the mass when it exists; ``density_g_cm3`` is only the
    explicit fallback, and the receipt always says which one was used.
    """
    from creo_mechdog.mass_properties import normalize_mass_properties

    operation: dict = {"op": "mass_properties"}
    if density_g_cm3 is not None:
        operation["density_g_cm3"] = float(density_g_cm3)
    accepted = submit([operation], model_id=model_id, readonly=True)
    job_id = accepted["job_id"]
    deadline = time.monotonic() + MASS_PROPERTIES_TIMEOUT_SECONDS
    record: dict = {}
    while True:
        path = bridge.job_path(job_id) / "job.json"
        if path.exists():
            record = bridge.read_json(path)
            if record.get("status") in _MASS_PROPERTIES_TERMINAL:
                break
        if time.monotonic() > deadline:
            raise RuntimeError(f"Mass properties query did not finish: job {job_id}")
        time.sleep(0.25)
    if record.get("status") != "succeeded":
        message = record.get("message") or f"Mass properties query failed: job {job_id}"
        raise RuntimeError(str(message))
    for entry in (record.get("result") or {}).get("operations") or []:
        if isinstance(entry, dict) and isinstance(entry.get("mass_properties"), dict):
            receipt = normalize_mass_properties(entry["mass_properties"])
            return {
                "job_id": job_id,
                "model_id": model_id,
                "revision": record.get("revision"),
                **receipt,
            }
    raise RuntimeError(f"Mass properties query returned no reading: job {job_id}")


def measure_surface_group(
    model_id: str,
    references: list[dict],
    tolerance_mm: float = 0.01,
    gap_search_mm: float = 1.0,
) -> dict:
    """FEAT-039/H04: read the group-level boundary measurement synchronously.

    The query is a read-only job: it writes nothing, does not regenerate and does
    not advance the revision, so the caller gets the receipt instead of a job id
    it would have to poll. The native executor measures the real boundary
    topology; nothing here recomputes or defaults a value.
    """
    operation: dict = {
        "op": "surface_group_measure",
        "references": references,
        "tolerance_mm": float(tolerance_mm),
        "gap_search_mm": float(gap_search_mm),
    }
    accepted = submit([operation], model_id=model_id, readonly=True)
    job_id = accepted["job_id"]
    deadline = time.monotonic() + MASS_PROPERTIES_TIMEOUT_SECONDS
    record: dict = {}
    while True:
        path = bridge.job_path(job_id) / "job.json"
        if path.exists():
            record = bridge.read_json(path)
            if record.get("status") in _MASS_PROPERTIES_TERMINAL:
                break
        if time.monotonic() > deadline:
            raise RuntimeError(f"Surface group measurement did not finish: job {job_id}")
        time.sleep(0.25)
    if record.get("status") != "succeeded":
        message = record.get("message") or f"Surface group measurement failed: job {job_id}"
        raise RuntimeError(str(message))
    for entry in (record.get("result") or {}).get("operations") or []:
        if isinstance(entry, dict) and entry.get("op") == "surface_group_measure":
            return {
                "job_id": job_id,
                "model_id": model_id,
                "revision": record.get("revision"),
                "readonly": True,
                "unit_name": entry.get("unit_name"),
                "length_scale_to_mm": entry.get("length_scale_to_mm"),
                "tolerance_mm": entry.get("tolerance_mm"),
                "gap_search_mm": entry.get("gap_search_mm"),
                "group": entry.get("group"),
            }
    raise RuntimeError(f"Surface group measurement returned no reading: job {job_id}")


def measure_surface_curvature(
    model_id: str,
    target: dict,
    faces: list,
    samples_per_direction: int = 12,
) -> dict:
    """DEV-074/H08: read the numerical curvature/G1 analysis synchronously.

    The query is a read-only job: it creates no feature, does not regenerate and
    does not advance the revision. The native executor samples the kernel's
    principal curvature and the seam normals; nothing here recomputes, rounds or
    defaults a value. There is no zebra-stripe or curvature-comb image API in
    Toolkit, so this receipt is the declared numeric equivalent.
    """
    operation: dict = {
        "op": "surface_curvature",
        "target": target,
        "faces": faces,
        "samples_per_direction": int(samples_per_direction),
    }
    accepted = submit([operation], model_id=model_id, readonly=True)
    job_id = accepted["job_id"]
    deadline = time.monotonic() + MASS_PROPERTIES_TIMEOUT_SECONDS
    record: dict = {}
    while True:
        path = bridge.job_path(job_id) / "job.json"
        if path.exists():
            record = bridge.read_json(path)
            if record.get("status") in _MASS_PROPERTIES_TERMINAL:
                break
        if time.monotonic() > deadline:
            raise RuntimeError(f"Surface curvature analysis did not finish: job {job_id}")
        time.sleep(0.25)
    if record.get("status") != "succeeded":
        message = record.get("message") or f"Surface curvature analysis failed: job {job_id}"
        raise RuntimeError(str(message))
    for entry in (record.get("result") or {}).get("operations") or []:
        if isinstance(entry, dict) and entry.get("op") == "surface_curvature":
            return {
                "job_id": job_id,
                "model_id": model_id,
                "revision": record.get("revision"),
                "readonly": True,
                "unit_name": entry.get("unit_name"),
                "length_scale_to_mm": entry.get("length_scale_to_mm"),
                "curvature_unit": entry.get("curvature_unit"),
                "radius_unit": entry.get("radius_unit"),
                "quilt_id": entry.get("quilt_id"),
                "samples_per_direction": entry.get("samples_per_direction"),
                "faces": entry.get("faces"),
                "summary": entry.get("summary"),
                "g1_max_angle_deg": entry.get("g1_max_angle_deg"),
                "g1_status": entry.get("g1_status"),
                "g1_threshold_deg": entry.get("g1_threshold_deg"),
                "within_g1": entry.get("within_g1"),
                "g1_points": entry.get("g1_points"),
            }
    raise RuntimeError(f"Surface curvature analysis returned no reading: job {job_id}")


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
        from creo_mechdog import seeds

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
    template_name: str | None = None,
) -> dict:
    operations = validate_operations(operations)
    require_available(operations)
    assertions = Assertions.model_validate(assertions or {}).model_dump(exclude_none=True)
    if loft_seed and (model_id is not None or readonly or model_type != "part"):
        raise ValueError("Native loft seed initialization is only available for a new part")
    if readonly and any(
        op["op"]
        not in (
            "dump_tree",
            "export",
            "udf_inspect",
            "mass_properties",
            "surface_group_measure",
            "surface_curvature",
        )
        for op in operations
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
                # FEAT-005: name both sides and the model so the caller can tell
                # which version it lost without a second inspect. The request is
                # still refused before any job exists.
                raise ValueError(
                    "Stale revision: "
                    f"model_id={model_id} "
                    f"current_revision={model['revision']} "
                    f"expected_revision={expected_revision}; "
                    "no job was created"
                )
            if not readonly:
                from creo_mechdog.reconciliation import validate_baseline

                validate_baseline(model)
        actual_type = model.get("model_type", "part")
        assembly_ops = {
            "assemble_component",
            "component_placement",
            "component_constraints",
            "remove_component",
            "recolor_assembly",
        }
        for op in operations:
            if op["op"].startswith("drawing_") and actual_type != "drawing":
                raise ValueError("Drawing operations require an MCP drawing")
            if actual_type == "drawing" and not (
                op["op"].startswith("drawing_") or op["op"] in {"regenerate", "save", "export"}
            ):
                raise ValueError("This operation requires a solid model")
            if op["op"] == "export":
                if op["format"] == "native_bundle" and actual_type != "assembly":
                    raise ValueError("native_bundle requires an assembly")
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
                "mass_properties",
                "feature_tree",
            }:
                raise ValueError("This operation requires a part model")
        # BUG-046 / DEV-051 T04: adding solid material into a sheetmetal body is
        # refused by Creo with a bare -1, so the plan is rejected here with an
        # identifiable code and viable tool guidance instead.
        if actual_type == "sheetmetal":
            from creo_mechdog.sheetmetal import solid_add_on_sheetmetal_problem

            problem = solid_add_on_sheetmetal_problem(operations)
            if problem:
                raise ValueError(problem)
        components = {}
        for op in operations:
            if op["op"] in ("assemble_component", "drawing_model"):
                source = model_info(op["source_model_id"])
                components.update(component_graph(source, model_id))
                if source.get("model_type") in ("assembly", "drawing"):
                    raise ValueError(
                        "Nested assembly copying is not yet supported; insert owned part/sheetmetal models"
                    )
        # DEV-047 T09: a replay plan binds the source revision/file digest it was
        # planned against. Re-read the registry and file bytes under the channel
        # lock so a source edit or external byte change is refused before a job
        # exists; the native executor re-checks the revision again before loading.
        from creo_mechdog.assembly_replay import validate_source_bindings

        validate_source_bindings(operations, models_root=MODELS)
        aliases = model_registry.aliases_of(model) if not new else {}
        # Deleted labels are tombstones: they can never name a new feature
        # (FEAT-027), so they are reserved exactly like existing aliases.
        feature_state.reject_tombstoned_labels(model if not new else None, operations)
        reserved = set(aliases) | (feature_state.tombstone_labels(model) if not new else set())
        # FEAT-058 review: an operation may create more than its own label (the
        # planar wall also creates its driving sketch `<label>_sk`). Every name a
        # plan introduces is protected, against the model and against the plan
        # itself.
        from creo_mechdog import native_planar_wall

        names = native_planar_wall.declared_names(operations)
        internal = [
            name
            for operation in operations
            for name in native_planar_wall.internal_labels(operation)
        ]
        duplicate = reserved.intersection(names)
        if duplicate:
            raise ValueError(f"Feature labels already exist: {sorted(duplicate)}")
        feature_state.reject_tombstoned_labels(
            model if not new else None,
            [{"op": "internal", "label": name} for name in internal],
        )
        conflict = native_planar_wall.name_conflict(names, set())
        if conflict:
            raise ValueError(
                "This plan declares the same feature name more than once: "
                f"{conflict}; a planar wall also creates its driving sketch <label>_sk"
            )
        # Part feature lifecycle admission: resolve explicit targets against
        # the saved inspection, refuse system objects/members, and require every
        # affected dependency to be listed (native re-checks before executing).
        feature_state.validate_plan(model if not new else None, operations)
        # FEAT-058: the native unattached planar wall is the *first* sheetmetal
        # wall and only regenerates in an empty sheetmetal part; its resize must
        # not rebuild features that depend on the wall, and a plan may create a
        # wall and resize it in the same breath. All of it is refused here,
        # before a job exists (the native executor re-checks subtype, emptiness,
        # names and children before it writes anything).
        features = None
        if not new and any(
            operation.get("op") == native_planar_wall.PLANAR_WALL_RESIZE_OP
            for operation in operations
        ):
            # A recorded child means a downstream feature depends on the wall.
            # The saved inspection is only read for a resize plan; an unreadable
            # reference leaves the native ProFeatureChildrenGet check authoritative.
            from creo_mechdog import inspection_refs

            try:
                saved = inspection_refs.full_inspection(model)
            except (ValueError, OSError):
                saved = None
            if isinstance(saved, dict) and isinstance(saved.get("features"), list):
                features = saved["features"]
        native_planar_wall.validate_plan(model if not new else None, operations, aliases, features)
        # FEAT-052: recolor_assembly admission and payload resolution share one
        # path for the standalone tool and execute_plan (the verified
        # checkpoint, appearance baseline, family grouping and complete
        # palette are checked here, before a job exists).
        from creo_mechdog import appearance

        operations = appearance.prepare_recolor_operations(model if not new else None, operations)
        from creo_mechdog import airfoil

        operations = airfoil.prepare(operations, aliases)
        # FEAT-039/W01: the endpoint weld policy is checked before a job exists,
        # so a profile the policy rejects never reaches the executor.
        from creo_mechdog import endpoint_welding

        operations = endpoint_welding.prepare_operations(operations)
        # FEAT-035: native receives the frozen hole-table row (fastener id, tap
        # drill, nominal, limit) instead of deriving any of it itself.
        from creo_mechdog import hole_standards

        operations = hole_standards.prepare(operations)
        # Initialize from a solid template. Native first-wall conversion creates
        # the sheetmetal body; the stock empty SMT body breaks attached walls.
        templates = {
            "part": "mmns_part_solid_abs.prt",
            "sheetmetal": "mmns_part_solid_abs.prt",
            "assembly": "mmns_asm_design_abs.asm",
            "drawing": "a4_drawing.drw",
        }
        # FEAT-058 probe only: a native unattached planar wall needs a real
        # sheetmetal part, and only the sheetmetal template produces one (a part
        # cannot be switched to the sheetmetal subtype). Accepted flows keep the
        # solid template, so the default path is unchanged.
        if template_name is not None:
            if not new or actual_type not in ("part", "sheetmetal"):
                raise ValueError("template_name is only available for a new part/sheetmetal model")
            if Path(template_name).name != template_name:
                raise ValueError("template_name must be a bare file name in the Creo templates")
        selected = template_name or templates[actual_type]
        template = Path(bridge.config()["creo_root"]) / "Common Files/templates" / selected
        if not template.is_file():
            raise ValueError(f"Missing local model template: {selected}")
        # BUG-100: acceptance releases the submit lock before the spawned
        # runner acquires the channel; an accepted-but-unfinished job must
        # reject here instead of letting this one queue behind it. Everything
        # above is validation without side effects, so no partial state exists.
        holder = bridge.admission_holder()
        if holder:
            raise bridge.ToolkitBusy(holder=holder)
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
                from creo_mechdog import seeds

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
            # R04/0.14.0: the accepted plan is echoed after validate_operations
            # (defaults applied, extrude omissions marked in defaulted_fields).
            # Label it so a receipt reader never mistakes it for the raw request.
            "operations": operations,
            "operations_view": "normalized",
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
                proc = subprocess.Popen(
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
        # Still inside the submit lock: the reservation is visible to the next
        # admission before this call returns (BUG-100).
        bridge.write_channel_claim(
            job_id,
            model_id=model_id,
            operation="execute_plan",
            runner_pid=getattr(proc, "pid", None),
        )
        return {**manifest, "model_name": model["model_name"], "revision": model["revision"]}


def failed_model_status(request: dict, result: dict, model: dict) -> str:
    """Registry status after a failed native job (BUG-105).

    Only positive evidence keeps the model ready: a read-only job, a verified
    rollback, or the native executor's "no operation was dispatched" marker.
    Every other failure (partially dispatched plan, missing rollback evidence)
    stays ``failed`` and must be resolved through ``creo_reconcile_model``. A
    model without a checkpoint has nothing to fall back to and also fails.
    """
    if not model.get("part_file"):
        return "failed"
    if (
        request.get("readonly")
        or result.get("rollback_succeeded")
        or result.get("model_unchanged") is True
    ):
        return "ready"
    return "failed"


def _checkpoint_present(request: dict) -> bool | None:
    """Whether the request's target already had a saved checkpoint.

    ``None`` means the request view did not carry ``part_file`` (legacy job):
    the caller must not read that absence as "no checkpoint".
    """
    model = request.get("model")
    if not isinstance(model, dict):
        return None
    if request.get("new"):
        return False
    if "part_file" in model:
        return bool(model.get("part_file"))
    return None


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
                        is_new_model=bool(request.get("new")),
                    )
                    # FEAT-052: project the native recolor block into the
                    # stable result shape (missing fields stay unknown and are
                    # never fabricated).
                    from creo_mechdog import appearance

                    appearance.annotate_recolor(result)
                    # FEAT-058: publish the planar wall verdict (feature
                    # identity, dimension count, signed frame envelope) on the
                    # result the client polls, because the tool returns the
                    # queued job rather than the finished one.
                    from creo_mechdog import native_planar_wall

                    native_planar_wall.annotate_result(result)
                    # FEAT-039/W01: publish the endpoint weld receipt per sketch
                    # operation; it is computed from the requested geometry and
                    # never claims the kernel welded anything.
                    from creo_mechdog import endpoint_welding

                    endpoint_welding.annotate_result(result, request["operations"])
                    # Shared preview projection (T07): raw capture codes live on
                    # the result, a failed image stays a failed image, and the
                    # model save/revision outcome is never altered by it.
                    from creo_mechdog import preview

                    preview.apply_preview_projection(result, directory=directory)
                    if result.get("success") and any(
                        op.get("op") == "export" and op.get("format") == "native_bundle"
                        for op in request["operations"]
                    ):
                        from creo_mechdog.assembly_bundle import create_bundle

                        try:
                            result["native_bundle"] = create_bundle(
                                model,
                                result.get("inspection", {}),
                                directory / "output",
                                path / "output",
                            )
                        except (OSError, ValueError) as exc:
                            result["success"] = False
                            result["message"] = f"native_bundle failed: {exc}"
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
                            # Deleted-label tombstones and the intentional
                            # suppression set are part of the model identity;
                            # a failed job never rewrites them.
                            feature_state.apply_result(model, result)
                        manifest.update(
                            status="succeeded",
                            stage="verified",
                            message="General feature plan completed",
                            revision=model["revision"],
                        )
                    else:
                        model["status"] = failed_model_status(request, result, model)
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
            bridge.apply_terminal_stage(manifest)
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
    # BUG-114: publish the scoped terminal effect (managed model, component
    # bindings, external outputs) on the same result the client polls. The
    # three verdicts come from the shared decision table; the job terminal
    # status, per-operation execution statuses and the legacy rollback fields
    # are never rewritten.
    if isinstance(result, dict) and manifest["status"] in ("failed", "unknown_outcome"):
        from creo_mechdog import terminal_effect

        terminal_effect.apply_to_result(
            result,
            job_status=manifest["status"],
            is_new_model=bool(request.get("new")),
            checkpoint_present=_checkpoint_present(request),
            operations=request["operations"],
        )
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
        is_new_model=bool(request.get("new")),
        checkpoint_present=_checkpoint_present(request),
        prior_aliases=prior_state.get("aliases"),
        prior_inspection=prior_state.get("inspection"),
        result_aliases=result_aliases,
        result_inspection=result_inspection,
    )
