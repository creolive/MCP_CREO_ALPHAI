"""DEV-047 T12 official example acceptance. Default is strictly offline.

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
from creo_mechdog.schema import validate_operations  # noqa: E402

ROOT = SOURCE_PATHS.resource_root
TOL = 1e-5
BOSS_RADIUS = 3.0
BOSS_HEIGHT = 3.0
DRAFT_ANGLE_DEG = 11.0
BASE_SIZE = 40.0
BASE_DEPTH = 10.0


def r_top() -> float:
    return BOSS_RADIUS - BOSS_HEIGHT * math.tan(math.radians(DRAFT_ANGLE_DEG))


def frustum_volume() -> float:
    r = r_top()
    return math.pi * BOSS_HEIGHT / 3.0 * (BOSS_RADIUS**2 + BOSS_RADIUS * r + r**2)


def flared_volume() -> float:
    """Creo's default draft direction flares this boss outward; verify both."""
    r = BOSS_RADIUS + BOSS_HEIGHT * math.tan(math.radians(DRAFT_ANGLE_DEG))
    return math.pi * BOSS_HEIGHT / 3.0 * (BOSS_RADIUS**2 + BOSS_RADIUS * r + r**2)


def cylinder_volume() -> float:
    return math.pi * BOSS_RADIUS**2 * BOSS_HEIGHT


def near(actual: Any, expected: Any, tolerance: float = TOL) -> None:
    assert math.isfinite(actual), actual
    assert abs(actual - expected) <= max(tolerance, abs(expected) * 1e-6), (actual, expected)


def load_example(name: str) -> dict:
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def materialize(document: dict) -> list[dict]:
    """Turn documented placeholders into schema-valid inputs without editing files."""
    operations = copy.deepcopy(document["request"]["operations"])
    for operation in operations:
        if operation.get("op") == "draft":
            for surface in operation["surfaces"]:
                if surface.get("kind") == "surface" and not isinstance(surface.get("id"), int):
                    surface["id"] = 12345
    return operations


def offline_checks() -> dict:
    batch = load_example("dev047_t12_batch_append.json")
    draft = load_example("dev047_t12_draft_boss.json")
    batch_operations = validate_operations(materialize(batch))
    draft_operations = validate_operations(materialize(draft))
    assert len(batch_operations) == 6, batch_operations
    assert len(draft_operations) == 3, draft_operations
    labels = [op["label"] for op in batch_operations + draft_operations]
    assert len(labels) == len(set(labels)), labels
    for document, count in ((batch, 6), (draft, 3)):
        text = json.dumps(document, ensure_ascii=False)
        assert "expected_revision" in text, document["description"][:40]
        assert "saved_file_reloaded_and_verified" in text, document["description"][:40]
    assert "200 operations" in json.dumps(batch, ensure_ascii=False)
    # The documented geometry is recomputed here, so the example cannot drift
    # from the formulas the live driver asserts.
    near(r_top(), 3.0 - 3.0 * math.tan(math.radians(11.0)))
    near(frustum_volume() + math.pi * (18.0 - 3.0 * r_top() - r_top() ** 2), cylinder_volume())
    return {
        "batch_operations": len(batch_operations),
        "draft_operations": len(draft_operations),
        "r_top_mm": r_top(),
        "frustum_volume_mm3": frustum_volume(),
        "cylinder_volume_mm3": cylinder_volume(),
        "removed_mm3": cylinder_volume() - frustum_volume(),
    }


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
            "tools/test_t12_examples.py",
            "tests/unit/test_t12_examples.py",
            "examples/dev047_t12_batch_append.json",
            "examples/dev047_t12_draft_boss.json",
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
            "task": "DEV-047 T12",
            "started_at": time.time(),
            "calls": [],
            "batch_append": None,
            "draft_boss": None,
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
        args: dict[str, Any] = {"operations": operations}
        if previous:
            args.update(model_id=previous["model_id"], expected_revision=previous["revision"])
        accepted = await self.call("creo_execute_plan", args)
        deadline = time.monotonic() + 360
        while True:
            terminal = await self.call("creo_get_job", {"job_id": accepted["job_id"]})
            if terminal["status"] not in ("queued", "running"):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(accepted["job_id"])
            await asyncio.sleep(1)
        assert terminal["status"] == ("succeeded" if success else "failed"), terminal
        if success:
            assert terminal["result"]["saved_file_reloaded_and_verified"] is True, terminal
        else:
            assert terminal["result"]["rollback_succeeded"] is True, terminal
        return terminal

    def check_contract(self, terminal: dict, count: int) -> None:
        results = terminal["result"]["operations"]
        assert len(results) == count, results
        for index, entry in enumerate(results):
            assert entry["index"] == index, entry
            assert entry["execution_status"] == "succeeded", entry
            assert entry["effect_status"] == "committed", entry

    def check_volume(self, snapshot: dict, expected: float) -> None:
        inspection = snapshot["inspection"]
        assert inspection["length_unit"]["name"] == "mm", inspection["length_unit"]
        assert inspection["volume_query_code"] == 0, inspection
        near(inspection["volume_mm3"], expected, max(TOL, expected * 1e-4))

    @staticmethod
    def sketch(label: str, entities: list[dict]) -> dict:
        return {
            "op": "sketch",
            "label": label,
            "plane": "XY",
            "entities": entities,
            "dimensioning": "coordinates",
        }

    async def batch_append_case(self) -> None:
        base = [
            self.sketch(
                "base_profile",
                [
                    {
                        "type": "rectangle",
                        "name": "base",
                        "min": [-BASE_SIZE / 2, -BASE_SIZE / 2],
                        "max": [BASE_SIZE / 2, BASE_SIZE / 2],
                    }
                ],
            ),
            {"op": "extrude", "label": "base_solid", "sketch": "base_profile", "depth": BASE_DEPTH},
        ]
        baseline = await self.plan(base)
        before = await self.snapshot(baseline["model_id"])
        document = load_example("dev047_t12_batch_append.json")
        terminal = await self.plan(materialize(document), before)
        self.check_contract(terminal, 6)
        after = await self.snapshot(terminal["model_id"])
        assert after["revision"] == before["revision"] + 1, (before["revision"], after["revision"])
        # Two pads on the 40x40x10 top face plus a radius-3 bore through the plate.
        expected = (
            BASE_SIZE * BASE_SIZE * BASE_DEPTH
            + 20.0 * 20.0 * 5.0
            + 10.0 * 10.0 * 5.0
            - math.pi * 3.0**2 * BASE_DEPTH
        )
        self.check_volume(after, expected)
        self.report["batch_append"] = {
            "model_id": terminal["model_id"],
            "job_id": terminal["job_id"],
            "revision_before": before["revision"],
            "revision_after": after["revision"],
            "operation_results": 6,
            "expected_volume_mm3": expected,
            "actual_volume_mm3": after["inspection"]["volume_mm3"],
            "base_job_id": baseline["job_id"],
            "passed": True,
        }
        self.save()

    def boss_face(self, snapshot: dict) -> int:
        for surface in snapshot["inspection"].get("surfaces", []):
            # Only cylinder entries carry radius plus axis in the inspection.
            radius = surface.get("radius")
            axis = surface.get("axis")
            if radius is None or axis is None:
                continue
            if abs(radius - BOSS_RADIUS) > 1e-6:
                continue
            if abs(abs(axis[2]) - 1.0) > 1e-6:
                continue
            return surface["id"]
        raise AssertionError("boss cylindrical face not found in inspection surfaces")

    async def draft_boss_case(self) -> None:
        document = load_example("dev047_t12_draft_boss.json")
        example_operations = materialize(document)
        assert example_operations[2]["op"] == "draft"
        self.report["draft_boss"] = {}
        # The example documents the single-plan flow (create boss, then draft).
        # This staged variant first creates and inspects a boss to obtain the
        # real face id, then submits only the draft operation. The default
        # direction flares outward on this machine, so both directions are
        # asserted against their own analytic frustum volumes.
        for flip, expected in ((False, flared_volume()), (True, frustum_volume())):
            boss = [
                self.sketch(
                    "boss_profile",
                    [{"type": "circle", "name": "boss", "center": [0, 0], "radius": BOSS_RADIUS}],
                ),
                {
                    "op": "extrude",
                    "label": "boss_solid",
                    "sketch": "boss_profile",
                    "depth": BOSS_HEIGHT,
                },
            ]
            prismatic = await self.plan(boss)
            before = await self.snapshot(prismatic["model_id"])
            self.check_volume(before, cylinder_volume())
            face_id = self.boss_face(before)
            operations = [copy.deepcopy(example_operations[2])]
            operations[0]["surfaces"][0]["id"] = face_id
            operations[0]["flip"] = flip
            terminal = await self.plan(operations, before)
            self.check_contract(terminal, 1)
            after = await self.snapshot(terminal["model_id"])
            self.check_volume(after, expected)
            self.report["draft_boss"][f"flip_{str(flip).lower()}"] = {
                "model_id": terminal["model_id"],
                "job_id": terminal["job_id"],
                "draft_face_id": face_id,
                "angle_deg": DRAFT_ANGLE_DEG,
                "prismatic_volume_mm3": cylinder_volume(),
                "expected_volume_mm3": expected,
                "actual_volume_mm3": after["inspection"]["volume_mm3"],
                "base_job_id": prismatic["job_id"],
                "passed": True,
            }
            self.save()
        self.report["draft_boss"]["r_top_mm"] = r_top()
        self.save()

    async def run(self) -> None:
        await self.batch_append_case()
        await self.draft_boss_case()
        self.report.update(
            native_acceptance="passed",
            scope="official_examples_batch_and_draft",
            unit_matrix="documented_fixed_template",
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
    parser.add_argument("--output", type=Path, default=ROOT / "build/t12_examples.json")
    args = parser.parse_args(argv)
    try:
        enabled = require_live(args)
    except ValueError as error:
        parser.error(str(error))
    if enabled:
        asyncio.run(live(args.output))
    else:
        summary = offline_checks()
        print(
            "OFFLINE ONLY: no MCP client, connection or native acceptance executed; use both "
            "explicit live flags after human session confirmation."
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
