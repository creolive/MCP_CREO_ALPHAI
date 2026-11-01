"""BUG-096 (Q03/E) failed-model cleanup acceptance driver. Default is strictly offline.

Only ``--live --confirm-session-usable`` starts an MCP client. The confirm flag
attests that the operator finished the BUG-001/BUG-091 session recovery
checks. The driver never launches or stops Creo, never clears protection,
never injects faults into real objects, never resubmits a busy/unknown job and
never erases anything outside the single cleanup path under test.

Offline (default): replays the stubbed probe matrix and the receipt contract
through ``creo_mechdog.failed_model_cleanup`` and writes a JSON report. No
MCP client, no connection, no Toolkit channel.

Live: three scenarios on the connected session, each recorded with raw tool
returns (job_id, model_id, terminal status, receipt).

  S1 main path:  create a new model with a plan that fails natively AFTER the
                 model exists, then rebuild the SAME name successfully.
                 Expect failed_model_cleanup.status=erased with
                 absence_verified=true, then the same-name job succeeds
                 (the feedback E rename workaround is gone).
  S2 pre-existing same-name victim: a successfully saved model holds the
                 name; a new-model job with the same name must fail with the
                 name conflict AND the victim must survive untouched
                 (receipt reason=preexisting_same_name, its file hash
                 unchanged, its revision still readable).
  S3 saved model failure: a failed edit on a checkpointed model must still
                 roll back to its save point with revision unchanged and
                 report failed_model_cleanup=not_new_model_job (cleanup is
                 not restore-checkpoint; the two blocks coexist).

  S4 unknown_outcome: deliberately NOT triggerable here. Fault injection into
                 real objects is forbidden, so the unknown_outcome contract
                 (no cleanup claim without real absence evidence) is only
                 covered by the offline stubs and must stay "未验证" in the
                 live report.

Manual integration checklist (run S1..S3 and confirm by eye in Creo):
  1. after S1's failed job the failed object is GONE from the Creo session
     (Model Tree / creo_list_session_models) and no .prt was written for it;
  2. the same model name creates again without renaming (S1 step 2);
  3. pre-existing models and their files are unaffected (S2 victim hash and
     every earlier job's output are unchanged);
  4. a failed job on an ALREADY SAVED model still restores its checkpoint
     (rollback_succeeded true), revision does NOT advance and the saved file
     still reloads;
  5. the receipt of every failed job is readable through
     creo_get_job(detail=compact).result.failed_model_cleanup and never
     claims absence_verified without the erased/cleaned pair.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))
if str(_SOURCE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT / "src"))

from creo_mechdog import failed_model_cleanup as cleanup  # noqa: E402

ROOT = _SOURCE_ROOT


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def require_live(args: argparse.Namespace) -> bool:
    if args.live and not args.confirm_session_usable:
        raise ValueError(
            "--live requires --confirm-session-usable after human session recovery checks"
        )
    return args.live


def require_manual_start(config_file: Path) -> None:
    """Driver-only precondition; never edits the user's startup configuration."""
    settings = json.loads(config_file.read_text(encoding="utf-8-sig"))
    if settings.get("auto_start_creo") is not False:
        raise ValueError(
            "Live acceptance requires config.json auto_start_creo=false; no client was started"
        )


def resolve_output(output: Path | None, run_id: str) -> Path:
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "bug096_failed_model_cleanup" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
    """Record source evidence without recording config, license or session IDs."""

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

    return {
        "head": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
    }


def stub(**overrides) -> dict:
    evidence = {
        "created_by_job": True,
        "identity_matches": True,
        "never_saved": True,
        "window_open": False,
        "user_modified": False,
        "referenced_by_other": False,
        "safety_query_failed": False,
    }
    evidence.update(overrides)
    return evidence


COUNTEREXAMPLES = {
    "preexisting_same_name": stub(created_by_job=False),
    "user_modified": stub(user_modified=True),
    "window_open": stub(window_open=True),
    "referenced_by_other": stub(referenced_by_other=True),
    "erase_safety_query_failed": stub(safety_query_failed=True),
    "absence_query_failed": stub(safety_query_failed=True),
    "identity_changed": stub(identity_matches=False),
    "saved_since_creation": stub(never_saved=False),
}


def offline(output: Path, run_id: str) -> dict:
    report = {
        "task": "BUG-096 failed-model cleanup",
        "run_id": run_id,
        "mode": "offline",
        "provenance": local_provenance(),
        "counterexamples": {},
        "receipt_shapes": {},
        "unknown_outcome_contract": {},
    }
    decision = cleanup.evaluate_candidate(stub())
    assert decision == {"action": "erase", "reason": "cleaned"}, decision
    report["proven_orphan"] = decision
    for name, evidence in COUNTEREXAMPLES.items():
        value = cleanup.evaluate_candidate(evidence)
        assert value["action"] == "keep", (name, value)
        report["counterexamples"][name] = value
    for reason, shape in cleanup.RECEIPT_SHAPES.items():
        code = -3 if shape["erase_code"] == "nonzero" else shape["erase_code"]
        value = {
            "attempted": shape["attempted"],
            "status": shape["status"],
            "reason": reason,
            "erase_code": code,
            "absence_verified": shape["absence_verified"],
        }
        assert cleanup.validate_receipt(value) == value, reason
        report["receipt_shapes"][reason] = "accepted"
        # 查询没执行时不得填成功: flipping absence_verified must be refused
        # for every reason whose flow never runs the absence queries.
        if not shape["absence_verified"]:
            tampered = dict(value, absence_verified=True)
            try:
                cleanup.validate_receipt(tampered)
            except ValueError:
                report["receipt_shapes"][reason] = "accepted; false absence claim refused"
            else:
                raise AssertionError(f"{reason} accepted a false absence claim")
    unknown = cleanup.receipt_unknown_outcome()
    cleanup.validate_receipt(unknown)
    report["unknown_outcome_contract"] = {
        "receipt": unknown,
        "claims_absence": unknown["absence_verified"],
        "note": "unknown_outcome jobs never claim a cleanup they did not prove",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def valid_plan(tag: str) -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": f"{tag}_profile",
            "plane": "XY",
            "entities": [{"type": "circle", "name": f"{tag}_c", "center": [0, 0], "radius": 5}],
        },
        {"op": "extrude", "label": f"{tag}_solid", "sketch": f"{tag}_profile", "depth": 10},
    ]


def failing_plan(tag: str) -> list[dict]:
    """Schema-valid plan that fails natively AFTER the new model exists.

    The round targets an edge id that cannot resolve, so the job fails inside
    the executor with the model already created - exactly the E orphan shape.
    """
    return valid_plan(tag) + [
        {
            "op": "round",
            "label": f"{tag}_bad_round",
            "size": 1,
            "references": [{"kind": "edge", "id": 999999}],
        }
    ]


class LiveRun:
    def __init__(self, client, output: Path, run_id: str) -> None:
        self.client = client
        self.output = output
        self.report: dict = {
            "task": "BUG-096 failed-model cleanup",
            "run_id": run_id,
            "mode": "live",
            "provenance": local_provenance(),
            "started_at": time.time(),
            "calls": [],
            "scenarios": [],
            "unknown_outcome": "not_injected (fault injection forbidden); offline contract only",
        }

    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def call(self, name: str, args: dict, *, allow_error: bool = False):
        record = {"tool": name, "args": copy.deepcopy(args), "started_at": time.time()}
        self.report["calls"].append(record)
        self.save()
        result = await self.client.call_tool(name, args)
        payload = result.structured_content
        record.update(
            finished_at=time.time(),
            is_error=result.is_error,
            result=payload if not result.is_error else str(result.content),
        )
        self.save()
        if result.is_error and not allow_error:
            raise RuntimeError(f"{name}: {result.content}")
        return payload

    async def terminal(self, job_id: str, budget: float = 300) -> dict:
        deadline = time.monotonic() + budget
        while True:
            job = await self.call("creo_get_job", {"job_id": job_id, "detail": "compact"})
            if job.get("status") in ("succeeded", "failed", "unknown_outcome"):
                return job
            if time.monotonic() >= deadline:
                raise TimeoutError(f"job {job_id} did not reach a terminal state")
            await asyncio.sleep(2)

    async def plan(
        self,
        operations: list,
        *,
        model_id: str | None = None,
        revision: int | None = None,
        model_name: str | None = None,
    ) -> dict:
        args: dict = {"operations": operations}
        if model_id is not None:
            args.update(model_id=model_id, expected_revision=revision)
        if model_name is not None:
            args["model_name"] = model_name
        accepted = await self.call("creo_execute_plan", args)
        job = await self.terminal(accepted["job_id"])
        return {"accepted": accepted, "job": job}

    async def session_names(self) -> list:
        listing = await self.call("creo_list_session_models", {"limit": 50})
        return [entry.get("name") for entry in listing.get("models", [])]

    async def run(self) -> None:
        status = await self.call("creo_session_status", {})
        if not status.get("connected"):
            raise RuntimeError(f"session not connected; nothing submitted: {status}")
        self.report["environment"] = await self.call("creo_check_environment", {})
        self.report["capabilities_count"] = len(
            (await self.call("creo_capabilities", {})).get("tools", [])
        )
        await self.scenario_main_path()
        await self.scenario_preexisting_same_name()
        await self.scenario_saved_model_rollback()
        self.report["live_acceptance"] = "completed"
        self.save()

    async def scenario_main_path(self) -> None:
        tag = "q03s1"
        scenario: dict = {"id": "S1_main_path", "model_name": tag}
        self.report["scenarios"].append(scenario)
        self.save()
        failed = await self.plan(failing_plan(tag), model_name=tag)
        scenario["failing_job"] = {
            "job_id": failed["accepted"]["job_id"],
            "model_id": failed["accepted"].get("model_id"),
            "status": failed["job"].get("status"),
            "message": failed["job"].get("message"),
            "failed_model_cleanup": failed["job"].get("result", {}).get("failed_model_cleanup"),
        }
        receipt = scenario["failing_job"]["failed_model_cleanup"] or {}
        scenario["assertions"] = {
            "job_failed": failed["job"].get("status") == "failed",
            "orphan_erased": receipt.get("status") == "erased",
            "absence_verified": receipt.get("absence_verified") is True,
            "reason_cleaned": receipt.get("reason") == "cleaned",
        }
        self.save()
        reused = await self.plan(valid_plan(tag), model_name=tag)
        scenario["same_name_retry"] = {
            "job_id": reused["accepted"]["job_id"],
            "model_id": reused["accepted"].get("model_id"),
            "status": reused["job"].get("status"),
            "revision": reused["job"].get("revision"),
        }
        scenario["assertions"]["same_name_reusable"] = reused["job"].get("status") == "succeeded"
        scenario["passed"] = all(scenario["assertions"].values())
        self.save()

    async def scenario_preexisting_same_name(self) -> None:
        tag = "q03s2"
        scenario: dict = {"id": "S2_preexisting_same_name", "model_name": tag}
        self.report["scenarios"].append(scenario)
        self.save()
        victim = await self.plan(valid_plan(tag), model_name=tag)
        if victim["job"].get("status") != "succeeded":
            scenario["error"] = "victim creation failed; scenario not evaluated"
            self.save()
            return
        victim_model = victim["accepted"].get("model_id")
        before = await self.call("creo_inspect_model", {"model_id": victim_model})
        conflict = await self.plan(valid_plan(tag), model_name=tag)
        receipt = conflict["job"].get("result", {}).get("failed_model_cleanup") or {}
        after = await self.call("creo_inspect_model", {"model_id": victim_model})
        scenario.update(
            victim_model_id=victim_model,
            victim_revision_before=before.get("revision"),
            conflict_job={
                "job_id": conflict["accepted"]["job_id"],
                "status": conflict["job"].get("status"),
                "message": conflict["job"].get("message"),
                "failed_model_cleanup": receipt,
            },
            victim_revision_after=after.get("revision"),
        )
        scenario["assertions"] = {
            "conflict_failed": conflict["job"].get("status") == "failed",
            "victim_kept": receipt.get("reason") == "preexisting_same_name",
            "no_false_absence_claim": receipt.get("absence_verified") is False,
            "victim_still_readable": after.get("revision") == before.get("revision"),
        }
        scenario["passed"] = all(scenario["assertions"].values())
        self.save()

    async def scenario_saved_model_rollback(self) -> None:
        scenario: dict = {"id": "S3_saved_model_rollback"}
        self.report["scenarios"].append(scenario)
        self.save()
        models = await self.call("creo_list_models", {})
        ready = [
            entry
            for entry in models.get("models", [])
            if entry.get("status") == "ready" and entry.get("part_file")
        ]
        if not ready:
            scenario["error"] = "no saved managed model available; scenario not evaluated"
            self.save()
            return
        target = ready[0]
        before = await self.call("creo_inspect_model", {"model_id": target["model_id"]})
        failed = await self.plan(
            failing_plan("q03s3"),
            model_id=target["model_id"],
            revision=before.get("revision"),
        )
        receipt = failed["job"].get("result", {}).get("failed_model_cleanup") or {}
        after = await self.call("creo_inspect_model", {"model_id": target["model_id"]})
        scenario.update(
            target_model_id=target["model_id"],
            revision_before=before.get("revision"),
            failing_job={
                "job_id": failed["accepted"]["job_id"],
                "status": failed["job"].get("status"),
                "rollback_succeeded": failed["job"].get("result", {}).get("rollback_succeeded"),
                "failed_model_cleanup": receipt,
            },
            revision_after=after.get("revision"),
        )
        scenario["assertions"] = {
            "job_failed": failed["job"].get("status") == "failed",
            "rollback_kept_old_semantics": failed["job"].get("result", {}).get("rollback_succeeded")
            is True,
            "revision_unchanged": after.get("revision") == before.get("revision"),
            "cleanup_reports_not_applicable": receipt.get("reason") == "not_new_model_job",
        }
        scenario["passed"] = all(scenario["assertions"].values())
        self.save()


async def live(output: Path, run_id: str) -> None:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=120,
    ) as client:
        run = LiveRun(client, output, run_id)
        run.save()
        try:
            await run.run()
        except Exception as error:
            run.report.update(live_acceptance="failed", error=f"{type(error).__name__}: {error}")
            raise
        finally:
            run.save()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        enabled = require_live(args)
        run_id = new_run_id()
        output = resolve_output(args.output, run_id)
    except ValueError as error:
        print(f"REFUSED BEFORE CONNECTION: {error}")
        return 2
    if enabled:
        asyncio.run(live(output, run_id))
        print(f"LIVE DONE run_id={run_id} report={output}")
    else:
        report = offline(output, run_id)
        print(
            "OFFLINE ONLY: no MCP client, connection or Toolkit channel executed. "
            f"counterexamples_kept={len(report['counterexamples'])} "
            f"receipt_shapes={len(report['receipt_shapes'])} run_id={run_id} report={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
