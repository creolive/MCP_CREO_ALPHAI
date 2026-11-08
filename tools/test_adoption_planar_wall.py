"""FEAT-058 acceptance driver: native rectangular planar wall.

Every run writes into its own ``build/planar_wall/<UTC stamp>/`` directory and
records the source identity it ran against (commit, branch, dirty flag, per-file
SHA256 of the implementation, worker digest), so a later rerun never overwrites
the evidence of an earlier one.

The offline half runs by default and decides everything that does not need Creo:
schema admission, the empty-sheetmetal rule, internal-name collisions, the
feature-identity and downstream-dependency rules, the square case, the signed
frame envelope (including the sorted-world-bbox and offset-origin fixtures that
must be rejected), the R03 geometry gauge (no-API verification, conflict refusal
and the current_plan context), and a controlled compile with the body-API
declaration forced off. The compile proves the branch is buildable only; it is
not a Creo 10 runtime result.

The live half (``--live --confirm-session-usable``) covers the review matrix:

  primary   100x60x1 -> 6000 mm3, resize to 120x80 -> 9600 mm3, same feature id,
            plus the admission refusals (non-empty model, unknown label, wall
            created by another operation);
  negative  the same wall with direction=negative: envelope n[-1,0];
  planes    XZ and YZ supports;
  square    a 60x60 square resized to 90x60 (a square is not a resize proof);
  large     185x232x1 (42920 mm3) build;
  single_plan create then resize in one plan: the loaded receipt must say
            current_plan because the wall was never saved and reloaded;
  downstream a flange attached to the wall turns it into a parent; the in-place
            resize is then refused before a job exists;
  rollback  the default conversion-template model refuses the native wall
            natively, keeps its revision, and still accepts the legacy first wall
            afterwards (rollback leaves the model editable);
  legacy    the documented conversion-template recipe plus a flange chain
            (42920 mm3 first wall) still builds.

Usage:
  python tools/test_adoption_planar_wall.py
  python tools/test_adoption_planar_wall.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

LENGTH = 100.0
WIDTH = 60.0
THICKNESS = 1.0
RESIZED_LENGTH = 120.0
RESIZED_WIDTH = 80.0
SQUARE_SIDE = 60.0
SQUARE_RESIZE = (90.0, 60.0)
BASE_PLATE_VOLUME_MM3 = 42920.0
LARGE_LENGTH = 185.0
LARGE_WIDTH = 232.0
SHEETMETAL_TEMPLATE = "mmns_part_sheetmetal_abs.prt"
SOLID_TEMPLATE = "mmns_part_solid_abs.prt"
# R03: every required combination, frozen as data. The controlled compile
# forces the no-API branch; the live half is the only runtime evidence.
R03_MATRIX = (
    ("primary_100x60_to_120x80", "100x60x1 -> 120x80x1, XY, positive, cross-job"),
    ("large_185x232", "185x232x1, XY, positive"),
    ("planes", "XY / XZ / YZ"),
    ("negative", "negative direction, envelope n[-1,0]"),
    ("single_plan", "create + resize in one plan, current_plan context"),
    ("saved_thickness", "cross-job resize reads the saved gauge"),
    ("continue_after_reject", "a refused edit leaves the model editable"),
)
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
# Creo model names are lowercase, at most 31 characters (BUG-069), so the run
# tag is a short lowercase hex stamp instead of the report timestamp.
RUN_ID = format(int(time.time()), "x")
SOURCE_FILES = (
    "bridge.py",
    "generic_bridge.py",
    "server.py",
    "src/creo_mechdog/native_planar_wall.py",
    "src/creo_mechdog/schema.py",
    "src/creo_mechdog/capabilities.py",
    "native/planar_wall.cpp",
    "native/planar_wall.h",
    "native/generic.cpp",
    "tools/test_adoption_planar_wall.py",
)


def source_identity() -> dict:
    """What this run actually executed, so the report is self-contained."""
    from creo_mechdog.source_provenance import local_provenance

    evidence = local_provenance(ROOT, SOURCE_FILES)
    worker = ROOT / "build" / "creo_worker.exe"
    return {
        "commit": evidence["commit"],
        "branch": evidence["branch"],
        "dirty": evidence["dirty"],
        "git_status": evidence["git_status"],
        **{
            key: evidence[key]
            for key in ("source_scope", "source_status", "source_errors", "source_file_count")
        },
        "source_sha256": evidence["source_sha256"],
        "source_fingerprint": evidence["source_fingerprint"],
        "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest()
        if worker.is_file()
        else None,
    }


def wait(job_id: str, timeout: float = 300.0) -> dict:
    terminal = {"succeeded", "failed", "aborted", "cancelled", "unknown_outcome"}
    deadline = time.time() + timeout
    record: dict = {}
    while time.time() < deadline:
        path = ROOT / "jobs" / job_id / "job.json"
        if path.is_file():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") in terminal:
                return record
        time.sleep(1.0)
    raise SystemExit(f"job {job_id} never finished: {record.get('status')}")


def operation_detail(job: dict, op: str) -> dict:
    for item in (job.get("result") or {}).get("operations") or []:
        if isinstance(item, dict) and item.get("op") == op:
            return item
    return {}


def inspection_of(job_id: str) -> dict:
    """Full inspection the executor kept as a sidecar next to the job."""
    for path in sorted((ROOT / "jobs" / job_id).glob("inspection-verified-*.json")):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {}


def eligible_wall_edge(inspection: dict) -> int | None:
    """First wall-contour edge the native probe accepted, if any."""
    check = inspection.get("wall_contour_check") or {}
    for edge in check.get("edges") or []:
        if isinstance(edge, dict) and edge.get("wall_contour_query_code") == 0:
            edge_id = edge.get("edge_id")
            if isinstance(edge_id, int):
                return edge_id
    return None


def native_lines(job_id: str, tokens: tuple[str, ...]) -> list[str]:
    log = ROOT / "jobs" / job_id / "native.log"
    if not log.is_file():
        return []
    return [
        line
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
        if any(token in line for token in tokens)
    ][-12:]


def report_directory() -> Path:
    target = ROOT / "build" / "planar_wall" / STAMP
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_report(mode: str, report: dict, directory: Path) -> Path:
    target = directory / f"adoption_{mode}.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


class Checks:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, name: str, ok: bool, detail: object = None) -> bool:
        self.items.append({"check": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    @property
    def failed(self) -> list[str]:
        return [item["check"] for item in self.items if not item["ok"]]


def model_record(model_type: str, has_solid: bool) -> dict:
    return {
        "model_type": model_type,
        "inspection_summary": {"has_solid": has_solid},
        "aliases": {},
    }


def controlled_no_api_compile(directory: Path) -> dict:
    """Compile the worker with the body-API declaration forced off.

    R03's controlled compile proves the no-API branch is buildable. It does not
    link, start Creo or exercise runtime behaviour, so it is not evidence that a
    Creo 10 session behaves like this machine. The reviewed worker is untouched:
    the object and log stay in this run's directory.
    """
    import bridge
    from creo_mechdog.build_support import compiler_setup_script

    try:
        settings = bridge.config()
        sdk = Path(settings["creo_root"]) / "Common Files/protoolkit/includes"
    except Exception as error:  # noqa: BLE001 - the missing toolchain is the finding
        return {"compiled": False, "reason": f"compiler configuration unavailable: {error}"}
    obj = directory / "worker_no_thickness_api.obj"
    script = directory / "no_thickness_api_build.cmd"
    log = directory / "no_thickness_api_build.log"
    script.write_text(
        "@echo off\n"
        "setlocal DisableDelayedExpansion\n"
        f"{compiler_setup_script(settings)}\n"
        f"cl /nologo /MD /EHsc /std:c++17 /bigobj /W3 /we4552 /DPRO_MACHINE=36 "
        f"/DPRO_OS=4 /DPRO_USE_VAR_ARGS /DMECHDOG_FORCE_NO_SHEETMETAL_THICKNESS_API "
        f'/I"{sdk}" /c "{ROOT / "native/worker.cpp"}" /Fo"{obj}"\n'
        "exit /b %errorlevel%\n",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(script)],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired as error:
        log.write_text(f"timeout: {error}", encoding="utf-8")
        return {"compiled": False, "reason": "controlled compile timed out"}
    output = (result.stdout or "") + (result.stderr or "")
    log.write_text(output, encoding="utf-8")
    return {
        "compiled": result.returncode == 0 and obj.is_file(),
        "returncode": result.returncode,
        "define": "MECHDOG_FORCE_NO_SHEETMETAL_THICKNESS_API",
        "object": str(obj),
        "log": str(log),
        "log_tail": output[-1200:],
    }


def offline_checks(directory: Path) -> Checks:
    from creo_mechdog import native_planar_wall as pwall
    from creo_mechdog.schema import validate_operations

    checks = Checks()
    checks.add(
        "R03 no-API matrix frozen",
        tuple(name for name, _ in R03_MATRIX)
        == (
            "primary_100x60_to_120x80",
            "large_185x232",
            "planes",
            "negative",
            "single_plan",
            "saved_thickness",
            "continue_after_reject",
        ),
        [name for name, _ in R03_MATRIX],
    )
    compiled = controlled_no_api_compile(directory)
    checks.add(
        "controlled no-API worker compiles",
        compiled["compiled"],
        dict(compiled, note="compile-only; not a Creo 10 runtime result"),
    )
    create = {
        "op": "sheetmetal_planar_wall",
        "label": "wall",
        "plane": "XY",
        "length": LENGTH,
        "width": WIDTH,
        "thickness": THICKNESS,
    }
    resize = {
        "op": "resize_sheetmetal_planar_wall",
        "feature": "wall",
        "length": RESIZED_LENGTH,
        "width": RESIZED_WIDTH,
    }
    validated = validate_operations([create, resize])
    checks.add(
        "schema admits both operations",
        validated[0]["op"] == "sheetmetal_planar_wall"
        and validated[1]["op"] == "resize_sheetmetal_planar_wall",
    )
    for name, broken in (
        ("zero length refused", dict(create, length=0)),
        ("negative thickness refused", dict(create, thickness=-1)),
        ("over-long label refused", dict(create, label="w" * 26)),
        ("unknown plane refused", dict(create, plane="AB")),
        ("unknown direction refused", dict(create, direction="sideways")),
    ):
        try:
            validate_operations([broken])
            checks.add(name, False, "no error raised")
        except Exception as error:  # noqa: BLE001 - the refusal is the evidence
            checks.add(name, True, str(error).splitlines()[0][:160])

    empty = model_record("sheetmetal", False)
    checks.add("create admitted on empty sheetmetal", pwall.create_problem(empty) is None)
    checks.add(
        "create refused on a part model",
        "sheetmetal" in (pwall.create_problem(model_record("part", False)) or ""),
    )
    checks.add(
        "create refused on a non-empty sheetmetal model",
        "already has geometry" in (pwall.create_problem(model_record("sheetmetal", True)) or ""),
    )
    checks.add(
        "internal sketch name protected",
        "wall_sk" in (pwall.create_problem(empty, {"wall_sk": {"op": "sketch"}}, create) or ""),
    )
    checks.add(
        "name collision detected in the plan",
        pwall.name_conflict(["wall", "wall_sk"], set()) == []
        and pwall.name_conflict(["wall_sk", "wall_sk"], set()) == ["wall_sk"],
    )
    checks.add(
        "same plan create then resize admitted",
        _admits(pwall, empty, [create, resize]),
    )
    checks.add(
        "resize of an undeclared wall refused",
        not _admits(pwall, empty, [resize]),
    )

    aliases = {"wall": {"op": "sheetmetal_planar_wall", "feature_id": 49}}
    checks.add(
        "resize admitted for a planar wall", pwall.resize_problem(empty, resize, aliases) is None
    )
    checks.add(
        "resize refused for an unknown label",
        "Unknown" in (pwall.resize_problem(empty, resize, {}) or ""),
    )
    checks.add(
        "resize refused for a wall made by another operation",
        "only walls created by"
        in (
            pwall.resize_problem(
                empty, resize, {"wall": {"op": "sheetmetal_wall", "feature_id": 47}}
            )
            or ""
        ),
    )
    features = [{"id": 49, "child_ids": [52]}]
    checks.add(
        "resize refused with a downstream dependency",
        "downstream dependencies" in (pwall.resize_problem(empty, resize, aliases, features) or ""),
    )

    created = _created_result()
    projection = pwall.result_projection(created)
    checks.add("created wall projection verified", projection["verified"], projection["problems"])
    checks.add("created perimeter covers four dimensions", projection["dimension_count"] >= 4)

    square = pwall.result_projection(
        dict(
            created,
            length=SQUARE_SIDE,
            width=SQUARE_SIDE,
            volume_mm3=SQUARE_SIDE * SQUARE_SIDE * THICKNESS,
            envelope={
                "u": {"min": 0.0, "max": SQUARE_SIDE},
                "v": {"min": 0.0, "max": SQUARE_SIDE},
                "n": {"min": 0.0, "max": THICKNESS},
            },
        )
    )
    checks.add(
        "square reported with both axes",
        square["square"] is True and square["verified"] and square["dimension_count"] >= 4,
        square["problems"],
    )
    under = pwall.result_projection(dict(created, dimension_count=1))
    checks.add("single-dimension square refused", not under["verified"], under["problems"])

    rotated = {
        "origin": [0.0, 0.0, 0.0],
        "u_axis": [0.0, 1.0, 0.0],
        "v_axis": [-1.0, 0.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
    }
    extents = pwall.signed_extents(rotated, [[-WIDTH, 0.0, 0.0], [0.0, LENGTH, THICKNESS]])
    checks.add(
        "signed envelope keeps u/v in frame axes",
        abs(extents["u"]["max"] - LENGTH) < 1e-9 and abs(extents["v"]["max"] - WIDTH) < 1e-9,
        extents,
    )
    sorted_box = {
        "u": {"min": 0.0, "max": WIDTH},
        "v": {"min": 0.0, "max": LENGTH},
        "n": {"min": 0.0, "max": THICKNESS},
    }
    checks.add(
        "sorted world bbox rejected",
        pwall.envelope_problem(rotated, sorted_box, LENGTH, WIDTH, THICKNESS) is not None,
    )
    checks.add(
        "opposite-side growth rejected",
        pwall.envelope_problem(
            created["frame"],
            {
                "u": {"min": 0.0, "max": LENGTH},
                "v": {"min": 0.0, "max": WIDTH},
                "n": {"min": -THICKNESS, "max": 0.0},
            },
            LENGTH,
            WIDTH,
            THICKNESS,
            "positive",
        )
        is not None,
    )
    checks.add(
        "negative direction accepted on the negative side",
        pwall.envelope_problem(
            created["frame"],
            {
                "u": {"min": 0.0, "max": LENGTH},
                "v": {"min": 0.0, "max": WIDTH},
                "n": {"min": -THICKNESS, "max": 0.0},
            },
            LENGTH,
            WIDTH,
            THICKNESS,
            "negative",
        )
        is None,
    )
    checks.add(
        "offset origin rejected",
        not pwall.result_projection(
            dict(
                created,
                envelope={
                    "u": {"min": 5.0, "max": 5.0 + LENGTH},
                    "v": {"min": 0.0, "max": WIDTH},
                    "n": {"min": 0.0, "max": THICKNESS},
                },
            )
        )["verified"],
    )
    checks.add(
        "missing volume rejected",
        not pwall.result_projection(dict(created, volume_mm3=None))["verified"],
    )
    checks.add(
        "unread gauge rejected",
        not pwall.result_projection(
            dict(created, thickness_verified=False, thickness_measured_mm=None)
        )["verified"],
    )
    checks.add(
        "gauge disagreement rejected",
        not pwall.result_projection(dict(created, thickness_measured_mm=3.71))["verified"],
    )

    resized = pwall.result_projection(
        dict(
            created,
            op="resize_sheetmetal_planar_wall",
            length=RESIZED_LENGTH,
            width=RESIZED_WIDTH,
            volume_mm3=RESIZED_LENGTH * RESIZED_WIDTH * THICKNESS,
            feature_id_before=49,
            thickness_loaded_mm=THICKNESS,
            envelope={
                "u": {"min": 0.0, "max": RESIZED_LENGTH},
                "v": {"min": 0.0, "max": RESIZED_WIDTH},
                "n": {"min": 0.0, "max": THICKNESS},
            },
        )
    )
    checks.add(
        "resize keeps feature identity", resized["feature_id_unchanged"] and resized["verified"]
    )
    rebuilt = pwall.result_projection(
        dict(
            created,
            op="resize_sheetmetal_planar_wall",
            feature_id_before=49,
            feature_id=57,
            length=RESIZED_LENGTH,
            width=RESIZED_WIDTH,
            envelope={
                "u": {"min": 0.0, "max": RESIZED_LENGTH},
                "v": {"min": 0.0, "max": RESIZED_WIDTH},
                "n": {"min": 0.0, "max": THICKNESS},
            },
        )
    )
    checks.add("rebuilt wall detected", not rebuilt["verified"], rebuilt["problems"])

    # --- R03: the no-body-API geometry gauge --------------------------------
    geometry_receipt = {
        "status": "verified",
        "source": "geometry_normal_span",
        "value_mm": THICKNESS,
        "reason": None,
        "context": "current_plan",
    }
    geometry = pwall.result_projection(
        dict(
            created,
            thickness_verified=False,
            thickness_measured_mm=None,
            thickness_geometry_span_mm=THICKNESS,
            thickness_validation=geometry_receipt,
        )
    )
    checks.add(
        "missing-API geometry gauge verifies without the API boolean",
        geometry["verified"]
        and geometry["thickness_verified"] is False
        and geometry["thickness_measured_mm"] is None
        and geometry["thickness_validation"]["source"] == "geometry_normal_span",
        geometry["problems"],
    )
    geometry_mismatch = pwall.result_projection(
        dict(
            created,
            thickness_verified=False,
            thickness_measured_mm=None,
            thickness_geometry_span_mm=2.0,
            thickness_validation=dict(
                geometry_receipt,
                status="mismatch",
                value_mm=2.0,
                reason="thickness_measured_mismatch",
            ),
        )
    )
    checks.add(
        "missing-API geometry conflict refused",
        not geometry_mismatch["verified"]
        and geometry_mismatch["thickness_validation"]["status"] == "mismatch",
        geometry_mismatch["problems"],
    )
    same_plan = dict(
        created,
        op="resize_sheetmetal_planar_wall",
        feature_id_before=49,
        length=RESIZED_LENGTH,
        width=RESIZED_WIDTH,
        volume_mm3=RESIZED_LENGTH * RESIZED_WIDTH * THICKNESS,
        envelope={
            "u": {"min": 0.0, "max": RESIZED_LENGTH},
            "v": {"min": 0.0, "max": RESIZED_WIDTH},
            "n": {"min": 0.0, "max": THICKNESS},
        },
        thickness_verified=False,
        thickness_measured_mm=None,
        thickness_loaded_mm=None,
        thickness_geometry_span_mm=THICKNESS,
        thickness_validation=geometry_receipt,
        thickness_loaded_validation=geometry_receipt,
        wall_created_this_job=True,
    )
    same_plan_projection = pwall.result_projection(same_plan)
    checks.add(
        "same-plan create then resize reports current_plan",
        same_plan_projection["verified"]
        and same_plan_projection["thickness_loaded_validation"]["context"] == "current_plan",
        same_plan_projection["problems"],
    )
    borrowed = pwall.result_projection(dict(same_plan, wall_created_this_job=False))
    checks.add(
        "current_plan receipt without the create fact refused",
        not borrowed["verified"]
        and borrowed["thickness_loaded_validation"]["reason"]
        == "thickness_validation_current_plan_without_create",
        borrowed["problems"],
    )
    return checks


def _admits(pwall, model: dict, operations: list[dict]) -> bool:
    try:
        pwall.validate_plan(model, operations)
    except ValueError:
        return False
    return True


def _created_result() -> dict:
    return {
        "op": "sheetmetal_planar_wall",
        "feature": "wall",
        "feature_id": 49,
        "sketch": "wall_sk",
        "length": LENGTH,
        "width": WIDTH,
        "thickness": THICKNESS,
        "direction": "positive",
        "dimension_count": 8,
        "volume_mm3": LENGTH * WIDTH * THICKNESS,
        "frame": {
            "origin": [0.0, 0.0, 0.0],
            "u_axis": [1.0, 0.0, 0.0],
            "v_axis": [0.0, 1.0, 0.0],
            "normal": [0.0, 0.0, 1.0],
        },
        "envelope": {
            "u": {"min": 0.0, "max": LENGTH},
            "v": {"min": 0.0, "max": WIDTH},
            "n": {"min": 0.0, "max": THICKNESS},
        },
        "sheetmetal_body": True,
        "thickness_source": "parameter",
        "thickness_measured_mm": THICKNESS,
        "thickness_verified": True,
        "thickness_body_code": 0,
        "body_linked": True,
    }


def _create_op(
    label: str = "wall",
    plane: str = "XY",
    direction: str = "positive",
    length: float = LENGTH,
    width: float = WIDTH,
) -> dict:
    return {
        "op": "sheetmetal_planar_wall",
        "label": label,
        "plane": plane,
        "length": length,
        "width": width,
        "thickness": THICKNESS,
        "direction": direction,
    }


def _resize_op(label: str, length: float, width: float) -> dict:
    return {
        "op": "resize_sheetmetal_planar_wall",
        "feature": label,
        "length": length,
        "width": width,
    }


class Live:
    """Thin wrapper over generic_bridge for one model at a time."""

    def __init__(self) -> None:
        import generic_bridge

        self.bridge = generic_bridge

    def model(self, tag: str, template: str = SHEETMETAL_TEMPLATE) -> tuple[str, dict, dict]:
        submit = self.bridge.submit(
            [],
            model_name=f"pw_{tag}_{RUN_ID}"[:31],
            model_type="sheetmetal",
            template_name=template,
        )
        job = wait(submit["job_id"])
        return submit["job_id"], job, (job.get("result") or {})

    def plan(self, model_id: str, operations: list[dict]) -> tuple[str, dict]:
        revision = self.bridge.model_info(model_id).get("revision")
        submit = self.bridge.submit(operations, model_id=model_id, expected_revision=revision)
        job = wait(submit["job_id"])
        return submit["job_id"], job

    def projection(self, job: dict, op: str) -> dict:
        from creo_mechdog import native_planar_wall as pwall

        return pwall.result_projection(operation_detail(job, op))


def live_checks(report: dict) -> Checks:
    from creo_mechdog.schema import validate_operations

    checks = Checks()
    live = Live()
    scenarios: dict[str, dict] = report.setdefault("scenarios", {})

    # --- primary: create, refusals, in-place resize -------------------------
    tag, setup_job, setup_result = live.model("primary")
    summary = setup_result.get("inspection_summary") or {}
    scenarios["primary_setup"] = {
        "job_id": tag,
        "status": setup_job.get("status"),
        "message": setup_job.get("message"),
        "model_type": summary.get("model_type"),
        "has_solid": summary.get("has_solid"),
    }
    if not checks.add(
        "empty sheetmetal model created",
        setup_job.get("status") == "succeeded"
        and summary.get("model_type") == "sheetmetal"
        and summary.get("has_solid") is False,
        scenarios["primary_setup"],
    ):
        return checks
    model_id = setup_job["model_id"]
    report["model_id"] = model_id

    create_op = _create_op()
    validate_operations([create_op])
    job_id, job = live.plan(model_id, [create_op])
    projection = live.projection(job, "sheetmetal_planar_wall")
    scenarios["create"] = {
        "job_id": job_id,
        "status": job.get("status"),
        "message": job.get("message"),
        "revision": job.get("revision"),
        "saved_file_reloaded_and_verified": (job.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ),
        "volume_mm3": (job.get("result") or {}).get("inspection_summary", {}).get("volume_mm3"),
        "planar_wall": projection,
        "native_evidence": native_lines(job_id, ("PLANAR_WALL", "Toolkit call")),
    }
    if not checks.add(
        "native planar wall created", job.get("status") == "succeeded", job.get("message")
    ):
        return checks
    checks.add(
        "created volume is length*width*thickness",
        abs((projection["volume_mm3"] or 0) - LENGTH * WIDTH * THICKNESS) < 0.01,
        projection["volume_mm3"],
    )
    checks.add("created wall verified", projection["verified"], projection["problems"])
    checks.add(
        "created wall gauge read back from its body",
        projection["thickness_verified"] is True
        and abs((projection["thickness_measured_mm"] or 0) - THICKNESS) < 1e-9,
        projection["thickness_measured_mm"],
    )
    checks.add(
        "created wall carries four+ point dimensions",
        (projection["dimension_count"] or 0) >= 4,
        projection["dimension_count"],
    )
    checks.add(
        "created wall saved, reloaded and verified",
        scenarios["create"]["saved_file_reloaded_and_verified"] is True,
    )
    wall_feature = projection["feature_id"]
    wall_sketch = projection["sketch"]

    refusals = {}
    for name, ops in (
        ("create on a non-empty sheetmetal model", [dict(create_op, label="wall2")]),
        ("resize unknown label", [_resize_op("no_such_wall", 10.0, 10.0)]),
        ("resize a wall made by another operation", [_resize_op(wall_sketch, 10.0, 10.0)]),
    ):
        try:
            live.bridge.submit(
                ops,
                model_id=model_id,
                expected_revision=live.bridge.model_info(model_id).get("revision"),
            )
            refusals[name] = "NOT REFUSED"
        except ValueError as error:
            refusals[name] = str(error).splitlines()[0][:200]
        except Exception as error:  # noqa: BLE001 - record the real refusal text
            refusals[name] = f"{type(error).__name__}: {error}"[:200]
    checks.add(
        "live refusal matrix",
        all("NOT REFUSED" not in value for value in refusals.values()),
        refusals,
    )
    scenarios["refusals"] = refusals

    resize_op = _resize_op("wall", RESIZED_LENGTH, RESIZED_WIDTH)
    validate_operations([resize_op])
    job_id, job = live.plan(model_id, [resize_op])
    projection = live.projection(job, "resize_sheetmetal_planar_wall")
    scenarios["resize"] = {
        "job_id": job_id,
        "status": job.get("status"),
        "message": job.get("message"),
        "revision": job.get("revision"),
        "saved_file_reloaded_and_verified": (job.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ),
        "volume_mm3": (job.get("result") or {}).get("inspection_summary", {}).get("volume_mm3"),
        "planar_wall": projection,
        "native_evidence": native_lines(job_id, ("PLANAR_WALL", "Toolkit call")),
    }
    if checks.add(
        "in-place resize succeeded", job.get("status") == "succeeded", job.get("message")
    ):
        checks.add(
            "resized volume is length*width*thickness",
            abs((projection["volume_mm3"] or 0) - RESIZED_LENGTH * RESIZED_WIDTH * THICKNESS)
            < 0.01,
            projection["volume_mm3"],
        )
        checks.add("resize verified", projection["verified"], projection["problems"])
        checks.add(
            "resize kept the wall feature id",
            projection["feature_id"] == wall_feature and projection["feature_id_unchanged"],
            {"before": wall_feature, "after": projection["feature_id"]},
        )
        loaded_validation = projection["thickness_loaded_validation"] or {}
        gauge_ok = (
            projection["thickness_measured_mm"] is not None
            and abs((projection["thickness_measured_mm"] or 0) - THICKNESS) < 1e-9
            and projection["thickness_loaded_mm"] is not None
            and abs((projection["thickness_loaded_mm"] or 0) - THICKNESS) < 1e-9
        ) or (
            loaded_validation.get("status") == "verified"
            and loaded_validation.get("source") == "geometry_normal_span"
            and abs((loaded_validation.get("value_mm") or 0) - THICKNESS) < 1e-9
        )
        checks.add(
            "resize kept the 1 mm gauge",
            gauge_ok,
            {
                "measured": projection["thickness_measured_mm"],
                "loaded": projection["thickness_loaded_mm"],
                "loaded_validation": loaded_validation,
            },
        )
        checks.add(
            "resized wall saved, reloaded and verified",
            scenarios["resize"]["saved_file_reloaded_and_verified"] is True,
        )

    # --- R03: 185 x 232 -----------------------------------------------------
    tag, setup_job, _ = live.model("large")
    if checks.add("large model created", setup_job.get("status") == "succeeded"):
        job_id, job = live.plan(
            setup_job["model_id"],
            [_create_op(label="wall_large", length=LARGE_LENGTH, width=LARGE_WIDTH)],
        )
        projection = live.projection(job, "sheetmetal_planar_wall")
        scenarios["large"] = {
            "job_id": job_id,
            "status": job.get("status"),
            "message": job.get("message"),
            "planar_wall": projection,
        }
        checks.add(
            "185x232x1 wall verified",
            job.get("status") == "succeeded"
            and projection["verified"]
            and abs((projection["volume_mm3"] or 0) - LARGE_LENGTH * LARGE_WIDTH * THICKNESS)
            < 0.01,
            projection["problems"],
        )

    # --- R03: create then resize in one plan --------------------------------
    tag, setup_job, _ = live.model("singleplan")
    if checks.add("single-plan model created", setup_job.get("status") == "succeeded"):
        job_id, job = live.plan(
            setup_job["model_id"],
            [_create_op(label="wall_sp"), _resize_op("wall_sp", RESIZED_LENGTH, RESIZED_WIDTH)],
        )
        projection = live.projection(job, "resize_sheetmetal_planar_wall")
        loaded = projection["thickness_loaded_validation"] or {}
        scenarios["single_plan"] = {
            "job_id": job_id,
            "status": job.get("status"),
            "message": job.get("message"),
            "planar_wall": projection,
        }
        checks.add(
            "single-plan create then resize reports current_plan",
            job.get("status") == "succeeded"
            and projection["verified"]
            and loaded.get("context") == "current_plan",
            {"problems": projection["problems"], "loaded": loaded},
        )

    # --- negative direction -------------------------------------------------
    tag, setup_job, _ = live.model("negative")
    if checks.add("negative model created", setup_job.get("status") == "succeeded"):
        job_id, job = live.plan(
            setup_job["model_id"], [_create_op(label="wall_neg", direction="negative")]
        )
        projection = live.projection(job, "sheetmetal_planar_wall")
        scenarios["negative"] = {
            "job_id": job_id,
            "status": job.get("status"),
            "message": job.get("message"),
            "volume_mm3": (job.get("result") or {}).get("inspection_summary", {}).get("volume_mm3"),
            "planar_wall": projection,
        }
        checks.add(
            "negative direction built on the negative side",
            job.get("status") == "succeeded"
            and projection["verified"]
            and projection["direction"] == "negative"
            and abs(projection["envelope"]["n"]["min"] + THICKNESS) < 1e-6
            and abs(projection["envelope"]["n"]["max"]) < 1e-6,
            projection["problems"] or projection.get("envelope"),
        )

    # --- XZ / YZ supports ---------------------------------------------------
    for plane in ("XZ", "YZ"):
        tag, setup_job, _ = live.model(f"plane_{plane.lower()}")
        if not checks.add(f"{plane} model created", setup_job.get("status") == "succeeded"):
            continue
        job_id, job = live.plan(
            setup_job["model_id"], [_create_op(label=f"wall_{plane.lower()}", plane=plane)]
        )
        projection = live.projection(job, "sheetmetal_planar_wall")
        scenarios[f"plane_{plane.lower()}"] = {
            "job_id": job_id,
            "status": job.get("status"),
            "message": job.get("message"),
            "volume_mm3": (job.get("result") or {}).get("inspection_summary", {}).get("volume_mm3"),
            "planar_wall": projection,
        }
        checks.add(
            f"{plane} planar wall verified",
            job.get("status") == "succeeded"
            and projection["verified"]
            and abs((projection["volume_mm3"] or 0) - LENGTH * WIDTH * THICKNESS) < 0.01,
            projection["problems"],
        )

    # --- square then rectangle ---------------------------------------------
    tag, setup_job, _ = live.model("square")
    if checks.add("square model created", setup_job.get("status") == "succeeded"):
        square_model = setup_job["model_id"]
        job_id, job = live.plan(
            square_model,
            [
                {
                    "op": "sheetmetal_planar_wall",
                    "label": "square",
                    "plane": "XY",
                    "length": SQUARE_SIDE,
                    "width": SQUARE_SIDE,
                    "thickness": THICKNESS,
                }
            ],
        )
        created = live.projection(job, "sheetmetal_planar_wall")
        job_id2, job2 = live.plan(square_model, [_resize_op("square", *SQUARE_RESIZE)])
        resized = live.projection(job2, "resize_sheetmetal_planar_wall")
        scenarios["square"] = {
            "create_job": job_id,
            "create_status": job.get("status"),
            "create_planar_wall": created,
            "resize_job": job_id2,
            "resize_status": job2.get("status"),
            "resize_message": job2.get("message"),
            "resize_planar_wall": resized,
        }
        checks.add(
            "square wall built with both axes",
            job.get("status") == "succeeded"
            and created["square"] is True
            and created["verified"]
            and abs((created["volume_mm3"] or 0) - SQUARE_SIDE * SQUARE_SIDE * THICKNESS) < 0.01,
            created["problems"],
        )
        checks.add(
            "square resized to a rectangle in place",
            job2.get("status") == "succeeded"
            and resized["verified"]
            and resized["square"] is False
            and resized["feature_id"] == created["feature_id"]
            and abs((resized["volume_mm3"] or 0) - SQUARE_RESIZE[0] * SQUARE_RESIZE[1] * THICKNESS)
            < 0.01,
            {"problems": resized["problems"], "feature": resized["feature_id"]},
        )

    # --- downstream dependency ---------------------------------------------
    tag, setup_job, _ = live.model("downstream")
    if checks.add("downstream model created", setup_job.get("status") == "succeeded"):
        down_model = setup_job["model_id"]
        job_id, job = live.plan(down_model, [_create_op()])
        wall = live.projection(job, "sheetmetal_planar_wall")
        edge = eligible_wall_edge(inspection_of(job_id))
        scenario = {
            "create_job": job_id,
            "create_status": job.get("status"),
            "wall_feature_id": wall["feature_id"],
            "edge_id": edge,
        }
        scenarios["downstream"] = scenario
        if checks.add(
            "downstream wall built",
            job.get("status") == "succeeded" and wall["verified"],
            wall["problems"],
        ) and checks.add("wall contour edge found", isinstance(edge, int), edge):
            flange_job_id, flange_job = live.plan(
                down_model,
                [
                    {
                        "op": "sheetmetal_flange",
                        "label": "wall_flange",
                        "edge": {"kind": "edge", "id": edge},
                        "height": 20.0,
                        "angle": 90.0,
                        "radius": 1.0,
                    }
                ],
            )
            scenario["flange_job"] = flange_job_id
            scenario["flange_status"] = flange_job.get("status")
            scenario["flange_message"] = flange_job.get("message")
            children = []
            for feature in inspection_of(flange_job_id).get("features") or []:
                if isinstance(feature, dict) and feature.get("id") == wall["feature_id"]:
                    children = feature.get("child_ids") or []
            scenario["wall_child_ids"] = children
            checks.add(
                "flange attached to the native wall",
                flange_job.get("status") == "succeeded" and bool(children),
                {"status": flange_job.get("status"), "children": children},
            )
            try:
                live.bridge.submit(
                    [_resize_op("wall", RESIZED_LENGTH, RESIZED_WIDTH)],
                    model_id=down_model,
                    expected_revision=live.bridge.model_info(down_model).get("revision"),
                )
                scenario["resize_refusal"] = "NOT REFUSED"
            except ValueError as error:
                scenario["resize_refusal"] = str(error).splitlines()[0][:240]
            except Exception as error:  # noqa: BLE001
                scenario["resize_refusal"] = f"{type(error).__name__}: {error}"[:240]
            checks.add(
                "resize refused before a job for a wall with children",
                "NOT REFUSED" not in str(scenario["resize_refusal"]),
                scenario["resize_refusal"],
            )

    # --- native refusal, rollback, then a legal edit -----------------------
    tag, setup_job, setup_result = live.model("rollback", template=SOLID_TEMPLATE)
    scenario = {"setup_job": tag, "setup_status": setup_job.get("status")}
    scenarios["rollback"] = scenario
    if checks.add("conversion-template model created", setup_job.get("status") == "succeeded"):
        rollback_model = setup_job["model_id"]
        before = live.bridge.model_info(rollback_model).get("revision")
        job_id, job = live.plan(rollback_model, [_create_op()])
        scenario.update(
            create_job=job_id,
            create_status=job.get("status"),
            create_message=job.get("message"),
            revision_before=before,
            revision_after=(job.get("result") or {}).get("revision", job.get("revision")),
        )
        checks.add(
            "native planar wall refused on a non-sheetmetal part",
            job.get("status") == "failed" and "sheetmetal part" in (job.get("message") or ""),
            job.get("message"),
        )
        checks.add(
            "refused job left the revision unchanged",
            live.bridge.model_info(rollback_model).get("revision") == before,
            {"before": before, "after": live.bridge.model_info(rollback_model).get("revision")},
        )
        example = json.loads(
            (ROOT / "examples" / "sheetmetal_base_yz.json").read_text(encoding="utf-8")
        )
        validate_operations(example["operations"])
        legacy_job_id, legacy_job = live.plan(rollback_model, example["operations"])
        volume = (legacy_job.get("result") or {}).get("inspection_summary", {}).get("volume_mm3")
        scenario.update(
            legacy_job=legacy_job_id,
            legacy_status=legacy_job.get("status"),
            legacy_message=legacy_job.get("message"),
            legacy_volume_mm3=volume,
        )
        checks.add(
            "legacy first wall still accepted after the refusal",
            legacy_job.get("status") == "succeeded"
            and isinstance(volume, (int, float))
            and abs(volume - BASE_PLATE_VOLUME_MM3) < 0.01,
            scenario,
        )

    # --- legacy first wall plus flange chain -------------------------------
    tag, setup_job, _ = live.model("legacy_chain", template=SOLID_TEMPLATE)
    scenario = {"setup_job": tag, "setup_status": setup_job.get("status")}
    scenarios["legacy_chain"] = scenario
    if checks.add("legacy chain model created", setup_job.get("status") == "succeeded"):
        legacy_model = setup_job["model_id"]
        example = json.loads(
            (ROOT / "examples" / "sheetmetal_base_yz.json").read_text(encoding="utf-8")
        )
        job_id, job = live.plan(legacy_model, example["operations"])
        wall_volume = (job.get("result") or {}).get("inspection_summary", {}).get("volume_mm3")
        scenario.update(
            wall_job=job_id,
            wall_status=job.get("status"),
            wall_message=job.get("message"),
            wall_volume_mm3=wall_volume,
        )
        ok = checks.add(
            "legacy first wall still builds",
            job.get("status") == "succeeded"
            and isinstance(wall_volume, (int, float))
            and abs(wall_volume - BASE_PLATE_VOLUME_MM3) < 0.01,
            scenario,
        )
        edge = eligible_wall_edge(inspection_of(job_id))
        scenario["edge_id"] = edge
        if ok and checks.add("legacy wall contour edge found", isinstance(edge, int), edge):
            flange_job_id, flange_job = live.plan(
                legacy_model,
                [
                    {
                        "op": "sheetmetal_flange",
                        "label": "base_flange",
                        "edge": {"kind": "edge", "id": edge},
                        "height": 20.0,
                        "angle": 90.0,
                        "radius": 1.0,
                    }
                ],
            )
            flange_volume = (
                (flange_job.get("result") or {}).get("inspection_summary", {}).get("volume_mm3")
            )
            scenario.update(
                flange_job=flange_job_id,
                flange_status=flange_job.get("status"),
                flange_message=flange_job.get("message"),
                flange_volume_mm3=flange_volume,
                flange_saved_reload=(flange_job.get("result") or {}).get(
                    "saved_file_reloaded_and_verified"
                ),
            )
            checks.add(
                "legacy flange chain still builds",
                flange_job.get("status") == "succeeded"
                and isinstance(flange_volume, (int, float))
                and flange_volume > BASE_PLATE_VOLUME_MM3
                and scenario["flange_saved_reload"] is True,
                scenario,
            )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    args = parser.parse_args()
    mode = "live" if args.live else "offline"
    if args.live and not args.confirm_session_usable:
        raise SystemExit("pass --confirm-session-usable after checking the live session")

    directory = report_directory()
    report: dict = {
        "work_item": "FEAT-058",
        "mode": mode,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "run_stamp": STAMP,
        "source": source_identity(),
        "expected": {
            "create_volume_mm3": LENGTH * WIDTH * THICKNESS,
            "resize_volume_mm3": RESIZED_LENGTH * RESIZED_WIDTH * THICKNESS,
            "square_volume_mm3": SQUARE_SIDE * SQUARE_SIDE * THICKNESS,
            "square_resize_volume_mm3": SQUARE_RESIZE[0] * SQUARE_RESIZE[1] * THICKNESS,
            "legacy_volume_mm3": BASE_PLATE_VOLUME_MM3,
        },
    }
    checks = offline_checks(directory)
    if args.live:
        try:
            live = live_checks(report)
        except Exception as error:  # noqa: BLE001 - a crash is a failed run, not a pass
            report["live_error"] = f"{type(error).__name__}: {error}"
            report["traceback"] = traceback.format_exc()[-2000:]
            live = Checks()
            live.add("live run completed", False, report["live_error"])
        checks.items.extend(live.items)

    report["checks"] = checks.items
    report["failed"] = checks.failed
    report["passed"] = not checks.failed
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    target = write_report(mode, report, directory)
    print(
        json.dumps(
            {"report": str(target), "passed": report["passed"], "failed": report["failed"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
