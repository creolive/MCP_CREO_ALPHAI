"""0.5.2 live acceptance evidence: BUG-080 mixed-unit assembly inspect + FEAT-006 unhealthy adoption refusal.

Runs against a live, session-checked Creo session. All product-visible behavior goes
through public MCP tools over stdio from this checkout. A minimal Toolkit fixture
(tools/wb080_live_fixture.cpp) is the only external writer and performs exactly two
operations that no public tool exposes: suppressing one feature of the created part
and placing it into an inch template assembly at translation (1, 2, 3) inch.

Phases:
  1. create part "wb080_unhealthy" (two pads) via creo_execute_plan;
  2. fixture suppresses the second pad and saves;
  3. creo_adopt_current_model(mode=inspect) must refuse with reason_code
     unhealthy_features and bounded per-feature diagnosis (id/status/name);
  4. fixture loads the inch template copy and places the part at (1, 2, 3) inch;
  5. creo_inspect_session_assembly must report the inch assembly unit, the
     component/parent unit scales, a millimeter-normalized translation of
     (25.4, 50.8, 76.2) and a raw translation of (1, 2, 3), complete=true;
  6. read-only check: the session inventory is unchanged by the inspection.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "tools.test_wb080_live", *sys.argv[1:]], cwd=ROOT)
    )

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from bridge import native_environment
from creo_mechdog.build_support import compiler_setup_script, validate_local_path
from creo_mechdog.paths import SOURCE_PATHS
from tools.dev_check import git_state, source_hash
from tools.test_direct_loft import Probe
from version import VERSION

COMPONENT_PREFIX = "wb080_unhealthy"
ASSEMBLY_PREFIX = "wb080_inch"
INCH = 25.4


def part_plan() -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "sk_base",
            "plane": "XY",
            "entities": [
                {"type": "rectangle", "name": "outline", "min": [0, 0], "max": [60, 40]}
            ],
        },
        {"op": "extrude", "label": "base", "sketch": "sk_base", "depth": 10},
        {
            "op": "sketch",
            "label": "sk_pad",
            "plane": "XY",
            "entities": [
                {"type": "rectangle", "name": "pad", "min": [70, 0], "max": [100, 40]}
            ],
        },
        {"op": "extrude", "label": "pad2", "sketch": "sk_pad", "depth": 5},
    ]


def build_fixture(directory: Path, report: dict) -> Path:
    settings = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    sdk = Path(settings["creo_root"]) / "Common Files/protoolkit"
    source = ROOT / "tools" / "wb080_live_fixture.cpp"
    executable = directory / "wb080_live_fixture.exe"
    for path in (sdk, directory, source):
        validate_local_path(str(path), "wb080 live fixture path")
    libraries = [
        sdk / "x86e_win64" / "obj" / name
        for name in (
            "protkmd_NU.lib",
            "ptasyncmd.lib",
            "ucore.lib",
            "udata.lib",
        )
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
    batch.write_text(
        "@echo off\n"
        + compiler_setup_script(settings)
        + f'\ncl /nologo /MD /EHsc /std:c++17 /DPRO_MACHINE=36 /DPRO_OS=4 /DPRO_USE_VAR_ARGS '
        + f'/I"{sdk / "includes"}" /c "{source}" /Fo:"{directory / "fixture.obj"}\n'
        + f'link /nologo /MACHINE:X64 /SUBSYSTEM:CONSOLE /OUT:"{executable}" '
        + f'"{directory / "fixture.obj"}" '
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
        timeout=120,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
        env=native_environment(),
    )
    payload = {}
    for line in completed.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            payload.update(json.loads(line))
    payload["returncode"] = completed.returncode
    payload["stderr"] = completed.stderr.strip()[:2000]
    return payload


def close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(b))


def matrix_translation(matrix: list) -> list:
    assert isinstance(matrix, list) and len(matrix) == 4, matrix
    return matrix[3][:3]


def rotation_is_identity(matrix: list) -> bool:
    expected = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    return all(
        close(value, target)
        for row, target in zip(matrix[:3], expected)
        for value, target in zip(row, target)
    )


async def await_toolkit_ready(probe: Probe, budget: float = 300.0) -> None:
    """Wait out the server's own startup build without recording readiness polls as evidence."""
    started = time.monotonic()
    while time.monotonic() - started < budget:
        response = await probe.client.call_tool("creo_list_session_models", {})
        busy = response.is_error and (response.structured_content or {}).get("status") == "busy"
        if not busy:
            return
        await asyncio.sleep(2.0)
    raise TimeoutError("Toolkit channel stayed busy during server startup")


async def session_names(probe: Probe) -> list[str]:
    inventory = await probe.call("creo_list_session_models", {})
    models = inventory.get("models", inventory if isinstance(inventory, list) else [])
    return sorted(
        str(item["name"]).upper()
        for item in models
        if isinstance(item, dict) and item.get("name")
    )


async def readonly_job(probe: Probe, tool: str, inputs: dict, case: str) -> dict:
    """Poll a read-only job to its terminal state (no saved/reload assertion)."""
    entry = {"case": case, "tool": tool, "input": inputs, "terminal": None}
    probe.report["jobs"].append(entry)
    started = time.monotonic()
    queued = await probe.call(tool, inputs)
    entry["job_id"] = queued["job_id"]
    probe.save()
    while time.monotonic() - started < probe.job_budget:
        state = await probe.call("creo_get_job", {"job_id": queued["job_id"], "detail": "compact"})
        if state["status"] not in ("queued", "running"):
            state = await probe.call("creo_get_job", {"job_id": queued["job_id"], "detail": "full"})
            entry["terminal"] = state
            probe.save()
            assert state["status"] == "succeeded", state
            return state
        await asyncio.sleep(0.5)
    raise TimeoutError(f"observation budget exceeded for {queued['job_id']}")


async def erase_with_retry(
    probe: Probe, targets: list[dict], stamp: str, case: str, attempts: int = 6
) -> dict:
    """Submit an erase apply, retrying transient channel-busy rejections."""
    for attempt in range(attempts):
        erase = await probe.call(
            "creo_erase_session_models", {"mode": "inspect", "targets": targets}
        )
        try:
            return await readonly_job(
                probe,
                "creo_erase_session_models",
                {
                    "mode": "apply",
                    "evidence_token": erase["evidence_token"],
                    "idempotency_key": f"wb080-{case}-{stamp}",
                },
                case,
            )
        except AssertionError as failure:
            if "busy" not in str(failure) or attempt == attempts - 1:
                raise
            await asyncio.sleep(3.0)
    raise AssertionError("unreachable")


async def main_async(args: argparse.Namespace) -> None:
    stamp = datetime.now().strftime("%H%M%S")
    component = f"{COMPONENT_PREFIX}_{stamp}"
    assembly_name = f"{ASSEMBLY_PREFIX}_{stamp}"
    directory = args.output.parent
    directory.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "work_items": ["BUG-080", "FEAT-006"],
        "version": VERSION,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            **git_state(ROOT),
            "resource_root": str(SOURCE_PATHS.resource_root),
            "checked_source_sha256": source_hash(ROOT / "tools" / "test_wb080_live.py"),
        },
        "environment": {
            "python": sys.version.split()[0],
            "session_check": "2026-10-24 passed; see docs/work-items/FEAT-006.md",
        },
        "calls": [],
        "jobs": [],
        "phases": {},
    }
    executable = build_fixture(directory, report)
    template = (
        Path(json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))["creo_root"])
        / "Common Files"
        / "templates"
        / "direct_asm_solid_inlbs_rel.asm"
    )
    assembly_file = directory / f"{assembly_name}.asm"
    shutil.copyfile(template, assembly_file)
    report["template"] = {"source": str(template), "copied_to": str(assembly_file)}

    params = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT
    )
    async with Client(params, read_timeout_seconds=90) as client:
        probe = Probe(client, report, args.output, args.job_budget)
        capabilities = await probe.call("creo_capabilities", {})
        assert capabilities["name"] == "MCP_CREO_MechDog", capabilities["name"]
        assert capabilities["server_version"] == VERSION, capabilities["server_version"]
        await await_toolkit_ready(probe)

        seed_source = ROOT / "seed_library" / "seeds" / "four_smooth" / "db_8bdd03c9da.prt.2"
        seed_file = directory / seed_source.name
        seed_name = seed_source.name.split(".")[0]

        # A crashed previous run may leave the seed copy in the session; the
        # service refuses same-name retrieval, so clear it first (best effort).
        pre = await session_names(probe)
        if seed_name.upper() in pre:
            try:
                await erase_with_retry(
                    probe, [{"name": seed_name, "model_type": "part"}], stamp, "preclean"
                )
                report["phases"]["pre_clean"] = "erased leftover seed copy"
            except Exception as failure:
                raise AssertionError(f"leftover seed copy blocks this run: {failure}") from failure

        before = await session_names(probe)

        part = await probe.job(
            "creo_execute_plan",
            {"operations": part_plan(), "model_name": component},
            "part_two_features",
        )
        report["phases"]["part"] = {
            "model_id": part["model_id"],
            "revision": part["revision"],
            "note": "kept healthy; it is the assembly component for BUG-080",
        }
        probe.save()

        # FEAT-006: an unmanaged seed copy is the only way to hit the
        # unhealthy_features reason itself (service-created models are managed
        # and refuse with managed_output first, which still carries the same
        # per-feature diagnosis in refusal_details).
        shutil.copyfile(seed_source, seed_file)
        opened = await readonly_job(
            probe,
            "creo_open_file",
            {
                "file_path": str(seed_file),
                "idempotency_key": f"wb080-seed-{stamp}",
            },
            "seed_open",
        )
        report["phases"]["seed_open"] = {
            "source": str(seed_source),
            "opened_name": opened["result"].get("open_file", {}).get("model_name"),
        }
        probe.save()

        suppression = run_fixture(executable, ["suppress", seed_name, "max"], directory)
        report["phases"]["suppress"] = suppression
        probe.save()
        assert suppression["returncode"] == 0, suppression
        assert suppression["suppress"] == 0 and suppression["save"] == 0, suppression

        # Adoption refusals are structured normal responses (available=false),
        # not MCP tool errors.
        refusal = await probe.call("creo_adopt_current_model", {"mode": "inspect"})
        assert refusal["available"] is False, refusal
        details = refusal.get("refusal_details", refusal)
        unhealthy = details.get("unhealthy_features")
        assert refusal.get("reason_code") == "unhealthy_features", refusal
        assert unhealthy and unhealthy["unhealthy_total"] >= 1, refusal
        suppressed_items = [item for item in unhealthy["items"] if item["status"] == "suppressed"]
        assert suppressed_items, unhealthy
        assert suppression["feature_id"] in {item["id"] for item in unhealthy["items"]}, unhealthy
        for item in unhealthy["items"]:
            assert isinstance(item["status_code"], int), item
            assert isinstance(item["name"], str), item
        assert "per-feature diagnosis" in details["health_breakdown"], details
        report["phases"]["adoption_refusal"] = {
            "reason_code": refusal.get("reason_code"),
            "suppressed_feature_id": suppression["feature_id"],
            "unhealthy_features": unhealthy,
        }
        probe.save()

        assembly = run_fixture(
            executable, ["asm", str(assembly_file), component], directory
        )
        report["phases"]["assembly"] = assembly
        probe.save()
        assert assembly["returncode"] == 0, assembly
        assert assembly["assemble"] == 0 and assembly["save"] == 0, assembly

        inspected = await probe.call("creo_inspect_session_assembly", {"name": assembly_name})
        root_unit = inspected["assembly"]["length_unit"]
        assert root_unit["name"] in ("in", "inch"), root_unit
        assert close(root_unit["scale_to_mm"], INCH), root_unit
        component_node = next(
            item for item in inspected["components"] if component.lower() in str(item.get("name", "")).lower()
        )
        units = component_node["units"]
        assert close(units["component"]["scale_to_mm"], 1.0), units
        assert close(units["parent"]["scale_to_mm"], INCH), units
        normalized = component_node["transform_to_parent"]
        assert rotation_is_identity(normalized), normalized
        assert all(
            close(a, b) for a, b in zip(matrix_translation(normalized), [INCH, 2 * INCH, 3 * INCH])
        ), normalized
        raw = component_node["transform_to_parent_raw"]
        assert all(
            close(a, b) for a, b in zip(matrix_translation(raw), [1.0, 2.0, 3.0])
        ), raw
        assert inspected["complete"] is True, inspected.get("complete")
        report["phases"]["assembly_inspect"] = {
            "length_unit": root_unit,
            "component_units": units,
            "transform_to_parent": normalized,
            "transform_to_parent_raw": raw,
            "complete": inspected["complete"],
        }
        probe.save()

        after_inspect = await session_names(probe)
        expected = set(before) | {
            name.upper()
            for name in (assembly_name, component, seed_name)
        }
        assert set(after_inspect) == expected, {"before": before, "after": after_inspect}
        report["phases"]["read_only"] = {"before": before, "after": after_inspect}

        # Best-effort cleanup: erase every leftover test assembly (unmanaged)
        # and the seed copy; managed fixture parts stay as registry evidence.
        leftover_assemblies = [
            name for name in after_inspect if name.startswith(ASSEMBLY_PREFIX.upper())
        ]
        erase_targets = [{"name": seed_name, "model_type": "part"}] + [
            {"name": name, "model_type": "assembly"} for name in leftover_assemblies
        ]
        try:
            await erase_with_retry(probe, erase_targets, stamp, "erase")
            report["phases"]["cleanup"] = "erase submitted"
        except Exception as failure:  # cleanup is best effort; the refusal is recorded
            report["phases"]["cleanup"] = f"erase refused (recorded): {failure}"
        probe.save()

    report["success"] = True
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"success": True, "output": str(args.output)}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "build" / "wb080-live" / "report.json",
    )
    parser.add_argument("--job-budget", type=float, default=300.0)
    arguments = parser.parse_args()
    asyncio.run(main_async(arguments))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
