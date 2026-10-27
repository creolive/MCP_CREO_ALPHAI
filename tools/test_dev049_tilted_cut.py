"""DEV-049 T04: R20 / 54deg / 4x6 tilted cut, six directed replay cases.

Default execution is strictly offline. Offline mode only validates the six
input plans and the independent volume oracle: it creates no MCP client, calls
no Toolkit function, connects to no Creo session and claims no native result.
Live mode requires *both* ``--live`` and ``--confirm-session-usable``.

Geometry basis (docs/development/0.6.1-FEEDBACK-PLAN-2026-10-27.md, section
"原斜槽的独立几何基准"): the base is an R20 disc on XY extruded +5, so
z in [0, 5]. The tilted plane normal is n = (cos54, sin54, 0), the sketch
U input is the original report's [0.809017, -0.587785, 0] and V = n x U = -Z.
The rectangle is u in [-4, 0], v in [-3, 3]; inside the disc the effective
height is 3.

Single direction expectation is ``3 * integral[-4,0] sqrt(400 - u^2) du =
238.390260127791 mm^3``; ``symmetric`` sweeps both sides and is exactly twice
that. The original report's ~478 is the bidirectional approximation and must
never be used as the single-direction expectation; the old 120/0 pair stays an
anomaly clue and must never be judged as passing.
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
from tools.test_t05_native import cross, dot, near, unit  # noqa: E402

# --- geometry basis -------------------------------------------------------

TILT_DEGREES = 54.0
BASE_RADIUS = 20.0
BASE_HEIGHT = 5.0
RECT_U = (-4.0, 0.0)
RECT_V = (-3.0, 3.0)
U_AXIS_INPUT = [0.809017, -0.587785, 0.0]

VOLUME_TOLERANCE = 0.01
ORACLE_CROSS_TOLERANCE = 1e-6
PLANE_TOL = 1e-6

STRATEGY_CODES = {"autodim": "ad", "coordinates": "co"}
DIRECTION_CODES = {"positive": "pos", "negative": "neg", "symmetric": "sym"}
DIRECTIONS = ("positive", "negative", "symmetric")
STRATEGIES = ("autodim", "coordinates")

# Offline fixture only. The live path derives the ID from model inspection; the
# original report's 74 and the older 2 are never reused as literals.
TILTED_FIXTURE = {
    "id": 911,
    "normal": [0.5877852522924731, 0.8090169943749475, 0.0],
    "origin": [0.0, 0.0, 0.0],
}


def tilted_normal() -> list[float]:
    """The support plane normal for a plane rotated TILT_DEGREES off the X plane."""
    angle = math.radians(TILT_DEGREES)
    return [math.cos(angle), math.sin(angle), 0.0]


def u_axis_normalized() -> list[float]:
    """The original report's U input, normalized; the raw value stays recorded."""
    return unit(U_AXIS_INPUT)


def v_axis() -> list[float]:
    """V is defined as n x u, which for this basis is -Z."""
    return cross(tilted_normal(), u_axis_normalized())


def effective_height() -> float:
    """Height of the rectangle that actually lies inside the z in [0, 5] disc.

    The sketch's V axis is -Z, so the rectangle's v range maps to z in
    [-v_max, -v_min]. The overlap with the base slab is the swept height.
    """
    z_low, z_high = -RECT_V[1], -RECT_V[0]
    overlap = min(z_high, BASE_HEIGHT) - max(z_low, 0.0)
    assert overlap > 0, (RECT_V, BASE_HEIGHT)
    return overlap


# --- independent volume oracle -------------------------------------------


def _chord_primitive(u: float) -> float:
    """Antiderivative of sqrt(R^2 - u^2) with respect to u."""
    radius = BASE_RADIUS
    return 0.5 * u * math.sqrt(radius * radius - u * u) + 0.5 * radius * radius * math.asin(
        u / radius
    )


def analytic_integral() -> float:
    """Closed form of height * integral[-4,0] sqrt(400 - u^2) du."""
    low, high = RECT_U
    span = _chord_primitive(high) - _chord_primitive(low)
    return effective_height() * span


def numeric_integral(panels: int = 2000) -> float:
    """Composite Simpson's rule over the same integrand; no closed form used."""
    low, high = RECT_U
    if panels < 2:
        raise ValueError("Simpson's rule needs at least 2 panels")
    if panels % 2:
        panels += 1

    def integrand(u: float) -> float:
        return math.sqrt(max(0.0, BASE_RADIUS * BASE_RADIUS - u * u))

    step = (high - low) / panels
    total = integrand(low) + integrand(high)
    for index in range(1, panels):
        total += (4.0 if index % 2 else 2.0) * integrand(low + index * step)
    return effective_height() * total * step / 3.0


def expected_volume(direction: str) -> float:
    """Single-direction volume for positive/negative; exactly twice for symmetric."""
    if direction not in DIRECTIONS:
        raise ValueError(f"Unknown cut direction: {direction}")
    single = analytic_integral()
    return 2.0 * single if direction == "symmetric" else single


def oracle_cross_check(panels: int = 2000) -> dict:
    """Run both integrations and bound their disagreement."""
    analytic = analytic_integral()
    numeric = numeric_integral(panels)
    difference = abs(analytic - numeric)
    assert difference <= ORACLE_CROSS_TOLERANCE, (analytic, numeric, difference)
    return {
        "analytic_single_mm3": analytic,
        "numeric_single_mm3": numeric,
        "abs_difference_mm3": difference,
        "cross_tolerance_mm3": ORACLE_CROSS_TOLERANCE,
        "panels": panels,
        "agrees": True,
    }


def judge_volume(direction: str, measured: float, tolerance: float = VOLUME_TOLERANCE) -> dict:
    """Score one measured removal against the independent expectation.

    This deliberately rejects the historical 120/0 anomaly pair and rejects a
    bidirectional value used as a single-direction expectation.
    """
    expected = expected_volume(direction)
    if not isinstance(measured, (int, float)) or not math.isfinite(measured):
        raise ValueError(f"Measured removal must be a finite number, got {measured!r}")
    error = abs(measured - expected)
    return {
        "direction": direction,
        "expected_mm3": expected,
        "measured_mm3": float(measured),
        "abs_error_mm3": error,
        "tolerance_mm3": tolerance,
        "passed": error <= tolerance,
    }


def validate_expectation(direction: str, claimed: float, tolerance: float = 1e-9) -> None:
    """Reject a claimed expectation that does not match the independent oracle.

    Guards against carrying the report's ~478 bidirectional approximation into
    a single-direction slot.
    """
    expected = expected_volume(direction)
    if not isinstance(claimed, (int, float)) or not math.isfinite(claimed):
        raise ValueError(f"Claimed expectation must be a finite number, got {claimed!r}")
    if abs(claimed - expected) > tolerance:
        raise ValueError(
            f"Claimed {direction} expectation {claimed} does not match the "
            f"independent oracle {expected}"
        )


# --- frame semantics ------------------------------------------------------


def check_frame(reported: dict, plane_normal: list | None = None) -> None:
    """The reported sketch frame must echo U, keep N parallel and V = N x U."""
    expect_n = tilted_normal() if plane_normal is None else plane_normal
    expect_u = u_axis_normalized()
    u, v, n = reported["u_axis"], reported["v_axis"], reported["normal"]

    near(u, expect_u)
    near(abs(dot(unit(n), unit(expect_n))), 1.0, PLANE_TOL)
    near(v, cross(unit(n), expect_u))
    for axis in (n, u, v):
        near(math.sqrt(dot(axis, axis)), 1.0)
    near(dot(u, n), 0.0)
    near(dot(u, v), 0.0)
    near(dot(n, v), 0.0)
    near(reported["origin"], [0.0, 0.0, 0.0])


def select_tilted_plane(datum_planes: list[dict]) -> dict:
    """Pick the unique datum plane through the origin with the tilted normal."""
    expect = unit(tilted_normal())
    candidates = []
    for plane in datum_planes:
        normal = unit(plane["normal"])
        if abs(abs(dot(normal, expect)) - 1.0) > PLANE_TOL:
            continue
        if abs(dot(normal, plane["origin"])) > PLANE_TOL:
            continue
        candidates.append(plane)
    if len(candidates) != 1:
        raise ValueError(
            "Expected exactly one tilted datum plane through the global origin, "
            f"found {len(candidates)}: {candidates}"
        )
    return candidates[0]


# --- input plans ----------------------------------------------------------


def setup_operations() -> list[dict]:
    """R20 disc extruded +5, then the Z axis and the 54 degree tilted plane."""
    return [
        {
            "op": "sketch",
            "label": "base_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "circle",
                    "name": "disc",
                    "center": [0.0, 0.0],
                    "radius": BASE_RADIUS,
                }
            ],
            "dimensioning": "coordinates",
        },
        {
            "op": "extrude",
            "label": "base_solid",
            "sketch": "base_profile",
            "depth": BASE_HEIGHT,
            "mode": "add",
            "direction": "positive",
            "depth_type": "blind",
        },
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
            "angle": TILT_DEGREES,
            "axis": {"kind": "datum_axis_feature", "label": "rotation_axis"},
        },
    ]


def slot_operations(case: dict, plane_id: int) -> list[dict]:
    """The 4x6 rectangle on the tilted plane and the through-all cut."""
    return [
        {
            "op": "sketch",
            "label": "slot_profile",
            "plane": {
                "reference": {"kind": "datum_plane", "id": plane_id},
                "origin": [0.0, 0.0, 0.0],
                "u_axis": list(U_AXIS_INPUT),
            },
            "entities": [
                {
                    "type": "rectangle",
                    "name": "slot",
                    "min": [RECT_U[0], RECT_V[0]],
                    "max": [RECT_U[1], RECT_V[1]],
                }
            ],
            "dimensioning": case["dimensioning"],
        },
        {
            "op": "extrude",
            "label": "slot_cut",
            "sketch": "slot_profile",
            "depth": BASE_HEIGHT,
            "mode": "cut",
            "direction": case["direction"],
            "depth_type": "through_all",
        },
    ]


def build_cases(run_tag: str) -> list[dict]:
    """Six cases: two dimensioning strategies x three cut directions."""
    cases = []
    for strategy in STRATEGIES:
        for direction in DIRECTIONS:
            code = f"{STRATEGY_CODES[strategy]}_{DIRECTION_CODES[direction]}"
            cases.append(
                {
                    "case": f"{strategy}_{direction}",
                    "dimensioning": strategy,
                    "direction": direction,
                    "model_name": f"dev049t04_{code}_{run_tag}",
                    "u_axis_input": list(U_AXIS_INPUT),
                    "u_axis_normalized": u_axis_normalized(),
                    "v_axis": v_axis(),
                    "expected_volume_mm3": expected_volume(direction),
                }
            )
    return cases


def validate_case_inputs(cases: list[dict]) -> None:
    """Every case must carry a legal plan and a unique, legal model name."""
    names = [case["model_name"] for case in cases]
    if len(names) != len(set(names)):
        raise ValueError(f"Model names must be unique within a run: {names}")
    for name in names:
        if not 1 <= len(name) <= 31:
            raise ValueError(f"Model name must be 1-31 characters: {name}")
        if not all(ch in "abcdefghijklmnopqrstuvwxyz0123456789_" for ch in name):
            raise ValueError(f"Model name must be lowercase letters/digits/underscore: {name}")
        if not (name[0].isalpha() or name[0].isdigit()):
            raise ValueError(f"Model name must start with a letter or digit: {name}")
    for case in cases:
        validate_operations(slot_operations(case, TILTED_FIXTURE["id"]))
    validate_operations(setup_operations())


# --- report plumbing ------------------------------------------------------


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def model_tag(run_id: str) -> str:
    """Short unique suffix for model names; Creo caps names at 31 characters."""
    return hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8]


def resolve_output(output: Path | None, run_id: str) -> Path:
    """Refuse to overwrite an existing report before any connection is made."""
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "dev049_t04" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


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
    names.update(("tools/test_dev049_tilted_cut.py", "tests/unit/test_dev049_tilted_cut.py"))
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


def geometry_basis() -> dict:
    """Direction/normal semantics and analytic quantities, embedded for live use."""
    return {
        "base_radius_mm": BASE_RADIUS,
        "base_height_mm": BASE_HEIGHT,
        "base_z_range": [0.0, BASE_HEIGHT],
        "base_volume_mm3": math.pi * BASE_RADIUS * BASE_RADIUS * BASE_HEIGHT,
        "tilt_degrees": TILT_DEGREES,
        "normal": tilted_normal(),
        "u_axis_input": list(U_AXIS_INPUT),
        "u_axis_normalized": u_axis_normalized(),
        "v_axis_is_n_cross_u": v_axis(),
        "v_axis_semantics": "v = n x u = -Z",
        "rectangle_u": list(RECT_U),
        "rectangle_v": list(RECT_V),
        "effective_height_mm": effective_height(),
        "single_direction_formula": "3 * integral[-4,0] sqrt(400 - u^2) du",
        "single_direction_expected_mm3": expected_volume("positive"),
        "symmetric_expected_mm3": expected_volume("symmetric"),
        "volume_tolerance_mm3": VOLUME_TOLERANCE,
        "historical_anomaly": {
            "old_single_pair": [120.0, 0.0],
            "note": "120 = 4*6*5 is the along-Z artefact; 0 is the empty negative sweep",
            "report_approximation": 478.0,
            "approximation_note": "~478 is bidirectional and must not be a single expectation",
        },
    }


# --- live runner ----------------------------------------------------------


class TiltedCutAcceptance:
    """Serial six-case live runner. Embedded frame and oracle checks only."""

    def __init__(self, client: Any, output: Path, run_id: str) -> None:
        self.client = client
        self.output = output
        self.run_id = run_id
        self.submitted: set[str] = set()
        self.report: dict = {
            "task": "DEV-049 T04",
            "scope": (
                "R20 / 54deg / 4x6 tilted cut, autodim/coordinates x positive/negative/symmetric"
            ),
            "run_id": run_id,
            "mode": "live",
            "live_run": True,
            "geometry_basis": geometry_basis(),
            "oracle": oracle_cross_check(),
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

    async def wait_job(self, job_id: str, expected: str | None = None, budget: float = 360) -> dict:
        """Poll one accepted job to a terminal state. Never resubmits anything."""
        deadline = time.monotonic() + budget
        while True:
            terminal = await self.call("creo_get_job", {"job_id": job_id})
            status = terminal.get("status")
            if status not in ("queued", "running"):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Job {job_id} did not reach a terminal state within {budget}s; "
                    "budget exhausted, do not resubmit"
                )
            await asyncio.sleep(1)
        if status not in ("succeeded", "failed"):
            raise RuntimeError(
                f"Job {job_id} returned an unknown terminal status {status!r}; "
                "recorded as-is, do not resubmit"
            )
        if expected is not None:
            assert status == expected, terminal
        return terminal

    async def submit_once(self, case_key: str, args: dict) -> dict:
        """Submit one case's plan exactly once; a repeat is a programming error."""
        if case_key in self.submitted:
            raise RuntimeError(f"Case {case_key} already submitted; never resubmit")
        self.submitted.add(case_key)
        return await self.call("creo_execute_plan", args)

    async def fresh_part(self, model_name: str) -> tuple[str, dict]:
        created = await self.call("creo_new_part", {"model_name": model_name})
        await self.wait_job(created["job_id"], "succeeded")
        model_id = created["model_id"]
        snapshot = await self.snapshot(model_id)
        assert snapshot["inspection"]["length_unit"]["name"] == "mm", snapshot["inspection"]
        assert not [b for b in snapshot["inspection"]["bodies"] if b.get("has_geometry")]
        return model_id, snapshot

    async def run_case(self, case: dict) -> None:
        model_id, before = await self.fresh_part(case["model_name"])
        setup = await self.submit_once(
            f"{case['case']}:setup",
            {
                "model_id": model_id,
                "expected_revision": before["revision"],
                "operations": setup_operations(),
            },
        )
        await self.wait_job(setup["job_id"], "succeeded")

        staged = await self.snapshot(model_id)
        plane = select_tilted_plane(staged["inspection"]["datum_planes"])
        plan = slot_operations(case, plane["id"])
        submitted = await self.submit_once(
            case["case"],
            {
                "model_id": model_id,
                "expected_revision": staged["revision"],
                "operations": plan,
            },
        )
        terminal = await self.wait_job(submitted["job_id"], "succeeded")
        assert terminal["result"]["saved_file_reloaded_and_verified"] is True, terminal

        saved = await self.snapshot(model_id)
        frame = self.alias(saved, "slot_profile")
        check_frame(frame, plane["normal"])
        near(frame["origin"], [0.0, 0.0, 0.0])
        assert frame["surface_id"] == plane["id"], (frame["surface_id"], plane["id"])

        removed = self.removed_mm3(terminal)
        verdict = judge_volume(case["direction"], removed)
        assert verdict["passed"], verdict

        self.report["cases"].append(
            {
                "case": case["case"],
                "dimensioning": case["dimensioning"],
                "direction": case["direction"],
                "model_name": case["model_name"],
                "model_id": model_id,
                "u_axis_input": list(U_AXIS_INPUT),
                "actual_frame": frame,
                "plane_id_from_inspection": plane["id"],
                "plane_normal": plane["normal"],
                "setup_job_id": setup["job_id"],
                "job_id": submitted["job_id"],
                "revision": saved["revision"],
                "saved_file_reloaded_and_verified": True,
                "material_removed_mm3": removed,
                "expected_volume_mm3": verdict["expected_mm3"],
                "abs_error_mm3": verdict["abs_error_mm3"],
                "passed": True,
            }
        )
        self.save()

    @staticmethod
    def alias(snapshot: dict, label: str) -> dict:
        aliases = snapshot.get("aliases") or {}
        assert label in aliases, {"snapshot_keys": sorted(snapshot), "aliases": aliases}
        return aliases[label]

    @staticmethod
    def removed_mm3(terminal: dict) -> float:
        for operation in terminal.get("result", {}).get("operations", []):
            if operation.get("label") == "slot_cut" and "material_removed_mm3" in operation:
                return float(operation["material_removed_mm3"])
        raise AssertionError(f"No material_removed_mm3 for slot_cut in {terminal}")

    async def run_all(self) -> None:
        from tools.mcp_readiness import wait_for_startup

        self.report["capabilities"] = await self.call("creo_capabilities", {})
        self.report["environment"] = await self.call("creo_check_environment", {})
        self.save()
        await wait_for_startup(self.client, self.report, self.output)
        status = await self.call("creo_session_status", {})
        assert status["connected"] is True, status
        try:
            for case in build_cases(model_tag(self.run_id)):
                await self.run_case(case)
            self.report.update(live_run=True, native_acceptance="recorded")
        except Exception as error:
            self.report.update(error=f"{type(error).__name__}: {error}")
            raise
        finally:
            self.save()


async def live(output: Path, run_id: str) -> None:
    from tools.test_t05_native import require_manual_start

    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=60,
    ) as client:
        runner = TiltedCutAcceptance(client, output, run_id)
        runner.save()
        await runner.run_all()


# --- offline stage --------------------------------------------------------


def _rejected(callable_) -> None:
    try:
        callable_()
    except (AssertionError, ValueError):
        return
    raise AssertionError("Expected the oracle to reject this value")


def _assert_passes(verdict: dict) -> None:
    if not verdict["passed"]:
        raise AssertionError(verdict)


def offline_checks(run_id: str) -> dict:
    """Validate the six inputs and the independent oracle. No native result."""
    cases = build_cases(model_tag(run_id))
    validate_case_inputs(cases)
    cross = oracle_cross_check()

    verdicts = {
        direction: judge_volume(direction, expected_volume(direction)) for direction in DIRECTIONS
    }
    for direction, verdict in verdicts.items():
        assert verdict["passed"], verdict

    rejections = {}
    for direction in DIRECTIONS:
        _rejected(lambda d=direction: _assert_passes(judge_volume(d, 120.0)))
        _rejected(lambda d=direction: _assert_passes(judge_volume(d, 0.0)))
        _rejected(lambda d=direction: validate_expectation(d, 478.0))
        _rejected(lambda d=direction: validate_expectation(d, 120.0))
        record = {
            "old_anomaly_120_rejected": True,
            "old_anomaly_0_rejected": True,
        }
        if direction == "symmetric":
            # The bidirectional value is the correct expectation here; what must
            # fail is a single-direction slot carrying it.
            record["bidirectional_as_single_rejected"] = "not_applicable"
        else:
            _rejected(
                lambda d=direction: _assert_passes(judge_volume(d, expected_volume("symmetric")))
            )
            _rejected(lambda d=direction: validate_expectation(d, expected_volume("symmetric")))
            record["bidirectional_as_single_rejected"] = True
        rejections[direction] = record

    frame = {
        "origin": [0.0, 0.0, 0.0],
        "normal": tilted_normal(),
        "u_axis": u_axis_normalized(),
        "v_axis": v_axis(),
    }
    check_frame(frame)

    return {
        "run_id": run_id,
        "cases": cases,
        "oracle": cross,
        "verdicts": verdicts,
        "rejections": rejections,
        "frame_check": "v = n x u confirmed",
    }


def write_offline_report(output: Path, run_id: str, results: dict) -> dict:
    report = {
        "task": "DEV-049 T04",
        "scope": (
            "R20 / 54deg / 4x6 tilted cut, autodim/coordinates x positive/negative/symmetric"
        ),
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": ("Offline stage only: inputs and oracle validated, no Toolkit connection."),
        "geometry_basis": geometry_basis(),
        "oracle": results["oracle"],
        "direction_verdicts": results["verdicts"],
        "oracle_rejections": results["rejections"],
        "frame_semantics": results["frame_check"],
        "cases": results["cases"],
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

    run_id = new_run_id()
    try:
        output = resolve_output(args.output, run_id)
    except ValueError as error:
        print(f"REFUSED BEFORE CONNECTION: {error}")
        return 2

    if not (args.live and args.confirm_session_usable):
        if args.live or args.confirm_session_usable:
            reason = "both --live and --confirm-session-usable are required"
        else:
            reason = "no live flags given"
        print(f"OFFLINE ONLY ({reason}): no MCP client, no Toolkit call, no Creo connection.")
        results = offline_checks(run_id)
        write_offline_report(output, run_id, results)
        print(f"offline_cases={len(results['cases'])} validated")
        print(f"oracle_analytic={results['oracle']['analytic_single_mm3']:.12f}")
        print(f"oracle_numeric={results['oracle']['numeric_single_mm3']:.12f}")
        print(f"oracle_abs_difference={results['oracle']['abs_difference_mm3']:.3e}")
        print(f"report={output}")
        print("LIVE NOT RUN: no native geometry result was produced or claimed.")
        return 0

    asyncio.run(live(output, run_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
