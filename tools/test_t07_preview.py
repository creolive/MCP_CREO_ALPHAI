"""DEV-047 T07 preview acceptance driver. Default is strictly offline.

Only ``--live --confirm-session-usable`` starts an MCP client. The confirm flag
attests that the operator has completed the BUG-001 session recovery checks.
The driver never launches or stops Creo, clears protection, injects faults,
submits startup/retry commands, or resubmits a busy/failed job.

The fixtures replay BUG-066 step by step on a disk, then add a cut and an
angular pattern. For each job the driver records the raw preview return codes
and keeps a copy of the image under the run directory so the reviewer can
compare it with the model by eye. Image content is deliberately NOT judged
here: a successful raster call or a non-empty file never proves the picture is
right, and geometry stays with the native inspection evidence.

The empty new part is the configuration the 0.8.x feedback names (a new part
with no operations). That case is recorded, not asserted as written, and the
same model is then continued in the same session with real geometry so the two
file outcomes can be compared. A sheetmetal part is captured as well, so a
thin wall is compared with a solid body instead of with another disk.

Every run writes a unique report and image directory and refuses to overwrite
an existing report, so historical evidence is never replaced.
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
import uuid
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
WALL_LENGTH_MM = 185.0
WALL_DEPTH_MM = 232.0
WALL_THICKNESS_MM = 1.0


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    """Refuse to overwrite an existing report before any connection is made."""
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "post090_n11_preview" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def resolve_images(output: Path | None, run_id: str) -> Path:
    """Every run keeps its own image directory; history is never replaced."""
    if output is not None:
        return Path(output).parent / "images"
    return ROOT / "build" / "post090_n11_preview" / run_id / "images"


def disk_volume() -> float:
    return math.pi * DISK_RADIUS_MM**2 * DISK_DEPTH_MM


def cut_volume(instances: int = 1) -> float:
    return instances * math.pi * CUT_RADIUS_MM**2 * DISK_DEPTH_MM


def sketch(label: str, entities: list[dict], plane: str = "XY") -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": plane,
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


def empty_plan() -> list[dict]:
    """A new part with no operations: the configuration the 0.8.x reports name.

    Nothing is modelled, so this plan is exactly the "empty part" whose preview
    the external reports record as ``failed_step="output_file"``. The driver
    records the outcome instead of asserting a written image.
    """
    return []


def sheetmetal_plan() -> list[dict]:
    """One flat sheetmetal wall, used as the thin-body comparison case."""
    return [
        sketch(
            "wall_sketch",
            [
                {
                    "type": "line",
                    "name": "wall_line",
                    "start": [0.0, 0.0],
                    "end": [WALL_LENGTH_MM, 0.0],
                    "construction": False,
                }
            ],
            plane="XZ",
        ),
        {
            "op": "sheetmetal_wall",
            "label": "base_wall",
            "sketch": "wall_sketch",
            "depth": WALL_DEPTH_MM,
            "thickness": WALL_THICKNESS_MM,
            "direction": "positive",
        },
    ]


def sheetmetal_volume() -> float:
    return WALL_LENGTH_MM * WALL_THICKNESS_MM * WALL_DEPTH_MM


def sheetmetal_model_name(run_id: str) -> str:
    """A unique model name for the sheetmetal comparison case.

    The name must fit the repository rule (lowercase letters, digits and
    underscores, at most 31 characters) and must not collide with an earlier
    run: the model stays in the Creo session under this name.
    """
    suffix = run_id.rsplit("_", 1)[-1]
    return f"t07_sheetmetal_{suffix}"


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
    def __init__(self, client: Any, output: Path, images: Path, run_id: str) -> None:
        self.client = client
        self.output = output
        self.images = images
        self.report: dict = {
            "task": "DEV-047 T07",
            "run_id": run_id,
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

    async def empty_part_case(self) -> dict:
        """Create the empty new part with the tool the 0.8.x reports name.

        ``creo_new_part`` is the public tool the external reports call out
        ("``creo_new_part`` preview always fails"). Using it here keeps the
        reproduction on the same entry point the report describes.
        """
        accepted = await self.call("creo_new_part", {})
        return await self.terminal(accepted["job_id"])

    async def sheetmetal_part_case(self, model_name: str) -> dict:
        """Create the sheetmetal model the wall operation needs.

        A sheetmetal operation is refused on a part model ("Sheetmetal
        operations require an MCP sheetmetal model"), so the comparison model
        is created with the sheetmetal entry point first and the wall plan
        then continues that model.

        The creation job returns the model revision in its terminal payload:
        a new model starts at revision 0 and the creation job takes it to 1,
        so the wall plan continues it with ``expected_revision=1``.
        """
        accepted = await self.call("creo_new_sheetmetal", {"model_name": model_name})
        terminal = await self.terminal(accepted["job_id"])
        self.report["sheetmetal_model"] = {
            "model_name": model_name,
            "job_id": terminal.get("job_id"),
            "model_id": terminal.get("model_id"),
            "revision": terminal.get("revision"),
            "status": terminal.get("status"),
            "created_with": "creo_new_sheetmetal",
        }
        self.save()
        if terminal.get("status") != "succeeded":
            raise RuntimeError(
                f"sheetmetal model {model_name}: job {terminal.get('job_id')} "
                f"ended {terminal.get('status')}"
            )
        return terminal

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

    def keep_image(self, case: str, path: Path) -> dict:
        self.images.mkdir(parents=True, exist_ok=True)
        target = self.images / f"{case}{path.suffix}"
        shutil.copyfile(path, target)
        data = target.read_bytes()
        return {
            "path": str(target),
            "job_image": str(path),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "content_verification": "human_review_pending",
        }

    def check_preview(
        self,
        case: str,
        terminal: dict,
        *,
        operation: dict | None = None,
        expect_written: bool = True,
    ) -> dict:
        """Record the raw capture codes and keep the image; never judge pixels.

        ``expect_written=False`` records an empty part as skipped when the
        native geometry probe confirms that only datums exist. Older workers
        may still return failed or written; retain their raw evidence.
        """
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
            # BUG-088: keep the filesystem stage beside the raster code so a
            # missing file can be told apart from a failed raster call.
            "file_check": preview.get("file_check"),
            "verification_error": preview.get("verification_error"),
        }
        # Raw codes are the evidence. A zero raster code alone does not mean the
        # picture is correct, so the image is retained for human review.
        if expect_written:
            assert preview.get("status") == "written", record
            assert codes.get("raster") == 0, record
            assert codes.get("display") == 0, record
            assert codes.get("refit") == 0, record
            assert codes.get("repaint") == 0, record
            assert preview.get("file_verified") is True, record
            image = Path(preview["path"])
            assert image.is_file() and image.stat().st_size > 0, record
            record["image"] = self.keep_image(case, image)
        else:
            # The empty part may legitimately produce no image. Record what the
            # filesystem stage reported and keep the raw codes; a missing image
            # must never be reported as a successful capture.
            record["image"] = None
            if preview.get("status") == "written":
                image = Path(preview["path"])
                assert image.is_file() and image.stat().st_size > 0, record
                record["image"] = self.keep_image(case, image)
            else:
                assert preview.get("status") in ("failed", "skipped_no_geometry"), record
                if preview.get("status") == "failed":
                    assert preview.get("failed_step"), record
                else:
                    assert not preview.get("failed_step"), record
                    assert not preview.get("file_verified"), record
        return record

    async def run_case(
        self,
        case: str,
        operations: list,
        previous: dict | None,
        *,
        expect_written: bool = True,
        empty_part: bool = False,
    ) -> dict:
        terminal = (
            await self.empty_part_case()
            if empty_part
            else await self.plan(
                operations,
                previous["model_id"] if previous else None,
                previous["revision"] if previous else None,
            )
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
        record["preview"] = self.check_preview(case, terminal, expect_written=expect_written)
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
        assert operation.get("execution_status") == "succeeded", operation
        record["operation_file"] = operation.get("file")
        assert record["operation_file"] and Path(record["operation_file"]).is_file(), record
        # The export operation carries the exported file; the capture evidence
        # (raw step codes, window/view checks) lives on the job-level preview
        # block that the shared T07 projection attaches to the result.
        record["exported_image"] = self.keep_image("explicit_jpeg_export", Path(operation["file"]))
        record["job_preview"] = self.check_preview("export_job_preview", terminal)
        self.report["cases"].append(record)
        self.save()
        return record

    async def run(self) -> None:
        # The empty new part first: it is the configuration the 0.8.x feedback
        # names, and its capture is allowed to fail. The same model is then
        # continued in this session with real geometry, so the empty-part file
        # outcome and a solid-body file outcome are directly comparable.
        empty = await self.run_case(
            "empty_part", empty_plan(), None, expect_written=False, empty_part=True
        )
        empty_model = {
            "model_id": empty["terminal"]["model_id"],
            "revision": empty["terminal"]["revision"],
        }
        empty_solid = await self.run_case("empty_part_solid", disk_plan(), empty_model)
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
        # A thin sheetmetal wall as the body-shape comparison: the raster path is
        # the same one, so a difference in the written file is attributable to
        # the body and not to a second capture implementation.
        #
        # The model is created with the sheetmetal entry point first. A
        # sheetmetal operation is refused on a part model ("Sheetmetal
        # operations require an MCP sheetmetal model"), so submitting the wall
        # plan as a new model would never reach the raster path at all.
        sheetmetal_created = await self.sheetmetal_part_case(
            sheetmetal_model_name(self.report["run_id"])
        )
        sheetmetal_source = {
            "model_id": sheetmetal_created["model_id"],
            "revision": sheetmetal_created["revision"],
        }
        sheetmetal = await self.run_case("sheetmetal_wall", sheetmetal_plan(), sheetmetal_source)
        sheetmetal_model = {
            "model_id": sheetmetal["terminal"]["model_id"],
            "revision": sheetmetal["terminal"]["revision"],
        }
        await self.export_case(pattern_model)
        self.report.update(
            preview_acceptance="passed",
            fixtures={
                "empty_part": empty_plan(),
                "empty_part_solid": disk_plan(),
                "disk": disk_plan(),
                "cut": cut_plan(),
                "pattern": pattern_plan(),
                "sheetmetal_wall": sheetmetal_plan(),
            },
            expected_volumes_mm3={
                "disk": disk_volume(),
                "after_cut": disk_volume() - cut_volume(1),
                "after_pattern": disk_volume() - cut_volume(PATTERN_COUNT),
                "sheetmetal_wall": sheetmetal_volume(),
            },
            # The empty part is expected to produce no image in the reported
            # configuration. Its file outcome is recorded, never asserted as a
            # written capture, and the image content stays human review. The
            # same model continued with a solid body in the same session shows
            # the second half of the comparison.
            empty_part_expectation="skipped_no_geometry_or_legacy_capture_recorded",
            empty_part_file_outcome={
                "empty_part": empty["record"]["preview"]["status"],
                "empty_part_solid": empty_solid["record"]["preview"]["status"],
                "same_model_id": empty_model["model_id"],
                "note": (
                    "Both rows are recorded outcomes. An empty part with no "
                    "operations and the same model after a solid body are "
                    "separate file-write results; the image content of the "
                    "written one is still human review."
                ),
            },
            sheetmetal_model_id=sheetmetal_model["model_id"],
            pending_native_acceptance=[],
        )


async def live(output: Path, images: Path, run_id: str) -> None:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=60,
    ) as client:
        acceptance = Acceptance(client, output, images, run_id)
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
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        enabled = require_live(args)
    except ValueError as error:
        parser.error(str(error))

    run_id = new_run_id()
    try:
        output = resolve_output(args.output, run_id)
        images = resolve_images(args.output, run_id)
    except ValueError as error:
        print(f"REFUSED BEFORE CONNECTION: {error}")
        return 2

    if enabled:
        asyncio.run(live(output, images, run_id))
    else:
        print(
            "OFFLINE ONLY: no MCP client, connection or preview capture executed; use both "
            "explicit live flags after human session confirmation. Expected fixture volumes: "
            f"disk={disk_volume():.3f}, after_cut={disk_volume() - cut_volume(1):.3f}, "
            f"after_pattern={disk_volume() - cut_volume(PATTERN_COUNT):.3f}, "
            f"sheetmetal_wall={sheetmetal_volume():.3f} mm3. "
            f"run_id={run_id} report={output} images={images}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
