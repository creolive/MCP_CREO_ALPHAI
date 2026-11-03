"""BUG-111 live fixture: rotation range and repeated keep_original copies.

Runs against an already open Creo session through the stdio server. Every main
case (C0-C6) starts from its own freshly built plate: the previous release ran
1, 5 and 7 ops on the same model, so a failure at the fifth copy could not be
separated from earlier damage or from the selection set growing with the body.

The cases answer separate questions:

* C0 - one -135 degree copy, plus a 225 degree request that must be refused
  before a job exists and must name the equivalent -135;
* C1 - four ops in one plan;
* C2 - five ops in one plan, the published batch size that failed at index 4;
* C3 - seven ops in one plan (the P12 blade count);
* C4 - the same five angles with -135 first, to see whether the failure follows
  the angle or the position;
* C5 - C2 again, but with an explicit body id taken from an inspection;
* C6 - C3 split into 4+3 with a fresh inspection between the batches.

Two phases are recorded, never mixed:

* ``reproduce`` (default) documents what happened, including the known failure
  at index 4; a correctly recorded failure is a pass for this phase;
* ``verify`` only passes when every operation committed, the revision is
  persisted, the saved file reloads and the body count matches the copy count.
  A reproduced failure can never pass ``verify``.

The driver records the target body, the selected face count and up to twenty
ids, active body count, feature ids/parents, raw status codes,
``failed_features``, volume and bbox. Nothing is asserted about Creo's internals
and no model outside this run is touched.

Usage (after a human confirms the session is operable):
    .venv\\Scripts\\python.exe tools\\test_geometry_transform_copies.py --confirmed-session-usable
    .venv\\Scripts\\python.exe tools\\test_geometry_transform_copies.py --phase verify --confirmed-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "build" / "geometry_transform_copies_report.json"

PLATE = [[0.0, 0.0], [120.0, 0.0], [120.0, 40.0], [0.0, 40.0]]
FOUR = (45.0, 90.0, 135.0, 180.0)
FIVE = (45.0, 90.0, 135.0, 180.0, -135.0)
SEVEN = (45.0, 90.0, 135.0, 180.0, -135.0, -90.0, -45.0)
PHASES = ("reproduce", "verify")
LABEL = re.compile(r"^[a-z][a-z0-9_]{0,27}$")
SAMPLE = 20


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _identity() -> dict:
    worker = ROOT / "build/creo_worker.exe"
    fingerprint = ROOT / "build/source.sha256"
    return {
        "version": _version(),
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(_git("status", "--porcelain")),
        "source_fingerprint": (
            fingerprint.read_text(encoding="utf-8").strip() if fingerprint.is_file() else None
        ),
        "worker_sha256": (
            hashlib.sha256(worker.read_bytes()).hexdigest() if worker.is_file() else None
        ),
        "worker_bytes": worker.stat().st_size if worker.is_file() else None,
    }


def _version() -> str | None:
    for line in (ROOT / "version.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("VERSION"):
            return line.split("=", 1)[1].strip().strip("\"'")
    return None


def _environment() -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "root": str(ROOT),
    }


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


def judge_copy_case(case: dict, *, phase: str = "reproduce") -> dict:
    """Judge one recorded copy case without touching Creo or any process.

    Only recorded evidence is read, so the same function runs in unit tests with
    synthetic dictionaries and on a live report without a second interpretation.
    ``reproduce`` documents the outcome; ``verify`` may only pass a fully
    committed batch.
    """
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {PHASES}")

    refusal = case.get("refusal")
    if refusal is not None:
        checks = []
        message = str(refusal.get("message") or "")
        checks.append(
            _check(
                "refusal_names_equivalent_angle",
                message[:200],
                "mentions -135",
                "pass" if "-135" in message else "fail",
            )
        )
        checks.append(
            _check(
                "refusal_created_no_job",
                refusal.get("job_id"),
                None,
                "pass" if refusal.get("job_id") in (None, "") else "fail",
            )
        )
        before = refusal.get("revision_before")
        after = refusal.get("revision_after")
        if isinstance(before, int) and isinstance(after, int):
            checks.append(
                _check(
                    "refusal_kept_revision",
                    after,
                    before,
                    "pass" if after == before else "fail",
                )
            )
        else:
            checks.append(_check("refusal_kept_revision", None, "two revisions", "unverified"))
        return _verdict(checks, "out-of-range request refused before submission", phase=phase)

    checks: list[dict] = []
    receipt = case.get("receipt") if isinstance(case.get("receipt"), dict) else {}
    body = receipt.get("result") if isinstance(receipt.get("result"), dict) else {}
    status = receipt.get("status")
    before = (case.get("snapshots") or {}).get("before")
    after = (case.get("snapshots") or {}).get("after")

    checks.append(
        _check(
            "terminal_receipt",
            status,
            "succeeded or failed",
            "pass" if status in ("succeeded", "failed") else "unverified",
        )
    )
    for name, snapshot in (("before_snapshot", before), ("after_snapshot", after)):
        complete = (
            isinstance(snapshot, dict)
            and isinstance(snapshot.get("revision"), int)
            and isinstance(snapshot.get("volume_mm3"), (int, float))
            and isinstance((snapshot.get("counts") or {}).get("bodies"), int)
        )
        checks.append(
            _check(
                name,
                bool(complete),
                "revision, volume_mm3 and body count",
                "pass" if complete else "unverified",
            )
        )

    if status == "failed":
        rollback = body.get("rollback_status")
        unchanged = body.get("model_unchanged")
        checks.append(
            _check(
                "rollback_evidence",
                {"rollback_status": rollback, "model_unchanged": unchanged},
                "rollback_status or model_unchanged",
                "pass" if rollback or unchanged is True else "unverified",
            )
        )
        index = body.get("failed_operation_index")
        checks.append(
            _check(
                "failure_position_recorded",
                index,
                "zero-based operation index",
                "pass" if isinstance(index, int) else "unverified",
            )
        )
        expected_index = (case.get("expectation") or {}).get("known_failure_index")
        if isinstance(expected_index, int) and isinstance(index, int):
            checks.append(
                _check(
                    "known_failure_position",
                    index,
                    expected_index,
                    "pass" if index == expected_index else "fail",
                )
            )
        if phase == "verify":
            checks.append(_check("verify_requires_committed_batch", "failed", "succeeded", "fail"))
        return _verdict(
            checks, "batch failed; reproduce records it, verify cannot pass", phase=phase
        )

    if status == "succeeded":
        receipt_revision = receipt.get("revision")
        after_revision = after.get("revision") if isinstance(after, dict) else None
        if isinstance(receipt_revision, int) and isinstance(after_revision, int):
            checks.append(
                _check(
                    "revision_persisted",
                    after_revision,
                    receipt_revision,
                    "pass" if receipt_revision == after_revision else "fail",
                )
            )
        else:
            checks.append(
                _check("revision_persisted", None, "receipt and after revision", "unverified")
            )

        successful = len(case.get("committed_operations") or [])
        expected_bodies = None
        if isinstance(before, dict) and isinstance(after, dict):
            start = (before.get("counts") or {}).get("bodies")
            end = (after.get("counts") or {}).get("bodies")
            if isinstance(start, int) and isinstance(end, int) and successful:
                expected_bodies = start + successful
                checks.append(
                    _check(
                        "bodies_added_per_copy",
                        end,
                        expected_bodies,
                        "pass" if end == expected_bodies else "fail",
                    )
                )
        if expected_bodies is None:
            checks.append(
                _check("bodies_added_per_copy", None, "body counts and committed ops", "unverified")
            )

        reloaded = body.get("saved_file_reloaded_and_verified")
        checks.append(
            _check(
                "saved_file_reloaded",
                reloaded,
                True,
                "pass" if reloaded is True else ("fail" if reloaded is False else "unverified"),
            )
        )
        if phase == "verify":
            volume_before = before.get("volume_mm3") if isinstance(before, dict) else None
            volume_after = after.get("volume_mm3") if isinstance(after, dict) else None
            checks.append(
                _check(
                    "volume_grew",
                    {"before": volume_before, "after": volume_after},
                    "after > before",
                    (
                        "pass"
                        if isinstance(volume_before, (int, float))
                        and isinstance(volume_after, (int, float))
                        and volume_after > volume_before
                        else "unverified"
                    ),
                )
            )
            return _verdict(checks, "batch committed with recorded geometry", phase=phase)
        return _verdict(checks, "batch committed; reproduce only", phase=phase)

    return _verdict(checks, "terminal status not recorded", phase=phase)


def _op(label: str, angle: float, body_id: int | None = None) -> dict:
    """One transform op; geometry_transform is only reachable inside a plan.

    ``keep_original`` copies the currently selected body. A body id is optional
    because the published path resolved the body implicitly; C5 supplies one.
    """
    references = [{"kind": "body"}] if body_id is None else [{"kind": "body", "id": body_id}]
    return {
        "op": "geometry_transform",
        "label": label,
        "references": references,
        "translation": [0, 0, 0],
        "rotation": [0, 0, angle],
        "keep_original": True,
    }


def scenario_specs() -> list[dict]:
    """The seven main cases, each with its own base model name.

    Kept as data so the offline regression can prove the cases are independent,
    the angles stay in range and the labels are accepted.
    """
    five = [_op(f"r13_c2_{index}", angle) for index, angle in enumerate(FIVE)]
    seven = [_op(f"r13_c3_{index}", angle) for index, angle in enumerate(SEVEN)]
    return [
        {
            "case_id": "C0",
            "model_name": "r13c0",
            "ops": [_op("r13_c0_neg135", -135.0)],
            "refusal_angle": 225.0,
            "expectation": {"known_failure_index": None},
        },
        {
            "case_id": "C1",
            "model_name": "r13c1",
            "ops": [_op(f"r13_c1_{index}", angle) for index, angle in enumerate(FOUR)],
            "expectation": {"known_failure_index": None},
        },
        {
            "case_id": "C2",
            "model_name": "r13c2",
            "ops": five,
            "expectation": {"known_failure_index": 4},
            "followup": True,
        },
        {
            "case_id": "C3",
            "model_name": "r13c3",
            "ops": seven,
            "expectation": {"known_failure_index": 4},
            "followup": True,
        },
        {
            "case_id": "C4",
            "model_name": "r13c4",
            "ops": [
                _op(f"r13_c4_{index}", angle)
                for index, angle in enumerate((-135.0, 45.0, 90.0, 135.0, 180.0))
            ],
            "expectation": {"known_failure_index": None},
        },
        {
            "case_id": "C5",
            "model_name": "r13c5",
            "ops": [_op(f"r13_c5_{index}", angle) for index, angle in enumerate(FIVE)],
            "explicit_body": True,
            "expectation": {"known_failure_index": 4},
        },
        {
            "case_id": "C6",
            "model_name": "r13c6",
            "batches": [
                [_op(f"r13_c6_a{index}", angle) for index, angle in enumerate(FIVE[:4])],
                [
                    _op(f"r13_c6_b{index}", angle)
                    for index, angle in enumerate((FIVE[4], -90.0, -45.0))
                ],
            ],
            "expectation": {"known_failure_index": None},
        },
    ]


async def call(client, name: str, arguments: dict) -> dict:
    response = await client.call_tool(name, arguments)
    if response.is_error:
        raise RuntimeError(f"{name}: {response.content}")
    return response.structured_content


async def rejected(client, name: str, arguments: dict) -> dict:
    """Return the refusal text plus proof that no job was created."""
    response = await client.call_tool(name, arguments)
    text = " ".join(block.text for block in response.content if hasattr(block, "text"))
    return {
        "message": text[:400],
        "is_error": bool(response.is_error),
        "job_id": None if response.is_error else (response.structured_content or {}).get("job_id"),
    }


async def poll(client, job_id: str, budget: int = 330) -> dict:
    result: dict = {}
    for _ in range(budget):
        result = await call(client, "creo_get_job", {"job_id": job_id})
        if result["status"] not in ("queued", "running"):
            break
        await asyncio.sleep(1)
    return result


def _calls(result: dict) -> list[dict]:
    body = result.get("result")
    if not isinstance(body, dict):
        return []
    operations = body.get("operations")
    return (
        [item for item in operations if isinstance(item, dict)]
        if isinstance(operations, list)
        else []
    )


def _failure(result: dict):
    body = result.get("result")
    if not isinstance(body, dict):
        return None
    found = {
        key: body.get(key)
        for key in (
            "failed_operation_index",
            "failed_stage",
            "failed_toolkit_call",
            "failed_transform",
            "rollback_status",
            "model_unchanged",
            "failed_features",
        )
        if key in body
    }
    return found or None


async def run_job(client, name: str, arguments: dict, record: dict) -> dict:
    created = await call(client, name, arguments)
    job_id = created["job_id"]
    print(f"{name} job={job_id} model={created.get('model_id')}", flush=True)
    result = await poll(client, job_id)
    entry = {
        "tool": name,
        "label": arguments.get("label"),
        "job_id": job_id,
        "status": result["status"],
        "stage": result.get("stage"),
        "message": str(result.get("message"))[:300],
        "rotation_deg": arguments.get("rotation"),
        "keep_original": arguments.get("keep_original"),
        "operations": [
            {
                key: operation.get(key)
                for key in ("index", "execution_status", "effect_status")
                if key in operation
            }
            for operation in _calls(result)
        ],
        "failure": _failure(result),
        "revision": result.get("revision"),
    }
    record["calls"].append(entry)
    print(f"  status={result['status']} message={str(result.get('message'))[:160]}", flush=True)
    return result


async def section(client, model_id: str, name: str, limit: int = 200):
    """One full-detail section, or None when the snapshot cannot provide it."""
    try:
        payload = await call(
            client,
            "creo_inspect_model",
            {"model_id": model_id, "detail": "full", "section": name, "limit": limit},
        )
    except Exception:  # noqa: BLE001 - a missing section is evidence, not a crash
        return None
    data = payload.get("data")
    records = data.get(name) if isinstance(data, dict) else None
    return records if isinstance(records, list) else None


async def snapshot(client, model_id: str, record: dict) -> dict:
    compact = await call(client, "creo_inspect_model", {"model_id": model_id})
    inspection = compact.get("inspection") or {}
    bodies = await section(client, model_id, "bodies")
    surfaces = await section(client, model_id, "surfaces")
    surface_ids = (
        [item.get("id") for item in (surfaces or []) if isinstance(item, dict)]
        if surfaces is not None
        else None
    )
    record.setdefault("sections", []).append(
        {
            "model_id": model_id,
            "revision": compact.get("revision"),
            "bodies_available": bodies is not None,
            "surfaces_available": surfaces is not None,
        }
    )
    return {
        "revision": compact.get("revision"),
        "status": compact.get("status"),
        "volume_mm3": inspection.get("volume_mm3"),
        "counts": inspection.get("counts"),
        "bodies": [
            {"id": item.get("id"), "bbox": item.get("bbox")}
            for item in (bodies or [])[:SAMPLE]
            if isinstance(item, dict)
        ],
        "bodies_total": len(bodies) if bodies is not None else None,
        "surface_ids_sample": (surface_ids or [])[:SAMPLE],
        "surfaces_total": len(surface_ids) if surface_ids is not None else None,
        "sample_truncated": (len(surface_ids) > SAMPLE) if surface_ids is not None else None,
    }


async def build_base(client, spec: dict, record: dict) -> dict:
    """Fresh plate for one case: new part, sketch, extrude."""
    part = await call(client, "creo_new_part", {"model_name": spec["model_name"]})
    model_id = part["model_id"]
    record["calls"].append(
        {
            "tool": "creo_new_part",
            "model_name": spec["model_name"],
            "job_id": part["job_id"],
            "model_id": model_id,
        }
    )
    created = await poll(client, part["job_id"])
    record["calls"][-1].update(
        {
            "status": created["status"],
            "stage": created.get("stage"),
            "message": str(created.get("message"))[:300],
        }
    )
    if created["status"] != "succeeded":
        raise RuntimeError(f"new_part failed for {spec['case_id']}: {created.get('message')}")
    revision = created["revision"]
    sketch = await run_job(
        client,
        "creo_create_sketch",
        {
            "model_id": model_id,
            "expected_revision": revision,
            "label": "r13_plate_profile",
            "entities": [
                {"type": "polyline", "name": "r13_plate_outline", "points": PLATE, "closed": True}
            ],
            "dimensioning": "coordinates",
        },
        record,
    )
    if sketch["status"] != "succeeded":
        raise RuntimeError(f"plate sketch failed for {spec['case_id']}: {sketch.get('message')}")
    revision = sketch["revision"]
    solid = await run_job(
        client,
        "creo_extrude",
        {
            "model_id": model_id,
            "expected_revision": revision,
            "label": "r13_plate",
            "sketch": "r13_plate_profile",
            "depth": 6,
        },
        record,
    )
    if solid["status"] != "succeeded":
        raise RuntimeError(f"plate extrude failed for {spec['case_id']}: {solid.get('message')}")
    return {"model_id": model_id, "revision": solid["revision"]}


async def run_case(client, spec: dict, record: dict, phase: str) -> dict:
    base = await build_base(client, spec, record)
    model_id, revision = base["model_id"], base["revision"]
    before = await snapshot(client, model_id, record)
    case = {
        "case_id": spec["case_id"],
        "scope": "copy_batch",
        "model_id": model_id,
        "base_model_name": spec["model_name"],
        "expectation": spec.get("expectation"),
        "request": {"operations": [], "refusal_angle": spec.get("refusal_angle")},
        "snapshots": {"before": before},
        "committed_operations": [],
        "identity": _identity(),
    }
    body_id = None
    if spec.get("explicit_body"):
        bodies = await section(client, model_id, "bodies")
        ids = [item.get("id") for item in (bodies or []) if isinstance(item, dict)]
        body_id = ids[0] if ids else None
        case["explicit_body_id"] = body_id

    batches = spec.get("batches") or [spec["ops"]]
    receipt: dict = {}
    for batch_index, ops in enumerate(batches):
        if body_id is not None:
            ops = [{**op, "references": [{"kind": "body", "id": body_id}]} for op in ops]
        plan = {"model_id": model_id, "expected_revision": revision, "operations": ops}
        case["request"]["operations"].append(ops)
        receipt = await run_job(client, "creo_execute_plan", plan, record)
        case["job_id"] = record["calls"][-1]["job_id"]
        case["receipt"] = {
            "status": receipt["status"],
            "stage": receipt.get("stage"),
            "message": str(receipt.get("message"))[:300],
            "revision": receipt.get("revision"),
            "result": receipt.get("result"),
        }
        if receipt["status"] == "succeeded":
            revision = receipt["revision"]
            case["committed_operations"].extend(
                item.get("index")
                for item in _calls(receipt)
                if item.get("execution_status") == "succeeded"
            )
        else:
            break
        if batch_index + 1 < len(batches):
            refreshed = await snapshot(client, model_id, record)
            case.setdefault("between_batches", []).append(refreshed)
            revision = refreshed.get("revision") or revision

    if spec.get("refusal_angle") is not None:
        baseline = await snapshot(client, model_id, record)
        refusal = await rejected(
            client,
            "creo_execute_plan",
            {
                "model_id": model_id,
                "expected_revision": revision,
                "operations": [_op("r13_c0_225", spec["refusal_angle"])],
            },
        )
        after_refusal = await snapshot(client, model_id, record)
        case["refusal"] = {
            **refusal,
            "revision_before": baseline.get("revision"),
            "revision_after": after_refusal.get("revision"),
        }

    after = await snapshot(client, model_id, record)
    case["snapshots"]["after"] = after
    if spec.get("followup") and receipt.get("status") == "failed":
        followup = await run_job(
            client,
            "creo_create_sketch",
            {
                "model_id": model_id,
                "expected_revision": after.get("revision") or revision,
                "label": "r13_after_failure",
                "entities": [
                    {
                        "type": "polyline",
                        "name": "r13_after_failure_outline",
                        "points": [[500.0, 0.0], [560.0, 0.0], [560.0, 20.0], [500.0, 20.0]],
                        "closed": True,
                    }
                ],
                "dimensioning": "coordinates",
            },
            record,
        )
        case["followup"] = {
            "status": followup["status"],
            "revision": followup.get("revision"),
            "message": str(followup.get("message"))[:300],
        }
    case["verification_level"] = "live"
    case["judged"] = judge_copy_case(case, phase=phase)
    return case


async def wait_ready(client, record: dict, budget: float = 300.0) -> dict:
    """Wait for the service's own startup (worker verify) to settle, then report."""
    deadline = time.monotonic() + budget
    seen: list[dict] = []
    while time.monotonic() < deadline:
        status = await call(client, "creo_session_status", {})
        if status.get("connected"):
            record["startup_wait"] = seen
            return status
        state = status.get("state") or status.get("connection_state")
        seen.append({"state": state, "message": str(status.get("message"))[:160]})
        if state in ("disabled", "selection_required", "configuration_error"):
            raise RuntimeError(f"session cannot become ready: {state}: {status.get('message')}")
        await asyncio.sleep(3)
    record["startup_wait"] = seen
    raise RuntimeError(f"session did not become connected within {budget:.0f}s")


async def scenario(record: dict, phase: str) -> None:
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT)
    )
    async with Client(parameters) as connected:
        status = await wait_ready(connected, record)
        record["session"] = {"connected": status.get("connected")}
        for spec in scenario_specs():
            print(f"case {spec['case_id']} model={spec['model_name']}", flush=True)
            record["cases"].append(await run_case(connected, spec, record, phase))


def summarize(record: dict, phase: str) -> str:
    verdicts = [case["judged"]["verdict"] for case in record["cases"]]
    if "fail" in verdicts:
        return "fail"
    if not verdicts or "unverified" in verdicts:
        return "unverified"
    return "pass"


def describe(failure: BaseException) -> str:
    """Flatten nested ExceptionGroups so the report keeps the real cause."""
    if isinstance(failure, BaseExceptionGroup):
        return " | ".join(describe(item) for item in failure.exceptions)
    return f"{type(failure).__name__}: {failure}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BUG-111 transform rotation/copy fixture")
    parser.add_argument("--phase", choices=PHASES, default="reproduce")
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
        "work_item": "BUG-111",
        "verification_level": "live",
        "scope": "copy_batch",
        "phase": arguments.phase,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": _environment(),
        "identity": _identity(),
        "calls": [],
        "cases": [],
        "success": False,
    }
    started = time.monotonic()
    error = None
    try:
        asyncio.run(scenario(record, arguments.phase))
    except BaseException as failure:  # noqa: BLE001 - the report is the product here
        error = describe(failure)
    record["elapsed_s"] = round(time.monotonic() - started, 1)
    if error:
        record["error"] = error
    record["verdict"] = summarize(record, arguments.phase)
    record["success"] = error is None and record["verdict"] == "pass"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: record[key] for key in ("success", "verdict", "error") if key in record},
            indent=2,
        )
    )
    print(f"report: {output}")
    if record["verdict"] == "pass" and error is None:
        return 0
    return 1 if record["verdict"] == "fail" else 2


if __name__ == "__main__":
    raise SystemExit(main())
