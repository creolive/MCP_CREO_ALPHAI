"""Run an example plan file against the session.

An example is a JSON file with one or more phases::

    {
      "phases": [
        {"operations": [{"op": "sketch", "label": "profile", ...}]},
        {"operations": [{"op": "surface_trim", "tool": {"kind": "curve",
                                                         "id": "$curve:cut"},
                         ...}]}
      ]
    }

A phase runs after the previous one against the same model. Inside a phase an
id may be written as ``$curve:<feature name>``, ``$quilt:<feature name>`` or
``$body:<feature name>``: the runner resolves it from the inspection after the
phase that created it, so an example stays declarative and never hard codes a
session id.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:  # the driver runs as a script and as a package module
    from surface_chain_chains import make_checks, section, submit_plan
except ImportError:  # pragma: no cover - the package import path
    from tools.surface_chain_chains import make_checks, section, submit_plan

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER_PREFIX = "$"


def load_example(path: Path) -> dict[str, Any]:
    """Read an example file and return its phases."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    phases = payload.get("phases")
    if not phases:
        operations = payload.get("operations")
        if not operations:
            raise ValueError("an example needs an operations list or phases")
        phases = [{"operations": operations}]
    for phase in phases:
        if not phase.get("operations"):
            raise ValueError("every phase needs operations")
    return {"phases": phases, "description": payload.get("description", "")}


def _feature_id(features: list, name: str) -> int | None:
    for feature in features:
        if str(feature.get("name", "")).lower() == name.lower():
            return feature.get("id")
    return None


def _curve_ids(geometry: list, feature_id: int | None) -> list[int]:
    return [
        item["id"]
        for item in geometry
        if item.get("feature_id") == feature_id and item.get("type") == 62
    ]


async def resolve_placeholders(client, model_id: str, operations: list[dict]) -> list[dict]:
    """Replace $curve/$quilt/$body placeholders with real ids."""
    features = await section(client, model_id, "features")
    geometry = await section(client, model_id, "feature_geometry")
    bodies = await section(client, model_id, "bodies")
    resolved: list[dict] = []
    for operation in operations:
        copied = json.loads(json.dumps(operation))
        stack = [copied]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for key, value in list(node.items()):
                    if (
                        isinstance(value, str)
                        and value.startswith(PLACEHOLDER_PREFIX)
                        and key == "id"
                    ):
                        kind, _, name = value[1:].partition(":")
                        if kind == "curve":
                            ids = _curve_ids(geometry, _feature_id(features, name))
                            if not ids:
                                raise ValueError(f"no curve found for {value}")
                            node[key] = ids[0]
                        elif kind == "quilt":
                            quilts = await section(client, model_id, "quilts")
                            match = next(
                                (quilt for quilt in quilts if _quilt_name(quilt, name)),
                                None,
                            )
                            if match is None:
                                raise ValueError(f"no quilt found for {value}")
                            node[key] = match.get("quilt_id")
                        elif kind == "body":
                            match = next(
                                (
                                    body
                                    for body in bodies
                                    if str(body.get("name", "")).lower() == name.lower()
                                ),
                                None,
                            )
                            if match is None:
                                raise ValueError(f"no body found for {value}")
                            node[key] = match.get("id")
                        else:
                            raise ValueError(f"unknown placeholder kind: {value}")
                    elif isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(node, list):
                stack.extend(item for item in node if isinstance(item, (dict, list)))
        resolved.append(copied)
    return resolved


def _quilt_name(quilt: dict, name: str) -> bool:
    return str(quilt.get("name", "")).lower() == name.lower()


def _stand_in_for_placeholders(operations: list[dict]) -> list[dict]:
    """Replace every placeholder id with a dummy number for the schema check."""

    def walk(node):
        if isinstance(node, dict):
            return {
                key: (
                    1
                    if isinstance(value, str) and value.startswith(PLACEHOLDER_PREFIX)
                    else walk(value)
                )
                for key, value in node.items()
            }
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(json.loads(json.dumps(operations)))


def case_example_offline(path: Path) -> dict:
    """Check an example against the schema without touching a session."""
    from creo_mechdog.capabilities import UNAVAILABLE_OPERATIONS
    from creo_mechdog.schema import validate_operations

    checks, check = make_checks()
    example = load_example(path)
    for index, phase in enumerate(example["phases"]):
        # A placeholder is resolved against the model at run time, so the schema
        # check stands in a dummy id for it.
        operations = _stand_in_for_placeholders(phase["operations"])
        try:
            validate_operations([dict(operation) for operation in operations])
            check(f"phase_{index}_accepted", True)
        except ValueError as error:
            check(f"phase_{index}_accepted", False, {"error": str(error)})
        kinds = {operation.get("op") for operation in phase["operations"]}
        gated = sorted(kinds & set(UNAVAILABLE_OPERATIONS))
        check(f"phase_{index}_uses_no_gated_operator", not gated, {"gated": gated})
    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_example": "not_verified",
        "example": path.name,
        "checks": checks,
    }


async def case_example_live(wait_ready, path: Path) -> dict:
    """Run every phase of an example against the session."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks, check = make_checks()
    jobs: list[str] = []
    example = load_example(path)

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        check(
            "session_ready",
            bool(started.get("connected")),
            {"state": started.get("state"), "message": str(started.get("message"))[:200]},
        )
        if not started.get("connected"):
            return {
                "mode": "live",
                "passed": False,
                "native_example": "not_verified",
                "example": path.name,
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
            }

        model_id = None
        revision = None
        phases: list[dict] = []
        for index, phase in enumerate(example["phases"]):
            operations = phase["operations"]
            if model_id:
                operations = await resolve_placeholders(client, model_id, operations)
            built = await submit_plan(client, operations, jobs, model_id, revision)
            check(
                f"phase_{index}_succeeded",
                built.get("status") == "succeeded",
                {"status": built.get("status"), "message": built.get("message")},
            )
            check(
                f"phase_{index}_saved_and_reloaded",
                bool(built.get("saved_verified")),
                {"saved_verified": built.get("saved_verified")},
            )
            model_id = built.get("model_id") or model_id
            revision = built.get("revision") or revision
            phases.append(
                {
                    "phase": index,
                    "status": built.get("status"),
                    "operation": built.get("operation"),
                    "saved_verified": built.get("saved_verified"),
                }
            )
            if built.get("status") != "succeeded":
                break

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_example": "verified" if passed else "failed",
        "example": path.name,
        "jobs": jobs,
        "phases": phases,
        "checks": checks,
    }
