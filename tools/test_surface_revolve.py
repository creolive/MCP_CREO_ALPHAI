"""FEAT-039/H09 surface-of-revolution driver: the documented non-planar route.

Any non-planar closed boundary fill has no native route (``surface_fill`` is
``PRO_FLAT`` over one planar sketch, and there is no boundary-loop input at
all). The delivered alternative for a spherical centre (R8) is the existing
surface-mode revolve: one meridian arc plus one construction centreline,
rotated 360 degrees. This driver takes that route through public MCP tools and
measures the result instead of assuming it.

Default mode is offline: it validates the published contract (surface-mode
revolve admission, planar fill unchanged, capabilities registration) without a
Creo session. ``--live --confirm-session-usable`` runs the live oracle:

* a R8 meridian arc revolved 360 degrees produces one closed quilt of
  4*pi*R^2 = 804.247719... mm2, no solid, saved and reloaded with a stable
  quilt id and area;
* ``surface_trim`` with the datum plane x=4 splits that sphere into the two
  analytic caps: 2*pi*R*(R-4) = 201.061929... mm2 and the remainder;
* ``thicken`` the retained cap by 2 mm symmetric measures the exact spherical
  shell volume for that region (outer radius R+1, inner R-1), not area x 2;
* ``solidify`` of the closed sphere measures 4/3*pi*R^3;
* a ``surface_fill`` request that tries to carry a 3D boundary is refused
  before a job, so planar fill keeps its published shape.

Usage (PowerShell, repo root):
  .venv\\Scripts\\python.exe tools\\test_surface_revolve.py
  .venv\\Scripts\\python.exe tools\\test_surface_revolve.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RADIUS_MM = 8.0
CUT_PLANE_X_MM = 4.0
THICKNESS_MM = 2.0
AREA_TOLERANCE_MM2 = 0.5
VOLUME_TOLERANCE_RELATIVE = 0.02

SPHERE_AREA_MM2 = 4.0 * math.pi * RADIUS_MM**2
CAP_AREA_MM2 = 2.0 * math.pi * RADIUS_MM * (RADIUS_MM - CUT_PLANE_X_MM)
REST_AREA_MM2 = SPHERE_AREA_MM2 - CAP_AREA_MM2
SPHERE_VOLUME_MM3 = 4.0 / 3.0 * math.pi * RADIUS_MM**3


def cap_shell_volume(outer: float, inner: float, cap: bool) -> float:
    """Exact volume of the spherical shell x >= CUT_PLANE_X_MM.

    A cap of sphere radius R has height h = R - cut; V = pi*h^2*(3R-h)/3.
    The retained remainder is the full shell minus that cap.
    """

    def cap_volume(radius: float) -> float:
        height = radius - CUT_PLANE_X_MM
        return math.pi * height**2 * (3.0 * radius - height) / 3.0

    shell = 4.0 / 3.0 * math.pi * (outer**3 - inner**3)
    return (
        cap_volume(outer) - cap_volume(inner)
        if cap
        else shell - (cap_volume(outer) - cap_volume(inner))
    )


def revolve_plan() -> list[dict[str, Any]]:
    return [
        {
            "op": "sketch",
            "label": "meridian_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "centerline",
                    "name": "revolve_axis",
                    "start": [-12.0, 0.0],
                    "end": [12.0, 0.0],
                },
                {
                    "type": "arc",
                    "name": "meridian_half",
                    "center": [0.0, 0.0],
                    "radius": RADIUS_MM,
                    "start_angle": 0.0,
                    "end_angle": 180.0,
                    "dir": 1,
                },
            ],
        },
        {
            "op": "revolve",
            "label": "sphere_quilt",
            "sketch": "meridian_profile",
            "angle": 360,
            "mode": "surface",
        },
    ]


def trim_plan(keep_side: str) -> list[dict[str, Any]]:
    return [
        {
            "op": "datum_plane",
            "label": "cap_plane",
            "reference": {"kind": "datum_plane", "axis": "x", "offset": 0},
            "offset": CUT_PLANE_X_MM,
        },
        {
            "op": "surface_trim",
            "label": "sphere_cap",
            "target": {"kind": "quilt_feature", "label": "sphere_quilt"},
            "tool": {"kind": "datum_plane", "label": "cap_plane"},
            "keep_side": keep_side,
        },
    ]


def thicken_plan(quilt_id: int) -> list[dict[str, Any]]:
    return [
        {
            "op": "thicken",
            "label": "cap_solid",
            "reference": {"kind": "quilt", "id": quilt_id},
            "thickness": THICKNESS_MM,
            "side": "symmetric",
        }
    ]


def solidify_plan() -> list[dict[str, Any]]:
    return [
        {
            "op": "solidify",
            "label": "sphere_solid",
            "reference": {"kind": "quilt_feature", "label": "sphere_quilt"},
            "side": "positive",
        }
    ]


def case_offline() -> dict:
    from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS
    from creo_mechdog.schema import validate_operations

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    try:
        validate_operations(revolve_plan())
        check("schema_accepts_surface_revolve_arc", True)
    except ValueError as error:
        check("schema_accepts_surface_revolve_arc", False, {"error": str(error)})

    # A surface revolve must accept an open meridian chain; the solid-profile
    # admission is explicitly skipped for mode=surface.
    open_meridian = revolve_plan()
    open_meridian[0]["entities"] = open_meridian[0]["entities"][1:]
    try:
        validate_operations(open_meridian)
        check("surface_mode_accepts_open_meridian", True)
    except ValueError as error:
        check("surface_mode_accepts_open_meridian", False, {"error": str(error)[:160]})

    # Non-planar fill: there is no boundary-loop channel at all. Any attempt to
    # carry a 3D closed boundary must be refused before a job exists.
    for name, operation in {
        "boundary_loop": {
            "op": "surface_fill",
            "label": "nonplanar_patch",
            "boundary": {"kind": "quilt", "id": 12},
        },
        "edges_list": {
            "op": "surface_fill",
            "label": "nonplanar_patch",
            "sketch": "planar_profile",
            "edges": [{"kind": "edge", "id": 5}],
        },
        "sections": {
            "op": "surface_fill",
            "label": "nonplanar_patch",
            "sections": ["a", "b", "c"],
        },
    }.items():
        try:
            validate_operations([operation])
            check(f"surface_fill_refuses_{name}", False, {"reason": "accepted"})
        except ValueError as error:
            check(f"surface_fill_refuses_{name}", True, {"error": str(error)[:160]})

    # Planar fill itself is untouched: one planar sketch, no new fields.
    try:
        validate_operations(
            [
                {
                    "op": "sketch",
                    "label": "planar_profile",
                    "plane": "XY",
                    "entities": [
                        {
                            "type": "rectangle",
                            "name": "rect",
                            "min": [0.0, 0.0],
                            "max": [40.0, 20.0],
                        }
                    ],
                },
                {"op": "surface_fill", "label": "planar_patch", "sketch": "planar_profile"},
            ]
        )
        check("planar_fill_contract_unchanged", True)
    except ValueError as error:
        check("planar_fill_contract_unchanged", False, {"error": str(error)})

    fill_fields = set()
    try:
        from creo_mechdog.schema import FillOp

        fill_fields = set(FillOp.model_fields)
    except Exception as error:  # pragma: no cover - import guard only
        check("fill_op_has_only_sketch", False, {"error": str(error)})
    else:
        check(
            "fill_op_has_only_sketch", fill_fields == {"op", "label", "sketch"}, sorted(fill_fields)
        )

    check("revolve_registered", "revolve" in REGISTERED_OPERATIONS)
    check("revolve_published", "revolve" not in UNAVAILABLE_OPERATIONS)
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    check(
        "server_tool_exposes_surface_mode",
        '"mode": mode' in server and "async def creo_revolve(" in server,
    )
    native = (ROOT / "native" / "generic.cpp").read_text(encoding="utf-8")
    check(
        "native_surface_revolve_branch",
        "PRO_FEAT_DATUM_SURF" in native and "PRO_EXT_FEAT_TYPE_SURFACE" in native,
    )
    fill_native = (ROOT / "native" / "surfaces.cpp").read_text(encoding="utf-8")
    check("native_fill_is_flat_only", "PRO_E_FEATURE_FORM, PRO_FLAT" in fill_native)
    return {
        "mode": "offline",
        "passed": all(item["ok"] for item in checks),
        "native_surface_revolve": "not_verified",
        "oracles": {
            "sphere_area_mm2": SPHERE_AREA_MM2,
            "cap_area_mm2": CAP_AREA_MM2,
            "rest_area_mm2": REST_AREA_MM2,
            "sphere_volume_mm3": SPHERE_VOLUME_MM3,
        },
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


async def try_call(client, tool: str, arguments: dict) -> tuple[bool, dict]:
    """Call a tool that may be legally refused; never raise on isError."""
    result = await client.call_tool(tool, arguments)
    if result.structured_content is not None:
        return bool(result.is_error), result.structured_content
    text = "".join(getattr(block, "text", "") for block in (result.content or []))
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = {"raw": text[:600]}
    return bool(result.is_error), payload


async def submit(client, operation_plan: list[dict], model_id=None, revision=None) -> dict:
    arguments: dict = {"operations": operation_plan}
    if model_id:
        arguments["model_id"] = model_id
        arguments["expected_revision"] = revision
    submitted = await call_tool(client, "creo_execute_plan", arguments)
    job_id = submitted.get("job_id")
    if not job_id:
        return {"status": "refused", "message": str(submitted)[:900]}
    deadline = time.monotonic() + 900
    state: dict = {}
    while time.monotonic() < deadline:
        state = await call_tool(client, "creo_get_job", {"job_id": job_id, "detail": "compact"})
        if state.get("status") in ("succeeded", "failed", "unknown_outcome"):
            break
        await asyncio.sleep(2)
    else:
        return {"status": "unsettled", "job_id": job_id, "message": "job did not settle"}
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
                "native_surface_revolve": "not_verified",
                "note": "the session never reported connected; no geometry was submitted",
                "checks": checks,
                "jobs": jobs,
            }

        capabilities = await call_tool(client, "creo_capabilities", {})
        published = "revolve" in (capabilities.get("operations") or [])
        check("revolve_published", published)

        # Negative control, submitted first and as a plan: a fill carrying a 3D
        # closed boundary must be refused before any job exists.
        is_error, refused = await try_call(
            client,
            "creo_execute_plan",
            {
                "operations": [
                    {
                        "op": "surface_fill",
                        "label": "nonplanar_patch",
                        "boundary": {"kind": "quilt", "id": 12},
                    }
                ]
            },
        )
        check(
            "nonplanar_fill_refused_before_job",
            is_error and not refused.get("job_id"),
            {"isError": is_error, "payload": str(refused)[:400]},
        )

        # 1) The R8 sphere as a surface of revolution.
        sphere = await submit(client, revolve_plan())
        remember(sphere)
        check(
            "revolve_job_succeeded",
            sphere.get("status") == "succeeded",
            {"status": sphere.get("status"), "message": str(sphere.get("message"))[:500]},
        )
        if sphere.get("status") != "succeeded":
            return {
                "mode": "live",
                "passed": False,
                "native_surface_revolve": "failed",
                "checks": checks,
                "jobs": jobs,
                "failure": operation_of(sphere, "revolve") or sphere.get("message"),
            }
        model_id = sphere["model_id"]
        revision = sphere.get("revision")
        check("sphere_saved_and_reloaded", saved_verified(sphere))

        features = await model_section(client, model_id, "features")
        revolve_feature = next(
            (f for f in features if str(f.get("name", "")).lower() == "sphere_quilt"), {}
        )
        check(
            "revolve_feature_is_datum_surface",
            revolve_feature.get("type") == 942,
            {"type": revolve_feature.get("type"), "type_name": revolve_feature.get("type_name")},
        )
        check(
            "revolve_feature_active",
            revolve_feature.get("status") == 0,
            revolve_feature.get("status"),
        )

        quilts = await model_section(client, model_id, "quilts")
        check("exactly_one_quilt", len(quilts) == 1, {"count": len(quilts), "quilts": quilts})
        sphere_quilt = quilts[0] if quilts else {}
        sphere_area = sphere_quilt.get("area_mm2")
        check(
            "sphere_area_matches_4pir2",
            isinstance(sphere_area, (int, float))
            and abs(sphere_area - SPHERE_AREA_MM2) <= AREA_TOLERANCE_MM2,
            {
                "area_mm2": sphere_area,
                "oracle_mm2": SPHERE_AREA_MM2,
                "delta_mm2": None
                if not isinstance(sphere_area, (int, float))
                else sphere_area - SPHERE_AREA_MM2,
            },
        )
        check(
            "sphere_quilt_is_closed", sphere_quilt.get("closed") is True, sphere_quilt.get("closed")
        )
        bodies = await model_section(client, model_id, "bodies")
        check(
            "no_solid_created",
            not any(b.get("material") is True or b.get("has_geometry") is True for b in bodies),
            {"bodies": bodies},
        )

        # 2) Trim the sphere with x=4; one side is the analytic cap.
        trimmed = await submit(client, trim_plan("one"), model_id, revision)
        remember(trimmed)
        trim = operation_of(trimmed, "surface_trim")
        kept_area = trim.get("area_after_mm2")
        check(
            "trim_job_succeeded",
            trimmed.get("status") == "succeeded",
            {"status": trimmed.get("status"), "message": str(trimmed.get("message"))[:500]},
        )
        is_cap = (
            isinstance(kept_area, (int, float))
            and abs(kept_area - CAP_AREA_MM2) <= AREA_TOLERANCE_MM2
        )
        is_rest = (
            isinstance(kept_area, (int, float))
            and abs(kept_area - REST_AREA_MM2) <= AREA_TOLERANCE_MM2
        )
        check(
            "trim_keeps_one_analytic_region",
            is_cap or is_rest,
            {
                "area_after_mm2": kept_area,
                "cap_oracle_mm2": CAP_AREA_MM2,
                "rest_oracle_mm2": REST_AREA_MM2,
            },
        )
        check("trim_saved_and_reloaded", saved_verified(trimmed))
        revision = trimmed.get("revision")

        # 3) Thicken the retained region by 2 mm symmetric.
        if is_cap or is_rest:
            expected_shell = cap_shell_volume(RADIUS_MM + 1.0, RADIUS_MM - 1.0, is_cap)
            after_trim = await model_section(client, model_id, "quilts")
            kept = [
                record
                for record in after_trim
                if isinstance(record.get("area_mm2"), (int, float))
                and abs(record["area_mm2"] - kept_area) <= AREA_TOLERANCE_MM2
            ]
            check(
                "kept_quilt_queryable",
                bool(kept),
                {"areas": [r.get("area_mm2") for r in after_trim]},
            )
            if kept:
                thickened = await submit(
                    client, thicken_plan(kept[0]["quilt_id"]), model_id, revision
                )
                remember(thickened)
                thicken = operation_of(thickened, "thicken")
                volume = thicken.get("volume_after_mm3")
                check(
                    "thicken_job_succeeded",
                    thickened.get("status") == "succeeded",
                    {
                        "status": thickened.get("status"),
                        "message": str(thickened.get("message"))[:500],
                    },
                )
                check(
                    "thicken_volume_matches_spherical_shell",
                    isinstance(volume, (int, float))
                    and abs(volume - expected_shell) <= VOLUME_TOLERANCE_RELATIVE * expected_shell,
                    {
                        "volume_after_mm3": volume,
                        "shell_oracle_mm3": expected_shell,
                        "area_times_thickness_mm3": kept_area * THICKNESS_MM,
                        "relative_tolerance": VOLUME_TOLERANCE_RELATIVE,
                    },
                )
                check("thicken_saved_and_reloaded", saved_verified(thickened))

        # 4) The other side of the same cut, on its own model.
        other = await submit(client, revolve_plan() + trim_plan("two"))
        remember(other)
        other_trim = operation_of(other, "surface_trim")
        other_area = other_trim.get("area_after_mm2")
        check(
            "other_side_job_succeeded",
            other.get("status") == "succeeded",
            {"status": other.get("status"), "message": str(other.get("message"))[:500]},
        )
        if isinstance(kept_area, (int, float)) and isinstance(other_area, (int, float)):
            check(
                "two_sides_sum_to_sphere_area",
                abs(kept_area + other_area - SPHERE_AREA_MM2) <= 1.0,
                {"one": kept_area, "two": other_area, "sphere_oracle_mm2": SPHERE_AREA_MM2},
            )
        else:
            check("two_sides_sum_to_sphere_area", False, {"one": kept_area, "two": other_area})

        # 5) Solidify the closed sphere: an independent closure/volume check.
        solidified = await submit(client, revolve_plan() + solidify_plan())
        remember(solidified)
        solid = operation_of(solidified, "solidify")
        volume = solid.get("volume_after_mm3")
        check(
            "solidify_job_succeeded",
            solidified.get("status") == "succeeded",
            {"status": solidified.get("status"), "message": str(solidified.get("message"))[:500]},
        )
        check(
            "solidify_volume_matches_4_3_pi_r3",
            isinstance(volume, (int, float))
            and abs(volume - SPHERE_VOLUME_MM3) <= VOLUME_TOLERANCE_RELATIVE * SPHERE_VOLUME_MM3,
            {
                "volume_after_mm3": volume,
                "oracle_mm3": SPHERE_VOLUME_MM3,
                "relative_tolerance": VOLUME_TOLERANCE_RELATIVE,
            },
        )

    passed = all(item["ok"] for item in checks)
    return {
        "mode": "live",
        "passed": passed,
        "native_surface_revolve": "verified" if passed else "failed",
        "oracles": {
            "sphere_area_mm2": SPHERE_AREA_MM2,
            "cap_area_mm2": CAP_AREA_MM2,
            "rest_area_mm2": REST_AREA_MM2,
            "cap_shell_volume_mm3": cap_shell_volume(RADIUS_MM + 1.0, RADIUS_MM - 1.0, True),
            "sphere_volume_mm3": SPHERE_VOLUME_MM3,
        },
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
    output = args.output or ROOT / "build" / "surface_revolve" / run_id / "report.json"
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
