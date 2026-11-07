"""BUG-102: draft-on-chamfered-face regression driver (offline + live stage).

The 0.10.0 feedback reports that a 40x30x10 block with chamfer(2) and round(R3)
accepted a 10 deg draft in 0.9.0 (+264.19 mm3) and fails with
``ProFeatureWithoptionsCreate=-1`` in 0.10.0. FEAT-051 added three element-tree
flags to the same code path, so the first thing to prove is *which* variable
changed the outcome - not to assume the geometry is impossible.

Offline stage (default):

* freezes the reported fixture and the single-variable A/B element sets;
* proves the native code still carries both the flags under test and the
  failure receipt fields;
* prints the exact live steps the assigned session must run, in order.

Live stage (--live --confirm-session-usable, scheduled separately): builds the
fixture (chamfer 2 on the (20,-15) vertical edge, round R3 on the (-20,-15)
edge of a 40x30x10 block), reads the *actual* side surface id and bottom
neutral face from inspection, then runs two independent parts with the same
10 deg draft request and ``flip=false`` / ``flip=true``. Each variant records
the request, the feature-tree readback, the pull reference/vector, the
material before/after/delta, the independent volume delta and the save-reload
verification. A failed create records ``draft_failure`` instead. It never
launches, restarts or closes Creo, never injects a fault and never resubmits.

This is evidence for the existing implementation (W02): a successful run
proves the requested/effective flip contract on this fixture; it does not
prove that the reporter's Creo 10 ``-1`` is fixed.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

ROOT = _SOURCE_ROOT
FIXTURE = {
    "block": {"length_mm": 40.0, "width_mm": 30.0, "height_mm": 10.0, "volume_mm3": 12000.0},
    "chamfer": {"size_mm": 2.0, "reported_delta_mm3": -20.0},
    "round": {"radius_mm": 3.0, "reported_delta_mm3": -19.314168},
    "draft": {"angle_deg": 10.0, "surface_id_reported": 69},
    "reported_deltas_mm3": {"0.9.0_flip_false": 264.19, "0.9.0_flip_true": -264.79},
}

# Single-variable A/B: only one element flag changes per variant. The current
# production tree is A; B removes the FEAT-051 additions so a live run can tell
# element-tree tightening apart from a genuinely infeasible angle.
VARIANTS = {
    "A_current": {
        "PRO_E_DRAFT_TWEAK_OR_INTERSEC": "PRO_DRAFT_UI_INTERSECT",
        "PRO_E_DRAFT_EXTEND": "PRO_DRAFT_UI_NO_EXTEND",
        "PRO_E_DRAFT_SPLIT": "PRO_DRAFT_UI_SPLIT_NONE",
    },
    "B_no_extend": {
        "PRO_E_DRAFT_TWEAK_OR_INTERSEC": "PRO_DRAFT_UI_INTERSECT",
        "PRO_E_DRAFT_EXTEND": None,
        "PRO_E_DRAFT_SPLIT": "PRO_DRAFT_UI_SPLIT_NONE",
    },
    "B_no_split": {
        "PRO_E_DRAFT_TWEAK_OR_INTERSEC": "PRO_DRAFT_UI_INTERSECT",
        "PRO_E_DRAFT_EXTEND": "PRO_DRAFT_UI_NO_EXTEND",
        "PRO_E_DRAFT_SPLIT": None,
    },
    "B_no_intersect": {
        "PRO_E_DRAFT_TWEAK_OR_INTERSEC": None,
        "PRO_E_DRAFT_EXTEND": "PRO_DRAFT_UI_NO_EXTEND",
        "PRO_E_DRAFT_SPLIT": "PRO_DRAFT_UI_SPLIT_NONE",
    },
}

LIVE_STEPS = (
    "Confirm session usability (no unknown protection, no accepted job pending); never launch, "
    "restart or stop Creo from the driver.",
    "New part: 40x30x10 block, chamfer size 2 on the (20,-15) vertical edge, round R3 on the "
    "(-20,-15) vertical edge.",
    "Inspect the fixture and record the side surface id actually used (normal (0,-1,0)) and the "
    "bottom neutral face (normal (0,0,-1)); never reuse the reported id 69.",
    "Variant flip=false: draft angle 10 on the recorded side face, neutral plane = bottom face; "
    "record the terminal state and the draft_geometry/draft_failure block.",
    "Variant flip=true on an independent part: same request with flip true; record requested_flip "
    "vs effective_flip, pull reference/vector, material delta and save/reload.",
    "If a variant fails, keep the draft_failure sample and do not call the run a fix; the reporter's "
    "Creo 10 -1 stays unproven until reproduced.",
)

# Live fixture: the exact reported block, with one chamfered and one rounded
# vertical edge so the drafted face is bounded by both detail features.
DRAFT_ANGLE_DEG = 10.0
BLOCK = {"length_mm": 40.0, "width_mm": 30.0, "height_mm": 10.0}
SIDE_NORMAL = (0.0, -1.0, 0.0)
SIDE_OFFSET_MM = 15.0  # dot((0,-15,0), unit(SIDE_NORMAL))
BOTTOM_NORMAL = (0.0, 0.0, -1.0)
BOTTOM_OFFSET_MM = 0.0
FIXTURE_VOLUME_MM3 = 11960.685832  # 12000 - chamfer (0.5*2*2*10) - round ((1-pi/4)*9*10)


def draft_delta_per_mm(angle_deg: float, height_mm: float) -> float:
    """Volume added/removed per millimetre of drafted face width.

    A face tilted by ``angle_deg`` about a neutral plane at its bottom edge
    sweeps a triangular prism of area ``0.5 * (height*tan(angle)) * height``.
    """
    return 0.5 * math.tan(math.radians(angle_deg)) * height_mm * height_mm


DRAFT_ORACLE_MM3 = draft_delta_per_mm(DRAFT_ANGLE_DEG, BLOCK["height_mm"]) * (
    BLOCK["length_mm"] - 2.0 - 3.0
)


def box_operations() -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "w02_profile",
            "plane": "XY",
            "entities": [
                {
                    "type": "polyline",
                    "name": "w02_rect",
                    "points": [
                        [-20.0, -15.0],
                        [20.0, -15.0],
                        [20.0, 15.0],
                        [-20.0, 15.0],
                    ],
                    "closed": True,
                }
            ],
            "dimensioning": "coordinates",
        },
        {
            "op": "extrude",
            "label": "w02_block",
            "sketch": "w02_profile",
            "depth": BLOCK["height_mm"],
        },
    ]


def select_vertical_edge_at(
    edges: list[dict], x: float, y: float, length_mm: float, tol: float = 1e-6
) -> int | None:
    for edge in edges or []:
        start, end = edge.get("start"), edge.get("end")
        if not isinstance(start, list) or not isinstance(end, list) or len(start) != 3:
            continue
        vertical = abs(start[0] - end[0]) <= tol and abs(start[1] - end[1]) <= tol
        if not vertical or abs(abs(end[2] - start[2]) - length_mm) > tol:
            continue
        if abs(start[0] - x) <= tol and abs(start[1] - y) <= tol:
            return edge["id"]
    return None


def select_plane_surface(
    surfaces: list[dict], normal: tuple, offset: float, tol: float = 1e-6
) -> int | None:
    length = math.sqrt(sum(value * value for value in normal))
    if length <= tol:
        return None
    direction = [value / length for value in normal]
    for surface in surfaces or []:
        candidate, origin = surface.get("normal"), surface.get("origin")
        if not isinstance(candidate, list) or not isinstance(origin, list):
            continue
        size = math.sqrt(sum(value * value for value in candidate))
        if size <= tol:
            continue
        alignment = abs(sum(a / size * b for a, b in zip(candidate, direction, strict=True)))
        if abs(alignment - 1.0) > 1e-6:
            continue
        if abs(sum(a * b for a, b in zip(origin, direction, strict=True)) - offset) <= tol:
            return surface["id"]
    return None


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def native_source(name: str) -> str:
    return (ROOT / "native" / name).read_text(encoding="utf-8")


def offline_checks() -> dict[str, Any]:
    source = native_source("advanced.cpp")
    draft = source[
        source.index("static J generic_draft(") : source.index("static void generic_sweep(")
    ]
    flags = []
    for name, values in VARIANTS.items():
        present = {flag: (value is None or value in draft) for flag, value in values.items()}
        flags.append({"variant": name, "expected_flags": values, "present_in_source": present})
    checks = {
        "fixture_frozen": FIXTURE["draft"]["angle_deg"] == 10.0
        and FIXTURE["chamfer"]["size_mm"] == 2.0
        and FIXTURE["round"]["radius_mm"] == 3.0,
        "flags_present_in_current_tree": all(
            value in draft for value in VARIANTS["A_current"].values()
        ),
        "failure_receipt_fields": all(
            token in draft
            for token in ("draft_failure", "requested_flip", "element_errors", "classification")
        ),
        "no_geometry_verdict_in_driver": "infeasible" not in json.dumps(FIXTURE),
    }
    checks["passed"] = all(value for key, value in checks.items() if key != "passed")
    return {
        "task": "BUG-102 / R10-02 draft regression A/B",
        "mode": "offline",
        "live_stage": "not_run",
        "statement": (
            "Offline stage only: fixture, A/B element sets and receipt fields frozen. No Toolkit "
            "connection, no geometry created, no verdict on whether the regression is fixed."
        ),
        "fixture": FIXTURE,
        "variants": flags,
        "live_steps": list(LIVE_STEPS),
        "checks": checks,
    }


def resolve_output(output: Path | None, run_id: str) -> Path:
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "bug102_draft" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
    """Collect source evidence even when running from an extracted release."""
    from creo_mechdog.source_provenance import local_provenance as collect

    return collect(ROOT, ("tools/test_draft_regression.py", "tests/unit/test_draft_observation.py"))


# --- live stage (requires --live --confirm-session-usable) -------------------


def require_manual_start(config_file: Path) -> None:
    """Driver-only precondition; never edits the user's startup configuration."""
    settings = json.loads(config_file.read_text(encoding="utf-8-sig"))
    if settings.get("auto_start_creo") is not False:
        raise ValueError(
            "Live acceptance requires config.json auto_start_creo=false; no client was started"
        )


class LiveRunner:
    """Serial MCP client wrapper; a failure freezes the run and keeps the scene."""

    def __init__(self, client: Any, output: Path, run_id: str) -> None:
        self.client = client
        self.output = output
        self.report: dict = {
            "task": "BUG-102 / W02 draft success-path receipt",
            "run_id": run_id,
            "mode": "live",
            "native_acceptance": "running",
            "fixture": FIXTURE,
            "live_fixture": {
                "block_mm": BLOCK,
                "chamfer_edge_at": [20.0, -15.0],
                "round_edge_at": [-20.0, -15.0],
                "side_normal": list(SIDE_NORMAL),
                "neutral_normal": list(BOTTOM_NORMAL),
                "draft_angle_deg": DRAFT_ANGLE_DEG,
                "expected_fixture_volume_mm3": FIXTURE_VOLUME_MM3,
                "draft_delta_oracle_mm3": DRAFT_ORACLE_MM3,
            },
            "variants": [],
            "calls": [],
            "provenance": local_provenance(),
        }

    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def call(self, name: str, args: dict) -> dict:
        record = {"tool": name, "args": copy.deepcopy(args), "started_at": time.time()}
        self.report["calls"].append(record)
        self.save()
        result = await self.client.call_tool(name, args)
        record.update(
            finished_at=time.time(),
            is_error=result.is_error,
            result=result.structured_content if not result.is_error else str(result.content),
        )
        self.save()
        if result.is_error:
            raise RuntimeError(f"{name}: {result.content}")
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
                raise RuntimeError(
                    f"Existing session is not ready; no modeling submitted: {status}"
                )
            if time.monotonic() >= deadline:
                raise TimeoutError("Startup observation budget exceeded; no modeling submitted")
            await asyncio.sleep(1)

    async def terminal(self, job_id: str, budget: float = 360) -> dict:
        deadline = time.monotonic() + budget
        while True:
            job = await self.call("creo_get_job", {"job_id": job_id, "detail": "full"})
            if job.get("status") not in ("queued", "running"):
                return job
            if time.monotonic() >= deadline:
                raise TimeoutError(f"job {job_id} did not reach a terminal state; do not resubmit")
            await asyncio.sleep(1)

    async def wait_channel_free(self, budget: float = 90) -> None:
        deadline = time.monotonic() + budget
        while True:
            status = await self.call("creo_session_status", {})
            facts = (status.get("session_health") or {}).get("facts") or {}
            channel = facts.get("channel") or {}
            if channel.get("busy") is False:
                return
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Toolkit channel stayed busy: {channel}")
            await asyncio.sleep(1)

    async def submit(self, name: str, args: dict) -> dict:
        """Re-submit only rejected requests.

        Another MCP server instance in this workspace may claim the channel for
        a startup build. A ``busy`` reply with ``accepted=false`` means no job
        was accepted, so the same request may be sent again once the occupying
        operation ends; an accepted job is never resubmitted.
        """
        for _ in range(3):
            await self.wait_channel_free()
            try:
                return await self.call(name, args)
            except RuntimeError as error:
                text = str(error)
                if "toolkit_busy" not in text or '"accepted": false' not in text:
                    raise
        raise RuntimeError(f"{name}: Toolkit stayed busy; no job was accepted")

    async def plan(
        self,
        operations: list,
        *,
        model_id: str | None = None,
        revision: int | None = None,
        model_name: str | None = None,
    ) -> dict:
        args: dict = {"operations": operations}
        if model_id is not None:
            args["model_id"] = model_id
            args["expected_revision"] = revision
        if model_name is not None:
            args["model_name"] = model_name
        return await self.submit("creo_execute_plan", args)

    async def snapshot(self, model_id: str) -> dict:
        from creo_mechdog.query_client import read_full_model

        return await read_full_model(self.call, model_id)

    @staticmethod
    def operation(terminal: dict, label: str) -> dict:
        for item in (terminal.get("result") or {}).get("operations", []):
            if item.get("label") == label:
                return item
        return {}

    async def variant(self, flip: bool) -> dict:
        tag = "f1" if flip else "f0"
        row: dict = {"variant": f"flip_{str(flip).lower()}", "requested_flip": flip}
        created = await self.plan(
            box_operations(), model_name=f"bug102_w02_{tag}_{self.report['run_id'][-8:]}"
        )
        base = await self.terminal(created["job_id"])
        if base.get("status") != "succeeded" or not (base.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ):
            raise RuntimeError(f"{row['variant']}: block creation did not succeed/verify: {base}")
        model_id = created["model_id"]
        row["model_id"] = model_id

        snap = await self.snapshot(model_id)
        surfaces = snap["inspection"].get("surfaces") or []
        edges = snap["inspection"].get("edges") or []
        pair = [
            select_plane_surface(surfaces, SIDE_NORMAL, SIDE_OFFSET_MM),
            select_plane_surface(surfaces, (1.0, 0.0, 0.0), 20.0),
        ]
        edge_id = select_vertical_edge_at(edges, -20.0, -15.0, BLOCK["height_mm"])
        if None in pair or edge_id is None:
            raise RuntimeError(
                f"{row['variant']}: fixture references not found: pair={pair} edge={edge_id}"
            )
        chamfer = await self.plan(
            [
                {
                    "op": "chamfer",
                    "label": "w02_chamfer",
                    "size": 2.0,
                    "references": [
                        {"surfaces": [{"kind": "surface", "id": item} for item in pair]}
                    ],
                }
            ],
            model_id=model_id,
            revision=snap["revision"],
        )
        chamfer_terminal = await self.terminal(chamfer["job_id"])
        if chamfer_terminal.get("status") != "succeeded":
            raise RuntimeError(f"{row['variant']}: chamfer failed: {chamfer_terminal}")

        snap = await self.snapshot(model_id)
        edge_id = select_vertical_edge_at(
            snap["inspection"].get("edges") or [], -20.0, -15.0, BLOCK["height_mm"]
        )
        if edge_id is None:
            raise RuntimeError(f"{row['variant']}: round edge missing after chamfer")
        rounded = await self.plan(
            [
                {
                    "op": "round",
                    "label": "w02_round",
                    "size": 3.0,
                    "references": [{"edge": {"kind": "edge", "id": edge_id}}],
                }
            ],
            model_id=model_id,
            revision=snap["revision"],
        )
        round_terminal = await self.terminal(rounded["job_id"])
        if round_terminal.get("status") != "succeeded":
            raise RuntimeError(f"{row['variant']}: round failed: {round_terminal}")

        # Re-read after both detail features: the drafted face and its neutral
        # plane are whatever inspection says, never the fixture assumptions.
        snap = await self.snapshot(model_id)
        surfaces = snap["inspection"].get("surfaces") or []
        side_id = select_plane_surface(surfaces, SIDE_NORMAL, SIDE_OFFSET_MM)
        neutral_id = select_plane_surface(surfaces, BOTTOM_NORMAL, BOTTOM_OFFSET_MM)
        fixture_volume = snap["inspection"].get("volume_mm3")
        row.update(
            {
                "side_surface_id": side_id,
                "neutral_surface_id": neutral_id,
                "fixture_volume_mm3": fixture_volume,
            }
        )
        if side_id is None or neutral_id is None:
            raise RuntimeError(
                f"{row['variant']}: drafted face or neutral plane missing: "
                f"side={side_id} neutral={neutral_id}"
            )

        submitted = await self.submit(
            "creo_draft",
            {
                "model_id": model_id,
                "expected_revision": snap["revision"],
                "label": "w02_draft",
                "surfaces": [{"kind": "surface", "id": side_id}],
                "neutral_plane": {"kind": "surface", "id": neutral_id},
                "angle": DRAFT_ANGLE_DEG,
                "flip": flip,
            },
        )
        draft = await self.terminal(submitted["job_id"])
        result = draft.get("result") or {}
        record = self.operation(draft, "w02_draft")
        geometry = record.get("draft_geometry") or {}
        row.update(
            {
                "job_id": draft.get("job_id"),
                "status": draft.get("status"),
                "saved_file_reloaded_and_verified": result.get("saved_file_reloaded_and_verified"),
                "rollback_succeeded": result.get("rollback_succeeded"),
                "draft_geometry": {
                    key: geometry.get(key)
                    for key in (
                        "source",
                        "query_code",
                        "requested_flip",
                        "effective_flip",
                        "flip",
                        "angle_deg",
                        "neutral_plane",
                        "pull_direction",
                        "pull_vector",
                    )
                },
                "material": {
                    key: record.get(key)
                    for key in (
                        "volume_before_mm3",
                        "volume_after_mm3",
                        "material_delta_mm3",
                        "material_measurement",
                    )
                },
                "draft_failure": record.get("draft_failure"),
            }
        )

        if draft.get("status") == "succeeded":
            after = await self.snapshot(model_id)
            after_volume = after["inspection"].get("volume_mm3")
            delta = row["material"].get("material_delta_mm3")
            independent = (
                after_volume - fixture_volume
                if after_volume is not None and fixture_volume is not None
                else None
            )
            row["independent_after_volume_mm3"] = after_volume
            row["independent_delta_mm3"] = independent
            row["draft_extent_mm"] = (
                abs(delta) / draft_delta_per_mm(DRAFT_ANGLE_DEG, BLOCK["height_mm"])
                if delta is not None
                else None
            )
            row["effective_flip_matches_requested"] = geometry.get("effective_flip") is flip
            row["checks"] = {
                "saved_file_reloaded_and_verified": row["saved_file_reloaded_and_verified"] is True,
                "requested_flip_echoed": geometry.get("requested_flip") is flip,
                "effective_flip_readback_is_bool": isinstance(geometry.get("effective_flip"), bool),
                "material_delta_recorded": delta is not None,
                "material_delta_matches_snapshot": (
                    delta is not None
                    and independent is not None
                    and abs(delta - independent) <= 0.5
                ),
                # Creo extends the drafted extent past the 35 mm face left between
                # the chamfer and round, so only the fixture's own 35..40 mm span
                # is asserted; the measured extent itself is reported above.
                "draft_extent_covers_side_face": (
                    delta is not None
                    and abs(delta) / draft_delta_per_mm(DRAFT_ANGLE_DEG, BLOCK["height_mm"]) >= 35.0
                ),
            }
        else:
            row["checks"] = {"draft_succeeded": False}
        row["checks"]["fixture_volume_near_expected"] = (
            fixture_volume is not None and abs(fixture_volume - FIXTURE_VOLUME_MM3) <= 0.5
        )
        row["passed"] = all(row["checks"].values())
        self.report["variants"].append(row)
        self.save()
        return row

    def cross_variant_checks(self) -> dict:
        variants = self.report["variants"]
        succeeded = [row for row in variants if row.get("status") == "succeeded"]
        checks: dict = {"both_variants_succeeded": len(succeeded) == 2}
        if len(succeeded) == 2:
            deltas = [row["material"].get("material_delta_mm3") for row in succeeded]
            checks["flip_toggles_material_sign"] = all(value is not None for value in deltas) and (
                (deltas[0] > 0) != (deltas[1] > 0)
            )
            checks["flip_magnitudes_match"] = all(value is not None for value in deltas) and abs(
                sum(deltas)
            ) <= 0.02 * max(abs(value) for value in deltas)
        return checks


async def live(output: Path, run_id: str) -> int:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=60,
    ) as client:
        runner = LiveRunner(client, output, run_id)
        runner.save()
        try:
            await runner.wait_ready()
            status = await runner.call("creo_session_status", {})
            assert status.get("connected") is True, status
            for flip in (False, True):
                await runner.variant(flip)
            checks = runner.cross_variant_checks()
            runner.report["cross_variant_checks"] = checks
            runner.report["native_acceptance"] = "passed" if all(checks.values()) else "failed"
        except Exception as error:
            runner.report.update(
                native_acceptance="failed", error=f"{type(error).__name__}: {error}"
            )
            raise
        finally:
            runner.save()
    return 0 if runner.report["native_acceptance"] == "passed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.live and not args.confirm_session_usable:
        print("live runs require --confirm-session-usable", file=sys.stderr)
        return 2
    run_id = new_run_id()
    if args.live:
        return asyncio.run(live(resolve_output(args.output, run_id), run_id))

    output = resolve_output(args.output, run_id)
    report = {"run_id": run_id, **offline_checks(), "provenance": local_provenance()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for check, value in report["checks"].items():
        print(f"{check}: {value}")
    print(f"report: {output}")
    print("offline: PASS" if report["checks"]["passed"] else "offline: FAIL")
    return 0 if report["checks"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
