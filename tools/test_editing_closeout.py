"""BUG-030 native cache/legacy regressions and BUG-029 no-op revision.

Developer integration test through the E-drive stdio MCP service. Mutations
are submitted once; a busy or unknown result stops the run. Legacy fixtures
change only records created by this run, under the shared channel lock, with
original control bytes and native-file hashes retained in the report folder.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import math
import platform
import sys
import time
import uuid
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import bridge
import generic_bridge as general
from creo_mechdog import inspection_refs, model_registry
from tools.dev_check import git_state
from tools.mcp_readiness import wait_for_startup
from version import VERSION

CIRCLE = [{"type": "circle", "name": "disk", "center": [0, 0], "radius": 8}]


def onaxis_sector(theta_max, radius):
    """BUG-082 on-axis sector profile (sketch plane XZ, revolve about the axis).

    The construction centerline is the revolve axis; ``l1`` is the radial edge
    on the +X side, the arc spans ``0 -> theta_max`` around the origin, and
    ``l2`` closes back to the origin (on the axis). Revolving 360 deg about the
    axis yields a spherical sector. The volume is NOT the half-ball formula
    ``(2*pi*R^3/3) * (1 - cos(theta_max))``; Pappus' theorem gives the correct
    ``V = (2*pi*R^3/3) * sin(theta_max)`` (the two agree only at 90 deg).
    """
    rad = math.radians(theta_max)
    return [
        {"type": "centerline", "name": "axis", "start": [0, 0], "end": [0, 20]},
        {"type": "line", "name": "l1", "start": [0, 0], "end": [radius, 0]},
        {
            "type": "arc",
            "name": "prof_arc",
            "center": [0, 0],
            "radius": radius,
            "start_angle": 0,
            "end_angle": theta_max,
        },
        {
            "type": "line",
            "name": "l2",
            "start": [radius * math.cos(rad), radius * math.sin(rad)],
            "end": [0, 0],
        },
    ]


def onaxis_sector_volume(radius, theta_max):
    """Spherical-sector volume of the on-axis sector revolved 360 deg."""
    return (2 * math.pi * radius**3 / 3) * math.sin(math.radians(theta_max))


def model_evidence(model: dict) -> dict:
    part = Path(model["part_file"]) if model.get("part_file") else None
    full = inspection_refs.full_inspection(model)
    aliases = model_registry.aliases_of(model)
    return {
        "revision": model["revision"],
        "status": model["status"],
        "pending_job": model.get("pending_job"),
        "recovery_pending": model.get("recovery_pending"),
        "part_sha256": hashlib.sha256(part.read_bytes()).hexdigest() if part else None,
        "inspection_sha256": inspection_refs.content_digest(full) if full is not None else None,
        "aliases_sha256": inspection_refs.content_digest(aliases),
        "inspection_summary": inspection_refs.summary_of(model),
        "feature_ids": {
            name: row["feature_id"]
            for name, row in aliases.items()
            if isinstance(row, dict) and "feature_id" in row
        },
    }


CASES = (
    "label_dimension_edit",
    "integer_dimension_edit",
    "numeric_string_dimension_edit",
    "legacy_unchanged",
    "legacy_changed",
    "dimensioning_and_clean_repeat",
    "parameter_driven_cache",
    "rectangle_native_verification",
    "entity_branch_native_verification",
    "arc_radius_inplace_edit",
    "onaxis_sector_coordinate_edit",
    "onaxis_sector_auto_to_autodim_edit",
    "onaxis_sector_autodim_edit",
    "onaxis_sector_auto_edit",
    "onaxis_sector_open_profile_failure",
    "reorder_noop_revision_plus_one",
)


class StartupObserver:
    """Stop on an explicit native connection failure instead of polling it."""

    def __init__(self, client, report):
        self.client = client
        self.report = report

    async def call_tool(self, name, args):
        response = await self.client.call_tool(name, args)
        status = response.structured_content
        if isinstance(status, dict):
            self.report["startup"] = status
            code = (status.get("native") or {}).get("toolkit_code")
            if status.get("connected") is not True and code not in (None, 0):
                raise RuntimeError(f"Native readiness failed ({code}); no modeling submitted")
        return response


class Closeout:
    def __init__(self, client, output, from_case=CASES[0]):
        self.client = client
        self.output = output
        self.selected_cases = CASES[CASES.index(from_case) :]
        self.created = set()
        self.report = {
            "version": VERSION,
            "git": git_state(ROOT),
            "python": platform.python_version(),
            "started_at": time.time(),
            "calls": [],
            "cases": [],
            "selected_cases": list(self.selected_cases),
        }

    def save(self):
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    async def call(self, name, args):
        result = await self.client.call_tool(name, args)
        payload = result.structured_content
        self.report["calls"].append(
            {"tool": name, "args": args, "is_error": result.is_error, "payload": payload}
        )
        self.save()
        if result.is_error:
            raise RuntimeError(f"{name}: {payload or result.content}")
        return payload

    async def job(self, name, args):
        submitted = await self.call(name, args)
        deadline = time.monotonic() + 330
        while True:
            value = await self.call(
                "creo_get_job", {"job_id": submitted["job_id"], "detail": "compact"}
            )
            if value["status"] not in {"queued", "running"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Preserve and poll the accepted job {submitted['job_id']}")
            await asyncio.sleep(1)
        assert value["status"] == "succeeded", value
        assert value["result"]["saved_file_reloaded_and_verified"] is True, value
        if "expected_revision" in args:
            assert value["revision"] == args["expected_revision"] + 1, value
        value["model_id"] = submitted["model_id"]
        value["job_id"] = submitted["job_id"]
        return value

    async def failed_job(self, name, args):
        submitted = await self.call(name, args)
        deadline = time.monotonic() + 330
        while True:
            value = await self.call(
                "creo_get_job", {"job_id": submitted["job_id"], "detail": "compact"}
            )
            if value["status"] not in {"queued", "running"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Preserve and poll the accepted job {submitted['job_id']}")
            await asyncio.sleep(1)
        value = await self.call("creo_get_job", {"job_id": submitted["job_id"], "detail": "full"})
        assert value["status"] == "failed", value
        assert value["result"]["rollback_succeeded"] is True, value
        value["model_id"] = submitted["model_id"]
        value["job_id"] = submitted["job_id"]
        return value

    def aliases(self, job):
        return model_registry.aliases_of(general.model_info(job["model_id"]))

    def detail(self, job, op):
        raw = bridge.read_json(bridge.job_path(job["job_id"]) / "native_result.json")
        return next(
            item
            for item in raw["operations"]
            if item["op"] == op and ("sketch" in item or "reordered" in item)
        )

    def volume(self, job, expected):
        actual = job["result"]["inspection_summary"]["volume_mm3"]
        assert abs(actual - expected) < 0.01, (actual, expected, job["job_id"])

    async def disk(self):
        job = await self.job(
            "creo_execute_plan",
            {
                "model_name": "cache_" + uuid.uuid4().hex[:12],
                "operations": [
                    {
                        "op": "sketch",
                        "label": "profile",
                        "plane": "XY",
                        "entities": CIRCLE,
                        "dimensions": [
                            {
                                "name": "diameter",
                                "type": "diameter",
                                "refs": [{"entity": "disk"}],
                                "value": 16,
                            }
                        ],
                    },
                    {"op": "extrude", "label": "pad", "sketch": "profile", "depth": 10},
                ],
            },
        )
        self.created.add(job["model_id"])
        self.volume(job, 640 * math.pi)
        meta = self.aliases(job)["profile"]
        assert meta["geometry_stale"] is False and meta["last_dimensioning"] == "auto"
        return job

    async def edit(self, job, entities=CIRCLE, mode="auto"):
        edited = await self.job(
            "creo_update_sketch_geometry",
            {
                "model_id": job["model_id"],
                "expected_revision": job["revision"],
                "sketch": "profile",
                "entities": entities,
                "dimensioning": mode,
            },
        )
        return edited, self.detail(edited, "update_sketch_geometry")

    async def resize(self, job, *, numeric=False, numeric_string=False):
        meta = self.aliases(job)["profile"]
        sketch = meta["feature_id"] if numeric or numeric_string else "profile"
        if numeric_string:
            sketch = str(sketch)
        edited = await self.job(
            "creo_set_sketch_dimensions",
            {
                "model_id": job["model_id"],
                "expected_revision": job["revision"],
                "sketch": sketch,
                "values": {str(meta["dimension_ids"]["diameter"]): 20},
            },
        )
        self.volume(edited, 1000 * math.pi)
        assert self.aliases(edited)["profile"]["geometry_stale"] is True
        return edited

    def make_legacy(self, job):
        mid = job["model_id"]
        assert mid in self.created
        with bridge.toolkit_lock(operation="bug030_isolated_legacy_fixture", model_id=mid):
            directory = general.model_path(mid)
            control = directory / "model.json"
            original = control.read_bytes()
            model = general.model_info(mid)
            assert model["status"] == "ready" and model["revision"] == job["revision"]
            assert not model.get("pending_job") and not model.get("recovery_pending")
            assert model["model_name"].startswith("cache_")
            part = Path(model["part_file"])
            digest = hashlib.sha256(part.read_bytes()).hexdigest()
            backup = self.output.parent / f"{mid}-model-before-legacy.json"
            backup.write_bytes(original)
            aliases = copy.deepcopy(model_registry.aliases_of(model))
            aliases["profile"].pop("geometry_stale", None)
            aliases["profile"].pop("last_dimensioning", None)
            model.pop("aliases_ref", None)
            model["aliases"] = aliases
            model_registry.write_model(directory, model)
            assert hashlib.sha256(part.read_bytes()).hexdigest() == digest
            self.report.setdefault("legacy_fixtures", []).append(
                {
                    "model_id": mid,
                    "revision": job["revision"],
                    "part_sha256": digest,
                    "control_backup": str(backup),
                    "original_control_sha256": hashlib.sha256(original).hexdigest(),
                }
            )
            self.save()

    def case(self, name, jobs, *, evidence=None):
        self.report["cases"].append(
            {"name": name, "jobs": jobs, "evidence": evidence, "passed": True}
        )
        self.save()
        print("CASE_PASS " + name, flush=True)

    async def run(self):
        for name, numeric, digit_string in (
            ("label_dimension_edit", False, False),
            ("integer_dimension_edit", True, False),
            ("numeric_string_dimension_edit", False, True),
        ):
            if name not in self.selected_cases:
                continue
            initial = await self.disk()
            changed = await self.resize(initial, numeric=numeric, numeric_string=digit_string)
            restored, details = await self.edit(changed)
            self.volume(restored, 640 * math.pi)
            assert details.get("unchanged") is not True
            self.case(name, [initial, changed, restored])

        for changed_first in (False, True):
            name = "legacy_changed" if changed_first else "legacy_unchanged"
            if name not in self.selected_cases:
                continue
            initial = await self.disk()
            current = await self.resize(initial) if changed_first else initial
            self.make_legacy(current)
            restored, details = await self.edit(current)
            self.volume(restored, 640 * math.pi)
            assert details.get("unchanged", False) is (not changed_first)
            assert self.aliases(restored)["profile"]["geometry_stale"] is False
            if not changed_first:
                assert details["native_geometry_verified"] is True
            self.case(
                "legacy_changed" if changed_first else "legacy_unchanged", [current, restored]
            )

        if "dimensioning_and_clean_repeat" in self.selected_cases:
            initial = await self.disk()
            coordinates, detail = await self.edit(initial, mode="coordinates")
            assert detail.get("unchanged") is not True
            automatic, detail = await self.edit(coordinates)
            assert detail.get("unchanged") is not True
            unchanged, detail = await self.edit(automatic)
            assert detail.get("unchanged") is True and detail["native_geometry_verified"] is True
            self.volume(unchanged, 640 * math.pi)
            self.case("dimensioning_and_clean_repeat", [initial, coordinates, automatic, unchanged])

        if "parameter_driven_cache" in self.selected_cases:
            initial = await self.disk()
            meta = self.aliases(initial)["profile"]
            # Feature sections omit nested collections; dimensions are available
            # as a separate flattened section with feature_id, id and symbol.
            dims = await self.call(
                "creo_inspect_model",
                {"model_id": initial["model_id"], "detail": "full", "section": "dimensions"},
            )
            symbol = next(
                dim["symbol"]
                for dim in dims["data"]["dimensions"]
                if dim["feature_id"] == meta["feature_id"]
                and dim["id"] == meta["dimension_ids"]["diameter"]
            )
            relation = await self.job(
                "creo_execute_plan",
                {
                    "model_id": initial["model_id"],
                    "expected_revision": initial["revision"],
                    "operations": [
                        {"op": "set_parameters", "values": {"CACHE_SIZE": 16.0}},
                        {"op": "set_relations", "lines": [symbol + " = CACHE_SIZE"]},
                    ],
                },
            )
            validated, detail = await self.edit(relation)
            assert detail.get("unchanged") is True
            assert self.aliases(validated)["profile"]["geometry_stale"] is False
            driven = await self.job(
                "creo_set_parameters",
                {
                    "model_id": validated["model_id"],
                    "expected_revision": validated["revision"],
                    "values": {"CACHE_SIZE": 20.0},
                },
            )
            self.volume(driven, 1000 * math.pi)
            assert self.aliases(driven)["profile"]["geometry_stale"] is True
            # Explicitly remove this isolated fixture's driver before requesting
            # new geometry, rather than pretending to override a driven dimension.
            released = await self.job(
                "creo_set_relations",
                {
                    "model_id": driven["model_id"],
                    "expected_revision": driven["revision"],
                    "lines": [],
                },
            )
            restored, detail = await self.edit(released)
            assert detail.get("unchanged") is not True
            self.volume(restored, 640 * math.pi)
            self.case(
                "parameter_driven_cache", [initial, relation, validated, driven, released, restored]
            )

        if "rectangle_native_verification" in self.selected_cases:
            rectangle = [{"type": "rectangle", "name": "box", "min": [0, 0], "max": [20, 10]}]
            initial = await self.job(
                "creo_execute_plan",
                {
                    "model_name": "cache_" + uuid.uuid4().hex[:12],
                    "operations": [
                        {"op": "sketch", "label": "profile", "entities": rectangle},
                        {"op": "extrude", "label": "pad", "sketch": "profile", "depth": 4},
                    ],
                },
            )
            repeated, detail = await self.edit(initial, rectangle)
            self.volume(repeated, 800)
            assert detail.get("unchanged") is True and detail["native_geometry_verified"] is True
            self.case("rectangle_native_verification", [initial, repeated])

        if "entity_branch_native_verification" in self.selected_cases:
            # BUG-030 native geometry verification: exercise the arc+line,
            # centerline+circle, ellipse and spline branches with identical
            # resubmissions. Volumes are matched against the first job because
            # free-form splines have no closed-form expectation.
            branches = {
                "arc_line": (
                    628.3185307,
                    [
                        {
                            "type": "arc",
                            "name": "dome",
                            "center": [0, 0],
                            "radius": 10,
                            "start_angle": 0,
                            "end_angle": 180,
                        },
                        {"type": "line", "name": "base", "start": [10, 0], "end": [-10, 0]},
                    ],
                ),
                "centerline_circle": (
                    804.2477193,
                    [
                        {
                            "type": "centerline",
                            "name": "axis",
                            "start": [-12, 0],
                            "end": [12, 0],
                        },
                        {"type": "circle", "name": "ring", "center": [0, 0], "radius": 8},
                    ],
                ),
                "ellipse": (
                    628.3185307,
                    [
                        {
                            "type": "ellipse",
                            "name": "oval",
                            "center": [0, 0],
                            "x_radius": 10,
                            "y_radius": 5,
                        }
                    ],
                ),
                "spline": (
                    None,
                    [
                        {
                            "type": "spline",
                            "name": "bulge",
                            "points": [[5, 0], [10, 5], [5, 10]],
                        },
                        {"type": "line", "name": "left", "start": [5, 10], "end": [0, 5]},
                        {"type": "line", "name": "bottom", "start": [0, 5], "end": [5, 0]},
                    ],
                ),
                "closed_spline": (
                    None,
                    [
                        {
                            "type": "spline",
                            "name": "blob",
                            "points": [[0, 0], [10, 2], [12, 9], [2, 11]],
                            "closed": True,
                        }
                    ],
                ),
            }
            jobs = []
            for branch, (expected, entities) in branches.items():
                initial = await self.job(
                    "creo_execute_plan",
                    {
                        "model_name": "cache_" + uuid.uuid4().hex[:12],
                        "operations": [
                            {
                                "op": "sketch",
                                "label": "profile",
                                "plane": "XY",
                                "entities": entities,
                            },
                            {"op": "extrude", "label": "pad", "sketch": "profile", "depth": 4},
                        ],
                    },
                )
                repeated, detail = await self.edit(initial, entities)
                actual = repeated["result"]["inspection_summary"]["volume_mm3"]
                baseline = initial["result"]["inspection_summary"]["volume_mm3"]
                assert abs(actual - baseline) < 0.01, (branch, actual, baseline)
                if expected is not None:
                    assert abs(actual - expected) < 0.01, (branch, actual, expected)
                if branch == "closed_spline":
                    # Solved periodic sections store fitted control points, so
                    # identity cannot be proven by point comparison; the safe
                    # replace path must run and preserve geometry instead.
                    assert detail.get("unchanged") is not True, (branch, detail)
                    assert self.aliases(repeated)["profile"]["geometry_stale"] is False
                else:
                    assert detail.get("unchanged") is True, (branch, detail)
                    assert detail["native_geometry_verified"] is True, (branch, detail)
                jobs.extend([initial, repeated])
            self.case("entity_branch_native_verification", jobs)

        if "reorder_noop_revision_plus_one" in self.selected_cases:
            initial = await self.job(
                "creo_execute_plan",
                {
                    "model_name": "cache_" + uuid.uuid4().hex[:12],
                    "operations": [
                        {
                            "op": "datum_plane",
                            "label": "dtp1",
                            "reference": {"kind": "datum_plane", "axis": "z"},
                            "offset": 5,
                        },
                        {
                            "op": "datum_plane",
                            "label": "dtp2",
                            "reference": {"kind": "datum_plane", "axis": "z"},
                            "offset": 10,
                        },
                    ],
                },
            )
            noop = await self.job(
                "creo_reorder_features",
                {
                    "model_id": initial["model_id"],
                    "expected_revision": initial["revision"],
                    "features": ["dtp2"],
                    "after": "dtp1",
                },
            )
            assert self.detail(noop, "reorder_features")["reordered"] is False
            self.case("reorder_noop_revision_plus_one", [initial, noop])

        if "arc_radius_inplace_edit" in self.selected_cases:
            # BUG-079: changing an arc radius during an in-place edit used to
            # under-dimension the redefined section, and feature regeneration
            # failed with a rollback. The revolve fixture keeps the arc off
            # the axis; the BUG-062 sphere fixture (endpoints on the axis)
            # never exercised this failure.
            def profile(radius):
                return [
                    {"type": "centerline", "name": "axis", "start": [0, 0], "end": [0, 20]},
                    {
                        "type": "arc",
                        "name": "prof_arc",
                        "center": [8, 5],
                        "radius": radius,
                        "start_angle": 0,
                        "end_angle": 180,
                    },
                    {
                        "type": "line",
                        "name": "prof_line",
                        "start": [8 - radius, 5],
                        "end": [8 + radius, 5],
                    },
                ]

            initial = await self.job(
                "creo_execute_plan",
                {
                    "model_name": "cache_" + uuid.uuid4().hex[:12],
                    "operations": [
                        {
                            "op": "sketch",
                            "label": "rev_sk",
                            "plane": "XY",
                            "entities": profile(5),
                        },
                        {"op": "revolve", "label": "rev1", "sketch": "rev_sk", "angle": 360},
                    ],
                },
            )
            self.created.add(initial["model_id"])
            # Half-disk profile revolved 360 deg about the axis: V = 8*pi^2*r^2.
            self.volume(initial, 200 * math.pi * math.pi)
            grown = await self.job(
                "creo_update_sketch_geometry",
                {
                    "model_id": initial["model_id"],
                    "expected_revision": initial["revision"],
                    "sketch": "rev_sk",
                    "entities": profile(6),
                },
            )
            self.volume(grown, 288 * math.pi * math.pi)
            detail = self.detail(grown, "update_sketch_geometry")
            assert detail.get("unchanged") is not True
            assert detail.get("preserved_feature_id") is not None
            restored = await self.job(
                "creo_update_sketch_geometry",
                {
                    "model_id": grown["model_id"],
                    "expected_revision": grown["revision"],
                    "sketch": "rev_sk",
                    "entities": profile(5),
                },
            )
            self.volume(restored, 200 * math.pi * math.pi)
            self.case("arc_radius_inplace_edit", [initial, grown, restored])

        if "onaxis_sector_coordinate_edit" in self.selected_cases:
            # BUG-082 on-axis sector: coordinates edits succeed and the volume
            # follows the spherical-sector formula V = (2*pi*R^3/3)*sin(theta_max)
            # (NOT the half-ball 1-cos(theta_max) formula, which only agrees at
            # 90 deg). The off-axis BUG-079 regression is the arc_radius_inplace_edit
            # case above; the half-circle on-axis baseline failure is a separate
            # item and is not asserted here.
            def plan(entities):
                return [
                    {"op": "sketch", "label": "rev_sk", "plane": "XZ", "entities": entities},
                    {"op": "revolve", "label": "rev1", "sketch": "rev_sk", "angle": 360},
                ]

            initial = await self.job(
                "creo_execute_plan",
                {
                    "model_name": "cache_" + uuid.uuid4().hex[:12],
                    "operations": plan(onaxis_sector(90, 10)),
                },
            )
            self.created.add(initial["model_id"])
            self.volume(initial, onaxis_sector_volume(10, 90))
            rev_id = self.aliases(initial)["rev1"]["feature_id"]
            angled = await self.job(
                "creo_update_sketch_geometry",
                {
                    "model_id": initial["model_id"],
                    "expected_revision": initial["revision"],
                    "sketch": "rev_sk",
                    "entities": onaxis_sector(80, 10),
                    "dimensioning": "coordinates",
                },
            )
            self.volume(angled, onaxis_sector_volume(10, 80))
            detail = self.detail(angled, "update_sketch_geometry")
            assert detail.get("unchanged") is not True
            assert detail.get("preserved_feature_id") is not None
            assert self.aliases(angled)["rev1"]["feature_id"] == rev_id
            back = await self.job(
                "creo_update_sketch_geometry",
                {
                    "model_id": angled["model_id"],
                    "expected_revision": angled["revision"],
                    "sketch": "rev_sk",
                    "entities": onaxis_sector(90, 10),
                    "dimensioning": "coordinates",
                },
            )
            self.volume(back, onaxis_sector_volume(10, 90))
            grown = await self.job(
                "creo_update_sketch_geometry",
                {
                    "model_id": back["model_id"],
                    "expected_revision": back["revision"],
                    "sketch": "rev_sk",
                    "entities": onaxis_sector(90, 12),
                    "dimensioning": "coordinates",
                },
            )
            self.volume(grown, onaxis_sector_volume(12, 90))
            assert self.aliases(grown)["rev1"]["feature_id"] == rev_id
            restored = await self.job(
                "creo_update_sketch_geometry",
                {
                    "model_id": grown["model_id"],
                    "expected_revision": grown["revision"],
                    "sketch": "rev_sk",
                    "entities": onaxis_sector(90, 10),
                    "dimensioning": "coordinates",
                },
            )
            self.volume(restored, onaxis_sector_volume(10, 90))
            # Direct submissions of the edited geometry (no in-place edit) also
            # succeed: the on-axis sector is valid geometry, the failure is
            # edit-path specific (D1_80 / D2_R12 controls).
            direct_80 = await self.job(
                "creo_execute_plan",
                {
                    "model_name": "cache_" + uuid.uuid4().hex[:12],
                    "operations": plan(onaxis_sector(80, 10)),
                },
            )
            self.created.add(direct_80["model_id"])
            self.volume(direct_80, onaxis_sector_volume(10, 80))
            direct_r12 = await self.job(
                "creo_execute_plan",
                {
                    "model_name": "cache_" + uuid.uuid4().hex[:12],
                    "operations": plan(onaxis_sector(90, 12)),
                },
            )
            self.created.add(direct_r12["model_id"])
            self.volume(direct_r12, onaxis_sector_volume(12, 90))
            self.case(
                "onaxis_sector_coordinate_edit",
                [initial, angled, back, grown, restored, direct_80, direct_r12],
            )

        if "onaxis_sector_auto_to_autodim_edit" in self.selected_cases:
            # BUG-082 regression (formerly the autodim failure case): the
            # external-report combination — implicit auto creation, explicit
            # autodim edit — now rides the BUG-079 coordinate upgrade on
            # principal planes and must succeed with identities preserved.
            initial = await self.job(
                "creo_execute_plan",
                {
                    "model_name": "cache_" + uuid.uuid4().hex[:12],
                    "operations": [
                        {
                            "op": "sketch",
                            "label": "rev_sk",
                            "plane": "XZ",
                            "entities": onaxis_sector(90, 10),
                        },
                        {"op": "revolve", "label": "rev1", "sketch": "rev_sk", "angle": 360},
                    ],
                },
            )
            self.created.add(initial["model_id"])
            self.volume(initial, onaxis_sector_volume(10, 90))
            identities = {
                name: self.aliases(initial)[name]["feature_id"] for name in ("rev_sk", "rev1")
            }
            angled = await self.job(
                "creo_update_sketch_geometry",
                {
                    "model_id": initial["model_id"],
                    "expected_revision": initial["revision"],
                    "sketch": "rev_sk",
                    "entities": onaxis_sector(80, 10),
                    "dimensioning": "autodim",
                },
            )
            self.volume(angled, onaxis_sector_volume(10, 80))
            for name, feature_id in identities.items():
                assert self.aliases(angled)[name]["feature_id"] == feature_id
            self.case("onaxis_sector_auto_to_autodim_edit", [initial, angled])

        if "onaxis_sector_open_profile_failure" in self.selected_cases:
            # BUG-082 failure fixture after the fix: an OPEN profile (l2 stops
            # short of the axis) is genuinely illegal geometry for the
            # downstream revolve, so the edit must fail, roll back cleanly and
            # publish feature-level diagnostics (failed_features) — without
            # keeping the old under-constrained autodim defect around just to
            # produce a failure.
            initial = await self.job(
                "creo_execute_plan",
                {
                    "model_name": "cache_" + uuid.uuid4().hex[:12],
                    "operations": [
                        {
                            "op": "sketch",
                            "label": "rev_sk",
                            "plane": "XZ",
                            "entities": onaxis_sector(90, 10),
                        },
                        {"op": "revolve", "label": "rev1", "sketch": "rev_sk", "angle": 360},
                    ],
                },
            )
            self.created.add(initial["model_id"])
            self.volume(initial, onaxis_sector_volume(10, 90))
            before = general.model_info(initial["model_id"])
            before_evidence = model_evidence(before)
            failed = await self.failed_job(
                "creo_update_sketch_geometry",
                {
                    "model_id": initial["model_id"],
                    "expected_revision": initial["revision"],
                    "sketch": "rev_sk",
                    "entities": [
                        {"type": "centerline", "name": "axis", "start": [0, 0], "end": [0, 20]},
                        {"type": "line", "name": "l1", "start": [0, 0], "end": [10, 0]},
                        {
                            "type": "arc",
                            "name": "prof_arc",
                            "center": [0, 0],
                            "radius": 10,
                            "start_angle": 0,
                            "end_angle": 90,
                        },
                        {"type": "line", "name": "l2", "start": [0, 10], "end": [0, 5]},
                    ],
                    "dimensioning": "autodim",
                },
            )
            assert failed["result"]["message"].startswith("Regeneration produced a failed"), failed
            features = failed["result"].get("failed_features") or []
            assert features, failed
            assert any(f["status"] != 0 for f in features), features
            after = general.model_info(initial["model_id"])
            after_evidence = model_evidence(after)
            assert after_evidence["revision"] == before_evidence["revision"]
            for key in ("part_sha256", "inspection_sha256", "aliases_sha256", "feature_ids"):
                assert after_evidence[key] == before_evidence[key], (
                    key,
                    before_evidence,
                    after_evidence,
                )
            assert after_evidence["pending_job"] == before_evidence["pending_job"]
            assert after_evidence["recovery_pending"] == before_evidence["recovery_pending"]
            evidence = {
                "before": before_evidence,
                "after": after_evidence,
                "job_revision": failed.get("revision"),
            }
            self.case("onaxis_sector_open_profile_failure", [initial, failed], evidence=evidence)

        if "onaxis_sector_autodim_edit" in self.selected_cases:
            # BUG-082 success target: explicit autodim on-axis edits (angle
            # 90->80->90, radius 10->12->10) must succeed with preserved
            # sketch/revolve identities. Expected to fail before the
            # regeneration fix lands; the autodim_failure case above is the
            # diagnostic contrast and stays regardless of this case's outcome.
            jobs = await verify_onaxis_edits(self, "autodim")
            self.case("onaxis_sector_autodim_edit", jobs)

        if "onaxis_sector_auto_edit" in self.selected_cases:
            # Diagnostic contrast for BUG-082: an implicit "auto" edit routes
            # to coordinate dimensions on principal planes (BUG-079), so this
            # exercises the production default path over the same edits.
            jobs = await verify_onaxis_edits(self, "auto")
            self.case("onaxis_sector_auto_edit", jobs)

        self.report["success"] = True
        self.save()
        print("EDITING_CLOSEOUT_SUCCESS=1", flush=True)


async def verify_onaxis_edits(suite, mode):
    """BUG-082 success target: four in-place on-axis sector edits in one mode.

    Creation and every edit use the same explicit ``mode`` (autodim for the
    new success case; coordinates also works as the proven contrast). Each
    edit must succeed, bump the revision, follow the spherical-sector volume
    and keep both feature identities; any failure stops the run instead of
    resubmitting.
    """
    initial = await suite.job(
        "creo_execute_plan",
        {
            "model_name": "cache_" + uuid.uuid4().hex[:12],
            "operations": [
                {
                    "op": "sketch",
                    "label": "rev_sk",
                    "plane": "XZ",
                    "entities": onaxis_sector(90, 10),
                    "dimensioning": mode,
                },
                {"op": "revolve", "label": "rev1", "sketch": "rev_sk", "angle": 360},
            ],
        },
    )
    suite.created.add(initial["model_id"])
    suite.volume(initial, onaxis_sector_volume(10, 90))
    identities = {name: suite.aliases(initial)[name]["feature_id"] for name in ("rev_sk", "rev1")}
    jobs = [initial]
    for theta, radius in ((80, 10), (90, 10), (90, 12), (90, 10)):
        edited = await suite.job(
            "creo_update_sketch_geometry",
            {
                "model_id": initial["model_id"],
                "expected_revision": initial["revision"],
                "sketch": "rev_sk",
                "entities": onaxis_sector(theta, radius),
                "dimensioning": mode,
            },
        )
        suite.volume(edited, onaxis_sector_volume(radius, theta))
        for name, feature_id in identities.items():
            assert suite.aliases(edited)[name]["feature_id"] == feature_id
        jobs.append(edited)
        initial = edited
    return jobs


async def main(*, retry_startup=False, from_case=CASES[0]):
    directory = ROOT / "build" / "editing-closeout" / uuid.uuid4().hex
    directory.mkdir(parents=True)
    output = directory / "report.json"
    print("REPORT=" + str(output), flush=True)
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=180,
    ) as client:
        suite = Closeout(client, output, from_case)
        try:
            if retry_startup:
                suite.report["explicit_startup_retry"] = (
                    await client.call_tool("creo_startup_status", {"retry": True})
                ).structured_content
                suite.save()
            await wait_for_startup(StartupObserver(client, suite.report), suite.report, output)
            suite.report["session"] = await suite.call("creo_session_status", {})
            assert suite.report["session"]["connected"] is True
            await suite.run()
        except BaseException as error:
            suite.report["success"] = False
            suite.report["error"] = repr(error)
            suite.save()
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--retry-startup",
        action="store_true",
        help="Explicitly retry startup once after user confirmation",
    )
    parser.add_argument(
        "--from-case",
        choices=CASES,
        default=CASES[0],
        help="Start at this case using new isolated models; never replay a previous job",
    )
    options = parser.parse_args()
    asyncio.run(main(retry_startup=options.retry_startup, from_case=options.from_case))
