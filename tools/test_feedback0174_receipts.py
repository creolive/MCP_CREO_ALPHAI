"""DEV-074/H12: live re-verification of the 0.17.4 receipt fields on MCP.

The 0.17.4 feedback added structured receipts (failed-resize identity fields,
source-aware gauge validation, empty-preview basis, structured nearest-edge
candidates, stale startup snapshots) and the BUG-115 same-plan admission. This
driver replays each one through the public MCP tools only and records the raw
payload it observed.

Discipline: one connection, one submission per case, no resubmission, no Creo
launch/close, no protection clearing, no fault injection. A busy channel, an
unknown terminal state or a readiness budget that expires stops the run and is
reported as such; nothing is retried.

Example (PowerShell, from the repo root):
.venv\\Scripts\\python.exe tools\\test_feedback0174_receipts.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TERMINAL = ("succeeded", "failed", "unknown_outcome")
OPEN = ("queued", "running", "waiting_for_channel", "building_worker", "executing_feature_plan")
READY_STATES = (
    "checking",
    "building_worker",
    "starting",
    "waiting_for_channel",
    "waiting_for_connection",
)


class LiveStop(RuntimeError):
    """A state that forbids further submission in this run."""


def run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{int(time.time() * 1000) % 1000:03d}"


def unique_name(tag: str) -> str:
    suffix = f"_{int(time.time() * 1000) % 100000:05d}"
    return f"{tag[: 31 - len(suffix)]}{suffix}"


async def call(client, tool: str, arguments: dict) -> dict:
    """One MCP call; keeps both the structured payload and the error text."""
    result = await client.call_tool(tool, arguments)
    structured = result.structured_content
    text = "\n".join(str(getattr(item, "text", "") or "") for item in (result.content or []))
    return {
        "is_error": bool(result.is_error),
        "structured": structured if isinstance(structured, dict) else None,
        "text": text,
    }


class Driver:
    def __init__(self, client) -> None:
        self.client = client
        self.report: dict[str, Any] = {
            "run_id": run_id(),
            "mode": "live",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "calls": [],
            "cases": {},
            "checks": [],
            "jobs": [],
            "models": {},
            "stopped": None,
        }
        self.output = ROOT / "build" / "h12_receipts" / self.report["run_id"] / "report.json"

    # -- reporting -------------------------------------------------------
    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def check(self, name: str, ok: bool, detail: Any = None) -> None:
        self.report["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        self.save()

    def record(self, case: str, value: Any) -> None:
        self.report["cases"].setdefault(case, {})
        if isinstance(value, dict):
            self.report["cases"][case].update(value)
        else:
            self.report["cases"][case] = value
        self.save()

    # -- plumbing --------------------------------------------------------
    async def probe(self, tool: str, arguments: dict) -> dict:
        answer = await call(self.client, tool, arguments)
        self.report["calls"].append(
            {
                "tool": tool,
                "arguments": arguments,
                "is_error": answer["is_error"],
                "status": (answer["structured"] or {}).get("status"),
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.save()
        return answer

    async def must(self, tool: str, arguments: dict) -> dict:
        answer = await self.probe(tool, arguments)
        if answer["is_error"]:
            body = answer["structured"] or {}
            if body.get("status") == "busy":
                raise LiveStop(f"{tool} refused: channel busy {json.dumps(body)[:600]}")
            raise LiveStop(f"{tool} failed: {(answer['text'] or json.dumps(body))[:600]}")
        if answer["structured"] is None:
            raise LiveStop(f"{tool} returned no structured payload: {answer['text'][:300]}")
        return answer["structured"]

    async def wait_ready(self, budget: float = 900.0) -> dict:
        deadline = time.monotonic() + budget
        while True:
            status = await self.must("creo_startup_status", {})
            state = status.get("state")
            if state == "ready" and status.get("connected") is True:
                return status
            if state not in READY_STATES and state != "ready":
                raise LiveStop(f"Toolkit not ready; nothing submitted: {json.dumps(status)[:800]}")
            if time.monotonic() >= deadline:
                raise LiveStop("Readiness budget exhausted; nothing submitted")
            await asyncio.sleep(2)

    async def wait_job(self, job_id: str, detail: str = "compact", budget: float = 600.0) -> dict:
        deadline = time.monotonic() + budget
        while True:
            state = await self.must("creo_get_job", {"job_id": job_id, "detail": detail})
            status = state.get("status")
            if status in TERMINAL:
                return state
            if status not in OPEN:
                raise LiveStop(f"job {job_id} reached {status!r}; do not resubmit")
            if time.monotonic() >= deadline:
                raise LiveStop(f"job {job_id} still {status} after {budget:.0f}s; do not resubmit")
            await asyncio.sleep(2)

    async def submit(self, tool: str, arguments: dict) -> dict:
        """Submit once and return both the queued answer and the terminal state."""
        queued = await self.probe(tool, arguments)
        if queued["is_error"] or not (queued["structured"] or {}).get("job_id"):
            return {"queued": queued, "terminal": None}
        job_id = queued["structured"]["job_id"]
        self.report["jobs"].append(job_id)
        self.save()
        terminal = await self.wait_job(job_id)
        return {"queued": queued["structured"], "terminal": terminal}

    async def models(self) -> dict[str, dict]:
        page = await self.must("creo_list_models", {"limit": 50, "detail": "compact"})
        return {item["model_id"]: item for item in page.get("models") or []}

    async def revision(self, model_id: str) -> Any:
        return (await self.models()).get(model_id, {}).get("revision")

    # -- cases -----------------------------------------------------------
    async def case_startup_snapshot(self) -> None:
        status = await self.must("creo_startup_status", {})
        self.record("startup_snapshot", {"first": status})
        # READY_FRESHNESS_SECONDS is 30: wait past it and re-read the same
        # snapshot without retrying, so the stale branch is observable.
        await asyncio.sleep(32)
        later = await self.must("creo_startup_status", {})
        self.record("startup_snapshot", {"after_freshness_window": later})
        self.check("startup:ready_when_fresh", status.get("state") == "ready")
        self.check("startup:stale_after_window", later.get("stale") is True, later.get("stale"))
        self.check(
            "startup:stale_declares_unverified",
            later.get("connection_verification") == "unverified_stale_snapshot"
            and later.get("current_connected") is None,
            {
                "connection_verification": later.get("connection_verification"),
                "current_connected": later.get("current_connected"),
                "state": later.get("state"),
                "connected": later.get("connected"),
            },
        )

    async def case_empty_preview(self, model_id: str, job: dict, label: str) -> None:
        result = (job.get("terminal") or {}).get("result") or {}
        block = result.get("preview") or {}
        basis = block.get("empty_geometry_basis")
        record = {
            "model_id": model_id,
            "job_id": (job.get("terminal") or {}).get("job_id"),
            "preview": block,
        }
        self.record(label, record)
        self.check(f"{label}:status_skipped", block.get("status") == "skipped_no_geometry", block)
        self.check(f"{label}:basis_present", isinstance(basis, dict), basis)
        self.check(
            f"{label}:basis_counts_empty",
            isinstance(basis, dict) and basis.get("non_datum_feature_count") == 0,
            basis,
        )
        self.check(
            f"{label}:no_bytes_or_step",
            block.get("bytes") is None
            and block.get("failed_step") is None
            and block.get("file_verified") is False
            and block.get("path") is None,
            {
                key: block.get(key)
                for key in ("bytes", "failed_step", "file_verified", "path", "failed_code")
            },
        )
        self.check(
            f"{label}:no_raster_codes",
            all(value is None for value in (block.get("codes") or {}).values()),
            block.get("codes"),
        )

    async def case_bug115(self, model_id: str, revision: int) -> None:
        chain = [
            {
                "op": "sketch",
                "label": "h12_chain_profile",
                "plane": "XY",
                "entities": [
                    {"type": "rectangle", "name": "rect", "min": [0.0, 0.0], "max": [40.0, 20.0]}
                ],
            },
            {"op": "surface_fill", "label": "h12_chain_base", "sketch": "h12_chain_profile"},
            {
                "op": "datum_plane",
                "label": "h12_chain_cut",
                "reference": {"kind": "datum_plane", "axis": "x", "offset": 0},
                "offset": 5.0,
            },
            {
                "op": "surface_trim",
                "label": "h12_chain_trim",
                "target": {"kind": "quilt_feature", "label": "h12_chain_base"},
                "tool": {"kind": "datum_plane", "label": "h12_chain_cut"},
                "keep_side": "one",
            },
            {
                "op": "thicken",
                "label": "h12_chain_solid",
                "reference": {"kind": "quilt_feature", "label": "h12_chain_trim"},
                "thickness": 2.0,
                "side": "symmetric",
            },
        ]
        before = await self.models()
        answer = await self.probe(
            "creo_execute_plan",
            {"operations": chain, "model_id": model_id, "expected_revision": revision},
        )
        after = await self.models()
        structured = answer["structured"] or {}
        self.record(
            "bug115_refusal",
            {
                "is_error": answer["is_error"],
                "has_job_id": bool(structured.get("job_id")),
                "message": answer["text"] or json.dumps(structured, ensure_ascii=False),
                "model_baseline": {
                    "before": before.get(model_id),
                    "after": after.get(model_id),
                },
            },
        )
        message = answer["text"] or ""
        self.check("bug115:refused", answer["is_error"] is True)
        self.check("bug115:no_job_id", not structured.get("job_id"), structured.get("job_id"))
        self.check("bug115:names_bug", "BUG-115" in message, message[:400])
        self.check(
            "bug115:alternative_present",
            "second plan" in message and "explicit" in message,
            message[:600],
        )
        self.check(
            "bug115:no_model_side_effect",
            before.get(model_id, {}).get("revision") == after.get(model_id, {}).get("revision")
            and before.get(model_id, {}).get("part_sha256")
            == after.get(model_id, {}).get("part_sha256"),
            {
                "before_revision": before.get(model_id, {}).get("revision"),
                "after_revision": after.get(model_id, {}).get("revision"),
            },
        )
        # The allowed fill -> thicken combination must still be accepted.
        allowed = [
            {
                "op": "sketch",
                "label": "h12_fill_profile",
                "plane": "XY",
                "entities": [
                    {"type": "rectangle", "name": "rect", "min": [0.0, 0.0], "max": [60.0, 40.0]}
                ],
            },
            {"op": "surface_fill", "label": "h12_fill_base", "sketch": "h12_fill_profile"},
            {
                "op": "thicken",
                "label": "h12_fill_solid",
                "reference": {"kind": "quilt_feature", "label": "h12_fill_base"},
                "thickness": 2.0,
                "side": "symmetric",
            },
        ]
        revision_now = await self.revision(model_id)
        job = await self.submit(
            "creo_execute_plan",
            {
                "operations": allowed,
                "model_id": model_id,
                "expected_revision": revision_now,
                "assertions": {"require_solid": True},
            },
        )
        terminal = job.get("terminal") or {}
        result = terminal.get("result") or {}
        # A generic plan reports the measured volume on the inspection summary,
        # not as a top-level result field.
        volume = result.get("volume_mm3")
        if not isinstance(volume, (int, float)):
            volume = (result.get("inspection") or {}).get("volume_mm3")
        if not isinstance(volume, (int, float)):
            volume = (result.get("inspection_summary") or {}).get("volume_mm3")
        self.record(
            "bug115_allowed_fill_thicken",
            {
                "job_id": terminal.get("job_id"),
                "status": terminal.get("status"),
                "revision": terminal.get("revision"),
                "saved_file_reloaded_and_verified": result.get("saved_file_reloaded_and_verified"),
                "volume_mm3": volume,
                "has_solid": (result.get("inspection") or {}).get("has_solid"),
                "message": terminal.get("message"),
            },
        )
        self.check(
            "bug115:allowed_combination_succeeds",
            terminal.get("status") == "succeeded"
            and result.get("saved_file_reloaded_and_verified") is True,
            {
                "status": terminal.get("status"),
                "message": terminal.get("message"),
                "saved": result.get("saved_file_reloaded_and_verified"),
            },
        )
        self.check(
            "bug115:allowed_volume",
            isinstance(volume, (int, float)) and abs(float(volume) - 60.0 * 40.0 * 2.0) <= 0.01,
            volume,
        )

    async def case_planar_wall(self, model_id: str, revision: int) -> tuple[str | None, Any]:
        plan = [
            {
                "op": "sheetmetal_planar_wall",
                "label": "h12_wall",
                "plane": "XY",
                "length": 100.0,
                "width": 60.0,
                "thickness": 1.0,
                "direction": "positive",
                "origin": [0.0, 0.0],
            }
        ]
        job = await self.submit(
            "creo_execute_plan",
            {"operations": plan, "model_id": model_id, "expected_revision": revision},
        )
        terminal = job.get("terminal") or {}
        result = terminal.get("result") or {}
        projection = result.get("planar_wall") or {}
        self.record(
            "planar_wall_create",
            {
                "job_id": terminal.get("job_id"),
                "status": terminal.get("status"),
                "revision": terminal.get("revision"),
                "saved_file_reloaded_and_verified": result.get("saved_file_reloaded_and_verified"),
                "planar_wall": projection,
                "message": terminal.get("message"),
            },
        )
        self.check(
            "wall:create_succeeds",
            terminal.get("status") == "succeeded" and projection.get("verified") is True,
            {"status": terminal.get("status"), "problems": projection.get("problems")},
        )
        current = projection.get("thickness_validation") or {}
        self.check(
            "wall:create_current_plan_context",
            current.get("context") == "current_plan" and current.get("status") == "verified",
            current,
        )
        self.check(
            "wall:create_effective_true",
            projection.get("thickness_verified_effective") is True,
            {
                "thickness_verified_effective": projection.get("thickness_verified_effective"),
                "thickness_api_scope": projection.get("thickness_api_scope"),
                "thickness_api_reason": projection.get("thickness_api_reason"),
                "thickness_fallback_source": projection.get("thickness_fallback_source"),
            },
        )
        return terminal.get("job_id"), terminal.get("revision")

    async def case_resize(self, model_id: str, revision: Any) -> Any:
        job = await self.submit(
            "creo_execute_plan",
            {
                "operations": [
                    {
                        "op": "resize_sheetmetal_planar_wall",
                        "feature": "h12_wall",
                        "length": 120.0,
                        "width": 80.0,
                    }
                ],
                "model_id": model_id,
                "expected_revision": revision,
            },
        )
        terminal = job.get("terminal") or {}
        result = terminal.get("result") or {}
        projection = result.get("planar_wall") or {}
        compact = await self.must(
            "creo_get_job", {"job_id": terminal.get("job_id"), "detail": "compact"}
        )
        compact_projection = (compact.get("result") or {}).get("planar_wall") or {}
        self.record(
            "resize_success",
            {
                "job_id": terminal.get("job_id"),
                "status": terminal.get("status"),
                "revision": terminal.get("revision"),
                "saved_file_reloaded_and_verified": result.get("saved_file_reloaded_and_verified"),
                "planar_wall": projection,
                "compact_planar_wall": compact_projection,
            },
        )
        current = projection.get("thickness_validation") or {}
        loaded = projection.get("thickness_loaded_validation") or {}
        self.check(
            "resize:succeeds",
            terminal.get("status") == "succeeded" and projection.get("verified") is True,
            {"status": terminal.get("status"), "problems": projection.get("problems")},
        )
        self.check(
            "resize:feature_identity",
            projection.get("feature_id_unchanged") is True
            and projection.get("feature_id") == projection.get("feature_id_before"),
            {
                "feature_id": projection.get("feature_id"),
                "feature_id_before": projection.get("feature_id_before"),
                "feature_id_unchanged": projection.get("feature_id_unchanged"),
            },
        )
        self.check(
            "resize:two_contexts",
            current.get("context") == "current_plan"
            and loaded.get("context") == "saved_loaded"
            and current.get("status") == "verified"
            and loaded.get("status") == "verified"
            and projection.get("thickness_verified_effective") is True
            and projection.get("thickness_loaded_verified_effective") is True,
            {"current": current, "loaded": loaded},
        )
        self.check(
            "resize:volume",
            isinstance(projection.get("volume_mm3"), (int, float))
            and abs(float(projection["volume_mm3"]) - 120.0 * 80.0 * 1.0) <= 0.01,
            projection.get("volume_mm3"),
        )
        self.check(
            "resize:compact_keeps_block",
            bool(compact_projection)
            and compact_projection.get("thickness_loaded_validation")
            == projection.get("thickness_loaded_validation"),
            {
                "keys": sorted(compact_projection),
                "problems": compact_projection.get("problems"),
            },
        )
        self.check(
            "resize:saved_reloaded",
            result.get("saved_file_reloaded_and_verified") is True,
            result.get("saved_file_reloaded_and_verified"),
        )
        return terminal.get("revision")

    async def case_resize_failure(self, model_id: str, revision: Any) -> Any:
        """A real volume-guard refusal: 0.001 mm cannot survive the sketch solve."""
        attempts = []
        for length, width in ((0.001, 20.0), (120.0, 0.001), (0.0005, 0.0005)):
            current_revision = await self.revision(model_id)
            job = await self.submit(
                "creo_execute_plan",
                {
                    "operations": [
                        {
                            "op": "resize_sheetmetal_planar_wall",
                            "feature": "h12_wall",
                            "length": length,
                            "width": width,
                        }
                    ],
                    "model_id": model_id,
                    "expected_revision": current_revision,
                },
            )
            terminal = job.get("terminal") or {}
            result = terminal.get("result") or {}
            attempts.append(
                {
                    "request": {"length": length, "width": width},
                    "job_id": terminal.get("job_id"),
                    "status": terminal.get("status"),
                    "message": terminal.get("message"),
                    "planar_wall": result.get("planar_wall"),
                    "rollback_succeeded": result.get("rollback_succeeded"),
                    "rollback_status": result.get("rollback_status"),
                    "revision": terminal.get("revision"),
                }
            )
            self.record("resize_failure_attempts", {"attempts": attempts})
            if terminal.get("status") != "succeeded":
                break
        self.check(
            "resize_failure:reproduced",
            attempts[-1].get("status") == "failed",
            {
                "status": attempts[-1].get("status"),
                "message": str(attempts[-1].get("message"))[:400],
                "planar_wall": attempts[-1].get("planar_wall"),
            },
        )
        failed = attempts[-1]
        projection = failed.get("planar_wall") or {}
        self.check(
            "resize_failure:no_contradiction",
            projection.get("feature_id_unchanged") is None
            and projection.get("thickness_loaded_validation") is None
            and projection.get("thickness_loaded_api_scope") is None
            and projection.get("thickness_loaded_verified_effective") is None,
            {
                key: projection.get(key)
                for key in (
                    "feature_id",
                    "feature_id_before",
                    "feature_id_unchanged",
                    "thickness_loaded_mm",
                    "thickness_loaded_validation",
                    "thickness_loaded_api_scope",
                    "thickness_loaded_api_reason",
                    "thickness_loaded_fallback_source",
                    "thickness_loaded_verified_effective",
                    "verified",
                    "problems",
                )
            },
        )
        return await self.revision(model_id)

    async def case_edge_mismatch(self, model_id: str) -> Any:
        revision = await self.revision(model_id)
        job = await self.submit(
            "creo_sheetmetal_flange",
            {
                "model_id": model_id,
                "expected_revision": revision,
                "label": "h12_flange_bad_edge",
                "edge": {
                    "kind": "edge_geometry",
                    "endpoints_mm": [[1000.0, 1000.0, 1000.0], [1001.0, 1001.0, 1001.0]],
                    "tolerance_mm": 1e-6,
                },
                "height": 10.0,
            },
        )
        terminal = job.get("terminal") or {}
        result = terminal.get("result") or {}
        operations = result.get("operations") or []
        diagnostic = (operations[0] if operations else {}).get("edge_geometry_diagnostic") or {}
        compact = await self.must(
            "creo_get_job", {"job_id": terminal.get("job_id"), "detail": "compact"}
        )
        compact_records = (compact.get("result") or {}).get("operations") or []
        compact_diagnostic = (compact_records[0] if compact_records else {}).get(
            "edge_geometry_diagnostic"
        ) or {}
        after = await self.revision(model_id)
        self.record(
            "edge_mismatch",
            {
                "job_id": terminal.get("job_id"),
                "status": terminal.get("status"),
                "message": terminal.get("message"),
                "edge_geometry_diagnostic": diagnostic,
                "compact_edge_geometry_diagnostic": compact_diagnostic,
                "failed_operation_index": result.get("failed_operation_index"),
                "failed_stage": result.get("failed_stage"),
                "failed_toolkit_call": result.get("failed_toolkit_call"),
                "rollback_succeeded": result.get("rollback_succeeded"),
                "rollback_status": result.get("rollback_status"),
                "revision_before": revision,
                "revision_after": after,
            },
        )
        self.check("edge:fails", terminal.get("status") == "failed", terminal.get("message"))
        self.check(
            "edge:diagnostic_shape",
            bool(diagnostic)
            and isinstance(diagnostic.get("nearest_edges"), list)
            and len(diagnostic["nearest_edges"]) == 5
            and diagnostic.get("candidate_limit") == 5
            and isinstance(diagnostic.get("straight_edge_count"), int)
            and isinstance(diagnostic.get("tolerance_mm"), (int, float)),
            {
                "count": len(diagnostic.get("nearest_edges") or []),
                "candidate_limit": diagnostic.get("candidate_limit"),
                "straight_edge_count": diagnostic.get("straight_edge_count"),
                "tolerance_mm": diagnostic.get("tolerance_mm"),
            },
        )
        self.check(
            "edge:compact_keeps_diagnostic",
            compact_diagnostic == diagnostic and bool(compact_diagnostic),
            {"compact": compact_diagnostic, "full": diagnostic},
        )
        self.check(
            "edge:rollback_keeps_revision",
            after == revision and result.get("rollback_succeeded") is True,
            {
                "before": revision,
                "after": after,
                "rollback_succeeded": result.get("rollback_succeeded"),
                "rollback_status": result.get("rollback_status"),
            },
        )
        return after

    async def run(self) -> int:
        started = await self.wait_ready()
        session = await self.must("creo_session_status", {})
        self.report["session"] = {
            key: session.get(key)
            for key in ("connected", "mode", "server_version", "session_health_status")
        }
        self.report["startup"] = {
            key: started.get(key) for key in ("state", "connected", "verified_at", "stale")
        }
        self.save()
        if session.get("connected") is not True:
            raise LiveStop(f"session not connected: {json.dumps(session)[:600]}")

        await self.case_startup_snapshot()

        part_name = unique_name("h12_empty_part")
        part_job = await self.submit("creo_new_part", {"model_name": part_name})
        part_terminal = part_job.get("terminal") or {}
        part_id = part_terminal.get("model_id")
        self.report["models"]["empty_part"] = part_id
        self.save()
        self.check(
            "empty_part:created",
            part_terminal.get("status") == "succeeded" and bool(part_id),
            part_terminal.get("message"),
        )
        await self.case_empty_preview(part_id, part_job, "preview_empty_part")

        await self.case_bug115(part_id, await self.revision(part_id))

        asm_name = unique_name("h12_empty_asm")
        asm_job = await self.submit("creo_new_assembly", {"model_name": asm_name})
        asm_terminal = asm_job.get("terminal") or {}
        asm_id = asm_terminal.get("model_id")
        self.report["models"]["empty_assembly"] = asm_id
        self.save()
        self.check(
            "empty_assembly:created",
            asm_terminal.get("status") == "succeeded" and bool(asm_id),
            asm_terminal.get("message"),
        )
        if asm_id:
            await self.case_empty_preview(asm_id, asm_job, "preview_empty_assembly")

        sheet_name = unique_name("h12_sheet")
        sheet_job = await self.submit(
            "creo_new_sheetmetal", {"model_name": sheet_name, "template": "native_planar"}
        )
        sheet_terminal = sheet_job.get("terminal") or {}
        sheet_id = sheet_terminal.get("model_id")
        self.report["models"]["sheetmetal"] = sheet_id
        self.save()
        self.check(
            "sheetmetal:created",
            sheet_terminal.get("status") == "succeeded" and bool(sheet_id),
            sheet_terminal.get("message"),
        )
        if not sheet_id:
            raise LiveStop("sheetmetal model was not created; wall/resize/flange cases not run")

        _, wall_revision = await self.case_planar_wall(sheet_id, await self.revision(sheet_id))
        resize_revision = await self.case_resize(sheet_id, wall_revision)
        await self.case_resize_failure(sheet_id, resize_revision)
        await self.case_edge_mismatch(sheet_id)
        self.save()
        return 0


def summarize(report: dict) -> str:
    failed = [item for item in report["checks"] if not item["ok"]]
    lines = [
        f"run_id={report['run_id']} checks={len(report['checks'])} failed={len(failed)}",
    ]
    for item in failed:
        lines.append(f"  FAILED {item['name']}: {json.dumps(item['detail'])[:300]}")
    return "\n".join(lines)


async def main(confirm: bool) -> int:
    if not confirm:
        raise SystemExit("Refusing to connect without --confirm-session-usable")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    driver: Driver | None = None
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        driver = Driver(client)
        try:
            await driver.run()
        except LiveStop as exc:
            driver.report["stopped"] = str(exc)
            driver.save()
            print(f"STOPPED: {exc}")
            print(summarize(driver.report))
            return 2
    print(summarize(driver.report))
    print(f"report={driver.output}")
    return 0 if all(item["ok"] for item in driver.report["checks"]) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    args = parser.parse_args()
    if not args.live:
        raise SystemExit("This driver only runs live: pass --live --confirm-session-usable")
    raise SystemExit(asyncio.run(main(args.confirm_session_usable)))
