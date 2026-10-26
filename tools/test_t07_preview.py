"""DEV-047 T07 preview acceptance driver. Default is strictly offline.

Only ``--live --confirm-session-usable`` starts an MCP client. The confirm flag
attests that the operator has completed the BUG-001 session recovery checks.
The driver never launches or stops Creo, clears protection, injects faults,
submits startup/retry commands, or resubmits a busy/failed job.

The fixtures replay BUG-066 step by step on a disk, then add a cut and an
angular pattern. For each job the driver records the raw preview return codes
and keeps a copy of the image under build/t07-preview/ so the T13 reviewer can
compare it with the model by eye. Image content is deliberately NOT judged
here: a successful raster call or a non-empty file never proves the picture is
right, and geometry stays with the native inspection evidence.
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
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402

ROOT = SOURCE_PATHS.resource_root
DISK_RADIUS_MM = 40.0
DISK_DEPTH_MM = 12.0
CUT_RADIUS_MM = 10.0
CUT_OFFSET_MM = 20.0
PATTERN_COUNT = 4
PATTERN_INCREMENT_DEG = 90.0
EVIDENCE = ROOT / "build/t07-preview"


def disk_volume() -> float:
    return math.pi * DISK_RADIUS_MM**2 * DISK_DEPTH_MM


def cut_volume(instances: int = 1) -> float:
    return instances * math.pi * CUT_RADIUS_MM**2 * DISK_DEPTH_MM


def sketch(label: str, entities: list[dict]) -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": "XY",
        "entities": entities,
        "dimensioning": "coordinates",
    }


def extrude(label: str, profile: str, **kwargs: Any) -> dict:
    return {"op": "extrude", "label": label, "sketch": profile, **kwargs}


def disk_plan() -> list[dict]:
    return [
        sketch(
            "disk_profile",
            [
                {
                    "type": "circle",
                    "name": "disk",
                    "center": [0.0, 0.0],
                    "radius": DISK_RADIUS_MM,
                }
            ],
        ),
        extrude("disk", "disk_profile", depth=DISK_DEPTH_MM),
    ]


def cut_plan() -> list[dict]:
    # The datum axis is created before the cut so the later angular pattern can
    # use it as the rotation axis without reordering features.
    return [
        {
            "op": "datum_axis",
            "label": "zaxis",
            "references": [
                {"kind": "datum_plane", "axis": "x", "offset": 0},
                {"kind": "datum_plane", "axis": "y", "offset": 0},
            ],
        },
        sketch(
            "cut_profile",
            [
                {
                    "type": "circle",
                    "name": "slot",
                    "center": [CUT_OFFSET_MM, 0.0],
                    "radius": CUT_RADIUS_MM,
                }
            ],
        ),
        extrude("cut", "cut_profile", mode="cut", depth_type="through_all"),
    ]


def pattern_plan() -> list[dict]:
    return [
        {
            "op": "axis_pattern",
            "label": "cut_pattern",
            "leader": "cut",
            "axis": {"kind": "datum_axis_feature", "label": "zaxis"},
            "count": PATTERN_COUNT,
            "increment_deg": PATTERN_INCREMENT_DEG,
        }
    ]


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
            "tools/test_t07_preview.py",
            "tests/unit/test_t07_preview.py",
            "src/creo_mechdog/preview.py",
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
            "task": "DEV-047 T07",
            "fixture_dimensioning": "coordinates",
            "started_at": time.time(),
            "calls": [],
            "cases": [],
            "preview_acceptance": "running",
            "image_content_verification": "human_review_pending",
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
        self, operations: list, model_id: str | None = None, revision: int | None = None
    ):
        args: dict = {"operations": operations}
        if model_id:
            args.update(model_id=model_id, expected_revision=revision)
        accepted = await self.call("creo_execute_plan", args)
        return await self.terminal(accepted["job_id"])

    async def terminal(self, job_id: str) -> dict:
        deadline = time.monotonic() + 360
        while time.monotonic() < deadline:
            terminal = await self.call("creo_get_job", {"job_id": job_id})
            if terminal["status"] not in ("queued", "running"):
                if terminal["status"] == "busy":
                    raise RuntimeError(f"{job_id}: channel busy; not resubmitting")
                return terminal
            await asyncio.sleep(1)
        raise TimeoutError(job_id)

    async def snapshot(self, model_id: str) -> dict:
        from creo_mechdog.query_client import read_full_model

        return await read_full_model(self.call, model_id)

    @staticmethod
    def keep_image(case: str, path: Path) -> dict:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        target = EVIDENCE / f"{case}{path.suffix}"
        shutil.copyfile(path, target)
        data = target.read_bytes()
        return {
            "path": str(target),
            "job_image": str(path),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "content_verification": "human_review_pending",
        }

    def check_preview(self, case: str, terminal: dict, *, operation: dict | None = None) -> dict:
        """Assert the raw capture codes and keep the image; never judge pixels."""
        result = terminal["result"]
        preview = result.get("preview") if operation is None else operation.get("preview")
        assert isinstance(preview, dict), (case, result)
        codes = preview.get("codes", {})
        record = {
            "case": case,
            "job_id": terminal.get("job_id"),
            "model_id": terminal.get("model_id"),
            "status": preview.get("status"),
            "preview_code": (result if operation is None else operation).get("preview_code"),
            "codes": codes,
            "window": preview.get("window"),
            "window_matches_model": preview.get("window_matches_model"),
            "current_window_matches": preview.get("current_window_matches"),
            "view_matrix_matches": preview.get("view_matrix_matches"),
            "failed_step": preview.get("failed_step"),
            "failed_code": preview.get("failed_code"),
            "file_verified": preview.get("file_verified"),
        }
        # Raw codes are the evidence. A zero raster code alone does not mean the
        # picture is correct, so the image is retained for human review.
        assert preview.get("status") == "written", record
        assert codes.get("raster") == 0, record
        assert codes.get("display") == 0, record
        assert codes.get("refit") == 0, record
        assert codes.get("repaint") == 0, record
        assert preview.get("file_verified") is True, record
        image = Path(preview["path"])
        assert image.is_file() and image.stat().st_size > 0, record
        record["image"] = self.keep_image(case, image)
        return record

    async def run_case(self, case: str, operations: list, previous: dict | None) -> dict:
        terminal = await self.plan(
            operations,
            previous["model_id"] if previous else None,
            previous["revision"] if previous else None,
        )
        record: dict = {
            "case": case,
            "job_id": terminal.get("job_id"),
            "model_id": terminal.get("model_id"),
            "status": terminal.get("status"),
            "revision": terminal.get("revision"),
        }
        if terminal["status"] != "succeeded":
            record["message"] = terminal.get("message")
            record["result_message"] = terminal.get("result", {}).get("message")
            self.report["cases"].append(record)
            self.save()
            raise RuntimeError(f"{case}: job {terminal.get('job_id')} ended {terminal['status']}")
        record["saved_file_reloaded_and_verified"] = terminal["result"].get(
            "saved_file_reloaded_and_verified"
        )
        record["preview"] = self.check_preview(case, terminal)
        try:
            snapshot = await self.snapshot(terminal["model_id"])
            inspection = snapshot["inspection"]
            record["volume_mm3"] = inspection.get("volume_mm3")
            record["volume_query_code"] = inspection.get("volume_query_code")
            record["features"] = [
                feature.get("type_name") for feature in inspection.get("features", [])
            ]
        except Exception as error:  # geometry facts are recorded, not asserted here
            record["inspection_error"] = f"{type(error).__name__}: {error}"
        self.report["cases"].append(record)
        self.save()
        return {"terminal": terminal, "record": record}

    async def export_case(self, model: dict) -> dict:
        accepted = await self.call(
            "creo_export_model", {"model_id": model["model_id"], "format": "jpeg"}
        )
        terminal = await self.terminal(accepted["job_id"])
        result = terminal.get("result", {})
        record = {
            "case": "explicit_jpeg_export",
            "job_id": terminal.get("job_id"),
            "model_id": terminal.get("model_id"),
            "status": terminal.get("status"),
            "result_message": result.get("message"),
        }
        if terminal["status"] != "succeeded":
            self.report["cases"].append(record)
            self.save()
            raise RuntimeError(f"export job {terminal.get('job_id')} ended {terminal['status']}")
        operations = result.get("operations") or []
        assert len(operations) == 1, operations
        operation = operations[0]
        assert operation.get("op") == "export", operation
        record["operation_file"] = operation.get("file")
        assert record["operation_file"] and Path(record["operation_file"]).is_file(), record
        record["job_preview"] = self.check_preview("export_job_preview", terminal)
        record["export_preview"] = self.check_preview(
            "export_operation", terminal, operation=operation
        )
        self.report["cases"].append(record)
        self.save()
        return record

    async def run(self) -> None:
        disk = await self.run_case("disk", disk_plan(), None)
        disk_model = {
            "model_id": disk["terminal"]["model_id"],
            "revision": disk["terminal"]["revision"],
        }
        cut = await self.run_case("disk_cut", cut_plan(), disk_model)
        cut_model = {
            "model_id": cut["terminal"]["model_id"],
            "revision": cut["terminal"]["revision"],
        }
        pattern = await self.run_case("disk_cut_pattern", pattern_plan(), cut_model)
        pattern_model = {
            "model_id": pattern["terminal"]["model_id"],
            "revision": pattern["terminal"]["revision"],
        }
        await self.export_case(pattern_model)
        self.report.update(
            preview_acceptance="passed",
            fixtures={
                "disk": disk_plan(),
                "cut": cut_plan(),
                "pattern": pattern_plan(),
            },
            expected_volumes_mm3={
                "disk": disk_volume(),
                "after_cut": disk_volume() - cut_volume(1),
                "after_pattern": disk_volume() - cut_volume(PATTERN_COUNT),
            },
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
                preview_acceptance="failed", error=f"{type(error).__name__}: {error}"
            )
            raise
        finally:
            acceptance.save()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/t07_preview_acceptance.json")
    args = parser.parse_args(argv)
    try:
        enabled = require_live(args)
    except ValueError as error:
        parser.error(str(error))
    if enabled:
        asyncio.run(live(args.output))
    else:
        print(
            "OFFLINE ONLY: no MCP client, connection or preview capture executed; use both "
            "explicit live flags after human session confirmation. Expected fixture volumes: "
            f"disk={disk_volume():.3f}, after_cut={disk_volume() - cut_volume(1):.3f}, "
            f"after_pattern={disk_volume() - cut_volume(PATTERN_COUNT):.3f} mm3."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
