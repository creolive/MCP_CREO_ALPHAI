"""FEAT-031 T13 driver: offline fixture report, or the live bundle round trip."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import sys
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.unit import test_assembly_bundle as fixture  # noqa: E402
from tools.sheetmetal_live import (  # noqa: E402
    LiveRunner,
    failure_text,
    require_manual_start,
    unique_name,
)

HANG_BUDGET_SECONDS = 180.0


def box_plan(low: list[float], high: list[float], depth: float) -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "box_sketch",
            "plane": "XY",
            "entities": [{"type": "rectangle", "name": "box", "min": low, "max": high}],
        },
        {
            "op": "extrude",
            "label": "box",
            "sketch": "box_sketch",
            "depth": depth,
            "mode": "add",
            "direction": "positive",
            "depth_type": "blind",
        },
    ]


def component_summary(payload: dict) -> list[dict]:
    rows = []
    for item in payload.get("components") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "label": item.get("label"),
                "identity": item.get("identity"),
                "translation": item.get("translation") or item.get("transform"),
                "name": item.get("name") or item.get("component_name"),
            }
        )
    return rows


async def create_model(
    runner: LiveRunner, tag: str, model_type: str, operations: list[dict]
) -> dict:
    name = unique_name(tag)
    created = await runner.submit(
        f"{tag}:create",
        "creo_execute_plan",
        {"model_name": name, "model_type": model_type, "operations": operations},
    )
    terminal = await runner.wait_job(created["job_id"], budget=HANG_BUDGET_SECONDS)
    return {"name": name, "created": created, "terminal": terminal}


async def run_reimport(bundle_dir: Path, output: Path | None, expected: Path) -> int:
    """Open an existing bundle from a new directory in a session without that assembly.

    Creo refuses to retrieve an assembly whose name is already loaded, and a managed
    model cannot be erased through creo_erase_session_models (the inspect step answers
    available=false). The live round trip therefore has to split: export in one
    session, then run this half after the operator restarts Creo, so the retrieval
    starts from an empty session and the bundle is proven independently of the export.
    """
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    manifest_path = bundle_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    want = json.loads(Path(expected).read_text(encoding="utf-8"))["cases"][0]["components_before"]
    run_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    target = output or ROOT / "build" / "assembly_bundle" / f"{run_id}_reimport" / "report.json"
    fresh_root = target.parent / "reimport"
    fresh_root.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    files = manifest.get("files") or []
    if not manifest.get("complete"):
        problems.append("manifest is not complete")
    if not files:
        problems.append("manifest lists no files")
    for item in files:
        relative = item.get("relative_path") or item.get("path")
        candidate = bundle_dir / str(relative)
        if not candidate.is_file():
            problems.append(f"missing bundle file {relative}")
            continue
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != item.get("sha256"):
            problems.append(f"sha256 mismatch for {relative}")
        shutil.copy2(candidate, fresh_root / candidate.name)
    root = manifest.get("root") or next(
        (item.name for item in fresh_root.iterdir() if item.suffix.lower() in (".asm", ".prt")),
        None,
    )
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=180) as client:
        runner = LiveRunner(
            client, target, "FEAT-031 / DEV-051 T13", "re-import an existing bundle", run_id
        )
        await runner.start()
        entry: dict = {
            "case": "reimport_only",
            "bundle": str(bundle_dir),
            "bundle_root": root,
            "files": len(files),
            "expected_components": want,
        }
        opened = await runner.submit(
            "reimport:open",
            "creo_open_file",
            {"file_path": str((fresh_root / root).resolve()), "idempotency_key": uuid.uuid4().hex},
        )
        terminal = await runner.wait_job(opened["job_id"], budget=HANG_BUDGET_SECONDS)
        entry["open_job_id"] = opened["job_id"]
        entry["open_status"] = terminal.get("status")
        if terminal.get("status") != "succeeded":
            entry["open_failure"] = failure_text(terminal)
            problems.append("re-opened assembly did not load")
        else:
            session = await runner.call("creo_inspect_session_assembly", {"name": Path(root).stem})
            components = session.get("components") or []
            entry["session"] = {
                key: (session.get("assembly") or {}).get(key)
                for key in ("name", "origin", "model_type", "modified")
            }
            entry["components_after"] = [
                {
                    "name": item.get("name"),
                    "label": item.get("occurrence_label"),
                    "resolved": item.get("resolved"),
                    "transform": item.get("transform_to_parent"),
                }
                for item in components
            ]
            if len(components) != len(want):
                problems.append(f"component count {len(components)} != {len(want)}")
            for expected_row, actual in zip(want, components):
                if (expected_row.get("translation") or []) != (
                    actual.get("transform_to_parent") or []
                ):
                    problems.append(f"transform mismatch for {expected_row.get('label')}")
                if actual.get("resolved") is not True:
                    problems.append(f"component {expected_row.get('label')} is not resolved")
        entry["manifest_problems"] = problems
        entry["passed"] = not problems
        runner.case(entry)
        runner.finish()
    print(json.dumps({"passed": not problems, "problems": problems}, ensure_ascii=False))
    return 0 if not problems else 1


async def run_live(output: Path | None) -> int:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    run_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    target = output or ROOT / "build" / "assembly_bundle" / run_id / "report.json"
    if target.exists():
        raise SystemExit(f"refusing to overwrite {target}")
    fresh_root = target.parent / "reimport"
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=180) as client:
        runner = LiveRunner(
            client,
            target,
            "FEAT-031 / DEV-051 T13",
            "two-part assembly: native_bundle export, manifest check, copy to a fresh directory "
            "and re-open",
            run_id,
        )
        try:
            await runner.start()
            runner.report["hang_budget_seconds"] = HANG_BUDGET_SECONDS
            first = await create_model(
                runner, "t13_src_a", "part", box_plan([0.0, 0.0], [50.0, 40.0], 10.0)
            )
            second = await create_model(
                runner, "t13_src_b", "part", box_plan([70.0, 0.0], [90.0, 20.0], 5.0)
            )
            entry: dict = {
                "case": "export_bundle",
                "sources": {
                    "a": first["created"]["model_id"],
                    "b": second["created"]["model_id"],
                },
            }
            if (
                first["terminal"].get("status") != "succeeded"
                or second["terminal"].get("status") != "succeeded"
            ):
                entry.update(failure="source part failed", passed=False)
                runner.case(entry)
            else:
                assembly = await create_model(
                    runner,
                    "t13_asm",
                    "assembly",
                    [
                        {
                            "op": "assemble_component",
                            "label": "part_alpha",
                            "source_model_id": first["created"]["model_id"],
                            "placement": "fixed",
                        },
                        {
                            "op": "assemble_component",
                            "label": "part_beta",
                            "source_model_id": second["created"]["model_id"],
                            "placement": "fixed",
                            "translation": [100.0, 0.0, 0.0],
                        },
                    ],
                )
                model_id = assembly["created"]["model_id"]
                entry.update(
                    assembly_model_id=model_id,
                    assembly_name=assembly["name"],
                    assembly_job_id=assembly["created"]["job_id"],
                    assembly_status=assembly["terminal"].get("status"),
                )
                if assembly["terminal"].get("status") != "succeeded":
                    entry.update(failure=failure_text(assembly["terminal"]), passed=False)
                    runner.case(entry)
                else:
                    before = await runner.call("creo_list_components", {"model_id": model_id})
                    entry["components_before"] = component_summary(before)
                    entry["revision_before"] = before.get("revision")
                    exported = await runner.submit(
                        "export:native_bundle",
                        "creo_export_model",
                        {"model_id": model_id, "format": "native_bundle"},
                    )
                    terminal = await runner.wait_job(exported["job_id"], budget=HANG_BUDGET_SECONDS)
                    result = terminal.get("result") or {}
                    bundle = result.get("native_bundle") or {}
                    entry.update(
                        export_job_id=exported["job_id"],
                        export_status=terminal.get("status"),
                        bundle=bundle,
                    )
                    manifest_path = Path(str(bundle.get("manifest") or ""))
                    problems: list[str] = []
                    if terminal.get("status") != "succeeded":
                        problems.append("export job did not succeed")
                    if not bundle.get("complete"):
                        problems.append("bundle reported incomplete")
                    if not manifest_path.is_file():
                        problems.append("manifest file missing")
                    manifest = {}
                    if manifest_path.is_file():
                        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                        entry["manifest"] = manifest
                        files = manifest.get("files") or []
                        if manifest.get("schema") != 1:
                            problems.append("manifest schema is not 1")
                        if not files:
                            problems.append("manifest lists no files")
                        for item in files:
                            relative = item.get("relative_path") or item.get("path")
                            if not relative:
                                problems.append("manifest file without relative path")
                                continue
                            candidate = manifest_path.parent / relative
                            if not candidate.is_file():
                                problems.append(f"missing bundle file {relative}")
                                continue
                            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
                            if digest != item.get("sha256"):
                                problems.append(f"sha256 mismatch for {relative}")
                    root_file = manifest.get("root")
                    reopened: dict = {}
                    # A partial bundle is not a deliverable: the target fails
                    # immediately and an incomplete package is never fed back
                    # into a session. Only a complete bundle prepares the
                    # re-import.
                    if not (bundle.get("complete") and not problems):
                        problems.append("incomplete bundle: re-import refused")
                        reopened["skipped"] = "incomplete_bundle"
                    elif root_file:
                        # The export job loaded its own assembly into this session and the
                        # bundle root carries that same name, so opening the copy would be
                        # refused with SESSION_NAME_CONFLICT (2026-10-30 live run). Erase
                        # exactly this run's exported root - the driver's own artifact -
                        # before the re-import; no other session model is touched, and an
                        # unavailable target fails the case instead of skipping the check.
                        erase_target = [{"name": Path(root_file).stem, "model_type": "assembly"}]
                        probe = await runner.call(
                            "creo_erase_session_models",
                            {"mode": "inspect", "targets": erase_target},
                        )
                        erase_summary = probe.get("session_erase") or {}
                        reopened["erase_inspect"] = {
                            "available": erase_summary.get("available"),
                            "erase_order": erase_summary.get("erase_order"),
                        }
                        if not (erase_summary.get("available") and probe.get("evidence_token")):
                            problems.append(
                                "the exported assembly was not erasable, so the re-import "
                                "would collide with the session name"
                            )
                        else:
                            applied = await runner.call(
                                "creo_erase_session_models",
                                {
                                    "mode": "apply",
                                    "evidence_token": probe["evidence_token"],
                                    "idempotency_key": uuid.uuid4().hex,
                                },
                            )
                            erased = await runner.wait_job(
                                applied["job_id"], budget=HANG_BUDGET_SECONDS
                            )
                            reopened["erase_job_id"] = applied["job_id"]
                            reopened["erase_status"] = erased.get("status")
                            if erased.get("status") != "succeeded":
                                problems.append(
                                    "the exported assembly could not be erased before re-import"
                                )
                        fresh_root.mkdir(parents=True, exist_ok=True)
                        for item in Path(str(bundle.get("directory"))).iterdir():
                            if item.is_file():
                                shutil.copy2(item, fresh_root / item.name)
                        opened = await runner.submit(
                            "reimport:open",
                            "creo_open_file",
                            {
                                "file_path": str((fresh_root / root_file).resolve()),
                                "idempotency_key": uuid.uuid4().hex,
                            },
                        )
                        opened_terminal = await runner.wait_job(
                            opened["job_id"], budget=HANG_BUDGET_SECONDS
                        )
                        reopened.update(
                            open_job_id=opened["job_id"],
                            open_status=opened_terminal.get("status"),
                            open_failure=failure_text(opened_terminal)
                            if opened_terminal.get("status") != "succeeded"
                            else None,
                        )
                        stem = Path(root_file).stem
                        if opened_terminal.get("status") == "succeeded":
                            session = await runner.call(
                                "creo_inspect_session_assembly", {"name": stem}
                            )
                            reopened["session_component_count"] = len(
                                session.get("components") or []
                            )
                            reopened["session_components"] = component_summary(session)
                            reopened["session"] = {
                                key: session.get(key)
                                for key in ("name", "path", "revision", "component_count")
                            }
                        expected_count = len(entry["components_before"])
                        if reopened.get("open_status") != "succeeded":
                            problems.append("re-opened assembly did not load")
                        if reopened.get("session_component_count") != expected_count:
                            problems.append(
                                "re-opened component count "
                                f"{reopened.get('session_component_count')!r} != {expected_count}"
                            )
                    entry["reimport"] = reopened
                    entry["manifest_problems"] = problems
                    entry["passed"] = not problems
                    runner.case(entry)
        except BaseException as error:
            runner.report["stopped"] = f"{type(error).__name__}: {error}"
            runner.finish()
            raise
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    rows = [
        {
            key: case.get(key)
            for key in (
                "case",
                "export_status",
                "manifest_problems",
                "reimport",
                "passed",
            )
        }
        for case in runner.report["cases"]
    ]
    print(json.dumps({"passed": runner.report["passed"], "cases": rows}, ensure_ascii=False))
    return 0 if runner.report["passed"] else 1


def provenance() -> dict:
    from creo_mechdog.source_provenance import local_provenance

    evidence = local_provenance(
        ROOT, ("tests/unit/test_assembly_bundle.py", "tools/test_assembly_bundle.py")
    )
    return {
        "commit": evidence["commit"],
        "branch": evidence["branch"],
        "dirty": evidence["dirty"],
        "git_status": evidence["git_status"],
        "source_fingerprint": evidence["source_fingerprint"],
        "environment": evidence["environment"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--reimport",
        type=Path,
        help="open an existing bundle directory instead of exporting (needs an empty session)",
    )
    parser.add_argument(
        "--expected",
        type=Path,
        help="report from the export run; its components_before is the expected pose set",
    )
    args = parser.parse_args(argv)
    if args.reimport:
        if not args.live or not args.confirm_session_usable:
            print("--reimport needs --live --confirm-session-usable", file=sys.stderr)
            return 2
        if not args.expected:
            print("--reimport needs --expected <export report.json>", file=sys.stderr)
            return 2
        return asyncio.run(run_reimport(args.reimport, args.output, args.expected))
    if args.live:
        if not args.confirm_session_usable:
            print("live runs require --confirm-session-usable", file=sys.stderr)
            return 2
        return asyncio.run(run_live(args.output))
    suite = unittest.defaultTestLoader.loadTestsFromModule(fixture)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    report = {
        "task": "DEV-051 T13 / FEAT-031",
        "mode": "offline",
        "native_acceptance": "not_run",
        "unit": {
            "run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
        },
        "contract": {
            "root": "owned model output",
            "manifest": "native_bundle/manifest.json",
            "max_files": 128,
            "max_bytes": 536870912,
            "manifest_bytes": 32768,
        },
        "pending_live": [
            "single and nested assembly opening in a fresh directory",
            "native reference resolution",
            "source snapshots and hashes",
            "revision and save/reload",
        ],
        "provenance": provenance(),
    }
    run_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    output = args.output or ROOT / "build" / "assembly_bundle" / run_id / "report.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    output.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    output.with_suffix(".sha256").write_text(digest + "  report.json\n", encoding="ascii")
    print(json.dumps({"report": str(output), "sha256": digest, "passed": result.wasSuccessful()}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
