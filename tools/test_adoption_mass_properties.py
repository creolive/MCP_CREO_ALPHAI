"""FEAT-057 / A01 acceptance driver: real mass properties.

Offline (default) it exercises the receipt normalizer and the schema bounds.
``--live`` creates a 10x20x30 block and checks the measured volume/centre of
mass, the no-density receipt (null mass plus hint), the explicit-density receipt
(47.1 g at 7.85 g/cm3) and that the read-only query leaves the revision alone.

Usage:
  python tools/test_adoption_mass_properties.py
  python tools/test_adoption_mass_properties.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from creo_mechdog.mass_properties import normalize_mass_properties  # noqa: E402
from creo_mechdog.schema import validate_operations  # noqa: E402

BLOCK = [10.0, 20.0, 30.0]
STEEL_DENSITY = 7.85
EXPECTED_VOLUME = BLOCK[0] * BLOCK[1] * BLOCK[2]
EXPECTED_MASS = EXPECTED_VOLUME * STEEL_DENSITY / 1000.0
EXPECTED_CENTER = [BLOCK[0] / 2, BLOCK[1] / 2, BLOCK[2] / 2]

PLAN = [
    {
        "op": "sketch",
        "label": "mp_sketch",
        "plane": "XY",
        "entities": [
            {
                "type": "rectangle",
                "name": "mpblk",
                "min": [0.0, 0.0],
                "max": [BLOCK[0], BLOCK[1]],
            }
        ],
    },
    {
        "op": "extrude",
        "label": "mpblk",
        "sketch": "mp_sketch",
        "depth": BLOCK[2],
        "mode": "add",
        "direction": "positive",
        "depth_type": "blind",
    },
]


def reading(**overrides) -> dict:
    base = {
        "volume_mm3": EXPECTED_VOLUME,
        "mass_g": EXPECTED_MASS,
        "density_g_cm3": STEEL_DENSITY,
        "density_source": "request",
        "center_of_mass_mm": EXPECTED_CENTER,
        "material_assigned": True,
        "mass_unit": None,
        "hint": None,
        "volume_query_code": 0,
        "mass_query_code": -1,
        "units_query_code": 0,
    }
    base.update(overrides)
    return base


def offline_cases() -> list[dict]:
    cases: list[dict] = []

    def refused(name: str, payload: dict) -> None:
        try:
            normalize_mass_properties(payload)
        except ValueError as error:
            cases.append(
                {"case": name, "kind": "offline_receipt", "observed": str(error), "pass": True}
            )
        else:
            cases.append(
                {"case": name, "kind": "offline_receipt", "observed": "accepted", "pass": False}
            )

    def accepted(name: str, payload: dict, check) -> None:
        try:
            result = normalize_mass_properties(payload)
        except ValueError as error:
            cases.append(
                {"case": name, "kind": "offline_receipt", "observed": str(error), "pass": False}
            )
            return
        observed = check(result)
        cases.append(
            {
                "case": name,
                "kind": "offline_receipt",
                "observed": observed,
                "pass": observed is True,
            }
        )

    accepted(
        "request_density_receipt",
        reading(),
        lambda result: (
            abs(result["mass_g"] - EXPECTED_MASS) < 1e-9 and result["density_source"] == "request"
        ),
    )
    accepted(
        "no_density_receipt",
        reading(
            mass_g=None,
            density_g_cm3=None,
            density_source="none",
            hint="Assign a material with a density",
        ),
        lambda result: (
            result["mass_g"] is None
            and result["density_g_cm3"] is None
            and result["hint"] is not None
        ),
    )
    accepted(
        "unknown_mass_unit_keeps_model_values",
        reading(density_source="model_material", mass_unit="lbm"),
        lambda result: (
            result["mass_unit"] == "lbm" and abs(result["mass_g"] - EXPECTED_MASS) < 1e-9
        ),
    )
    refused("mass_without_source", reading(density_source="none"))
    refused("mass_mismatch", reading(mass_g=EXPECTED_MASS + 1.0))
    refused("missing_volume", reading(volume_mm3=None))
    refused("unknown_source", reading(density_source="assumed"))

    for name, payload, expected in (
        ("schema_rejects_zero_density", {"op": "mass_properties", "density_g_cm3": 0}, True),
        ("schema_rejects_high_density", {"op": "mass_properties", "density_g_cm3": 40}, True),
        ("schema_accepts_steel", {"op": "mass_properties", "density_g_cm3": STEEL_DENSITY}, False),
        ("schema_accepts_no_density", {"op": "mass_properties"}, False),
    ):
        rejected = False
        observed = "accepted"
        try:
            validate_operations([payload])
        except ValueError as error:
            rejected = True
            observed = str(error)
        cases.append(
            {
                "case": name,
                "kind": "offline_schema",
                "observed": observed,
                "pass": rejected is expected,
            }
        )
    return cases


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


def run_live(generic_bridge) -> tuple[list[dict], bool]:
    cases: list[dict] = []
    created = generic_bridge.submit(PLAN, model_name="mp_acc_" + str(int(time.time())))
    job = wait(created["job_id"])
    cases.append(
        {
            "case": "fixture_block",
            "kind": "setup",
            "job_id": created["job_id"],
            "status": job.get("status"),
            "message": job.get("message"),
            "pass": job.get("status") == "succeeded",
        }
    )
    if job.get("status") != "succeeded":
        return cases, False

    model_id = job["model_id"]
    before = generic_bridge.model_info(model_id).get("revision")

    plain = generic_bridge.get_mass_properties(model_id)
    checks = {
        "volume": abs((plain.get("volume_mm3") or 0) - EXPECTED_VOLUME) < 1e-6,
        "center": _close_triple(plain.get("center_of_mass_mm"), EXPECTED_CENTER),
        "mass_null": plain.get("mass_g") is None,
        "source_none": plain.get("density_source") == "none",
        "hint": bool(plain.get("hint")),
    }
    cases.append(
        {
            "case": "part_without_density",
            "kind": "live_receipt",
            "observed": plain,
            "checks": checks,
            "pass": all(checks.values()),
        }
    )

    steel = generic_bridge.get_mass_properties(model_id, STEEL_DENSITY)
    checks = {
        "volume": abs((steel.get("volume_mm3") or 0) - EXPECTED_VOLUME) < 1e-6,
        "mass": abs((steel.get("mass_g") or 0) - EXPECTED_MASS) < 1e-6,
        "density": abs((steel.get("density_g_cm3") or 0) - STEEL_DENSITY) < 1e-9,
        "source_request": steel.get("density_source") == "request",
        "job_and_model": bool(steel.get("job_id")) and steel.get("model_id") == model_id,
    }
    cases.append(
        {
            "case": "part_with_requested_steel",
            "kind": "live_receipt",
            "observed": steel,
            "checks": checks,
            "pass": all(checks.values()),
        }
    )

    after = generic_bridge.model_info(model_id).get("revision")
    cases.append(
        {
            "case": "read_only_revision",
            "kind": "live_boundary",
            "observed": {"before": before, "after": after},
            "pass": before == after,
        }
    )

    cases.extend(assembly_cases(generic_bridge, model_id))
    return cases, all(case["pass"] for case in cases)


def assembly_cases(generic_bridge, part_id: str) -> list[dict]:
    """Two translated instances: totals must double, the centre must shift."""
    cases: list[dict] = []
    created = generic_bridge.submit(
        [
            {
                "op": "assemble_component",
                "label": "mp_asm_i1",
                "source_model_id": part_id,
                "placement": "default",
            }
        ],
        model_name="mp_asm_" + str(int(time.time())),
        model_type="assembly",
    )
    job = wait(created["job_id"])
    cases.append(
        {
            "case": "fixture_assembly",
            "kind": "setup",
            "job_id": created["job_id"],
            "status": job.get("status"),
            "message": job.get("message"),
            "pass": job.get("status") == "succeeded",
        }
    )
    if job.get("status") != "succeeded":
        return cases

    assembly_id = job["model_id"]
    revision = generic_bridge.model_info(assembly_id).get("revision")
    second = generic_bridge.submit(
        [
            {
                "op": "assemble_component",
                "label": "mp_asm_i2",
                "source_model_id": part_id,
                "placement": "default",
            }
        ],
        model_id=assembly_id,
        expected_revision=revision,
    )
    second_job = wait(second["job_id"])
    cases.append(
        {
            "case": "fixture_second_instance",
            "kind": "setup",
            "job_id": second["job_id"],
            "status": second_job.get("status"),
            "message": second_job.get("message"),
            "pass": second_job.get("status") == "succeeded",
        }
    )
    if second_job.get("status") != "succeeded":
        return cases

    # Translate the second instance explicitly: the assembly pose on
    # assemble_component is not honoured on this build, while
    # component_placement moves the placed occurrence.
    translate = generic_bridge.submit(
        [
            {
                "op": "component_placement",
                "component": "mp_asm_i2",
                "translation": [BLOCK[0] * 5, 0.0, 0.0],
            }
        ],
        model_id=assembly_id,
        expected_revision=generic_bridge.model_info(assembly_id).get("revision"),
    )
    translate_job = wait(translate["job_id"])
    cases.append(
        {
            "case": "fixture_instance_translation",
            "kind": "setup",
            "job_id": translate["job_id"],
            "status": translate_job.get("status"),
            "message": translate_job.get("message"),
            "pass": translate_job.get("status") == "succeeded",
        }
    )
    if translate_job.get("status") != "succeeded":
        return cases

    before = generic_bridge.model_info(assembly_id).get("revision")
    receipt = generic_bridge.get_mass_properties(assembly_id, STEEL_DENSITY)
    after = generic_bridge.model_info(assembly_id).get("revision")
    expected_volume = EXPECTED_VOLUME * 2
    expected_mass = EXPECTED_MASS * 2
    # Instance one spans x 0..10 (centre 5), instance two is moved to 50..60
    # (centre 55), so the assembly centre sits at x 30.
    expected_center = [EXPECTED_CENTER[0] + BLOCK[0] * 2.5, EXPECTED_CENTER[1], EXPECTED_CENTER[2]]
    checks = {
        "volume_doubled": abs((receipt.get("volume_mm3") or 0) - expected_volume) < 1e-6,
        "mass_doubled": abs((receipt.get("mass_g") or 0) - expected_mass) < 1e-6,
        "center_translated": _close_triple(receipt.get("center_of_mass_mm"), expected_center),
        "source_request": receipt.get("density_source") == "request",
        "read_only_revision": before == after,
        "assembly_query_code": (receipt.get("query_codes") or {}).get("volume") == 0,
    }
    cases.append(
        {
            "case": "assembly_two_instances",
            "kind": "live_receipt",
            "model_id": assembly_id,
            "observed": receipt,
            "expected": {
                "volume_mm3": expected_volume,
                "mass_g": expected_mass,
                "center_of_mass_mm": expected_center,
            },
            "checks": checks,
            "pass": all(checks.values()),
        }
    )
    return cases


def _close_triple(value, expected) -> bool:
    if not isinstance(value, list) or len(value) != len(expected):
        return False
    return all(abs(float(v) - float(e)) < 1e-6 for v, e in zip(value, expected))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", default="build/acceptance_mass_properties.json")
    args = parser.parse_args()

    report: dict = {"live": bool(args.live), "cases": offline_cases()}
    offline_ok = all(case["pass"] for case in report["cases"])
    if not args.live:
        report["success"] = offline_ok
        write(args.output, report)
        print(json.dumps({"offline_ok": offline_ok, "report": args.output}, ensure_ascii=False))
        return 0 if offline_ok else 1
    if not args.confirm_session_usable:
        raise SystemExit("pass --confirm-session-usable after checking the live session")

    import generic_bridge

    try:
        live, ok = run_live(generic_bridge)
    except Exception as error:
        live, ok = (
            [{"case": "driver_error", "kind": "error", "observed": str(error), "pass": False}],
            False,
        )
    report["cases"].extend(live)
    report["success"] = offline_ok and ok
    write(args.output, report)
    print(
        json.dumps(
            {
                "success": report["success"],
                "failed_cases": [case["case"] for case in report["cases"] if not case["pass"]],
                "report": args.output,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["success"] else 1


def write(path: str, report: dict) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
