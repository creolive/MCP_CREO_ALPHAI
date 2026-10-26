"""DEV-047 T08 part feature lifecycle native acceptance. Default is strictly offline.

Only ``--live --confirm-session-usable`` starts an MCP client. The second flag
attests that the operator has completed the BUG-001 session recovery checks.
The driver never launches or stops Creo, clears protection, injects faults,
submits startup/retry commands, or resubmits a busy or failed job.
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
BASE_WIDTH, BASE_HEIGHT, BASE_DEPTH = 120.0, 80.0, 10.0
PAD_RADIUS, PAD_DEPTH = 10.0, 5.0
BASE_VOLUME = BASE_WIDTH * BASE_HEIGHT * BASE_DEPTH
PAD_VOLUME = math.pi * PAD_RADIUS**2 * PAD_DEPTH
TOTAL_VOLUME = BASE_VOLUME + PAD_VOLUME


def near(actual: Any, expected: Any, tolerance: float = TOL) -> None:
    assert isinstance(actual, (int, float)), (actual, expected)
    assert math.isfinite(actual), actual
    assert abs(actual - expected) <= max(tolerance, abs(expected) * 1e-6), (actual, expected)


def sketch(label: str, entities: list[dict]) -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": "XY",
        "entities": entities,
        "dimensioning": "coordinates",
    }


def extrude(label: str, profile: str, **kwargs: Any) -> dict:
    return {"op": "extrude", "label": label, "sketch": profile, "depth": PAD_DEPTH, **kwargs}


def feature_state(action: str, targets: list[Any]) -> dict:
    return {"op": "feature_state", "action": action, "targets": targets}


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


def pad(label: str = "pad", profile: str = "pad_sketch") -> list[dict]:
    return [
        sketch(
            profile,
            [{"type": "circle", "name": "boss", "center": [0, 0], "radius": PAD_RADIUS}],
        ),
        extrude(label, profile),
    ]


def planned_cases() -> dict[str, list[dict]]:
    """Every operation list this driver would submit, for offline validation."""
    return {
        "base": base_plate(),
        "pad": pad(),
        "dependency_refusal": [feature_state("delete", ["pad_sketch"])],
        "suppress": [feature_state("suppress", ["pad_sketch", "pad"])],
        "resume": [feature_state("resume", ["pad_sketch", "pad"])],
        "failed_assertion": [feature_state("suppress", ["pad_sketch", "pad"])],
        "delete": [feature_state("delete", ["pad_sketch", "pad"])],
        "deleted_label_reuse": [
            sketch(
                "pad_sketch",
                [{"type": "circle", "name": "again", "center": [0, 0], "radius": 4}],
            )
        ],
        "legal_edit": pad("pad2", "pad2_sketch"),
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
            "tools/test_t08_feature_state.py",
            "tests/unit/test_t08_feature_state.py",
            "src/creo_mechdog/feature_state.py",
            "native/feature_state.cpp",
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
            "task": "DEV-047 T08",
            "fixture_dimensioning": "coordinates",
            "expected_volume_mm3": {
                "base": BASE_VOLUME,
                "with_pad": TOTAL_VOLUME,
                "pad": PAD_VOLUME,
            },
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

    async def expect_rejection(
        self,
        operations: list[dict],
        category: str,
        *,
        previous: dict | None = None,
        expected_revision: int | None = None,
    ) -> str:
        args: dict[str, Any] = {"operations": operations}
        if previous:
            args.update(
                model_id=previous["model_id"],
                expected_revision=(
                    previous["revision"] if expected_revision is None else expected_revision
                ),
            )
        result = await self.call("creo_execute_plan", args, allow_error=True)
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
        assert category in message, message
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
        self,
        operations: list,
        previous: dict | None = None,
        *,
        success: bool = True,
        expected_revision: int | None = None,
        assertions: dict | None = None,
    ) -> dict:
        args: dict[str, Any] = {"operations": operations}
        if previous:
            args.update(
                model_id=previous["model_id"],
                expected_revision=(
                    previous["revision"] if expected_revision is None else expected_revision
                ),
            )
        if assertions is not None:
            args["assertions"] = assertions
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
    def feature_by_label(cls, snapshot: dict, label: str) -> dict:
        entry = snapshot.get("aliases", {}).get(label)
        assert isinstance(entry, dict), (label, snapshot.get("aliases"))
        wanted = entry["feature_id"]
        for feature in cls.features(snapshot):
            if feature["id"] == wanted:
                return feature
        raise AssertionError((label, wanted))

    def check_volume(self, snapshot: dict, expected: float) -> None:
        inspection = snapshot["inspection"]
        assert inspection["length_unit"]["name"] == "mm", inspection["length_unit"]
        assert inspection["volume_query_code"] == 0, inspection
        near(inspection["volume_mm3"], expected, max(TOL, expected * 1e-6))

    def check_feature_state(self, snapshot: dict, suppressed_labels: set[str]) -> None:
        state = snapshot.get("feature_state")
        assert isinstance(state, dict), state
        recorded = {key for key in state["suppressed"]}
        assert recorded == suppressed_labels, (recorded, suppressed_labels)
        for label in suppressed_labels:
            feature = self.feature_by_label(snapshot, label)
            assert feature["status"] == 5, feature
        for feature in self.features(snapshot):
            if feature["status"] == 5:
                assert any(
                    entry.get("feature_id") == feature["id"]
                    for entry in state["suppressed"].values()
                ), feature

    async def run(self) -> None:
        base = await self.plan(base_plate())
        base_snapshot = await self.snapshot(base["model_id"])
        self.check_volume(base_snapshot, BASE_VOLUME)
        self.check_feature_state(base_snapshot, set())

        pad_job = await self.plan(pad(), base)
        with_pad = await self.snapshot(pad_job["model_id"])
        self.check_volume(with_pad, TOTAL_VOLUME)
        pad_feature = self.feature_by_label(with_pad, "pad")
        pad_sketch = self.feature_by_label(with_pad, "pad_sketch")
        assert pad_sketch["id"] in pad_feature["parent_ids"], pad_feature
        self.report["cases"].append(
            {
                "case": "pad_baseline",
                "job_id": pad_job["job_id"],
                "model_id": pad_job["model_id"],
                "volume_mm3": with_pad["inspection"]["volume_mm3"],
                "pad_feature_id": pad_feature["id"],
                "pad_sketch_feature_id": pad_sketch["id"],
                "passed": True,
            }
        )
        self.save()

        # Dependency refusal: the child extrusion stays active, so deleting the
        # sketch alone must be refused with the dependency list and no job.
        message = await self.expect_rejection(
            [feature_state("delete", ["pad_sketch"])],
            "do not cover every affected dependency",
        )
        self.report["admission_rejections"][-1]["dependency_ids_returned"] = [
            feature["id"] for feature in (pad_feature, pad_sketch) if str(feature["id"]) in message
        ]
        self.save()

        suppress = await self.plan([feature_state("suppress", ["pad_sketch", "pad"])], pad_job)
        suppressed = await self.snapshot(suppress["model_id"])
        self.check_volume(suppressed, BASE_VOLUME)
        self.check_feature_state(suppressed, {"pad_sketch", "pad"})
        operation = suppress["result"]["operations"][0]
        assert operation["execution_status"] == "succeeded", operation
        assert operation["effect_status"] == "committed", operation
        assert operation["target_count"] == 2, operation
        assert {item["effect"] for item in operation["targets"]} == {"suppressed"}, operation
        self.report["cases"].append(
            {
                "case": "suppress",
                "job_id": suppress["job_id"],
                "model_id": suppress["model_id"],
                "volume_mm3": suppressed["inspection"]["volume_mm3"],
                "operation": operation,
                "passed": True,
            }
        )
        self.save()

        resume = await self.plan([feature_state("resume", ["pad_sketch", "pad"])], suppress)
        resumed = await self.snapshot(resume["model_id"])
        self.check_volume(resumed, TOTAL_VOLUME)
        self.check_feature_state(resumed, set())
        self.report["cases"].append(
            {
                "case": "resume",
                "job_id": resume["job_id"],
                "model_id": resume["model_id"],
                "volume_mm3": resumed["inspection"]["volume_mm3"],
                "expected_volume_mm3": TOTAL_VOLUME,
                "passed": True,
            }
        )
        self.save()

        # Failed assertion after a real suppress: the job must roll back, keep
        # the revision, the volume and the empty suppression registry.
        before_failure = await self.snapshot(resume["model_id"])
        failed = await self.plan(
            [feature_state("suppress", ["pad_sketch", "pad"])],
            resume,
            success=False,
            assertions={"volume_mm3": TOTAL_VOLUME, "volume_tolerance": 0.01},
        )
        restored = await self.snapshot(resume["model_id"])
        assert restored["revision"] == before_failure["revision"], restored["revision"]
        self.check_volume(restored, TOTAL_VOLUME)
        self.check_feature_state(restored, set())
        self.report["failure_recovery"].append(
            {
                "failed_job_id": failed["job_id"],
                "failure_message": failed["result"].get("message"),
                "failed_stage": failed["result"].get("failed_stage"),
                "rollback_succeeded": True,
                "revision_before": before_failure["revision"],
                "revision_after_failure": restored["revision"],
                "volume_mm3": restored["inspection"]["volume_mm3"],
                "suppression_registry_after": restored["feature_state"]["suppressed"],
                "passed": True,
            }
        )
        self.save()

        # Stale revision never creates a job.
        await self.expect_rejection(
            [feature_state("resume", ["pad_sketch", "pad"])],
            "Stale revision",
            previous=restored,
            expected_revision=restored["revision"] - 1,
        )

        delete = await self.plan([feature_state("delete", ["pad_sketch", "pad"])], restored)
        deleted = await self.snapshot(delete["model_id"])
        self.check_volume(deleted, BASE_VOLUME)
        assert deleted["feature_state"]["tombstone_count"] == 2, deleted["feature_state"]
        assert not set(deleted["aliases"]).intersection({"pad_sketch", "pad"}), deleted["aliases"]
        assert "pad" not in {feature.get("name", "").lower() for feature in self.features(deleted)}
        self.report["cases"].append(
            {
                "case": "delete",
                "job_id": delete["job_id"],
                "model_id": delete["model_id"],
                "volume_mm3": deleted["inspection"]["volume_mm3"],
                "tombstones": deleted["feature_state"]["tombstones"],
                "passed": True,
            }
        )
        self.save()

        # A tombstoned label can never name a new feature.
        await self.expect_rejection(
            [
                sketch(
                    "pad_sketch",
                    [{"type": "circle", "name": "again", "center": [0, 0], "radius": 4}],
                )
            ],
            "deleted labels cannot be reused",
        )

        legal = await self.plan(pad("pad2", "pad2_sketch"), delete)
        after = await self.snapshot(legal["model_id"])
        self.check_volume(after, TOTAL_VOLUME)
        self.check_feature_state(after, set())
        assert "pad2" in after["aliases"], after["aliases"]
        self.report["cases"].append(
            {
                "case": "legal_edit_after_delete",
                "job_id": legal["job_id"],
                "model_id": legal["model_id"],
                "volume_mm3": after["inspection"]["volume_mm3"],
                "saved_file_reloaded_and_verified": True,
                "passed": True,
            }
        )
        self.report.update(
            native_acceptance="passed",
            scope="part_feature_lifecycle",
            geometry_matrix="passed",
            admission_matrix="passed",
            save_reload_matrix="passed",
            rollback_matrix="passed",
            pending_native_acceptance=[],
        )
        self.save()


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


def offline_summary() -> dict:
    cases = planned_cases()
    checked = {}
    for name, operations in cases.items():
        try:
            validate_operations(operations)
            checked[name] = "valid"
        except Exception as error:  # noqa: BLE001 - the offline report records the reason
            checked[name] = f"invalid: {error}"
    return {
        "base_volume_mm3": BASE_VOLUME,
        "pad_volume_mm3": PAD_VOLUME,
        "total_volume_mm3": TOTAL_VOLUME,
        "cases": checked,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/t08_feature_state.json")
    args = parser.parse_args(argv)
    try:
        enabled = require_live(args)
    except ValueError as error:
        parser.error(str(error))
    if enabled:
        asyncio.run(live(args.output))
    else:
        summary = offline_summary()
        print("OFFLINE ONLY: no MCP client, connection or native acceptance executed.")
        print(
            "Use --live --confirm-session-usable after human session confirmation to run the "
            "lifecycle matrix."
        )
        print(
            "Expected volumes: base={base_volume_mm3:.6f} mm3, with pad={total_volume_mm3:.6f} "
            "mm3 (pad={pad_volume_mm3:.6f} mm3)".format(**summary)
        )
        print("Planned operation lists: " + json.dumps(summary["cases"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
