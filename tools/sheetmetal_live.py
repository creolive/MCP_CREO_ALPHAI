"""Shared live harness for the DEV-051 sheetmetal acceptance drivers.

T03 (BUG-032), T04 (BUG-046) and T11 (FEAT-014) each keep their own offline
driver; this module only carries what a live run needs and what all three must
record identically: the MCP call wrapper, the terminal polling rule, the saved
snapshot reader, the failure extractor and the report writer.

Offline safety: the MCP client is created by the caller, never here, and
nothing in this module touches Creo unless a runner method is awaited. A live
run never launches, restarts or closes Creo, never clears a protection, never
retries and never resubmits an accepted job. A busy channel, an unknown
terminal state or an exhausted polling budget raises LiveStop, which the
drivers record and then propagate so no further submission is made.

Every case uses a fresh model name; the report is written under
build/<kind>/<run_id>/report.json and is never overwritten.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{0,30}$")
TERMINAL_STATUSES = ("succeeded", "failed")
OPEN_STATUSES = ("queued", "running")
READY_STATES = (
    "checking",
    "building_worker",
    "starting",
    "waiting_for_channel",
    "waiting_for_connection",
)


class LiveStop(RuntimeError):
    """A state that forbids any further submission in this session."""


def require_manual_start(config_file: Path) -> None:
    """Refuse to run unless the user opened Creo manually."""
    settings = json.loads(config_file.read_text(encoding="utf-8-sig"))
    if settings.get("auto_start_creo") is not False:
        raise ValueError(
            "Live acceptance requires config.json auto_start_creo=false; no client was started"
        )


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(kind: str, run_id: str, output: Path | None) -> Path:
    """Refuse to overwrite an existing report before any connection is made."""
    path = Path(output) if output is not None else ROOT / "build" / kind / run_id / "report.json"
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def unique_name(tag: str) -> str:
    """A fresh Creo model name: 1-31 chars, lowercase letters/digits/underscore.

    Long descriptive tags are shortened so the random suffix still fits the
    31-character rule; the suffix alone keeps the name unique per run.
    """
    suffix = "_" + uuid.uuid4().hex[:6]
    name = f"{tag[: 31 - len(suffix)]}{suffix}"
    if not NAME_PATTERN.match(name):
        raise ValueError(f"Model name {name!r} violates the 31-character name rule")
    return name


def failure_text(terminal: dict) -> dict:
    """Preserve the raw failure evidence a failed job returned."""
    result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
    operations = []
    for operation in result.get("operations") or []:
        if not isinstance(operation, dict):
            continue
        operations.append(
            {
                key: operation.get(key)
                for key in (
                    "index",
                    "label",
                    "execution_status",
                    "effect_status",
                    "error",
                    "message",
                    "toolkit_code",
                )
                if operation.get(key) is not None
            }
        )
    return {
        "job_status": terminal.get("status"),
        "message": terminal.get("message"),
        "toolkit_code": result.get("toolkit_code"),
        "rollback_succeeded": result.get("rollback_succeeded"),
        "failed_stage": result.get("failed_stage"),
        "failed_toolkit_call": result.get("failed_toolkit_call"),
        "operations": operations,
        "native_log_tail": (terminal.get("native_log_tail") or "")[-1500:],
    }


class LiveRunner:
    """Serial MCP runner for one acceptance task; one instance per run."""

    def __init__(self, client: Any, output: Path, task: str, scope: str, run_id: str) -> None:
        self.client = client
        self.output = output
        self.run_id = run_id
        self.submitted: set[str] = set()
        self.report: dict[str, Any] = {
            "task": task,
            "scope": scope,
            "run_id": run_id,
            "mode": "live",
            "started_at": time.time(),
            "creo": {},
            "cases": [],
            "calls": [],
            "stopped": None,
            "environment": {
                "auto_start_creo": False,
                "human_session_confirmation": True,
                "launches_or_restarts_creo": False,
                "resubmits_accepted_jobs": False,
            },
        }

    # --- reporting ------------------------------------------------------
    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def finish(self) -> dict:
        self.report["finished_at"] = time.time()
        self.report["passed"] = all(case.get("passed") is True for case in self.report["cases"])
        self.save()
        digest = hashlib.sha256(self.output.read_bytes()).hexdigest()
        self.output.with_name("report.sha256").write_text(
            f"{digest}  {self.output.name}\n", encoding="utf-8"
        )
        return {"report": str(self.output), "report_sha256": digest}

    def case(self, entry: dict) -> dict:
        self.report["cases"].append(entry)
        self.save()
        return entry

    # --- MCP plumbing ---------------------------------------------------
    async def probe(self, tool: str, arguments: dict) -> dict:
        """One call, keeping both the structured payload and the text error."""
        result = await self.client.call_tool(tool, arguments)
        structured = result.structured_content
        text = "\n".join(str(getattr(item, "text", "") or "") for item in (result.content or []))
        self.report["calls"].append(
            {
                "tool": tool,
                "arguments": arguments,
                "is_error": bool(result.is_error),
                "status": structured.get("status") if isinstance(structured, dict) else None,
                "at": round(time.time(), 3),
            }
        )
        self.save()
        return {
            "is_error": bool(result.is_error),
            "structured": structured if isinstance(structured, dict) else None,
            "text": text,
        }

    async def call(self, tool: str, arguments: dict) -> dict:
        answer = await self.probe(tool, arguments)
        if answer["is_error"]:
            body = answer["structured"] or {}
            detail = json.dumps(body, ensure_ascii=False) if body else answer["text"]
            if body.get("status") == "busy":
                raise LiveStop(f"{tool} refused: toolkit channel busy {detail[:800]}")
            raise LiveStop(f"{tool} failed: {detail[:800]}")
        if answer["structured"] is None:
            raise LiveStop(f"{tool} returned no structured payload: {answer['text'][:400]}")
        return answer["structured"]

    async def start(self, budget: float = 300.0) -> dict:
        """Wait for the manually opened session; never launches Creo."""
        deadline = time.monotonic() + budget
        while True:
            status = await self.call("creo_startup_status", {})
            state = status.get("state")
            if state == "ready" and status.get("connected") is True:
                self.report["creo"]["startup"] = status
                session = await self.call("creo_session_status", {})
                self.report["creo"]["session"] = {
                    key: session.get(key)
                    for key in ("connected", "server_version", "session_health")
                }
                self.report["creo"]["session_health_status"] = (
                    session.get("session_health") or {}
                ).get("status")
                self.save()
                if session.get("connected") is not True:
                    raise LiveStop(f"Session not connected: {session}")
                return status
            if state not in READY_STATES:
                raise LiveStop(f"Toolkit is not ready; nothing submitted: {status}")
            if time.monotonic() >= deadline:
                raise LiveStop("Readiness budget exhausted; nothing submitted")
            await asyncio.sleep(1)

    async def submit(self, case_key: str, tool: str, arguments: dict) -> dict:
        """Submit a case exactly once; a repeated key is a driver bug."""
        if case_key in self.submitted:
            raise RuntimeError(f"Case {case_key} was already submitted; never resubmit")
        self.submitted.add(case_key)
        return await self.call(tool, arguments)

    async def wait_job(self, job_id: str, budget: float = 420.0) -> dict:
        """Poll one accepted job to succeeded/failed. Never resubmits."""
        deadline = time.monotonic() + budget
        while True:
            terminal = await self.call("creo_get_job", {"job_id": job_id})
            status = terminal.get("status")
            if status in TERMINAL_STATUSES:
                return terminal
            if status not in OPEN_STATUSES:
                raise LiveStop(f"Job {job_id} reached {status!r}; scene preserved, do not resubmit")
            if time.monotonic() >= deadline:
                raise LiveStop(f"Job {job_id} still {status} after {budget:.0f}s; do not resubmit")
            await asyncio.sleep(1)

    async def snapshot(self, model_id: str) -> dict:
        """The complete saved snapshot: inspection sections plus aliases."""
        from creo_mechdog.query_client import read_full_model

        return await read_full_model(self.call, model_id)

    # --- readers --------------------------------------------------------
    @staticmethod
    def inspection(snapshot: dict) -> dict:
        value = snapshot.get("inspection")
        return value if isinstance(value, dict) else {}

    @classmethod
    def volume(cls, snapshot: dict) -> float | None:
        return cls.inspection(snapshot).get("volume_mm3")

    @staticmethod
    def aliases(snapshot: dict) -> dict:
        value = snapshot.get("aliases")
        return value if isinstance(value, dict) else {}

    @classmethod
    def feature_types(cls, snapshot: dict) -> dict:
        counts: dict[str, int] = {}
        for feature in cls.inspection(snapshot).get("features") or []:
            name = str(feature.get("type_name") or "other")
            counts[name] = counts.get(name, 0) + 1
        return counts

    @classmethod
    def record(cls, snapshot: dict, label: str) -> dict:
        value = cls.aliases(snapshot).get(label)
        return value if isinstance(value, dict) else {}
