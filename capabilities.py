"""Release scope. Registered tools are not a claim that every Creo operation works."""

from __future__ import annotations

from version import VERSION

REGISTERED_OPERATIONS = (
    "airfoil_sketch",
    "update_airfoil",
    "update_sketch_geometry",
    "feature_group",
    "reorder_features",
    "axis_pattern",
    "geometry_transform",
    "set_geometry_transform",
    "sketch",
    "extrude",
    "revolve",
    "hole",
    "round",
    "chamfer",
    "datum_plane",
    "datum_axis",
    "shell",
    "dimension_pattern",
    "mirror",
    "sweep",
    "loft",
    "draft",
    "sheetmetal_wall",
    "sheetmetal_flange",
    "sheetmetal_unbend",
    "sheetmetal_flat_pattern",
    "sheetmetal_bend_back",
    "assemble_component",
    "component_placement",
    "component_constraints",
    "remove_component",
    "feature_state",
    "set_dimensions",
    "set_sketch_dimensions",
    "set_parameters",
    "set_relations",
    "feature_tree",
    "regenerate",
    "save",
    "export",
    "dump_tree",
    "udf_inspect",
    "udf_create",
    "datum_csys",
    "datum_points",
    "surface_fill",
    "thicken",
    "solidify",
    "boolean_bodies",
    "rib",
    "drawing_model",
    "drawing_sheet",
    "drawing_view",
    "drawing_projection",
    "drawing_view_update",
    "drawing_note",
    "drawing_note_update",
    "drawing_table",
    "drawing_table_cell",
    "drawing_dimension",
    "drawing_delete",
)

UNAVAILABLE_OPERATIONS = {}


def require_available(operations: list[dict]) -> None:
    unavailable = [op["op"] for op in operations if op["op"] in UNAVAILABLE_OPERATIONS]
    if unavailable:
        details = "; ".join(
            f"{name}: {UNAVAILABLE_OPERATIONS[name]}" for name in dict.fromkeys(unavailable)
        )
        raise ValueError(
            f"Not available in the {VERSION} release; no native job was queued. {details}"
        )
    for op in operations:
        if op["op"] == "loft" and (op.get("mode", "add") != "add" or op.get("new_body", False)):
            raise ValueError(
                "Direct Blend supports solid add into the default body only; cut, surface and new_body are not accepted"
            )


def families() -> dict:
    return {
        "callback_lifecycle": {
            "enabled": True,
            "tool": "creo_callback_status",
            "scope": "Stable resident Blend registration, deployment identity and bounded live readiness",
            "automatic_loading": False,
            "automatic_creo_restart": False,
        },
        "model_reconciliation": {
            "enabled": True,
            "tool": "creo_reconcile_model",
            "actions": ["restore_baseline", "accept_saved", "accept_live", "abandon_new"],
            "scope": "Owned part/sheetmetal models; explicit evidence-bound recovery; assembly/drawing rejected",
            "original_plan_replay": False,
            "inspect_requires_creo": False,
        },
        "model_adoption": {
            "enabled": True,
            "tool": "creo_adopt_current_model",
            "actions": ["inspect", "prepare", "apply"],
            "never_saved_models": "Explicit prepare freezes a verified snapshot; apply confirms it. Later source edits are excluded.",
            "snapshot_evidence_renewal": "inspect(model_id=...) without copying; 600-second tokens",
            "scope": (
                "Explicit managed-copy adoption of the user's current window model; the source "
                "model and its file are never modified; identity from origin path, file sha256 "
                "and live inspection, never display names"
            ),
            "supported": "independent part/sheetmetal, millimeter units, no external dependencies, healthy features",
            "limits": (
                "assembly/drawing, non-millimeter units, dependent or unhealthy models are "
                "refused; each source file adopts at most once; failed adoption resolves via "
                "creo_reconcile_model abandon_new"
            ),
        },
        "file_adoption": {
            "enabled": True,
            "tool": "creo_adopt_file",
            "actions": ["inspect", "apply"],
            "maximum_paths": 20,
            "scope": "Healthy independent millimeter parts/sheetmetal; ordered independent commits; no display/window switching",
            "limits": "Duplicate origins refused; modified/ambiguous residents refused; existing_resident disk/content equality before inspection unknown; unknown stops remainder and preserves protection",
            "evidence_seconds": 600,
            "native_acceptance": "Creo 12.4 developer validation in 0.6.0; WorkBuddy was canceled and was not run",
        },
        "session_models": {
            "enabled": True,
            "tool": "creo_list_session_models",
            "scope": "Read-only session inventory, frozen pagination, unknown fields are null",
            "limit": {"default": 20, "maximum": 50, "page_bytes": 32768},
            "automatic_activation": False,
            "automatic_adoption": False,
        },
        "session_assembly": {
            "enabled": True,
            "tool": "creo_inspect_session_assembly",
            "scope": (
                "Read-only inspection of a resident session assembly by name: "
                "tree-order components with occurrence paths, normalized "
                "millimeter coordinate transforms (row-vector 4x4, translation "
                "last row) with raw matrices and real per-node unit info "
                "(null when unknown), and constraint snapshots; frozen pagination"
            ),
            "limit": {"default": 20, "maximum": 50, "page_bytes": 32768},
            "supported": "resident assemblies selected by name; nested assemblies, repeated instances, suppressed and unresolved components",
            "limits": (
                "no writes: no loading, activation, regeneration, save, adoption "
                "or managed revision; assembly editing/adoption not included"
            ),
        },
        "assembly_replay": {
            "enabled": True,
            "tool": "creo_plan_assembly_rebuild",
            "snapshot_schema_version": 3,
            "supported_constraints": [
                "mate",
                "align",
                "mate_offset",
                "align_offset",
                "insert",
                "csys",
            ],
            "scope": (
                "Read-only planning of a single-level assembly rebuild from a frozen "
                "creo_inspect_session_assembly snapshot: explicit occurrence and "
                "source-reference mappings produce ordered assemble_component then "
                "component_constraints operations for creo_execute_plan"
            ),
            "placement_semantics": (
                "fixed and default placements are replayed as their real placement "
                "operations; a constrained component is inserted fixed and then its "
                "constraints are set; a component without recorded constraints is "
                "frozen at its observed pose and labelled packaged/unconstrained"
            ),
            "binding": (
                "each assemble_component carries the source model, revision and file "
                "sha256; creo_execute_plan and the native executor re-check the binding "
                "before the source is used. The 600-second snapshot window is planning "
                "evidence, not a long-lived write authorization"
            ),
            "limits": (
                "snapshot schema 3, complete single-level assemblies and managed "
                "part/sheetmetal sources only; unknown constraint types, missing, "
                "ambiguous or nested references, older/expired snapshots, changed "
                "sources and plans over the 200-operation limit are refused; no split "
                "transactions, no FEAT-050 comparison, no new constraint types"
            ),
        },
        "disk_open": {
            "enabled": True,
            "tool": "creo_open_file",
            "scope": (
                "Read-only retrieval and display of existing on-disk .prt/.asm models "
                "(explicit or highest numeric version); never saves, erases, renames "
                "or adopts; creates no managed model"
            ),
            "supported": (
                "part, sheetmetal and complete assemblies; retrieval requires no "
                "same-name/same-type session model; assemblies additionally require a "
                "session without parts/assemblies"
            ),
            "limits": (
                "no managed revision and no adoption (use creo_adopt_current_model "
                "afterwards); incomplete assemblies fail with residues reported and "
                "missing components marked unknown; display failures are reported "
                "separately from retrieval"
            ),
        },
        "session_erase": {
            "enabled": True,
            "tool": "creo_erase_session_models",
            "actions": ["inspect", "apply"],
            "scope": (
                "Explicit, evidence-bound erasure of selected session models; the "
                "manifest erases assembly-before-components; nothing is saved and no "
                "disk file is deleted; apply holds one channel lock per job"
            ),
            "supported": (
                "saved (has origin), unmodified, non-managed part/sheetmetal/assembly "
                "session models; targets not referenced outside the manifest and free "
                "of manifest dependency cycles; the current window model may qualify"
            ),
            "limits": (
                "incomplete session enumeration refuses; managed models stay with "
                "creo_reconcile_model; no global/recursive erase, no manifest "
                "widening, mid-manifest failures stop and report without resubmitting"
            ),
        },
        "generation_reclaim": {
            "enabled": True,
            "tool": "creo_reclaim_generations",
            "actions": ["inspect", "apply"],
            "evidence_seconds": 600,
            "scope": (
                "Explicit, evidence-bound reclamation of this project's own loader "
                "and payload generation directories; no Toolkit connection, no DLL "
                "load and no automatic cleanup on startup, upgrade or status queries"
            ),
            "supported": (
                "generation directories explicitly listed by "
                "creo_callback_status.generation_inventory that are provably "
                "unreferenced in every dimension: no current/registered/runtime "
                "reference, definitive local records, consistent deployment record "
                "and flat project-owned content"
            ),
            "limits": (
                "current, registered, runtime-referenced, rollback-retained and "
                "unprovable (missing/corrupt/conflicting records) generations are "
                "kept; paths outside build/blend_loader and build/blend_callback, "
                "links/reparse points, expired evidence, changed content or "
                "references, and occupied files are refused; apply uses the shared "
                "channel lock, is idempotent per key and reports per-item "
                "reclaimed/kept/failed/unknown because deletion is not rolled back"
            ),
        },
        "registry_maintenance": {
            "enabled": True,
            "tools": ["creo_registry_health", "creo_migrate_registry"],
            "scope": (
                "Read-only registry health report (entry sizes, budget usage, "
                "corruption and migration state; 80% warning threshold) plus the "
                "explicit migration that splits legacy inline registry records and "
                "job-evidence manifests into content-addressed detail sidecars"
            ),
            "guarantees": (
                "original bytes are backed up before any rewrite; details persist "
                "before the control record publishes atomically; reruns are "
                "idempotent and interrupted migrations resume; model identity, "
                "revision and history conclusions never change; apply holds the "
                "common nonblocking channel lock and refuses active or unproven owners; "
                "targets are validated owned model_ids, never arbitrary paths"
            ),
            "limits": (
                "the unified 16 MiB read budget is never raised; neither tool "
                "connects Toolkit; migration never deletes files and leaves "
                "oversized raw native results untouched on disk; health, migration "
                "inspect and apply/replay responses use limit/cursor under a whole-response "
                "32 KiB budget, with complete counts and bounded previews"
            ),
        },
        "seed_library": {
            "enabled": True,
            "scope": "MIT native seeds bundled with source; SHA256 validation, local registration and automatic count/mode selection",
            "automatic_pairs": [
                "2/straight",
                "2/smooth",
                "3/straight",
                "3/smooth",
                "4/straight",
                "4/smooth",
                "5/smooth",
                "6/straight",
                "6/smooth",
            ],
            "available_scope": (
                "available means the seed file bytes match the published SHA256; it does not mean "
                "the current Creo session can load this seed"
            ),
            "native_load_probe": (
                "not_performed; listing and validation never connect to Creo and never trial-load "
                "a seed"
            ),
            "compatibility_evidence": (
                "external Creo 9 reported the tested seeds failing with -16; a Creo 10 "
                "three-section success is on record; the current session and the other seeds "
                "are unverified"
            ),
            "production_version": (
                "seed_build_version stays null until a traceable generation record or reliable "
                "native evidence names it for the exact seed SHA256; the UGC header token is "
                "kept as an unverified clue only"
            ),
            "limits": "no automatic download, arbitrary seed generation or mode/count conversion",
        },
        "airfoil": {
            "enabled": True,
            "scope": "symmetric NACA 00xx native sketch splines; chord/thickness/twist/origin/pivot edits preserve sketch and Blend IDs",
            "native_test": "five smooth stations, two sequential middle-section edits and edit after a native group axis pattern; STL section comparison",
            "limits": "no camber; metadata driven MCP edits, not Creo relation-driven airfoil dimensions; creation-time sample count is fixed",
        },
        "sketch_dimensioning": {
            "enabled": True,
            "modes": ["auto", "autodim", "coordinates"],
            "scope": "auto selects native coordinate dimensions on any valid sketch plane for supported undimensioned profiles with at least 10 expanded entities or coordinate/radius magnitude above 1000 mm; coordinates can be requested explicitly",
            "native_test": "19-line large-coordinate profile, R40000 12-gon, large capsule on XY and rotated/translated XZ, large YZ circle and explicit-coordinate rectangle; native sketch/solid IDs, named dimension edits, STL boundaries and save/erase/reload verified",
            "limits": "coordinates supports line/centerline/rectangle/polyline/circle/arc on any valid sketch plane (principal string or dictionary plane), without user dimensions/constraints; input u/v components are named after their dominant native section axis; actual geometry checked to 1e-5 mm when creating/replacing; centerlines are verified as infinite lines (direction and offset) and skewed centerlines carry no endpoint dimensions; spline/ellipse use autodim; no normalization or rigid solving; solid extrude/revolve admission checks multi-loop input for open, branched, self-intersecting, intersecting, tangent, zero-area and near-tolerance contours and rejects only confirmed cases; sketch results report analytic contour/entity counts plus the solved native section counts; the native solver remains authoritative; not proof of every constraint or extreme shape",
        },
        "sketch_geometry_edit": {
            "enabled": True,
            "scope": "in-place geometry replacement; entity names/types/counts and sketch feature ID retained; dimensions rebuilt using auto/autodim/coordinates",
            "native_test": "large 19-line and capsule replacements preserve downstream extrusion IDs, geometry, saved reload; failed dimension assertions roll back and live refresh confirms restoration",
            "limits": "replaces prior dimensions/constraints and clears airfoil metadata; query new named dimension IDs after replacement; spline/ellipse retain the original autodim path; coordinate mode cannot be mixed with user constraints",
        },
        "feature_lifecycle": {
            "enabled": True,
            "tool": "creo_execute_plan",
            "op": "feature_state",
            "actions": ["delete", "suppress", "resume"],
            "scope": (
                "managed part/sheetmetal ordinary sketches, datums, protrusion/revolve and "
                "their cuts, group and pattern headers; explicit label/ID targets with real "
                "before/after status per target"
            ),
            "dependency_rule": (
                "every affected descendant must be listed explicitly; a missing dependency "
                "returns the dependency list and refuses the plan (native re-checks before "
                "executing; no automatic cascade)"
            ),
            "identity": (
                "deleted labels become tombstones and are never rebound; suppression keeps "
                "the feature identity; resume applies only to suppressed targets"
            ),
            "suppression_registry": (
                "intentional suppression is recorded per model/job and participates in health, "
                "saved-reload and rollback comparison; unrecorded suppression stays unhealthy"
            ),
            "limits": (
                "assembly components use remove_component; system-required objects (default "
                "coordinate system and template datums) and individually targeted group/pattern "
                "members are refused; unrecorded or inconsistent suppression is refused; "
                "native acceptance pending"
            ),
        },
        "placement": {
            "enabled": True,
            "scope": "native body FlexMove or quilt/geometry Move, in-place translation/rotation edits, local feature groups, reorder and axis patterns",
            "native_test": "body rotate/translate/edit with true solid bounding boxes; quilt rotate/translate/thicken/edit; five-section blade group pattern and later airfoil edit; save/erase/reload",
            "limits": "body branch can require Flexible Modeling license; copy-original, multiple bodies, custom csys, complex quilts and datum/curve combinations require local validation",
        },
        "drawing": {
            "enabled": True,
            "scope": "native DRW sheets, general/projected views, driving dimensions, notes, tables, edits, deletion and PDF",
            "limits": "owned part/sheetmetal snapshots; no live source update, assembly drawings, sections, detail views, GD&T or automatic BOM",
        },
        "datums": {
            "enabled": True,
            "scope": "coordinate systems and dimensioned point arrays in addition to planes and axes",
            "native_test": "XYZ offsets 10/20/30, Z rotation 45 degrees, native origin check and offset dimension edit",
        },
        "surface_solid": {
            "enabled": True,
            "scope": "planar fill, thicken and solidify",
            "native_test": "20 x 10 fill, symmetric thickness 2 to 3; plane cut of a cube",
            "limits": "closed-quilt solidification, curved-quilt offset/cut and all side options need further validation",
        },
        "boolean_bodies": {
            "enabled": True,
            "native_test": "overlapping cubes: union 1500, difference 500 and intersection 500 mm3",
            "limits": "multi-target/tool lists and keep_tools require further native validation",
        },
        "rib": {
            "enabled": True,
            "scope": "native profile rib driven by an open sketch",
            "limits": "sketch must intersect the solid; material side depends on sketch direction; trajectory ribs are not wrapped",
        },
        "udf": {
            "enabled": True,
            "scope": "local UDF metadata and independent native feature-group placement with reference/variable-dimension mapping",
            "limits": "part/sheetmetal only; exact reference prompts required; assembly UDFs, quadrants, variable parameters and manufacturing UDFs are not wrapped; libraries supplied by user",
        },
        "mirror": {
            "enabled": True,
            "native_test": "whole solid about a principal datum plane",
            "limits": "whole-part/geometry references only; feature/subtree mirror is rejected",
        },
        "sweep": {
            "enabled": True,
            "native_test": "straight and quarter-circle trajectories; solid add, straight cut, open surface followed by thicken, symmetric thin; named section edits, native ID preservation, analytic volume checks, save/erase/reload and failed-assertion rollback on 2026-10-11",
            "limits": "constant section; compound trajectories, all frame options, capped surfaces and intersections still require local validation; thin is total symmetric wall thickness",
        },
        "draft": {
            "enabled": True,
            "native_test": "constant unsplit draft on a planar face with a planar neutral reference",
            "limits": "variable, split and rib draft are not high-level tools",
        },
        "loft": {
            "enabled": True,
            "tool": "creo_loft",
            "scope": "direct native solid Blend from independent MCP-owned XY sketches ordered by increasing Z; create in a feature plan or append to an owned part",
            "interpolation": ["straight", "smooth"],
            "native_test": "3/4/6 straight and smooth factory cases; append 3/smooth to an existing saved base, preserve native IDs, edit dimensions, verify all-section STL, save/erase/reload and failed-append rollback with a live refresh",
            "limits": "solid add into the default body only; no cut/surface/new_body, nonparallel sections or endpoint tangency/curvature controls; native reports support Chinese/English Creo; requires explicit resident callback initialization before modeling under every loader policy, otherwise rejects before DLL load; modeling never loads DLLs or changes security policy",
            "callback_setup": "creo_capabilities.direct_blend_callback lists the generated registry_file; load/start it via Creo Auxiliary Applications and review the DLL prompt before modeling",
        },
        "loft_seed": {
            "enabled": True,
            "tool": "creo_new_loft_part",
            "scope": "new native part by rebinding an automatically selected bundled seed or explicit compatible seed to new XY sketch/airfoil sections",
            "section_count_input_range": [2, 20],
            "seed_section_count_must_match": True,
            "interpolation": ["straight", "smooth"],
            "tested_section_count_mode_pairs": [
                {"section_count": 2, "interpolation": "straight"},
                {"section_count": 2, "interpolation": "smooth"},
                {"section_count": 3, "interpolation": "straight"},
                {"section_count": 3, "interpolation": "smooth"},
                {"section_count": 4, "interpolation": "straight"},
                {"section_count": 4, "interpolation": "smooth"},
                {"section_count": 5, "interpolation": "smooth"},
                {"section_count": 6, "interpolation": "straight"},
                {"section_count": 6, "interpolation": "smooth"},
            ],
            "mode_verification": "requested interpolation must match the saved seed; native PRO_FEAT_INFO checked before save, after parameter edits and after reload",
            "compatibility_evidence": (
                "external Creo 9 reported the tested seeds failing with -16; a Creo 10 "
                "three-section success is on record; the current session and the other seeds "
                "are unverified"
            ),
            "load_failure_diagnosis": (
                "a failed native load keeps the original API, error code and stage plus the seed "
                "identity, SHA256 and the session release; the error alone never names the cause"
            ),
            "native_test": "five-section smooth rectangles and NACA 0012 spline airfoils; middle sketch/plane edits; saved reload, all-section STL checks and failed-assertion rollback; two-section rectangle/circle/triangle regression",
            "limits": "requires a saved solid Blend seed with matching section count and interpolation, Chinese/English Creo; XY sketches with strictly increasing Z offsets; no seed section insertion/removal, mode conversion, cut/surface or tangency controls; use direct loft for existing-target insertion; seed endpoint settings and datums are inherited; input range is not proof that every count/profile is tested; free endpoints may produce identical geometry with two sections",
        },
        "sheetmetal": {
            "enabled": True,
            "scope": "first flat wall, attached flange, unbend, bend-back and flat pattern",
            "native_test": "40 x 30 x 1 wall, 90 degree flange with R2/R3 bend, followed by unfolding and refolding",
            "limits": "first wall uses thin extrusion then native conversion; bend relief, forms, hems and jogs are not high-level tools",
        },
        "assembly": {
            "enabled": True,
            "orientation_input": (
                "XYZ Euler degrees (X then Y then Z), or exclusive nested 3x3 rotation_matrix; "
                "row vectors local to parent, translation separately in mm; finite real numbers, "
                "orthogonality and determinant +1 within 1e-6, without repair or transpose"
            ),
            "matrix_validation": "offline production helper and MCP/schema regression; live placement/save-reload unverified",
            "native_test": "part snapshots, rigid placement, removal, 3 datum-plane align constraints and 20 mm offset",
            "component_changes": (
                "jobs with component operations report a bounded manifest component_changes "
                "summary (also present in detail=compact): committed (real native feature "
                "identities; moved carries queried from/to transforms), rolled_back ONLY "
                "with native rollback_succeeded evidence (requested intents only, never "
                "reported as effective), no_effect (busy rejection/worker not started or "
                "native model_unchanged; nothing attempted or mutated) or unknown_outcome "
                "(empty; failed-after-execution without confirmed rollback, or unconfirmed "
                "outcome; protection retained)"
            ),
            "constraint_names": (
                "list_components constraints keep the numeric SDK type code and add type_name "
                "from the same mapping as inspect_session_assembly; unknown codes stay numeric "
                "with type_name unknown"
            ),
            "pipeline": "single execute_plan job inserts multiple components (distinct labels per occurrence); official rebuild pipeline: docs/ASSEMBLY_REBUILD.md with examples/assembly_rebuild_pipeline.json",
            "limits": "MCP-owned part/sheetmetal sources; no nested assemblies; source edits do not update snapshots (regenerate via remove + re-assemble or rebuild); mate/insert/csys/default placement need further validation",
        },
    }
