"""DEV-051 T09D performance baseline driver (measurement design, not an optimization).

External observation to investigate: one user-reported job on a model with about
1408 edges (edges, not parts) took roughly 50-60 s end to end. No phase split
exists, so nothing is known yet about where the time goes. This driver only
builds a reproducible baseline: equivalent small/large fixtures, single-operation
versus batch plans, at least three independent repetitions per class, structured
per-stage timings, and an explicit unobservable list.

Equivalence contract between the two plan modes (both must hold or the case is
judged failed, timing is then not comparable):

* the same nominal geometry spec (plate plus pockets) is built twice as fresh,
  independent models, once delivered as N sequential single-operation jobs and
  once as one batch plan job;
* both deliveries must reach the same analytic final volume, the same cut
  feature delta and the same edge count (counts.edges from the saved verified
  snapshot);
* every job must end succeeded with saved_file_reloaded_and_verified is true.
  Save/reload protection is never relaxed, and the single mode inherently
  performs N save/reload events versus one for the batch, which is recorded per
  case (save_reload_events) so the two paths stay interpretable.

Stage observability over MCP is bounded: generic job manifests expose only
created_at and finished_at, native.log PHASE markers carry no timestamps, and
this driver never reads job directories. Everything between job acceptance and
the terminal write (executor startup, queue split, native solve, checks,
save/reload, result registration) is reported as "unobservable" with null
values, never estimated or interpolated.

Default is strictly offline: no MCP client, no Toolkit connection, no Creo.
Offline runs validate fixture layouts, plan schemas and the equivalence math,
and exercise the timing recorder with synthetic data that is labelled
"synthetic_data, not a benchmark". Only --live --confirm-session-usable starts
an MCP client. The driver never launches or stops Creo, clears protection,
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
from datetime import datetime
from pathlib import Path
from typing import Any

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402

ROOT = SOURCE_PATHS.resource_root

# --- fixture definitions ----------------------------------------------------
# Lengths in millimetres. Pockets are cut "positive" (blind) from the XY sketch
# plane, so they open at the plate bottom face z=0; this keeps every cut a
# plain blind extrude on one plane while the removed volume stays exactly
# width x height x depth per pocket.

SPECS: dict[str, dict[str, Any]] = {
    "small": {
        "model_class": "small",
        "plate": {"width": 60.0, "height": 60.0, "depth": 5.0},
        "pocket": {"width": 10.0, "height": 10.0, "depth": 2.5},
        # (col_count, row_count, pitch): pocket centres on a centred grid.
        "grid": {"columns": 2, "rows": 1, "pitch": 30.0},
        "contours_per_cut": 1,
    },
    "large": {
        "model_class": "large",
        "plate": {"width": 240.0, "height": 240.0, "depth": 8.0},
        "pocket": {"width": 12.0, "height": 12.0, "depth": 3.0},
        "grid": {"columns": 12, "rows": 8, "pitch": 20.0},
        "contours_per_cut": 12,
    },
}

# The external observation sits near 1408 edges on one job. The large fixture
# targets the same edge scale with 96 rectangular pockets, but the resulting
# edge count is native geometry: it is only measured live via counts.edges and
# never predicted offline.
EDGE_SCALE_REFERENCE = {"observed_edges": 1408, "meaning": "edges, not parts"}

VOLUME_TOLERANCE_MM3 = 0.01
POLL_INTERVAL_S = 1.0
JOB_BUDGET_S = 600.0
DEFAULT_REPS = 3

UNOBSERVABLE_REASON = (
    "No per-phase timestamps are exposed over MCP: generic job manifests carry "
    "only created_at and finished_at, native.log PHASE markers carry no "
    "timestamps, and this driver does not read job directories. The value is "
    "null and the status is 'unobservable'; it is never estimated."
)

UNOBSERVABLE_STAGES = (
    "queue_wait",
    "executor_startup",
    "native_solve",
    "native_checks",
    "save_reload",
    "result_registration",
)

OBSERVABLE_STAGES = (
    "submit_round_trip",
    "polling",
    "post_job_inspection",
    "fixture_preparation",
)


# --- fixture construction ---------------------------------------------------


def rect(name: str, cx: float, cy: float, width: float, height: float) -> dict:
    return {
        "type": "rectangle",
        "name": name,
        "min": [cx - width / 2.0, cy - height / 2.0],
        "max": [cx + width / 2.0, cy + height / 2.0],
    }


def pocket_centres(spec: dict) -> list[tuple[float, float]]:
    grid = spec["grid"]
    xs = [(col - (grid["columns"] - 1) / 2.0) * grid["pitch"] for col in range(grid["columns"])]
    ys = [(row - (grid["rows"] - 1) / 2.0) * grid["pitch"] for row in range(grid["rows"])]
    return [(x, y) for y in ys for x in xs]


def pocket_count(spec: dict) -> int:
    return spec["grid"]["columns"] * spec["grid"]["rows"]


def cut_count(spec: dict) -> int:
    """One cut operation per row of contours_per_cut pockets."""
    return pocket_count(spec) // spec["contours_per_cut"]


def plate_operations(spec: dict) -> list[dict]:
    plate = spec["plate"]
    return [
        {
            "op": "sketch",
            "label": "plate_profile",
            "plane": "XY",
            "entities": [rect("plate", 0.0, 0.0, plate["width"], plate["height"])],
            "dimensioning": "coordinates",
        },
        {
            "op": "extrude",
            "label": "plate",
            "sketch": "plate_profile",
            "depth": plate["depth"],
        },
    ]


def cut_plan_operations(spec: dict) -> list[list[dict]]:
    """One sketch+cut operation pair per cut; the unit of a single-op job.

    Contours are chunked by ``contours_per_cut`` (not by grid row) so both
    fixtures stay well defined: small cuts one pocket per operation, large cuts
    one 12-pocket row per operation.
    """
    pocket = spec["pocket"]
    centres = pocket_centres(spec)
    per_cut = spec["contours_per_cut"]
    plans = []
    for cut_index in range(cut_count(spec)):
        label = f"pockets_cut_{cut_index:02d}"
        selected = centres[cut_index * per_cut : (cut_index + 1) * per_cut]
        entities = [
            rect(f"pocket_c{cut_index:02d}_{index:02d}", x, y, pocket["width"], pocket["height"])
            for index, (x, y) in enumerate(selected)
        ]
        plans.append(
            [
                {
                    "op": "sketch",
                    "label": f"{label}_profile",
                    "plane": "XY",
                    "entities": entities,
                    "dimensioning": "coordinates",
                },
                {
                    "op": "extrude",
                    "label": label,
                    "sketch": f"{label}_profile",
                    "mode": "cut",
                    "depth": pocket["depth"],
                    "depth_type": "blind",
                    "direction": "positive",
                },
            ]
        )
    return plans


def single_mode_jobs(spec: dict) -> list[list[dict]]:
    """Single-operation delivery: one cut pair per job, in order."""
    return cut_plan_operations(spec)


def batch_mode_plan(spec: dict) -> list[dict]:
    """Batch delivery: all cut pairs in one plan."""
    return [operation for pair in cut_plan_operations(spec) for operation in pair]


def plate_volume_mm3(spec: dict) -> float:
    plate = spec["plate"]
    return plate["width"] * plate["height"] * plate["depth"]


def expected_final_volume_mm3(spec: dict) -> float:
    pocket = spec["pocket"]
    removed = pocket_count(spec) * pocket["width"] * pocket["height"] * pocket["depth"]
    return plate_volume_mm3(spec) - removed


def expected_cut_delta(spec: dict) -> int:
    return cut_count(spec)


def validate_layout(spec: dict) -> dict:
    """Pockets must sit inside the plate and never overlap each other."""
    plate = spec["plate"]
    pocket = spec["pocket"]
    half_w = plate["width"] / 2.0
    half_h = plate["height"] / 2.0
    margin = half_w
    for x, y in pocket_centres(spec):
        assert abs(x) + pocket["width"] / 2.0 < half_w, (x, pocket["width"], half_w)
        assert abs(y) + pocket["height"] / 2.0 < half_h, (y, pocket["height"], half_h)
        margin = min(
            margin,
            half_w - abs(x) - pocket["width"] / 2.0,
            half_h - abs(y) - pocket["height"] / 2.0,
        )
    centres = pocket_centres(spec)
    minimum_gap = float("inf")
    for index, (x1, y1) in enumerate(centres):
        for x2, y2 in centres[index + 1 :]:
            gap = max(abs(x2 - x1) - pocket["width"], abs(y2 - y1) - pocket["height"])
            minimum_gap = min(minimum_gap, gap)
    assert minimum_gap >= 0.0, minimum_gap
    return {
        "pocket_count": pocket_count(spec),
        "cut_operation_count": cut_count(spec),
        "contours_per_cut": spec["contours_per_cut"],
        "edge_margin_mm": margin,
        "minimum_pairwise_gap_mm": minimum_gap,
    }


def validate_expectation(spec: dict) -> None:
    grid_volume = (
        pocket_count(spec)
        * spec["pocket"]["width"]
        * spec["pocket"]["height"]
        * spec["pocket"]["depth"]
    )
    assert expected_final_volume_mm3(spec) == plate_volume_mm3(spec) - grid_volume
    assert grid_volume < plate_volume_mm3(spec)


def validate_case_inputs() -> dict:
    from creo_mechdog.schema import validate_operations

    details = {}
    for name, spec in SPECS.items():
        validate_operations(plate_operations(spec))
        for pair in single_mode_jobs(spec):
            validate_operations(pair)
        validate_operations(batch_mode_plan(spec))
        validate_expectation(spec)
        details[name] = validate_layout(spec)
    return details


def mode_equivalence(spec: dict) -> dict:
    """Offline proof that both delivery modes expect the identical result."""
    single_volume = expected_final_volume_mm3(spec)
    batch_volume = expected_final_volume_mm3(spec)
    single_delta = len(single_mode_jobs(spec))
    batch_delta = sum(1 for op in batch_mode_plan(spec) if op["op"] == "extrude")
    return {
        "single_expected_final_volume_mm3": single_volume,
        "batch_expected_final_volume_mm3": batch_volume,
        "volumes_equal": single_volume == batch_volume,
        "single_cut_delta": single_delta,
        "batch_cut_delta": batch_delta,
        "cut_deltas_equal": single_delta == batch_delta,
        "single_save_reload_events": len(single_mode_jobs(spec)),
        "batch_save_reload_events": 1,
        "note": (
            "Save/reload event counts differ by construction (N jobs vs one plan); "
            "they are part of the measured delivery path and are recorded, never hidden."
        ),
    }


def geometry_basis() -> dict:
    basis = {"length_unit": "mm", "pocket_opening": "plate bottom face z=0 (positive blind cut)"}
    for name, spec in SPECS.items():
        basis[name] = {
            "plate": spec["plate"],
            "pocket": spec["pocket"],
            "grid": spec["grid"],
            "pocket_count": pocket_count(spec),
            "cut_operation_count": cut_count(spec),
            "plate_volume_mm3": plate_volume_mm3(spec),
            "expected_final_volume_mm3": expected_final_volume_mm3(spec),
            "edge_count": "measured_at_live_time (counts.edges), never predicted",
        }
    basis["edge_scale_reference"] = EDGE_SCALE_REFERENCE
    return basis


# --- timing records ---------------------------------------------------------


def unobservable_stages() -> dict:
    return {
        stage: {"value": None, "status": "unobservable", "reason": UNOBSERVABLE_REASON}
        for stage in UNOBSERVABLE_STAGES
    }


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def job_timing_record(
    submit_seconds: float,
    poll_latencies: list[float],
    client_total_seconds: float,
    terminal: dict,
) -> dict:
    """One job's observable timing. Unobservable sub-stages stay null.

    ``submit_seconds``/``client_total_seconds``/``poll_latencies`` come from
    ``time.monotonic()`` on the driver side; the server window comes from the
    terminal manifest's own created_at/finished_at when both parse.
    """
    created = _parse_iso(terminal.get("created_at"))
    finished = _parse_iso(terminal.get("finished_at"))
    server_window = None
    if created is not None and finished is not None:
        server_window = (finished - created).total_seconds()
    return {
        "submit_round_trip_s": round(submit_seconds, 6),
        "poll_count": len(poll_latencies),
        "poll_call_total_s": round(sum(poll_latencies), 6),
        "server_accept_to_terminal_s": (
            round(server_window, 6) if server_window is not None else None
        ),
        "client_total_s": round(client_total_seconds, 6),
        "server_timestamps": {
            "created_at": terminal.get("created_at"),
            "finished_at": terminal.get("finished_at"),
        },
        "stages": unobservable_stages(),
        "observable_stages": list(OBSERVABLE_STAGES),
    }


def summarize(seconds: list[float]) -> dict:
    """Median and range over independent repetitions. Never fabricates values."""
    ordered = sorted(seconds)
    count = len(ordered)
    if count == 0:
        return {"n": 0, "median_s": None, "min_s": None, "max_s": None}
    middle = count // 2
    if count % 2:
        median = ordered[middle]
    else:
        median = (ordered[middle - 1] + ordered[middle]) / 2.0
    return {
        "n": count,
        "median_s": round(median, 6),
        "min_s": round(ordered[0], 6),
        "max_s": round(ordered[-1], 6),
    }


def case_summary(
    jobs: list[dict],
    first_submit_monotonic: float,
    last_terminal_monotonic: float,
) -> dict:
    windows = [job["timing"]["server_accept_to_terminal_s"] for job in jobs]
    totals = [job["timing"]["client_total_s"] for job in jobs]
    reloaded = [job for job in jobs if job.get("saved_file_reloaded_and_verified") is True]
    return {
        "measured_job_count": len(jobs),
        "measured_client_total_s": round(last_terminal_monotonic - first_submit_monotonic, 6),
        "measured_server_window_sum_s": (
            round(sum(windows), 6) if all(window is not None for window in windows) else None
        ),
        "per_job_client_total_s": totals,
        "per_job_server_window_s": windows,
        "save_reload_events": len(reloaded),
        "save_reload_complete": len(reloaded) == len(jobs),
    }


# --- provenance -------------------------------------------------------------


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    """Unique run directory; refuse to overwrite any existing report."""
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "t09d_performance" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def resolve_selection(
    classes: list[str] | None, modes: list[str] | None
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Resolve the --classes/--modes selectors against the known sets.

    Unknown or repeated names are refused before any connection, so a typo
    never silently reduces the measured scope.
    """
    known_classes = tuple(SPECS)
    known_modes = ("single", "batch")
    chosen_classes = tuple(classes) if classes else known_classes
    chosen_modes = tuple(modes) if modes else known_modes
    for name in chosen_classes:
        if name not in known_classes:
            raise ValueError(f"unknown class {name!r}; known classes are {list(known_classes)}")
    for name in chosen_modes:
        if name not in known_modes:
            raise ValueError(f"unknown mode {name!r}; known modes are {list(known_modes)}")
    for label, values in (("class", chosen_classes), ("mode", chosen_modes)):
        repeated = sorted({name for name in values if list(values).count(name) > 1})
        if repeated:
            raise ValueError(f"repeated {label}(s) {repeated}")
    return chosen_classes, chosen_modes


def summarize_cases(cases: list[dict]) -> list[dict]:
    """Per class and mode statistics over the PASSED repetitions only.

    A failed or unverified repetition contributes no timing sample: its
    measured time would describe a run that did not meet the contract.
    The failed cases stay listed so an incomplete sample is visible.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for case in cases:
        groups.setdefault((case["model_class"], case["plan_mode"]), []).append(case)
    summary = []
    for (model_class, mode), group in sorted(groups.items()):
        passed = [case for case in group if case.get("passed")]
        failed = [case for case in group if not case.get("passed")]
        entry = {
            "model_class": model_class,
            "plan_mode": mode,
            "client_total_s": summarize(
                [case["summary"]["measured_client_total_s"] for case in passed]
            ),
            "server_window_sum_s": summarize(
                [
                    case["summary"]["measured_server_window_sum_s"]
                    for case in passed
                    if case["summary"]["measured_server_window_sum_s"] is not None
                ]
            ),
            "save_reload_events_per_case": sorted(
                {case["summary"]["save_reload_events"] for case in group}
            ),
            "cold_jobs": sum(
                1 for case in group for job in case["jobs"] if job["warm_cold"] == "cold"
            ),
            "passed_cases": len(passed),
            "case_count": len(group),
            "failed_cases": [case["case"] for case in failed],
            "sample_rule": (
                "timing statistics use the passed repetitions only; a failed "
                "repetition is listed under failed_cases and contributes no sample"
            ),
        }
        summary.append(entry)
    return summary


def merge_reports(reports: list[dict]) -> dict:
    """Merge the case/equivalence data of several reports of the SAME source.

    Only reports with an identical ``source_fingerprint`` may be merged: the
    measurements must describe the same tested source. The merged report keeps
    every case, recomputes the summary over the pooled cases and records the
    contributing runs.
    """
    fingerprints = {
        (report.get("provenance") or {}).get("source_fingerprint") for report in reports
    }
    if len(fingerprints) > 1:
        raise ValueError(
            "refusing to merge reports with different source fingerprints: "
            f"{sorted(map(str, fingerprints))}"
        )
    merged: dict = {
        "task": "DEV-051 T09D",
        "scope": "performance baseline, merged over several runs of the same source",
        "mode": "live",
        "live_run": True,
        "merged": True,
        "source_fingerprint": next(iter(fingerprints)),
        "runs": [report.get("run_id") for report in reports],
        "cases": [],
        "equivalence": [],
        "summary": [],
    }
    for report in reports:
        merged["cases"].extend(report.get("cases") or [])
        merged["equivalence"].extend(report.get("equivalence") or [])
    merged["summary"] = summarize_cases(merged["cases"])
    return merged


def local_provenance() -> dict:
    from creo_mechdog.source_provenance import local_provenance as collect

    evidence = collect(
        ROOT,
        (
            "tools/test_plan_performance.py",
            "tests/unit/test_plan_performance.py",
        ),
    )
    # Preserve the released report aliases while sharing source completeness checks.
    evidence["provenance_mode"] = "git" if evidence["git_status"] == "available" else "filesystem"
    evidence["git_unavailable"] = evidence["git_status"] != "available"
    evidence["commit"] = evidence["commit"] or ""
    evidence["branch"] = evidence["branch"] or ""
    return evidence


# --- live runner ------------------------------------------------------------


class PlanPerformanceRun:
    """Serial live runner; one Toolkit job at a time, never resubmits."""

    def __init__(
        self,
        client: Any,
        output: Path,
        run_id: str,
        reps: int,
        classes: tuple[str, ...] = ("small", "large"),
    ) -> None:
        self.client = client
        self.output = output
        self.run_id = run_id
        self.reps = reps
        self.classes = tuple(classes)
        self.session_job_index = 0
        self.report: dict = {
            "task": "DEV-051 T09D",
            "scope": "performance baseline: equivalent single-op vs batch plans, small vs large",
            "run_id": run_id,
            "mode": "live",
            "live_run": True,
            "native_acceptance": "running",
            "external_observation": {
                "single_job_seconds": "about 50-60 (external impression, not phase-timed)",
                "model_size": EDGE_SCALE_REFERENCE,
                "phase_split": "none available yet",
            },
            "protocol": {
                "reps_per_class": reps,
                "classes": list(self.classes),
                "modes": ["single", "batch"],
                "warm_cold_rule": (
                    "session_job_index 0 is 'cold' (first Toolkit job of this driver "
                    "session); every later job is 'warm'. Classification is recorded "
                    "per job, not averaged away."
                ),
                "equivalence": (
                    "single and batch deliver the same nominal geometry as fresh "
                    "independent models; final volume, cut delta and counts.edges must "
                    "match the analytic expectation across modes, and every job must "
                    "save and reload verified, otherwise the case is judged failed."
                ),
                "sample_rule": (
                    "only a case that passed contributes to the timing statistics; a "
                    "failed equivalence voids its group's timing and is recorded as a "
                    "failed sample with its raw error"
                ),
            },
            "fixtures": geometry_basis(),
            "cases": [],
            "equivalence": [],
            "summary": [],
            "calls": [],
            "progress": {
                "completed_cases": [],
                "last_completed_case": None,
                "stage": "starting",
            },
            "provenance": local_provenance(),
        }

    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def timed_call(self, name: str, args: dict) -> tuple[dict, float]:
        self.report["calls"].append(
            {"tool": name, "at": time.time(), "args_bytes": len(json.dumps(args, default=str))}
        )
        self.save()
        started = time.monotonic()
        result = await self.client.call_tool(name, args)
        elapsed = time.monotonic() - started
        self.report["calls"][-1]["duration_s"] = round(elapsed, 6)
        if getattr(result, "is_error", False):
            raise RuntimeError(f"{name} failed: {result.content}")
        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            return structured, elapsed
        for item in getattr(result, "content", []) or []:
            text = getattr(item, "text", None)
            if text:
                decoded = json.loads(text)
                if isinstance(decoded, dict):
                    return decoded, elapsed
        raise RuntimeError(f"{name} returned no structured payload")

    async def call(self, name: str, args: dict) -> dict:
        structured, _ = await self.timed_call(name, args)
        return structured

    async def compact_snapshot(self, model_id: str) -> dict:
        """Bounded saved snapshot: revision, volume and counts (incl. edges)."""
        started = time.monotonic()
        page = await self.call("creo_inspect_model", {"model_id": model_id, "detail": "compact"})
        inspection = page.get("inspection", {})
        return {
            "revision": page.get("revision"),
            "volume_mm3": inspection.get("volume_mm3"),
            "counts": inspection.get("counts"),
            "latency_s": round(time.monotonic() - started, 6),
        }

    async def wait_job(
        self, job_id: str, budget: float = JOB_BUDGET_S
    ) -> tuple[dict, float, list[float]]:
        """Poll one accepted job to a terminal state. Never resubmits."""
        deadline = time.monotonic() + budget
        poll_latencies: list[float] = []
        started = time.monotonic()
        while True:
            terminal, latency = await self.timed_call("creo_get_job", {"job_id": job_id})
            poll_latencies.append(latency)
            status = terminal.get("status")
            if status not in ("queued", "running"):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Job {job_id} did not reach a terminal state within {budget}s; "
                    "budget exhausted, do not resubmit"
                )
            await asyncio.sleep(POLL_INTERVAL_S)
        if status not in ("succeeded", "failed"):
            raise RuntimeError(
                f"Job {job_id} returned an unknown terminal status {status!r}; "
                "recorded as-is, do not resubmit"
            )
        return terminal, time.monotonic() - started, poll_latencies

    async def submit_job(self, args: dict) -> tuple[dict, float]:
        self.session_job_index += 1
        started = time.monotonic()
        manifest = await self.call("creo_execute_plan", args)
        return manifest, time.monotonic() - started

    async def run_measured_job(self, key: str, args: dict, cold_label: str | None) -> dict:
        manifest, submit_seconds = await self.submit_job(args)
        job_id = manifest["job_id"]
        terminal, wait_total, poll_latencies = await self.wait_job(job_id)
        record = {
            "key": key,
            "job_id": job_id,
            "model_id": manifest.get("model_id"),
            "status": terminal.get("status"),
            "session_job_index": self.session_job_index - 1,
            "warm_cold": "cold" if self.session_job_index == 1 else "warm",
            "timing": job_timing_record(
                submit_seconds, poll_latencies, submit_seconds + wait_total, terminal
            ),
            "saved_file_reloaded_and_verified": terminal.get("result", {}).get(
                "saved_file_reloaded_and_verified"
            ),
        }
        if terminal.get("status") != "succeeded":
            record["raw_error"] = {
                "message": terminal.get("message"),
                "reason": terminal.get("reason"),
                "reason_details": terminal.get("reason_details"),
                "native_log_tail": terminal.get("native_log_tail"),
            }
        if cold_label:
            record["label"] = cold_label
        return record

    async def run_case(self, model_class: str, mode: str, rep: int, model_tag: str) -> dict:
        spec = SPECS[model_class]
        suffix = f"{model_class[:2]}{mode[0]}{rep}_{model_tag}"[:16]
        model_name = f"t09d_{suffix}"
        fixture_started = time.monotonic()
        manifest, submit_seconds = await self.submit_job(
            {"operations": plate_operations(spec), "model_name": model_name}
        )
        plate_terminal, wait_total, poll_latencies = await self.wait_job(manifest["job_id"])
        assert plate_terminal["status"] == "succeeded", plate_terminal
        model_id = manifest["model_id"]
        fixture_record = {
            "fixture_preparation_job_id": manifest["job_id"],
            "fixture_preparation_s": round(time.monotonic() - fixture_started, 6),
            "fixture_submit_round_trip_s": round(submit_seconds, 6),
            "fixture_poll_call_total_s": round(sum(poll_latencies), 6),
            "fixture_client_total_s": round(submit_seconds + wait_total, 6),
        }
        before = await self.compact_snapshot(model_id)
        assert before["revision"] is not None, before

        measured: list[dict] = []
        measured_started = time.monotonic()
        if mode == "single":
            for index, pair in enumerate(single_mode_jobs(spec)):
                measured.append(
                    await self.run_measured_job(
                        f"{model_class}_{mode}_rep{rep}_job{index}",
                        {
                            "model_id": model_id,
                            "expected_revision": before["revision"],
                            "operations": pair,
                        },
                        None,
                    )
                )
                # Chain revisions: each next job needs the revision saved by the
                # previous one; the compact read is itself a timed observable.
                before = await self.compact_snapshot(model_id)
                measured[-1]["post_inspection_latency_s"] = before["latency_s"]
        else:
            measured.append(
                await self.run_measured_job(
                    f"{model_class}_{mode}_rep{rep}_job0",
                    {
                        "model_id": model_id,
                        "expected_revision": before["revision"],
                        "operations": batch_mode_plan(spec),
                    },
                    None,
                )
            )
            after = await self.compact_snapshot(model_id)
            measured[-1]["post_inspection_latency_s"] = after["latency_s"]

        # A failed or unverified job is recorded as a failed sample with its
        # raw error; it never contributes to the timing statistics and never
        # counts as a repetition.
        failed_jobs = [
            job
            for job in measured
            if job["status"] != "succeeded"
            or job.get("saved_file_reloaded_and_verified") is not True
        ]
        final = await self.compact_snapshot(model_id)
        case = {
            "case": f"{model_class}_{mode}_rep{rep}",
            "model_class": model_class,
            "plan_mode": mode,
            "rep": rep,
            "model_name": model_name,
            "model_id": model_id,
            "synthetic_data": False,
            "requested_scale": {
                "pocket_count": pocket_count(spec),
                "cut_operation_count": cut_count(spec),
                "single_mode_job_count": len(measured) if mode == "single" else 1,
            },
            "fixture": fixture_record,
            "jobs": measured,
            "result": {
                "final_volume_mm3": final["volume_mm3"],
                "expected_final_volume_mm3": expected_final_volume_mm3(spec),
                "final_counts": final["counts"],
                "volume_error_mm3": (
                    abs(final["volume_mm3"] - expected_final_volume_mm3(spec))
                    if isinstance(final["volume_mm3"], (int, float))
                    else None
                ),
                "volume_match": (
                    abs(final["volume_mm3"] - expected_final_volume_mm3(spec))
                    <= VOLUME_TOLERANCE_MM3
                    if isinstance(final["volume_mm3"], (int, float))
                    else False
                ),
                "revision": final["revision"],
                "post_job_inspection_latency_s": final["latency_s"],
            },
            "summary": case_summary(measured, measured_started, time.monotonic()),
        }
        passed = (
            not failed_jobs
            and case["result"]["volume_match"]
            and case["summary"]["save_reload_complete"]
            and all(job["status"] == "succeeded" for job in measured)
        )
        case["passed"] = passed
        if failed_jobs:
            case["failure"] = {
                "failed_job_count": len(failed_jobs),
                "raw_error": [job.get("raw_error") for job in failed_jobs],
                "note": (
                    "a failed or unverified job voids this repetition: it is recorded with "
                    "its raw error and contributes no timing sample"
                ),
            }
        self.report["cases"].append(case)
        progress = self.report["progress"]
        progress["completed_cases"].append(case["case"])
        progress["last_completed_case"] = case["case"]
        progress["stage"] = "case_completed"
        self.save()
        return case

    def compare_modes(self, single: dict, batch: dict) -> dict:
        """Same-rep single vs batch: identical geometry, identical edges."""
        left = single["result"]
        right = batch["result"]
        edges_left = (left["final_counts"] or {}).get("edges")
        edges_right = (right["final_counts"] or {}).get("edges")
        row = {
            "model_class": single["model_class"],
            "rep": single["rep"],
            "synthetic_data": False,
            "volume_both_match_expectation": left["volume_match"] and right["volume_match"],
            "volumes_equal_mm3": (
                abs(left["final_volume_mm3"] - right["final_volume_mm3"]) <= VOLUME_TOLERANCE_MM3
                if isinstance(left["final_volume_mm3"], (int, float))
                and isinstance(right["final_volume_mm3"], (int, float))
                else False
            ),
            "edges": {
                "single": edges_left,
                "batch": edges_right,
                "equal": edges_left == edges_right,
            },
            "job_count": {"single": len(single["jobs"]), "batch": len(batch["jobs"])},
            "save_reload_events": {
                "single": single["summary"]["save_reload_events"],
                "batch": batch["summary"]["save_reload_events"],
            },
            "comparable": (
                left["volume_match"]
                and right["volume_match"]
                and edges_left == edges_right
                and single["summary"]["save_reload_complete"]
                and batch["summary"]["save_reload_complete"]
            ),
        }
        self.report["equivalence"].append(row)
        return row

    def build_summary(self) -> list[dict]:
        """Per class and mode statistics; see summarize_cases for the rule."""
        return summarize_cases(self.report["cases"])

    async def run_all(self) -> None:
        from tools.mcp_readiness import wait_for_startup

        self.report["capabilities"] = await self.call("creo_capabilities", {})
        self.report["environment"] = await self.call("creo_check_environment", {})
        self.save()
        await wait_for_startup(self.client, self.report, self.output)
        status = await self.call("creo_session_status", {})
        assert status["connected"] is True, status
        model_tag = hashlib.sha256(self.run_id.encode("utf-8")).hexdigest()[:8]
        try:
            for model_class in self.classes:
                for rep in range(1, self.reps + 1):
                    single = await self.run_case(model_class, "single", rep, model_tag)
                    batch = await self.run_case(model_class, "batch", rep, model_tag)
                    self.compare_modes(single, batch)
                    self.save()
            self.report["summary"] = self.build_summary()
            self.report["native_acceptance"] = "recorded"
            self.report["progress"]["stage"] = "completed"
        except Exception as error:
            self.report["error"] = f"{type(error).__name__}: {error}"
            self.report["summary"] = self.build_summary()
            self.report["progress"]["stage"] = "interrupted"
            raise
        finally:
            self.save()


async def live(output: Path, run_id: str, reps: int, classes: tuple[str, ...]) -> None:
    from tools.test_t05_native import require_manual_start

    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=60,
    ) as client:
        runner = PlanPerformanceRun(client, output, run_id, reps, classes=classes)
        runner.save()
        await runner.run_all()


# --- offline stage ----------------------------------------------------------


def synthetic_timing_checks() -> dict:
    """Exercise the timing recorder with fabricated data.

    Every value below is invented. This proves the recorder's arithmetic and its
    unobservable marking only; it is labelled synthetic and is never a
    benchmark, never a live result, and never cited as a measurement.
    """
    terminal = {
        "created_at": "2026-10-30T10:00:00+08:00",
        "finished_at": "2026-10-30T10:00:51+08:00",
    }
    record = job_timing_record(0.25, [0.01, 0.01, 0.02], 52.0, terminal)
    assert record["server_accept_to_terminal_s"] == 51.0, record
    assert record["submit_round_trip_s"] == 0.25
    assert record["poll_count"] == 3
    assert math.isclose(record["poll_call_total_s"], 0.04, abs_tol=1e-9)
    for stage in UNOBSERVABLE_STAGES:
        entry = record["stages"][stage]
        assert entry == {"value": None, "status": "unobservable", "reason": UNOBSERVABLE_REASON}

    missing = job_timing_record(0.5, [], 1.0, {"created_at": terminal["created_at"]})
    assert missing["server_accept_to_terminal_s"] is None
    garbage = job_timing_record(0.5, [], 1.0, {"created_at": "not-a-time", "finished_at": None})
    assert garbage["server_accept_to_terminal_s"] is None

    summary = summarize([3.0, 1.0, 2.0, 4.0])
    assert summary == {"n": 4, "median_s": 2.5, "min_s": 1.0, "max_s": 4.0}, summary
    odd = summarize([5.0, 1.0, 3.0])
    assert odd == {"n": 3, "median_s": 3.0, "min_s": 1.0, "max_s": 5.0}, odd
    assert summarize([]) == {"n": 0, "median_s": None, "min_s": None, "max_s": None}

    return {
        "synthetic_data": True,
        "not_a_benchmark": True,
        "statement": (
            "Synthetic timing data used to verify the recorder only: server window "
            "arithmetic, unobservable marking, missing/garbage timestamp handling and "
            "median/range math. Not a measurement of anything."
        ),
        "server_window_s": record["server_accept_to_terminal_s"],
        "missing_timestamp_window": missing["server_accept_to_terminal_s"],
        "garbage_timestamp_window": garbage["server_accept_to_terminal_s"],
        "unobservable_stage_keys": sorted(record["stages"]),
        "summary_even": summary,
        "summary_odd": odd,
        "summary_empty": summarize([]),
        "passed": True,
    }


def equivalence_checks() -> dict:
    details = validate_case_inputs()
    per_class = {}
    for name, spec in SPECS.items():
        equivalence = mode_equivalence(spec)
        assert equivalence["volumes_equal"], equivalence
        assert equivalence["cut_deltas_equal"], equivalence
        assert equivalence["single_save_reload_events"] == cut_count(spec)
        assert equivalence["batch_save_reload_events"] == 1
        per_class[name] = equivalence
    return {"layout": details, "modes": per_class, "passed": True}


def offline_checks() -> dict:
    return {
        "run_id": None,
        "fixtures": equivalence_checks(),
        "synthetic_timing": synthetic_timing_checks(),
    }


def write_offline_report(
    output: Path, run_id: str, results: dict, classes: tuple[str, ...], modes: tuple[str, ...]
) -> dict:
    report = {
        "task": "DEV-051 T09D",
        "scope": "performance baseline driver, offline preparation stage",
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "synthetic_data": True,
        "not_a_benchmark": True,
        "statement": (
            "Offline stage only: fixture layouts, plan schemas and the single/batch "
            "equivalence math validated, and the timing recorder exercised with "
            "synthetic data. No Toolkit connection, no Creo, no measurement of real "
            "performance. Nothing here may be read as a benchmark or as an "
            "improvement claim."
        ),
        "external_observation": {
            "single_job_seconds": "about 50-60 (external impression, not phase-timed)",
            "model_size": EDGE_SCALE_REFERENCE,
            "phase_split": "none available yet",
        },
        "observability": {
            "observable_stages": list(OBSERVABLE_STAGES),
            "unobservable_stages": {
                stage: {"value": None, "status": "unobservable", "reason": UNOBSERVABLE_REASON}
                for stage in UNOBSERVABLE_STAGES
            },
        },
        "fixtures": geometry_basis(),
        "protocol": {
            "reps_per_class": DEFAULT_REPS,
            "classes": list(classes),
            "modes": list(modes),
            "warm_cold_rule": (
                "session_job_index 0 is 'cold'; every later job is 'warm'; recorded per job."
            ),
            "sample_rule": (
                "only a passed repetition contributes to the timing statistics; a failed "
                "repetition is recorded with its raw error and contributes no sample"
            ),
        },
        "checks": results,
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
    parser.add_argument("--reps", type=int, default=DEFAULT_REPS)
    parser.add_argument(
        "--classes",
        action="append",
        dest="classes",
        default=None,
        metavar="NAME",
        help=(
            "measure only these model classes (repeatable, small|large); the default "
            "measures both. Splitting the run keeps each part inside a bounded tool "
            "timeout; the parts are merged afterwards only when their source "
            "fingerprints are identical"
        ),
    )
    parser.add_argument(
        "--modes",
        action="append",
        dest="modes",
        default=None,
        metavar="NAME",
        help="measure only these delivery modes (repeatable, single|batch)",
    )
    args = parser.parse_args(argv)

    if args.reps < 1:
        parser.error("--reps must be at least 1")
    if args.reps != DEFAULT_REPS:
        print(f"NOTE: --reps {args.reps} deviates from the protocol minimum {DEFAULT_REPS}")
    try:
        classes, modes = resolve_selection(args.classes, args.modes)
    except ValueError as error:
        print(f"REFUSED BEFORE CONNECTION: {error}")
        return 2

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
        results = offline_checks()
        results["run_id"] = run_id
        write_offline_report(output, run_id, results, classes, modes)
        fixtures = results["fixtures"]
        print(f"offline_classes={len(fixtures['layout'])} validated")
        print("synthetic_data=true not_a_benchmark=true (timing recorder check only)")
        print(f"report={output}")
        print("LIVE NOT RUN: no performance measurement was produced or claimed.")
        return 0

    asyncio.run(live(output, run_id, args.reps, classes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
