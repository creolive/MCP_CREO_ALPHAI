"""BUG-094 offline driver for the creo_datum_plane parameter contract.

Offline stage (default): the shared admission matrix for reference kinds, the
angle/offset combination rejection, the angle-axis selection contract, the
tool-description contract, and a native source guard. The source guard only
proves the committed backstop is present in the working tree; it is not native
verification and no executor is built here.

Live stage (--live --confirm-session-usable, scheduled separately by the
orchestrator): runs the same contract against the manually opened Creo session.
The live matrix covers the actual directed axis (+Z and -Z orientations are
read from inspection, never assumed from the label), angle +54/-54/0 about the
measured axis with a Rodrigues-rotation normal oracle, offset-only, an explicit
offset measured from a previously rotated plane, the standalone creo_datum_plane
tool and the execute_plan entry on the same contract, and the rejection cases
(angle with a nonzero offset, missing kind, plane-labelled axis) which must
fail without a dispatched job, a new feature, or a revision change. Every
successful modeling job must report saved_file_reloaded_and_verified is true.
It never launches, restarts or closes Creo, never injects a fault, never clears
a protection and never resubmits a job; a busy channel, an unknown terminal
state or a polling timeout stops the run and preserves the scene.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import math
import sys
import time
import unittest
import uuid
from pathlib import Path
from typing import Any

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402

ROOT = SOURCE_PATHS.resource_root

TOL = 1e-6
REPORTED_OFFSET_MM = -8.65981
REPORTED_ANGLE_DEG = 54.0


# --- shared oracle helpers -------------------------------------------------


def dot(a: list | tuple, b: list | tuple) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def cross(a: list | tuple, b: list | tuple) -> list[float]:
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def unit(a: list | tuple) -> list[float]:
    length = math.sqrt(dot(a, a))
    assert math.isfinite(length) and length > TOL, a
    return [x / length for x in a]


def near(actual: Any, expected: Any, tolerance: float = TOL) -> None:
    if isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected), (actual, expected)
        for a, b in zip(actual, expected, strict=True):
            near(a, b, tolerance)
    else:
        assert math.isfinite(actual) and abs(actual - expected) <= tolerance, (actual, expected)


def parallel(actual: list, expected: list) -> None:
    """Plane normals are lines: parallelism distinguishes the angle, not the sign."""
    near(abs(dot(unit(actual), unit(expected))), 1)


def rotate_normal(normal: list, axis_origin: list, axis_direction: list, degrees: float) -> list:
    """Rodrigues rotation of a plane normal about the measured directed axis."""
    d = unit(axis_direction)
    angle = math.radians(degrees)
    turned = cross(d, normal)
    return [
        normal[i] * math.cos(angle)
        + turned[i] * math.sin(angle)
        + d[i] * dot(d, normal) * (1 - math.cos(angle))
        for i in range(3)
    ]


def on_line(point: list, origin: list, direction: list) -> None:
    near(cross([p - o for p, o in zip(point, origin, strict=True)], unit(direction)), [0, 0, 0])


def plane_constant(plane: dict, normal: list) -> float:
    return dot(plane["origin"], unit(normal))


def datum_plane_op(**overrides) -> dict:
    op = {
        "op": "datum_plane",
        "label": "datum",
        "reference": {"kind": "datum_plane", "axis": "z"},
    }
    op.update(overrides)
    return op


# --- offline validation matrix ---------------------------------------------


def check_validation_matrix() -> dict:
    """Re-run the key positives and negatives; every case asserts or raises."""
    from creo_mechdog.schema import validate_operations

    positives = []
    positives.append(("offset_only", validate_operations([datum_plane_op(offset=7.5)])[0]))
    positives.append(
        (
            "angle_only",
            validate_operations(
                [
                    datum_plane_op(
                        angle=REPORTED_ANGLE_DEG,
                        axis={"kind": "datum_axis_feature", "label": "rotation_axis"},
                    )
                ]
            )[0],
        )
    )
    positives.append(
        (
            "angle_zero",
            validate_operations([datum_plane_op(angle=0, axis={"kind": "axis", "id": 83})])[0],
        )
    )
    for name, op in positives:
        assert "angle" not in op or op["offset"] == 0, (name, op)

    rejections = [
        (
            "reported_angle_offset",
            datum_plane_op(offset=REPORTED_OFFSET_MM, angle=54),
            "nonzero offset",
        ),
        ("angle_zero_offset", datum_plane_op(offset=5.0, angle=0), "nonzero offset"),
        ("angle_without_axis", datum_plane_op(angle=54), "angle axis"),
        ("missing_kind", datum_plane_op(reference={}), "before a job is dispatched"),
        (
            "plane_label_axis",
            datum_plane_op(angle=54, axis={"kind": "plane", "id": 9}),
            "angle axis",
        ),
        (
            "datum_feature_axis",
            datum_plane_op(angle=54, axis={"kind": "datum_feature", "label": "axis_label"}),
            "angle axis",
        ),
    ]
    for name, op, expected_fragment in rejections:
        original = copy.deepcopy(op)
        try:
            validate_operations([op])
        except ValueError as error:
            assert expected_fragment in str(error), (name, str(error))
        else:
            raise AssertionError(f"{name}: contract rejection missing")
        assert op == original, name

    return {
        "positives": [name for name, _ in positives],
        "rejections": [name for name, _, _ in rejections],
        "passed": True,
    }


def check_tool_description() -> dict:
    import server

    tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
    description = " ".join(tools["creo_datum_plane"].description.split())
    for fragment in (
        "angle (including 0)",
        "combining angle with a nonzero offset is rejected before a job is dispatched",
        "silently dropping the offset",
        "{kind:'axis',id:N}",
        "{kind:'datum_axis_feature',label:'axis_label'}",
        "not a rotation axis",
        "Missing kind and unknown labels are rejected before a job is dispatched",
        "matches an existing planar face",
    ):
        assert fragment in description, fragment
    return {"fragments_checked": 8, "passed": True}


def check_native_source() -> dict:
    """Committed-backstop guard; not native verification and no build is run here."""
    source = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8", errors="replace")
    guards = {
        "resolve_missing_kind": "Reference requires a {kind:...} selection object",
        "angle_offset_combination": "cannot combine an explicit angle with a nonzero offset",
        "angle_axis_kind": "An angled datum_plane requires axis {kind:'axis',id:N} or",
    }
    for name, fragment in guards.items():
        assert fragment in source, name
    return {"guards": sorted(guards), "statement": "source guard only; build and live pending"}


def run_unit_module() -> dict:
    from tests.unit import test_datum_plane_contract

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_datum_plane_contract)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    return {
        "module": "tests.unit.test_datum_plane_contract",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "successful": result.wasSuccessful(),
    }


# --- live stage (scheduled separately; requires --live --confirm-session-usable)


def require_manual_start(config_file: Path) -> None:
    """Driver-only precondition; never edits the user's startup configuration."""
    settings = json.loads(config_file.read_text(encoding="utf-8-sig"))
    if settings.get("auto_start_creo") is not False:
        raise ValueError(
            "Live acceptance requires config.json auto_start_creo=false; no client was started"
        )


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "post0100_datum_plane" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
    """Collect source evidence even when running from an extracted release."""
    from creo_mechdog.source_provenance import local_provenance as collect

    return collect(
        ROOT,
        (
            "native/generic.cpp",
            "src/creo_mechdog/references.py",
            "src/creo_mechdog/schema.py",
            "server.py",
            "tests/unit/test_datum_plane_contract.py",
            "tools/test_datum_plane_contract.py",
        ),
    )


class LiveRunner:
    """Serial MCP client wrapper; one stop condition freezes the whole run."""

    def __init__(self, client: Any, output: Path) -> None:
        self.client = client
        self.output = output
        self.report: dict = {
            "task": "BUG-094",
            "started_at": time.time(),
            "native_acceptance": "running",
            "cases": [],
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
        record = {"tool": name, "args": copy.deepcopy(args), "started_at": time.time()}
        self.report["calls"].append(record)
        self.save()
        result = await self.client.call_tool(name, args)
        record["finished_at"] = time.time()
        record["is_error"] = result.is_error
        record["result"] = result.structured_content
        self.save()
        if result.is_error:
            raise RuntimeError(f"{name}: {result.content}")
        return result.structured_content

    async def expect_rejection(self, name: str, args: dict, fragment: str) -> dict:
        record = {"tool": name, "args": copy.deepcopy(args), "started_at": time.time()}
        self.report["calls"].append(record)
        self.save()
        result = await self.client.call_tool(name, args)
        record["finished_at"] = time.time()
        record["is_error"] = result.is_error
        record["content"] = str(result.content)
        self.save()
        assert result.is_error, (name, result.structured_content)
        assert fragment in str(result.content), (name, record["content"])
        assert "job_id" not in (result.structured_content or {}), record
        return record

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

    async def run_job(self, name: str, args: dict, success: bool = True) -> dict:
        accepted = await self.call(name, args)
        deadline = time.monotonic() + 360
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError(accepted["job_id"])
            terminal = await self.call("creo_get_job", {"job_id": accepted["job_id"]})
            if terminal["status"] not in ("queued", "running"):
                break
            await asyncio.sleep(1)
        assert terminal["status"] == ("succeeded" if success else "failed"), terminal
        if success:
            assert terminal["result"]["saved_file_reloaded_and_verified"] is True, terminal
        else:
            assert terminal["result"]["rollback_succeeded"] is True, terminal
        return terminal

    async def snapshot(self, model_id: str) -> dict:
        from creo_mechdog.query_client import read_full_model

        return await read_full_model(self.call, model_id)

    def measured_plane(self, snapshot: dict, label: str) -> dict:
        aliases = snapshot.get("aliases") or {}
        assert label in aliases, {"labels": sorted(aliases)}
        feature_id = aliases[label]["feature_id"]
        # datum_planes entries carry the geometry id only; map feature -> geometry
        # through the inspection feature list the same way native reports it.
        feature = next(
            (f for f in snapshot["inspection"]["features"] if f.get("id") == feature_id), None
        )
        assert feature is not None, {
            "feature_id": feature_id,
            "features": [f.get("id") for f in snapshot["inspection"]["features"]],
        }
        geometry_ids = {item["id"] for item in feature.get("geometry_items") or []}
        planes = [p for p in snapshot["inspection"]["datum_planes"] if p.get("id") in geometry_ids]
        assert len(planes) == 1, planes
        return planes[0]

    def measured_axis(self, snapshot: dict, label: str) -> dict:
        aliases = snapshot.get("aliases") or {}
        assert label in aliases, {"labels": sorted(aliases)}
        feature_id = aliases[label]["feature_id"]
        axes = [a for a in snapshot["inspection"]["datum_axes"] if a["feature_id"] == feature_id]
        assert len(axes) == 1, axes
        axis = axes[0]
        assert axis["geometry_known"] and axis["data_query_code"] == axis["line_query_code"] == 0, (
            axis
        )
        return axis

    def check_plane(
        self,
        snapshot: dict,
        label: str,
        normal_oracle: list,
        on_axis: dict | None,
        constant: float | None,
    ) -> dict:
        plane = self.measured_plane(snapshot, label)
        parallel(plane["normal"], normal_oracle)
        if on_axis is not None:
            on_line(plane["origin"], on_axis["origin"], on_axis["direction"])
        if constant is not None:
            near(plane_constant(plane, normal_oracle), constant)
        return plane


async def live(output: Path, run_id: str) -> int:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=60,
    ) as client:
        runner = LiveRunner(client, output)
        runner.report["run_id"] = run_id
        runner.save()
        try:
            await runner.wait_ready()
            assert (await runner.call("creo_session_status", {}))["connected"]

            # Fresh part: a datum axis through the X and Y datum planes. Its
            # actual direction is read from inspection, never assumed from a
            # label; both +Z and -Z orientations feed the same oracle.
            first = await runner.run_job(
                "creo_execute_plan",
                {
                    "operations": [
                        {
                            "op": "datum_axis",
                            "label": "rotation_axis",
                            "references": [
                                {"kind": "datum_plane", "axis": "x"},
                                {"kind": "datum_plane", "axis": "y"},
                            ],
                        }
                    ]
                },
            )
            model_id = first["model_id"]
            snap = await runner.snapshot(model_id)
            axis = runner.measured_axis(snap, "rotation_axis")
            near(abs(dot(axis["direction"], [0, 0, 1])), 1)
            on_line([0, 0, 0], axis["origin"], axis["direction"])
            runner.report["measured_axis"] = {
                "origin": axis["origin"],
                "direction": axis["direction"],
            }

            reference = {"kind": "datum_plane", "axis": "x"}
            base_normal = [1.0, 0.0, 0.0]

            # plan entry: +/-54 deg about the measured axis, zero angle.
            angled = [
                ("tilt_p54", REPORTED_ANGLE_DEG),
                ("tilt_m54", -REPORTED_ANGLE_DEG),
                ("tilt_zero", 0.0),
            ]
            revision = first["revision"]
            for label, angle in angled:
                terminal = await runner.run_job(
                    "creo_execute_plan",
                    {
                        "model_id": model_id,
                        "expected_revision": revision,
                        "operations": [
                            datum_plane_op(
                                label=label,
                                reference=copy.deepcopy(reference),
                                angle=angle,
                                axis={"kind": "datum_axis_feature", "label": "rotation_axis"},
                            )
                        ],
                    },
                )
                revision = terminal["revision"]
                snap = await runner.snapshot(model_id)
                oracle = rotate_normal(base_normal, axis["origin"], axis["direction"], angle)
                runner.report["cases"].append(
                    {
                        "case": f"plan_angle_{angle:g}",
                        "job_id": terminal["job_id"],
                        "plane": runner.check_plane(snap, label, oracle, axis, 0.0),
                    }
                )
            # +54 and -54 must not collapse into the same plane orientation.
            p54 = next(
                c["plane"]["normal"] for c in runner.report["cases"] if c["case"] == "plan_angle_54"
            )
            m54 = next(
                c["plane"]["normal"]
                for c in runner.report["cases"]
                if c["case"] == "plan_angle_-54"
            )
            assert abs(dot(unit(p54), unit(m54))) < 1 - 1e-6, (p54, m54)

            offset_terminal = await runner.run_job(
                "creo_execute_plan",
                {
                    "model_id": model_id,
                    "expected_revision": revision,
                    "operations": [
                        datum_plane_op(
                            label="off10", reference=copy.deepcopy(reference), offset=10.0
                        )
                    ],
                },
            )
            revision = offset_terminal["revision"]
            snap = await runner.snapshot(model_id)
            runner.report["cases"].append(
                {
                    "case": "plan_offset_only",
                    "job_id": offset_terminal["job_id"],
                    "plane": runner.check_plane(snap, "off10", base_normal, None, 10.0),
                }
            )

            # Explicit offset measured from the previously rotated plane.
            rotated_terminal = await runner.run_job(
                "creo_execute_plan",
                {
                    "model_id": model_id,
                    "expected_revision": revision,
                    "operations": [
                        datum_plane_op(
                            label="tilted_offset",
                            reference={"kind": "datum_feature", "label": "tilt_p54"},
                            offset=10.0,
                        )
                    ],
                },
            )
            revision = rotated_terminal["revision"]
            snap = await runner.snapshot(model_id)
            runner.report["cases"].append(
                {
                    "case": "plan_offset_after_rotation",
                    "job_id": rotated_terminal["job_id"],
                    "plane": runner.check_plane(snap, "tilted_offset", p54, None, 10.0),
                }
            )

            # Standalone tool entry: same contract, same oracle.
            tool_terminal = await runner.run_job(
                "creo_datum_plane",
                {
                    "model_id": model_id,
                    "expected_revision": revision,
                    "label": "tool_m54",
                    "reference": copy.deepcopy(reference),
                    "offset": 0.0,
                    "angle": -REPORTED_ANGLE_DEG,
                    "axis": {"kind": "datum_axis_feature", "label": "rotation_axis"},
                },
            )
            revision = tool_terminal["revision"]
            snap = await runner.snapshot(model_id)
            runner.report["cases"].append(
                {
                    "case": "tool_angle_-54",
                    "job_id": tool_terminal["job_id"],
                    "plane": runner.check_plane(
                        snap,
                        "tool_m54",
                        rotate_normal(
                            base_normal, axis["origin"], axis["direction"], -REPORTED_ANGLE_DEG
                        ),
                        axis,
                        0.0,
                    ),
                }
            )

            # Rejections: no dispatched job, no new feature, revision unchanged.
            planes_before = len((await runner.snapshot(model_id))["inspection"]["datum_planes"])
            rejections = [
                (
                    "creo_datum_plane",
                    {
                        "model_id": model_id,
                        "expected_revision": revision,
                        "label": "combined_rejected",
                        "reference": copy.deepcopy(reference),
                        "offset": REPORTED_OFFSET_MM,
                        "angle": REPORTED_ANGLE_DEG,
                        "axis": {"kind": "datum_axis_feature", "label": "rotation_axis"},
                    },
                    "nonzero offset",
                ),
                (
                    "creo_execute_plan",
                    {
                        "model_id": model_id,
                        "expected_revision": revision,
                        "operations": [datum_plane_op(reference={"offset": 5.0})],
                    },
                    "before a job is dispatched",
                ),
                (
                    "creo_execute_plan",
                    {
                        "model_id": model_id,
                        "expected_revision": revision,
                        "operations": [
                            datum_plane_op(
                                label="plane_axis_rejected",
                                angle=30,
                                axis={"kind": "datum_feature", "label": "off10"},
                            )
                        ],
                    },
                    "angle axis",
                ),
            ]
            for tool, args, fragment in rejections:
                await runner.expect_rejection(tool, args, fragment)
            snap = await runner.snapshot(model_id)
            assert len(snap["inspection"]["datum_planes"]) == planes_before, snap["inspection"][
                "datum_planes"
            ]
            assert snap["revision"] == revision, (snap["revision"], revision)
            runner.report["rejection_cases"] = [
                {"tool": tool, "fragment": fragment} for tool, _, fragment in rejections
            ]
            runner.report["native_acceptance"] = "passed"
        except Exception as error:
            runner.report.update(
                native_acceptance="failed", error=f"{type(error).__name__}: {error}"
            )
            raise
        finally:
            runner.save()
    return 0


def write_offline_report(output: Path, run_id: str, results: dict) -> dict:
    report = {
        "task": "BUG-094 / DEV-053 P06",
        "scope": "datum_plane reference kind, angle-axis selection, angle/offset contract",
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: shared admission matrix, tool description contract and "
            "native source guard validated. No Toolkit connection, no build, no native "
            "geometry; live execution is scheduled separately by the orchestrator."
        ),
        "checks": results,
        "unit_module": run_unit_module(),
        "provenance": local_provenance(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.live and not args.confirm_session_usable:
        print("live runs require --confirm-session-usable", file=sys.stderr)
        return 2
    if args.live:
        run_id = new_run_id()
        return asyncio.run(live(resolve_output(args.output, run_id), run_id))

    run_id = new_run_id()
    output = resolve_output(args.output, run_id)
    results = {
        "validation_matrix": check_validation_matrix(),
        "tool_description": check_tool_description(),
        "native_source_guard": check_native_source(),
    }
    report = write_offline_report(output, run_id, results)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name("report.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"report_sha256: {digest}")
    print(f"unit_module: {report['unit_module']}")
    return 0 if report["unit_module"]["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
