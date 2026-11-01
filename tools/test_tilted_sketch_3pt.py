"""BUG-097 Q06 L2 live evidence: three-point oblique sketch from the archived smoke case.

The archived ``smoke_3pt_min_repro.json`` is re-expressed through the frozen
FEAT-053 ``through_points`` contract (the only conversion performed). The plan
creates three datum points, a three-point plane, a closed triangle sketch on
that plane and a symmetric 9.87008714331235 mm extrude.

Offline mode validates the converted plan, the independent triangle-area oracle
and the expected section frame; it never connects to Creo. ``--live`` requires
``--confirm-session-usable`` and an operator-confirmed session, and records:

* the sketch operation's ``section_location`` block (L1 UV mapping evidence);
* the terminal job, ``saved_file_reloaded_and_verified`` and revision;
* the real extruded volume against the independent area x depth oracle;
* on failure, the bounded ``feature_errors`` block (L2 CompleteFeature evidence).

This is substitute evidence for the archived original job: the original native
log and job id were not shipped with the feedback package.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.test_datum_plane_through_points import converted_smoke_operations  # noqa: E402
from version import VERSION  # noqa: E402

SMOKE_POINTS = {
    "dpa0": [-95.191114, 40.0, -88.395141],
    "dpb0": [95.191114, 40.0, 88.395141],
    "dpd0": [94.701973, 50.416667, 89.27114],
}
TRIANGLE_UV = [[0.0, 0.0], [190.382228, 22.394433], [189.893088, 32.838154]]
DEPTH_MM = 9.87008714331235  # archived original precision
VOLUME_RELATIVE_TOLERANCE = 1e-6


def triangle_area_mm2(points: list[list[float]]) -> float:
    (x0, y0), (x1, y1), (x2, y2) = points
    return abs((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)) / 2.0


def expected_volume_mm3() -> float:
    return triangle_area_mm2(TRIANGLE_UV) * DEPTH_MM


def expected_normal() -> list[float]:
    a, b, c = (SMOKE_POINTS["dpa0"], SMOKE_POINTS["dpb0"], SMOKE_POINTS["dpd0"])
    ab = [b[i] - a[i] for i in range(3)]
    ac = [c[i] - a[i] for i in range(3)]
    cross = [
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    ]
    length = math.sqrt(sum(value * value for value in cross))
    return [value / length for value in cross]


def provenance() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True, timeout=15
        ).stdout.strip()

    names = set(
        git("ls-files", "--", "*.py", "native/*.h", "native/*.hpp", "native/*.cpp").splitlines()
    )
    names.update({"tools/test_tilted_sketch_3pt.py", "tests/unit/test_tilted_sketch_3pt.py"})
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


def offline_checks() -> dict:
    from creo_mechdog.schema import validate_operations

    operations = converted_smoke_operations()
    validate_operations(operations)
    kinds = [operation["op"] for operation in operations]
    assert kinds == [
        "datum_points",
        "datum_points",
        "datum_points",
        "datum_plane",
        "sketch",
        "extrude",
    ], kinds
    plane = operations[3]["reference"]
    assert plane == {"kind": "through_points", "points": ["dpa0", "dpb0", "dpd0"]}, plane
    sketch = operations[4]
    assert sketch["dimensioning"] == "coordinates", sketch
    assert sketch["plane"]["reference"] == {"kind": "datum_feature", "label": "pl00a"}, sketch
    assert operations[5]["depth"] == DEPTH_MM, operations[5]
    assert operations[5]["direction"] == "symmetric", operations[5]
    area = triangle_area_mm2(TRIANGLE_UV)
    volume = expected_volume_mm3()
    assert 900.0 < area < 1100.0, area
    normal = expected_normal()
    assert abs(math.sqrt(sum(value * value for value in normal)) - 1.0) < 1e-12, normal
    return {
        "operation_kinds": kinds,
        "triangle_area_mm2": area,
        "expected_volume_mm3": volume,
        "expected_normal": normal,
        "depth_mm": DEPTH_MM,
        "oracle": "independent closed-form triangle area x symmetric depth",
    }


class Runner:
    def __init__(self, client: Any, output: Path) -> None:
        self.client = client
        self.output = output
        self.report: dict = {
            "task": "BUG-097 Q06 L2",
            "scope": (
                "archived smoke_3pt_min_repro converted to FEAT-053 through_points: "
                "oblique sketch L1 section_location, complete-feature L2, volume, save/reload"
            ),
            "fixture": "smoke_3pt_min_repro (substitute for the missing original job log)",
            "offline": offline_checks(),
            "native_acceptance": "not_run",
            "cases": [],
            "calls": [],
            "toolkit_serial": True,
            "provenance": provenance(),
        }

    def save(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def _invoke(self, name: str, args: dict) -> Any:
        record = {
            "tool": name,
            "args": copy.deepcopy(args),
            "started_at": time.time(),
            "response_received": False,
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
            call_state="returned",
            finished_at=time.time(),
            is_error=result.is_error,
            result=result.structured_content,
            content=str(result.content),
        )
        self.save()
        return result

    async def call(self, name: str, args: dict) -> dict:
        result = await self._invoke(name, args)
        if result.is_error:
            raise RuntimeError(f"{name}: {result.content}")
        return result.structured_content

    async def snapshot(self, model_id: str) -> dict:
        from creo_mechdog.query_client import read_full_model

        return await read_full_model(self.call, model_id)

    async def wait_job(self, job_id: str, expected: str, budget: float = 480) -> dict:
        deadline = time.monotonic() + budget
        while True:
            terminal = await self.call("creo_get_job", {"job_id": job_id})
            if terminal["status"] not in ("queued", "running"):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Job {job_id} did not reach a terminal state; do not resubmit")
            await asyncio.sleep(1)
        assert terminal["status"] == expected, terminal
        return terminal

    def projection_span(self, body: dict, normal: list[float]) -> float | None:
        bbox = body.get("bbox") or {}
        low, high = bbox.get("min"), bbox.get("max")
        if not (isinstance(low, list) and isinstance(high, list)):
            return None
        values = []
        for mask in range(8):
            corner = [high[i] if mask & (1 << i) else low[i] for i in range(3)]
            values.append(sum(corner[i] * normal[i] for i in range(3)))
        return max(values) - min(values)

    async def run(self, run_tag: str) -> None:
        from tools.mcp_readiness import wait_for_startup

        self.report["capabilities"] = await self.call("creo_capabilities", {})
        self.report["environment"] = await self.call("creo_check_environment", {})
        self.report["native_acceptance"] = "starting"
        self.save()
        try:
            await wait_for_startup(self.client, self.report, self.output)
            status = await self.call("creo_session_status", {})
            assert status["connected"] is True, status
            self.report["native_acceptance"] = "running"
            created = await self.call("creo_new_part", {"model_name": f"q06l2_{run_tag}"})
            await self.wait_job(created["job_id"], "succeeded")
            model_id = created["model_id"]
            before = await self.snapshot(model_id)
            operations = converted_smoke_operations()
            submitted = await self.call(
                "creo_execute_plan",
                {
                    "model_id": model_id,
                    "expected_revision": before["revision"],
                    "operations": operations,
                },
            )
            terminal = await self.wait_job(submitted["job_id"], "succeeded")
            result = terminal["result"]
            assert result["saved_file_reloaded_and_verified"] is True, terminal
            records = {record.get("label"): record for record in result["operations"]}
            sketch = records["smk"]
            section_location = sketch.get("section_location")
            assert isinstance(section_location, dict), sketch
            assert section_location.get("matrix_identity") is True, section_location
            assert section_location.get("identity_plausible") is False, section_location
            assert section_location.get("uv_mapping") == "frame_basis", section_location
            after = await self.snapshot(model_id)
            assert after["revision"] > before["revision"], (before["revision"], after["revision"])
            volume = after["inspection"]["volume_mm3"]
            expected = expected_volume_mm3()
            deviation = abs(volume - expected) / expected
            assert deviation <= VOLUME_RELATIVE_TOLERANCE, (volume, expected, deviation)
            bodies = [body for body in after["inspection"]["bodies"] if body.get("has_geometry")]
            assert len(bodies) == 1, bodies
            normal = expected_normal()
            span = self.projection_span(bodies[0], normal)
            if span is not None:
                assert abs(span - DEPTH_MM) <= 1e-3, (span, DEPTH_MM)
            aliases = after.get("aliases") or {}
            for label in ("dpa0", "dpb0", "dpd0", "pl00a", "smk", "smk_ex"):
                assert label in aliases, (label, sorted(aliases))
            self.report["cases"].append(
                {
                    "case": "oblique_triangle_3pt",
                    "model_id": model_id,
                    "job_id": submitted["job_id"],
                    "revision_before": before["revision"],
                    "revision_after": after["revision"],
                    "saved_file_reloaded_and_verified": True,
                    "section_location": section_location,
                    "sketch_frame": {
                        key: sketch.get(key) for key in ("origin", "normal", "u_axis", "v_axis")
                    },
                    "expected_volume_mm3": expected,
                    "actual_volume_mm3": volume,
                    "relative_deviation": deviation,
                    "normal_thickness_mm": span,
                    "aliases": sorted(aliases),
                    "passed": True,
                }
            )
            self.report["native_acceptance"] = "passed"
        except Exception as error:
            self.report["native_acceptance"] = "failed"
            self.report["error"] = f"{type(error).__name__}: {error}"
            failure = None
            for record in reversed(self.report["calls"]):
                payload = record.get("result") or {}
                if record.get("is_error") or (
                    isinstance(payload, dict) and payload.get("status") == "failed"
                ):
                    failure = {
                        "tool": record.get("tool"),
                        "status": payload.get("status"),
                        "result": payload,
                        "content": record.get("content"),
                    }
                    break
            self.report["failure"] = failure
            raise
        finally:
            self.save()


async def live(output: Path, run_tag: str) -> None:
    from tools.mcp_readiness import require_manual_start

    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT),
        read_timeout_seconds=60,
    ) as client:
        runner = Runner(client, output)
        runner.save()
        await runner.run(run_tag)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.live and not args.confirm_session_usable:
        parser.error("--live requires --confirm-session-usable and verified session admission")
    run_tag = uuid.uuid4().hex[:8]
    if not args.live:
        report = {
            "task": "BUG-097 Q06 L2",
            "mode": "offline",
            "live_execution": "not_run",
            "offline": offline_checks(),
            "provenance": provenance(),
        }
        path = args.output or ROOT / "build" / "tilted_sketch_3pt" / run_tag / "report.json"
        if path.exists():
            parser.error(f"refusing to overwrite {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path)
        return 0
    path = args.output or ROOT / "build" / "tilted_sketch_3pt" / run_tag / "report.json"
    if path.exists():
        parser.error(f"refusing to overwrite {path}")
    asyncio.run(live(path, run_tag))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
