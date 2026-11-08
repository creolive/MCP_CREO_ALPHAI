"""BUG-108 live fixture: does a thin oblique profile still translate as a whole?

Runs against an already open Creo session through the stdio server. Nine
candidates are built, each in its own part: the long thin ``TRIANGLE`` profile
with an x offset of 0, 40 or -260 mm, three separate models per offset. The
offsets are the published trigger shape (a profile that a coordinate solve may
translate instead of reshaping), and every candidate keeps the default 1e-5 mm
gate: an explicit ``geometry_tolerance_mm`` cannot stand in for the default one,
so the request is omitted.

A candidate is a witness for the rigid-translation branch only when all of these
are recorded:

* the sketch job succeeded with ``tolerance_source=default_coordinates`` and
  ``accepted_by_request`` false;
* the shift is measured in both stages, the translation is greater than
  1e-5 mm and no more than 1e-2 mm, and the shape residual after removing the
  translation is at most 1e-5 mm;
* the native top-level block and the final receipt both say
  ``accepted_rigid=true``;
* the driver recomputes the translation and residual from the solved point
  correspondences instead of trusting the flags;
* the extruded volume matches the analytic prism, the saved file reloads, and a
  later legal edit still works.

Anything else - no measurable shift, a deformed profile, an explicit tolerance,
a missing stage - is recorded as a control or as unverified. It is never counted
as the target branch.

Usage (after a human confirms the session is operable):
    .venv\\Scripts\\python.exe tools\\test_sketch_shift_batch.py --confirmed-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mcp_readiness import wait_for_startup  # noqa: E402
from version import VERSION  # noqa: E402

REPORT = ROOT / "build/sketch_shift_batch.json"
TRIANGLE = [[0.0, 0.0], [260.0, 0.0], [130.0, 20.9]]
DEPTH_MM = 5.0
COORDINATE_GATE_MM = 1e-5
RIGID_LIMIT_MM = 1e-2
OFFSETS = (0.0, 40.0, -260.0)
MODELS_PER_OFFSET = 3


def _environment() -> dict:
    from creo_mechdog.source_provenance import local_provenance

    worker = ROOT / "build/creo_worker.exe"
    fingerprint = ROOT / "build/source.sha256"
    identity = local_provenance(ROOT)
    return {
        "version": VERSION,
        "commit": identity["commit"],
        "branch": identity["branch"],
        "dirty": identity["dirty"],
        "git_status": identity["git_status"],
        "source_fingerprint": (
            fingerprint.read_text(encoding="utf-8").strip() if fingerprint.is_file() else None
        ),
        "worker_bytes": worker.stat().st_size if worker.is_file() else None,
        "worker_sha256": (
            hashlib.sha256(worker.read_bytes()).hexdigest() if worker.is_file() else None
        ),
    }


def expected_volume_mm3(points: list[list[float]], depth: float = DEPTH_MM) -> float:
    """Analytic prism volume of a closed polygon extruded in +z."""
    area = 0.0
    for index, (x0, y0) in enumerate(points):
        x1, y1 = points[(index + 1) % len(points)]
        area += x0 * y1 - x1 * y0
    return abs(area) / 2.0 * depth


def rigid_fit(source: list[list[float]], solved: list[list[float]]) -> dict | None:
    """Independent translation and residual from point correspondences.

    The mean displacement is the translation candidate; the residual is the
    largest remaining per-point distance. Reproducing the native numbers here is
    the point: a flag that nobody recomputed is not evidence.
    """
    if len(source) != len(solved) or len(source) < 3:
        return None
    deltas = [
        (float(sx) - float(px), float(sy) - float(py))
        for (px, py), (sx, sy) in zip(source, solved)
        if isinstance(sx, (int, float))
    ]
    if len(deltas) != len(source):
        return None
    count = len(deltas)
    u = sum(dx for dx, _ in deltas) / count
    v = sum(dy for _, dy in deltas) / count
    residual = max(math.hypot(dx - u, dy - v) for dx, dy in deltas)
    return {
        "translation_mm": {"u": u, "v": v},
        "magnitude_mm": math.hypot(u, v),
        "residual_mm": residual,
        "point_count": count,
    }


def shift_candidates() -> list[dict]:
    """Nine independent candidates: three offsets, three models each."""
    candidates = []
    for offset in OFFSETS:
        for repeat in range(MODELS_PER_OFFSET):
            index = len(candidates) + 1
            points = [[x + offset, y] for x, y in TRIANGLE]
            candidates.append(
                {
                    "case_id": f"S{index:02d}",
                    "model_name": f"r13s{index:02d}",
                    "offset_mm": offset,
                    "repeat": repeat,
                    "points": points,
                    "depth": DEPTH_MM,
                    "geometry_tolerance_mm": None,
                    "expected_volume_mm3": expected_volume_mm3(points),
                }
            )
    return candidates


def _check(name: str, actual, expected, result: str) -> dict:
    return {"check": name, "actual": actual, "expected": expected, "result": result}


def _verdict(checks: list[dict], reason: str, **extra) -> dict:
    results = {item["result"] for item in checks}
    if not checks:
        verdict = "unverified"
    elif "fail" in results:
        verdict = "fail"
    elif "unverified" in results:
        verdict = "unverified"
    else:
        verdict = "pass"
    return {"verdict": verdict, "reason": reason, "checks": checks, **extra}


def _magnitude(translation) -> float | None:
    if not isinstance(translation, dict):
        return None
    u, v = translation.get("u"), translation.get("v")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in (u, v)):
        return None
    return math.hypot(float(u), float(v))


def judge_shift_case(case: dict) -> dict:
    """Judge one recorded BUG-108 candidate from its evidence only."""
    checks: list[dict] = []
    stages = case.get("stages") if isinstance(case.get("stages"), dict) else {}
    sketch = stages.get("sketch") if isinstance(stages.get("sketch"), dict) else {}
    solid = stages.get("solid") if isinstance(stages.get("solid"), dict) else {}
    shift = sketch.get("sketch_shifted") if isinstance(sketch.get("sketch_shifted"), dict) else {}
    deviation = sketch.get("geometry_deviation")
    if not isinstance(deviation, dict):
        deviation = {}
    native = (
        case.get("measurement", {}).get("native")
        if isinstance(case.get("measurement"), dict)
        else None
    )
    native = native if isinstance(native, dict) else {}
    independent = (
        case.get("measurement", {}).get("independent")
        if isinstance(case.get("measurement"), dict)
        else None
    )

    checks.append(
        _check(
            "sketch_succeeded",
            sketch.get("status"),
            "succeeded",
            "pass" if sketch.get("status") == "succeeded" else "unverified",
        )
    )
    detected = shift.get("detected")
    if detected is not True:
        checks.append(
            _check(
                "shift_detected",
                detected,
                True,
                "unverified" if detected is False else "unverified",
            )
        )
        return _verdict(checks, "control: no measurable shift, the target branch was not exercised")
    rigid = shift.get("rigid")
    checks.append(
        _check(
            "rigid_profile",
            rigid,
            True,
            "pass" if rigid is True else "unverified",
        )
    )
    source = shift.get("tolerance_source")
    by_request = shift.get("accepted_by_request")
    checks.append(
        _check(
            "default_coordinate_gate",
            {"tolerance_source": source, "accepted_by_request": by_request},
            {"tolerance_source": "default_coordinates", "accepted_by_request": False},
            "pass" if source == "default_coordinates" and by_request is False else "unverified",
        )
    )

    translation = shift.get("translation_mm") or native.get("translation_mm")
    magnitude = _magnitude(translation)
    if magnitude is None:
        checks.append(_check("translation_measured", None, "u/v translation", "unverified"))
    else:
        checks.append(
            _check(
                "translation_above_noise",
                magnitude,
                f"> {COORDINATE_GATE_MM}",
                "pass" if magnitude > COORDINATE_GATE_MM else "unverified",
            )
        )
        over = magnitude > RIGID_LIMIT_MM
        accepted = shift.get("accepted_rigid") is True
        checks.append(
            _check(
                "translation_within_limit",
                magnitude,
                f"<= {RIGID_LIMIT_MM}",
                "fail" if over and accepted else ("unverified" if over else "pass"),
            )
        )

    residual = shift.get("shape_deviation_mm", shift.get("residual_mm"))
    if isinstance(residual, (int, float)) and not isinstance(residual, bool):
        checks.append(
            _check(
                "shape_residual",
                residual,
                f"<= {COORDINATE_GATE_MM}",
                "pass" if residual <= COORDINATE_GATE_MM else "fail",
            )
        )
    else:
        checks.append(_check("shape_residual", None, f"<= {COORDINATE_GATE_MM}", "unverified"))

    accepted_rigid = shift.get("accepted_rigid")
    final_accepted = deviation.get("accepted_rigid")
    checks.append(
        _check(
            "native_accepted_rigid",
            accepted_rigid,
            True,
            "pass" if accepted_rigid is True else "unverified",
        )
    )
    checks.append(
        _check(
            "final_receipt_accepted_rigid",
            final_accepted,
            True,
            "pass" if final_accepted is True else "unverified",
        )
    )
    if isinstance(deviation.get("translation_mm"), dict) and translation:
        dev_magnitude = _magnitude(deviation.get("translation_mm"))
        if dev_magnitude is not None and magnitude is not None:
            checks.append(
                _check(
                    "stage_agreement",
                    round(abs(dev_magnitude - magnitude), 9),
                    "<= 1e-4",
                    "pass" if abs(dev_magnitude - magnitude) <= 1e-4 else "fail",
                )
            )

    if not isinstance(independent, dict):
        checks.append(_check("independent_fit", None, "recomputed translation", "unverified"))
    else:
        fit_magnitude = independent.get("magnitude_mm")
        fit_residual = independent.get("residual_mm")
        checks.append(
            _check(
                "independent_fit_measured",
                {"magnitude_mm": fit_magnitude, "residual_mm": fit_residual},
                "numeric translation and residual",
                "pass" if isinstance(fit_magnitude, (int, float)) else "unverified",
            )
        )
        if isinstance(fit_residual, (int, float)) and not isinstance(fit_residual, bool):
            checks.append(
                _check(
                    "independent_residual",
                    fit_residual,
                    f"<= {COORDINATE_GATE_MM}",
                    "pass" if fit_residual <= COORDINATE_GATE_MM else "fail",
                )
            )
        if isinstance(fit_magnitude, (int, float)) and magnitude is not None:
            checks.append(
                _check(
                    "independent_agrees_with_native",
                    round(abs(fit_magnitude - magnitude), 9),
                    "<= 1e-4",
                    "pass" if abs(fit_magnitude - magnitude) <= 1e-4 else "fail",
                )
            )

    checks.append(
        _check(
            "solid_succeeded",
            solid.get("status"),
            "succeeded",
            "pass" if solid.get("status") == "succeeded" else "unverified",
        )
    )
    volume = (case.get("measurement") or {}).get("volume_mm3")
    expected = (case.get("request") or {}).get("expected_volume_mm3")
    if isinstance(volume, (int, float)) and isinstance(expected, (int, float)):
        tolerance = max(1e-6, abs(expected) * 1e-8)
        checks.append(
            _check(
                "volume_oracle",
                {"actual": volume, "expected": expected, "tolerance": tolerance},
                "within tolerance",
                "pass" if abs(volume - expected) <= tolerance else "fail",
            )
        )
    else:
        checks.append(_check("volume_oracle", None, "measured and analytic volume", "unverified"))

    reloaded = case.get("saved_file_reloaded_and_verified")
    checks.append(
        _check(
            "saved_file_reloaded",
            reloaded,
            True,
            "pass" if reloaded is True else ("fail" if reloaded is False else "unverified"),
        )
    )
    followup = case.get("followup")
    checks.append(
        _check(
            "later_legal_edit",
            (followup or {}).get("status") if isinstance(followup, dict) else None,
            "succeeded",
            "pass"
            if isinstance(followup, dict) and followup.get("status") == "succeeded"
            else "unverified",
        )
    )
    return _verdict(checks, "rigid translation witnessed and recomputed")


async def call(client: Client, name: str, args: dict) -> dict:
    response = await client.call_tool(name, args)
    if response.is_error:
        raise RuntimeError(f"{name}: {response.content}")
    return response.structured_content


async def poll(client: Client, job_id: str, budget: int = 330) -> dict:
    result: dict = {}
    for _ in range(budget):
        result = await call(client, "creo_get_job", {"job_id": job_id})
        if result["status"] not in ("queued", "running"):
            break
        await asyncio.sleep(1)
    return result


async def run_job(client: Client, name: str, args: dict, record: dict) -> dict:
    created = await call(client, name, args)
    job_id = created["job_id"]
    print(f"{name} job={job_id} model={created.get('model_id')}", flush=True)
    result = await poll(client, job_id)
    record["calls"].append(
        {
            "tool": name,
            "label": args.get("label") or args.get("sketch"),
            "job_id": job_id,
            "status": result["status"],
            "stage": result.get("stage"),
            "message": str(result.get("message"))[:300],
            "sketch_shifted": _shifted(result),
            "geometry_deviation": _deviation(result),
        }
    )
    print(f"  status={result['status']} message={str(result.get('message'))[:160]}", flush=True)
    return result


def _operations(result: dict) -> list[dict]:
    body = result.get("result")
    if not isinstance(body, dict):
        return []
    operations = body.get("operations")
    return (
        [item for item in operations if isinstance(item, dict)]
        if isinstance(operations, list)
        else []
    )


def _shifted(result: dict):
    for operation in _operations(result):
        if "sketch_shifted" in operation:
            return operation["sketch_shifted"]
        nested = (
            (operation.get("result") or {}) if isinstance(operation.get("result"), dict) else {}
        )
        if "sketch_shifted" in nested:
            return nested["sketch_shifted"]
    body = result.get("result")
    if isinstance(body, dict) and isinstance(body.get("sketch_shifted"), dict):
        return body["sketch_shifted"]
    return None


def _deviation(result: dict):
    for operation in _operations(result):
        if "geometry_deviation" in operation:
            deviation = operation["geometry_deviation"]
            if isinstance(deviation, dict):
                return {
                    key: deviation.get(key)
                    for key in (
                        "available",
                        "max_deviation_mm",
                        "shape_deviation_mm",
                        "residual_mm",
                        "rigid",
                        "translation_mm",
                        "accepted_rigid",
                        "tolerance_source",
                        "exceeds_warning",
                        "shift_detected",
                        "accepted_by_request",
                    )
                }
    return None


def _sketch(model_id: str, revision: int, label: str, points, tolerance: float | None) -> dict:
    payload = {
        "model_id": model_id,
        "expected_revision": revision,
        "label": label,
        "entities": [
            {
                "type": "polyline",
                "name": f"{label}_outline",
                "points": points,
                "closed": True,
            }
        ],
        "dimensioning": "coordinates",
    }
    if tolerance is not None:
        payload["geometry_tolerance_mm"] = tolerance
    return payload


async def solved_points(client: Client, model_id: str, label: str):
    """Solved sketch points of one feature, or None when unavailable.

    The independent recomputation needs the post-solve coordinates; when the
    saved snapshot does not expose them the candidate stays unverified instead
    of borrowing the native numbers.
    """
    try:
        payload = await call(
            client,
            "creo_inspect_model",
            {"model_id": model_id, "detail": "full", "section": "feature_geometry", "limit": 200},
        )
    except Exception:  # noqa: BLE001 - missing geometry is evidence
        return None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    records = data.get("feature_geometry") or []
    for record in records:
        if not isinstance(record, dict) or record.get("label") != label:
            continue
        for item in record.get("geometry_items") or []:
            if isinstance(item, dict) and isinstance(item.get("points"), list):
                points = [
                    [point[0], point[1]]
                    for point in item["points"]
                    if isinstance(point, (list, tuple)) and len(point) >= 2
                ]
                return points or None
    return None


async def run_candidate(client: Client, candidate: dict, record: dict) -> dict:
    part = await call(client, "creo_new_part", {"model_name": candidate["model_name"]})
    model_id = part["model_id"]
    created = await poll(client, part["job_id"])
    record["calls"].append(
        {
            "tool": "creo_new_part",
            "model_name": candidate["model_name"],
            "job_id": part["job_id"],
            "model_id": model_id,
            "status": created["status"],
        }
    )
    case = {
        "case_id": candidate["case_id"],
        "scope": "rigid_translation",
        "model_id": model_id,
        "model_name": candidate["model_name"],
        "request": {
            "points": candidate["points"],
            "offset_mm": candidate["offset_mm"],
            "depth": candidate["depth"],
            "geometry_tolerance_mm": candidate["geometry_tolerance_mm"],
            "expected_volume_mm3": candidate["expected_volume_mm3"],
        },
        "stages": {},
        "measurement": {},
        "verification_level": "live",
        "identity": _environment(),
    }
    if created["status"] != "succeeded":
        case["error"] = f"new_part failed: {created.get('message')}"
        case["judged"] = _verdict([], "new part did not build")
        return case

    revision = created["revision"]
    sketch = await run_job(
        client,
        "creo_create_sketch",
        _sketch(
            model_id, revision, f"{candidate['model_name']}_profile", candidate["points"], None
        ),
        record,
    )
    case["stages"]["sketch"] = {
        "status": sketch["status"],
        "revision": sketch.get("revision"),
        "message": str(sketch.get("message"))[:300],
        "sketch_shifted": _shifted(sketch),
        "geometry_deviation": _deviation(sketch),
    }
    if sketch["status"] != "succeeded":
        case["judged"] = judge_shift_case(case)
        return case
    revision = sketch["revision"]

    native = _shifted(sketch) or {}
    solved = await solved_points(client, model_id, f"{candidate['model_name']}_profile")
    fit = rigid_fit(candidate["points"], solved) if solved else None
    case["measurement"]["native"] = native
    case["measurement"]["independent"] = fit
    case["measurement"]["solved_points"] = solved

    solid = await run_job(
        client,
        "creo_extrude",
        {
            "model_id": model_id,
            "expected_revision": revision,
            "label": f"{candidate['model_name']}_solid",
            "sketch": f"{candidate['model_name']}_profile",
            "depth": candidate["depth"],
        },
        record,
    )
    case["stages"]["solid"] = {
        "status": solid["status"],
        "revision": solid.get("revision"),
        "message": str(solid.get("message"))[:300],
        "geometry_deviation": _deviation(solid),
    }
    if solid["status"] == "succeeded":
        revision = solid["revision"]
        compact = await call(client, "creo_inspect_model", {"model_id": model_id})
        inspection = compact.get("inspection") or {}
        case["measurement"]["volume_mm3"] = inspection.get("volume_mm3")
        body = solid.get("result") if isinstance(solid.get("result"), dict) else {}
        case["saved_file_reloaded_and_verified"] = body.get("saved_file_reloaded_and_verified")

    if native.get("accepted_rigid") is True:
        followup = await run_job(
            client,
            "creo_set_parameters",
            {
                "model_id": model_id,
                "expected_revision": revision,
                "parameters": {"r13_bug108_marker": "1"},
            },
            record,
        )
        case["followup"] = {
            "status": followup["status"],
            "revision": followup.get("revision"),
            "message": str(followup.get("message"))[:300],
        }
    case["judged"] = judge_shift_case(case)
    return case


async def run_control(client: Client, record: dict) -> dict:
    """Explicit-tolerance control: a released-but-moved sketch is not the target.

    It documents that the request tolerance path still reports
    ``accepted_by_request`` and is deliberately excluded from target coverage.
    """
    part = await call(client, "creo_new_part", {"model_name": "r13ctrl"})
    model_id = part["model_id"]
    created = await poll(client, part["job_id"])
    record["calls"].append(
        {
            "tool": "creo_new_part",
            "model_name": "r13ctrl",
            "job_id": part["job_id"],
            "model_id": model_id,
            "status": created["status"],
        }
    )
    if created["status"] != "succeeded":
        return {"case_id": "CTRL", "scope": "control", "error": str(created.get("message"))[:300]}
    sketch = await run_job(
        client,
        "creo_create_sketch",
        _sketch(
            model_id,
            created["revision"],
            "r13ctrl_profile",
            [[0.0, 80.0], [260.0, 80.0], [130.0, 100.9]],
            0.01,
        ),
        record,
    )
    return {
        "case_id": "CTRL",
        "scope": "control",
        "model_id": model_id,
        "status": sketch["status"],
        "sketch_shifted": _shifted(sketch),
        "geometry_deviation": _deviation(sketch),
        "verification_level": "live",
    }


async def scenario(record: dict) -> None:
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT)
    )
    async with Client(parameters) as connected:
        await wait_for_startup(connected, record, REPORT)
        status = await call(connected, "creo_session_status", {})
        record["session"] = {"connected": status.get("connected")}
        assert status["connected"], status
        for candidate in shift_candidates():
            print(f"candidate {candidate['case_id']} offset={candidate['offset_mm']}", flush=True)
            record["cases"].append(await run_candidate(connected, candidate, record))
        record["control"] = await run_control(connected, record)


def summarize(record: dict) -> str:
    verdicts = [case.get("judged", {}).get("verdict", "unverified") for case in record["cases"]]
    if "fail" in verdicts:
        return "fail"
    if not verdicts or "unverified" in verdicts:
        return "unverified"
    return "pass"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BUG-108 sketch shift live fixture")
    parser.add_argument(
        "--confirmed-session-usable",
        action="store_true",
        help="required: a human already confirmed the open Creo session is operable",
    )
    parser.add_argument("--output", default=str(REPORT))
    arguments = parser.parse_args(argv)
    if not arguments.confirmed_session_usable:
        print("live runs require --confirmed-session-usable after human session checks")
        return 2
    output = Path(arguments.output)
    record: dict = {
        "work_item": "BUG-108",
        "verification_level": "live",
        "scope": "rigid_translation",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": _environment(),
        "calls": [],
        "cases": [],
        "success": False,
    }
    started = time.monotonic()
    error = None
    try:
        asyncio.run(scenario(record))
    except Exception as failure:  # noqa: BLE001 - the report is the product here
        error = f"{type(failure).__name__}: {failure}"
    record["elapsed_s"] = round(time.monotonic() - started, 1)
    if error:
        record["error"] = error
    record["verdict"] = summarize(record)
    record["success"] = error is None and record["verdict"] == "pass"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: record[key] for key in ("success", "verdict", "error") if key in record}, indent=2
        )
    )
    print(f"report: {output}")
    if record["verdict"] == "pass" and error is None:
        return 0
    return 1 if record["verdict"] == "fail" else 2


if __name__ == "__main__":
    raise SystemExit(main())
