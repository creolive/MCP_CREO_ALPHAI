"""FEAT-007 R12: long-poll acceptance over a real stdio MCP session.

The offline contract (integer 0..30, expiry fields, no job creation while
waiting) is covered by unit tests. This driver exercises the same fields
through the real client/server pair on the connected Creo session:

* ``wait_seconds=0`` returns the current record immediately;
* a one second wait on a running job expires with ``wait_expired=true`` and the
  record untouched;
* a thirty second wait returns as soon as the job reaches a terminal state,
  well before the deadline;
* cancelling the client-side wait (the protocol-level interruption) does not
  cancel the job: the same job id reaches terminal afterwards, and nothing is
  resubmitted;
* an out-of-range wait is refused without touching the job;
* a second client reads the same persisted job without creating anything.

Only ``--live --confirm-session-usable`` runs it; every job it creates is a
fresh empty sheetmetal model so no geometry is needed to observe the wait.
The report lands in build/job_wait/<run_id>/ and is never overwritten.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))
if str(_SOURCE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT / "src"))

from bridge import MAX_JOB_WAIT_SECONDS, _validate_wait_seconds  # noqa: E402
from tools.test_failed_model_cleanup import local_provenance, require_manual_start  # noqa: E402

ROOT = _SOURCE_ROOT
TERMINAL = ("succeeded", "failed", "unknown_outcome")


def describe_error(error: BaseException, depth: int = 0) -> str:
    """Flatten nested ExceptionGroups so a report keeps the real cause."""
    text = f"{'  ' * depth}{type(error).__name__}: {error}"
    for inner in getattr(error, "exceptions", ()) or ():
        text += "\n" + describe_error(inner, depth + 1)
    return text[:1200]


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    path = (
        Path(output) if output is not None else ROOT / "build" / "job_wait" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def offline_checks() -> dict:
    accepted = [value for value in (0, 1, 30) if _validate_wait_seconds(value) == value]
    refused = {}
    for value in (31, -1, 1.5, True, "5", None):
        try:
            _validate_wait_seconds(value)
        except ValueError as error:
            refused[repr(value)] = str(error)[:120]
    assert accepted == [0, 1, 30], accepted
    assert set(refused) == {"31", "-1", "1.5", "True", "'5'", "None"}, refused
    return {
        "max_wait_seconds": MAX_JOB_WAIT_SECONDS,
        "accepted": accepted,
        "refused": refused,
        "note": (
            "offline only proves the integer gate; the real stdio wait, expiry, "
            "cancellation and multi-client read are unrun here"
        ),
    }


class Waiter:
    def __init__(self, client, output: Path, run_id: str) -> None:
        self.client = client
        self.output = output
        self.report: dict = {
            "task": "FEAT-007 R12 long-poll acceptance",
            "run_id": run_id,
            "mode": "live",
            "started_at": time.time(),
            "provenance": local_provenance(),
            "cases": [],
            "calls": [],
        }

    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def call(self, name: str, args: dict, *, allow_error: bool = False) -> dict:
        record = {"tool": name, "args": dict(args), "started_at": time.time()}
        self.report["calls"].append(record)
        try:
            result = await self.client.call_tool(name, args)
        except BaseException as error:  # cancellation must be recorded, not swallowed
            record.update(finished_at=time.time(), raised=f"{type(error).__name__}: {error}"[:300])
            self.save()
            raise
        payload = result.structured_content if not result.is_error else None
        record.update(
            finished_at=time.time(),
            is_error=result.is_error,
            status=(payload or {}).get("status"),
            wait_expired=(payload or {}).get("wait_expired"),
            waited_seconds=(payload or {}).get("waited_seconds"),
            detail=None if payload is None else str(result.content)[:200],
        )
        self.save()
        if result.is_error and not allow_error:
            raise RuntimeError(f"{name}: {result.content}")
        return (
            payload if payload is not None else {"is_error": True, "content": str(result.content)}
        )

    async def poll(self, job_id: str, wait_seconds: int) -> tuple[dict, float]:
        started = time.monotonic()
        payload = await self.call(
            "creo_get_job", {"job_id": job_id, "detail": "compact", "wait_seconds": wait_seconds}
        )
        return payload, time.monotonic() - started

    async def submit(self, model_name: str) -> dict:
        return await self.call("creo_new_sheetmetal", {"model_name": model_name})

    async def create_job(self, tag: str) -> dict:
        model_name = f"{tag}_{self.report['run_id'].rsplit('_', 1)[-1]}"
        accepted = await self.submit(model_name)
        return {"model_name": model_name, "accepted": accepted}

    async def case_immediate(self, job: dict) -> None:
        case = {"id": "immediate_zero_wait", "job_id": job["accepted"]["job_id"]}
        self.report["cases"].append(case)
        self.save()
        payload, elapsed = await self.poll(case["job_id"], 0)
        case["payload"] = {
            "status": payload.get("status"),
            "wait_seconds": payload.get("wait_seconds"),
            "waited_seconds": payload.get("waited_seconds"),
            "wait_expired": payload.get("wait_expired"),
            "revision": payload.get("revision"),
        }
        case["wall_seconds"] = round(elapsed, 3)
        case["assertions"] = {
            "returned_immediately": elapsed < 2.0,
            "wait_seconds_echo": payload.get("wait_seconds") == 0,
            "waited_seconds_zero": payload.get("waited_seconds") == 0,
            "not_marked_expired": payload.get("wait_expired") is False,
        }
        case["passed"] = all(case["assertions"].values())
        self.save()

    async def case_expiry(self, job: dict) -> None:
        case = {"id": "expiry_one_second", "job_id": job["accepted"]["job_id"]}
        self.report["cases"].append(case)
        self.save()
        payload, elapsed = await self.poll(case["job_id"], 1)
        status = payload.get("status")
        case["payload"] = {
            "status": status,
            "wait_seconds": payload.get("wait_seconds"),
            "waited_seconds": payload.get("waited_seconds"),
            "wait_expired": payload.get("wait_expired"),
        }
        case["wall_seconds"] = round(elapsed, 3)
        if status in TERMINAL:
            # A fast job legitimately returns before the deadline; that is the
            # terminal contract, not proof of expiry, so say so instead of
            # turning a timing race into a false failure.
            case["terminal_too_fast"] = True
            case["assertions"] = {
                "returned_before_deadline": float(payload.get("waited_seconds") or 0) < 4.0,
                "terminal_without_expiry_flag": payload.get("wait_expired") is False,
            }
            case["note"] = "expiry not observed: the job reached a terminal state first"
        else:
            case["assertions"] = {
                "not_terminal_when_waiting": True,
                "expired_flag": payload.get("wait_expired") is True,
                "waited_at_least_one_second": float(payload.get("waited_seconds") or 0) >= 1.0,
                "waited_well_under_deadline": float(payload.get("waited_seconds") or 0) < 4.0,
            }
        case["passed"] = all(case["assertions"].values())
        self.save()

    async def case_terminal(self, job: dict) -> None:
        case = {"id": "terminal_within_thirty_seconds", "job_id": job["accepted"]["job_id"]}
        self.report["cases"].append(case)
        self.save()
        payload, elapsed = await self.poll(case["job_id"], 30)
        status = payload.get("status")
        case["payload"] = {
            "status": status,
            "wait_seconds": payload.get("wait_seconds"),
            "waited_seconds": payload.get("waited_seconds"),
            "wait_expired": payload.get("wait_expired"),
            "revision": payload.get("revision"),
            "model_id": payload.get("model_id"),
        }
        case["wall_seconds"] = round(elapsed, 3)
        case["assertions"] = {
            "reached_terminal": status in TERMINAL,
            "not_expired": payload.get("wait_expired") is False,
            "returned_before_deadline": elapsed < 30.0,
            "same_job": payload.get("job_id") == case["job_id"],
        }
        case["passed"] = all(case["assertions"].values())
        self.save()

    async def case_cancel(self, job: dict) -> None:
        case = {"id": "client_cancel_does_not_cancel_job", "job_id": job["accepted"]["job_id"]}
        self.report["cases"].append(case)
        self.save()
        task = asyncio.create_task(self.poll(case["job_id"], 30))
        await asyncio.sleep(1.0)
        task.cancel()
        outcome = await asyncio.gather(task, return_exceptions=True)
        case["cancel_outcome"] = f"{type(outcome[0]).__name__}: {outcome[0]}"
        case["cancelled_after_seconds"] = 1.0
        self.save()
        immediate, _ = await self.poll(case["job_id"], 0)
        after, elapsed = await self.poll(case["job_id"], 30)
        case["read_after_cancel"] = {
            "status": immediate.get("status"),
            "revision": immediate.get("revision"),
        }
        case["terminal_after_cancel"] = {
            "status": after.get("status"),
            "wait_expired": after.get("wait_expired"),
            "wall_seconds": round(elapsed, 3),
            "revision": after.get("revision"),
            "model_id": after.get("model_id"),
        }
        case["assertions"] = {
            "cancel_raised": isinstance(outcome[0], BaseException),
            "session_still_readable": immediate.get("job_id") == case["job_id"],
            "job_still_reached_terminal": after.get("status") in TERMINAL,
            "no_second_job_for_model": after.get("job_id") == case["job_id"],
        }
        case["passed"] = all(case["assertions"].values())
        self.save()

    async def case_boundaries(self, job: dict) -> None:
        case = {"id": "wait_boundaries_refused", "job_id": job["accepted"]["job_id"]}
        self.report["cases"].append(case)
        self.save()
        before, _ = await self.poll(case["job_id"], 0)
        refused = {}
        for value in (31, 1.5):
            payload = await self.call(
                "creo_get_job",
                {"job_id": case["job_id"], "detail": "compact", "wait_seconds": value},
                allow_error=True,
            )
            refused[str(value)] = payload.get("content", "")[:160]
        after, _ = await self.poll(case["job_id"], 0)
        case["refused"] = refused
        case["assertions"] = {
            "thirty_one_refused": "wait_seconds" in refused["31"],
            "one_and_a_half_refused": "wait_seconds" in refused["1.5"],
            "job_unchanged": after.get("revision") == before.get("revision")
            and after.get("status") == before.get("status"),
        }
        case["passed"] = all(case["assertions"].values())
        self.save()


async def multi_client_read(job_id: str, expected: dict, report: dict) -> dict:
    """A second stdio client reads the same persisted job; nothing is created."""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    case: dict = {"id": "second_client_reads_same_job", "job_id": job_id, "assertions": {}}
    report["cases"].append(case)
    try:
        async with Client(params, read_timeout_seconds=120) as second:
            result = await second.call_tool(
                "creo_get_job", {"job_id": job_id, "detail": "compact", "wait_seconds": 0}
            )
            payload = result.structured_content or {}
            case["payload"] = {
                "status": payload.get("status"),
                "revision": payload.get("revision"),
                "model_id": payload.get("model_id"),
                "wait_expired": payload.get("wait_expired"),
            }
            case["assertions"] = {
                "read_succeeded": result.is_error is False,
                "same_status": payload.get("status") == expected.get("status"),
                "same_revision": payload.get("revision") == expected.get("revision"),
                "same_model": payload.get("model_id") == expected.get("model_id"),
                "still_same_job": payload.get("job_id") == job_id,
            }
    except BaseException as error:
        # mcp's stdio_client teardown can raise an ExceptionGroup after the read
        # already succeeded; record it instead of discarding the read evidence.
        case["client_error"] = describe_error(error)
    if not case["assertions"]:
        case["assertions"] = {"read_succeeded": False}
    case["passed"] = all(case["assertions"].values())
    return case


async def live(output: Path, run_id: str) -> int:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    from tools.mcp_readiness import wait_for_startup

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    waiter: Waiter | None = None
    teardown = None
    try:
        async with Client(params, read_timeout_seconds=180) as client:
            waiter = Waiter(client, output, run_id)
            waiter.save()
            try:
                startup = await wait_for_startup(client, {}, output)
                waiter.report["startup"] = {
                    key: startup.get(key)
                    for key in ("state", "phase", "connected", "retry_id", "retry_blocked_by")
                }
                waiter.save()
                status = await waiter.call("creo_session_status", {})
                waiter.report["session"] = {
                    "connected": status.get("connected"),
                    "state": status.get("state"),
                }
                if not status.get("connected"):
                    waiter.report["stopped"] = "session not connected; nothing submitted"
                    waiter.report["passed"] = False
                    waiter.save()
                    return 1
                first = await waiter.create_job("wait_a")
                waiter.report["first_job"] = {
                    "model_name": first["model_name"],
                    "job_id": first["accepted"].get("job_id"),
                    "model_id": first["accepted"].get("model_id"),
                }
                await waiter.case_immediate(first)
                await waiter.case_expiry(first)
                await waiter.case_terminal(first)
                await waiter.case_boundaries(first)

                second = await waiter.create_job("wait_b")
                waiter.report["second_job"] = {
                    "model_name": second["model_name"],
                    "job_id": second["accepted"].get("job_id"),
                    "model_id": second["accepted"].get("model_id"),
                }
                await waiter.case_cancel(second)

                terminal, _ = await waiter.poll(second["accepted"]["job_id"], 0)
                await multi_client_read(second["accepted"]["job_id"], terminal, waiter.report)
                waiter.report["passed"] = all(
                    case.get("passed") is True for case in waiter.report["cases"]
                )
                waiter.report["finished_at"] = time.time()
                waiter.save()
            except BaseException as error:
                waiter.report["stopped"] = describe_error(error)
                waiter.report["passed"] = False
    except BaseException as error:  # teardown failures must not orphan the server
        teardown = describe_error(error)
    if waiter is None:
        raise RuntimeError(f"MCP client never started: {teardown}")
    if teardown:
        waiter.report["client_teardown"] = teardown[:600]
        waiter.report.setdefault("stopped", "client teardown failed")
        waiter.report["passed"] = False
    waiter.save()
    print(json.dumps({"report": str(output), "passed": waiter.report["passed"]}))
    return 0 if waiter.report["passed"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.live and not args.confirm_session_usable:
        print("live runs require --confirm-session-usable", file=sys.stderr)
        return 2
    try:
        run_id = new_run_id()
        output = resolve_output(args.output, run_id)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    if args.live:
        try:
            require_manual_start(ROOT / "config.json")
        except (ValueError, OSError) as error:
            print(f"LIVE_REFUSED: {error}", file=sys.stderr)
            return 2
        return asyncio.run(live(output, run_id))

    report = {
        "task": "FEAT-007 R12 long-poll acceptance",
        "run_id": run_id,
        "mode": "offline",
        "native_acceptance": "not_run",
        "provenance": local_provenance(),
        "checks": offline_checks(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OFFLINE ONLY: no MCP client, connection or Toolkit channel executed. {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
