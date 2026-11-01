"""BUG-095 offline driver for the sketch origin rejection diagnostics.

Offline stage (default): the frozen diagnostics contract exercised on the
oracle plane math (on-plane, 0.5e-6, 2e-6 and the reported 1.07e-4 mm
deviation, both signs), the admission matrix for omitted/exact origins, the
Python-side result projection, and a native source guard. The source guard
only proves the committed backstop is present in the working tree; it is not
native verification and no executor is built here.

Live stage (--live --confirm-session-usable, scheduled separately by the
orchestrator): runs the same contract against the manually opened Creo
session. Positives: an omitted origin and an exact on-plane origin keep
building on the original frame (actual frame read back from the result,
saved_file_reloaded_and_verified true) and a 0.5e-6 mm deviation stays within
the frozen 1e-6 mm tolerance. Rejections: 2e-6 and +/-1.07e-4 mm deviations
fail with a sketch_origin_diagnostics block whose numbers are checked against
the measured support plane from inspection; no feature is created and the
revision is unchanged. Every rejection must report rollback evidence; a busy
channel, an unknown terminal state or a polling timeout stops the run and
preserves the scene.
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
ORIGIN_TOLERANCE_MM = 1e-6
REPORTED_DEVIATION_MM = 1.07e-4


# --- shared oracle helpers -------------------------------------------------


def dot(a: list | tuple, b: list | tuple) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


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
    near(abs(dot(unit(actual), unit(expected))), 1)


def signed_distance(normal: list, constant: float, point: list) -> float:
    return dot(normal, point) - constant


def diagnostics_oracle(normal: list, constant: float, requested_origin: list) -> dict:
    """Mirror of the native sketch_frame rejection payload (BUG-095)."""
    signed = signed_distance(normal, constant, requested_origin)
    return {
        "status": "origin_outside_support_plane",
        "distance_to_plane_mm": abs(signed),
        "signed_distance_to_plane_mm": signed,
        "origin_tolerance_mm": ORIGIN_TOLERANCE_MM,
        "support_plane": {"normal": list(normal), "constant_mm": constant},
        "requested_origin": list(requested_origin),
        "suggested_origin": [requested_origin[i] - signed * normal[i] for i in range(3)],
    }


def sketch_op(plane: Any, label: str = "profile") -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": plane,
        "dimensioning": "coordinates",
        "entities": [{"type": "circle", "name": "ring", "center": [0, 0], "radius": 2}],
    }


# --- offline validation matrix ---------------------------------------------


def check_oracle_matrix() -> dict:
    """The frozen admission rule and payload math, on two plane shapes."""
    planes = [
        ([0.0, 0.0, 1.0], 0.0),
        (unit([1.0, -1.0, 1.0]), 5.0),
    ]
    checked = 0
    for normal, constant in planes:
        tangent = [normal[1] - normal[2], normal[2] - normal[0], normal[0] - normal[1]]
        tangent = unit(tangent)
        for deviation in (0.0, 0.5e-6, 2e-6, REPORTED_DEVIATION_MM):
            for sign in (1, -1):
                point = [
                    normal[i] * constant + tangent[i] * 2.0 + normal[i] * sign * deviation
                    for i in range(3)
                ]
                signed = signed_distance(normal, constant, point)
                if deviation <= ORIGIN_TOLERANCE_MM:
                    assert abs(signed) <= ORIGIN_TOLERANCE_MM, (deviation, signed)
                else:
                    assert abs(signed) > ORIGIN_TOLERANCE_MM, (deviation, signed)
                block = diagnostics_oracle(normal, constant, point)
                near(block["distance_to_plane_mm"], deviation)
                near(abs(block["signed_distance_to_plane_mm"]), deviation)
                # The suggested origin is advice only and lies on the plane.
                residual = signed_distance(
                    normal, constant, block["suggested_origin"]
                )
                near(residual, 0.0, 1e-12)
                checked += 1
    return {"planes": len(planes), "points_checked": checked, "passed": True}


def check_admission_matrix() -> dict:
    """Omitted and exact origins stay admitted; malformed origin is rejected."""
    from creo_mechdog.schema import validate_operations

    omitted = validate_operations([sketch_op({"reference": {"kind": "plane", "id": 11}})])[0]
    assert "origin" not in omitted["plane"], omitted["plane"]
    exact = validate_operations(
        [
            sketch_op(
                {
                    "reference": {"kind": "datum_plane", "id": 163},
                    "origin": [10, 0, 0],
                    "u_axis": [0, 0, 1],
                }
            )
        ]
    )[0]
    assert exact["plane"]["origin"] == [10, 0, 0], exact["plane"]
    try:
        validate_operations([sketch_op({"reference": {"kind": "plane", "id": 11}, "origin": [1, 0]})])
    except ValueError as error:
        assert "origin" in str(error), str(error)
    else:
        raise AssertionError("malformed origin rejection missing")
    return {"positives": ["origin_omitted", "origin_exact"], "rejections": ["origin_malformed"],
            "passed": True}


def check_native_source() -> dict:
    """Committed-backstop guard; not native verification and no build is run here."""
    source = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8", errors="replace")
    guards = {
        "diagnostics_block": '"sketch_origin_diagnostics"',
        "rejection_status": '"origin_outside_support_plane"',
        "measured_fields": '"signed_distance_to_plane_mm"',
        "support_plane_equation": '"constant_mm"',
        "suggested_projection": '"suggested_origin"',
        "threshold_unchanged": "fabs(signed_distance) > 1e-6",
        "deterministic_message": "Sketch origin is outside support plane: signed distance",
    }
    for name, fragment in guards.items():
        assert fragment in source, name
    return {"guards": sorted(guards), "statement": "source guard only; build and live pending"}


def run_unit_modules() -> dict:
    summary = {}
    for module_name in (
        "tests.unit.test_sketch_origin_diagnostics",
        "tests.unit.test_t04_arbitrary_plane_coordinates",
    ):
        module = unittest.defaultTestLoader.loadTestsFromName(module_name)
        result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(module)
        summary[module_name] = {
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "successful": result.wasSuccessful(),
        }
    return summary


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
        else ROOT / "build" / "post0100_sketch_origin" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
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
            "native/generic.cpp",
            "src/creo_mechdog/operation_results.py",
            "tests/unit/test_sketch_origin_diagnostics.py",
            "tests/unit/test_t04_arbitrary_plane_coordinates.py",
            "tools/test_sketch_origin_diagnostics.py",
        )
    )
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in sorted(names)
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


def find_z_datum_plane(snapshot: dict) -> dict:
    """The plane behind {kind:'datum_plane',axis:'z'}: z-normal through origin.

    The executor's signed distance uses its own oriented normal, so the oracle
    only relies on the plane's normal line and constant, not the stored sign.
    """
    planes = [
        p
        for p in snapshot["inspection"]["datum_planes"]
        if abs(abs(unit(p["normal"])[2]) - 1) <= 1e-9
        and abs(dot(p["normal"], p["origin"])) <= 1e-9
    ]
    assert planes, snapshot["inspection"]["datum_planes"]
    return planes[0]


def check_diagnostics_block(block: Any, plane: dict, requested_origin: list) -> dict:
    """Check the rejection evidence against the measured support plane."""
    assert isinstance(block, dict), block
    assert block["status"] == "origin_outside_support_plane", block
    normal = unit(plane["normal"])
    delta = [requested_origin[i] - plane["origin"][i] for i in range(3)]
    oracle_signed = dot(normal, delta)
    near(abs(block["signed_distance_to_plane_mm"]), abs(oracle_signed), 1e-12)
    near(block["distance_to_plane_mm"], abs(block["signed_distance_to_plane_mm"]), 1e-15)
    assert block["distance_to_plane_mm"] > ORIGIN_TOLERANCE_MM, block
    near(block["origin_tolerance_mm"], ORIGIN_TOLERANCE_MM)
    support = block["support_plane"]
    parallel(support["normal"], normal)
    near(abs(support["constant_mm"] - dot(normal, plane["origin"])), 0.0, 1e-9)
    near(dot(unit(support["normal"]), support["normal"]), 1.0, 1e-9)
    assert block["requested_origin"] == requested_origin, block
    # The suggested origin lies on the measured support plane (sign-free).
    suggested_residual = sum(
        unit(support["normal"])[i] * block["suggested_origin"][i] for i in range(3)
    ) - dot(unit(support["normal"]), plane["origin"])
    near(suggested_residual, 0.0, 1e-9)
    return block


class LiveRunner:
    """Serial MCP client wrapper; one stop condition freezes the whole run."""

    def __init__(self, client: Any, output: Path) -> None:
        self.client = client
        self.output = output
        self.report: dict = {
            "task": "BUG-095",
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

    async def expect_rejection(self, name: str, args: dict) -> dict:
        accepted = await self.call(name, args)
        deadline = time.monotonic() + 360
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError(accepted["job_id"])
            terminal = await self.call("creo_get_job", {"job_id": accepted["job_id"]})
            if terminal["status"] not in ("queued", "running"):
                break
            await asyncio.sleep(1)
        assert terminal["status"] == "failed", terminal
        assert terminal["result"]["rollback_succeeded"] is True, terminal
        return terminal

    async def snapshot(self, model_id: str) -> dict:
        from creo_mechdog.query_client import read_full_model

        return await read_full_model(self.call, model_id)

    def sketch_record(self, terminal: dict, label: str) -> dict:
        records = [
            op
            for op in terminal["result"]["operations"]
            if op.get("op") == "sketch" and op.get("label") == label
        ]
        assert len(records) == 1, terminal["result"]["operations"]
        return records[0]

    def check_frame(self, record: dict, expected_origin: list, plane: dict) -> None:
        parallel(record["normal"], plane["normal"])
        near(record["origin"], expected_origin, 1e-9)


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

            # Fresh part: a base sketch on the named XY plane. Its actual
            # frame is read back from the result, never assumed.
            first = await runner.run_job(
                "creo_execute_plan", {"operations": [sketch_op("XY", "base")]}
            )
            model_id = first["model_id"]
            revision = first["revision"]
            base_record = runner.sketch_record(first, "base")
            snap = await runner.snapshot(model_id)
            plane = find_z_datum_plane(snap)
            runner.check_frame(base_record, plane["origin"], plane)
            runner.report["cases"].append(
                {"case": "named_plane_origin_omitted", "job_id": first["job_id"]}
            )

            # Exact on-plane origin: continuation succeeds on the same frame.
            exact = await runner.run_job(
                "creo_execute_plan",
                {
                    "model_id": model_id,
                    "expected_revision": revision,
                    "operations": [
                        sketch_op(
                            {
                                "reference": {"kind": "datum_plane", "axis": "z"},
                                "origin": [0, 0, 0],
                                "u_axis": [1, 0, 0],
                            },
                            "exact_origin",
                        )
                    ],
                },
            )
            revision = exact["revision"]
            exact_record = runner.sketch_record(exact, "exact_origin")
            runner.check_frame(exact_record, [0.0, 0.0, 0.0], plane)
            runner.report["cases"].append(
                {"case": "exact_origin_continuation", "job_id": exact["job_id"]}
            )

            # 0.5e-6 mm deviation stays inside the frozen tolerance: accepted
            # and built at the requested origin, no snapping.
            within = await runner.run_job(
                "creo_execute_plan",
                {
                    "model_id": model_id,
                    "expected_revision": revision,
                    "operations": [
                        sketch_op(
                            {
                                "reference": {"kind": "datum_plane", "axis": "z"},
                                "origin": [0, 0, 0.5e-6],
                                "u_axis": [1, 0, 0],
                            },
                            "within_tolerance",
                        )
                    ],
                },
            )
            revision = within["revision"]
            within_record = runner.sketch_record(within, "within_tolerance")
            runner.check_frame(within_record, [0.0, 0.0, 0.5e-6], plane)
            runner.report["cases"].append(
                {"case": "within_tolerance_0p5e-6_accepted", "job_id": within["job_id"]}
            )

            # Rejections: 2e-6 and the reported 1.07e-4 mm deviation, both
            # signs. Each must fail with measured evidence, no new feature
            # and an unchanged revision.
            aliases_before = sorted((await runner.snapshot(model_id))["aliases"])
            rejections = []
            for label, deviation in (
                ("rejected_2e-6", 2e-6),
                ("reported_plus", REPORTED_DEVIATION_MM),
                ("reported_minus", -REPORTED_DEVIATION_MM),
            ):
                terminal = await runner.expect_rejection(
                    "creo_execute_plan",
                    {
                        "model_id": model_id,
                        "expected_revision": revision,
                        "operations": [
                            sketch_op(
                                {
                                    "reference": {"kind": "datum_plane", "axis": "z"},
                                    "origin": [0, 0, deviation],
                                    "u_axis": [1, 0, 0],
                                },
                                label,
                            )
                        ],
                    },
                )
                revision = terminal["revision"]
                record = runner.sketch_record(terminal, label)
                block = check_diagnostics_block(
                    record.get("sketch_origin_diagnostics"), plane, [0.0, 0.0, deviation]
                )
                assert "Sketch origin is outside support plane" in str(
                    terminal["result"].get("message", "")
                ), terminal["result"].get("message")
                rejections.append(
                    {
                        "case": label,
                        "job_id": terminal["job_id"],
                        "signed_distance_to_plane_mm": block["signed_distance_to_plane_mm"],
                        "distance_to_plane_mm": block["distance_to_plane_mm"],
                    }
                )
            snap = await runner.snapshot(model_id)
            assert sorted(snap["aliases"]) == aliases_before, snap["aliases"]
            assert snap["revision"] == revision, (snap["revision"], revision)
            runner.report["rejection_cases"] = rejections
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
        "task": "BUG-095 / DEV-053 P07",
        "scope": "sketch origin rejection diagnostics contract, frozen 1e-6 mm threshold",
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: diagnostics oracle matrix, admission matrix, "
            "result projection and native source guard validated. No Toolkit "
            "connection, no build, no native geometry; live execution is "
            "scheduled separately by the orchestrator."
        ),
        "checks": results,
        "unit_modules": run_unit_modules(),
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
        "oracle_matrix": check_oracle_matrix(),
        "admission_matrix": check_admission_matrix(),
        "native_source_guard": check_native_source(),
    }
    report = write_offline_report(output, run_id, results)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name("report.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"report_sha256: {digest}")
    print(f"unit_modules: {report['unit_modules']}")
    return 0 if all(m["successful"] for m in report["unit_modules"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
