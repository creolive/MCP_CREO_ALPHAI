"""DEV-048 T04: Right datum plane, u_axis +/-Z, 10x20 rectangle, +4 blind.

Default execution is strictly offline. Offline mode only validates the input
plans, the frame/box oracle and the assertion logic: it creates no MCP client,
calls no Toolkit function, connects to no Creo session and claims no native
result. Live mode requires *both* ``--live`` and ``--confirm-session-usable``
and a config with ``auto_start_creo`` false; it reuses the read-only readiness
observation and provenance pattern of ``tools/test_t05_native.py``.

The Right plane geometry ID is never hardcoded: the live path creates a new
metric part, inspects it and requires exactly one datum plane that passes the
global origin with a normal parallel to X.
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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creo_mechdog.schema import validate_operations  # noqa: E402
from tools.test_t05_native import cross, dot, near, require_manual_start, unit  # noqa: E402

RIGHT_AXIS = [1.0, 0.0, 0.0]
U_POSITIVE = [0, 0, 1]
U_NEGATIVE = [0, 0, -1]
U_PARALLEL = [1, 0, 0]
RECT_MIN = [0, 0]
RECT_MAX = [10, 20]
DEPTH = 4
VOLUME = (RECT_MAX[0] - RECT_MIN[0]) * (RECT_MAX[1] - RECT_MIN[1]) * DEPTH
PLANE_TOL = 1e-6

# Offline fixture only. The live path derives the ID from model inspection.
RIGHT_FIXTURE = [
    {"id": 163, "normal": [1.0, 0.0, 0.0], "origin": [0.0, 0.0, 0.0]},
    {"id": 164, "normal": [0.0, 1.0, 0.0], "origin": [0.0, 0.0, 0.0]},
    {"id": 165, "normal": [0.0, 0.0, 1.0], "origin": [0.0, 0.0, 0.0]},
    {"id": 166, "normal": [1.0, 0.0, 0.0], "origin": [10.0, 0.0, 0.0]},
]


def select_right_plane(datum_planes: list[dict]) -> dict:
    """Pick the unique datum plane through the origin whose normal is parallel to X."""
    candidates = []
    for plane in datum_planes:
        normal = unit(plane["normal"])
        if abs(abs(dot(normal, RIGHT_AXIS)) - 1.0) > PLANE_TOL:
            continue
        if abs(dot(normal, plane["origin"])) > PLANE_TOL:
            continue
        candidates.append(plane)
    if len(candidates) != 1:
        raise ValueError(
            "Expected exactly one Right datum plane through the global origin, "
            f"found {len(candidates)}: {candidates}"
        )
    return candidates[0]


def sketch_plan(plane_id: int, origin: list, u_axis: list) -> dict:
    return {
        "op": "sketch",
        "label": "profile",
        "plane": {
            "reference": {"kind": "datum_plane", "id": plane_id},
            "origin": list(origin),
            "u_axis": list(u_axis),
        },
        "entities": [
            {
                "type": "rectangle",
                "name": "box",
                "min": list(RECT_MIN),
                "max": list(RECT_MAX),
            }
        ],
        "dimensioning": "coordinates",
    }


def extrude_plan() -> dict:
    return {
        "op": "extrude",
        "label": "solid",
        "sketch": "profile",
        "depth": DEPTH,
        "mode": "add",
        "direction": "positive",
        "depth_type": "blind",
    }


def plan_for(plane_id: int, origin: list, u_axis: list) -> list[dict]:
    return [sketch_plan(plane_id, origin, u_axis), extrude_plan()]


def box_measurements(frame: dict) -> dict:
    """Map the rectangle corners through the reported frame; no native values used."""
    o, u, v, n = (frame[key] for key in ("origin", "u_axis", "v_axis", "normal"))
    vertices = [
        [o[i] + a * u[i] + b * v[i] + t * n[i] for i in range(3)]
        for a in (RECT_MIN[0], RECT_MAX[0])
        for b in (RECT_MIN[1], RECT_MAX[1])
        for t in (0, DEPTH)
    ]
    bounds = [
        [min(point[i] for point in vertices) for i in range(3)],
        [max(point[i] for point in vertices) for i in range(3)],
    ]
    center = [sum(point[i] for point in vertices) / len(vertices) for i in range(3)]
    return {"volume_mm3": float(VOLUME), "bbox": bounds, "center_of_gravity": center}


def check_frame(reported: dict, expect_u: list) -> None:
    """The reported frame must echo U, keep N parallel to X and satisfy V = N x U."""
    u, v, n = reported["u_axis"], reported["v_axis"], reported["normal"]
    near(u, expect_u)
    near(abs(dot(n, RIGHT_AXIS)), 1.0, PLANE_TOL)
    near(v, cross(n, expect_u))
    for axis in (n, u, v):
        near(math.sqrt(dot(axis, axis)), 1.0)
    near(dot(u, n), 0.0)
    near(dot(u, v), 0.0)
    near(dot(n, v), 0.0)


def check_measurements(snapshot: dict, expected: dict) -> None:
    state = snapshot["inspection"]
    assert state["length_unit"]["name"] == "mm", state["length_unit"]
    near(state["length_unit"]["scale_to_mm"], 1.0)
    assert state["volume_query_code"] == 0, state["volume_query_code"]
    near(state["volume_mm3"], expected["volume_mm3"])
    near(state["center_of_gravity"], expected["center_of_gravity"])
    bodies = [body for body in state["bodies"] if body.get("has_geometry")]
    assert len(bodies) == 1, bodies
    near(bodies[0]["bbox"], expected["bbox"])


def check_unchanged(before: dict, after: dict) -> None:
    assert after["revision"] == before["revision"], (before["revision"], after["revision"])
    assert after.get("aliases") == before.get("aliases"), (
        before.get("aliases"),
        after.get("aliases"),
    )
    old, new = before["inspection"], after["inspection"]
    near(new["volume_mm3"], old["volume_mm3"])
    near(new["center_of_gravity"], old["center_of_gravity"])
    old_bodies = [body for body in old["bodies"] if body.get("has_geometry")]
    new_bodies = [body for body in new["bodies"] if body.get("has_geometry")]
    assert len(new_bodies) == len(old_bodies), (old_bodies, new_bodies)
    for old_body, new_body in zip(old_bodies, new_bodies, strict=True):
        near(new_body["bbox"], old_body["bbox"])


def local_provenance() -> dict:
    """Same shape as tools/test_t05_native.local_provenance, for this driver."""
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
            "tools/test_dev048_plane_frame.py",
            "tests/unit/test_dev048_plane_frame.py",
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


class PlaneFrameAcceptance:
    def __init__(self, client: Any, output: Path) -> None:
        self.client = client
        self.output = output
        self.last_valid: dict | None = None
        self.report: dict = {
            "task": "DEV-048 T04",
            "scope": "Right datum plane; u_axis +/-Z; 0..10 x 0..20 rectangle; +4 blind",
            "plane_frame_matrix": "not_run",
            "native_acceptance": "not_run",
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

    async def _invoke(self, name: str, args: dict) -> Any:
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
        return result

    async def call(self, name: str, args: dict) -> dict:
        result = await self._invoke(name, args)
        if result.is_error:
            raise RuntimeError(f"{name}: {result.content}")
        return result.structured_content

    async def snapshot(self, model_id: str) -> dict:
        from creo_mechdog.query_client import read_full_model

        return await read_full_model(self.call, model_id)

    def alias(self, snapshot: dict, label: str) -> dict:
        aliases = snapshot.get("aliases") or {}
        assert label in aliases, {"snapshot_keys": sorted(snapshot), "aliases": aliases}
        return aliases[label]

    async def wait_job(self, job_id: str, expected: str, budget: float = 360) -> dict:
        deadline = time.monotonic() + budget
        while True:
            terminal = await self.call("creo_get_job", {"job_id": job_id})
            if terminal["status"] not in ("queued", "running"):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Job {job_id} did not reach a terminal state; do not resubmit")
            await asyncio.sleep(1)
        assert terminal["status"] == expected, terminal
        return terminal

    async def fresh_part(self, model_name: str) -> tuple[str, dict]:
        created = await self.call("creo_new_part", {"model_name": model_name})
        await self.wait_job(created["job_id"], "succeeded")
        model_id = created["model_id"]
        snapshot = await self.snapshot(model_id)
        assert snapshot["inspection"]["length_unit"]["name"] == "mm", snapshot["inspection"]
        assert not [b for b in snapshot["inspection"]["bodies"] if b.get("has_geometry")]
        return model_id, snapshot

    async def valid_case(self, key: str, u_axis: list, index: int) -> None:
        model_id, before = await self.fresh_part(f"dev048t04_{key[:2]}{index}")
        plane = select_right_plane(before["inspection"]["datum_planes"])
        plan = plan_for(plane["id"], plane["origin"], u_axis)
        submitted = await self.call(
            "creo_execute_plan",
            {
                "model_id": model_id,
                "expected_revision": before["revision"],
                "operations": plan,
            },
        )
        terminal = await self.wait_job(submitted["job_id"], "succeeded")
        assert terminal["result"]["saved_file_reloaded_and_verified"] is True, terminal
        saved = await self.snapshot(model_id)
        frame = self.alias(saved, "profile")
        check_frame(frame, u_axis)
        near(frame["origin"], plane["origin"])
        assert frame["surface_id"] == plane["id"], (frame["surface_id"], plane["id"])
        operation = next(
            op for op in terminal["result"]["operations"] if op.get("label") == "profile"
        )
        for field in ("origin", "normal", "u_axis", "v_axis"):
            near(operation[field], frame[field])
        assert operation["surface_id"] == plane["id"], operation
        expected = box_measurements(frame)
        check_measurements(saved, expected)
        bodies = [body for body in saved["inspection"]["bodies"] if body.get("has_geometry")]
        self.report["cases"].append(
            {
                "case": key,
                "u_axis_input": list(u_axis),
                "right_plane_id": plane["id"],
                "right_plane_normal": plane["normal"],
                "right_plane_origin": plane["origin"],
                "job_id": submitted["job_id"],
                "model_id": model_id,
                "revision": saved["revision"],
                "saved_file_reloaded_and_verified": True,
                "actual_frame": frame,
                "expected_volume_mm3": expected["volume_mm3"],
                "native_volume_mm3": saved["inspection"]["volume_mm3"],
                "expected_bbox": expected["bbox"],
                "actual_bbox": bodies[0]["bbox"],
                "expected_center_of_gravity": expected["center_of_gravity"],
                "actual_center_of_gravity": saved["inspection"]["center_of_gravity"],
                "passed": True,
            }
        )
        self.save()
        self.last_valid = {"model_id": model_id, "plane": plane, "snapshot": saved}

    async def parallel_case(self) -> None:
        assert self.last_valid is not None, "The parallel-U case reuses the last valid part"
        model_id = self.last_valid["model_id"]
        plane = self.last_valid["plane"]
        before = self.last_valid["snapshot"]
        plan = plan_for(plane["id"], plane["origin"], U_PARALLEL)
        result = await self._invoke(
            "creo_execute_plan",
            {
                "model_id": model_id,
                "expected_revision": before["revision"],
                "operations": plan,
            },
        )
        job_id = None
        if result.is_error:
            structured = result.structured_content or {}
            assert structured.get("status") != "busy", structured
            text = str(result.content)
            if not any(token in text for token in ("u_axis", "parallel")):
                raise RuntimeError(f"Entry refused for an unrelated reason: {text}")
            rejection = "entry_refusal"
        else:
            job_id = result.structured_content["job_id"]
            terminal = await self.wait_job(job_id, "failed")
            assert terminal["result"]["rollback_succeeded"] is True, terminal
            detail = json.dumps(terminal.get("result"), ensure_ascii=False) + str(
                terminal.get("message")
            )
            assert "parallel to the support plane normal" in detail, terminal
            rejection = "native_refusal"
        after = await self.snapshot(model_id)
        check_unchanged(before, after)
        self.report["cases"].append(
            {
                "case": "parallel_u_axis_refusal",
                "u_axis_input": list(U_PARALLEL),
                "right_plane_id": plane["id"],
                "model_id": model_id,
                "rejection": rejection,
                "job_id": job_id,
                "revision_before": before["revision"],
                "revision_after": after["revision"],
                "aliases_unchanged": True,
                "volume_unchanged_mm3": after["inspection"]["volume_mm3"],
                "geometry_passed": False,
                "refusal_verified": True,
            }
        )
        self.save()

    async def run_all(self) -> None:
        from tools.mcp_readiness import wait_for_startup

        self.report["capabilities"] = await self.call("creo_capabilities", {})
        self.report["environment"] = await self.call("creo_check_environment", {})
        self.report["plane_frame_matrix"] = "starting"
        self.save()
        try:
            await wait_for_startup(self.client, self.report, self.output)
            status = await self.call("creo_session_status", {})
            assert status["connected"] is True, status
            self.report["plane_frame_matrix"] = "running"
            await self.valid_case("u_positive_z", U_POSITIVE, 1)
            await self.valid_case("u_negative_z", U_NEGATIVE, 2)
            await self.parallel_case()
            self.report.update(
                plane_frame_matrix="passed",
                native_acceptance="partial",
                pending_native_acceptance=[
                    "This driver covers only the Right plane +/-Z instances",
                    "External Creo 10 reports are not reproduced by this local driver",
                ],
            )
        except Exception as error:
            self.report.update(
                plane_frame_matrix="failed",
                native_acceptance="failed",
                error=f"{type(error).__name__}: {error}",
            )
            raise
        finally:
            self.save()


async def live(output: Path) -> None:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=60,
    ) as client:
        runner = PlaneFrameAcceptance(client, output)
        runner.save()
        await runner.run_all()


def _rejected(callable_) -> None:
    try:
        callable_()
    except (AssertionError, ValueError):
        return
    raise AssertionError("Expected the check to reject this value")


def offline_checks() -> tuple[int, int]:
    """Validate plans and assertion logic only; nothing here is a native result."""
    passed = 0
    total = 0

    def check(name: str, callable_) -> None:
        nonlocal passed, total
        total += 1
        callable_()
        passed += 1
        print(f"  ok  {name}")

    plane = select_right_plane(RIGHT_FIXTURE)

    def selection() -> None:
        assert plane["id"] == 163, plane
        _rejected(lambda: select_right_plane([]))
        _rejected(lambda: select_right_plane(RIGHT_FIXTURE + [dict(RIGHT_FIXTURE[0])]))
        _rejected(lambda: select_right_plane([RIGHT_FIXTURE[3]]))

    def valid_plans() -> None:
        for u_axis in (U_POSITIVE, U_NEGATIVE):
            operations = validate_operations(plan_for(plane["id"], plane["origin"], u_axis))
            sketch, extrude = operations
            assert sketch["plane"]["reference"] == {"kind": "datum_plane", "id": 163}, sketch
            assert sketch["plane"]["u_axis"] == u_axis, sketch
            assert sketch["plane"]["origin"] == [0.0, 0.0, 0.0], sketch
            entity = sketch["entities"][0]
            assert entity["min"] == [0, 0] and entity["max"] == [10, 20], entity
            assert sketch["dimensioning"] == "coordinates", sketch
            assert extrude["op"] == "extrude", extrude
            assert extrude["label"] == "solid", extrude
            assert extrude["sketch"] == "profile", extrude
            assert extrude["depth"] == DEPTH, extrude
            assert extrude["mode"] == "add", extrude
            assert extrude["direction"] == "positive", extrude
            assert extrude["depth_type"] == "blind", extrude

    def parallel_plan() -> None:
        # Entry currently accepts a U parallel to the face normal, so the refusal
        # must come from the native boundary; the live driver accepts either.
        operations = validate_operations(plan_for(plane["id"], plane["origin"], U_PARALLEL))
        assert operations[0]["plane"]["u_axis"] == [1, 0, 0], operations[0]

    def oracle_positive_normal() -> None:
        frame = {
            "origin": [0, 0, 0],
            "normal": [1, 0, 0],
            "u_axis": [0, 0, 1],
            "v_axis": [0, -1, 0],
        }
        measured = box_measurements(frame)
        near(measured["volume_mm3"], 800.0)
        near(measured["bbox"], [[0, -20, 0], [4, 0, 10]])
        near(measured["center_of_gravity"], [2, -10, 5])

    def oracle_negative_normal() -> None:
        frame = {
            "origin": [0, 0, 0],
            "normal": [-1, 0, 0],
            "u_axis": [0, 0, 1],
            "v_axis": [0, 1, 0],
        }
        measured = box_measurements(frame)
        near(measured["volume_mm3"], 800.0)
        near(measured["bbox"], [[-4, 0, 0], [0, 20, 10]])
        near(measured["center_of_gravity"], [-2, 10, 5])

    def frame_checks() -> None:
        good = {
            "origin": [0, 0, 0],
            "normal": [1, 0, 0],
            "u_axis": [0, 0, 1],
            "v_axis": [0, -1, 0],
        }
        check_frame(good, U_POSITIVE)
        check_frame({**good, "normal": [-1, 0, 0], "v_axis": [0, 1, 0]}, U_POSITIVE)
        _rejected(lambda: check_frame({**good, "u_axis": [0, 0, -1]}, U_POSITIVE))
        _rejected(lambda: check_frame({**good, "normal": [0, 1, 0]}, U_POSITIVE))
        _rejected(lambda: check_frame({**good, "v_axis": [0, 1, 0]}, U_POSITIVE))
        _rejected(lambda: check_frame({**good, "u_axis": [0, 0, 2]}, U_POSITIVE))

    def measurement_checks() -> None:
        frame = {
            "origin": [0, 0, 0],
            "normal": [-1, 0, 0],
            "u_axis": [0, 0, -1],
            "v_axis": [0, -1, 0],
        }
        expected = box_measurements(frame)
        snapshot = {
            "revision": 1,
            "inspection": {
                "length_unit": {"name": "mm", "scale_to_mm": 1.0},
                "volume_query_code": 0,
                "volume_mm3": expected["volume_mm3"],
                "center_of_gravity": expected["center_of_gravity"],
                "bodies": [{"has_geometry": True, "bbox": expected["bbox"]}],
            },
        }
        check_measurements(snapshot, expected)
        bad_volume = copy.deepcopy(snapshot)
        bad_volume["inspection"]["volume_mm3"] = 799.0
        _rejected(lambda: check_measurements(bad_volume, expected))
        bad_bbox = copy.deepcopy(snapshot)
        bad_bbox["inspection"]["bodies"][0]["bbox"] = [[0, 0, 0], [4, 20, 10]]
        _rejected(lambda: check_measurements(bad_bbox, expected))
        bad_center = copy.deepcopy(snapshot)
        bad_center["inspection"]["center_of_gravity"] = [0, 0, 0]
        _rejected(lambda: check_measurements(bad_center, expected))

    def unchanged_checks() -> None:
        before = {
            "revision": 3,
            "aliases": {"profile": {"feature_id": 7}},
            "inspection": {
                "volume_mm3": 800.0,
                "center_of_gravity": [2, -10, 5],
                "bodies": [{"has_geometry": True, "bbox": [[0, -20, 0], [4, 0, 10]]}],
            },
        }
        check_unchanged(before, copy.deepcopy(before))
        bumped = copy.deepcopy(before)
        bumped["revision"] = 4
        _rejected(lambda: check_unchanged(before, bumped))
        resized = copy.deepcopy(before)
        resized["inspection"]["volume_mm3"] = 1600.0
        _rejected(lambda: check_unchanged(before, resized))

    check("select_right_plane picks one plane through the origin", selection)
    check("both +Z and -Z plans survive input validation", valid_plans)
    check("parallel U is currently rejected by the native boundary, not entry", parallel_plan)
    check("eight-corner oracle with N=+X", oracle_positive_normal)
    check("eight-corner oracle with N=-X", oracle_negative_normal)
    check("frame assertions accept U/N/V and reject bad frames", frame_checks)
    check("measurement assertions reject wrong volume, bbox or center", measurement_checks)
    check("unchanged assertions reject a revision or volume change", unchanged_checks)
    return passed, total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/dev048_t04_plane_frame.json")
    args = parser.parse_args(argv)
    if not (args.live and args.confirm_session_usable):
        if args.live or args.confirm_session_usable:
            reason = "both --live and --confirm-session-usable are required"
        else:
            reason = "no live flags given"
        print(f"OFFLINE ONLY ({reason}): no MCP client, no Toolkit call, no Creo connection.")
        passed, total = offline_checks()
        print(f"offline_checks={passed}/{total} passed")
        print("LIVE NOT RUN: no native geometry result was produced or claimed.")
        return 0
    asyncio.run(live(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
