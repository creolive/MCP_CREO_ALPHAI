"""Part feature lifecycle admission, registries and result projection (T08).

``creo_execute_plan`` gains ``op="feature_state"`` with ``action`` of
``delete``/``suppress``/``resume`` and explicit ``targets`` (feature labels or
nonnegative native feature IDs). This module owns the Python half of the
double check: it resolves every target against the saved inspection, refuses
system objects and grouped members, requires every affected dependency to be
listed explicitly, and keeps the deleted-label tombstones and the intentional
suppression registry consistent with the saved inspection.

Nothing here invents geometry facts: the native executor re-checks the same
rules against the live model before it calls Toolkit, and every recorded
registry value must match an actually observed feature status.
"""

from __future__ import annotations

import re
from typing import Any

LABEL_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,27}$")
ACTIONS = ("delete", "suppress", "resume")
TOMBSTONES = "feature_tombstones"
SUPPRESSED = "suppressed_features"

# Native ProFeatStatus values used by the saved inspection.
ACTIVE = 0
SUPPRESSED_STATUS = 5
# Native ProGroupStatus / ProPatternStatus / ProGrppatternStatus values.
GROUP_MEMBER = 1
PATTERN_MEMBER = 2
GRPPATTERN_MEMBER = 2

MAX_TARGETS = 100


def _error(path: str, message: str) -> ValueError:
    return ValueError(f"{path}: {message}")


def normalize_target(value: Any, path: str) -> str | int:
    """Return a canonical target: a validated label or a native feature ID."""
    # Digit-only strings are stringified integer targets elsewhere in the
    # public contract (BUG-073); labels cannot start with a digit.
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        value = int(value)
    if type(value) is int:
        if not 0 <= value <= 2147483647:
            raise _error(path, "feature ID targets must be nonnegative 32-bit integers")
        return value
    if isinstance(value, str):
        if not LABEL_PATTERN.fullmatch(value):
            raise _error(
                path,
                "feature label targets must start with a lowercase letter, contain only "
                "[a-z0-9_] and be at most 28 characters; or pass a nonnegative feature ID",
            )
        return value
    raise _error(path, "each target must be a feature label or a nonnegative feature ID")


def target_key(target: str | int) -> str:
    return f"label:{target}" if isinstance(target, str) else f"id:{target}"


def _registry(model: dict | None, key: str) -> dict[str, dict]:
    value = (model or {}).get(key)
    return value if isinstance(value, dict) else {}


def tombstones_of(model: dict | None) -> dict[str, dict]:
    return _registry(model, TOMBSTONES)


def suppressed_of(model: dict | None) -> dict[str, dict]:
    return _registry(model, SUPPRESSED)


def tombstone_labels(model: dict | None) -> set[str]:
    labels = set(tombstones_of(model))
    for entry in tombstones_of(model).values():
        label = entry.get("label") if isinstance(entry, dict) else None
        if isinstance(label, str):
            labels.add(label)
    return labels


def _tombstone_ids(model: dict | None) -> set[int]:
    ids = set()
    for entry in tombstones_of(model).values():
        if isinstance(entry, dict) and type(entry.get("feature_id")) is int:
            ids.add(entry["feature_id"])
    return ids


def _features(model: dict | None) -> list[dict] | None:
    if not model:
        return None
    ref = model.get("inspection_ref")
    source = model.get("inspection")
    if ref is not None:
        from creo_mechdog.inspection_refs import full_inspection

        try:
            source = full_inspection(model)
        except Exception:  # noqa: BLE001 - a stale reference is reported by admission
            return None
    features = source.get("features") if isinstance(source, dict) else None
    return features if isinstance(features, list) else None


def _aliases(model: dict | None) -> dict[str, dict]:
    if not model:
        return {}
    from creo_mechdog.model_registry import aliases_of

    try:
        return aliases_of(model)
    except (OSError, ValueError):
        return {}


def _feature_by_id(features: list[dict], feature_id: int) -> dict | None:
    for feature in features:
        if feature.get("id") == feature_id:
            return feature
    return None


def _find_label(model: dict | None, features: list[dict], label: str) -> int | None:
    entry = _aliases(model).get(label)
    if isinstance(entry, dict) and type(entry.get("feature_id")) is int:
        return entry["feature_id"]
    for key, value in _aliases(model).items():
        if key.lower() == label.lower() and isinstance(value, dict):
            if type(value.get("feature_id")) is int:
                return value["feature_id"]
    return None


def _feature_label(model: dict | None, feature_id: int) -> str | None:
    for label, entry in _aliases(model).items():
        if isinstance(entry, dict) and entry.get("feature_id") == feature_id:
            return label
    return None


def _is_member(feature: dict) -> str | None:
    if feature.get("group_status") == GROUP_MEMBER:
        return "group member"
    if feature.get("pattern_status") == PATTERN_MEMBER:
        return "pattern member"
    if feature.get("grppattern_status") == GRPPATTERN_MEMBER:
        return "group pattern member"
    return None


def _is_grouped_child(feature: dict) -> bool:
    """Members follow their header and cannot be listed as independent targets."""
    return _is_member(feature) is not None


def _dependencies(feature: dict) -> list[int]:
    value = feature.get("child_ids")
    if not isinstance(value, list):
        return []
    return [item for item in value if type(item) is int]


def _parents(feature: dict) -> list[int]:
    value = feature.get("parent_ids")
    if not isinstance(value, list):
        return []
    return [item for item in value if type(item) is int]


def _describe(model: dict | None, features: list[dict], ids: list[int]) -> list[dict]:
    described = []
    for feature_id in ids:
        feature = _feature_by_id(features, feature_id)
        described.append(
            {
                "feature_id": feature_id,
                "label": _feature_label(model, feature_id),
                "name": feature.get("name") if feature else None,
                "type_name": feature.get("type_name") if feature else None,
                "status": feature.get("status") if feature else None,
            }
        )
    return described


def registry_issues(model: dict | None) -> list[str]:
    """Report intentional-suppression entries that the saved model contradicts."""
    features = _features(model)
    if features is None:
        return []
    by_id = {feature.get("id"): feature for feature in features}
    recorded = {}
    issues = []
    for key, entry in suppressed_of(model).items():
        feature_id = entry.get("feature_id") if isinstance(entry, dict) else None
        if type(feature_id) is not int:
            issues.append(f"suppression registry entry {key!r} has no feature ID")
            continue
        recorded[feature_id] = key
        feature = by_id.get(feature_id)
        if feature is None:
            issues.append(
                f"recorded suppressed feature {feature_id} ({key}) is absent from the saved model"
            )
        elif feature.get("status") != SUPPRESSED_STATUS:
            issues.append(
                f"recorded suppressed feature {feature_id} ({key}) has status "
                f"{feature.get('status')}, not suppressed"
            )
    for feature in features:
        feature_id = feature.get("id")
        if feature.get("status") == SUPPRESSED_STATUS and feature_id not in recorded:
            issues.append(f"feature {feature_id} is suppressed but not recorded as intentional")
    return issues


def _resolve_target(
    model: dict | None,
    features: list[dict],
    target: str | int,
    path: str,
) -> dict:
    tombstones = tombstones_of(model)
    if isinstance(target, str):
        if target in tombstone_labels(model):
            entry = tombstones.get(target, {})
            raise _error(
                path,
                f"label {target!r} is a tombstone of deleted feature "
                f"{entry.get('feature_id')}; deleted labels cannot be reused or referenced",
            )
        feature_id = _find_label(model, features, target)
        if feature_id is None:
            raise _error(path, f"unknown feature label {target!r}")
    else:
        feature_id = target
        if feature_id in _tombstone_ids(model):
            raise _error(
                path, f"feature {feature_id} was deleted; deleted targets cannot be reused"
            )
    feature = _feature_by_id(features, feature_id)
    if feature is None:
        raise _error(
            path,
            f"feature {feature_id} is absent from the saved model inspection; "
            "re-inspect the model before changing its feature state",
        )
    return {"target": target, "feature_id": feature_id, "feature": feature}


def _validate_target_rules(
    model: dict | None,
    resolved: dict,
    action: str,
    features: list[dict],
    path: str,
) -> None:
    feature = resolved["feature"]
    feature_id = resolved["feature_id"]
    status = feature.get("status")
    if feature.get("system_required") is True:
        raise _error(
            path,
            f"feature {feature_id} is a system-required object (default coordinate system or "
            "template datum) and cannot be deleted, suppressed or resumed",
        )
    member = _is_member(feature)
    if member:
        raise _error(
            path,
            f"feature {feature_id} is a {member}; operate on its group/pattern header instead "
            "of an individual member",
        )
    if feature.get("incomplete") is True:
        raise _error(path, f"feature {feature_id} is incomplete and cannot be changed")
    if action == "resume":
        if status != SUPPRESSED_STATUS:
            raise _error(
                path,
                f"feature {feature_id} is not suppressed (status {status}); resume only applies "
                "to suppressed features",
            )
    elif action == "suppress":
        if status == SUPPRESSED_STATUS:
            raise _error(path, f"feature {feature_id} is already suppressed")
    elif action == "delete":
        # Deleting a suppressed feature is allowed; its tombstone replaces the
        # suppression entry. Deleting an already deleted feature is refused
        # above by the tombstone check.
        pass


def _check_dependencies(
    model: dict | None,
    action: str,
    resolved: list[dict],
    features: list[dict],
    path: str,
) -> None:
    targets = {item["feature_id"]: item["feature"] for item in resolved}
    if action in ("delete", "suppress"):
        missing: set[int] = set()
        for feature_id, feature in targets.items():
            pending = list(_dependencies(feature))
            seen = {feature_id}
            while pending:
                child_id = pending.pop()
                if child_id in seen:
                    continue
                seen.add(child_id)
                child = _feature_by_id(features, child_id)
                if child is None:
                    continue
                # A grouped member follows its header and cannot be an
                # independent target; the header operation covers it.
                if _is_grouped_child(child):
                    continue
                if child_id not in targets:
                    missing.add(child_id)
                pending.extend(_dependencies(child))
        if missing:
            ordered = sorted(missing)
            raise _error(
                path,
                f"delete/suppress targets do not cover every affected dependency; "
                f"list these feature IDs explicitly (no automatic cascade): "
                f"{_describe(model, features, ordered)}",
            )
    elif action == "resume":
        missing = set()
        for feature_id, feature in targets.items():
            for parent_id in _parents(feature):
                parent = _feature_by_id(features, parent_id)
                if parent is None or parent.get("status") != SUPPRESSED_STATUS:
                    continue
                if parent_id not in targets:
                    missing.add(parent_id)
        if missing:
            ordered = sorted(missing)
            raise _error(
                path,
                "resume targets require their suppressed parents to be resumed in the same "
                f"request; list these feature IDs explicitly: {_describe(model, features, ordered)}",
            )


def validate_plan(model: dict | None, operations: list[dict]) -> None:
    """Admission for every ``feature_state`` input in one plan.

    Called before a job exists: a refusal creates no job and no model change.
    """
    feature_ops = [
        (index, operation)
        for index, operation in enumerate(operations)
        if operation.get("op") == "feature_state"
    ]
    if not feature_ops:
        return
    if model is None:
        raise ValueError("feature_state requires an existing managed model")
    model_type = (model or {}).get("model_type", "part")
    if model_type not in ("part", "sheetmetal"):
        raise ValueError(
            "feature_state supports managed part/sheetmetal models only; assembly components "
            "are changed with remove_component and drawings are out of scope"
        )
    features = _features(model)
    if features is None:
        raise ValueError(
            "feature_state requires the model's saved inspection with dependency evidence; "
            "no inspection is available for this model"
        )
    issues = registry_issues(model)
    if issues:
        raise ValueError(
            "feature_state refused: the recorded intentional suppression set does not match "
            f"the saved model ({'; '.join(issues)})"
        )
    for index, operation in feature_ops:
        path = f"operations[{index}]"
        action = operation.get("action")
        if action not in ACTIONS:
            raise _error(path, f"action must be one of {', '.join(ACTIONS)}")
        targets = operation.get("targets")
        if not isinstance(targets, list) or not targets:
            raise _error(path, "feature_state requires at least one explicit target")
        if len(targets) > MAX_TARGETS:
            raise _error(path, f"feature_state supports at most {MAX_TARGETS} targets")
        seen = set()
        resolved = []
        for position, raw in enumerate(targets):
            target = normalize_target(raw, f"{path}.targets[{position}]")
            key = target_key(target)
            if key in seen:
                raise _error(path, f"duplicate target {target!r}")
            seen.add(key)
            resolved.append(_resolve_target(model, features, target, f"{path}.targets[{position}]"))
        for item in resolved:
            _validate_target_rules(model, item, action, features, path)
        _check_dependencies(model, action, resolved, features, path)


REFERENCE_KINDS = {
    "feature",
    "datum_feature",
    "datum_axis_feature",
    "sketch_curves",
    "quilt_feature",
    "datum_csys_feature",
    "datum_point_feature",
}


def reject_tombstoned_labels(model: dict | None, operations: list[dict]) -> None:
    """A deleted label must never be bound to a new feature or reference."""
    reserved = tombstone_labels(model)
    if not reserved:
        return
    for index, operation in enumerate(operations):
        label = operation.get("label")
        if isinstance(label, str) and label in reserved:
            raise ValueError(
                f"operations[{index}].label: {label!r} is a tombstone of a deleted feature; "
                "deleted labels cannot be reused for new features"
            )

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                reference = value.get("label")
                if value.get("kind") in REFERENCE_KINDS and reference in reserved:
                    raise ValueError(
                        f"operations[{index}]: {reference!r} is a tombstone of a deleted "
                        "feature and cannot be referenced"
                    )
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(operation)


def registry_payload(model: dict | None, result: dict) -> dict[str, dict]:
    """Validate the native registry output before it is persisted on the model."""
    tombstones = result.get(TOMBSTONES, tombstones_of(model))
    suppressed = result.get(SUPPRESSED, suppressed_of(model))
    for key, value in ((TOMBSTONES, tombstones), (SUPPRESSED, suppressed)):
        if not isinstance(value, dict):
            raise ValueError(f"Native feature_state result returned a malformed {key}")
        for name, entry in value.items():
            if not isinstance(entry, dict) or type(entry.get("feature_id")) is not int:
                raise ValueError(f"Native feature_state result has an invalid {key} entry {name!r}")
    return {TOMBSTONES: tombstones, SUPPRESSED: suppressed}


def apply_result(model: dict, result: dict) -> None:
    """Persist the native registries on the model control record."""
    if TOMBSTONES not in result and SUPPRESSED not in result:
        return
    for key, value in registry_payload(model, result).items():
        model[key] = value


def project_operation(operation: dict, targets: list[Any]) -> None:
    """Keep the per-target detail inside the single input's own result.

    T02 requires one terminal record per input; the target list is a
    specialized field of that record, never extra result records. Missing
    native detail stays missing instead of being synthesized.
    """
    detail = operation.get("targets")
    if not isinstance(detail, list):
        return
    operation["target_count"] = len(detail)
    operation["requested_target_count"] = len(targets)
    operation["targets_complete"] = len(detail) == len(targets)
