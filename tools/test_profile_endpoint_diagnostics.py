"""BUG-049 / N03: near-tolerance endpoint diagnostics driver (offline default).

The original 0.8.5 attachments named in the N00 mapping (gear10.json,
gear10_snapped.json, mc_rings10.json, mc_prep.py, mc_rings.py) are missing,
so every fixture below is a fixed line/arc substitute. This is NOT a replay
of the reported case and never claims to be one.

The gap constants are experimental sampling points around the 1e-6 mm native
diagnostic clustering value and the externally reported 7.72e-7 mm case.
They are not admission thresholds and are never claimed to be a kernel
welding tolerance:

* input closure admits gaps up to 1e-4 mm (auto/autodim) and rejects anything
  above 1e-9 mm for coordinates dimensioning;
* the native section summary clusters endpoints at 1e-6 mm for its own
  report only (tolerance_scope=diagnostic_endpoint_clustering).

Whether the kernel welds which gap is decided only by the live stage; the
offline stage fixes the inputs, the independent area x depth oracle and the
two-stage comparison table shape. The driver never snaps endpoints, widens a
tolerance, or resubmits a job.

Default is strictly offline. Only --live --confirm-session-usable starts an
MCP client. The driver never launches or stops Creo, clears protection,
injects faults, or resubmits a job.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
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
GAP_SAMPLES_MM = (0.5e-6, 0.77e-6, 1.0e-6, 1.2e-6)
OPEN_CHAIN_GAP_MM = 0.5
SQUARE_SIDE_MM = 10.0
RING_RADIUS_MM = 3.0
STADIUM_LENGTH_MM = 20.0
STADIUM_RADIUS_MM = 5.0
ARC_SAMPLES = 512
AREA_TOLERANCE_MM2 = 1e-6
VOLUME_TOLERANCE_MM3 = 0.01
SAMPLE_LIMIT = 20
ARC_ECHO_FIELDS = ("start_uv", "end_uv", "center_uv", "radius_mm")

MISSING_ATTACHMENTS = (
    "scripts/gear10.json",
    "scripts/gear10_snapped.json",
    "scripts/mc_rings10.json",
    "scripts/mc_prep.py",
    "scripts/mc_rings.py",
)


# --- fixtures ---------------------------------------------------------------


def gapped_square(gap_mm: float, origin: tuple[float, float] = (0.0, 0.0)) -> list[dict]:
    """A square of four lines whose last endpoint stops ``gap_mm`` short.

    The closing chord from (0, gap) to (0, 0) runs along x=0, so the area of
    the topologically closed walk is exactly side^2 for any gap.
    """
    ox, oy = origin
    s = SQUARE_SIDE_MM
    return [
        {"type": "line", "name": "sq_l0", "start": [ox, oy], "end": [ox + s, oy]},
        {"type": "line", "name": "sq_l1", "start": [ox + s, oy], "end": [ox + s, oy + s]},
        {"type": "line", "name": "sq_l2", "start": [ox + s, oy + s], "end": [ox, oy + s]},
        {"type": "line", "name": "sq_l3", "start": [ox, oy + s], "end": [ox, oy + gap_mm]},
    ]


def ring_entities(gap_mm: float, center: tuple[float, float] = (0.0, 0.0)) -> list[dict]:
    """Four quarter arcs whose last arc stops ``gap_mm`` short of the start.

    The angular shortfall is gap/radius radians, so the chord length is
    2r sin(gap / 2r), which matches the design gap to O(gap^3/r^2).
    """
    shortfall_deg = math.degrees(gap_mm / RING_RADIUS_MM)
    cx, cy = center
    entities = [
        {
            "type": "arc",
            "name": f"ring_a{quarter}",
            "center": [cx, cy],
            "radius": RING_RADIUS_MM,
            "start_angle": quarter * 90.0,
            "end_angle": quarter * 90.0 + 90.0,
        }
        for quarter in range(4)
    ]
    entities[3]["end_angle"] = 360.0 - shortfall_deg
    return entities


def gapped_stadium(gap_mm: float) -> list[dict]:
    """A line/arc mix: two lines and two half-circle arcs with one gap.

    The top line stops ``gap_mm`` short of the left arc's start point; the
    closing chord is horizontal, so the enclosed area is the exact stadium
    area minus the 0.5*r*gap chord-integral convention of the clustered walk.
    """
    r = STADIUM_RADIUS_MM
    length = STADIUM_LENGTH_MM
    return [
        {"type": "line", "name": "st_l0", "start": [0.0, -r], "end": [length, -r]},
        {
            "type": "arc",
            "name": "st_a0",
            "center": [length, 0.0],
            "radius": r,
            "start_angle": -90.0,
            "end_angle": 90.0,
        },
        {"type": "line", "name": "st_l1", "start": [length, r], "end": [gap_mm, r]},
        {
            "type": "arc",
            "name": "st_a1",
            "center": [0.0, 0.0],
            "radius": r,
            "start_angle": 90.0,
            "end_angle": 270.0,
        },
    ]


def independent_endpoint_gap(entities: list[dict]) -> float:
    """Largest distance between consecutive endpoints of the chain order."""
    endpoints: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for entity in entities:
        if entity["type"] == "line":
            endpoints.append((tuple(entity["start"]), tuple(entity["end"])))
        else:
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


def contour_points(entities: list[dict], samples: int = ARC_SAMPLES) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for entity in entities:
        if entity["type"] == "line":
            points.append(tuple(entity["start"]))
        else:
            cx, cy = entity["center"]
            radius = entity["radius"]
            start = math.radians(entity["start_angle"])
            end = math.radians(entity["end_angle"])
            for step in range(samples):
                angle = start + (end - start) * step / samples
                points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def polygon_area(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def sampled_area(entities: list[dict], samples: int = ARC_SAMPLES) -> float:
    return polygon_area(contour_points(entities, samples))


def extrapolated_area(entities: list[dict], samples: int = ARC_SAMPLES) -> float:
    coarse = sampled_area(entities, samples)
    fine = sampled_area(entities, samples * 2)
    return (4.0 * fine - coarse) / 3.0


def closed_form_area(shape: str) -> float:
    if shape == "square":
        return SQUARE_SIDE_MM**2
    if shape == "ring":
        return math.pi * RING_RADIUS_MM**2
    if shape == "stadium":
        return STADIUM_LENGTH_MM * 2 * STADIUM_RADIUS_MM + math.pi * STADIUM_RADIUS_MM**2
    raise ValueError(f"Unknown shape {shape!r}")


# --- cases ------------------------------------------------------------------


def _gap_tag(gap_mm: float) -> str:
    text = f"{gap_mm:.2e}"  # "5.00e-07" / "0.00e+00"
    return text.replace("e-", "m").replace("e+", "p").replace(".", "_")


def build_cases(tag: str) -> list[dict]:
    """Two exact controls plus four gap samples on lines and on arcs.

    Gap cases submit with dimensioning "auto" (1e-4 mm input closure); the
    exact controls use the strict "coordinates" mode. All gap constants are
    experimental samples, not admission thresholds.
    """
    cases: list[dict] = []
    for shape, gap, role in (
        ("square", 0.0, "control"),
        ("ring", 0.0, "control"),
        ("square", GAP_SAMPLES_MM[0], "experimental"),
        ("square", GAP_SAMPLES_MM[1], "experimental"),
        ("square", GAP_SAMPLES_MM[2], "experimental"),
        ("square", GAP_SAMPLES_MM[3], "experimental"),
        ("ring", GAP_SAMPLES_MM[0], "experimental"),
        ("ring", GAP_SAMPLES_MM[1], "experimental"),
        ("ring", GAP_SAMPLES_MM[2], "experimental"),
        ("ring", GAP_SAMPLES_MM[3], "experimental"),
    ):
        name = f"{'exact' if gap == 0.0 else 'gap'}_{shape}_{_gap_tag(gap)}"
        entities = gapped_square(gap) if shape == "square" else ring_entities(gap)
        cases.append(
            {
                "case": name,
                "role": role,
                "shape": shape,
                "gap_mm": gap,
                "dimensioning": "coordinates" if gap == 0.0 else "auto",
                "entities": entities,
                "expected_area_mm2": closed_form_area(shape),
                "expected_removed_mm3": closed_form_area(shape) * PLATE_DEPTH_MM,
                "model_name": f"n03_{name[:12]}_{tag}"[:31],
            }
        )
    return cases


def plate_operations() -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "plate_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "circle",
                    "name": "plate",
                    "center": [0.0, 0.0],
                    "radius": PLATE_RADIUS_MM,
                }
            ],
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
            "entities": case["entities"],
            "dimensioning": case["dimensioning"],
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


def open_chain_operations() -> list[dict]:
    """A genuinely open chain: rejected by admission before any submission."""
    return cut_operations(
        {
            "case": "open_chain",
            "dimensioning": "auto",
            "entities": gapped_square(OPEN_CHAIN_GAP_MM),
        }
    )


def original_inputs() -> dict:
    return {
        "attachments": {name: "missing" for name in MISSING_ATTACHMENTS},
        "original_case_replay": "not_possible_missing_attachments",
        "not_original_replay": True,
        "search_scope": (
            "N00 mapping (docs/validation/feedback-0.8.x-2026-10-30/MAPPING.md): repository "
            "working tree, git history, archived feedback directories, Downloads/0.8.x; "
            "reported earlier searches covered Downloads/0.6.1, 0.7.0 and build/*.zip"
        ),
        "note": (
            "Every fixture here is a fixed line/arc substitute; the reported 10-slot "
            "gear geometry is unknown and cannot be reconstructed from the reports."
        ),
    }


def tolerance_basis() -> dict:
    return {
        "input_closure_auto_mm": 1e-4,
        "input_closure_coordinates_mm": 1e-9,
        "native_diagnostic_clustering_mm": 1e-6,
        "kernel_welding_tolerance": "unknown_not_claimed",
        "gap_samples_role": (
            "experimental sampling points around the diagnostic clustering value and the "
            "externally reported 7.72e-7 mm case; not admission thresholds"
        ),
    }


def design_gap_mm(shape: str, gap_mm: float) -> float:
    """Independently computed endpoint distance for the designed shortfall."""
    if shape == "square":
        return gap_mm
    if shape == "ring":
        return 2 * RING_RADIUS_MM * math.sin(gap_mm / RING_RADIUS_MM / 2)
    raise ValueError(f"Unknown shape {shape!r}")


def analyze_case(case: dict) -> dict:
    """Input-side analysis rows for one case (source=input, no native claim)."""
    from creo_mechdog.profile_diagnostics import analyze_profile

    report = analyze_profile(case["entities"])
    near = report["categories"]["near_tolerance"]
    return {
        "case": case["case"],
        "shape": case["shape"],
        "role": case["role"],
        "gap_mm": case["gap_mm"],
        "dimensioning": case["dimensioning"],
        "source": "input",
        "entity_count": report["entity_count"],
        "closed_contour_count": report["closed_contour_count"],
        "open_contour_count": report["open_contour_count"],
        "near_tolerance_count": near["count"],
        "max_endpoint_gap_mm": max(
            (contour["max_join_gap_mm"] for contour in report["contours"]), default=0.0
        ),
        "independent_endpoint_gap_mm": independent_endpoint_gap(case["entities"]),
    }


def endpoint_comparison(case: dict, operation: Any) -> list[dict]:
    """Two-stage per-arc rows: input echo vs the measured (solved) echo."""
    profile = operation.get("profile") if isinstance(operation, dict) else None
    input_arcs = {
        entry.get("name"): entry
        for entry in (profile or {}).get("arc_geometry", [])
        if isinstance(entry, dict)
    }
    rows = []
    measured = operation.get("arc_geometry") if isinstance(operation, dict) else None
    for entry in measured or []:
        if not isinstance(entry, dict):
            continue
        source = input_arcs.get(entry.get("name"))
        rows.append(
            {
                "entity": entry.get("name"),
                "source": entry.get("source"),
                "query_code": entry.get("query_code"),
                "input": {
                    field: source.get(field) if source else None for field in ARC_ECHO_FIELDS
                },
                "solved": {field: entry.get(field) for field in ARC_ECHO_FIELDS},
            }
        )
    return rows


# --- offline stage ----------------------------------------------------------


def projection_observability() -> dict:
    """Lock the public projection behaviour with a synthetic native record."""
    from creo_mechdog import operation_results

    case = build_cases("offline")[2]  # first experimental square gap
    record = {"op": "sketch", "index": 0, "label": "cut_profile", "succeeded": True}
    result = operation_results.annotate_native_result(
        {"success": True, "operations": [record]},
        readonly=False,
        inputs=[{"op": "sketch", "label": "cut_profile", "entities": case["entities"]}],
    )
    projected = result["operations"][0]
    return {
        "profile_source": projected["profile"]["source"],
        "max_endpoint_gap_mm": projected["profile"]["max_endpoint_gap_mm"],
        "near_tolerance_pairs": projected["profile"]["near_tolerance_pairs"],
        "native_section_absent": "native_section" not in projected,
        "sample_limit": SAMPLE_LIMIT,
    }


def offline_checks(run_id: str) -> dict:
    from creo_mechdog.schema import validate_operations

    tag = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8]
    cases = build_cases(tag)
    validate_operations(plate_operations())
    with_open = open_chain_operations()
    try:
        validate_operations(with_open)
        raise AssertionError("the open chain must be rejected by admission")
    except ValueError:
        pass

    rows = []
    for case in cases:
        validate_operations(cut_operations(case))
        analysis = analyze_case(case)
        numeric = extrapolated_area(case["entities"])
        area_error = abs(numeric - case["expected_area_mm2"])
        if area_error > AREA_TOLERANCE_MM2:
            raise AssertionError(f"{case['case']}: numeric area off by {area_error}")
        gap = independent_endpoint_gap(case["entities"])
        expected_gap = design_gap_mm(case["shape"], case["gap_mm"])
        if abs(gap - expected_gap) > max(expected_gap * 1e-7, 1e-15):
            raise AssertionError(f"{case['case']}: endpoint gap {gap} != {expected_gap}")
        if case["gap_mm"]:
            analysis["near_tolerance_as_expected"] = analysis["near_tolerance_count"] >= 1
        else:
            analysis["near_tolerance_as_expected"] = analysis["near_tolerance_count"] == 0
        rows.append(analysis)

    # Coordinate dimensioning must reject every gap sample before submission.
    rejections = {}
    for case in cases:
        if not case["gap_mm"]:
            continue
        strict = [dict(op) for op in cut_operations(case)]
        strict[0] = dict(strict[0], dimensioning="coordinates")
        try:
            validate_operations(strict)
            raise AssertionError(f"{case['case']}: coordinates mode must reject the gap")
        except ValueError:
            rejections[case["case"]] = True

    return {
        "run_id": run_id,
        "cases": rows,
        "coordinates_rejections": rejections,
        "open_chain_rejected_by_admission": True,
        "projection_observability": projection_observability(),
    }


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "post090_n03" / run_id / "report.json"
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
            "tools/test_profile_endpoint_diagnostics.py",
            "tests/unit/test_profile_endpoint_diagnostics.py",
        ),
    )


def write_report(output: Path, report: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def write_offline_report(output: Path, run_id: str, results: dict) -> dict:
    report = {
        "task": "BUG-049 / N03 near-tolerance endpoint diagnostics",
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: substitute fixtures, independent oracle and projection "
            "locks validated; no Toolkit connection, no native geometry result, no claim "
            "about which gaps the kernel welds."
        ),
        "original_inputs": original_inputs(),
        "tolerance_basis": tolerance_basis(),
        "plate": {
            "radius_mm": PLATE_RADIUS_MM,
            "depth_mm": PLATE_DEPTH_MM,
            "volume_mm3": math.pi * PLATE_RADIUS_MM**2 * PLATE_DEPTH_MM,
        },
        "area_tolerance_mm2": AREA_TOLERANCE_MM2,
        "volume_tolerance_mm3": VOLUME_TOLERANCE_MM3,
        "cases": results["cases"],
        "coordinates_rejections": results["coordinates_rejections"],
        "open_chain_rejected_by_admission": results["open_chain_rejected_by_admission"],
        "projection_observability": results["projection_observability"],
        "provenance": local_provenance(),
    }
    write_report(output, report)
    return report


# --- live stage -------------------------------------------------------------


class ProfileEndpointAcceptance:
    """Serial live runner: one plate part and one cut per fixture case.

    Controls must succeed with the oracle volume. Experimental gap cases are
    recorded either way: a success must carry the reloaded-and-verified flag
    and the oracle volume, a failure must carry the original error and a
    confirmed rollback. The kernel welding behaviour is the experiment, not
    an assertion.
    """

    def __init__(self, client: Any, output: Path, run_id: str) -> None:
        self.client = client
        self.output = output
        self.run_id = run_id
        self.submitted: set[str] = set()
        self.report: dict = {
            "task": "BUG-049 / N03 near-tolerance endpoint diagnostics",
            "run_id": run_id,
            "mode": "live",
            "live_run": True,
            "native_acceptance": "running",
            "original_inputs": original_inputs(),
            "tolerance_basis": tolerance_basis(),
            "not_original_replay": True,
            "cases": [],
            "calls": [],
            "provenance": local_provenance(),
        }

    def save(self) -> None:
        write_report(self.output, self.report)

    async def call(self, name: str, args: dict) -> dict:
        self.report["calls"].append({"tool": name, "args": args, "at": time.time()})
        self.save()
        result = await self.client.call_tool(name, args)
        if getattr(result, "is_error", False):
            raise RuntimeError(f"{name} failed: {result.content}")
        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            return structured
        for item in getattr(result, "content", []) or []:
            text = getattr(item, "text", None)
            if text:
                decoded = json.loads(text)
                if isinstance(decoded, dict):
                    return decoded
        raise RuntimeError(f"{name} returned no structured payload")

    async def wait_job(self, job_id: str, budget: float = 360) -> dict:
        deadline = time.monotonic() + budget
        while True:
            terminal = await self.call("creo_get_job", {"job_id": job_id})
            status = terminal.get("status")
            if status not in ("queued", "running"):
                return terminal
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Job {job_id} did not reach a terminal state within {budget}s; "
                    "budget exhausted, do not resubmit"
                )
            await asyncio.sleep(1)

    async def submit_once(self, case_key: str, args: dict) -> dict:
        if case_key in self.submitted:
            raise RuntimeError(f"Case {case_key} already submitted; never resubmit")
        self.submitted.add(case_key)
        return await self.call("creo_execute_plan", args)

    @staticmethod
    def cut_operation(terminal: dict) -> dict:
        for operation in terminal.get("result", {}).get("operations", []):
            if operation.get("label") == "cut":
                return operation
        return {}

    @staticmethod
    def sketch_operation(terminal: dict) -> dict:
        for operation in terminal.get("result", {}).get("operations", []):
            if operation.get("label") == "cut_profile":
                return operation
        return {}

    async def snapshot_volume(self, model_id: str) -> float:
        from creo_mechdog.query_client import read_full_model

        snapshot = await read_full_model(self.call, model_id)
        return float(snapshot["inspection"]["volume_mm3"])

    async def run_case(self, case: dict) -> None:
        created = await self.submit_once(
            f"{case['case']}:new_part",
            {"operations": plate_operations(), "model_name": case["model_name"]},
        )
        created_terminal = await self.wait_job(created["job_id"])
        if created_terminal.get("status") != "succeeded":
            raise RuntimeError(f"plate creation failed for {case['case']}: {created_terminal}")
        model_id = created["model_id"]
        before_volume = await self.snapshot_volume(model_id)

        submitted = await self.submit_once(
            case["case"],
            {
                "model_id": model_id,
                "expected_revision": created_terminal["result"]["revision"],
                "operations": cut_operations(case),
            },
        )
        terminal = await self.wait_job(submitted["job_id"])
        status = terminal.get("status")
        result = terminal.get("result", {})
        row: dict = {
            "case": case["case"],
            "role": case["role"],
            "shape": case["shape"],
            "gap_mm": case["gap_mm"],
            "dimensioning": case["dimensioning"],
            "model_id": model_id,
            "plate_job_id": created_terminal["job_id"],
            "job_id": submitted["job_id"],
            "status": status,
            "expected_removed_mm3": case["expected_removed_mm3"],
        }
        if status == "succeeded":
            assert result.get("saved_file_reloaded_and_verified") is True, terminal
            after_volume = await self.snapshot_volume(model_id)
            removed = before_volume - after_volume
            row.update(
                {
                    "removed_mm3": removed,
                    "abs_error_mm3": abs(removed - case["expected_removed_mm3"]),
                    "volume_within_tolerance": abs(removed - case["expected_removed_mm3"])
                    <= VOLUME_TOLERANCE_MM3,
                    "saved_file_reloaded_and_verified": True,
                }
            )
            if case["role"] == "control":
                assert row["volume_within_tolerance"], row
        elif status == "failed":
            assert result.get("rollback_succeeded") is True, terminal
            row.update(
                {
                    "error": result.get("error"),
                    "rollback_succeeded": True,
                    "volume_within_tolerance": None,
                }
            )
        else:
            raise RuntimeError(f"{case['case']}: unexpected terminal status {status!r}")

        sketch = self.sketch_operation(terminal)
        row["input_profile"] = sketch.get("profile")
        row["native_section"] = sketch.get("native_section")
        row["endpoint_comparison"] = endpoint_comparison(case, sketch)
        self.report["cases"].append(row)
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
            tag = hashlib.sha256(self.run_id.encode("utf-8")).hexdigest()[:8]
            for case in build_cases(tag):
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
        runner = ProfileEndpointAcceptance(client, output, run_id)
        runner.save()
        await runner.run_all()


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
        report = write_offline_report(output, run_id, results)
        print(f"offline_cases={len(results['cases'])} validated")
        print("not_original_replay=true (gear10/gear10_snapped/mc_rings10/mc_prep.py missing)")
        print(f"open_chain_rejected={results['open_chain_rejected_by_admission']}")
        print(
            f"projection_max_endpoint_gap_mm={report['projection_observability']['max_endpoint_gap_mm']}"
        )
        print(f"report={output}")
        print("LIVE NOT RUN: no native geometry result was produced or claimed.")
        return 0

    asyncio.run(live(output, run_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
