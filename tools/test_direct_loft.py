"""BUG-007 real stdio reproduction. Stop all writes on an uncertain outcome.

The default run checks a small solid, then the task card's two-circle checkpoint
and direct Blend. --suite adds serial repetitions, smooth/three-section/solid
targets, rejected inputs, rollback and matching seed comparisons. It does not
manufacture modal/loader dialogs or constitute WorkBuddy acceptance.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from creo_mechdog.query_client import read_full_model

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "tools.test_direct_loft", *sys.argv[1:]], cwd=ROOT)
    )

from tools.dev_check import git_state, source_hash
from version import VERSION


class UncertainOutcome(RuntimeError):
    """The caller must not submit another write or clear a pending job."""


def circle_sections(count: int = 2) -> list[dict]:
    sizes = [(0, 10), (25, 6)] if count == 2 else [(0, 10), (12.5, 8), (25, 6)]
    return [
        {
            "op": "sketch",
            "label": f"sk_{chr(97 + i)}",
            "plane": "XY",
            "offset": z,
            "entities": [{"type": "circle", "name": f"c_{i}", "center": [0, 0], "radius": r}],
        }
        for i, (z, r) in enumerate(sizes)
    ]


def small_solid() -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "base_profile",
            "plane": "XY",
            "offset": -5,
            "entities": [{"type": "rectangle", "name": "base", "min": [-10, -10], "max": [10, 10]}],
        },
        {"op": "extrude", "label": "base", "sketch": "base_profile", "depth": 5},
    ]


def verify_blend(
    state: dict,
    count: int,
    mode: str,
    before: dict | None = None,
    expected_volume: float | None = None,
) -> None:
    result = state["result"]
    assert state["status"] == "succeeded", state
    assert result["saved_file_reloaded_and_verified"] is True
    inspection = result["inspection"]
    assert inspection["healthy"] and inspection["has_solid"] and inspection["units"] == "mm"
    bodies = [body for body in inspection["bodies"] if body["state"] == 4]
    assert len(bodies) == 1, bodies
    feature_id = result["aliases"]["blend_probe"]["feature_id"]
    native = next(f for f in inspection["features"] if f["id"] == feature_id)
    assert native["status"] == 0 and not native["incomplete"]
    for phase in ("before_save", "after_reload"):
        settings = result["loft_checks"][phase]["blend_probe"]
        assert settings["feature_id"] == feature_id
        assert settings["section_count"] == count and settings["interpolation"] == mode
        assert settings["native_subtype"].lower() in ("blend", "混合")
    if before is not None:
        assert state["revision"] == before["revision"] + 1
        current = {f["id"]: f for f in inspection["features"]}
        for original in before["result"]["inspection"]["features"]:
            assert current[original["id"]]["name"] == original["name"]
            assert current[original["id"]]["type"] == original["type"]
        for label, meta in before["result"]["aliases"].items():
            assert result["aliases"][label]["feature_id"] == meta["feature_id"]
    if expected_volume is not None:
        assert abs(inspection["volume_mm3"] - expected_volume) <= max(0.01, expected_volume * 1e-6)
        bbox = bodies[0]["bbox"]
        expected = [
            [-10, -10, -5 if before and before["result"]["inspection"]["has_solid"] else 0],
            [10, 10, 25],
        ]
        assert all(
            abs(a - b) < 1e-5 for row, target in zip(bbox, expected) for a, b in zip(row, target)
        ), bbox


class Probe:
    def __init__(self, client: Client, report: dict, output: Path, job_budget: float) -> None:
        self.client = client
        self.report = report
        self.output = output
        self.job_budget = job_budget
        self.uncertain = False

    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    async def call(self, tool: str, inputs: dict, expect_error: bool = False) -> dict:
        if tool == "creo_inspect_model" and "detail" not in inputs and not expect_error:
            return await read_full_model(self.call, inputs["model_id"])
        started = time.monotonic()
        entry = {"tool": tool, "input": inputs, "at": datetime.now(timezone.utc).isoformat()}
        self.report["calls"].append(entry)
        self.save()
        try:
            response = await self.client.call_tool(tool, inputs)
        except Exception as exc:
            entry["transport_error"] = repr(exc)
            raise
        finally:
            entry["elapsed_seconds"] = time.monotonic() - started
            self.save()
        entry.update(is_error=response.is_error, result=response.structured_content)
        if response.is_error:
            entry["raw_error"] = [item.model_dump(mode="json") for item in response.content]
        self.save()
        assert response.is_error == expect_error, entry
        return response.structured_content

    async def job(
        self,
        tool: str,
        inputs: dict,
        case: str,
        expected_failure: bool = False,
        allow_failure: bool = False,
    ) -> dict:
        if self.uncertain:
            raise UncertainOutcome("Previous job is uncertain; no further submissions allowed")
        entry = {"case": case, "tool": tool, "input": inputs, "terminal": None}
        self.report["jobs"].append(entry)
        started = time.monotonic()
        try:
            queued = await self.call(tool, inputs)
            entry["job_id"] = queued["job_id"]
            self.save()
            print(json.dumps({"case": case, "job_id": queued["job_id"]}), flush=True)
            while time.monotonic() - started < self.job_budget:
                state = await self.call(
                    "creo_get_job", {"job_id": queued["job_id"], "detail": "compact"}
                )
                if state["status"] not in ("queued", "running"):
                    state = await self.call(
                        "creo_get_job", {"job_id": queued["job_id"], "detail": "full"}
                    )
                    entry["terminal"] = state
                    if state["status"] == "unknown_outcome":
                        raise UncertainOutcome(
                            f"Inspect job {queued['job_id']} and its model before any write"
                        )
                    permitted = (
                        {"succeeded", "failed"}
                        if allow_failure
                        else {"failed" if expected_failure else "succeeded"}
                    )
                    assert state["status"] in permitted, state
                    if state["status"] == "succeeded" and tool != "creo_refresh_model":
                        assert state["result"]["saved_file_reloaded_and_verified"] is True
                    return state
                await asyncio.sleep(0.5)
            raise UncertainOutcome(
                f"Observation budget exceeded for {queued['job_id']}; job may still run"
            )
        except (UncertainOutcome, TimeoutError) as exc:
            self.uncertain = True
            entry["uncertain_reason"] = str(exc)
            raise
        except Exception:
            # A lost submission/poll response cannot prove that a mutation failed.
            if self.report["calls"][-1].get("transport_error"):
                self.uncertain = True
                entry["uncertain_reason"] = (
                    "Transport failure; execution result cannot be confirmed"
                )
            raise
        finally:
            entry["elapsed_seconds"] = time.monotonic() - started
            if "job_id" in entry:
                log = ROOT / "jobs" / entry["job_id"] / "native.log"
                if log.is_file():
                    entry["developer_native_log"] = log.read_text(
                        encoding="utf-8", errors="replace"
                    )
            self.save()


async def run(args: argparse.Namespace) -> dict:
    sources = [
        *ROOT.glob("*.py"),
        *ROOT.glob("src/**/*.py"),
        *ROOT.glob("native/*.cpp"),
        Path(__file__),
    ]
    report = {
        "work_item": args.work_item,
        "version": VERSION,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            **git_state(ROOT),
            "fingerprints": {p.relative_to(ROOT).as_posix(): source_hash(p) for p in sources},
        },
        "environment": {"os": platform.platform(), "python": platform.python_version()},
        "suite": args.suite,
        "observation_budget_seconds": args.job_budget,
        "calls": [],
        "jobs": [],
        "success": False,
        "unverified": [
            "WorkBuddy acceptance",
            "Creo 10",
            "modal state",
            "first DLL loader prompt",
            "concurrency",
        ],
    }
    probe = None
    for name in ("creo_worker.exe", "creo_blend_sync.dll"):
        file = ROOT / "build" / name
        if file.is_file():
            report.setdefault("native_build", {})[name] = hashlib.sha256(
                file.read_bytes()
            ).hexdigest()
    for name in ("source.sha256", "blend_sync_build.json"):
        file = ROOT / "build" / name
        if file.is_file():
            report.setdefault("native_build", {})[name] = file.read_text(encoding="utf-8")
    try:
        params = StdioServerParameters(
            command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT
        )
        async with Client(params, read_timeout_seconds=65) as client:
            probe = Probe(client, report, args.output, args.job_budget)
            cap = await probe.call("creo_capabilities", {})
            assert Path(cap["runtime"]["code_root"]).resolve() == ROOT.resolve()
            assert not cap["runtime"]["source_changed_since_startup"]
            await probe.call("creo_check_environment", {})
            status = await probe.call("creo_startup_status", {"retry": args.retry})
            deadline = time.monotonic() + 130
            while (
                status["state"]
                in {"checking", "building_worker", "starting", "waiting_for_connection"}
                and time.monotonic() < deadline
            ):
                await asyncio.sleep(1)
                status = await probe.call("creo_startup_status", {})
            report["startup"] = status
            if status["state"] != "ready":
                report["blocked"] = (
                    "Toolkit connection baseline failed; loft reproduction not started (BUG-005/BUG-008)"
                )
                return report
            session = await probe.call("creo_session_status", {})
            assert session["connected"], session
            report["session"] = session
            base = await probe.job(
                "creo_execute_plan",
                {
                    "operations": small_solid(),
                    "assertions": {"volume_mm3": 2000, "require_solid": True},
                },
                "connection_small_solid",
            )
            assert abs(base["result"]["inspection"]["volume_mm3"] - 2000) < 0.01
            cases = [(2, "straight", False)]
            if args.suite:
                cases += [(2, "straight", False)] * 2 + [
                    (3, "straight", False),
                    (2, "smooth", False),
                    (3, "smooth", False),
                    (2, "straight", True),
                ]
            for index, (count, mode, solid) in enumerate(cases):
                case = f"direct_{index}_{count}_{mode}"
                ops = (small_solid() if solid else []) + circle_sections(count)
                checkpoint = await probe.job(
                    "creo_execute_plan",
                    {"model_name": "bug007_" + uuid.uuid4().hex[:14], "operations": ops},
                    case + "_checkpoint",
                )
                loft_input = {
                    "model_id": checkpoint["model_id"],
                    "expected_revision": checkpoint["revision"],
                    "label": "blend_probe",
                    "sections": [op["label"] for op in circle_sections(count)],
                    "mode": "add",
                    "interpolation": mode,
                    "new_body": False,
                }
                if args.suite and index == 1:
                    loft_input["sections"] = [
                        checkpoint["result"]["aliases"][label]["feature_id"]
                        for label in loft_input["sections"]
                    ]
                before = await probe.call(
                    "creo_inspect_model", {"model_id": checkpoint["model_id"]}
                )
                checkpoint_file = Path(checkpoint["result"]["part_file"])
                checkpoint_hash = hashlib.sha256(checkpoint_file.read_bytes()).hexdigest()
                report.setdefault("checkpoints", []).append(
                    {
                        "case": case,
                        "model_id": checkpoint["model_id"],
                        "revision": checkpoint["revision"],
                        "part_file": str(checkpoint_file),
                        "sha256": checkpoint_hash,
                    }
                )
                if args.suite:
                    for changes in (
                        {"expected_revision": checkpoint["revision"] - 1},
                        {"sections": ["sk_a", "sk_a"]},
                        {"mode": "cut"},
                        {"mode": "surface"},
                        {"new_body": True},
                    ):
                        await probe.call("creo_loft", {**loft_input, **changes}, expect_error=True)
                        assert (
                            await probe.call(
                                "creo_inspect_model", {"model_id": checkpoint["model_id"]}
                            )
                            == before
                        )
                direct = await probe.job("creo_loft", loft_input, case, allow_failure=True)
                if args.expect_setup_required:
                    assert direct["status"] == "failed", direct
                if direct["status"] == "failed":
                    if args.expect_setup_required:
                        assert "BLEND_CALLBACK_SETUP_REQUIRED" in direct.get("message", ""), direct
                        # B1/F01: the rejection itself must advertise the seed route.
                        for hint in (
                            "creo_new_loft_part",
                            "creo_list_seeds",
                            "callback_free_route",
                        ):
                            assert hint in direct.get("message", ""), (hint, direct)
                        assert report["jobs"][-1]["elapsed_seconds"] < 30, report["jobs"][-1]
                        assert "TK_CALL_BEGIN name=blend_dll_load" not in report["jobs"][-1].get(
                            "developer_native_log", ""
                        )
                    assert (
                        direct["result"].get("rollback_succeeded") is True
                        or direct["result"].get("model_unchanged") is True
                    ), direct
                    after = await probe.call(
                        "creo_inspect_model", {"model_id": checkpoint["model_id"]}
                    )
                    for key in ("revision", "part_file", "inspection", "aliases"):
                        assert after[key] == before[key], key
                    assert (
                        hashlib.sha256(checkpoint_file.read_bytes()).hexdigest() == checkpoint_hash
                    )
                    restored = await probe.job(
                        "creo_refresh_model",
                        {"model_id": checkpoint["model_id"]},
                        case + "_failed_refresh",
                    )
                    assert restored["revision"] == checkpoint["revision"]
                    assert restored["result"]["aliases"] == checkpoint["result"]["aliases"]
                    assert (
                        restored["result"]["inspection"]["features"]
                        == checkpoint["result"]["inspection"]["features"]
                    )
                    if args.expect_setup_required:
                        plan_failure = await probe.job(
                            "creo_execute_plan",
                            {
                                "model_id": checkpoint["model_id"],
                                "expected_revision": checkpoint["revision"],
                                "operations": [
                                    {
                                        "op": "loft",
                                        **{
                                            k: v
                                            for k, v in loft_input.items()
                                            if k not in ("model_id", "expected_revision")
                                        },
                                    }
                                ],
                            },
                            case + "_plan_rejection",
                            expected_failure=True,
                        )
                        assert "BLEND_CALLBACK_SETUP_REQUIRED" in plan_failure.get("message", "")
                        assert (
                            plan_failure["result"].get("rollback_succeeded") is True
                            or plan_failure["result"].get("model_unchanged") is True
                        )
                        assert report["jobs"][-1]["elapsed_seconds"] < 30
                        assert "TK_CALL_BEGIN name=blend_dll_load" not in report["jobs"][-1].get(
                            "developer_native_log", ""
                        )
                        after_plan = await probe.call(
                            "creo_inspect_model", {"model_id": checkpoint["model_id"]}
                        )
                        for key in ("revision", "part_file", "inspection", "aliases"):
                            assert after_plan[key] == before[key], key
                        assert (
                            hashlib.sha256(checkpoint_file.read_bytes()).hexdigest()
                            == checkpoint_hash
                        )
                    await probe.job(
                        "creo_execute_plan",
                        {"operations": small_solid(), "assertions": {"volume_mm3": 2000}},
                        case + "_after_failed_small_solid",
                    )
                    report["confirmed_direct_failure_checked"] = True
                    if args.expect_setup_required:
                        report["restricted_loader_verified"] = True
                        report["success"] = True
                        report["unverified"].append(
                            "seed control not part of restricted-loader-only run"
                        )
                        return report
                expected = (
                    4900 * math.pi / 3 + (2000 if solid else 0) if mode == "straight" else None
                )
                if direct["status"] == "succeeded":
                    verify_blend(direct, count, mode, checkpoint, expected)
                seed = next(
                    (
                        s
                        for s in cap["seed_library"]["seeds"]
                        if s["section_count"] == count
                        and s["interpolation"] == mode
                        and s["available"]
                    ),
                    None,
                )
                assert seed is not None, (count, mode)
                seeded = await probe.job(
                    "creo_new_loft_part",
                    {
                        "seed_file": seed["seed_file"],
                        "seed_feature_id": seed["seed_feature_id"],
                        "sections": circle_sections(count),
                        "label": "blend_probe",
                        "interpolation": mode,
                    },
                    case + "_seed_control",
                )
                verify_blend(
                    seeded,
                    count,
                    mode,
                    expected_volume=4900 * math.pi / 3 if mode == "straight" else None,
                )
                if direct["status"] == "failed":
                    raise AssertionError(
                        "Direct loft failed; restored checkpoint and subsequent small solid verified; seed control is independent"
                    )
                if not solid:
                    assert (
                        abs(
                            seeded["result"]["inspection"]["volume_mm3"]
                            - direct["result"]["inspection"]["volume_mm3"]
                        )
                        < 0.01
                    )
                if args.suite:
                    failed = await probe.job(
                        "creo_execute_plan",
                        {
                            "model_id": direct["model_id"],
                            "expected_revision": direct["revision"],
                            "operations": [
                                {
                                    "op": "sketch",
                                    "label": "rollback_probe",
                                    "offset": 40,
                                    "entities": [
                                        {
                                            "type": "circle",
                                            "name": "c",
                                            "center": [0, 0],
                                            "radius": 1,
                                        }
                                    ],
                                }
                            ],
                            "assertions": {"volume_mm3": 1},
                        },
                        case + "_rollback",
                        expected_failure=True,
                    )
                    assert failed["result"]["rollback_succeeded"] is True
                    refreshed = await probe.job(
                        "creo_refresh_model",
                        {"model_id": direct["model_id"]},
                        case + "_rollback_refresh",
                    )
                    assert refreshed["revision"] == direct["revision"]
                    assert refreshed["result"]["aliases"] == direct["result"]["aliases"]
                    assert (
                        abs(
                            refreshed["result"]["inspection"]["volume_mm3"]
                            - direct["result"]["inspection"]["volume_mm3"]
                        )
                        < 0.01
                    )
                    await probe.job(
                        "creo_execute_plan",
                        {"operations": small_solid(), "assertions": {"volume_mm3": 2000}},
                        case + "_post_failure_small_solid",
                    )
            report["success"] = True
    except Exception as exc:
        report["failure"] = repr(exc)
        report["writes_stopped_for_uncertain_outcome"] = bool(probe and probe.uncertain)
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {k: report[k] for k in ("success", "blocked", "failure") if k in report},
                ensure_ascii=False,
            ),
            flush=True,
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--retry",
        action="store_true",
        help="Explicit startup recheck; existing Creo sessions are preserved",
    )
    parser.add_argument("--suite", action="store_true")
    parser.add_argument("--work-item", default="BUG-007")
    parser.add_argument(
        "--expect-setup-required",
        action="store_true",
        help="Verify rejection before DLL load, unchanged checkpoint, rollback and subsequent small solid; not a successful Blend test",
    )
    parser.add_argument(
        "--job-budget",
        type=float,
        default=900,
        help="Observation only; never cancels or resubmits a job",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "build/bug007_direct_loft.json")
    args = parser.parse_args()
    if not math.isfinite(args.job_budget) or args.job_budget <= 0:
        parser.error("--job-budget must be finite and positive")
    return 0 if asyncio.run(run(args))["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
