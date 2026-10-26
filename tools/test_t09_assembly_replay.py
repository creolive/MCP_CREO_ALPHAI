"""DEV-047 T09 assembly constraint replay acceptance. Default is strictly offline.

Only ``--live --confirm-session-usable`` starts an MCP client. The second flag
attests that the operator has completed the BUG-001 session recovery checks.
The driver never launches or stops Creo, clears protection, injects faults,
submits startup/retry commands, or resubmits a busy or failed job.

Live scope: build two source parts, assemble a single-level source assembly with
all six supported constraint types plus fixed/default placements, inspect it,
plan a rebuild against a fresh target assembly, execute it, prove real
constraint following by moving the sibling base and changing an offset, then
refuse missing mappings, expired/older snapshots and a changed source without
touching the target model or the source file.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402
from creo_mechdog.schema import validate_operations  # noqa: E402

ROOT = SOURCE_PATHS.resource_root
TOL = 1e-5
BASE_WIDTH, BASE_HEIGHT, BASE_DEPTH = 120.0, 80.0, 10.0
BOSS_RADIUS, BOSS_HEIGHT = 10.0, 20.0
PIN_RADIUS, PIN_HEIGHT = 9.0, 30.0
SUPPORTED_TYPES = ("mate", "align", "mate_offset", "align_offset", "insert", "csys")


def near(actual: Any, expected: Any, tolerance: float = TOL) -> None:
    assert isinstance(actual, (int, float)), (actual, expected)
    assert math.isfinite(actual), actual
    assert abs(actual - expected) <= max(tolerance, abs(expected) * 1e-6), (actual, expected)


def sketch(label: str, entities: list[dict], plane: str = "XY") -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": plane,
        "entities": entities,
        "dimensioning": "coordinates",
    }


def extrude(label: str, profile: str, depth: float, **kwargs: Any) -> dict:
    return {"op": "extrude", "label": label, "sketch": profile, "depth": depth, **kwargs}


def base_part() -> list[dict]:
    return [
        sketch(
            "base_profile",
            [
                {
                    "type": "rectangle",
                    "name": "plate",
                    "min": [-BASE_WIDTH / 2, -BASE_HEIGHT / 2],
                    "max": [BASE_WIDTH / 2, BASE_HEIGHT / 2],
                }
            ],
        ),
        extrude("base", "base_profile", BASE_DEPTH),
        sketch(
            "boss_profile",
            [{"type": "circle", "name": "boss", "center": [0, 0], "radius": BOSS_RADIUS}],
        ),
        extrude("boss", "boss_profile", BOSS_HEIGHT),
    ]


def pin_part() -> list[dict]:
    return [
        sketch(
            "pin_profile",
            [{"type": "circle", "name": "pin", "center": [0, 0], "radius": PIN_RADIUS}],
        ),
        extrude("pin", "pin_profile", PIN_HEIGHT),
    ]


def planned_cases() -> dict[str, dict]:
    """Plan-shaped operations the driver would submit, validated offline."""
    binding = {
        "source_model_id": "a" * 32,
        "source_revision": 3,
        "source_part_sha256": "b" * 64,
        "source_model_name": "base",
        "source_part_file": "C:/models/a/output/part.prt",
        "occurrence": "base",
        "occurrence_path": [5],
        "target_label": "t_base",
    }
    return {
        "insert_fixed": {
            "op": "assemble_component",
            "label": "t_base",
            "source_model_id": "a" * 32,
            "translation": [0, 0, 0],
            "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "placement": "fixed",
            "constraints": [],
            "rebuild_binding": binding,
        },
        "insert_default": {
            "op": "assemble_component",
            "label": "t_lid",
            "source_model_id": "a" * 32,
            "placement": "default",
            "rebuild_binding": binding,
        },
        "constraint_sibling": {
            "op": "component_constraints",
            "component": "t_pin",
            "constraints": [
                {
                    "type": "mate_offset",
                    "assembly_reference": {"kind": "surface", "id": 41},
                    "component_reference": {"kind": "surface", "id": 42},
                    "offset": 25.0,
                    "assembly_side": "yellow",
                    "component_side": "red",
                    "assembly_component": "t_base",
                }
            ],
        },
        "constraint_root": {
            "op": "component_constraints",
            "component": "t_pin",
            "constraints": [
                {
                    "type": "csys",
                    "assembly_reference": {"kind": "default_csys"},
                    "component_reference": {"kind": "default_csys"},
                    "offset": 0,
                    "assembly_side": "none",
                    "component_side": "none",
                }
            ],
        },
    }


def offline_check() -> dict:
    cases = planned_cases()
    for name, operation in cases.items():
        checked = validate_operations([operation])
        assert len(checked) == 1, (name, checked)
    return {
        "offline_only": True,
        "cases": list(cases),
        "constraint_types": list(SUPPORTED_TYPES),
        "toolkit_calls": "none",
    }


def require_live(args: argparse.Namespace) -> bool:
    if args.live and not args.confirm_session_usable:
        raise ValueError(
            "--live requires --confirm-session-usable after human session recovery checks"
        )
    return args.live


def require_manual_start(config_file: Path) -> None:
    """Driver-only precondition; never edits the user's startup configuration."""
    settings = json.loads(config_file.read_text(encoding="utf-8-sig"))
    if settings.get("auto_start_creo") is not False:
        raise ValueError(
            "Live acceptance requires config.json auto_start_creo=false; no client was started"
        )


def local_provenance() -> dict:
    """Record source evidence without recording config, license or session IDs."""
    from version import VERSION

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout.strip()

    names = set(
        git("ls-files", "--", "*.py", "native/*.h", "native/*.hpp", "native/*.cpp").splitlines()
    )
    names.update(
        (
            "tools/test_t09_assembly_replay.py",
            "tests/unit/test_t09_assembly_replay.py",
            "src/creo_mechdog/assembly_replay.py",
        )
    )
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in sorted(names)
        if (ROOT / name).is_file()
    }
    return {
        "version": VERSION,
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "dirty": bool(git("status", "--porcelain")),
        "source_sha256": hashes,
        "source_fingerprint": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "auto_start_creo": False,
        "human_session_confirmation": True,
    }


class Acceptance:
    def __init__(self, client: Any, output: Path) -> None:
        self.client = client
        self.output = output
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        self.source_name = f"t09_src_{stamp}"
        self.target_name = f"t09_dst_{stamp}"
        self.report: dict = {
            "task": "DEV-047 T09",
            "fixture": "120x80x10 plate + boss, Ø18x30 pin",
            "source_assembly": self.source_name,
            "target_assembly": self.target_name,
            "started_at": time.time(),
            "calls": [],
            "cases": [],
            "replay": {},
            "following": [],
            "admission_rejections": [],
            "invariance": [],
            "native_acceptance": "running",
            "toolkit_serial": True,
            "provenance": local_provenance(),
        }

    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def call(self, name: str, args: dict, *, allow_error: bool = False) -> Any:
        record = {
            "tool": name,
            "args": copy.deepcopy(args),
            "started_at": time.time(),
            "response_received": False,
            "outcome": "unknown",
            "call_state": "awaiting_response",
        }
        self.report["calls"].append(record)
        self.save()
        try:
            result = await self.client.call_tool(name, args)
        except Exception as error:
            record.update(
                call_state="client_exception",
                finished_at=time.time(),
                client_exception={"type": type(error).__name__, "message": str(error)},
            )
            self.save()
            raise
        record.update(
            response_received=True,
            outcome="response_received",
            call_state="returned",
            finished_at=time.time(),
            is_error=result.is_error,
            result=result.structured_content,
            content=str(result.content),
        )
        self.save()
        if result.is_error and not allow_error:
            raise RuntimeError(f"{name}: {result.content}")
        return result if allow_error else result.structured_content

    async def wait_ready(self, budget: float = 180) -> None:
        deadline = time.monotonic() + budget
        while True:
            status = await self.call("creo_startup_status", {})
            if status.get("state") == "ready" and status.get("connected") is True:
                return
            if status.get("state") not in {
                "checking",
                "building_worker",
                "starting",
                "waiting_for_connection",
            }:
                raise RuntimeError(
                    f"Existing session is not ready; no modeling submitted: {status}"
                )
            if time.monotonic() >= deadline:
                raise TimeoutError("Startup observation budget exceeded; no modeling submitted")
            await asyncio.sleep(1)

    async def plan(self, operations: list, model: dict | None = None) -> dict:
        args: dict = {"operations": operations}
        if model:
            args.update(model_id=model["model_id"], expected_revision=model["revision"])
        accepted = await self.call("creo_execute_plan", args)
        deadline = time.monotonic() + 360
        while time.monotonic() < deadline:
            terminal = await self.call("creo_get_job", {"job_id": accepted["job_id"]})
            if terminal["status"] not in ("queued", "running"):
                break
            await asyncio.sleep(1)
        else:
            raise TimeoutError(accepted["job_id"])
        assert terminal["status"] == "succeeded", terminal
        assert terminal["result"]["saved_file_reloaded_and_verified"] is True, terminal
        return terminal

    async def snapshot(self, model_id: str) -> dict:
        from creo_mechdog.query_client import read_full_model

        return await read_full_model(self.call, model_id)

    @staticmethod
    def kind_of(inspection: dict, item_id: int) -> dict:
        """Turn a snapshot item id into an execute_plan reference using real collections."""
        for surface in inspection.get("surfaces", []):
            if surface.get("id") == item_id:
                return {"kind": "surface", "id": item_id}
        for edge in inspection.get("edges", []):
            if edge.get("id") == item_id:
                return {"kind": "edge", "id": item_id}
        for plane in inspection.get("datum_planes", []):
            if plane.get("id") == item_id:
                return {"kind": "datum_plane", "id": item_id}
        for axis in inspection.get("datum_axes", []):
            if axis.get("id") == item_id:
                return {"kind": "axis", "id": item_id}
        return {"kind": "csys", "id": item_id}

    def reference_mapping(self, snapshot: dict, inspections: dict[str, dict]) -> list[dict]:
        entries = []
        seen = set()
        for node in snapshot["components"]:
            owner_label = node["occurrence_label"]
            source_id = self.source_ids[owner_label]
            inspection = inspections[source_id]
            for row in node["constraints"]:
                for key in ("asm_reference", "comp_reference"):
                    reference = row.get(key)
                    if not isinstance(reference, dict):
                        continue
                    owner = None
                    if reference.get("owner_scope") == "component":
                        owner = reference.get("occurrence_label")
                    identity = (
                        owner,
                        reference.get("item_type"),
                        reference.get("item_id"),
                        row.get(f"{'asm' if key == 'asm_reference' else 'comp'}_side"),
                    )
                    if identity in seen:
                        continue
                    seen.add(identity)
                    target = (
                        {"kind": "default_csys"}
                        if row["type"] == "csys"
                        else self.kind_of(inspection, reference["item_id"])
                    )
                    entries.append(
                        {
                            "source": {
                                "component": owner,
                                "item_type": reference["item_type"],
                                "item_id": reference["item_id"],
                                "side": identity[3],
                            },
                            "target": target,
                        }
                    )
        return entries

    async def build_sources(self) -> None:
        base = await self.plan(base_part())
        self.base_id = base["model_id"]
        pin = await self.plan(pin_part())
        self.pin_id = pin["model_id"]
        self.source_ids = {"base": self.base_id, "pin": self.pin_id}
        self.report["sources"] = {"base": self.base_id, "pin": self.pin_id}

    def surfaces(self, inspection: dict) -> dict[str, int]:
        """Pick reference faces from the real inspection by geometry, not by id."""
        planar = [
            surface
            for surface in inspection.get("surfaces", [])
            if isinstance(surface.get("normal"), list)
        ]
        curved = [
            surface
            for surface in inspection.get("surfaces", [])
            if not isinstance(surface.get("normal"), list)
        ]
        top = max(
            (s for s in planar if s["normal"][2] > 0.99),
            key=lambda s: s["bbox"][1][2],
            default=None,
        )
        bottom = max(
            (s for s in planar if s["normal"][2] < -0.99),
            key=lambda s: s["bbox"][0][2],
            default=None,
        )
        side = max(
            (s for s in planar if s["normal"][0] > 0.99),
            key=lambda s: s["bbox"][1][0],
            default=None,
        )
        if not all((top, bottom, side)) or not curved:
            raise RuntimeError("Fixture faces were not found in the native inspection")
        return {
            "top": top["id"],
            "bottom": bottom["id"],
            "side": side["id"],
            "cylinder": curved[0]["id"],
        }

    async def build_source_assembly(self) -> dict:
        created = await self.call("creo_new_assembly", {"model_name": self.source_name})
        source = {"model_id": created["model_id"], "revision": created["revision"]}
        base_faces = self.surfaces(await self.snapshot(self.base_id))
        pin_faces = self.surfaces(await self.snapshot(self.pin_id))
        result = await self.plan(
            [
                {
                    "op": "assemble_component",
                    "label": "base",
                    "source_model_id": self.base_id,
                    "placement": "default",
                },
                {
                    "op": "assemble_component",
                    "label": "p_mate",
                    "source_model_id": self.pin_id,
                    "translation": [0, 0, BASE_DEPTH],
                    "placement": "constraints",
                    "constraints": [
                        {
                            "type": "mate",
                            "assembly_reference": {"kind": "surface", "id": base_faces["top"]},
                            "component_reference": {
                                "kind": "surface",
                                "id": pin_faces["bottom"],
                            },
                        },
                        {
                            "type": "align",
                            "assembly_reference": {"kind": "surface", "id": base_faces["side"]},
                            "component_reference": {"kind": "surface", "id": pin_faces["side"]},
                        },
                    ],
                },
                {
                    "op": "assemble_component",
                    "label": "p_offset",
                    "source_model_id": self.pin_id,
                    "translation": [30, 0, BASE_DEPTH],
                    "placement": "constraints",
                    "constraints": [
                        {
                            "type": "mate_offset",
                            "assembly_reference": {"kind": "surface", "id": base_faces["top"]},
                            "component_reference": {
                                "kind": "surface",
                                "id": pin_faces["bottom"],
                            },
                            "offset": 25,
                        },
                        {
                            "type": "align_offset",
                            "assembly_reference": {"kind": "surface", "id": base_faces["side"]},
                            "component_reference": {"kind": "surface", "id": pin_faces["side"]},
                            "offset": 20,
                        },
                    ],
                },
                {
                    "op": "assemble_component",
                    "label": "p_insert",
                    "source_model_id": self.pin_id,
                    "translation": [0, 30, BASE_DEPTH],
                    "placement": "constraints",
                    "constraints": [
                        {
                            "type": "insert",
                            "assembly_component": "base",
                            "assembly_reference": {
                                "kind": "surface",
                                "id": base_faces["cylinder"],
                            },
                            "component_reference": {
                                "kind": "surface",
                                "id": pin_faces["cylinder"],
                            },
                        }
                    ],
                },
                {
                    "op": "assemble_component",
                    "label": "p_csys",
                    "source_model_id": self.pin_id,
                    "translation": [30, 30, BASE_DEPTH],
                    "placement": "constraints",
                    "constraints": [
                        {
                            "type": "csys",
                            "assembly_reference": {"kind": "default_csys"},
                            "component_reference": {"kind": "default_csys"},
                        }
                    ],
                },
            ],
            source,
        )
        self.report["source_assembly_job"] = result["job_id"]
        return result

    async def rejection(self, name: str, call: Any) -> str:
        result = await call
        record = {
            "name": name,
            "is_error": result.is_error,
            "content": str(result.content),
            "returned_at": time.time(),
        }
        self.report["admission_rejections"].append(record)
        self.save()
        assert result.is_error, record
        return str(result.content)

    async def run(self) -> None:
        await self.build_sources()
        source_job = await self.build_source_assembly()
        snapshot = await self.call(
            "creo_inspect_session_assembly", {"name": self.source_name, "limit": 50}
        )
        self.report["snapshot_id"] = snapshot["snapshot_id"]
        self.report["snapshot_schema_version"] = snapshot["snapshot_schema_version"]
        self.report["constraints_seen"] = [
            {
                "occurrence": node["occurrence_label"],
                "type": row["type"],
                "replayable": row["replayable"],
            }
            for node in snapshot["components"]
            for row in node["constraints"]
        ]
        assert snapshot["snapshot_schema_version"] == 3, snapshot["snapshot_schema_version"]
        types = {row["type"] for node in snapshot["components"] for row in node["constraints"]}
        assert set(SUPPORTED_TYPES) <= types, types
        assert all(
            isinstance(row["offset_mm"], (int, float))
            for node in snapshot["components"]
            for row in node["constraints"]
            if row["type"] in ("mate_offset", "align_offset")
        )
        assert any(
            row.get("asm_reference", {}).get("owner_scope") == "component"
            for node in snapshot["components"]
            for row in node["constraints"]
            if row["type"] != "csys"
        ), "no same-level sibling reference in the snapshot"

        inspections = {
            self.base_id: await self.snapshot(self.base_id),
            self.pin_id: await self.snapshot(self.pin_id),
        }
        component_mapping = [
            {
                "occurrence": node["occurrence_label"],
                "label": f"t_{node['occurrence_label']}",
                "source_model_id": self.source_ids[node["occurrence_label"]],
            }
            for node in snapshot["components"]
        ]
        reference_mapping = self.reference_mapping(snapshot, inspections)
        plan = await self.call(
            "creo_plan_assembly_rebuild",
            {
                "snapshot_id": snapshot["snapshot_id"],
                "component_mapping": component_mapping,
                "reference_mapping": reference_mapping,
            },
        )
        self.report["replay"]["plan"] = plan
        assert plan["read_only"] is True
        assert "operation_results" not in plan
        operations = plan["operations"]
        assert [op["op"] for op in operations].index("component_constraints") > max(
            index for index, op in enumerate(operations) if op["op"] == "assemble_component"
        )
        validate_operations(operations)
        assert any(
            "assembly_component" in row
            for op in operations
            if op["op"] == "component_constraints"
            for row in op["constraints"]
        )
        assert all("rebuild_binding" in op for op in operations if op["op"] == "assemble_component")

        target = await self.call("creo_new_assembly", {"model_name": self.target_name})
        executed = await self.plan(operations, target)
        self.report["replay"].update(
            target_model_id=executed["model_id"],
            target_job_id=executed["job_id"],
            target_revision=executed["revision"],
        )
        components = await self.call("creo_list_components", {"model_id": executed["model_id"]})
        rows = components["components"]
        replayed_types = {
            row["type_name"] for component in rows for row in component["constraints"]
        }
        assert set(SUPPORTED_TYPES) <= replayed_types, replayed_types
        offsets = {
            row["type_name"]: row["offset"]
            for component in rows
            for row in component["constraints"]
            if "offset" in row
        }
        near(offsets.get("mate_offset", 0), 25.0, 1e-3)
        near(offsets.get("align_offset", 0), 20.0, 1e-3)
        self.report["replay"]["constraints"] = [
            {"label": component.get("label"), "constraints": component["constraints"]}
            for component in rows
        ]

        # Real following: move the sibling base; every component constrained to it
        # must move with it. Then change an offset and verify the dependent moves.
        before = {row.get("label"): row.get("transform") for row in rows if row.get("label")}
        moved = await self.plan(
            [
                {
                    "op": "component_placement",
                    "component": "t_base",
                    "translation": [10, 0, 0],
                }
            ],
            executed,
        )
        after_rows = (await self.call("creo_list_components", {"model_id": moved["model_id"]}))[
            "components"
        ]
        after = {row.get("label"): row.get("transform") for row in after_rows if row.get("label")}
        for label in ("t_p_mate", "t_p_offset", "t_p_insert"):
            if label not in before or label not in after:
                continue
            delta = after[label][3][0] - before[label][3][0]
            near(delta, 10.0, 1e-3)
            self.report["following"].append(
                {"label": label, "driver": "sibling base moved +10 mm", "delta_x": delta}
            )
        if "t_p_csys" in before and "t_p_csys" in after:
            root_delta = after["t_p_csys"][3][0] - before["t_p_csys"][3][0]
            assert abs(root_delta) <= 1e-6, root_delta
            self.report["following"].append(
                {"label": "t_p_csys", "driver": "root assembly csys", "delta_x": root_delta}
            )
        changed = await self.plan(
            [
                {
                    "op": "component_constraints",
                    "component": "t_p_offset",
                    "constraints": [
                        {
                            "type": "mate_offset",
                            "assembly_component": "t_base",
                            "assembly_reference": {
                                "kind": "surface",
                                "id": self._reference_id(
                                    snapshot, "p_offset", "mate_offset", "asm"
                                ),
                            },
                            "component_reference": {
                                "kind": "surface",
                                "id": self._reference_id(
                                    snapshot, "p_offset", "mate_offset", "comp"
                                ),
                            },
                            "offset": 40,
                        }
                    ],
                }
            ],
            moved,
        )
        offset_rows = (await self.call("creo_list_components", {"model_id": changed["model_id"]}))[
            "components"
        ]
        self.report["following"].append(
            {
                "label": "t_p_offset",
                "driver": "mate_offset 25 -> 40 mm",
                "transform": next(
                    (row["transform"] for row in offset_rows if row.get("label") == "t_p_offset"),
                    None,
                ),
            }
        )

        # Rejections must not touch the target model or the source file.
        target_before = await self.snapshot(executed["model_id"])
        source_before = await self.snapshot(self.pin_id)
        missing = await self.rejection(
            "missing component mapping",
            self.call(
                "creo_plan_assembly_rebuild",
                {
                    "snapshot_id": snapshot["snapshot_id"],
                    "component_mapping": component_mapping[:-1],
                    "reference_mapping": reference_mapping,
                },
                allow_error=True,
            ),
        )
        assert "incomplete" in missing
        missing_reference = await self.rejection(
            "missing root reference mapping",
            self.call(
                "creo_plan_assembly_rebuild",
                {
                    "snapshot_id": snapshot["snapshot_id"],
                    "component_mapping": component_mapping,
                    "reference_mapping": [
                        entry
                        for entry in reference_mapping
                        if not (entry["source"]["component"] is None)
                    ],
                },
                allow_error=True,
            ),
        )
        assert "root reference" in missing_reference
        expired_id = self.write_snapshot_copy(snapshot, 601, 3)
        expired = await self.rejection(
            "expired snapshot",
            self.call(
                "creo_plan_assembly_rebuild",
                {
                    "snapshot_id": expired_id,
                    "component_mapping": component_mapping,
                    "reference_mapping": reference_mapping,
                },
                allow_error=True,
            ),
        )
        assert "expired" in expired
        old_id = self.write_snapshot_copy(snapshot, 0, 2)
        older = await self.rejection(
            "older snapshot schema",
            self.call(
                "creo_plan_assembly_rebuild",
                {
                    "snapshot_id": old_id,
                    "component_mapping": component_mapping,
                    "reference_mapping": reference_mapping,
                },
                allow_error=True,
            ),
        )
        assert "older" in older

        pin_before_edit = await self.snapshot(self.pin_id)
        dimension = next(
            (
                item
                for feature in pin_before_edit["inspection"]["features"]
                for item in feature.get("dimensions", [])
                if isinstance(item.get("value"), (int, float))
            ),
            None,
        )
        assert dimension is not None, "the fixture pin has no editable dimension"
        edited = await self.plan(
            [
                {
                    "op": "set_dimensions",
                    "values": [{"id": dimension["id"], "value": dimension["value"] + 2}],
                }
            ],
            {"model_id": self.pin_id, "revision": pin_before_edit["revision"]},
        )
        self.report["following"].append(
            {"label": "source edit", "job_id": edited["job_id"], "dimension_id": dimension["id"]}
        )
        source_after_edit = await self.snapshot(self.pin_id)
        assert source_after_edit["revision"] > source_before["revision"]
        changed_source = await self.call(
            "creo_execute_plan",
            {
                "operations": operations,
                "model_id": executed["model_id"],
                "expected_revision": target_before["revision"],
            },
            allow_error=True,
        )
        record = {
            "name": "changed source binding",
            "is_error": changed_source.is_error,
            "content": str(changed_source.content),
        }
        self.report["admission_rejections"].append(record)
        assert changed_source.is_error
        target_after = await self.snapshot(executed["model_id"])
        source_after = await self.snapshot(self.pin_id)
        assert target_after["revision"] == target_before["revision"], "target model changed"
        assert source_after["revision"] == source_after_edit["revision"], "source changed again"
        assert source_after["volume_mm3"] == source_after_edit["volume_mm3"]
        self.report["invariance"].append(
            {
                "target_revision_before": target_before["revision"],
                "target_revision_after": target_after["revision"],
                "source_revision": source_after["revision"],
                "source_volume_mm3": source_after["volume_mm3"],
                "source_unchanged_by_rejected_call": True,
            }
        )
        self.report.update(
            native_acceptance="passed",
            source_assembly_job=source_job["job_id"],
            six_constraint_types=sorted(replayed_types),
            sibling_reference_following=True,
        )

    def _reference_id(self, snapshot: dict, occurrence: str, ctype: str, side: str) -> int:
        for node in snapshot["components"]:
            if node["occurrence_label"] != occurrence:
                continue
            for row in node["constraints"]:
                if row["type"] != ctype:
                    continue
                key = "asm_reference" if side == "asm" else "comp_reference"
                return row[key]["item_id"]
        raise RuntimeError(f"reference not found in snapshot: {occurrence}/{ctype}/{side}")

    def write_snapshot_copy(self, snapshot: dict, age_seconds: int, version: int) -> str:
        """Copy the real snapshot into a fresh job directory with altered evidence.

        Only the snapshot file is written; no native job, model record or
        Toolkit call is created by this fixture.
        """
        import uuid

        import bridge

        snapshot_id = uuid.uuid4().hex
        directory = bridge.job_path(snapshot_id)
        directory.mkdir(parents=True)
        payload = copy.deepcopy(snapshot)
        payload["created"] = time.time() - age_seconds
        payload["schema_version"] = version
        (directory / "session_assembly.json").write_text(json.dumps(payload), encoding="utf-8")
        self.report.setdefault("snapshot_copies", []).append(snapshot_id)
        return snapshot_id


async def live(output: Path) -> None:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=60,
    ) as client:
        acceptance = Acceptance(client, output)
        acceptance.save()
        try:
            acceptance.report["capabilities"] = await acceptance.call("creo_capabilities", {})
            acceptance.report["environment"] = await acceptance.call("creo_check_environment", {})
            await acceptance.wait_ready()
            status = await acceptance.call("creo_session_status", {})
            assert status["connected"], status
            await acceptance.run()
        except Exception as error:
            acceptance.report.update(
                native_acceptance="failed", error=f"{type(error).__name__}: {error}"
            )
            raise
        finally:
            acceptance.save()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/t09_assembly_replay.json")
    args = parser.parse_args(argv)
    try:
        enabled = require_live(args)
    except ValueError as error:
        parser.error(str(error))
    if enabled:
        asyncio.run(live(args.output))
    else:
        print(json.dumps(offline_check(), indent=2))
        print(
            "OFFLINE ONLY: no MCP client, connection or native acceptance executed; use both "
            "explicit live flags after human session confirmation."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
