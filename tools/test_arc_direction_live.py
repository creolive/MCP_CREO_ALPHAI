"""FEAT-034 live acceptance: explicit arc ``dir`` shapes the intended segment.

Default is strict offline (oracle tables only). ``--live --confirm-session-usable``
connects to a Creo session the user opened manually and measures one arc+chord
extrusion per case; it never launches or closes Creo and never resubmits a job.

Geometry: radius 10 mm arc plus its chord, extruded 5 mm. Independent oracle is
``depth * 0.5 * r^2 * (theta - sin(theta))`` with theta from the T02 sweep rule,
computed here without calling production normalization.

Judgment is strict and reads only real result fields: a case passes only when
the measured volume matches the oracle, a native ``arc_geometry`` echo reports
the declared direction and sweep, and ``result.saved_file_reloaded_and_verified``
is exactly ``true``. Missing echo or missing reload evidence is a failure, never
a silent pass, and the reload flag is never taken from the terminal top level.
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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RADIUS_MM = 10.0
DEPTH_MM = 5.0
TOLERANCE_MM3 = 0.01
SWEEP_TOLERANCE_DEG = 1e-6


def oracle_sweep_deg(start_deg: float, end_deg: float, direction: int) -> float:
    if direction > 0:
        return (end_deg - start_deg) % 360.0
    return (start_deg - end_deg) % 360.0


def oracle_volume_mm3(start_deg: float, end_deg: float, direction: int) -> float:
    theta = math.radians(oracle_sweep_deg(start_deg, end_deg, direction))
    return DEPTH_MM * 0.5 * RADIUS_MM * RADIUS_MM * (theta - math.sin(theta))


def on_circle(angle_deg: float) -> list[float]:
    angle = math.radians(angle_deg)
    return [RADIUS_MM * math.cos(angle), RADIUS_MM * math.sin(angle)]


def arc_chord_entities(start_deg: float, end_deg: float, direction: int | None) -> list[dict]:
    """The arc+chord profile; names must match for in-place update entries."""
    arc: dict[str, Any] = {
        "type": "arc",
        "name": "arc_a",
        "center": [0.0, 0.0],
        "radius": RADIUS_MM,
        "start_angle": start_deg,
        "end_angle": end_deg,
    }
    if direction is not None:
        arc["dir"] = direction
    chord = {
        "type": "line",
        "name": "chord_a",
        "start": on_circle(end_deg),
        "end": on_circle(start_deg),
    }
    return [arc, chord]


def operations(
    start_deg: float, end_deg: float, direction: int | None, plane: str = "XY"
) -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "seg",
            "plane": plane,
            "entities": arc_chord_entities(start_deg, end_deg, direction),
            "dimensioning": "coordinates",
        },
        {"op": "extrude", "label": "body", "sketch": "seg", "depth": DEPTH_MM},
    ]


def detached_chord_entities(start_deg: float, end_deg: float, direction: int | None) -> list[dict]:
    """Same names/types as the base profile, but the chord misses the arc ends.

    Schema-valid input that cannot regenerate the dependent extrusion: the
    native failure exercises the real checkpoint rollback path.
    """
    entities = arc_chord_entities(start_deg, end_deg, direction)
    for entity in entities:
        if entity["type"] == "line":
            entity["start"] = [entity["start"][0] + 3.0, entity["start"][1] + 3.0]
            entity["end"] = [entity["end"][0] + 3.0, entity["end"][1] + 3.0]
    return entities


# The four geometry cases already accepted on 2026-10-29. Their angles, dir
# values and oracle volumes must not change: they pin the legacy semantics.
CASES: list[dict] = [
    {"case": "legacy_0_to_90", "start": 0.0, "end": 90.0, "dir": None},
    {"case": "legacy_90_to_0", "start": 90.0, "end": 0.0, "dir": None},
    {"case": "dir_minus1_90_to_0", "start": 90.0, "end": 0.0, "dir": -1},
    {"case": "dir_minus1_0_to_90", "start": 0.0, "end": 90.0, "dir": -1},
]

# T02 phase 2 coverage: a tilted sketch frame and in-place direction switches
# (including a zero-crossing angle pair), judged by the same strict verdict.
FRAME_CASES: list[dict] = [
    {"case": "tilted_xz_dir_minus1_0_to_90", "plane": "XZ", "start": 0.0, "end": 90.0, "dir": -1},
]

EDIT_CASES: list[dict] = [
    {"case": "edit_switch_dir_0_to_90", "start": 0.0, "end": 90.0, "from_dir": 1, "to_dir": -1},
    {
        "case": "edit_switch_dir_cross_zero",
        "start": 350.0,
        "end": 10.0,
        "from_dir": 1,
        "to_dir": -1,
    },
    {
        "case": "edit_switch_dir_tilted_xz",
        "plane": "XZ",
        "start": 0.0,
        "end": 90.0,
        "from_dir": 1,
        "to_dir": -1,
    },
]

ILLEGAL_EDIT_CASES: list[dict] = [
    {"case": "illegal_dir_zero", "kind": "schema", "start": 0.0, "end": 90.0, "dir": 0},
    {"case": "illegal_dir_float", "kind": "schema", "start": 0.0, "end": 90.0, "dir": -1.0},
    {"case": "illegal_zero_sweep", "kind": "schema", "start": 45.0, "end": 45.0, "dir": 1},
    {"case": "illegal_full_circle", "kind": "schema", "start": 0.0, "end": 360.0, "dir": 1},
    {"case": "illegal_open_profile", "kind": "native", "start": 0.0, "end": 90.0, "dir": 1},
]


# --- strict verdicts (pure; exercised by tests/unit/test_arc_direction_live.py)


def result_block(terminal: dict | None) -> dict:
    """The native result block of a job terminal.

    ``saved_file_reloaded_and_verified``, the operation echo and the aliases
    live inside this block and nowhere else.
    """
    result = (terminal or {}).get("result")
    return result if isinstance(result, dict) else {}


def reload_flag(terminal: dict | None) -> bool | None:
    """Reload evidence from ``result.saved_file_reloaded_and_verified``.

    The terminal top level never carries this flag; reading it there always
    yields ``None`` and must not be treated as "no save happened".
    """
    return result_block(terminal).get("saved_file_reloaded_and_verified")


def arc_echoes(terminal: dict | None) -> list[dict]:
    found = []
    for operation in result_block(terminal).get("operations") or []:
        if not isinstance(operation, dict):
            continue
        for entity in operation.get("arc_geometry") or []:
            if isinstance(entity, dict):
                found.append(entity)
    return found


def native_arc_echo(terminal: dict | None, name: str = "arc_a") -> dict | None:
    """The measured echo of one arc entity, or None when none was reported."""
    found = arc_echoes(terminal)
    for entity in found:
        if entity.get("name") == name:
            return entity
    return found[0] if len(found) == 1 else None


def numeric_volume_mm3(value: Any) -> float | None:
    """A finite measured volume, or None; booleans and null are never numbers.

    ``True``/``False`` are int subclasses, so a plain isinstance check would
    read them as 1.0/0.0 mm3 and a NaN would slip past every tolerance
    comparison; evidence that is not a finite number is missing evidence.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def measured_volume_mm3(payload: dict | None) -> float | None:
    """Volume from an inspection payload (job result block or inspect reply).

    The real evidence sits in exactly one layer: ``inspection`` (inspect
    replies and legacy inline job results) or ``inspection_summary`` (job
    results after the BUG-077 split, where the full payload moved behind
    ``inspection_ref``). A layer that is present but lacks ``volume_mm3`` is
    missing evidence: the other layers are never mined for a stale value
    (BUG-093: the N07 refresh carried 1428.0972451017303 inside
    ``inspection_summary`` while the driver read only ``inspection``/top level
    and judged ``volume_missing``).
    """
    source = payload or {}
    for key in ("inspection", "inspection_summary"):
        if key in source and isinstance(source[key], dict):
            return numeric_volume_mm3(source[key].get("volume_mm3"))
    return numeric_volume_mm3(source.get("volume_mm3"))


def echo_failures(echo: dict | None, direction: int, sweep_deg: float) -> list[str]:
    """A missing or non-native echo always fails; a real echo must agree."""
    if echo is None:
        return ["native_arc_echo_missing"]
    if echo.get("source") != "native":
        return ["native_arc_echo_not_measured"]
    failures = []
    if echo.get("dir") != direction:
        failures.append("arc_echo_dir_mismatch")
    sweep = echo.get("sweep_deg")
    if not isinstance(sweep, (int, float)):
        failures.append("native_arc_echo_missing")
    elif abs(float(sweep) - sweep_deg) > SWEEP_TOLERANCE_DEG:
        failures.append("arc_echo_sweep_mismatch")
    return failures


def edit_identity(before: dict | None, after: dict | None) -> dict:
    """In-place identity evidence across an edit; only contradictions are judged.

    ``preserved_feature_id`` on the update record and the ``body`` alias id
    show the sketch and the downstream extrude were edited in place. Absent
    data is reported as unavailable and is not judged; a present disagreement
    is a failure for the caller.
    """
    before_aliases = result_block(before).get("aliases")
    after_aliases = result_block(after).get("aliases")

    def alias_id(aliases: Any, label: str) -> Any:
        entry = aliases.get(label) if isinstance(aliases, dict) else None
        return entry.get("feature_id") if isinstance(entry, dict) else None

    before_sketch = alias_id(before_aliases, "seg")
    preserved = None
    for operation in result_block(after).get("operations") or []:
        if isinstance(operation, dict) and "preserved_feature_id" in operation:
            preserved = operation["preserved_feature_id"]
    before_body = alias_id(before_aliases, "body")
    after_body = alias_id(after_aliases, "body")
    return {
        "sketch_feature_id_preserved": (
            None if before_sketch is None or preserved is None else preserved == before_sketch
        ),
        "downstream_feature_id_preserved": (
            None if before_body is None or after_body is None else before_body == after_body
        ),
        "before_sketch_feature_id": before_sketch,
        "preserved_feature_id": preserved,
        "before_downstream_feature_id": before_body,
        "after_downstream_feature_id": after_body,
    }


def judge_create_case(case: dict, terminal: dict | None, inspection: dict | None) -> dict:
    """Strict verdict for one arc+chord extrusion.

    ``passed`` requires all of: the job succeeded, the measured volume matches
    the independent oracle, a native arc echo reports the declared direction
    and sweep, and ``result.saved_file_reloaded_and_verified`` is exactly
    ``True``. Volume alone never passes a case.
    """
    direction = 1 if case.get("dir") is None else case["dir"]
    expected_sweep = oracle_sweep_deg(case["start"], case["end"], direction)
    expected_volume = oracle_volume_mm3(case["start"], case["end"], direction)
    measured = measured_volume_mm3(inspection)
    echo = native_arc_echo(terminal)
    reloaded = reload_flag(terminal)
    failures = []
    if (terminal or {}).get("status") != "succeeded":
        failures.append("job_not_succeeded")
    if measured is None:
        failures.append("volume_missing")
    elif abs(measured - expected_volume) > TOLERANCE_MM3:
        failures.append("volume_mismatch")
    failures.extend(echo_failures(echo, direction, expected_sweep))
    if reloaded is not True:
        failures.append("reload_verification_missing")
    return {
        "case": case["case"],
        "stage": case.get("stage", "create"),
        "dir": case.get("dir"),
        "start_angle": case["start"],
        "end_angle": case["end"],
        "job_id": (terminal or {}).get("job_id"),
        "model_id": (terminal or {}).get("model_id"),
        "revision": (terminal or {}).get("revision"),
        "expected_sweep_deg": expected_sweep,
        "expected_volume_mm3": expected_volume,
        "measured_volume_mm3": measured,
        "abs_error_mm3": None if measured is None else abs(measured - expected_volume),
        "arc_echo": echo,
        "saved_file_reloaded_and_verified": reloaded,
        "failures": failures,
        "passed": not failures,
    }


def judge_direction_edit(
    case: dict, before: dict | None, after: dict | None, inspection: dict | None
) -> dict:
    """In-place direction switch: the geometry must really change downstream.

    ``before``/``after`` are the create and update job terminals. ``passed``
    requires: the update succeeded with reload evidence, the volume equals the
    to_dir oracle and no longer the from_dir one, a native echo with the new
    direction and sweep, and a revision incremented by exactly one. A
    contradicted feature identity also fails; missing identity data is recorded
    but not judged.
    """
    from_dir = case["from_dir"]
    to_dir = case["to_dir"]
    expected_before = oracle_volume_mm3(case["start"], case["end"], from_dir)
    expected_after = oracle_volume_mm3(case["start"], case["end"], to_dir)
    expected_sweep = oracle_sweep_deg(case["start"], case["end"], to_dir)
    measured = measured_volume_mm3(inspection)
    echo = native_arc_echo(after)
    reloaded = reload_flag(after)
    failures = []
    if (after or {}).get("status") != "succeeded":
        failures.append("job_not_succeeded")
    if measured is None:
        failures.append("volume_missing")
    else:
        if abs(measured - expected_after) > TOLERANCE_MM3:
            failures.append("volume_mismatch")
        if abs(measured - expected_before) <= TOLERANCE_MM3:
            failures.append("geometry_did_not_change")
    failures.extend(echo_failures(echo, to_dir, expected_sweep))
    if reloaded is not True:
        failures.append("reload_verification_missing")
    before_revision = (before or {}).get("revision")
    after_revision = (after or {}).get("revision")
    if (
        not isinstance(before_revision, int)
        or not isinstance(after_revision, int)
        or after_revision != before_revision + 1
    ):
        failures.append("revision_not_incremented")
    identity = edit_identity(before, after)
    if identity["sketch_feature_id_preserved"] is False:
        failures.append("sketch_identity_changed")
    if identity["downstream_feature_id_preserved"] is False:
        failures.append("downstream_identity_changed")
    return {
        "case": case["case"],
        "stage": "direction_edit",
        "plane": case.get("plane", "XY"),
        "start_angle": case["start"],
        "end_angle": case["end"],
        "from_dir": from_dir,
        "to_dir": to_dir,
        "job_id": (after or {}).get("job_id"),
        "model_id": (after or {}).get("model_id"),
        "revision_before": before_revision,
        "revision_after": after_revision,
        "expected_volume_before_mm3": expected_before,
        "expected_volume_mm3": expected_after,
        "measured_volume_mm3": measured,
        "abs_error_mm3": None if measured is None else abs(measured - expected_after),
        "arc_echo": echo,
        "saved_file_reloaded_and_verified": reloaded,
        "identity": identity,
        "failures": failures,
        "passed": not failures,
    }


def judge_illegal_edit(
    case: dict,
    outcome: dict,
    before_volume: float | None,
    after_volume: float | None,
    revision_before: int | None,
    revision_after: int | None,
    *,
    model_id: str | None = None,
    refresh_terminal: dict | None = None,
) -> dict:
    """An illegal edit must be rejected and leave the model untouched.

    ``outcome`` carries what the submission returned (``rejected``,
    ``error_text``, ``terminal``). ``passed`` requires the rejection, an
    unchanged live volume and an unchanged model revision; a native-failure
    terminal additionally carries its rollback evidence in the row. Missing
    revision evidence is a failure, never a silent pass. When the caller
    supplies the evidence refresh job, a terminal for a different model_id is
    also a failure: same-source volume comparison only means something when
    the refresh measured the model the edit targeted.
    """
    terminal = outcome.get("terminal") or {}
    rejected = bool(outcome.get("rejected"))
    failures = []
    if not rejected:
        failures.append("illegal_edit_accepted")
    if after_volume is None:
        failures.append("volume_missing")
    elif before_volume is None:
        failures.append("baseline_volume_missing")
    elif abs(after_volume - before_volume) > TOLERANCE_MM3:
        failures.append("model_changed_after_illegal_edit")
    if not isinstance(revision_before, int) or not isinstance(revision_after, int):
        failures.append("revision_evidence_missing")
    elif revision_after != revision_before:
        failures.append("revision_changed_after_illegal_edit")
    refreshed_model_id = (
        refresh_terminal.get("model_id") if isinstance(refresh_terminal, dict) else None
    )
    if model_id is not None and refresh_terminal is not None and refreshed_model_id != model_id:
        failures.append("wrong_model_refreshed")
    result = result_block(terminal)
    rollback = (
        {
            key: result.get(key)
            for key in (
                "rollback_succeeded",
                "model_unchanged",
                "rollback_message",
                "rollback_code",
            )
        }
        if terminal
        else None
    )
    if terminal:
        if isinstance(rollback, dict) and rollback.get("model_unchanged") is False:
            failures.append("model_changed_after_illegal_edit")
        if not (result.get("rollback_succeeded") is True or result.get("model_unchanged") is True):
            # A job that ran and failed must show a real rollback (or proof the
            # model was never touched); silence here is not evidence.
            failures.append("rollback_not_verified")
    return {
        "case": case["case"],
        "stage": "illegal_edit",
        "kind": case.get("kind"),
        "job_id": outcome.get("job_id"),
        "error_text": outcome.get("error_text"),
        "terminal_status": terminal.get("status"),
        "rollback": rollback,
        "expected_model_id": model_id,
        "refreshed_model_id": refreshed_model_id,
        "baseline_volume_mm3": before_volume,
        "measured_volume_mm3": after_volume,
        "revision_before": revision_before,
        "revision_after": revision_after,
        "failures": sorted(set(failures)),
        "passed": not failures,
    }


def judge_save_reload(
    case_name: str, save_terminal: dict | None, expected_volume: float, inspection: dict | None
) -> dict:
    """Explicit save: reload evidence from the real field and unchanged geometry.

    The expected volume is direction-discriminating (the two segment volumes
    differ by an order of magnitude), so the post-reload measurement also
    evidences that the direction survived the save.
    """
    measured = measured_volume_mm3(inspection)
    reloaded = reload_flag(save_terminal)
    failures = []
    if (save_terminal or {}).get("status") != "succeeded":
        failures.append("job_not_succeeded")
    if reloaded is not True:
        failures.append("reload_verification_missing")
    if measured is None:
        failures.append("volume_missing")
    elif abs(measured - expected_volume) > TOLERANCE_MM3:
        failures.append("volume_mismatch")
    return {
        "case": case_name,
        "stage": "save_reload",
        "job_id": (save_terminal or {}).get("job_id"),
        "expected_volume_mm3": expected_volume,
        "measured_volume_mm3": measured,
        "abs_error_mm3": None if measured is None else abs(measured - expected_volume),
        "saved_file_reloaded_and_verified": reloaded,
        "failures": failures,
        "passed": not failures,
    }


def require_manual_start(config_file: Path) -> None:
    settings = json.loads(config_file.read_text(encoding="utf-8-sig"))
    if settings.get("auto_start_creo") is not False:
        raise ValueError(
            "Live acceptance requires config.json auto_start_creo=false; no client was started"
        )


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    """Refuse to overwrite an existing report before anything else runs."""
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "arc_direction_live" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


async def live(output: Path) -> None:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    from tools.test_arc_direction import local_provenance

    require_manual_start(ROOT / "config.json")
    report: dict[str, Any] = {
        "task": "DEV-051 T02",
        "scope": ("FEAT-034 explicit arc dir: creation, direction edit, illegal edit, save/reload"),
        "mode": "live",
        "run_id": output.parent.name,
        "started_at": time.time(),
        "provenance": local_provenance(),
        "cases": [],
        "edit_cases": [],
        "illegal_edits": [],
        "calls": 0,
    }

    def flush() -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    flush()
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=120) as client:

        async def call(name: str, args: dict) -> Any:
            report["calls"] += 1
            result = await client.call_tool(name, args)
            if result.is_error:
                raise RuntimeError(f"{name}: {result.content}")
            return result

        async def try_call(name: str, args: dict) -> tuple[Any, str | None]:
            """A submission that may be legally rejected; never raises on isError."""
            report["calls"] += 1
            result = await client.call_tool(name, args)
            if result.is_error:
                return None, "".join(
                    getattr(content, "text", "") for content in (result.content or [])
                )
            return result, None

        async def settle(job_id: str) -> dict:
            """Poll an accepted job to a terminal state; never resubmit."""
            poll_deadline = time.monotonic() + 300
            while True:
                terminal = (await call("creo_get_job", {"job_id": job_id})).structured_content or {}
                if terminal.get("status") not in ("queued", "running"):
                    return terminal
                if time.monotonic() >= poll_deadline:
                    raise TimeoutError(f"{job_id} did not settle; do not resubmit")
                await asyncio.sleep(1)

        async def submit_job(name: str, args: dict) -> dict:
            body = (await call(name, args)).structured_content or {}
            job_id = body.get("job_id")
            if not job_id:
                raise RuntimeError(f"{name} returned no job_id: {body}")
            terminal = await settle(job_id)
            if terminal.get("status") != "succeeded":
                raise AssertionError(terminal)
            return terminal

        async def inspect_payload(model_id: str) -> dict:
            return (
                await call("creo_inspect_model", {"model_id": model_id})
            ).structured_content or {}

        deadline = time.monotonic() + 180
        while True:
            status = (await call("creo_startup_status", {})).structured_content or {}
            if status.get("state") == "ready" and status.get("connected") is True:
                break
            if time.monotonic() >= deadline:
                flush()
                raise TimeoutError("session not ready; nothing submitted")
            await asyncio.sleep(1)
        report["status"] = status
        flush()

        # Stage 1+2: creation (the four legacy cases plus the tilted frame)
        # with an explicit save and reload verification for every model.
        for case in [*CASES, *FRAME_CASES]:
            terminal = await submit_job(
                "creo_execute_plan",
                {
                    "operations": operations(
                        case["start"], case["end"], case["dir"], case.get("plane", "XY")
                    )
                },
            )
            model_id = terminal.get("model_id")
            row = judge_create_case(case, terminal, await inspect_payload(model_id))
            saved = await submit_job(
                "creo_save_model",
                {"model_id": model_id, "expected_revision": terminal.get("revision")},
            )
            save_row = judge_save_reload(
                case["case"], saved, row["expected_volume_mm3"], await inspect_payload(model_id)
            )
            row["save_reload"] = save_row
            row["failures"] = [
                *row["failures"],
                *(f"save_reload:{name}" for name in save_row["failures"]),
            ]
            row["passed"] = not row["failures"]
            report["cases"].append(row)
            flush()
            if not row["passed"]:
                raise AssertionError(row)

        # Stage 3: in-place direction switch on fresh models; the downstream
        # extrude must follow the new section and the revision must advance.
        # Each entry keeps the latest terminal (the save job) and the measured
        # post-save volume as the baseline for the later illegal-edit stage,
        # whose expected_revision must be the current one after that save.
        edit_models: list[tuple[str, dict, dict, float | None]] = []
        for case in EDIT_CASES:
            terminal = await submit_job(
                "creo_execute_plan",
                {
                    "operations": operations(
                        case["start"], case["end"], case["from_dir"], case.get("plane", "XY")
                    )
                },
            )
            model_id = terminal.get("model_id")
            create_case = {
                "case": case["case"] + "_create",
                "start": case["start"],
                "end": case["end"],
                "dir": case["from_dir"],
            }
            create_row = judge_create_case(create_case, terminal, await inspect_payload(model_id))
            edited = await submit_job(
                "creo_update_sketch_geometry",
                {
                    "model_id": model_id,
                    "expected_revision": terminal.get("revision"),
                    "sketch": "seg",
                    "entities": arc_chord_entities(case["start"], case["end"], case["to_dir"]),
                    "dimensioning": "coordinates",
                },
            )
            edit_row = judge_direction_edit(case, terminal, edited, await inspect_payload(model_id))
            saved = await submit_job(
                "creo_save_model",
                {"model_id": model_id, "expected_revision": edited.get("revision")},
            )
            save_row = judge_save_reload(
                case["case"],
                saved,
                edit_row["expected_volume_mm3"],
                await inspect_payload(model_id),
            )
            edit_row["create"] = create_row
            edit_row["save_reload"] = save_row
            edit_row["failures"] = [
                *edit_row["failures"],
                *(f"create:{name}" for name in create_row["failures"]),
                *(f"save_reload:{name}" for name in save_row["failures"]),
            ]
            edit_row["passed"] = not edit_row["failures"]
            report["edit_cases"].append(edit_row)
            flush()
            if not edit_row["passed"]:
                raise AssertionError(edit_row)
            edit_models.append(
                (model_id, saved, case, edit_row["save_reload"]["measured_volume_mm3"])
            )

        # Stage 4: illegal edits on the first edited model must be rejected
        # without geometry or revision damage, then a legal edit must still work.
        # The unchanged check compares the same live measurement before and
        # after each attempt, never the oracle against a measurement.
        model_id, latest, case, baseline_volume = edit_models[0]
        current_revision = latest.get("revision")
        for illegal in ILLEGAL_EDIT_CASES:
            entities = (
                detached_chord_entities(illegal["start"], illegal["end"], illegal["dir"])
                if illegal["kind"] == "native"
                else arc_chord_entities(illegal["start"], illegal["end"], illegal["dir"])
            )
            outcome: dict[str, Any] = {
                "rejected": False,
                "error_text": None,
                "terminal": None,
                "job_id": None,
            }
            result, error_text = await try_call(
                "creo_update_sketch_geometry",
                {
                    "model_id": model_id,
                    "expected_revision": current_revision,
                    "sketch": "seg",
                    "entities": entities,
                    "dimensioning": "coordinates",
                },
            )
            if error_text is not None:
                outcome.update(rejected=True, error_text=error_text)
            else:
                body = result.structured_content or {}
                job_id = body.get("job_id")
                outcome["job_id"] = job_id
                if not job_id:
                    outcome.update(rejected=True, error_text=json.dumps(body, ensure_ascii=False))
                else:
                    terminal = await settle(job_id)
                    outcome["terminal"] = terminal
                    outcome["rejected"] = terminal.get("status") != "succeeded"
            refreshed = await submit_job("creo_refresh_model", {"model_id": model_id})
            row = judge_illegal_edit(
                illegal,
                outcome,
                baseline_volume,
                measured_volume_mm3(result_block(refreshed)),
                current_revision,
                refreshed.get("revision"),
                model_id=model_id,
                refresh_terminal=refreshed,
            )
            report["illegal_edits"].append(row)
            flush()
            if not row["passed"]:
                raise AssertionError(row)

        # Stage 5: the next legal edit after the failures proves the model is
        # not wedged and the revision never moved; then save and reload again.
        recovery_case = {
            "case": case["case"] + "_recovery_edit",
            "start": case["start"],
            "end": case["end"],
            "from_dir": case["to_dir"],
            "to_dir": case["from_dir"],
        }
        recovered, recovery_error = await try_call(
            "creo_update_sketch_geometry",
            {
                "model_id": model_id,
                "expected_revision": current_revision,
                "sketch": "seg",
                "entities": arc_chord_entities(case["start"], case["end"], case["from_dir"]),
                "dimensioning": "coordinates",
            },
        )
        if recovery_error is not None:
            recovery_row = {
                "case": recovery_case["case"],
                "stage": "direction_edit",
                "passed": False,
                "failures": ["next_legal_edit_failed"],
                "error_text": recovery_error,
            }
        else:
            terminal = await settle((recovered.structured_content or {}).get("job_id"))
            recovery_row = judge_direction_edit(
                recovery_case, latest, terminal, await inspect_payload(model_id)
            )
            saved = await submit_job(
                "creo_save_model",
                {"model_id": model_id, "expected_revision": terminal.get("revision")},
            )
            save_row = judge_save_reload(
                recovery_case["case"],
                saved,
                recovery_row["expected_volume_mm3"],
                await inspect_payload(model_id),
            )
            recovery_row["save_reload"] = save_row
            recovery_row["failures"] = [
                *recovery_row["failures"],
                *(f"save_reload:{name}" for name in save_row["failures"]),
            ]
            recovery_row["passed"] = not recovery_row["failures"]
        report["recovery_edit"] = recovery_row
        flush()
        if not recovery_row["passed"]:
            raise AssertionError(recovery_row)

    report["finished_at"] = time.time()
    flush()
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name("report.sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")


def coverage_inventory() -> dict:
    """Which live case covers which required acceptance aspect.

    The offline report states this mapping so the coverage claim is
    auditable without running the live matrix: every aspect the T02
    remainder asks for must name at least one real case.
    """
    return {
        "direction_in_place_edit": [case["case"] for case in EDIT_CASES],
        "cross_zero": [case["case"] for case in EDIT_CASES if case["start"] > case["end"]],
        "tilted_frame": [
            case["case"] for case in [*FRAME_CASES, *EDIT_CASES] if case.get("plane", "XY") != "XY"
        ],
        "downstream_regeneration": [case["case"] for case in EDIT_CASES],
        "illegal_edit": [case["case"] for case in ILLEGAL_EDIT_CASES],
        "save_reload": [case["case"] for case in [*CASES, *FRAME_CASES, *EDIT_CASES]],
        "create_geometry": [case["case"] for case in [*CASES, *FRAME_CASES]],
    }


def offline_report(output: Path) -> dict:
    """The offline report: oracle tables and the live coverage inventory.

    Written to the requested unique path so the offline stage leaves an
    auditable artifact; an existing file is never overwritten.
    """
    rows = []
    for case in [*CASES, *FRAME_CASES]:
        direction = 1 if case["dir"] is None else case["dir"]
        rows.append(
            {
                "case": case["case"],
                "plane": case.get("plane", "XY"),
                "sweep_deg": oracle_sweep_deg(case["start"], case["end"], direction),
                "expected_volume_mm3": oracle_volume_mm3(case["start"], case["end"], direction),
            }
        )
    edits = []
    for case in EDIT_CASES:
        edits.append(
            {
                "case": case["case"],
                "plane": case.get("plane", "XY"),
                "from_dir": case["from_dir"],
                "to_dir": case["to_dir"],
                "volume_from_mm3": oracle_volume_mm3(case["start"], case["end"], case["from_dir"]),
                "volume_to_mm3": oracle_volume_mm3(case["start"], case["end"], case["to_dir"]),
            }
        )
    from tools.test_arc_direction import local_provenance

    report = {
        "task": "DEV-051 T02",
        "scope": ("FEAT-034 explicit arc dir: creation, direction edit, illegal edit, save/reload"),
        "mode": "offline",
        "native_acceptance": "not_run",
        "run_id": output.parent.name,
        "oracle": rows,
        "edit_oracle": edits,
        "illegal_edits": [case["case"] for case in ILLEGAL_EDIT_CASES],
        "coverage": coverage_inventory(),
        "strict_judgement": (
            "a live case passes only with the job succeeded, the measured volume on the "
            "independent oracle, a native arc_geometry echo reporting the declared dir and "
            "sweep, and result.saved_file_reloaded_and_verified is exactly true"
        ),
        "provenance": local_provenance(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name("report.sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return report


def offline(output: Path) -> int:
    report = offline_report(output)
    print(
        json.dumps(
            {
                "mode": "offline",
                "report": str(output),
                "oracle": report["oracle"],
                "edit_oracle": report["edit_oracle"],
                "illegal_edits": report["illegal_edits"],
                "coverage": report["coverage"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("LIVE NOT RUN: no MCP client, no Toolkit call, no Creo connection.")
    return 0


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
        return offline(output)
    asyncio.run(live(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
