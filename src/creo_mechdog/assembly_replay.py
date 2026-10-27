"""Read-only assembly constraint replay planning (DEV-047 T09, FEAT-049).

``creo_plan_assembly_rebuild`` turns a frozen ``creo_inspect_session_assembly``
snapshot plus explicit component/reference mappings into an ordered
``creo_execute_plan`` operation list: every component is inserted first, then the
recorded mate/align/mate_offset/align_offset/insert/csys constraints are set on
the inserted copies.

Planning never loads, activates, adopts or modifies the source assembly or its
components, creates no job or revision, and opens no Toolkit connection. Every
operation that inserts a component carries the source revision and file digest it
was planned against; admission and the native executor re-check that binding
before the source is used. A snapshot is valid as planning evidence for 600
seconds only, and that window is never a long-lived write authorization.
"""

from __future__ import annotations

import copy
import hashlib
import math
import re
import time
from pathlib import Path
from typing import Any

import bridge
from creo_mechdog import model_registry, session_assembly

SNAPSHOT_SCHEMA_VERSION = session_assembly.SNAPSHOT_SCHEMA_VERSION
SNAPSHOT_SECONDS = session_assembly.SNAPSHOT_SECONDS
MAX_OPERATIONS = 200
MAX_CONSTRAINTS_PER_COMPONENT = 20
SUPPORTED_CONSTRAINTS = ("mate", "align", "mate_offset", "align_offset", "insert", "csys")
OFFSET_CONSTRAINTS = ("mate_offset", "align_offset")
SIDES = ("yellow", "red", "none")
LABEL_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,27}$")
MODEL_ID = re.compile(r"^[a-f0-9]{32}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024

PLAN_NOTE = (
    "read-only plan: no component loading, activation, adoption, regeneration, save, "
    "managed revision or Toolkit connection happened here; pass operations to "
    "creo_execute_plan with the target assembly model_id and expected_revision"
)
BINDING_NOTE = (
    "every assemble_component carries rebuild_binding (source model, revision and file "
    "sha256); creo_execute_plan re-reads the registry and file bytes before queueing, and "
    "the native executor re-checks the revision before loading the source"
)
WINDOW_NOTE = (
    "the 600-second snapshot window is planning evidence only, not a long-lived write "
    "authorization; source revision/digest binding is re-verified at submission"
)


def _error(path: str, message: str) -> ValueError:
    return ValueError(f"{path}: {message}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot(snapshot_id: Any) -> tuple[dict, Path]:
    if not isinstance(snapshot_id, str) or not MODEL_ID.fullmatch(snapshot_id):
        raise ValueError(
            "snapshot_id must be the 32 hexadecimal snapshot_id returned by "
            "creo_inspect_session_assembly"
        )
    file = bridge.job_path(snapshot_id) / "session_assembly.json"
    if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError(
            "Assembly snapshot is unavailable; collect a new snapshot with "
            "creo_inspect_session_assembly"
        )
    snapshot = bridge.read_json(file)
    if not isinstance(snapshot, dict):
        raise ValueError("Assembly snapshot does not contain an object; inspect again")
    version = snapshot.get("schema_version")
    if type(version) is not int:
        raise ValueError(
            "Assembly snapshot has no schema_version (older service version) and cannot be "
            "replayed; collect a new snapshot with creo_inspect_session_assembly"
        )
    if version != SNAPSHOT_SCHEMA_VERSION:
        if version < SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                f"Assembly snapshot schema_version {version} is older than the replay "
                f"schema {SNAPSHOT_SCHEMA_VERSION}; it has no reference identity, "
                "direction, offset-unit or replayable evidence - collect a new snapshot"
            )
        raise ValueError(
            f"Assembly snapshot schema_version {version} is newer than this service "
            f"supports ({SNAPSHOT_SCHEMA_VERSION}); update the service or collect a new snapshot"
        )
    created = snapshot.get("created")
    if type(created) not in (int, float) or not math.isfinite(created):
        raise ValueError("Assembly snapshot has no usable creation time; inspect again")
    age = time.time() - created
    if age > SNAPSHOT_SECONDS:
        raise ValueError(
            f"Assembly snapshot expired ({int(age)} s old, limit {SNAPSHOT_SECONDS} s); a "
            "snapshot can only be planned within its window - collect a new snapshot"
        )
    if snapshot.get("complete") is not True or any(
        snapshot.get(key) is True for key in ("incomplete", "truncated", "depth_limited")
    ):
        raise ValueError(
            "Assembly snapshot is incomplete (truncated, depth-limited or a failed query); "
            "its constraint evidence cannot be replayed - fix the session and inspect again"
        )
    components = snapshot.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("Assembly snapshot lists no components; nothing can be rebuilt")
    return snapshot, file


def _component_nodes(snapshot: dict) -> list[dict]:
    nodes = []
    for index, node in enumerate(snapshot["components"]):
        path = f"snapshot.components[{index}]"
        if not isinstance(node, dict):
            raise _error(path, "must be an object")
        occurrence = node.get("occurrence_path")
        if (
            not isinstance(occurrence, list)
            or not occurrence
            or any(type(item) is not int or item < 0 for item in occurrence)
        ):
            raise _error(path, "has no explicit occurrence_path; collect a new snapshot")
        depth = node.get("depth")
        if depth != len(occurrence) - 1:
            raise _error(path, "occurrence_path and depth disagree; collect a new snapshot")
        if depth != 0 or len(occurrence) != 1:
            raise _error(
                path,
                "is a nested component occurrence; only single-level assemblies can be "
                "replayed in this phase (nested replay is refused)",
            )
        kind = node.get("model_type")
        if kind == "assembly":
            raise _error(path, "is a sub-assembly; nested replay is not supported")
        if kind not in ("part", "sheetmetal"):
            raise _error(
                path, f"is not a replayable part/sheetmetal component (model_type={kind!r})"
            )
        if node.get("resolved") is not True:
            raise _error(path, "is unresolved; fix the session before planning")
        if node.get("suppressed") is not False:
            raise _error(path, "is suppressed; suppressed occurrences cannot be replayed")
        label = node.get("occurrence_label")
        if not isinstance(label, str) or not label:
            raise _error(
                path,
                "has no occurrence_label; older snapshots without same-level component "
                "identity cannot be replayed - collect a new snapshot",
            )
        matrix = node.get("transform_to_parent")
        if node.get("transform_mm_known") is not True or matrix is None:
            reason = node.get("transform_unknown_reason")
            raise _error(
                path,
                "has no known millimeter source transform"
                + (f" ({reason})" if reason else "")
                + "; the initial pose cannot be replayed",
            )
        nodes.append(node)
    return nodes


def _pose(matrix: Any, path: str) -> tuple[list[float], list[list[float]]]:
    if (
        not isinstance(matrix, list)
        or len(matrix) != 4
        or any(
            not isinstance(row, list)
            or len(row) != 4
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in row)
            for row in matrix
        )
    ):
        raise _error(path, "source transform must be a finite 4x4 matrix")
    if abs(matrix[3][3] - 1.0) > 1e-9 or any(abs(matrix[index][3]) > 1e-9 for index in range(3)):
        raise _error(path, "source transform must be an affine row-vector matrix")
    rotation = [[float(matrix[row][column]) for column in range(3)] for row in range(3)]
    for left in range(3):
        for right in range(3):
            dot = sum(rotation[left][k] * rotation[right][k] for k in range(3))
            if abs(dot - (1.0 if left == right else 0.0)) > 1e-6:
                raise _error(
                    path,
                    "source transform rotation is not orthonormal within 1e-6; it is not repaired",
                )
    determinant = (
        rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
        - rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
        + rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0])
    )
    if abs(determinant - 1.0) > 1e-6:
        raise _error(path, "source transform determinant must be +1 within 1e-6")
    translation = [float(matrix[3][column]) for column in range(3)]
    return translation, rotation


def _occurrence_key(value: Any, path: str) -> tuple[str, Any]:
    if isinstance(value, list):
        if not value or any(type(item) is not int or not 0 <= item <= 2147483647 for item in value):
            raise _error(
                path,
                "occurrence must be a nonempty occurrence_path of nonnegative integer IDs",
            )
        return "path", tuple(value)
    if isinstance(value, str) and value.strip() and len(value) <= 256:
        return "label", value
    raise _error(
        path,
        "occurrence must be the snapshot occurrence_label or its occurrence_path list",
    )


def _component_mappings(component_mapping: Any, nodes: list[dict]) -> list[tuple[int, dict]]:
    if not isinstance(component_mapping, list):
        raise ValueError("component_mapping must be a list of occurrence mappings")
    by_path = {tuple(node["occurrence_path"]): index for index, node in enumerate(nodes)}
    by_label: dict[str, list[int]] = {}
    for index, node in enumerate(nodes):
        by_label.setdefault(node["occurrence_label"], []).append(index)
    matched: dict[int, dict] = {}
    for position, raw in enumerate(component_mapping):
        path = f"component_mapping[{position}]"
        if not isinstance(raw, dict):
            raise _error(path, "must be an object")
        unknown = set(raw) - {"occurrence", "label", "source_model_id"}
        if unknown:
            raise _error(path, f"unknown fields: {sorted(unknown)}")
        for key in ("occurrence", "label", "source_model_id"):
            if key not in raw:
                raise _error(path, f"missing required field '{key}'")
        kind, key = _occurrence_key(raw["occurrence"], f"{path}.occurrence")
        if kind == "path":
            index = by_path.get(key)
            if index is None:
                raise _error(
                    path,
                    f"occurrence_path {list(key)} does not match any snapshot component",
                )
        else:
            candidates = by_label.get(key, [])
            if not candidates:
                raise _error(path, f"occurrence '{key}' does not match any snapshot component")
            if len(candidates) > 1:
                paths = [nodes[index]["occurrence_path"] for index in candidates]
                raise _error(
                    path,
                    f"occurrence label '{key}' is ambiguous ({paths}); pass occurrence_path",
                )
            index = candidates[0]
        if index in matched:
            raise _error(path, "maps an occurrence that another entry already maps")
        label = raw["label"]
        if not isinstance(label, str) or not LABEL_PATTERN.fullmatch(label):
            raise _error(
                path,
                "label must start with a lowercase letter, contain only [a-z0-9_] and be at "
                "most 28 characters",
            )
        source = raw["source_model_id"]
        if not isinstance(source, str) or not MODEL_ID.fullmatch(source):
            raise _error(path, "source_model_id must be 32 lowercase hexadecimal characters")
        matched[index] = {"label": label, "source_model_id": source, "position": position}
    missing = [node["occurrence_label"] for index, node in enumerate(nodes) if index not in matched]
    if missing:
        raise ValueError(
            "component_mapping is incomplete; every snapshot occurrence needs a target "
            f"component and source model: missing {missing}"
        )
    labels = [entry["label"] for entry in matched.values()]
    if len(labels) != len(set(labels)):
        duplicates = sorted({label for label in labels if labels.count(label) > 1})
        raise ValueError(f"component_mapping target labels must be unique: duplicates {duplicates}")
    return [(index, matched[index]) for index in sorted(matched)]


def _source_binding(source_model_id: str, path: str) -> dict:
    root = bridge.ROOT / "models" / source_model_id
    if root.is_symlink() or root.is_junction():
        raise _error(path, "source model directory cannot be a link")
    model = model_registry.read_control(root)
    kind = model.get("model_type")
    if kind not in ("part", "sheetmetal"):
        raise _error(
            path,
            f"source model is {kind!r}; only owned part/sheetmetal models can be replayed",
        )
    if model.get("status") != "ready" or model.get("pending_job") or model.get("recovery_pending"):
        raise _error(path, "source model is not ready (pending or unknown job); inspect it first")
    revision = model.get("revision")
    if type(revision) is not int or revision < 1:
        raise _error(path, "source model has no saved revision to bind")
    part_file = model.get("part_file")
    digest = model.get("part_sha256")
    if not isinstance(part_file, str) or not part_file:
        raise _error(path, "source model has no verified saved native file")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise _error(path, "source model has no recorded file digest")
    file = Path(part_file)
    expected_directory = (root / "output").resolve()
    if file.is_symlink() or not file.is_file() or file.parent.resolve() != expected_directory:
        raise _error(path, "source model saved file is missing or outside its owned output")
    actual = _sha256(file)
    if actual != digest:
        raise _error(
            path,
            "source file bytes changed on disk after it was registered; inspect the model "
            "before planning",
        )
    return {
        "source_model_id": source_model_id,
        "source_model_name": model.get("model_name"),
        "source_revision": revision,
        "source_part_sha256": digest,
        "source_part_file": part_file,
    }


def _reference_entries(reference_mapping: Any) -> dict[tuple, list[dict]]:
    if not isinstance(reference_mapping, list):
        raise ValueError("reference_mapping must be a list of source-to-target references")
    entries: dict[tuple, list[dict]] = {}
    seen: set[tuple] = set()
    for position, raw in enumerate(reference_mapping):
        path = f"reference_mapping[{position}]"
        if not isinstance(raw, dict):
            raise _error(path, "must be an object")
        unknown = set(raw) - {"source", "target", "target_component", "target_side"}
        if unknown:
            raise _error(path, f"unknown fields: {sorted(unknown)}")
        source = raw.get("source")
        if not isinstance(source, dict):
            raise _error(path, "requires a source reference object")
        source_unknown = set(source) - {"component", "item_type", "item_id", "side"}
        if source_unknown:
            raise _error(path, f"unknown source fields: {sorted(source_unknown)}")
        item_type = source.get("item_type")
        item_id = source.get("item_id")
        if type(item_type) is not int or type(item_id) is not int:
            raise _error(path, "source requires integer item_type and item_id from the snapshot")
        component = source.get("component")
        if component is not None and (not isinstance(component, str) or not component):
            raise _error(path, "source.component must be an occurrence label or null")
        side = source.get("side")
        if side is not None and side not in SIDES:
            raise _error(path, f"source.side must be one of {list(SIDES)}")
        target = raw.get("target")
        if not isinstance(target, dict) or not isinstance(target.get("kind"), str):
            raise _error(path, "target must be an execute_plan reference object with kind")
        target_component = raw.get("target_component")
        if target_component is not None and (
            not isinstance(target_component, str) or not target_component
        ):
            raise _error(path, "target_component must be a target component label or null")
        target_side = raw.get("target_side")
        if target_side is not None and target_side not in SIDES:
            raise _error(path, f"target_side must be one of {list(SIDES)}")
        key = (component, item_type, item_id)
        if (key, side) in seen:
            raise _error(path, "duplicates another source reference mapping")
        seen.add((key, side))
        entries.setdefault(key, []).append(
            {
                "component": component,
                "item_type": item_type,
                "item_id": item_id,
                "side": side,
                "target": copy.deepcopy(target),
                "target_component": target_component,
                "target_side": target_side,
                "position": position,
            }
        )
    return entries


def _lookup(entries: dict[tuple, list[dict]], reference: dict, side: str, path: str) -> dict:
    key = (reference["component"], reference["item_type"], reference["item_id"])
    candidates = entries.get(key, [])
    matches = [entry for entry in candidates if entry["side"] in (None, side)]
    if not matches:
        scope = "root" if reference["component"] is None else f"sibling '{reference['component']}'"
        raise _error(
            path,
            f"reference_mapping has no entry for the {scope} reference "
            f"(item_type={reference['item_type']}, item_id={reference['item_id']}, side={side})",
        )
    if len(matches) > 1:
        raise _error(
            path,
            "reference_mapping has several entries for the same source reference "
            f"(item_type={reference['item_type']}, item_id={reference['item_id']}); add side or "
            "remove the duplicate",
        )
    return matches[0]


def _reference(reference: Any, path: str) -> dict:
    if not isinstance(reference, dict):
        raise _error(path, "snapshot reference is missing")
    scope = reference.get("owner_scope")
    if scope == "nested":
        raise _error(path, "points into a nested occurrence; nested replay is refused")
    if scope not in ("assembly", "component"):
        raise _error(path, f"has no identifiable occurrence scope ({scope!r})")
    item_type = reference.get("item_type")
    item_id = reference.get("item_id")
    if reference.get("item_query_code") not in (0, None):
        raise _error(path, "geometry identity query failed in the snapshot")
    if type(item_type) is not int or type(item_id) is not int:
        raise _error(path, "has no explicit item_type/item_id identity")
    component = None
    if scope == "component":
        component = reference.get("occurrence_label")
        if not isinstance(component, str) or not component:
            raise _error(path, "has no same-level component occurrence_label")
    return {
        "component": component,
        "item_type": item_type,
        "item_id": item_id,
        "scope": scope,
    }


def _placement(node: dict, path: str) -> tuple[str, str, list[dict]]:
    constraints = node.get("constraints")
    if not isinstance(constraints, list):
        raise _error(path, "snapshot constraints are not a list; collect a new snapshot")
    if len(constraints) > MAX_CONSTRAINTS_PER_COMPONENT:
        raise _error(
            path,
            f"has {len(constraints)} constraints; at most {MAX_CONSTRAINTS_PER_COMPONENT} "
            "are accepted per component plan",
        )
    if not constraints:
        # No recorded constraint: freeze the observed pose explicitly. This is a
        # real placement state, never a stand-in for a constraint we failed to
        # replay (unreplayable constraints are refused above/below).
        return "fixed", "packaged" if node.get("packaged") is True else "unconstrained", []
    placement_rows = [
        row
        for row in constraints
        if isinstance(row, dict) and row.get("placement_kind") in ("fixed", "default")
    ]
    remaining = [row for row in constraints if row not in placement_rows]
    automatic = [
        row for row in constraints if isinstance(row, dict) and row.get("placement_kind") == "auto"
    ]
    if automatic:
        raise _error(path, "contains an automatic placement constraint, which cannot be replayed")
    if placement_rows:
        if remaining:
            raise _error(
                path,
                "mixes a fixed/default placement with other constraints; replaying it would "
                "silently change the source placement",
            )
        if len(placement_rows) > 1:
            raise _error(path, "records more than one fixed/default placement")
        kind = placement_rows[0]["placement_kind"]
        return kind, kind, []
    for index, row in enumerate(constraints):
        item_path = f"{path}.constraints[{index}]"
        if not isinstance(row, dict):
            raise _error(item_path, "must be an object")
        ctype = row.get("type")
        if ctype not in SUPPORTED_CONSTRAINTS:
            raise _error(
                item_path,
                f"unsupported constraint type {ctype!r}; this phase replays only "
                f"{list(SUPPORTED_CONSTRAINTS)}",
            )
        if row.get("replayable") is not True:
            reason = row.get("reason") or "unknown"
            raise _error(item_path, f"constraint is not replayable ({reason})")
    return "constraints", "constraints", list(constraints)


def _constraint_operations(
    node: dict,
    target: str,
    target_labels: dict[str, str],
    entries: dict[tuple, list[dict]],
    node_index: int,
) -> list[dict]:
    target_names = set(target_labels.values())
    operations = []
    constraints: list[dict] = []
    for position, row in enumerate(node["constraints"]):
        path = f"snapshot.components[{node_index}].constraints[{position}]"
        ctype = row["type"]
        assembly_reference = _reference(row.get("asm_reference"), f"{path}.asm_reference")
        component_reference = _reference(row.get("comp_reference"), f"{path}.comp_reference")
        assembly_side = row.get("asm_side")
        component_side = row.get("comp_side")
        if assembly_side not in SIDES or component_side not in SIDES:
            raise _error(
                path,
                "snapshot does not carry both datum directions; collect a new snapshot",
            )
        assembly_entry = _lookup(
            entries, assembly_reference, assembly_side, f"{path}.asm_reference"
        )
        component_entry = _lookup(
            entries, component_reference, component_side, f"{path}.comp_reference"
        )
        assembly_component = assembly_entry["target_component"]
        owner = assembly_reference["component"]
        if owner is not None:
            if assembly_component is None:
                assembly_component = target_labels.get(owner)
            if assembly_component not in target_names:
                raise _error(
                    f"reference_mapping[{assembly_entry['position']}].target_component",
                    f"must name a planned target component; source sibling '{owner}' maps to "
                    f"'{target_labels.get(owner)}'",
                )
        if component_entry["target_component"] is not None:
            raise _error(
                f"reference_mapping[{component_entry['position']}].target_component",
                "is not allowed on a component-side reference; it is always resolved inside "
                "the component being constrained",
            )
        if ctype in OFFSET_CONSTRAINTS:
            offset = row.get("offset_mm")
            if type(offset) not in (int, float) or not math.isfinite(offset):
                raise _error(
                    path,
                    "offset is not convertible to millimeters (unknown assembly length unit); "
                    "collect a snapshot with a known unit",
                )
            offset = float(offset)
        else:
            offset = 0.0
        constraint = {
            "type": ctype,
            "assembly_reference": copy.deepcopy(assembly_entry["target"]),
            "component_reference": copy.deepcopy(component_entry["target"]),
            "offset": offset,
            "assembly_side": assembly_entry["target_side"] or assembly_side,
            "component_side": component_entry["target_side"] or component_side,
        }
        if assembly_component is not None:
            constraint["assembly_component"] = assembly_component
        constraints.append(constraint)
    # One component_constraints operation per component: the native setter
    # replaces the component's whole constraint set, so per-constraint
    # operations would silently drop every constraint but the last.
    if constraints:
        operations.append(
            {"op": "component_constraints", "component": target, "constraints": constraints}
        )
    return operations


def plan_assembly_rebuild(
    snapshot_id: str,
    component_mapping: list[dict],
    reference_mapping: list[dict],
) -> dict:
    """Plan an ordered insert-then-constrain rebuild from a frozen snapshot."""
    snapshot, _ = _snapshot(snapshot_id)
    nodes = _component_nodes(snapshot)
    mapped = _component_mappings(component_mapping, nodes)
    entries = _reference_entries(reference_mapping)
    target_labels = {nodes[index]["occurrence_label"]: entry["label"] for index, entry in mapped}

    bindings = []
    bindings_by_source: dict[str, dict] = {}
    placements = []
    insert_operations = []
    constraint_operations: list[dict] = []
    for node_index, entry in mapped:
        node = nodes[node_index]
        target = entry["label"]
        path = f"component_mapping[{entry['position']}]"
        source = entry["source_model_id"]
        if source not in bindings_by_source:
            bindings_by_source[source] = _source_binding(source, path)
            bindings.append(bindings_by_source[source])
        binding = bindings_by_source[source]
        translation, rotation = _pose(
            node["transform_to_parent"], f"snapshot.components[{node_index}]"
        )
        mode, source_placement, constraints = _placement(node, path)
        insertion = "fixed" if mode in ("fixed", "constraints") else "default"
        insert_operations.append(
            {
                "op": "assemble_component",
                "label": target,
                "source_model_id": source,
                "translation": translation,
                "rotation_matrix": rotation,
                "placement": insertion,
                "constraints": [],
                "rebuild_binding": {
                    **binding,
                    "occurrence": node["occurrence_label"],
                    "occurrence_path": list(node["occurrence_path"]),
                    "target_label": target,
                },
            }
        )
        constraint_index = None
        if constraints:
            constraint_index = len(mapped) + len(constraint_operations)
            constraint_operations.extend(
                _constraint_operations(node, target, target_labels, entries, node_index)
            )
        placements.append(
            {
                "occurrence": node["occurrence_label"],
                "occurrence_path": list(node["occurrence_path"]),
                "target_label": target,
                "mode": mode,
                "source_placement": source_placement,
                "constraint_count": len(constraints),
                "intermediate_placement": insertion if mode == "constraints" else None,
                "insert_operation_index": len(insert_operations) - 1,
                "constraint_operation_index": constraint_index,
            }
        )

    operations = insert_operations + constraint_operations
    if len(operations) > MAX_OPERATIONS:
        raise ValueError(
            f"the plan needs {len(operations)} operations; creo_execute_plan supports at most "
            f"{MAX_OPERATIONS}. It is refused instead of being split into several transactions"
        )

    created = snapshot["created"]
    age = max(0, int(time.time() - created))
    return {
        "read_only": True,
        "snapshot": {
            "snapshot_id": snapshot_id,
            "schema_version": snapshot.get("schema_version"),
            "assembly": snapshot.get("assembly"),
            "created": created,
            "checked_at": snapshot.get("checked_at"),
            "age_seconds": age,
            "expires_in_seconds": max(0, SNAPSHOT_SECONDS - age),
            "complete": snapshot.get("complete"),
            "session_fingerprint": snapshot.get("session_fingerprint"),
        },
        "operations": operations,
        "operation_count": len(operations),
        "max_operations": MAX_OPERATIONS,
        "source_bindings": bindings,
        "placements": placements,
        "supported_constraints": list(SUPPORTED_CONSTRAINTS),
        "offset_unit": "snapshot assembly length unit converted to millimeters (offset_mm)",
        "directions": "asm_side/comp_side and target_side are preserved per reference",
        "planning_window_seconds": SNAPSHOT_SECONDS,
        "plan_note": PLAN_NOTE,
        "binding_note": BINDING_NOTE,
        "window_note": WINDOW_NOTE,
    }


def validate_source_bindings(operations: list[dict], models_root: Path | None = None) -> None:
    """Re-check every replay source binding before a job is queued.

    Runs inside the caller's Toolkit channel lock, so the registry revision and
    the file digest read here cannot race another admitted MCP write.
    """
    root = Path(models_root) if models_root is not None else bridge.ROOT / "models"
    for index, operation in enumerate(operations):
        binding = operation.get("rebuild_binding")
        if binding is None:
            continue
        path = f"operations[{index}].rebuild_binding"
        if operation.get("op") != "assemble_component":
            raise _error(path, "is only accepted on assemble_component")
        if not isinstance(binding, dict):
            raise _error(path, "must be an object")
        source = operation.get("source_model_id")
        if binding.get("source_model_id") != source:
            raise _error(path, "source_model_id does not match the operation")
        revision = binding.get("source_revision")
        digest = binding.get("source_part_sha256")
        if type(revision) is not int or revision < 1:
            raise _error(path, "source_revision must be a positive integer")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise _error(path, "source_part_sha256 must be a 64-character lowercase digest")
        if not isinstance(source, str) or not MODEL_ID.fullmatch(source):
            raise _error(f"operations[{index}].source_model_id", "is not a managed model id")
        directory = root / source
        if directory.is_symlink() or directory.is_junction():
            raise _error(path, "source model directory cannot be a link")
        model = model_registry.read_control(directory)
        if (
            model.get("status") != "ready"
            or model.get("pending_job")
            or model.get("recovery_pending")
        ):
            raise _error(path, "source model is no longer ready; inspect it before replay")
        if model.get("revision") != revision:
            raise _error(
                path,
                f"source revision changed after planning (bound {revision}, current "
                f"{model.get('revision')}); collect a new snapshot and plan again",
            )
        if model.get("part_sha256") != digest:
            raise _error(
                path,
                "source file digest changed after planning; collect a new snapshot and plan again",
            )
        part_file = model.get("part_file")
        if not isinstance(part_file, str) or not part_file:
            raise _error(path, "source model has no verified saved native file")
        file = Path(part_file)
        if (
            file.is_symlink()
            or not file.is_file()
            or file.parent.resolve() != (directory / "output").resolve()
        ):
            raise _error(path, "source model saved file is missing or outside its owned output")
        if _sha256(file) != digest:
            raise _error(
                path,
                "source file bytes changed on disk after planning; inspect the model before "
                "replaying",
            )
