"""DEV-047 T05 non-millimeter unit live acceptance. Default is strictly offline.

Only --live --confirm-session-usable starts an MCP client; the second flag
attests that the operator completed the BUG-001 session recovery checks. The
run requires config.json auto_start_creo=false (set and byte-restored by the
operator around the run), never clears protection, never retries a busy
submission and never restarts Creo.

Production-path unit coverage with no service changes:
  preclean  erase any leftover four_smooth seed copy from earlier probes;
  mm        open one fresh seed copy read-only, adopt-inspect it (millimeter
            baseline: units/volume/center_of_gravity/length_unit through the
            production adoption inspection), then erase the copy;
  fixture   tools/t05_units_fixture converts a second seed copy to inch with
            PRO_UNITCONVERT_SAME_SIZE, adds two 25.4 mm offset planes and one
            datum axis (exactly 1.0 inch after conversion) and backs the copy
            up under a fresh name; the seed file on disk stays untouched;
  inch      open the inch part read-only, adopt-inspect must refuse with
            non_millimeter_units while the public response carries the real
            inch unit semantics (units name, scale_to_mm 25.4, raw
            center_of_gravity scaled by 1/25.4, volume_mm3 null with
            volume_query_code 0 because native in^3 is never relabeled mm^3);
            the path-adoption inspect keeps the full refused evidence, and its
            retained inspection carries the datum axis at raw inch coordinates
            (the 25.4 mm fixture offsets read exactly 1.0);
  cleanup   erase the inch part; the session ends as it started.

Unknown-unit behavior cannot be induced on a healthy real model without
fault injection (stopped under BUG-001); it stays covered by the offline
stub/unit tests and is recorded as such, never as live evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    raise SystemExit(
        subprocess.call(
            [sys.executable, "-m", "tools.test_t05_units_live", *sys.argv[1:]], cwd=ROOT
        )
    )

from bridge import native_environment
from creo_mechdog.build_support import compiler_setup_script, validate_local_path
from creo_mechdog.paths import SOURCE_PATHS
from tools.dev_check import git_state, source_hash
from version import VERSION

SEED = ROOT / "seed_library" / "seeds" / "four_smooth" / "db_8bdd03c9da.prt.2"
SEED_NAME = "db_8bdd03c9da"
INCH = 25.4
TOL = 1e-6


def near(actual: Any, expected: Any, tolerance: float = TOL) -> None:
    if isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected), (actual, expected)
        for a, b in zip(actual, expected, strict=True):
            near(a, b, tolerance)
    else:
        assert actual is not None and abs(actual - expected) <= tolerance, (actual, expected)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_live(args: argparse.Namespace) -> bool:
    if args.live and not args.confirm_session_usable:
        raise ValueError(
            "--live requires --confirm-session-usable after human session recovery checks"
        )
    return args.live


def require_manual_start(config_file: Path) -> None:
    settings = json.loads(config_file.read_text(encoding="utf-8-sig"))
    if settings.get("auto_start_creo") is not False:
        raise ValueError(
            "Live acceptance requires config.json auto_start_creo=false; no client was started"
        )


def build_fixture(directory: Path, report: dict) -> Path:
    directory = directory.resolve()
    settings = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    sdk = Path(settings["creo_root"]) / "Common Files/protoolkit"
    source = ROOT / "tools" / "t05_units_fixture.cpp"
    executable = directory / "t05_units_fixture.exe"
    for path in (sdk, directory, source):
        validate_local_path(str(path), "t05 units fixture path")
    libraries = [
        sdk / "x86e_win64" / "obj" / name
        for name in ("protkmd_NU.lib", "ptasyncmd.lib", "ucore.lib", "udata.lib")
    ]
    system = [
        "bcrypt.lib",
        "kernel32.lib",
        "user32.lib",
        "wsock32.lib",
        "advapi32.lib",
        "mpr.lib",
        "winspool.lib",
        "netapi32.lib",
        "psapi.lib",
        "gdi32.lib",
        "shell32.lib",
        "comdlg32.lib",
        "ole32.lib",
        "ws2_32.lib",
    ]
    batch = directory / "build_fixture.cmd"
    object_file = directory / "fixture.obj"
    batch.write_text(
        "@echo off\n"
        + compiler_setup_script(settings)
        + "\ncl /nologo /MD /EHsc /std:c++17 /DPRO_MACHINE=36 /DPRO_OS=4 /DPRO_USE_VAR_ARGS "
        + f'/I"{sdk / "includes"}" /c "{source}" /Fo:"{object_file}"\n'
        + f'link /nologo /MACHINE:X64 /SUBSYSTEM:CONSOLE /OUT:"{executable}" "{object_file}" '
        + " ".join(f'"{lib}"' for lib in libraries)
        + " "
        + " ".join(system)
        + "\n"
        + "exit /b %errorlevel%\n",
        encoding="utf-8",
    )
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (directory / "build_fixture.log").open("wb") as log:
        built = subprocess.run(
            ["cmd.exe", "/d", "/c", str(batch)],
            cwd=directory,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=180,
            creationflags=flags,
        )
    report["fixture_build"] = {"returncode": built.returncode, "log": "build_fixture.log"}
    assert built.returncode == 0, "fixture compilation failed"
    return executable


def run_fixture(executable: Path, arguments: list[str], directory: Path) -> dict:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    completed = subprocess.run(
        [str(executable), *arguments],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=180,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
        env=native_environment(),
    )
    payload: dict = {}
    for line in completed.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            payload.update(json.loads(line))
    payload["returncode"] = completed.returncode
    payload["stderr"] = completed.stderr.strip()[:2000]
    payload["stdout_lines"] = [line for line in completed.stdout.splitlines() if line.strip()]
    return payload


class Acceptance:
    def __init__(self, client: Any, output: Path, directory: Path, stamp: str) -> None:
        self.client = client
        self.output = output
        self.directory = directory
        self.stamp = stamp
        self.report: dict[str, Any] = {
            "work_items": ["DEV-047"],
            "version": VERSION,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "source": {
                **git_state(ROOT),
                "resource_root": str(SOURCE_PATHS.resource_root),
                "checked_source_sha256": {
                    "driver": source_hash(ROOT / "tools" / "test_t05_units_live.py"),
                    "fixture": source_hash(ROOT / "tools" / "t05_units_fixture.cpp"),
                },
            },
            "seed": {"path": str(SEED), "sha256": sha256(SEED)},
            "phases": {},
            "calls": [],
        }

    def save(self) -> None:
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def call(self, name: str, args: dict) -> dict:
        record = {"tool": name, "args": args, "at": time.time()}
        self.report["calls"].append(record)
        try:
            result = await self.client.call_tool(name, args)
        except Exception as error:  # noqa: BLE001
            record["exception"] = f"{type(error).__name__}: {error}"
            self.save()
            raise
        record["is_error"] = result.is_error
        record["result"] = result.structured_content
        return result.structured_content

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
                raise RuntimeError(f"Existing session is not ready; no queries submitted: {status}")
            if time.monotonic() >= deadline:
                raise TimeoutError("Startup observation budget exceeded; no queries submitted")
            await asyncio.sleep(1)

    async def poll_job(self, tool: str, inputs: dict, case: str, budget: float = 300) -> dict:
        entry = {"case": case, "tool": tool, "input": inputs, "terminal": None}
        self.report.setdefault("jobs", []).append(entry)
        accepted = await self.call(tool, inputs)
        assert "job_id" in accepted, accepted
        entry["job_id"] = accepted["job_id"]
        self.save()
        started = time.monotonic()
        while time.monotonic() - started < budget:
            state = await self.call(
                "creo_get_job", {"job_id": accepted["job_id"], "detail": "compact"}
            )
            if state["status"] not in ("queued", "running"):
                entry["terminal"] = await self.call(
                    "creo_get_job", {"job_id": accepted["job_id"], "detail": "full"}
                )
                self.save()
                return entry["terminal"]
            await asyncio.sleep(0.5)
        raise TimeoutError(f"observation budget exceeded for {accepted['job_id']}")

    async def session_names(self) -> list[str]:
        names: list[str] = []
        cursor = None
        while True:
            args = {"limit": 50}
            if cursor:
                args["cursor"] = cursor
            inventory = await self.call("creo_list_session_models", args)
            models = inventory.get("models", [])
            names.extend(
                str(item["name"]).upper()
                for item in models
                if isinstance(item, dict) and item.get("name")
            )
            cursor = inventory.get("next_cursor")
            if not cursor:
                assert inventory.get("complete") is True, inventory
                return sorted(set(names))

    async def erase(self, targets: list[dict], case: str) -> dict:
        inspected = await self.call(
            "creo_erase_session_models", {"mode": "inspect", "targets": targets}
        )
        token = inspected.get("evidence_token")
        assert token, inspected
        terminal = await self.poll_job(
            "creo_erase_session_models",
            {
                "mode": "apply",
                "evidence_token": token,
                "idempotency_key": f"t05units-{case}-{self.stamp}",
            },
            case,
        )
        assert terminal["status"] == "succeeded", terminal
        return terminal

    def preflight_inspection(self, origin_suffix: str) -> tuple[dict, dict]:
        """Latest adoption preflight job for this source origin: summary + full sidecar."""
        jobs = ROOT / "jobs"
        candidates = []
        for entry in jobs.iterdir():
            manifest = entry / "job.json"
            if not manifest.is_file():
                continue
            try:
                meta = json.loads(manifest.read_text(encoding="utf-8"))
                result = json.loads((entry / "native_result.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if meta.get("kind") != "adoption_preflight":
                continue
            live = result.get("live") or {}
            origin = live.get("origin")
            if isinstance(origin, str) and origin.lower().endswith(origin_suffix.lower()):
                candidates.append((meta.get("created_at", ""), entry, live))
        assert candidates, f"no adoption preflight found for {origin_suffix}"
        _, entry, live = max(candidates, key=lambda item: item[0])
        reference = live.get("inspection_ref") or {}
        sidecar = (
            Path(reference["file"])
            if isinstance(reference, dict) and reference.get("file")
            else None
        )
        inspection = (
            json.loads(sidecar.read_text(encoding="utf-8"))
            if sidecar and sidecar.is_file()
            else None
        )
        return live, {
            "job_dir": str(entry),
            "inspection_sidecar": str(sidecar),
            "inspection": inspection,
        }


async def inch_flow(acceptance: Acceptance) -> None:
    report = acceptance.report
    executable = build_fixture(acceptance.directory, report)
    acceptance.save()

    names_before = await acceptance.session_names()
    report["phases"]["session_start"] = {
        "count": len(names_before),
        "has_seed_copy": SEED_NAME.upper() in names_before,
    }

    # preclean: an aborted earlier attempt may have left the seed copy or one
    # of its own converted inch parts in the session.
    leftovers = [{"name": SEED_NAME, "model_type": "part"}] * (SEED_NAME.upper() in names_before)
    leftovers += [
        {"name": name.lower(), "model_type": "part"}
        for name in names_before
        if name.startswith("T05_INCH_")
    ]
    if leftovers:
        await acceptance.erase(leftovers, "preclean")
        report["phases"]["preclean"] = {"erased": [target["name"] for target in leftovers]}
        acceptance.save()

    # mm baseline through the production adoption inspection.
    seed_copy = acceptance.directory / SEED.name
    shutil.copyfile(SEED, seed_copy)
    seed_before = sha256(SEED)
    opened = await acceptance.poll_job(
        "creo_open_file",
        {"file_path": str(seed_copy), "idempotency_key": f"t05units-mm-{acceptance.stamp}"},
        "mm_open",
    )
    assert opened["status"] == "succeeded", opened
    open_result = opened["result"]["open_file"]
    assert open_result["loaded"] is True and open_result["displayed"] is True, open_result
    adoption = await acceptance.call("creo_adopt_current_model", {"mode": "inspect"})
    assert adoption.get("available") is True, adoption
    summary = adoption["current_model"]["inspection_summary"]
    assert summary["units"] == "mm", summary
    assert summary["units_query_code"] == 0 and summary["volume_query_code"] == 0, summary
    near(summary["length_unit"]["scale_to_mm"], 1.0, 1e-9)
    mm_volume = summary["volume_mm3"]
    mm_gravity = summary["center_of_gravity"]
    _live, evidence = acceptance.preflight_inspection(SEED.name)
    assert evidence["inspection"] is not None, evidence
    mm_full = evidence["inspection"]
    assert mm_full["units"] == "mm" and mm_full["volume_mm3"] == mm_volume, mm_full
    report["phases"]["mm_baseline"] = {
        "job_id": opened["job_id"],
        "volume_mm3": mm_volume,
        "center_of_gravity": mm_gravity,
        "length_unit": summary["length_unit"],
        "datum_axes": len(mm_full.get("datum_axes") or []),
        "evidence": {k: evidence[k] for k in ("job_dir", "inspection_sidecar")},
    }
    acceptance.save()
    await acceptance.erase([{"name": SEED_NAME, "model_type": "part"}], "mm_erase")

    # fixture: convert a fresh copy to inch, add 1-inch offset planes + axis.
    inch_name = f"t05_inch_{acceptance.stamp}"
    inch_dir = acceptance.directory / "inch"
    inch_dir.mkdir(parents=True, exist_ok=True)
    fixture = run_fixture(
        executable,
        ["inch", str(seed_copy), inch_name, str(inch_dir)],
        acceptance.directory,
    )
    report["phases"]["fixture"] = fixture
    acceptance.save()
    assert fixture["returncode"] == 0, fixture
    assert fixture.get("error") is None, fixture
    assert fixture.get("disconnect") == 0, fixture
    assert fixture.get("resolved", -1) == 0, fixture  # inch unit resolved
    inch_file = inch_dir / f"{inch_name}.prt"
    versions = sorted(inch_dir.glob(f"{inch_name}.prt.*"))
    assert versions, sorted(inch_dir.iterdir())
    report["phases"]["fixture"]["written"] = [p.name for p in versions]
    assert sha256(SEED) == seed_before, "the seed file on disk changed during the run"

    # inch queries through the same production paths.
    opened = await acceptance.poll_job(
        "creo_open_file",
        {"file_path": str(inch_file), "idempotency_key": f"t05units-inch-{acceptance.stamp}"},
        "inch_open",
    )
    assert opened["status"] == "succeeded", opened
    open_result = opened["result"]["open_file"]
    assert open_result["loaded"] is True, open_result
    adoption = await acceptance.call("creo_adopt_current_model", {"mode": "inspect"})
    assert adoption.get("available") is False, adoption
    assert adoption.get("reason_code") == "non_millimeter_units", adoption
    details = adoption.get("refusal_details") or {}
    assert details.get("actual_units") in ("inch", "in"), details
    assert details.get("actual_units_known") is True and details.get("units_query_code") == 0, (
        details
    )
    summary = adoption["current_model"]["inspection_summary"]
    assert summary["units"] in ("inch", "in"), summary
    assert summary["units_query_code"] == 0 and summary["volume_query_code"] == 0, summary
    near(summary["length_unit"]["scale_to_mm"], INCH, 1e-9)
    assert summary["length_unit"]["scale_to_mm_known"] is True, summary
    # BUG-072 contract: native inch volumes are never relabeled mm^3; the
    # millimeter-normalized field stays null while the raw query succeeded and
    # length_unit carries the 25.4 scale for callers.
    assert summary["volume_mm3"] is None, summary
    near(summary["center_of_gravity"], [value / INCH for value in mm_gravity])
    report["phases"]["inch_refusal"] = {
        "open_job_id": opened["job_id"],
        "reason_code": adoption["reason_code"],
        "refusal_details": details,
        "inspection_summary": summary,
    }
    acceptance.save()

    # The window-model refusal cleans its staging sidecar; the path-adoption
    # inspect keeps durable per-item evidence, so the full inch inspection
    # (including the raw-inch datum axes) is read through that production path.
    path_adoption = await acceptance.call(
        "creo_adopt_file", {"mode": "inspect", "file_path": str(inch_file)}
    )
    items = path_adoption.get("items") or []
    assert len(items) == 1 and items[0]["status"] == "refused", items
    assert items[0]["reason"] == "non_millimeter_units", items[0]
    path_details = items[0].get("refusal_details") or {}
    assert path_details.get("actual_units") in ("inch", "in"), path_details
    assert path_details.get("units_query_code") == 0, path_details
    evidence_job = ROOT / "jobs" / items[0]["evidence_job_id"]
    native_result = json.loads((evidence_job / "native_result.json").read_text(encoding="utf-8"))
    live_result = native_result.get("live") or {}
    inch_inline = isinstance(live_result.get("inspection"), dict)
    inch_full = live_result.get("inspection")
    sidecar = None
    if not inch_inline:
        # Older probe evidence keeps only a controlled sidecar reference.
        reference = live_result.get("inspection_ref") or {}
        sidecar = Path(reference["file"])
        assert sidecar.is_file(), reference  # path adoption keeps refused evidence
        inch_full = json.loads(sidecar.read_text(encoding="utf-8"))
    assert inch_full["units"] in ("inch", "in") and inch_full["units_query_code"] == 0, inch_full
    near(inch_full["length_unit"]["scale_to_mm"], INCH, 1e-9)
    assert inch_full["volume_mm3"] is None and inch_full["volume_query_code"] == 0, inch_full
    near(inch_full["center_of_gravity"], [value / INCH for value in mm_gravity])
    axes = [a for a in inch_full.get("datum_axes", []) if a.get("geometry_known")]
    assert axes, inch_full.get("datum_axes")
    axis_hits = []
    for axis in axes:
        if abs(abs(axis["direction"][2]) - 1.0) > 1e-6:
            continue
        if abs(axis["origin"][0] - 1.0) > TOL or abs(axis["origin"][1] - 1.0) > TOL:
            continue
        assert axis["data_query_code"] == 0 and axis["line_query_code"] == 0, axis
        axis_hits.append({k: axis[k] for k in ("id", "feature_id", "origin", "direction")})
    assert axis_hits, [a.get("origin") for a in axes]
    report["phases"]["inch_queries"] = {
        "adopt_file_item": {
            "status": items[0]["status"],
            "reason": items[0]["reason"],
            "refusal_details": path_details,
        },
        "length_unit": inch_full["length_unit"],
        "volume_mm3": inch_full["volume_mm3"],
        "volume_query_code": inch_full["volume_query_code"],
        "center_of_gravity_raw": inch_full["center_of_gravity"],
        "axis_hits": axis_hits,
        "evidence": {
            "job_dir": str(evidence_job),
            "inspection_inline": inch_inline,
            "inspection_sidecar": str(sidecar) if sidecar else None,
        },
    }
    acceptance.save()

    # cleanup: the session ends as it started.
    await acceptance.erase([{"name": inch_name, "model_type": "part"}], "inch_erase")
    names_after = await acceptance.session_names()
    report["phases"]["cleanup"] = {
        "count": len(names_after),
        "seed_copy_remaining": SEED_NAME.upper() in names_after,
        "inch_remaining": inch_name.upper() in names_after,
    }
    assert SEED_NAME.upper() not in names_after and inch_name.upper() not in names_after
    report["native_unit_coverage"] = {
        "millimeter": "passed (T05 metric matrix, build/t05-native-05.json)",
        "inch_part": "passed",
        "mixed_assembly": "BUG-080 live evidence 2026-10-24 (docs/validation/BUG080-FEAT006-LIVE-2026-10-24)",
        "unknown": "not inducible on a healthy real session without fault injection "
        "(stopped under BUG-001); offline stub/unit coverage only",
    }
    report["native_acceptance"] = "non_millimeter_passed_unknown_stub_only"


async def live(output: Path) -> None:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    stamp = datetime.now().strftime("%H%M%S")
    directory = (output.parent / f"run-{stamp}").resolve()
    directory.mkdir(parents=True, exist_ok=True)
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=90,
    ) as client:
        acceptance = Acceptance(client, output, directory, stamp)
        acceptance.save()
        try:
            acceptance.report["capabilities"] = await acceptance.call("creo_capabilities", {})
            await acceptance.wait_ready()
            status = await acceptance.call("creo_session_status", {})
            assert status["connected"], status
            await inch_flow(acceptance)
        except Exception as error:
            acceptance.report.update(
                native_acceptance="failed", error=f"{type(error).__name__}: {error}"
            )
            raise
        finally:
            acceptance.report["finished_utc"] = datetime.now(timezone.utc).isoformat()
            acceptance.save()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/t05_units_live.json")
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
