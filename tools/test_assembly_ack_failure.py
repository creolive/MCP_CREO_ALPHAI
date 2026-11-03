"""BUG-110 live probe: does a failed model have a working way out?

Builds a small source part, creates an assembly, then submits an assembly job
that is meant to fail natively (a mate constraint pointing at a surface id that
cannot exist). Each outcome is judged separately, never merged:

* ``failure_guard`` - the job rolled back cleanly and the model stayed ``ready``.
  ``ack_failure`` must then refuse. This is the zero-change guard, not the
  success path;
* ``ack_success`` - the model actually landed in ``failed``. The probe inspects
  it, freezes the revision, file bytes and component bindings, applies
  ``ack_failure``, verifies nothing changed, replays the identical arguments,
  and finally proves the model is usable again with a separate legal operation;
* ``part_guard`` - the same zero-change guard observed on a part, recorded so a
  part result is never counted as assembly coverage.

Part coverage and assembly coverage are reported separately: a part
acknowledgement never closes the assembly case.

Nothing is asserted about Creo's internals. The report states what happened.

Usage (after a human confirmed the session is operable):
    .venv\\Scripts\\python.exe tools\\test_assembly_ack_failure.py --confirmed-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "build" / "assembly_ack_failure_report.json"
PLATE = [[0.0, 0.0], [60.0, 0.0], [60.0, 20.0], [0.0, 20.0]]


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


def _coverage(model_type: str, scope: str, verdict: str) -> dict:
    return {
        "model_type": model_type,
        "scope": scope,
        "covers_ack_success": scope == "ack_success" and verdict == "pass",
        "covers_assembly": model_type == "assembly",
    }


def judge_ack_case(case: dict, *, model_type: str = "assembly") -> dict:
    """Judge one recorded reconciliation case from its evidence only."""
    checks: list[dict] = []
    scope = case.get("scope")
    failure = case.get("failure") if isinstance(case.get("failure"), dict) else {}
    state = (
        case.get("state_after_failure") if isinstance(case.get("state_after_failure"), dict) else {}
    )
    actions = case.get("actions")
    available = None
    if isinstance(actions, list):
        for item in actions:
            if isinstance(item, dict) and item.get("action") == "ack_failure":
                available = item.get("available")

    checks.append(
        _check(
            "failure_job_recorded",
            failure.get("status"),
            "failed",
            "pass" if failure.get("status") == "failed" else "unverified",
        )
    )

    if scope == "ack_success":
        checks.append(
            _check(
                "model_landed_failed",
                state.get("status"),
                "failed",
                "pass" if state.get("status") == "failed" else "unverified",
            )
        )
        checks.append(
            _check(
                "ack_offered",
                available,
                True,
                "pass" if available is True else "unverified",
            )
        )
        applied = case.get("apply") if isinstance(case.get("apply"), dict) else {}
        result = applied.get("result") if isinstance(applied.get("result"), dict) else {}
        checks.append(
            _check(
                "ack_applied",
                {"status": result.get("status"), "action": result.get("action")},
                {"status": "ready", "action": "ack_failure"},
                (
                    "pass"
                    if result.get("status") == "ready" and result.get("action") == "ack_failure"
                    else ("fail" if result else "unverified")
                ),
            )
        )

        before = applied.get("before") if isinstance(applied.get("before"), dict) else {}
        after = applied.get("after") if isinstance(applied.get("after"), dict) else {}
        if isinstance(before.get("revision"), int) and isinstance(after.get("revision"), int):
            checks.append(
                _check(
                    "revision_unchanged",
                    after.get("revision"),
                    before.get("revision"),
                    "pass" if after.get("revision") == before.get("revision") else "fail",
                )
            )
        else:
            checks.append(_check("revision_unchanged", None, "two revisions", "unverified"))
        if before.get("file_sha256") and after.get("file_sha256"):
            checks.append(
                _check(
                    "file_bytes_unchanged",
                    after.get("file_sha256"),
                    before.get("file_sha256"),
                    "pass" if after.get("file_sha256") == before.get("file_sha256") else "fail",
                )
            )
        else:
            checks.append(_check("file_bytes_unchanged", None, "two file hashes", "unverified"))
        if isinstance(before.get("bindings"), list) and isinstance(after.get("bindings"), list):
            checks.append(
                _check(
                    "bindings_unchanged",
                    after.get("bindings"),
                    before.get("bindings"),
                    "pass" if after.get("bindings") == before.get("bindings") else "fail",
                )
            )
        else:
            checks.append(_check("bindings_unchanged", None, "two binding lists", "unverified"))

        replay = case.get("replay") if isinstance(case.get("replay"), dict) else {}
        checks.append(
            _check(
                "replay_same_key",
                replay.get("same_key"),
                True,
                "pass" if replay.get("same_key") is True else "unverified",
            )
        )
        # Replay outcomes are judged from the evidence itself, not from whether the
        # key matched: a second mutation or a changed result is a failed invariant
        # even when the request was replayed with a different key. Only absent
        # evidence stays unverified.
        mutation = replay.get("second_mutation")
        checks.append(
            _check(
                "replay_single_transaction",
                mutation,
                False,
                "pass" if mutation is False else ("fail" if mutation is True else "unverified"),
            )
        )
        same_result = replay.get("same_result")
        checks.append(
            _check(
                "replay_same_result",
                same_result,
                True,
                "pass"
                if same_result is True
                else ("fail" if same_result is False else "unverified"),
            )
        )

        followup = case.get("followup") if isinstance(case.get("followup"), dict) else {}
        checks.append(
            _check(
                "usable_after_ack",
                followup.get("status"),
                "succeeded",
                "pass" if followup.get("status") == "succeeded" else "unverified",
            )
        )
        verdict = _verdict(checks, "acknowledged a failed model without touching it")
        return {**verdict, "coverage": _coverage(model_type, "ack_success", verdict["verdict"])}

    if scope == "failure_guard":
        checks.append(
            _check(
                "model_stayed_ready",
                state.get("status"),
                "ready",
                "pass" if state.get("status") == "ready" else "unverified",
            )
        )
        refusal = case.get("ack_refusal")
        message = str((refusal or {}).get("message") or "") if isinstance(refusal, dict) else ""
        checks.append(
            _check(
                "ack_refused_on_ready",
                message[:200],
                "a refusal message",
                "pass" if refusal and message else "unverified",
            )
        )
        verdict = _verdict(checks, "zero-change guard: nothing to acknowledge")
        return {**verdict, "coverage": _coverage(model_type, "failure_guard", verdict["verdict"])}

    return {
        **_verdict([], f"unknown scope: {scope!r}"),
        "coverage": _coverage(model_type, str(scope), "unverified"),
    }


async def call(client, name: str, arguments: dict) -> dict:
    response = await client.call_tool(name, arguments)
    if response.is_error:
        raise RuntimeError(f"{name}: {response.content}")
    return response.structured_content


async def expect_error(client, name: str, arguments: dict) -> dict:
    response = await client.call_tool(name, arguments)
    message = " ".join(block.text for block in response.content if hasattr(block, "text"))
    return {"message": message[:400], "is_error": bool(response.is_error)}


async def poll(client, job_id: str, budget: int = 300, delay: float = 0.5) -> dict:
    result: dict = {}
    for _ in range(budget):
        result = await call(client, "creo_get_job", {"job_id": job_id})
        if result["status"] not in ("queued", "running"):
            break
        await asyncio.sleep(delay)
    return result


async def job(
    client, name: str, arguments: dict, record: dict, expect_failure: bool = False
) -> dict:
    created = await call(client, name, arguments)
    job_id = created["job_id"]
    result = await poll(client, job_id)
    record["calls"].append(
        {
            "tool": name,
            "job_id": job_id,
            "status": result["status"],
            "stage": result.get("stage"),
            "message": str(result.get("message"))[:400],
            "revision": result.get("revision"),
            "model_unchanged": (result.get("result") or {}).get("model_unchanged"),
            "rollback_status": (result.get("result") or {}).get("rollback_status"),
            "failed_operation_index": (result.get("result") or {}).get("failed_operation_index"),
            "saved_file_reloaded_and_verified": (result.get("result") or {}).get(
                "saved_file_reloaded_and_verified"
            ),
        }
    )
    print(f"{name} job={job_id} status={result['status']}", flush=True)
    if expect_failure and result["status"] == "succeeded":
        raise RuntimeError(f"{name} was expected to fail but succeeded")
    return result


async def wait_ready(client, record: dict, budget: float = 300.0) -> dict:
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


def file_sha256(path: str | None) -> str | None:
    if not path:
        return None
    file = Path(path)
    return hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None


async def bindings(client, model_id: str) -> list[dict] | None:
    try:
        payload = await call(client, "creo_list_components", {"model_id": model_id})
    except Exception:  # noqa: BLE001 - missing bindings stay unverified
        return None
    components = payload.get("components")
    if not isinstance(components, list):
        return None
    return [
        {
            key: item.get(key)
            for key in ("component_id", "feature_id", "source_model_id", "model_name")
            if key in item
        }
        for item in components
        if isinstance(item, dict)
    ]


async def snapshot(client, model_id: str) -> dict:
    try:
        compact = await call(client, "creo_inspect_model", {"model_id": model_id})
    except Exception:  # noqa: BLE001
        return {}
    return {
        "revision": compact.get("revision"),
        "status": compact.get("status"),
        "file_sha256": file_sha256(compact.get("part_file")),
        "bindings": await bindings(client, model_id),
    }


def _ack_arguments(model_id: str, inspected: dict, key: str) -> dict:
    """One acknowledgement request; replays pass the exact same dictionary."""
    return {
        "model_id": model_id,
        "mode": "apply",
        "action": "ack_failure",
        "confirm_failure_ack": True,
        "expected_revision": inspected["revision"],
        "expected_pending_job_id": inspected.get("pending_job"),
        "evidence_token": inspected.get("evidence_token"),
        "idempotency_key": key,
    }


async def build_source(client, record: dict, suffix: int) -> tuple[str, int]:
    part = await call(client, "creo_new_part", {"model_name": f"r13src{suffix}"})
    source_id = part["model_id"]
    created = await job(client, "creo_get_job", {"job_id": part["job_id"]}, record)
    revision = created["revision"]
    sketch = await job(
        client,
        "creo_create_sketch",
        {
            "model_id": source_id,
            "expected_revision": revision,
            "label": "r13_ack_profile",
            "entities": [
                {
                    "type": "polyline",
                    "name": "r13_ack_outline",
                    "points": PLATE,
                    "closed": True,
                }
            ],
            "dimensioning": "coordinates",
        },
        record,
    )
    if sketch["status"] == "succeeded":
        revision = sketch["revision"]
    solid = await job(
        client,
        "creo_extrude",
        {
            "model_id": source_id,
            "expected_revision": revision,
            "label": "r13_ack_plate",
            "sketch": "r13_ack_profile",
            "depth": 5,
        },
        record,
    )
    if solid["status"] == "succeeded":
        revision = solid["revision"]
    return source_id, revision


async def part_guard(client, record: dict, suffix: int) -> dict:
    """A failing part job: record whether the zero-change guard also applies."""
    part = await call(client, "creo_new_part", {"model_name": f"r13part{suffix}"})
    model_id = part["model_id"]
    await job(client, "creo_get_job", {"job_id": part["job_id"]}, record)
    failed = await job(
        client,
        "creo_extrude",
        {
            "model_id": model_id,
            "expected_revision": 1,
            "label": "r13_missing_sketch",
            "sketch": "r13_does_not_exist",
            "depth": 5,
        },
        record,
        expect_failure=True,
    )
    inspected = await call(client, "creo_reconcile_model", {"model_id": model_id})
    case = {
        "case_id": "PART-GUARD",
        "scope": "failure_guard",
        "model_type": "part",
        "model_id": model_id,
        "failure": {"job_id": record["calls"][-1]["job_id"], "status": failed["status"]},
        "state_after_failure": {
            "status": inspected.get("status"),
            "revision": inspected.get("revision"),
        },
        "actions": inspected.get("actions"),
        "verification_level": "live",
    }
    if inspected.get("status") == "ready":
        case["ack_refusal"] = await expect_error(
            client,
            "creo_reconcile_model",
            _ack_arguments(model_id, inspected, f"r13-part-guard-{int(time.time())}"),
        )
    case["judged"] = judge_ack_case(case, model_type="part")
    return case


async def assembly_case(client, record: dict, suffix: int) -> dict:
    source_id, _ = await build_source(client, record, suffix)
    surface_ids: list[int] = []
    try:
        surfaces = await call(
            client,
            "creo_inspect_model",
            {"model_id": source_id, "detail": "full", "section": "surfaces", "limit": 200},
        )
        listing = (surfaces.get("data") or {}).get("surfaces") or []
        surface_ids = [
            item.get("id")
            for item in listing
            if isinstance(item, dict) and isinstance(item.get("id"), int)
        ]
        record["source_surface_ids"] = surface_ids[:8]
    except Exception as failure:  # noqa: BLE001 - recorded, the failure is the point
        record["inspect_error"] = str(failure)[:400]
    component_surface = surface_ids[0] if surface_ids else 1

    assembly = await call(client, "creo_new_assembly", {"model_name": f"r13asm{suffix}"})
    assembly_id = assembly["model_id"]
    record["assembly_model_id"] = assembly_id
    await job(client, "creo_get_job", {"job_id": assembly["job_id"]}, record)

    before_failure = await snapshot(client, assembly_id)
    failed = await job(
        client,
        "creo_assemble_component",
        {
            "model_id": assembly_id,
            "expected_revision": before_failure.get("revision"),
            "label": "r13_ack_pin",
            "source_model_id": source_id,
            "placement": "constraints",
            "constraints": [
                {
                    "type": "mate",
                    "assembly_reference": {"kind": "surface", "id": 999999},
                    "component_reference": {"kind": "surface", "id": component_surface},
                }
            ],
        },
        record,
        expect_failure=True,
    )
    inspected = await call(client, "creo_reconcile_model", {"model_id": assembly_id})
    case = {
        "case_id": "ASM",
        "scope": "failure_guard",
        "model_type": "assembly",
        "model_id": assembly_id,
        "failure": {"job_id": record["calls"][-1]["job_id"], "status": failed["status"]},
        "state_after_failure": {
            "status": inspected.get("status"),
            "revision": inspected.get("revision"),
            "pending_job": inspected.get("pending_job"),
        },
        "actions": inspected.get("actions"),
        "failure_result": failed.get("result"),
        "verification_level": "live",
    }
    if inspected.get("status") != "failed":
        # Zero-change guard: the model stayed ready and the action must refuse.
        case["ack_refusal"] = await expect_error(
            client,
            "creo_reconcile_model",
            _ack_arguments(assembly_id, inspected, f"r13-ack-guard-{int(time.time())}"),
        )
        case["judged"] = judge_ack_case(case, model_type="assembly")
        record["outcome"] = "failure_rollback_left_model_ready"
        return case

    # The model is genuinely failed: acknowledge it and prove nothing else moved.
    case["scope"] = "ack_success"
    before = await snapshot(client, assembly_id)
    arguments = _ack_arguments(assembly_id, inspected, f"r13-ack-{int(time.time())}")
    acknowledged = await call(client, "creo_reconcile_model", arguments)
    after = await snapshot(client, assembly_id)
    case["apply"] = {
        "arguments": {key: value for key, value in arguments.items() if key != "evidence_token"},
        "result": {
            key: acknowledged.get(key)
            for key in (
                "mode",
                "action",
                "model_id",
                "status",
                "revision",
                "reconciliation",
                "note",
                "message",
                "job_id",
            )
        },
        "before": before,
        "after": after,
    }
    replay = await call(client, "creo_reconcile_model", arguments)
    replayed = await snapshot(client, assembly_id)
    case["replay"] = {
        "same_key": True,
        "same_result": replay.get("revision") == acknowledged.get("revision")
        and replay.get("status") == acknowledged.get("status"),
        "second_mutation": replayed.get("revision") != after.get("revision"),
        "result": {key: replay.get(key) for key in ("status", "revision", "note", "message")},
    }
    followup = await job(
        client,
        "creo_assemble_component",
        {
            "model_id": assembly_id,
            "expected_revision": replayed.get("revision"),
            "label": "r13_after_ack",
            "source_model_id": source_id,
            "placement": "identity",
        },
        record,
    )
    case["followup"] = {
        "status": followup["status"],
        "revision": followup.get("revision"),
        "message": str(followup.get("message"))[:300],
    }
    case["judged"] = judge_ack_case(case, model_type="assembly")
    record["outcome"] = "ack_failure_applied"
    return case


async def scenario(record: dict) -> None:
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT)
    )
    async with Client(parameters) as connected:
        status = await wait_ready(connected, record)
        record["session"] = {"connected": status.get("connected")}
        suffix = int(time.time()) % 100000
        record["cases"].append(await part_guard(connected, record, suffix))
        record["cases"].append(await assembly_case(connected, record, suffix))


def summarize(record: dict) -> dict:
    """Per-model-type coverage; never merge part and assembly into one pass."""
    coverage: dict[str, str] = {}
    for model_type in ("part", "assembly"):
        verdicts = [
            case["judged"]["verdict"]
            for case in record["cases"]
            if case.get("model_type") == model_type
        ]
        if "fail" in verdicts:
            coverage[model_type] = "fail"
        elif any(
            case["judged"].get("coverage", {}).get("covers_ack_success")
            for case in record["cases"]
            if case.get("model_type") == model_type
        ):
            coverage[model_type] = "ack_success"
        elif verdicts and "unverified" not in verdicts:
            coverage[model_type] = "guard_only"
        else:
            coverage[model_type] = "unverified"
    return coverage


def describe(failure: BaseException) -> str:
    if isinstance(failure, BaseExceptionGroup):
        return " | ".join(describe(item) for item in failure.exceptions)
    return f"{type(failure).__name__}: {failure}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BUG-110 assembly ack_failure probe")
    parser.add_argument("--confirmed-session-usable", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    arguments = parser.parse_args(argv)
    if not arguments.confirmed_session_usable:
        print("live runs require --confirmed-session-usable after human session checks")
        return 2
    record: dict = {
        "work_item": "BUG-110",
        "verification_level": "live",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "identity": _identity(),
        "calls": [],
        "cases": [],
        "success": False,
    }
    started = time.monotonic()
    error = None
    try:
        asyncio.run(scenario(record))
    except BaseException as failure:  # noqa: BLE001 - the report is the product here
        error = describe(failure)
    record["elapsed_s"] = round(time.monotonic() - started, 1)
    if error:
        record["error"] = error
    record["coverage"] = summarize(record)
    record["verdict"] = (
        "fail"
        if "fail" in record["coverage"].values()
        else ("pass" if record["coverage"].get("assembly") == "ack_success" else "unverified")
    )
    record["success"] = error is None and record["verdict"] == "pass"
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: record[key]
                for key in ("success", "verdict", "coverage", "outcome", "error")
                if key in record
            },
            indent=2,
        )
    )
    print(f"report: {output}")
    if record["verdict"] == "pass" and error is None:
        return 0
    return 1 if record["verdict"] == "fail" else 2


if __name__ == "__main__":
    raise SystemExit(main())
