"""DEV-047 T05 analytical native acceptance. Default is strictly offline.

Only --live --confirm-session-usable starts an MCP client. The second flag
attests that the operator has completed BUG-001 session recovery checks.
Never clears protection, retries a busy submission, or restarts Creo.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import itertools
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

from creo_mechdog.paths import SOURCE_PATHS

ROOT = SOURCE_PATHS.resource_root
TILTED_NORMAL = (0.587785, 0.809017, 0.0)
TOL = 1e-5


def dot(a: list | tuple, b: list | tuple) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def unit(a: list | tuple) -> list[float]:
    length = math.sqrt(dot(a, a))
    assert math.isfinite(length) and length > 0, a
    return [x / length for x in a]


def cross(a: list | tuple, b: list | tuple) -> list[float]:
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def near(actual: Any, expected: Any, tolerance: float = TOL) -> None:
    if isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected), (actual, expected)
        for a, b in zip(actual, expected, strict=True):
            near(a, b, tolerance)
    else:
        assert math.isfinite(actual) and abs(actual - expected) <= tolerance, (actual, expected)


def box_oracle(frame: dict, depth: float, direction: str) -> tuple[list, list]:
    """10 by 20 section centered on O; depth denotes total symmetric depth."""
    low, high = {
        "positive": (0, depth),
        "negative": (-depth, 0),
        "symmetric": (-depth / 2, depth / 2),
    }[direction]
    o, u, v, n = (frame[key] for key in ("origin", "u_axis", "v_axis", "normal"))
    vertices = [
        [o[i] + a * u[i] + b * v[i] + t * n[i] for i in range(3)]
        for a, b, t in itertools.product((-5, 5), (-10, 10), (low, high))
    ]
    bounds = [
        [min(p[i] for p in vertices) for i in range(3)],
        [max(p[i] for p in vertices) for i in range(3)],
    ]
    center = [o[i] + (low + high) / 2 * n[i] for i in range(3)]
    return bounds, center


def rotate(point: list, origin: list, direction: list, degrees: float) -> list[float]:
    """Rodrigues rotation about the measured directed native line."""
    n = unit(direction)
    delta = [p - o for p, o in zip(point, origin, strict=True)]
    angle = math.radians(degrees)
    turn = cross(n, delta)
    return [
        origin[i]
        + delta[i] * math.cos(angle)
        + turn[i] * math.sin(angle)
        + n[i] * dot(n, delta) * (1 - math.cos(angle))
        for i in range(3)
    ]


def on_line(point: list, origin: list, direction: list) -> None:
    near(cross([p - o for p, o in zip(point, origin, strict=True)], unit(direction)), [0, 0, 0])


def match_centers(actual: list, expected: list) -> None:
    """Bijection: every expected cut has one distinct actual cylindrical center."""
    assert len(actual) == len(expected), (actual, expected)
    remaining = list(actual)
    for point in expected:
        matches = [
            i
            for i, candidate in enumerate(remaining)
            if all(abs(x - y) <= TOL for x, y in zip(candidate, point, strict=True))
        ]
        assert len(matches) == 1, (point, remaining)
        remaining.pop(matches[0])


def sketch(label: str, plane: Any, entity: dict) -> dict:
    # These analytical primitives have fully specified coordinates. Keep T05's
    # geometry oracle independent of the separately observed auto/autodim failure.
    return {
        "op": "sketch",
        "label": label,
        "plane": plane,
        "entities": [entity],
        "dimensioning": "coordinates",
    }


def rectangle(a: float, b: float) -> dict:
    return {"type": "rectangle", "name": "box", "min": [-a / 2, -b / 2], "max": [a / 2, b / 2]}


def circle(center: list, radius: float) -> dict:
    return {"type": "circle", "name": "circle", "center": center, "radius": radius}


def extrude(
    label: str, profile: str, depth: float, direction: str = "positive", **kwargs: Any
) -> dict:
    return {
        "op": "extrude",
        "label": label,
        "sketch": profile,
        "depth": depth,
        "direction": direction,
        **kwargs,
    }


def tilt_setup() -> list[dict]:
    return [
        {
            "op": "datum_axis",
            "label": "rotation_axis",
            "references": [
                {"kind": "datum_plane", "axis": "x"},
                {"kind": "datum_plane", "axis": "y"},
            ],
        },
        {
            "op": "datum_plane",
            "label": "tilted",
            "reference": {"kind": "datum_plane", "axis": "x"},
            "angle": 54,
            "axis": {"kind": "datum_axis_feature", "label": "rotation_axis"},
        },
    ]


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
    from creo_mechdog.source_provenance import local_provenance as collect

    evidence = collect(
        ROOT,
        (
            "native/axis_geometry.h",
            "tests/native/test_axis_geometry.cpp",
            "tests/unit/test_t05_geometry.py",
            "tools/test_axis_geometry.py",
            "tools/test_t05_native.py",
        ),
    )
    # Preserve the released report aliases while sharing source completeness checks.
    evidence["provenance_mode"] = "git" if evidence["git_status"] == "available" else "filesystem"
    evidence["git_unavailable"] = evidence["git_status"] != "available"
    evidence["commit"] = evidence["commit"] or ""
    evidence["branch"] = evidence["branch"] or ""
    return evidence


class Acceptance:
    def __init__(self, client: Any, output: Path) -> None:
        self.client = client
        self.output = output
        self.report: dict = {
            "task": "DEV-047 T05",
            "fixture_sketch_dimensioning": "coordinates",
            "started_at": time.time(),
            "cases": [],
            "native_acceptance": "running",
            "metric_geometry_matrix": "not_run",
            "native_unit_coverage": {
                "millimeter": "not_run",
                "non_millimeter_coordinates": "pending",
                "unknown_units_and_query_failures": "pending",
                "mixed_units": {
                    "status": "not_applicable_to_single_part_matrix",
                    "reason": "Each part has one principal length unit; assembly mixed units require separate evidence",
                },
            },
            "calls": [],
            "toolkit_serial": True,
            "provenance": local_provenance(),
        }

    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def call(self, name: str, args: dict) -> dict:
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
        if result.is_error:
            raise RuntimeError(f"{name}: {result.content}")
        return result.structured_content

    async def metric_matrix(self) -> None:
        self.report["metric_geometry_matrix"] = "running"
        for direction in ("positive", "negative", "symmetric"):
            await self.tilted(direction)
            await self.tilted(direction, principal=True)
            await self.tilted(direction, through=True)
        for count, increment, cylinder in itertools.product((2, 10), (36, -36), (False, True)):
            await self.pattern(count, increment, cylinder)
        await self.pattern(10, 36, False, origin=True)
        self.report.update(metric_geometry_matrix="passed", native_acceptance="partial")
        self.report["native_unit_coverage"]["millimeter"] = "passed"
        self.report["pending_native_acceptance"] = [
            "non_millimeter_coordinates",
            "unknown_units_and_query_failures",
        ]

    async def wait_job(self, accepted: dict, success: bool = True) -> dict:
        deadline = time.monotonic() + 360
        while time.monotonic() < deadline:
            terminal = await self.call(
                "creo_get_job", {"job_id": accepted["job_id"], "detail": "full"}
            )
            if terminal["status"] not in ("queued", "running"):
                break
            await asyncio.sleep(1)
        else:
            raise TimeoutError(accepted["job_id"])
        assert terminal["status"] == ("succeeded" if success else "failed"), terminal
        if success:
            assert terminal["result"]["saved_file_reloaded_and_verified"] is True, terminal
        else:
            assert terminal["result"]["rollback_succeeded"] is True, terminal
        return terminal

    async def depth_case(
        self,
        name: str,
        terminal: dict,
        *,
        expected_volume: float,
        expected_depth: float,
        expected_requested_type: str | None,
        expected_requested_depth: float | None,
        expected_defaulted: list[str],
    ) -> dict:
        operation = next(
            (item for item in terminal["result"]["operations"] if item.get("label") == "solid"),
            {},
        )
        block = operation.get("extrude_depth") or {}
        snapshot = await self.snapshot(terminal["model_id"])
        volume = snapshot["inspection"]["volume_mm3"]
        checks = {
            "source_feature_tree": block.get("source") == "feature_tree",
            "query_code_ok": block.get("query_code") == 0,
            "requested_type": block.get("requested_depth_type") == expected_requested_type,
            "requested_depth": block.get("requested_depth_mm") == expected_requested_depth,
            "effective_type_blind": block.get("effective_depth_type") == "blind",
            "effective_depth": block.get("effective_depth_mm") == expected_depth,
            "defaulted_fields": block.get("defaulted_fields") == expected_defaulted,
            "volume_mm3": abs(volume - expected_volume) <= max(0.05, 1e-4 * expected_volume),
            "saved_file_reloaded_and_verified": terminal["result"][
                "saved_file_reloaded_and_verified"
            ]
            is True,
        }
        case = {
            "case": name,
            "model_id": terminal["model_id"],
            "job_id": terminal.get("job_id"),
            "volume_mm3": volume,
            "extrude_depth": block,
            "checks": checks,
            "passed": all(checks.values()),
        }
        self.report.setdefault("extrude_depth_cases", []).append(case)
        return case

    async def extrude_depth_receipt(self) -> None:
        """W05: omission vs tree readback on 10x10 extrusions (100 / 1000 mm3)."""
        self.report["extrude_depth_receipt"] = "running"
        base = await self.plan([sketch("box_profile", "XY", rectangle(10, 10))])
        revision = (await self.snapshot(base["model_id"]))["revision"]
        accepted = await self.call(
            "creo_extrude",
            {
                "model_id": base["model_id"],
                "expected_revision": revision,
                "label": "solid",
                "sketch": "box_profile",
            },
        )
        await self.depth_case(
            "standalone_omitted_both",
            await self.wait_job(accepted),
            expected_volume=100.0,
            expected_depth=1.0,
            expected_requested_type=None,
            expected_requested_depth=None,
            expected_defaulted=["depth", "depth_type"],
        )
        extracted = await self.plan(
            [
                sketch("box_profile", "XY", rectangle(10, 10)),
                {"op": "extrude", "label": "solid", "sketch": "box_profile", "depth": 10},
            ]
        )
        await self.depth_case(
            "plan_depth_only",
            extracted,
            expected_volume=1000.0,
            expected_depth=10.0,
            expected_requested_type=None,
            expected_requested_depth=10.0,
            expected_defaulted=["depth_type"],
        )
        passed = all(case["passed"] for case in self.report["extrude_depth_cases"])
        self.report["extrude_depth_receipt"] = "passed" if passed else "failed"
        if not passed:
            raise RuntimeError(
                f"extrude_depth receipt failed: {self.report['extrude_depth_cases']}"
            )

    async def snapshot(self, model_id: str) -> dict:
        from creo_mechdog.query_client import read_full_model

        return await read_full_model(self.call, model_id)

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

    async def plan(
        self, operations: list, previous: dict | None = None, success: bool = True
    ) -> dict:
        args = {"operations": operations}
        if previous:
            args.update(model_id=previous["model_id"], expected_revision=previous["revision"])
        accepted = await self.call("creo_execute_plan", args)
        deadline = time.monotonic() + 360
        while time.monotonic() < deadline:
            terminal = await self.call("creo_get_job", {"job_id": accepted["job_id"]})
            if terminal["status"] not in ("queued", "running"):
                break
            await asyncio.sleep(1)
        else:
            raise TimeoutError(accepted["job_id"])
        assert terminal["status"] == ("succeeded" if success else "failed"), terminal
        if success:
            assert terminal["result"]["saved_file_reloaded_and_verified"] is True, terminal
        else:
            assert terminal["result"]["rollback_succeeded"] is True, terminal
        return terminal

    def check_snapshot(
        self, snapshot: dict, volume: float, bounds: list | None = None, center: list | None = None
    ) -> None:
        state = snapshot["inspection"]
        assert state["length_unit"]["name"] == "mm", state["length_unit"]
        near(state["length_unit"]["scale_to_mm"], 1)
        assert state["volume_query_code"] == 0
        near(state["volume_mm3"], volume)
        if center is not None:
            near(state["center_of_gravity"], center)
        if bounds is not None:
            bodies = [b for b in state["bodies"] if b.get("has_geometry")]
            assert len(bodies) == 1, bodies
            near(bodies[0]["bbox"], bounds)

    def alias(self, snapshot: dict, label: str) -> dict:
        # A snapshot whose aliases section was unavailable has no key at all;
        # fail with the snapshot shape instead of a bare KeyError.
        aliases = snapshot.get("aliases") or {}
        assert label in aliases, {
            "snapshot_keys": sorted(snapshot),
            "aliases": aliases,
        }
        return aliases[label]

    async def tilted(self, direction: str, principal: bool = False, through: bool = False) -> None:
        setup = [] if principal else tilt_setup()
        plane = (
            "XY"
            if principal
            else {"reference": {"kind": "datum_feature", "label": "tilted"}, "u_axis": [0, 0, 1]}
        )
        result = await self.plan(
            setup
            + [
                sketch("profile", plane, rectangle(10, 20)),
                extrude(
                    "solid", "profile", 12 if through else 4, "symmetric" if through else direction
                ),
            ]
        )
        before = await self.snapshot(result["model_id"])
        frame = self.alias(before, "profile")
        if not principal:
            # Datum orientation is native; geometric plane must have the fixed normal line.
            near(abs(dot(frame["normal"], unit(TILTED_NORMAL))), 1, 1e-6)
            near(frame["u_axis"], [0, 0, 1])
        bounds, center = box_oracle(
            frame, 12 if through else 4, "symmetric" if through else direction
        )
        self.check_snapshot(before, 2400 if through else 800, bounds, center)
        if through:
            result = await self.plan(
                [
                    sketch("cut_profile", plane, rectangle(2, 4)),
                    extrude(
                        "cut", "cut_profile", 1, direction, mode="cut", depth_type="through_all"
                    ),
                ],
                result,
            )
            removed = 96 if direction == "symmetric" else 48
            sign = {"positive": 1, "negative": -1, "symmetric": 0}[direction]
            center = [-removed * 3 * sign * x / (2400 - removed) for x in frame["normal"]]
            self.check_snapshot(
                await self.snapshot(result["model_id"]), 2400 - removed, bounds, center
            )
        self.report["cases"].append(
            {
                "case": "extrusion",
                "direction": direction,
                "principal": principal,
                "through_all": through,
                "job_id": result["job_id"],
                "model_id": result["model_id"],
                "actual_frame": frame,
                "passed": True,
            }
        )
        self.save()

    def axis(self, snapshot: dict, label: str, expected: list) -> dict:
        feature_id = self.alias(snapshot, label)["feature_id"]
        axes = [a for a in snapshot["inspection"]["datum_axes"] if a["feature_id"] == feature_id]
        assert len(axes) == 1, axes
        axis = axes[0]
        assert axis["geometry_known"] and axis["data_query_code"] == axis["line_query_code"] == 0, (
            axis
        )
        near(abs(dot(axis["direction"], [0, 0, 1])), 1)
        on_line(expected, axis["origin"], axis["direction"])
        return axis

    async def pattern(
        self, count: int, increment: float, cylinder: bool, origin: bool = False
    ) -> None:
        x, y = (0, 0) if origin else (4, -3)
        result = await self.plan(
            [
                sketch("disk_profile", "XY", circle([x, y], 30)),
                extrude("disk", "disk_profile", 6, "symmetric"),
            ]
        )
        snap = await self.snapshot(result["model_id"])
        cylinders = [
            s
            for s in snap["inspection"]["surfaces"]
            if s.get("radius") is not None and abs(s["radius"] - 30) <= TOL
        ]
        # Creo may split the base cylinder where sketch reference lines cross
        # it; co-axial same-radius pieces are still one analytical cylinder.
        assert cylinders, snap["inspection"]["surfaces"]
        assert (
            len({(round(s["origin"][0], 6), round(s["origin"][1], 6)) for s in cylinders}) == 1
        ), cylinders
        base_planes = []
        for coordinate in (0, 1):
            candidates = [
                p
                for p in snap["inspection"]["datum_planes"]
                if abs(abs(p["normal"][coordinate]) - 1) < TOL
                and abs(p["origin"][coordinate]) < TOL
            ]
            assert len(candidates) == 1, candidates
            base_planes.append(candidates[0])
        # Offset planes are first queried; explicit geometry IDs identify the actual supports.
        result = await self.plan(
            [
                {
                    "op": "datum_plane",
                    "label": "axis_x",
                    "reference": {"kind": "datum_plane", "id": base_planes[0]["id"]},
                    "offset": x * base_planes[0]["normal"][0],
                },
                {
                    "op": "datum_plane",
                    "label": "axis_y",
                    "reference": {"kind": "datum_plane", "id": base_planes[1]["id"]},
                    "offset": y * base_planes[1]["normal"][1],
                },
            ],
            result,
        )
        snap = await self.snapshot(result["model_id"])
        refs = []
        for label, coordinate in (("axis_x", 0), ("axis_y", 1)):
            fid = self.alias(snap, label)["feature_id"]
            geometries = [
                g
                for f in snap["inspection"]["features"]
                if f["id"] == fid
                for g in f["geometry_items"]
            ]
            assert len(geometries) == 1, geometries
            plane = next(
                p for p in snap["inspection"]["datum_planes"] if p["id"] == geometries[0]["id"]
            )
            near(plane["origin"][coordinate], (x, y)[coordinate])
            refs.append({"kind": "datum_plane", "id": plane["id"]})
        result = await self.plan(
            [
                {"op": "datum_axis", "label": "plane_axis", "references": refs},
                {
                    "op": "datum_axis",
                    "label": "cylinder_axis",
                    "references": [{"kind": "surface", "id": cylinders[0]["id"]}],
                },
            ],
            result,
        )
        snap = await self.snapshot(result["model_id"])
        measured = {
            label: self.axis(snap, label, [x, y, 0]) for label in ("plane_axis", "cylinder_axis")
        }
        # The operation result is measured before save; snapshot is measured after reload.
        for operation in result["result"]["operations"]:
            if operation["op"] == "datum_axis":
                actual = operation["datum_axes"][0]
                assert operation["axes_query_code"] == 0 and actual["geometry_known"]
                on_line([x, y, 0], actual["origin"], actual["direction"])
                near(abs(dot(actual["direction"], measured[operation["label"]]["direction"])), 1)
        label = "cylinder_axis" if cylinder else "plane_axis"
        axis = measured[label]
        result = await self.plan(
            [
                sketch("hole_profile", "XY", circle([x + 12, y], 1)),
                extrude("hole", "hole_profile", 8, "symmetric", mode="cut"),
            ],
            result,
        )
        before = await self.snapshot(result["model_id"])
        self.check_snapshot(before, math.pi * (900 - 1) * 6)
        result = await self.plan(
            [
                {
                    "op": "axis_pattern",
                    "label": "holes",
                    "leader": "hole",
                    "axis": {"kind": "datum_axis_feature", "label": label},
                    "count": count,
                    "increment_deg": increment,
                }
            ],
            result,
        )
        after = await self.snapshot(result["model_id"])
        expected = [
            rotate([x + 12, y, 0], [x, y, 0], axis["direction"], i * increment)
            for i in range(count)
        ]
        actual = []
        seen_centers = set()
        for surface in after["inspection"]["surfaces"]:
            if surface.get("radius") is not None and abs(surface["radius"] - 1) <= TOL:
                near(abs(dot(surface["axis"], [0, 0, 1])), 1)
                center = (round(surface["origin"][0], 6), round(surface["origin"][1], 6))
                # A hole whose cylinder Creo split at a reference line still
                # counts once; each expected hole keeps exactly one center.
                if center not in seen_centers:
                    seen_centers.add(center)
                    actual.append([surface["origin"][0], surface["origin"][1], 0])
        match_centers(actual, expected)
        self.check_snapshot(after, math.pi * (900 - count) * 6)
        near(
            before["inspection"]["volume_mm3"] - after["inspection"]["volume_mm3"],
            (count - 1) * math.pi * 6,
        )
        self.axis(after, label, [x, y, 0])
        failed = await self.plan(
            [
                sketch("miss_profile", "XY", circle([1000, 1000], 1)),
                extrude("miss", "miss_profile", 8, "symmetric", mode="cut"),
            ],
            result,
            success=False,
        )
        restored = await self.snapshot(result["model_id"])
        assert restored["revision"] == after["revision"], (failed, restored)
        self.check_snapshot(restored, after["inspection"]["volume_mm3"])
        assert "aliases" in restored and "aliases" in after, {
            "restored_keys": sorted(restored),
            "after_keys": sorted(after),
        }
        assert restored["aliases"] == after["aliases"]
        restored_holes = []
        restored_seen = set()
        for s in restored["inspection"]["surfaces"]:
            if s.get("radius") is not None and abs(s["radius"] - 1) <= TOL:
                center = (round(s["origin"][0], 6), round(s["origin"][1], 6))
                if center not in restored_seen:
                    restored_seen.add(center)
                    restored_holes.append([s["origin"][0], s["origin"][1], 0])
        match_centers(restored_holes, expected)
        self.report["cases"].append(
            {
                "case": "axis_pattern",
                "count": count,
                "increment": increment,
                "axis_source": label,
                "origin_control": origin,
                "directed_axis": axis,
                "expected_centers": expected,
                "actual_centers": actual,
                "model_id": result["model_id"],
                "job_id": result["job_id"],
                "rollback_job_id": failed["job_id"],
                "passed": True,
            }
        )
        self.save()


async def live(output: Path, section: str = "all") -> None:
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
            runtime, cursor = [], None
            while True:
                args = {"detail": "full", "section": "runtime"}
                if cursor:
                    args["cursor"] = cursor
                page = await acceptance.call("creo_capabilities", args)
                runtime.append(page)
                cursor = page.get("next_cursor")
                if not cursor:
                    break
            acceptance.report["runtime_identity"] = runtime
            # Server lifespan still runs its normal preparation; the checked setting
            # prevents Creo launch. This explicit live probe connects to the session.
            await acceptance.wait_ready()
            status = await acceptance.call("creo_session_status", {})
            assert status["connected"], status
            if section in ("all", "metric-matrix"):
                await acceptance.metric_matrix()
            if section in ("all", "extrude-depth"):
                await acceptance.extrude_depth_receipt()
            if section == "extrude-depth":
                # A section run proves the receipt only; the metric matrix
                # stays "not_run" so the overall verdict is partial.
                acceptance.report["native_acceptance"] = "partial"
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
    parser.add_argument("--output", type=Path, default=ROOT / "build/t05_native_acceptance.json")
    parser.add_argument(
        "--section",
        choices=("all", "metric-matrix", "extrude-depth"),
        default="all",
        help="Limit a live run to one section (default: all)",
    )
    args = parser.parse_args(argv)
    try:
        enabled = require_live(args)
    except ValueError as error:
        parser.error(str(error))
    if enabled:
        asyncio.run(live(args.output, args.section))
    else:
        print(
            "OFFLINE ONLY: no MCP client, connection or native acceptance executed; use both explicit live flags after human session confirmation."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
