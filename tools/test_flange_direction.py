"""DEV-051 T05/T11 A: is the flange bend direction really switchable?

The 2026-10-29 22:06 run settled the geometry question and exposed the direction one:
both flanges were real 90 degree bends (bbox Z grew 79 mm) but both went down, and
`flip=true` was identical to `flip=false`, so `flip` reached no working element. The
follow-up probe measured the only element that moves the bend,
PRO_E_SMT_FLANGE_SEC_FLIP - top edge FALSE -> down, TRUE -> up; bottom edge FALSE -> up,
TRUE -> down - so the side is relative to the attachment face, and TRUE ("out of the
selected face") is now the default with `flip` asking for the material side.

Verdict rule (docs/development/DEV051-T05-ACCEPTANCE.md): the base plate is 185 x 232 x 1,
so a 90 degree flange with height 80 grows the bbox by at least 0.9 x 80 = 72 mm in Z,
either up or down. |Z growth| below 72 mm is a failure even when the volume delta matches.
Direction is read from the bbox and compared with the case's explicit expectation: the
default case must go up (out of the top face) and `flip=true` must go down, so a switch
that does nothing fails instead of passing.

Offline mode checks the native section structure against the stock Creo shapes in
<creo_root>/Common Files/text/smt/flange_shapes: every stock shape holds one line, one
coordinate system and one length dimension and no centerline, and sketch +x is the
direction normal to the parent wall. Only --live --confirm-session-usable starts an MCP
client.

Hang rule: one flange job that is not terminal after 180 seconds is a hang. The driver
never resubmits, never kills or restarts Creo, records the job id, the stage and the
native log tail, and stops every further submission.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
import uuid
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402
from tests.unit import test_sheetmetal_flange as fx  # noqa: E402
from tools.sheetmetal_live import (  # noqa: E402
    LiveRunner,
    LiveStop,
    failure_text,
    require_manual_start,
    unique_name,
)

ROOT = SOURCE_PATHS.resource_root
HANG_BUDGET_SECONDS = 180.0
Z_GROWTH_RATIO = 0.9
CASES = (
    ("angle90_outward", "default side: out of the selected top face", False, "up"),
    ("angle90_inward", "flip=true: the opposite, material side", True, "down"),
)

# DEV-053 P08 (FEAT-014) validation design, frozen here and scheduled for the
# live window by the orchestrator. Nothing below runs offline; the design is
# the contract the live cases must judge against, and it records what is
# genuinely supported versus still unproven.
FREE_END_FLANGE_DESIGN = {
    "subject": "free-end first flange with flip in both directions",
    "fixture": (
        "one fresh 185x232x1 wall per case (tests.unit.test_sheetmetal_flange "
        "wall_sketch + wall_base_op); the +x top edge selected by geometry from the "
        "current inspection, both bend ends at free plate corners"
    ),
    "cases": [
        {
            "name": "free_end_default_outward",
            "flip": False,
            "expect": (
                "real 90 degree bend out of the attachment face: |bbox Z growth| >= 72 mm, "
                "direction up on the top edge, saved_file_reloaded_and_verified true, "
                "revision +1"
            ),
        },
        {
            "name": "free_end_flip_inward",
            "flip": True,
            "expect": (
                "the same bend on the opposite, material side: direction down on the top "
                "edge, |bbox Z growth| >= 72 mm, saved_file_reloaded_and_verified true"
            ),
        },
    ],
    "oracle": (
        "bbox-only bend detection plus the explicit per-case side expectation; the "
        "volume delta alone cannot separate a bend from a coplanar extension"
    ),
    "status": "supported_on_free_end_pending_this_live_run",
}

FIXED_SURFACE_DESIGN = {
    "subject": "fixed_surface allowed for sheetmetal_unbend / bend_back / flat_pattern",
    "reference_contract": (
        "bare reference object {kind:'surface',id:N} taken from model inspection; the "
        "native executor decides whether that geometry can stay fixed - there is no "
        "unconditional 'any surface works' guarantee"
    ),
    "cases": [
        {
            "name": "unbend_fixed_on_wall_face",
            "op": "sheetmetal_unbend",
            "fixed_surface": {"kind": "surface", "id": "<wall_face_id from wall_contract>"},
            "expect": (
                "all bends unfold about the chosen wall face; wall volume unchanged; "
                "saved_file_reloaded_and_verified true; revision +1"
            ),
        },
        {
            "name": "bend_back_fixed_on_wall_face",
            "op": "sheetmetal_bend_back",
            "fixed_surface": {"kind": "surface", "id": "<wall_face_id from wall_contract>"},
            "expect": (
                "the previously unbent bends return; bbox and volume match the pre-unbend "
                "state; saved_file_reloaded_and_verified true"
            ),
        },
        {
            "name": "flat_pattern_fixed_on_wall_face",
            "op": "sheetmetal_flat_pattern",
            "fixed_surface": {"kind": "surface", "id": "<wall_face_id from wall_contract>"},
            "expect": (
                "flat pattern created about the chosen wall face; the solid volume "
                "unchanged; saved_file_reloaded_and_verified true"
            ),
        },
        {
            "name": "fixed_surface_on_flange_face",
            "op": "sheetmetal_unbend",
            "fixed_surface": {"kind": "surface", "id": "<flange wall face id>"},
            "expect": (
                "either the bend unfolds about the flange face with matching geometry, or "
                "the native executor refuses with a real error and a rollback - an "
                "accepted-but-wrong geometry is a failure"
            ),
        },
    ],
    "negative_controls": [
        {
            "name": "fixed_surface_datum_plane",
            "input": {"kind": "datum_plane", "id": 11},
            "expect": (
                "admission rejects the non-surface reference before any feature exists; "
                "the historical F4 S6 complaint must not be re-read as a supported input"
            ),
        },
        {
            "name": "fixed_surface_stale_edge_id",
            "input": {"kind": "edge", "id": 121},
            "expect": (
                "rejected as the wrong reference kind; historical fixed edge ids are never "
                "reused - references are re-selected by geometry from the current inspection"
            ),
        },
    ],
    "status": (
        "reference syntax supported; the native accept/refuse outcome per face is "
        "unproven and stays open until the live run"
    ),
}

CANDIDATE_EDGE_DESIGN = {
    "subject": "candidate edge discovery before a flange attempt",
    "procedure": (
        "inspect the model (the bounded wall_contour_check runs on sheetmetal parts), "
        "read wall_contour_status/query_code/revision from the public full inspection "
        "(wall_contour_check in the whole snapshot or metadata page), "
        "then pick the attach edge BY GEOMETRY from the current inspection (the "
        "2026-10-31 F5 flow: the Z=0 bottom edges of the standard base plate) - never "
        "by a historical edge id"
    ),
    "acceptance": [
        "edges with wall_contour_status=eligible carry a flange attempt; ineligible "
        "edges are skipped without a submission",
        "query failure keeps status=unknown with the real code and is never treated as "
        "ineligible",
        "an eligible edge whose end is adjacent to an existing bend is STILL rejected "
        "before create (failure_reason=adjacent_bend_ends): the candidate-edge pass "
        "never unlocks that boundary",
        "the discovery query creates no flange and modifies no model",
    ],
    "status": "projection tested offline; the real query values await the live run",
}


def pending_validation() -> dict:
    """The live schedule the orchestrator still owes (DEV-053 P08)."""
    return {
        "free_end_first_flange": FREE_END_FLANGE_DESIGN,
        "fixed_surface_unbend_family": FIXED_SURFACE_DESIGN,
        "candidate_edge_discovery": CANDIDATE_EDGE_DESIGN,
        "not_executed": (
            "offline stage only; --live --confirm-session-usable runs these under the "
            "orchestrator's serial Creo window"
        ),
    }


def native_section() -> dict:
    """The flange function body, so a regression is caught without Creo."""
    source = (ROOT / "native" / "advanced.cpp").read_text(encoding="utf-8")
    start = source.find("static void generic_sheetmetal_flange(const J &op)")
    if start < 0:
        raise SystemExit("generic_sheetmetal_flange is missing from native/advanced.cpp")
    end = source.find("\nstatic void fix_component", start)
    body = source[start:end]
    leg = re.search(r"double leg\[2\] = \{h \* sin\(a\), h \* cos\(a\)\};", body)
    return {
        "function": "generic_sheetmetal_flange",
        "leg_on_sketch_normal": bool(leg),
        "centerline_removed": '"centerline"' not in body,
        "profile_entity_count": body.count('{"type", "line"}'),
        "height_type_none": "PRO_SMT_WALL_HEIGHT_NONE" in body,
        "section_side_flip_is_the_switch": (
            'op.value("flip", false) ? PRO_B_FALSE : PRO_B_TRUE' in body
            and "integer(root, PRO_E_SMT_FLANGE_SEC_FLIP, sec_flip)" in body
        ),
        "traj_normal_not_the_switch": (
            "PRO_FLANGE_TRAJ_NORM_FLIP" not in body
            and "PRO_E_SMT_FLANGE_TRAJ_CRV_NORM, PRO_FLANGE_TRAJ_NORM_NO_FLIP" in body
        ),
        "statement": (
            "stock flange_shapes hold one line, one coordinate system and one length "
            "dimension and no centerline; sketch +x is normal to the parent wall; the bend "
            "side comes from PRO_E_SMT_FLANGE_SEC_FLIP, not from the trajectory normal"
        ),
    }


def verdict(before: tuple, after: tuple, height: float, expected: str) -> dict:
    """Bbox-only judgement: Z growth is the bend, in-plane growth is not.

    The envelope counts in both directions, so a downward flange is still a bend. The
    direction is then compared with the case's explicit expectation, so a `flip` that
    changes nothing fails on the case that asks for the other side.
    """
    growth_z = max(after[1][2] - before[1][2], before[0][2] - after[0][2])
    direction = fx.classify_direction(after)
    return {
        "bbox_before_mm": [list(before[0]), list(before[1])],
        "bbox_after_mm": [list(after[0]), list(after[1])],
        "z_growth_mm": growth_z,
        "required_z_growth_mm": height * Z_GROWTH_RATIO,
        "direction": direction,
        "expected_direction": expected,
        "direction_matches": direction == expected,
        "bent": growth_z >= height * Z_GROWTH_RATIO,
    }


def plan() -> list[dict]:
    return [
        {
            "case": name,
            "change": description,
            "flip": flip,
            "expected_direction": expected,
            "model": "fresh per case",
            "height_mm": fx.FLANGE_HEIGHT_MM,
            "angle_deg": fx.FLANGE_ANGLE_DEG,
            "radius_mm": fx.FLANGE_RADIUS_MM,
        }
        for name, description, flip, expected in CASES
    ]


def offline_report(output: Path | None) -> dict:
    report = {
        "task": "FEAT-014 / DEV-051 T05/T11 / DEV-053 P08",
        "scope": "one flange per model, bbox Z growth decides a 90 degree bend",
        "mode": "offline",
        "hang_budget_seconds": HANG_BUDGET_SECONDS,
        "native_section": native_section(),
        "cases": plan(),
        "pending_live_validation": pending_validation(),
        "not_executed": "no MCP client, no Creo connection; use --live --confirm-session-usable",
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report"] = str(output)
    return report


async def run_case(runner: LiveRunner, name: str, flip: bool, expected: str) -> dict:
    model_name = unique_name(f"f4_{name}")
    created = await runner.submit(
        f"{name}:base",
        "creo_execute_plan",
        {
            "model_name": model_name,
            "model_type": "sheetmetal",
            "operations": [fx.wall_sketch(), fx.wall_base_op()],
        },
    )
    model_id = created["model_id"]
    terminal = await runner.wait_job(created["job_id"], budget=HANG_BUDGET_SECONDS)
    entry: dict = {
        "case": name,
        "flip": flip,
        "expected_direction": expected,
        "model_name": model_name,
        "model_id": model_id,
        "base_job_id": created["job_id"],
        "base_status": terminal.get("status"),
        "base_revision": terminal.get("revision"),
    }
    if terminal.get("status") != "succeeded":
        entry.update(failure=failure_text(terminal), passed=False)
        return runner.case(entry)

    snapshot = await runner.snapshot(model_id)
    bounds = fx.active_bbox(runner.inspection(snapshot))
    entry.update(base_volume_mm3=runner.volume(snapshot))
    reference = fx.select_wall_edge(runner.inspection(snapshot), bounds, "+x", face="top")
    submitted = await runner.submit(
        f"{name}:flange",
        "creo_sheetmetal_flange",
        {
            "model_id": model_id,
            "expected_revision": snapshot.get("revision"),
            "label": "f_px",
            "edge": dict(reference["edge"]),
            "height": fx.FLANGE_HEIGHT_MM,
            "angle": fx.FLANGE_ANGLE_DEG,
            "radius": fx.FLANGE_RADIUS_MM,
            "flip": flip,
            "y_factor": fx.FLANGE_Y_FACTOR,
        },
    )
    terminal = await runner.wait_job(submitted["job_id"], budget=HANG_BUDGET_SECONDS)
    entry.update(flange_job_id=submitted["job_id"], flange_status=terminal.get("status"))
    if terminal.get("status") != "succeeded":
        after = await runner.snapshot(model_id)
        entry.update(
            failure=failure_text(terminal),
            revision_after=after.get("revision"),
            volume_after_mm3=runner.volume(after),
            passed=False,
        )
        return runner.case(entry)

    after = await runner.snapshot(model_id)
    after_bounds = fx.active_bbox(runner.inspection(after))
    added = None
    if runner.volume(after) is not None and entry["base_volume_mm3"] is not None:
        added = runner.volume(after) - entry["base_volume_mm3"]
    judged = verdict(bounds, after_bounds, fx.FLANGE_HEIGHT_MM, expected)
    saved = (terminal.get("result") or {}).get("saved_file_reloaded_and_verified")
    side = runner.record(after, "f_px")
    entry.update(
        edge=reference["geometry"],
        revision_after=after.get("revision"),
        volume_after_mm3=runner.volume(after),
        added_mm3=added,
        saved_file_reloaded_and_verified=saved,
        bend_side_echo=side.get("bend_side"),
        sec_flip_echo=side.get("sec_flip_element"),
        **judged,
    )
    entry["passed"] = bool(judged["bent"] and judged["direction_matches"] and saved is True)
    return runner.case(entry)


async def live(output: Path, run_id: str) -> int:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=240) as client:
        runner = LiveRunner(
            client,
            output,
            "FEAT-014 / DEV-051 T05/T11",
            "one flange per fresh model; |bbox Z growth| decides a 90 degree bend and the "
            "explicit direction expectation decides the side",
            run_id,
        )
        runner.report["hang_budget_seconds"] = HANG_BUDGET_SECONDS
        blocked = None
        try:
            await runner.start()
            for name, description, flip, expected in CASES:
                if blocked:
                    runner.case(
                        {
                            "case": name,
                            "change": description,
                            "expected_direction": expected,
                            "passed": False,
                            "not_executed": blocked,
                        }
                    )
                    continue
                entry = await run_case(runner, name, flip, expected)
                if entry.get("base_status") != "succeeded":
                    blocked = "the base first wall did not succeed, so no flange was submitted"
                elif entry.get("bent") is False:
                    blocked = (
                        "case "
                        + name
                        + " produced a flat wall; the next variable is not worth a second submission "
                        "until the section direction is decided"
                    )
        except (LiveStop, BaseException) as error:
            runner.report["stopped"] = f"{type(error).__name__}: {error}"
            runner.finish()
            raise
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if runner.report["passed"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.live and not args.confirm_session_usable:
        raise SystemExit("--live requires --confirm-session-usable after human session checks")
    if args.live:
        run_id = f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
        output = args.output or ROOT / "build" / "flange_direction" / run_id / "report.json"
        if output.exists():
            raise SystemExit(f"Refusing to overwrite an existing report: {output}")
        return asyncio.run(live(output, run_id))
    print(json.dumps(offline_report(args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
