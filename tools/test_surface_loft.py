"""FEAT-009/H02 surface loft driver: the minimal two-section boundary blend.

Default mode is offline: it validates the published contract (schema admission,
capability registration and the unchanged solid-loft semantics) without any
Creo session. ``--live --confirm-session-usable`` runs the live oracle through
public MCP tools only:

* two 40 mm straight sections 20 mm apart produce one open quilt of
  800.0 mm2 (+/- 0.5), measured, saved and reloaded with an unchanged id/area;
* no solid is created by the loft;
* ``surface_trim`` with a datum plane at x=20 leaves 400.0 mm2 (+/- 0.5) on
  each side (one run per side, separate models);
* ``thicken`` the 800 mm2 quilt by 2 mm measures 1600 mm3 (+/- 0.5).

Usage (PowerShell, repo root):
  .venv\\Scripts\\python.exe tools\\test_surface_loft.py
  .venv\\Scripts\\python.exe tools\\test_surface_loft.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AREA_TOLERANCE_MM2 = 0.5
VOLUME_TOLERANCE_MM3 = 0.5


def loft_plan(keep_side: str | None = None) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = [
        {
            "op": "sketch",
            "label": "loft_a",
            "plane": "XY",
            "entities": [
                {"type": "line", "name": "section_a", "start": [0.0, 0.0], "end": [40.0, 0.0]}
            ],
        },
        {
            "op": "sketch",
            "label": "loft_b",
            "plane": "XY",
            "offset": 20.0,
            "entities": [
                {"type": "line", "name": "section_b", "start": [0.0, 0.0], "end": [40.0, 0.0]}
            ],
        },
        {"op": "surface_loft", "label": "loft_surface", "sections": ["loft_a", "loft_b"]},
    ]
    if keep_side:
        plan.extend(
            [
                {
                    "op": "datum_plane",
                    "label": "trim_x",
                    "reference": {"kind": "datum_plane", "axis": "x", "offset": 0},
                    "offset": 20.0,
                },
                {
                    "op": "surface_trim",
                    "label": "loft_trimmed",
                    "target": {"kind": "quilt_feature", "label": "loft_surface"},
                    "tool": {"kind": "datum_plane", "label": "trim_x"},
                    "keep_side": keep_side,
                },
            ]
        )
    return plan


THICKEN_PLAN: list[dict[str, Any]] = [
    {
        "op": "thicken",
        "label": "loft_solid",
        "reference": {"kind": "quilt_feature", "label": "loft_surface"},
        "thickness": 2.0,
        "side": "symmetric",
    }
]


def case_offline() -> dict:
    from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS
    from creo_mechdog.schema import validate_operations

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    valid = loft_plan()
    try:
        validate_operations(valid)
        check("schema_accepts_two_section_surface_loft", True)
    except ValueError as error:
        check("schema_accepts_two_section_surface_loft", False, {"error": str(error)})

    rejected = {
        "three_sections": {
            "op": "surface_loft",
            "label": "loft_surface",
            "sections": ["a", "b", "c"],
        },
        "one_section": {"op": "surface_loft", "label": "loft_surface", "sections": ["a"]},
        "smooth": {
            "op": "surface_loft",
            "label": "loft_surface",
            "sections": ["a", "b"],
            "interpolation": "smooth",
        },
        "duplicate_sections": {
            "op": "surface_loft",
            "label": "loft_surface",
            "sections": ["a", "a"],
        },
        "closed": {
            "op": "surface_loft",
            "label": "loft_surface",
            "sections": ["a", "b"],
            "closed": True,
        },
        "continuity": {
            "op": "surface_loft",
            "label": "loft_surface",
            "sections": ["a", "b"],
            "continuity": "G1",
        },
        "solid_output": {
            "op": "surface_loft",
            "label": "loft_surface",
            "sections": ["a", "b"],
            "mode": "add",
        },
    }
    for name, operation in rejected.items():
        try:
            validate_operations([operation])
            check(f"schema_rejects_{name}", False, {"reason": "accepted"})
        except ValueError as error:
            check(f"schema_rejects_{name}", True, {"error": str(error)[:160]})

    for operation in (
        {"op": "loft", "label": "solid_loft", "sections": ["a", "b"], "mode": "surface"},
        {
            "op": "loft",
            "label": "solid_loft",
            "sections": ["a", "b"],
            "new_body": True,
        },
    ):
        try:
            validate_operations([operation])
            from creo_mechdog.capabilities import require_available

            require_available([operation])
            check("solid_loft_unchanged", False, {"reason": "surface/new_body accepted"})
        except ValueError:
            check("solid_loft_unchanged", True)

    check("operation_registered", "surface_loft" in REGISTERED_OPERATIONS)
    check("operation_published", "surface_loft" not in UNAVAILABLE_OPERATIONS)
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    check("server_tool_registered", "async def creo_surface_loft(" in server)
    native = (ROOT / "native" / "surface_loft.cpp").read_text(encoding="utf-8")
    check("native_entry_point", "static void generic_surface_loft(const J &op)" in native)
    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_surface_loft": "not_run",
        "checks": checks,
    }


async def wait_ready(client, budget_seconds: int = 210) -> dict:
    deadline = time.monotonic() + budget_seconds
    state: dict = {}
    retry = True
    while time.monotonic() < deadline:
        state = (await client.call_tool("creo_startup_status", {"retry": retry})).structured_content
        retry = False
        if state.get("connected"):
            return state
        if state.get("state") in ("timeout", "failed", "error", "blocked", "unavailable"):
            return state
        await asyncio.sleep(2)
    return state


async def call_tool(client, tool: str, arguments: dict) -> dict:
    result = await client.call_tool(tool, arguments)
    if result.structured_content is not None:
        return result.structured_content
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text[:600]}
    return {}


async def submit(client, operation_plan: list[dict], model_id=None, revision=None) -> dict:
    arguments: dict = {"operations": operation_plan}
    if model_id:
        arguments["model_id"] = model_id
        arguments["expected_revision"] = revision
    submitted = await call_tool(client, "creo_execute_plan", arguments)
    job_id = submitted.get("job_id")
    if not job_id:
        return {"status": "refused", "message": str(submitted)[:600]}
    deadline = time.monotonic() + 900
    state: dict = {}
    while time.monotonic() < deadline:
        state = await call_tool(client, "creo_get_job", {"job_id": job_id, "detail": "compact"})
        if state.get("status") in ("succeeded", "failed", "unknown_outcome"):
            break
        await asyncio.sleep(2)
    else:
        return {"status": "unsettled", "job_id": job_id, "message": "job did not settle"}
    # The compact projection keeps the operation criteria under a 32 KiB budget,
    # which is what a large result needs; the full page is paginated and would
    # have to be stitched from several calls.
    view = await call_tool(
        client,
        "creo_get_job",
        {"job_id": job_id, "detail": "compact", "sections": ["operations"]},
    )
    if view.get("status"):
        state = view
    state["job_id"] = job_id
    return state


def operation_of(state: dict, op: str) -> dict:
    operations = (state.get("result") or {}).get("operations") or state.get("operations") or []
    for operation in operations:
        if operation.get("op") == op:
            return operation
    return {}


def saved_verified(state: dict) -> bool:
    result = state.get("result") or {}
    return bool(
        result.get("saved_file_reloaded_and_verified")
        or state.get("saved_file_reloaded_and_verified")
    )


async def model_section(client, model_id: str, name: str, limit: int = 200) -> list:
    page = await call_tool(
        client,
        "creo_inspect_model",
        {"model_id": model_id, "detail": "full", "section": name, "limit": limit},
    )
    return (page.get("data") or {}).get(name) or []


async def case_live() -> dict:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    checks: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    def remember(state: dict) -> None:
        jobs.append(
            {
                "job_id": state.get("job_id"),
                "status": state.get("status"),
                "model_id": state.get("model_id"),
                "revision": state.get("revision"),
                "message": str(state.get("message"))[:300],
            }
        )

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        check(
            "session_ready",
            bool(started.get("connected")),
            {"state": started.get("state"), "message": str(started.get("message"))[:200]},
        )
        if not started.get("connected"):
            return {
                "mode": "live",
                "passed": False,
                "native_surface_loft": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
                "jobs": jobs,
            }

        capabilities = await call_tool(client, "creo_capabilities", {})
        published = "surface_loft" in (capabilities.get("operations") or [])
        check("surface_loft_published", published)
        if not published:
            return {
                "mode": "live",
                "passed": False,
                "native_surface_loft": "gated",
                "note": "surface_loft is refused before any job; no geometry was submitted",
                "checks": checks,
                "jobs": jobs,
            }

        # 1) The boundary blend itself, on a fresh model.
        build = await submit(client, loft_plan())
        remember(build)
        check(
            "loft_job_succeeded",
            build.get("status") == "succeeded",
            {"status": build.get("status"), "message": str(build.get("message"))[:400]},
        )
        if build.get("status") != "succeeded":
            return {
                "mode": "live",
                "passed": False,
                "native_surface_loft": "failed",
                "checks": checks,
                "jobs": jobs,
                "failure": (operation_of(build, "surface_loft") or build.get("message")),
            }
        model_id = build["model_id"]
        revision = build.get("revision")
        loft = operation_of(build, "surface_loft")
        check("saved_file_reloaded_and_verified", saved_verified(build))
        check(
            "surface_type_is_datum_surface",
            loft.get("surface_type") == "datum_surface",
            loft.get("surface_type"),
        )
        check(
            "feature_type_is_datum_surface",
            loft.get("feature_type") == 942,
            loft.get("feature_type"),
        )
        check("exactly_one_quilt_item", loft.get("quilt_count") == 1, loft.get("quilt_count"))
        quilt_id = loft.get("quilt_id")
        check("quilt_id_present", isinstance(quilt_id, int), quilt_id)
        area = loft.get("surface_area_mm2")
        check(
            "measured_area_800",
            isinstance(area, (int, float)) and abs(area - 800.0) <= AREA_TOLERANCE_MM2,
            {"surface_area_mm2": area},
        )
        check(
            "quilt_is_open",
            loft.get("quilt_closed_native") == "open",
            loft.get("quilt_closed_native"),
        )
        check("no_solid_created", loft.get("has_solid") is False, loft.get("has_solid"))

        # Saved/reloaded identity: the model's own quilt collection after the job.
        quilts = await model_section(client, model_id, "quilts")
        check("model_has_exactly_one_quilt", len(quilts) == 1, {"quilt_count": len(quilts)})
        reloaded = quilts[0] if quilts else {}
        check(
            "quilt_id_stable_after_reload",
            reloaded.get("quilt_id") == quilt_id,
            reloaded.get("quilt_id"),
        )
        reloaded_area = reloaded.get("area_mm2")
        check(
            "area_stable_after_reload",
            isinstance(reloaded_area, (int, float))
            and abs(reloaded_area - 800.0) <= AREA_TOLERANCE_MM2,
            {"area_mm2": reloaded_area},
        )

        # 2) trim at x=20 (side one) while the model still holds only the open
        # quilt; a thicken would consume the quilt for a later trim.
        trim_one = await submit(client, loft_plan(keep_side="one")[3:], model_id, revision)
        remember(trim_one)
        trimmed = operation_of(trim_one, "surface_trim")
        area_after = trimmed.get("area_after_mm2")
        check(
            "trim_one_job_succeeded",
            trim_one.get("status") == "succeeded",
            {"status": trim_one.get("status"), "message": str(trim_one.get("message"))[:400]},
        )
        check(
            "trim_one_area_400",
            isinstance(area_after, (int, float)) and abs(area_after - 400.0) <= AREA_TOLERANCE_MM2,
            {"area_after_mm2": area_after},
        )

        # 3) A fresh model: build the loft, then thicken the 800 mm2 open quilt
        # by 2 mm -> 1600 mm3.
        thicken_model = await submit(client, loft_plan())
        remember(thicken_model)
        check(
            "thicken_base_loft_succeeded",
            thicken_model.get("status") == "succeeded",
            {
                "status": thicken_model.get("status"),
                "message": str(thicken_model.get("message"))[:400],
            },
        )
        if thicken_model.get("status") == "succeeded":
            thicken = await submit(
                client, THICKEN_PLAN, thicken_model["model_id"], thicken_model.get("revision")
            )
            remember(thicken)
            thickened = operation_of(thicken, "thicken")
            volume = thickened.get("volume_after_mm3")
            check(
                "thicken_job_succeeded",
                thicken.get("status") == "succeeded",
                {"status": thicken.get("status"), "message": str(thicken.get("message"))[:400]},
            )
            check(
                "thicken_volume_1600",
                isinstance(volume, (int, float)) and abs(volume - 1600.0) <= VOLUME_TOLERANCE_MM3,
                {"volume_after_mm3": volume},
            )

        # 4) The other side of the same x=20 cut, on its own model.
        second = await submit(client, loft_plan(keep_side="two"))
        remember(second)
        second_trim = operation_of(second, "surface_trim")
        second_area = second_trim.get("area_after_mm2")
        check(
            "trim_two_job_succeeded",
            second.get("status") == "succeeded",
            {"status": second.get("status"), "message": str(second.get("message"))[:400]},
        )
        check(
            "trim_two_area_400",
            isinstance(second_area, (int, float))
            and abs(second_area - 400.0) <= AREA_TOLERANCE_MM2,
            {"area_after_mm2": second_area},
        )
        check(
            "two_sides_sum_to_800",
            isinstance(area_after, (int, float))
            and isinstance(second_area, (int, float))
            and abs(area_after + second_area - 800.0) <= 1.0,
            {"one": area_after, "two": second_area},
        )

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_surface_loft": "verified" if passed else "failed",
        "checks": checks,
        "jobs": jobs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.live and not args.confirm_session_usable:
        print("live runs require --confirm-session-usable", file=sys.stderr)
        return 2

    report = asyncio.run(case_live()) if args.live else case_offline()
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    output = args.output or ROOT / "build" / "surface_loft" / run_id / "report.json"
    if output.exists():
        print(f"refusing to overwrite {output}", file=sys.stderr)
        return 3
    report["run_id"] = run_id
    report["report_path"] = str(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
