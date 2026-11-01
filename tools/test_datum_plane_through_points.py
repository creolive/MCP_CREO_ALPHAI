"""FEAT-053: datum_plane three-point form ({kind:'through_points'}).

Default execution is strictly offline. Offline mode only validates the input
plans (including the explicit conversion of the external 0.10.0 package forms),
the triangle judgment oracle and the readback assertion logic: it creates no
MCP client, calls no Toolkit function, connects to no Creo session and claims
no native result. Live mode requires *both* ``--live`` and
``--confirm-session-usable`` and a config with ``auto_start_creo`` false; it
reuses the readiness and provenance pattern of ``tools/test_dev048_plane_frame.py``.

The judgment constants below mirror the native checks in ``native/generic.cpp``
(pre-creation coordinate readback and post-creation verification). They are
dimensionless ratios or millimeter values documented in
``docs/work-items/FEAT-053.md``; the offline unit tests pin both sides.
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
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creo_mechdog.schema import validate_operations  # noqa: E402
from tools.test_t05_native import cross, dot, near, require_manual_start, unit  # noqa: E402

THROUGH_POINTS_KIND = "through_points"
# Repeated points: the shortest side may not vanish relative to the triangle's
# own scale (the longest side). Dimensionless, so the verdict never depends on
# the absolute world-coordinate size (FEAT-053).
DUPLICATE_RATIO_TOLERANCE = 1e-9
# Near-collinear: the smallest altitude divided by the longest side must stay
# above this ratio, otherwise the plane normal cannot be reconstructed reliably
# from the three points. Dimensionless and scale-free (FEAT-053).
COLLINEAR_ALTITUDE_RATIO_TOLERANCE = 1e-6
# Post-creation: each point's distance to the created plane must stay below
# max(floor, ratio * longest side), reported in millimeters.
DISTANCE_TOLERANCE_FLOOR_MM = 1e-6
DISTANCE_RELATIVE_RATIO = 1e-9
# Post-creation: |abs(dot(plane normal, (B-A)x(C-A))) - 1| must stay below this
# dimensionless bound. Sign is ignored on purpose: reversing the point order
# flips the cross product but names the same geometric plane.
ALIGNMENT_TOLERANCE = 1e-9

RUN_TAG = uuid.uuid4().hex[:6]

# Offline fixture copies of the external smoke_3pt_min_repro.json geometry
# (0.10.0 evening package, mm). The live path builds its own plans from these.
SMOKE_POINTS = {
    "dpa0": [-95.191114, 40.0, -88.395141],
    "dpb0": [95.191114, 40.0, 88.395141],
    "dpd0": [94.701973, 50.416667, 89.27114],
}
SMOKE_SOURCE = (
    ROOT
    / "docs"
    / "validation"
    / "feedback-0.10.0-2026-11-01"
    / "originals"
    / "06_P12_v12_配方"
    / "smoke_3pt_min_repro.json"
)


def distance_tolerance_mm(longest_side_mm: float) -> float:
    """Scale-aware acceptance bound for point-to-plane distances (mm)."""
    return max(DISTANCE_TOLERANCE_FLOOR_MM, DISTANCE_RELATIVE_RATIO * longest_side_mm)


def _vectors(points: list) -> tuple[list, list, list]:
    if not isinstance(points, (list, tuple)) or len(points) != 3:
        raise ValueError("classify_points requires exactly three points")
    a, b, c = (list(p) for p in points)
    for p in (a, b, c):
        if not isinstance(p, (list, tuple)) or len(p) != 3:
            raise ValueError("each point must be a numeric 3D position")
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in p):
            raise ValueError("point coordinates must be finite real numbers")
    return a, b, c


def triangle_geometry(points: list) -> dict:
    """Side lengths, longest side and smallest altitude of the point triangle."""
    a, b, c = _vectors(points)
    ab = [b[i] - a[i] for i in range(3)]
    bc = [c[i] - b[i] for i in range(3)]
    ca = [a[i] - c[i] for i in range(3)]
    sides = [math.sqrt(dot(v, v)) for v in (ab, bc, ca)]
    longest = max(sides)
    ac = [c[i] - a[i] for i in range(3)]
    normal = cross(ab, ac)
    area2 = math.sqrt(dot(normal, normal))
    min_altitude = area2 / longest if longest > 0 else 0.0
    return {
        "sides": sides,
        "longest_side": longest,
        "min_altitude": min_altitude,
        "min_altitude_ratio": min_altitude / longest if longest > 0 else 0.0,
    }


def classify_points(points: list) -> dict:
    """Mirror of the native pre-creation judgment.

    Returns the geometry plus a classification of
    ``ok`` / ``repeated_points`` / ``nearly_collinear`` / ``undecidable``.
    """
    try:
        geometry = triangle_geometry(points)
    except ValueError as error:
        return {"classification": "undecidable", "reason": str(error)}
    longest = geometry["longest_side"]
    if not math.isfinite(longest) or longest <= 0:
        return {
            "classification": "undecidable",
            "reason": "the three points do not span a measurable triangle",
            "geometry": geometry,
        }
    if min(geometry["sides"]) <= DUPLICATE_RATIO_TOLERANCE * longest:
        return {
            "classification": "repeated_points",
            "reason": "two of the three points coincide within tolerance",
            "geometry": geometry,
        }
    if geometry["min_altitude"] <= COLLINEAR_ALTITUDE_RATIO_TOLERANCE * longest:
        return {
            "classification": "nearly_collinear",
            "reason": "the three points are nearly collinear and do not determine a plane",
            "geometry": geometry,
        }
    return {"classification": "ok", "geometry": geometry}


def convert_plane_operation(op: dict) -> dict:
    """Explicitly convert an external 0.10.0 package datum_plane into the contract.

    Accepted input forms are ``{"thru_points": [...]}`` inside ``reference``
    (02/03 report style) and a bare ``thru_points`` key on the operation (04
    patch style). Both become ``reference={"kind":"through_points","points":[...]}``.
    The executor-internal ``{"kind":"datum_point_feature","label":...}`` target
    cannot be converted here (it names one point of a three-point form) and is
    refused. Already-contract references pass through unchanged.
    """
    if not isinstance(op, dict) or op.get("op") != "datum_plane":
        raise ValueError("convert_plane_operation expects a datum_plane operation")
    converted = copy.deepcopy(op)
    if "thru_points" in converted:
        if "reference" in converted:
            raise ValueError(
                "a datum_plane cannot carry both a reference and a direct thru_points key; "
                f"convert it to reference={{{THROUGH_POINTS_KIND!r}:'...', 'points':[...]}}"
            )
        raw = converted.pop("thru_points")
        converted["reference"] = {"thru_points": raw}
    reference = converted.get("reference")
    if isinstance(reference, dict) and "thru_points" in reference and "kind" not in reference:
        raw = reference["thru_points"]
        converted["reference"] = {"kind": THROUGH_POINTS_KIND, "points": copy.deepcopy(raw)}
    if isinstance(reference, dict) and reference.get("kind") == "datum_point_feature":
        raise ValueError(
            "{kind:'datum_point_feature',label:...} is the executor-internal single-point "
            "resolution target and cannot be converted in place; build the three-point form "
            f"reference={{{THROUGH_POINTS_KIND!r}:'through_points','points':[label_a,label_b,label_c]}}"
        )
    return converted


def converted_smoke_operations() -> list[dict]:
    """The external smoke_3pt_min_repro.json plan with the plane reference converted."""
    raw = json.loads(SMOKE_SOURCE.read_text(encoding="utf-8"))
    return [
        convert_plane_operation(op) if op.get("op") == "datum_plane" else copy.deepcopy(op)
        for op in raw
    ]


def plane_op(label: str = "pl00a", points: list | None = None, **overrides) -> dict:
    op = {
        "op": "datum_plane",
        "label": label,
        "reference": {
            "kind": THROUGH_POINTS_KIND,
            "points": list(points or ["dpa0", "dpb0", "dpd0"]),
        },
    }
    op.update(overrides)
    return op


def points_op(label: str, positions: list) -> dict:
    return {
        "op": "datum_points",
        "label": label,
        "points": [
            {"name": f"p{index}", "position": list(position)}
            for index, position in enumerate(positions)
        ],
    }


def smoke_points_ops() -> list[dict]:
    return [points_op(label, [position]) for label, position in SMOKE_POINTS.items()]


def check_readback(detail: dict, expected_point_ids: list[int]) -> dict:
    """Assert the native readback evidence of a created three-point plane.

    Checks the three documented assertions (FEAT-053): every point lies on the
    plane, the plane normal is equivalent to the cross product of the point
    legs, and the created feature's constraints reference exactly the expected
    single points. Raises on any violation; returns a summary otherwise.
    """
    frame = detail["plane_frame"]
    precheck = detail["precheck"]
    verification = detail["verification"]
    assert precheck["classification"] == "ok", precheck
    near(math.sqrt(dot(frame["normal"], frame["normal"])), 1.0, 1e-9)
    longest = precheck["longest_side"]
    tolerance = distance_tolerance_mm(longest)
    assert verification["distance_tolerance"] == tolerance, verification
    for distance in verification["point_distances"]:
        assert distance <= tolerance, (distance, tolerance)
    assert verification["max_point_distance"] <= tolerance, verification
    positions = [entry["position"] for entry in detail["points"]]
    ab = [positions[1][i] - positions[0][i] for i in range(3)]
    ac = [positions[2][i] - positions[0][i] for i in range(3)]
    expected_normal = unit(cross(ab, ac))
    alignment = dot(expected_normal, frame["normal"])
    assert abs(abs(verification["normal_alignment"]) - 1) <= ALIGNMENT_TOLERANCE, verification
    assert abs(abs(alignment) - 1) <= ALIGNMENT_TOLERANCE, (alignment, frame["normal"])
    assert verification["alignment_tolerance"] == ALIGNMENT_TOLERANCE, verification
    constraints = verification["constraints"]
    assert verification["constraint_count"] == 3, verification
    status = verification.get("references_status") or {}
    if status.get("available") is False:
        assert status.get("reason"), verification
        return {
            "max_point_distance_mm": verification["max_point_distance"],
            "normal_alignment": verification["normal_alignment"],
            "references_available": False,
            "references_unavailable_reason": status.get("reason"),
            "constraint_count": verification["constraint_count"],
        }
    assert verification["references_ok"] is True, verification
    assert verification["verified"] is True, verification
    assert [c["constr_type_name"] for c in constraints] == ["thru"] * 3, constraints
    assert [c["ref_type_name"] for c in constraints] == ["point"] * 3, constraints
    assert sorted(c["ref_id"] for c in constraints) == sorted(expected_point_ids), (
        constraints,
        expected_point_ids,
    )
    return {
        "max_point_distance_mm": verification["max_point_distance"],
        "normal_alignment": verification["normal_alignment"],
        "point_ids": sorted(expected_point_ids),
    }


def check_failure_invariant(before: dict, after: dict) -> None:
    """A refused or failed three-point plane must leave revision and features alone."""
    assert after["revision"] == before["revision"], (before["revision"], after["revision"])
    assert after.get("aliases") == before.get("aliases"), (
        before.get("aliases"),
        after.get("aliases"),
    )
    old = [f["id"] for f in before["inspection"]["features"]]
    new = [f["id"] for f in after["inspection"]["features"]]
    assert new == old, (old, new)


def local_provenance() -> dict:
    """Same shape as tools/test_dev048_plane_frame.local_provenance, for this driver."""
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
            "tools/test_datum_plane_through_points.py",
            "tests/unit/test_datum_plane_through_points.py",
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


class ThreePointPlaneAcceptance:
    """Live acceptance matrix for FEAT-053; only runs behind --live."""

    def __init__(self, client: Any, output: Path) -> None:
        self.client = client
        self.output = output
        self.report: dict = {
            "task": "FEAT-053",
            "scope": (
                "datum_plane through_points: main plane, oblique smoke geometry, large/small "
                "scale, reversed point order, wrong reference, repeated and nearly collinear "
                "points, failure invariants and save/erase/reload"
            ),
            "acceptance": "not_run",
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
        return model_id, snapshot

    def case_plan(self, labels: list[str], positions: list[list]) -> list[dict]:
        operations = [points_op(label, [position]) for label, position in zip(labels, positions)]
        operations.append(plane_op(points=labels))
        return operations

    async def valid_case(self, key: str, labels: list[str], positions: list[list]) -> None:
        model_id, before = await self.fresh_part(f"feat053_{key[:6]}_{RUN_TAG}")
        plan = self.case_plan(labels, positions)
        expected = classify_points(positions)
        assert expected["classification"] == "ok", expected
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
        operation = next(
            op for op in terminal["result"]["operations"] if op.get("label") == "pl00a"
        )
        expected_ids = [entry["point_id"] for entry in operation["points"]]
        summary = check_readback(operation, expected_ids)
        saved = await self.snapshot(model_id)
        for label in labels:
            entry = saved["aliases"][label]
            assert entry["op"] == "datum_points", entry
        plane_entry = saved["aliases"]["pl00a"]
        assert plane_entry["op"] == "datum_plane", plane_entry
        self.report["cases"].append(
            {
                "case": key,
                "labels": labels,
                "positions": positions,
                "classification": expected,
                "job_id": submitted["job_id"],
                "model_id": model_id,
                "revision": saved["revision"],
                "saved_file_reloaded_and_verified": True,
                "readback": summary,
                "plane_frame": operation["plane_frame"],
                "passed": True,
            }
        )
        self.save()

    async def refusal_case(self, key: str, plan: list[dict], marker: str) -> None:
        model_id, before = await self.fresh_part(f"feat053_{key[:6]}_{RUN_TAG}")
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
            assert marker in str(result.content), result.content
            rejection = "entry_refusal"
        else:
            job_id = result.structured_content["job_id"]
            terminal = await self.wait_job(job_id, "failed")
            assert terminal["result"]["rollback_succeeded"] is True, terminal
            detail = json.dumps(terminal.get("result"), ensure_ascii=False) + str(
                terminal.get("message")
            )
            assert marker in detail, terminal
            rejection = "native_refusal"
        after = await self.snapshot(model_id)
        check_failure_invariant(before, after)
        self.report["cases"].append(
            {
                "case": key,
                "model_id": model_id,
                "job_id": job_id,
                "rejection": rejection,
                "revision_before": before["revision"],
                "revision_after": after["revision"],
                "features_unchanged": True,
                "marker": marker,
                "refusal_verified": True,
            }
        )
        self.save()

    async def run_all(self) -> None:
        from tools.mcp_readiness import wait_for_startup

        self.report["capabilities"] = await self.call("creo_capabilities", {})
        self.report["environment"] = await self.call("creo_check_environment", {})
        self.report["acceptance"] = "starting"
        self.save()
        try:
            await wait_for_startup(self.client, self.report, self.output)
            status = await self.call("creo_session_status", {})
            assert status["connected"] is True, status
            self.report["acceptance"] = "running"
            await self.valid_case(
                "main_plane",
                ["mpa", "mpb", "mpc"],
                [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [0.0, 10.0, 0.0]],
            )
            await self.valid_case(
                "oblique_smoke", list(SMOKE_POINTS), [list(p) for p in SMOKE_POINTS.values()]
            )
            for key, factor in (("large_scale", 1000.0), ("small_scale", 0.001)):
                scaled = [[v * factor for v in p] for p in SMOKE_POINTS.values()]
                await self.valid_case(key, [f"{key[:2]}{i}" for i in range(3)], scaled)
            reversed_labels = list(SMOKE_POINTS)[::-1]
            reversed_positions = [list(SMOKE_POINTS[label]) for label in reversed_labels]
            await self.valid_case("reversed_order", reversed_labels, reversed_positions)
            wrong = self.case_plan(["wra", "wrb", "wrc"], [[0, 0, 0], [1, 0, 0], [0, 1, 0]])
            wrong[-1]["reference"] = {"kind": "datum_point_feature", "label": "wra"}
            await self.refusal_case("wrong_reference_form", wrong, "through_points")
            collinear = self.case_plan(
                ["cla", "clb", "clc"], [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
            )
            await self.refusal_case("nearly_collinear", collinear, "nearly collinear")
            repeated = self.case_plan(
                ["rpa", "rpb", "rpc"], [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
            )
            await self.refusal_case("repeated_points", repeated, "repeated")
            self.report.update(
                acceptance="passed",
                pending=[
                    "WorkBuddy black-box scenarios are a separate step",
                    "Creo 9/10 runs are not covered by this driver",
                ],
            )
        except Exception as error:
            self.report.update(
                acceptance="failed",
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
        runner = ThreePointPlaneAcceptance(client, output)
        runner.save()
        await runner.run_all()


def _rejected(callable_) -> None:
    try:
        callable_()
    except (AssertionError, ValueError):
        return
    raise AssertionError("Expected the check to reject this value")


def offline_checks() -> tuple[int, int]:
    """Validate plans, conversion, oracle and assertion logic; no native results."""
    passed = 0
    total = 0

    def check(name: str, callable_) -> None:
        nonlocal passed, total
        total += 1
        callable_()
        passed += 1
        print(f"  ok  {name}")

    def smoke_conversion() -> None:
        operations = converted_smoke_operations()
        dumped = validate_operations(operations)
        plane = next(op for op in dumped if op["op"] == "datum_plane")
        assert plane["reference"] == {
            "kind": "through_points",
            "points": ["dpa0", "dpb0", "dpd0"],
        }, plane
        raw = json.loads(SMOKE_SOURCE.read_text(encoding="utf-8"))
        raw_plane = next(op for op in raw if op.get("op") == "datum_plane")
        assert "thru_points" in raw_plane["reference"], raw_plane
        _rejected(
            lambda: convert_plane_operation(
                {
                    "op": "datum_plane",
                    "label": "p",
                    "reference": {"kind": "datum_point_feature", "label": "dpa0"},
                }
            )
        )

    def judgment_oracle() -> None:
        smoke = [list(p) for p in SMOKE_POINTS.values()]
        assert classify_points(smoke)["classification"] == "ok", smoke
        for factor in (1e-3, 1.0, 1e6):
            scaled = [[v * factor for v in p] for p in smoke]
            verdict = classify_points(scaled)
            assert verdict["classification"] == "ok", (factor, verdict)
        collinear = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        assert classify_points(collinear)["classification"] == "nearly_collinear", collinear
        near_collinear = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 1e-9, 0.0]]
        assert classify_points(near_collinear)["classification"] == "nearly_collinear"
        repeated = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        assert classify_points(repeated)["classification"] == "repeated_points"
        coincident = [[0.0, 0.0, 0.0]] * 3
        assert classify_points(coincident)["classification"] == "undecidable"
        _rejected(lambda: triangle_geometry([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]))
        _rejected(lambda: triangle_geometry([[0.0, 0.0, float("nan")], [1, 0, 0], [0, 1, 0]]))

    def readback_assertions() -> None:
        smoke = [list(p) for p in SMOKE_POINTS.values()]
        geometry = classify_points(smoke)["geometry"]
        ab = [smoke[1][i] - smoke[0][i] for i in range(3)]
        ac = [smoke[2][i] - smoke[0][i] for i in range(3)]
        normal = unit(cross(ab, ac))
        detail = {
            "plane_frame": {"surface_id": 47, "normal": normal, "origin": list(smoke[0])},
            "precheck": {"classification": "ok", **geometry},
            "points": [
                {"label": label, "feature_id": i + 7, "point_id": 70 + i, "position": position}
                for i, (label, position) in enumerate(zip(SMOKE_POINTS, smoke))
            ],
            "verification": {
                "point_distances": [0.0, 0.0, 0.0],
                "max_point_distance": 0.0,
                "distance_tolerance": distance_tolerance_mm(geometry["longest_side"]),
                "normal_alignment": 1.0,
                "alignment_tolerance": ALIGNMENT_TOLERANCE,
                "constraint_count": 3,
                "constraints": [
                    {
                        "constr_type": 0,
                        "constr_type_name": "thru",
                        "ref_type_name": "point",
                        "ref_id": ref_id,
                    }
                    for ref_id in (70, 71, 72)
                ],
                "references_ok": True,
                "verified": True,
            },
        }
        summary = check_readback(detail, [70, 71, 72])
        assert summary["point_ids"] == [70, 71, 72], summary
        flipped = copy.deepcopy(detail)
        flipped["verification"]["normal_alignment"] = -1.0
        flipped["plane_frame"]["normal"] = [-v for v in normal]
        check_readback(flipped, [70, 71, 72])
        far = copy.deepcopy(detail)
        far["verification"]["point_distances"] = [0.0, 0.5, 0.0]
        far["verification"]["max_point_distance"] = 0.5
        _rejected(lambda: check_readback(far, [70, 71, 72]))
        skew = copy.deepcopy(detail)
        skew["verification"]["normal_alignment"] = 0.99
        _rejected(lambda: check_readback(skew, [70, 71, 72]))
        wrong_refs = copy.deepcopy(detail)
        wrong_refs["verification"]["constraints"][0]["ref_id"] = 73
        _rejected(lambda: check_readback(wrong_refs, [70, 71, 72]))
        wrong_type = copy.deepcopy(detail)
        wrong_type["verification"]["constraints"][1]["ref_type_name"] = "axis"
        _rejected(lambda: check_readback(wrong_type, [70, 71, 72]))

    def failure_invariants() -> None:
        before = {
            "revision": 2,
            "aliases": {"dpa0": {"feature_id": 7, "op": "datum_points"}},
            "inspection": {"features": [{"id": 5}, {"id": 7}]},
        }
        check_failure_invariant(before, copy.deepcopy(before))
        bumped = copy.deepcopy(before)
        bumped["revision"] = 3
        _rejected(lambda: check_failure_invariant(before, bumped))
        grown = copy.deepcopy(before)
        grown["inspection"]["features"] = [{"id": 5}, {"id": 7}, {"id": 9}]
        _rejected(lambda: check_failure_invariant(before, grown))

    check("external smoke plan converts to the kind contract and validates", smoke_conversion)
    check("triangle judgment is scale-free and rejects bad triples", judgment_oracle)
    check("readback assertions accept real frames and reject drift", readback_assertions)
    check("failure invariants require revision and features unchanged", failure_invariants)
    return passed, total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "build/feat053_through_points_live.json"
    )
    args = parser.parse_args(argv)
    if not (args.live and args.confirm_session_usable):
        if args.live or args.confirm_session_usable:
            print("both --live and --confirm-session-usable are required", file=sys.stderr)
            return 2
        passed, total = offline_checks()
        print(f"offline checks: {passed}/{total} passed (no native result claimed)")
        return 0 if passed == total else 1
    asyncio.run(live(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
