"""DEV-047 T06 multi-contour native acceptance. Default is strictly offline.

Only --live --confirm-session-usable starts an MCP client. The second flag
attests that the operator has completed BUG-001 session recovery checks. The
driver never launches or stops Creo, clears protection, submits startup/retry
commands, or resubmits a busy or failed job.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402
from tools import t06_fixtures as fixtures  # noqa: E402

ROOT = SOURCE_PATHS.resource_root
TOL = 1e-5
BASE_WIDTH, BASE_HEIGHT, BASE_DEPTH = 120.0, 80.0, 10.0


def near(actual: Any, expected: Any, tolerance: float = TOL) -> None:
    if isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected), (actual, expected)
        for a, b in zip(actual, expected, strict=True):
            near(a, b, tolerance)
    else:
        assert math.isfinite(actual), actual
        assert abs(actual - expected) <= max(tolerance, abs(expected) * 1e-6), (actual, expected)


def sketch(label: str = "profile", entities: list[dict] | None = None) -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": "XY",
        "entities": entities,
        "dimensioning": "coordinates",
    }


def extrude(label: str, profile: str = "profile", **kwargs: Any) -> dict:
    return {
        "op": "extrude",
        "label": label,
        "sketch": profile,
        "depth": fixtures.DEPTH_MM,
        **kwargs,
    }


def base_plate() -> list[dict]:
    return [
        sketch(
            "base_profile",
            [
                {
                    "type": "rectangle",
                    "name": "plate",
                    "min": [-BASE_WIDTH / 2, -BASE_HEIGHT / 2],
                    "max": [BASE_WIDTH / 2, BASE_HEIGHT / 2],
                }
            ],
        ),
        extrude("base", "base_profile", depth=BASE_DEPTH),
    ]


def shifted(entities: list[dict], dx: float, dy: float) -> list[dict]:
    """Translate fixture entities; the illegal-case inputs are only rejected, never run."""
    result = []
    for entity in entities:
        item = copy.deepcopy(entity)
        if "center" in item:
            item["center"] = [item["center"][0] + dx, item["center"][1] + dy]
        for key in ("start", "end"):
            if key in item:
                item[key] = [item[key][0] + dx, item[key][1] + dy]
        result.append(item)
    return result


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


def local_provenance() -> dict:
    """Record source evidence without recording config, license or session IDs."""
    from version import VERSION

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

    names = set(
        git("ls-files", "--", "*.py", "native/*.h", "native/*.hpp", "native/*.cpp").splitlines()
    )
    names.update(
        (
            "tools/test_t06_native.py",
            "tools/t06_fixtures.py",
            "tests/unit/test_t06_multi_contours.py",
            "src/creo_mechdog/profile_diagnostics.py",
        )
    )
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in sorted(names)
    }
    return {
        "version": VERSION,
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "dirty": bool(git("status", "--porcelain")),
        "source_sha256": hashes,
        "source_fingerprint": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "auto_start_creo": False,
        "human_session_confirmation": True,
    }


class Acceptance:
    def __init__(self, client: Any, output: Path) -> None:
        self.client = client
        self.output = output
        self.report: dict = {
            "task": "DEV-047 T06",
            "fixture_dimensioning": "coordinates",
            "started_at": time.time(),
            "calls": [],
            "cases": [],
            "admission_rejections": [],
            "failure_recovery": [],
            "native_acceptance": "running",
            "toolkit_serial": True,
            "provenance": local_provenance(),
        }

    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def call(self, name: str, args: dict, *, allow_error: bool = False) -> Any:
        record = {
            "tool": name,
            "args": copy.deepcopy(args),
            "started_at": time.time(),
            "response_received": False,
            "outcome": "unknown",
            "call_state": "awaiting_response",
        }
        self.report["calls"].append(record)
        self.save()
        try:
            result = await self.client.call_tool(name, args)
        except Exception as error:
            record.update(
                call_state="client_exception",
                finished_at=time.time(),
                client_exception={"type": type(error).__name__, "message": str(error)},
            )
            self.save()
            raise
        record.update(
            response_received=True,
            outcome="response_received",
            call_state="returned",
            finished_at=time.time(),
            is_error=result.is_error,
            result=result.structured_content,
            content=str(result.content),
        )
        self.save()
        if result.is_error and not allow_error:
            raise RuntimeError(f"{name}: {result.content}")
        return result if allow_error else result.structured_content

    async def expect_rejection(self, operations: list[dict], category: str | None) -> str:
        result = await self.call("creo_execute_plan", {"operations": operations}, allow_error=True)
        record = {
            "operations": copy.deepcopy(operations),
            "is_error": result.is_error,
            "content": str(result.content),
            "category": category,
            "returned_at": time.time(),
        }
        self.report["admission_rejections"].append(record)
        self.save()
        assert result.is_error, record
        message = str(result.content)
        if category:
            assert category in message, message
        assert "operations[" in message, message
        return message

    async def snapshot(self, model_id: str) -> dict:
        from creo_mechdog.query_client import read_full_model

        return await read_full_model(self.call, model_id)

    async def wait_ready(self, budget: float = 180) -> None:
        deadline = time.monotonic() + budget
        while True:
            status = await self.call("creo_startup_status", {})
            if status.get("state") == "ready" and status.get("connected") is True:
                return
            if status.get("state") not in {
                "checking",
                "building_worker",
                "starting",
                "waiting_for_connection",
            }:
                raise RuntimeError(
                    f"Existing session is not ready; no modeling submitted: {status}"
                )
            if time.monotonic() >= deadline:
                raise TimeoutError("Startup observation budget exceeded; no modeling submitted")
            await asyncio.sleep(1)

    async def plan(
        self, operations: list, previous: dict | None = None, success: bool = True
    ) -> dict:
        args = {"operations": operations}
        if previous:
            args.update(model_id=previous["model_id"], expected_revision=previous["revision"])
        accepted = await self.call("creo_execute_plan", args)
        deadline = time.monotonic() + 360
        while time.monotonic() < deadline:
            terminal = await self.call("creo_get_job", {"job_id": accepted["job_id"]})
            if terminal["status"] not in ("queued", "running"):
                break
            await asyncio.sleep(1)
        else:
            raise TimeoutError(accepted["job_id"])
        assert terminal["status"] == ("succeeded" if success else "failed"), terminal
        if success:
            assert terminal["result"]["saved_file_reloaded_and_verified"] is True, terminal
        else:
            assert terminal["result"]["rollback_succeeded"] is True, terminal
        return terminal

    @staticmethod
    def features(snapshot: dict) -> list[dict]:
        return snapshot["inspection"]["features"]

    @classmethod
    def feature_delta(cls, before: dict, after: dict) -> dict[str, int]:
        def counts(snapshot: dict) -> dict[str, int]:
            result: dict[str, int] = {}
            for feature in cls.features(snapshot):
                name = feature.get("type_name", "other")
                result[name] = result.get(name, 0) + 1
            return result

        old, new = counts(before), counts(after)
        return {name: new.get(name, 0) - old.get(name, 0) for name in set(old) | set(new)}

    def check_volume(self, snapshot: dict, expected: float) -> None:
        inspection = snapshot["inspection"]
        assert inspection["length_unit"]["name"] == "mm", inspection["length_unit"]
        assert inspection["volume_query_code"] == 0, inspection
        near(inspection["volume_mm3"], expected, max(TOL, expected * 1e-6))

    def check_sketch_diagnostics(
        self, terminal: dict, case: dict, operation_index: int = 0
    ) -> None:
        operation = terminal["result"]["operations"][operation_index]
        profile = operation["profile"]
        assert profile["source"] == "input" and profile["analysis"] == "complete", profile
        assert profile["closed_contour_count"] == case["expected_contour_count"], profile
        assert profile["entity_count"] == case["expected_entity_count"], profile
        near(
            profile["material_area_mm2"],
            case["expected_area_mm2"],
            max(TOL, case["expected_area_mm2"] * 1e-6),
        )
        section = operation["native_section"]
        assert section["available"], section
        assert section["closed_contours"] == case["expected_contour_count"], section
        assert section["contours"] == case["expected_contour_count"], section
        assert section["entities"] == case["expected_entity_count"], section
        assert section["open_ends"] == 0, section

    async def add_case(self, case: dict) -> None:
        # Sketch and extrusion are separate jobs so the solved native section is
        # recorded before the feature-creation stage under test.
        sketch_job = await self.plan([sketch("profile", case["entities"])])
        sketch_snapshot = await self.snapshot(sketch_job["model_id"])
        self.check_sketch_diagnostics(sketch_job, case)
        result = await self.plan([extrude("solid")], sketch_job)
        snapshot = await self.snapshot(result["model_id"])
        self.check_volume(snapshot, case["expected_area_mm2"] * case["depth"])
        delta = self.feature_delta(sketch_snapshot, snapshot)
        assert delta.get("protrusion") == 1, delta
        assert delta.get("cut", 0) == 0, delta
        self.report["cases"].append(
            {
                "case": "add",
                "fixture": case["name"],
                "expected_volume_mm3": case["expected_area_mm2"] * case["depth"],
                "actual_volume_mm3": snapshot["inspection"]["volume_mm3"],
                "feature_delta": delta,
                "sketch_job_id": sketch_job["job_id"],
                "job_id": result["job_id"],
                "model_id": result["model_id"],
                "saved_file_reloaded_and_verified": True,
                "passed": True,
            }
        )
        self.save()

    async def cut_case(self, case: dict) -> None:
        base = await self.plan(base_plate())
        base_snapshot = await self.snapshot(base["model_id"])
        self.check_volume(base_snapshot, BASE_WIDTH * BASE_HEIGHT * BASE_DEPTH)
        sketch_job = await self.plan([sketch("cut_profile", case["entities"])], base)
        self.check_sketch_diagnostics(sketch_job, case)
        before = await self.snapshot(sketch_job["model_id"])
        result = await self.plan(
            [
                extrude(
                    "cut",
                    "cut_profile",
                    mode="cut",
                    depth_type="through_all",
                )
            ],
            sketch_job,
        )
        after = await self.snapshot(result["model_id"])
        expected = BASE_WIDTH * BASE_HEIGHT * BASE_DEPTH - case["expected_area_mm2"] * BASE_DEPTH
        self.check_volume(after, expected)
        delta = self.feature_delta(before, after)
        assert delta.get("cut") == 1, delta
        assert delta.get("protrusion", 0) == 0, delta
        self.report["cases"].append(
            {
                "case": "cut",
                "fixture": case["name"],
                "expected_volume_mm3": expected,
                "actual_volume_mm3": after["inspection"]["volume_mm3"],
                "feature_delta": delta,
                "sketch_job_id": sketch_job["job_id"],
                "job_id": result["job_id"],
                "model_id": result["model_id"],
                "saved_file_reloaded_and_verified": True,
                "passed": True,
            }
        )
        self.save()

    async def rejection_cases(self) -> None:
        for name, factory in fixtures.INVALID.items():
            await self.expect_rejection(
                [sketch("rejected", factory()), extrude("rejected_solid")], name
            )
        await self.expect_rejection(
            [sketch("open", fixtures.open_chain()), extrude("open_solid")], "open"
        )

    async def failure_then_legal(self) -> None:
        base = await self.plan(base_plate())
        before = await self.snapshot(base["model_id"])
        # A cut far outside the plate creates no material change: the native
        # path fails after feature creation and the job must roll back.
        far = shifted(fixtures.separated(5, "circle")["entities"], 5000.0, 5000.0)
        failed = await self.plan(
            [
                sketch("miss", far),
                extrude("miss_cut", "miss", mode="cut", depth_type="through_all"),
            ],
            base,
            success=False,
        )
        restored = await self.snapshot(base["model_id"])
        assert restored["revision"] == before["revision"], (failed, restored["revision"])
        assert restored["aliases"] == before["aliases"], restored["aliases"]
        self.check_volume(restored, BASE_WIDTH * BASE_HEIGHT * BASE_DEPTH)
        legal = fixtures.separated(2, "circle")
        result = await self.plan(
            [
                sketch("recover", legal["entities"]),
                extrude("recover_cut", "recover", mode="cut", depth_type="through_all"),
            ],
            base,
        )
        after = await self.snapshot(result["model_id"])
        self.check_volume(
            after, BASE_WIDTH * BASE_HEIGHT * BASE_DEPTH - legal["expected_area_mm2"] * BASE_DEPTH
        )
        self.check_sketch_diagnostics(result, legal)
        self.report["failure_recovery"].append(
            {
                "failed_job_id": failed["job_id"],
                "failure_message": failed["result"].get("message"),
                "failed_sketch_native_section": (
                    failed["result"]["operations"][0].get("native_section")
                    if failed["result"].get("operations")
                    else None
                ),
                "rollback_succeeded": True,
                "revision_before": before["revision"],
                "revision_after_failure": restored["revision"],
                "legal_job_id": result["job_id"],
                "legal_volume_mm3": after["inspection"]["volume_mm3"],
                "passed": True,
            }
        )
        self.save()

    async def run(self) -> None:
        self.report["cases"] = []
        for case in fixtures.legal_cases():
            await self.add_case(case)
        for case in (fixtures.separated(2, "circle"), fixtures.mixed()):
            await self.cut_case(case)
        await self.rejection_cases()
        await self.failure_then_legal()
        self.report.update(
            native_acceptance="passed",
            scope="independent_fixtures",
            external_case_replay="not_applicable_missing_attachments",
            geometry_matrix="passed",
            admission_matrix="passed",
            pending_native_acceptance=[],
        )


async def live(output: Path) -> None:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=60,
    ) as client:
        acceptance = Acceptance(client, output)
        acceptance.save()
        try:
            acceptance.report["capabilities"] = await acceptance.call("creo_capabilities", {})
            acceptance.report["environment"] = await acceptance.call("creo_check_environment", {})
            await acceptance.wait_ready()
            status = await acceptance.call("creo_session_status", {})
            assert status["connected"], status
            await acceptance.run()
        except Exception as error:
            acceptance.report.update(
                native_acceptance="failed", error=f"{type(error).__name__}: {error}"
            )
            raise
        finally:
            acceptance.save()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/t06_native_acceptance.json")
    args = parser.parse_args(argv)
    try:
        enabled = require_live(args)
    except ValueError as error:
        parser.error(str(error))
    if enabled:
        asyncio.run(live(args.output))
    else:
        print(
            "OFFLINE ONLY: no MCP client, connection or native acceptance executed; use both "
            "explicit live flags after human session confirmation."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
