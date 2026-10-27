"""DEV-049 T05 substitute profile replay for the 0.6.1 multi-contour report.

The external attachments named in the report (gear10.json and
sketch_entities.json) were never shipped, so the reported 5/10 four-arc case
cannot be replayed byte for byte. This driver therefore replays only the
differences that the existing DEV-047 T06 fixtures do not cover, and labels
every result as substitute verification:

* five_arc_rings_cut / ten_arc_rings_cut: four-arc closed loops in a
  cut + through_all plan. T06 covered those rings as a protrusion and cut only
  the mixed 2-circle + 5-ring sketch.
* control_two_circles_r2: the report's own control on the reported plate
  (R2 circles at +/-8, 5 mm plate). T06 already covers 2-circle cuts; this case
  exists to tie the substitute plate to the report's 125.663706 mm3 number and
  is not claimed as new coverage.

The driver never asserts a contour limit: the report's "supported 2" phrasing
stays an unproven claim and no multi-contour ceiling is derived here.

Default is strictly offline. Only --live --confirm-session-usable starts an MCP
client. The driver never launches or stops Creo, clears protection, injects
faults, submits startup/retry commands, or resubmits a job.
"""

from __future__ import annotations

import argparse
import asyncio
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

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402

ROOT = SOURCE_PATHS.resource_root

PLATE_RADIUS_MM = 20.0
PLATE_DEPTH_MM = 5.0
REPORTED_CIRCLE_RADIUS_MM = 2.0
REPORTED_CIRCLE_CENTERS = ((-8.0, 0.0), (8.0, 0.0))
REPORTED_TWO_CIRCLE_REMOVED_MM3 = 125.663706
RING_RADIUS_MM = 3.0
RING_SPACING_MM = 12.0
ARC_SAMPLES = 256
AREA_TOLERANCE_MM2 = 1e-6
VOLUME_TOLERANCE_MM3 = 0.01
ORIGINAL_INPUTS = ("gear10.json", "sketch_entities.json")


def near(actual: float, expected: float, tolerance: float) -> None:
    assert math.isfinite(actual), actual
    assert abs(actual - expected) <= max(tolerance, abs(expected) * 1e-9), (actual, expected)


# --- substitute fixtures ---------------------------------------------------


def circle(name: str, center: tuple[float, float], radius: float) -> dict:
    return {
        "type": "circle",
        "name": name,
        "center": [float(center[0]), float(center[1])],
        "radius": radius,
    }


def arc_ring(name: str, center: tuple[float, float], radius: float = RING_RADIUS_MM) -> dict:
    """One closed loop made of four quarter arcs; the fourth ends at 360 degrees."""
    return {
        "name": name,
        "entities": [
            {
                "type": "arc",
                "name": f"{name}_{quarter}",
                "center": [float(center[0]), float(center[1])],
                "radius": radius,
                "start_angle": quarter * 90.0,
                "end_angle": quarter * 90.0 + 90.0,
            }
            for quarter in range(4)
        ],
    }


def circle_contour(name: str, center: tuple[float, float], radius: float) -> dict:
    return {"name": name, "entities": [circle(name, center, radius)]}


def ring_row(count: int, prefix: str = "ring") -> list[dict]:
    start = -(count - 1) * RING_SPACING_MM / 2
    return [
        arc_ring(f"{prefix}{index}", (start + index * RING_SPACING_MM, 0.0))
        for index in range(count)
    ]


def _circular_contour(contour: dict) -> tuple[tuple[float, float], float] | None:
    """Return (center, radius) when the contour is a circle or a 4-quarter ring."""
    entities = contour["entities"]
    centers = {(tuple(entity["center"]), entity["radius"]) for entity in entities}
    if len(centers) != 1:
        return None
    ((center, radius),) = centers
    if len(entities) == 1 and entities[0]["type"] == "circle":
        return center, radius
    if len(entities) == 4 and all(entity["type"] == "arc" for entity in entities):
        spans = sorted((entity["start_angle"], entity["end_angle"]) for entity in entities)
        expected = [(0.0, 90.0), (90.0, 180.0), (180.0, 270.0), (270.0, 360.0)]
        if all(abs(a - b) < 1e-9 and abs(c - d) < 1e-9 for (a, c), (b, d) in zip(spans, expected)):
            return center, radius
    return None


def analytic_area(contour: dict) -> float:
    circular = _circular_contour(contour)
    if circular is None:
        raise ValueError(f"Contour {contour['name']} is not a circle or a four-quarter ring")
    return math.pi * circular[1] ** 2


def contour_points(contour: dict, samples: int = ARC_SAMPLES) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for entity in contour["entities"]:
        if entity["type"] == "circle":
            cx, cy = entity["center"]
            radius = entity["radius"]
            for step in range(samples):
                angle = 2.0 * math.pi * step / samples
                points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        elif entity["type"] == "arc":
            cx, cy = entity["center"]
            radius = entity["radius"]
            start = math.radians(entity["start_angle"])
            end = math.radians(entity["end_angle"])
            for step in range(samples):
                angle = start + (end - start) * step / samples
                points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        else:
            raise ValueError(f"Unsupported entity type {entity['type']!r}")
    return points


def polygon_area(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def sampled_area(contour: dict, samples: int = ARC_SAMPLES) -> float:
    """Inscribed-polygon area; converges as 1/n^2 and never uses pi r squared."""
    return polygon_area(contour_points(contour, samples))


def extrapolated_area(contour: dict, samples: int = ARC_SAMPLES) -> float:
    """Richardson extrapolation of two inscribed polygons, error O(n^-4)."""
    coarse = sampled_area(contour, samples)
    fine = sampled_area(contour, samples * 2)
    return (4.0 * fine - coarse) / 3.0


def closure_gap(contour: dict) -> float:
    """Largest distance between consecutive entity endpoints, including the wrap."""
    entities = contour["entities"]
    if len(entities) == 1 and entities[0]["type"] == "circle":
        return 0.0
    endpoints: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for entity in entities:
        cx, cy = entity["center"]
        radius = entity["radius"]
        start = math.radians(entity["start_angle"])
        end = math.radians(entity["end_angle"])
        endpoints.append(
            (
                (cx + radius * math.cos(start), cy + radius * math.sin(start)),
                (cx + radius * math.cos(end), cy + radius * math.sin(end)),
            )
        )
    gap = 0.0
    for index, (_, end) in enumerate(endpoints):
        nxt = endpoints[(index + 1) % len(endpoints)][0]
        gap = max(gap, math.dist(end, nxt))
    return gap


def pairwise_gap(left: dict, right: dict) -> float:
    """Proven center distance minus both radii; negative means overlap."""
    a = _circular_contour(left)
    b = _circular_contour(right)
    if a is None or b is None:
        raise ValueError("pairwise_gap only supports circular contours")
    return math.dist(a[0], b[0]) - a[1] - b[1]


def entities_of(case: dict) -> list[dict]:
    return [entity for contour in case["contours"] for entity in contour["entities"]]


def build_cases(run_tag: str) -> list[dict]:
    """Three substitute cases; only the ring cuts are claimed as new coverage."""
    two_circles = {
        "case": "control_two_circles_r2",
        "role": "control_reference",
        "expectation_source": "reported_value",
        "note": (
            "Report control on the reported plate; T06 already covers 2-circle cuts, "
            "so this is a numeric anchor, not new coverage."
        ),
        "contours": [
            circle_contour(f"control{index}", center, REPORTED_CIRCLE_RADIUS_MM)
            for index, center in enumerate(REPORTED_CIRCLE_CENTERS)
        ],
        "reported_removed_mm3": REPORTED_TWO_CIRCLE_REMOVED_MM3,
    }
    five = {
        "case": "five_arc_rings_cut",
        "role": "uncovered_difference",
        "expectation_source": "substitute",
        "note": (
            "Reported 5-ring input is missing; radius 3 and spacing 12 are this driver's "
            "substitute geometry, not the reported gear profile."
        ),
        "contours": ring_row(5, "five"),
        "reported_removed_mm3": None,
    }
    ten = {
        "case": "ten_arc_rings_cut",
        "role": "uncovered_difference",
        "expectation_source": "substitute",
        "note": (
            "T06 cut only the 5-ring mix; 10 four-arc rings in a cut plan were never "
            "submitted. Geometry is the same substitute row as the five-ring case."
        ),
        "contours": ring_row(10, "ten"),
        "reported_removed_mm3": None,
    }
    cases = [two_circles, five, ten]
    for case in cases:
        case["depth"] = PLATE_DEPTH_MM
        case["expected_contour_count"] = len(case["contours"])
        case["expected_entity_count"] = len(entities_of(case))
        case["expected_area_mm2"] = sum(analytic_area(contour) for contour in case["contours"])
        case["expected_removed_mm3"] = case["expected_area_mm2"] * case["depth"]
        case["model_name"] = f"dev049t05_{case['case'][:12]}_{run_tag}"[:31]
    return cases


def plate_volume() -> float:
    return math.pi * PLATE_RADIUS_MM**2 * PLATE_DEPTH_MM


def plate_operations() -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "plate_profile",
            "plane": "XY",
            "entities": [circle("plate", (0.0, 0.0), PLATE_RADIUS_MM)],
            "dimensioning": "coordinates",
        },
        {"op": "extrude", "label": "plate", "sketch": "plate_profile", "depth": PLATE_DEPTH_MM},
    ]


def cut_operations(case: dict) -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "cut_profile",
            "plane": "XY",
            "entities": entities_of(case),
            "dimensioning": "coordinates",
        },
        {
            "op": "extrude",
            "label": "cut",
            "sketch": "cut_profile",
            "mode": "cut",
            "depth": PLATE_DEPTH_MM,
            "depth_type": "through_all",
            "direction": "positive",
        },
    ]


def judge_volume(case: dict, measured: Any) -> dict:
    if isinstance(measured, bool) or not isinstance(measured, (int, float)):
        raise ValueError(f"Measured volume must be a number, got {measured!r}")
    if not math.isfinite(float(measured)):
        raise ValueError(f"Measured volume is not finite: {measured!r}")
    expected = case["expected_removed_mm3"]
    error = abs(float(measured) - expected)
    return {
        "case": case["case"],
        "expected_mm3": expected,
        "measured_mm3": float(measured),
        "abs_error_mm3": error,
        "tolerance_mm3": VOLUME_TOLERANCE_MM3,
        "passed": error <= VOLUME_TOLERANCE_MM3,
    }


def validate_expectation(case: dict) -> None:
    """Recompute area x thickness from the coordinates; reject a stale table."""
    area = sum(analytic_area(contour) for contour in case["contours"])
    near(area, case["expected_area_mm2"], AREA_TOLERANCE_MM2)
    near(area * case["depth"], case["expected_removed_mm3"], AREA_TOLERANCE_MM2 * case["depth"])
    near(case["depth"], PLATE_DEPTH_MM, 1e-12)


def validate_case_inputs(cases: list[dict]) -> None:
    from creo_mechdog.schema import validate_operations

    names = set()
    for case in cases:
        name = case["model_name"]
        if not name or not name[0].isalnum():
            raise ValueError(f"Invalid model name {name!r}")
        if not all(
            character.islower() or character.isdigit() or character == "_" for character in name
        ):
            raise ValueError(f"Invalid model name {name!r}")
        if len(name) > 31:
            raise ValueError(f"Model name too long: {name!r}")
        if name in names:
            raise ValueError(f"Duplicate model name {name!r}")
        names.add(name)
        validate_operations(plate_operations())
        validate_operations(cut_operations(case))
        validate_expectation(case)


def geometry_basis() -> dict:
    return {
        "plate": {
            "radius_mm": PLATE_RADIUS_MM,
            "depth_mm": PLATE_DEPTH_MM,
            "z_range": [0.0, PLATE_DEPTH_MM],
            "volume_mm3": plate_volume(),
        },
        "dimensioning": "coordinates",
        "operation": "cut + through_all + direction=positive",
        "direction_note": (
            "The report's section 3 says cut + through_all + negative but does not give the "
            "sketch plane; a negative sweep from a z=0..5 plate would remove nothing, so the "
            "plane/direction pair is recorded as an explicit driver choice, not a replay."
        ),
        "substitute_ring_radius_mm": RING_RADIUS_MM,
        "substitute_ring_spacing_mm": RING_SPACING_MM,
        "arc_samples_per_entity": ARC_SAMPLES,
        "area_tolerance_mm2": AREA_TOLERANCE_MM2,
        "volume_tolerance_mm3": VOLUME_TOLERANCE_MM3,
        "reported_two_circle_removed_mm3": REPORTED_TWO_CIRCLE_REMOVED_MM3,
        "reported_control_recomputed_mm3": (
            2.0 * math.pi * REPORTED_CIRCLE_RADIUS_MM**2 * PLATE_DEPTH_MM
        ),
    }


def original_inputs() -> dict:
    return {
        "gear10.json": "missing",
        "sketch_entities.json": "missing",
        "original_part_model": "missing",
        "original_preview_images": "missing",
        "original_case_replay": "not_possible_missing_attachments",
        "search_scope": (
            "repository working tree and git history, C:/Users/Administrator/Downloads "
            "(including 0.6.1), and release archives under build/"
        ),
        "note": (
            "The reported 10-ring 40-arc payload cannot be replayed verbatim; every case "
            "below is substitute verification."
        ),
    }


def coverage_table() -> list[dict]:
    return [
        {
            "item": "2 independent circles",
            "original_input": "missing",
            "existing_evidence": "DEV-047 T06 live add/2_circles and cut/2_circles (2026-10-26)",
            "difference": "none material; the R2/+-8/depth-5 plate here is the report control",
            "needed": "cite only",
        },
        {
            "item": "5 four-arc closed loops",
            "original_input": "missing",
            "existing_evidence": "T06 live add/5_arc_rings and cut/two_circles_five_arc_rings",
            "difference": "5 rings alone in a cut plan; reported gear coordinates unknown",
            "needed": "substitute fixture five_arc_rings_cut",
        },
        {
            "item": "10 four-arc closed loops",
            "original_input": "missing",
            "existing_evidence": "T06 live add/10_arc_rings only",
            "difference": "10 rings were never submitted in a cut plan",
            "needed": "substitute fixture ten_arc_rings_cut",
        },
        {
            "item": "reported gear profile (40 arcs)",
            "original_input": "gear10.json missing",
            "existing_evidence": "none",
            "difference": "geometry unknown; cannot be reconstructed from the report",
            "needed": "blocked until the attachment is supplied",
        },
        {
            "item": "preview distortion (blank / long strips)",
            "original_input": "no Part2 model or preview image",
            "existing_evidence": "DEV-047 T07 five-image review 2026-10-27 (no distortion)",
            "difference": "the original configuration was never captured",
            "needed": "T04 same-job image or the original image; BUG-066 stays unreproduced",
        },
    ]


# --- live runner -----------------------------------------------------------


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def model_tag(run_id: str) -> str:
    return hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8]


def resolve_output(output: Path | None, run_id: str) -> Path:
    """Refuse to overwrite an existing report before any connection is made."""
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "dev049_t05" / run_id / "report.json"
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
        ("tools/test_dev049_profile_replay.py", "tests/unit/test_dev049_profile_replay.py")
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


class ProfileReplayAcceptance:
    """Serial three-case live runner. Records substitute scope on every case."""

    def __init__(self, client: Any, output: Path, run_id: str) -> None:
        self.client = client
        self.output = output
        self.run_id = run_id
        self.submitted: set[str] = set()
        self.report: dict = {
            "task": "DEV-049 T05",
            "scope": "substitute replay of the 0.6.1 multi-contour report",
            "run_id": run_id,
            "mode": "live",
            "live_run": True,
            "native_acceptance": "running",
            "original_inputs": original_inputs(),
            "replacement_verification": True,
            "contour_limit_claim": "not_asserted",
            "coverage": coverage_table(),
            "cases": [],
            "calls": [],
            "provenance": local_provenance(),
        }

    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def call(self, name: str, args: dict) -> dict:
        self.report["calls"].append({"tool": name, "args": args, "at": time.time()})
        self.save()
        return await self.client.call_tool(name, args)

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
        if case_key in self.submitted:
            raise RuntimeError(f"Case {case_key} already submitted; never resubmit")
        self.submitted.add(case_key)
        return await self.call("creo_execute_plan", args)

    @staticmethod
    def feature_counts(snapshot: dict) -> dict:
        counts: dict[str, int] = {}
        for feature in snapshot["inspection"]["features"]:
            name = feature.get("type_name", "other")
            counts[name] = counts.get(name, 0) + 1
        return counts

    @staticmethod
    def profile_of(terminal: dict) -> dict:
        for operation in terminal.get("result", {}).get("operations", []):
            if operation.get("label") == "cut_profile" and "profile" in operation:
                return operation
        raise AssertionError(f"No cut_profile operation in {terminal}")

    async def run_case(self, case: dict) -> None:
        created = await self.submit_once(
            f"{case['case']}:new_part",
            {"operations": plate_operations(), "model_name": case["model_name"]},
        )
        created_terminal = await self.wait_job(created["job_id"], "succeeded")
        model_id = created["model_id"]
        before = await self.snapshot(model_id)
        near(before["inspection"]["volume_mm3"], plate_volume(), PLATE_DEPTH_MM)

        submitted = await self.submit_once(
            case["case"],
            {
                "model_id": model_id,
                "expected_revision": before["revision"],
                "operations": cut_operations(case),
            },
        )
        terminal = await self.wait_job(submitted["job_id"], "succeeded")
        assert terminal["result"]["saved_file_reloaded_and_verified"] is True, terminal

        after = await self.snapshot(model_id)
        operation = self.profile_of(terminal)
        section = operation["native_section"]
        assert section["available"], section
        assert section["closed_contours"] == case["expected_contour_count"], section
        assert section["entities"] == case["expected_entity_count"], section
        assert section["open_ends"] == 0, section
        assert operation["profile"]["closed_contour_count"] == case["expected_contour_count"]

        delta = {
            name: self.feature_counts(after).get(name, 0) - self.feature_counts(before).get(name, 0)
            for name in set(self.feature_counts(before)) | set(self.feature_counts(after))
        }
        assert delta.get("cut") == 1, delta
        assert delta.get("protrusion", 0) == 0, delta

        removed = before["inspection"]["volume_mm3"] - after["inspection"]["volume_mm3"]
        verdict = judge_volume(case, removed)
        assert verdict["passed"], verdict

        self.report["cases"].append(
            {
                "case": case["case"],
                "role": case["role"],
                "expectation_source": case["expectation_source"],
                "note": case["note"],
                "model_name": case["model_name"],
                "model_id": model_id,
                "plate_job_id": created_terminal["job_id"],
                "job_id": submitted["job_id"],
                "revision": after["revision"],
                "contour_count": section["closed_contours"],
                "entity_count": section["entities"],
                "native_section": section,
                "feature_delta": delta,
                "material_removed_mm3": removed,
                "expected_removed_mm3": verdict["expected_mm3"],
                "abs_error_mm3": verdict["abs_error_mm3"],
                "saved_file_reloaded_and_verified": True,
                "passed": True,
            }
        )
        self.save()

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
            self.report.update(native_acceptance="recorded")
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
        runner = ProfileReplayAcceptance(client, output, run_id)
        runner.save()
        await runner.run_all()


# --- offline stage ---------------------------------------------------------


def _rejected(callable_) -> None:
    try:
        callable_()
    except (AssertionError, ValueError):
        return
    raise AssertionError("Expected the oracle to reject this value")


def _assert_passes(verdict: dict) -> None:
    if not verdict["passed"]:
        raise AssertionError(verdict)


def reported_control() -> dict:
    recomputed = 2.0 * math.pi * REPORTED_CIRCLE_RADIUS_MM**2 * PLATE_DEPTH_MM
    return {
        "reported_mm3": REPORTED_TWO_CIRCLE_REMOVED_MM3,
        "recomputed_mm3": recomputed,
        "abs_difference_mm3": abs(recomputed - REPORTED_TWO_CIRCLE_REMOVED_MM3),
        "agrees_at_six_decimals": round(recomputed, 6) == REPORTED_TWO_CIRCLE_REMOVED_MM3,
    }


def offline_checks(run_id: str) -> dict:
    """Validate the substitute inputs and the independent area x depth oracle."""
    cases = build_cases(model_tag(run_id))
    validate_case_inputs(cases)

    checked = []
    for case in cases:
        raw = sum(sampled_area(contour) for contour in case["contours"])
        numeric = sum(extrapolated_area(contour) for contour in case["contours"])
        near(
            numeric,
            case["expected_area_mm2"],
            AREA_TOLERANCE_MM2 * case["expected_contour_count"],
        )
        gaps = [closure_gap(contour) for contour in case["contours"]]
        for gap in gaps:
            assert gap <= 1e-9, (case["case"], gap)
        minimum = min(
            pairwise_gap(left, right)
            for index, left in enumerate(case["contours"])
            for right in case["contours"][index + 1 :]
        )
        assert minimum > 0.0, (case["case"], minimum)
        verdict = judge_volume(case, case["expected_removed_mm3"])
        assert verdict["passed"], verdict
        checked.append(
            {
                "case": case["case"],
                "role": case["role"],
                "expectation_source": case["expectation_source"],
                "model_name": case["model_name"],
                "contour_count": case["expected_contour_count"],
                "entity_count": case["expected_entity_count"],
                "analytic_area_mm2": case["expected_area_mm2"],
                "inscribed_area_mm2": raw,
                "numeric_area_mm2": numeric,
                "area_abs_difference_mm2": abs(numeric - case["expected_area_mm2"]),
                "max_closure_gap_mm": max(gaps),
                "minimum_pairwise_gap_mm": minimum,
                "depth_mm": case["depth"],
                "expected_removed_mm3": case["expected_removed_mm3"],
                "reported_removed_mm3": case["reported_removed_mm3"],
                "note": case["note"],
            }
        )

    rejections = {}
    for case in cases:
        expected = case["expected_removed_mm3"]
        for label, bad in (
            ("zero", 0.0),
            ("double", expected * 2.0),
            ("t06_depth_8", case["expected_area_mm2"] * 8.0),
            ("diameter_confusion", case["expected_area_mm2"] * 4.0 * case["depth"]),
        ):
            _rejected(lambda c=case, b=bad: _assert_passes(judge_volume(c, b)))
        rejections[case["case"]] = {
            "zero": True,
            "double": True,
            "t06_depth_8": True,
            "diameter_confusion": True,
            "non_numeric": True,
        }
        _rejected(lambda c=case: judge_volume(c, "120"))
        _rejected(lambda c=case: judge_volume(c, float("nan")))

    control = reported_control()
    assert control["agrees_at_six_decimals"], control

    return {
        "run_id": run_id,
        "cases": checked,
        "rejections": rejections,
        "reported_control": control,
    }


def write_offline_report(output: Path, run_id: str, results: dict) -> dict:
    report = {
        "task": "DEV-049 T05",
        "scope": "substitute replay of the 0.6.1 multi-contour report",
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: substitute inputs and the area x thickness oracle validated, "
            "no Toolkit connection, no native geometry result."
        ),
        "original_inputs": original_inputs(),
        "replacement_verification": True,
        "contour_limit_claim": "not_asserted",
        "coverage": coverage_table(),
        "geometry_basis": geometry_basis(),
        "oracle": {
            "reported_control": results["reported_control"],
            "rejections": results["rejections"],
        },
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
        print("original_case_replay=not_possible (gear10.json, sketch_entities.json missing)")
        print("replacement_verification=true")
        print(f"reported_control_agrees={results['reported_control']['agrees_at_six_decimals']}")
        print(f"report={output}")
        print("LIVE NOT RUN: no native geometry result was produced or claimed.")
        return 0

    asyncio.run(live(output, run_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
