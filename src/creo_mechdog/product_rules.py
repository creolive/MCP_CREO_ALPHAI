"""Pure, offline product rules; executable means snapshot admission only."""

from __future__ import annotations

import hashlib
import json
import math

from creo_mechdog.paths import SOURCE_PATHS
from creo_mechdog.schema import validate_operations

_TEMPLATE_PATHS = {"box_frame": "examples/product_rules/box_frame.json"}
_PARAMETER_RULES = {
    "length_mm": (100, 10, 1000),
    "width_mm": (60, 10, 1000),
    "height_mm": (40, 10, 1000),
    "wall_mm": (2, 0.5, 20),
}
_REQUIRED = ("sketch", "extrude")


def _number(value: object, context: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{context}: expected a finite number (not bool or string)")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{context}: number is not representable") from None
    if not math.isfinite(result):
        raise ValueError(f"{context}: expected a finite number")
    return result


def _load_template(template_id: str) -> tuple[dict, str]:
    if not isinstance(template_id, str) or template_id not in _TEMPLATE_PATHS:
        raise ValueError("template_id: unsupported template; expected box_frame")
    try:
        raw = (SOURCE_PATHS.resource_root / _TEMPLATE_PATHS[template_id]).read_bytes()
        template = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"template {template_id}: cannot read valid JSON: {error}") from error
    fixed = {
        "schema_version": 1,
        "template_id": "box_frame",
        "template_version": "1.0.0",
        "units": {"length": "mm", "angle": "deg"},
        "recipe": "open_rectangular_box_v1",
        "operation_allowlist": list(_REQUIRED),
    }
    if not isinstance(template, dict) or set(template) != set(fixed) | {"parameters", "validation"}:
        raise ValueError(f"template {template_id}: unexpected or missing fields")
    if type(template["schema_version"]) is not int:
        raise ValueError("template schema_version: expected integer 1")
    for field, expected in fixed.items():
        if template[field] != expected:
            raise ValueError(f"template {field}: unsupported declaration")
    declarations = template["parameters"]
    if not isinstance(declarations, dict) or set(declarations) != set(_PARAMETER_RULES):
        raise ValueError("template parameters: unexpected or missing fields")
    for name, expected in _PARAMETER_RULES.items():
        declaration = declarations[name]
        if not isinstance(declaration, dict) or set(declaration) != {
            "default",
            "minimum",
            "maximum",
        }:
            raise ValueError(f"template parameters.{name}: invalid declaration")
        actual = tuple(
            _number(declaration[key], f"template parameters.{name}.{key}")
            for key in ("default", "minimum", "maximum")
        )
        if actual != expected:
            raise ValueError(f"template parameters.{name}: unsupported bounds/default")
    validation = template["validation"]
    if not isinstance(validation, dict) or set(validation) != {"minimum_cavity_mm"}:
        raise ValueError("template validation: invalid declaration")
    if _number(validation["minimum_cavity_mm"], "template validation.minimum_cavity_mm") != 1:
        raise ValueError("template validation.minimum_cavity_mm: expected 1 mm")
    return template, hashlib.sha256(raw).hexdigest()


def _blocking_items(snapshot: dict | None) -> list[dict]:
    if snapshot is None:
        return [{"code": "capabilities_unknown", "reason": "No capability_snapshot supplied"}]
    if not isinstance(snapshot, dict):
        raise ValueError("capability_snapshot: expected dict or None")
    if "operations" not in snapshot:
        return [{"code": "capabilities_unknown", "reason": "capability_snapshot.operations absent"}]
    operations = snapshot["operations"]
    if not isinstance(operations, list) or any(not isinstance(op, str) for op in operations):
        raise ValueError("capability_snapshot.operations: expected list[str]")
    return [
        {"code": "missing_capability", "capability": op} for op in _REQUIRED if op not in operations
    ]


def build_product_plan(
    template_id: str, parameters: dict, capability_snapshot: dict | None
) -> dict:
    """Build a bounded plan without submitting work or observing a runtime."""
    template, digest = _load_template(template_id)
    if not isinstance(parameters, dict):
        raise ValueError("parameters: expected dict")
    if any(name not in _PARAMETER_RULES for name in parameters):
        raise ValueError("parameters: unknown parameter field")
    normalized = {}
    for name, declaration in template["parameters"].items():
        value = _number(parameters.get(name, declaration["default"]), f"parameters.{name}")
        if not declaration["minimum"] <= value <= declaration["maximum"]:
            raise ValueError(f"parameters.{name}: outside declared bounds")
        normalized[name] = value
    length, width, height, wall = (normalized[name] for name in _PARAMETER_RULES)
    for name, cavity in (
        ("length_mm", length - 2 * wall),
        ("width_mm", width - 2 * wall),
        ("height_mm", height - wall),
    ):
        if cavity < template["validation"]["minimum_cavity_mm"]:
            raise ValueError(f"parameters.{name}/wall_mm: cavity must be at least 1 mm")
    blocking = _blocking_items(capability_snapshot)

    def rectangle(label, name, offset, minimum, maximum):
        return {
            "op": "sketch",
            "label": label,
            "plane": "XY",
            "offset": offset,
            "dimensioning": "coordinates",
            "entities": [{"type": "rectangle", "name": name, "min": minimum, "max": maximum}],
        }

    operations = validate_operations(
        [
            rectangle("outer_profile", "outer_rect", 0, [0, 0], [length, width]),
            {
                "op": "extrude",
                "label": "outer_body",
                "sketch": "outer_profile",
                "depth": height,
                "depth_type": "blind",
                "mode": "add",
                "direction": "positive",
            },
            rectangle(
                "cavity_profile", "cavity_rect", height, [wall, wall], [length - wall, width - wall]
            ),
            {
                "op": "extrude",
                "label": "cavity_cut",
                "sketch": "cavity_profile",
                "depth": height - wall,
                "depth_type": "blind",
                "mode": "cut",
                "direction": "negative",
            },
        ]
    )
    result = {
        "template_id": template_id,
        "template_version": template["template_version"],
        "template_sha256": digest,
        "normalized_parameters": normalized,
        "required_capabilities": list(_REQUIRED),
        "plan": None if blocking else {"operations": operations},
        "blocking_items": blocking,
        "executable": not blocking,
        "expected_geometry": {
            "volume_mm3": length * width * height
            - (length - 2 * wall) * (width - 2 * wall) * (height - wall),
            "bbox_mm": {"min": [0, 0, 0], "max": [length, width, height]},
        },
        "validation": {"schema": "passed", "native": "not_run", "saved_reload": "not_run"},
    }
    if len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 32768:
        raise ValueError("product plan response exceeds 32768 UTF-8 bytes; no operations returned")
    return result
