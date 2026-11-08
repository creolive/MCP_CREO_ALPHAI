"""FEAT-063 offline acceptance driver; never creates or connects a CAD session."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from creo_mechdog.paths import SOURCE_PATHS
from creo_mechdog.product_rules import build_product_plan
from version import VERSION


def run_checks() -> dict:
    """Return offline evidence without writing it or using external programs."""
    capabilities = {"operations": ["sketch", "extrude"]}
    cases = []
    for name, parameters, volume in (
        ("default", {}, 35712),
        ("second_size", {"length_mm": 120, "width_mm": 80, "height_mm": 50, "wall_mm": 3}, 83508),
    ):
        result = build_product_plan("box_frame", parameters, capabilities)
        cases.append(
            {
                "name": name,
                "passed": result["executable"]
                and result["expected_geometry"]["volume_mm3"] == volume,
                "expected_volume_mm3": volume,
                "result": result,
            }
        )
    blocked = build_product_plan("box_frame", {}, {"operations": ["sketch"]})
    cases.append(
        {
            "name": "missing_extrude",
            "passed": not blocked["executable"]
            and blocked["plan"] is None
            and blocked["blocking_items"]
            == [{"code": "missing_capability", "capability": "extrude"}],
            "result": blocked,
        }
    )
    try:
        build_product_plan("box_frame", {"wall_mm": True}, capabilities)
    except ValueError as error:
        cases.append({"name": "reject_bool", "passed": True, "error": str(error)})
    else:
        cases.append({"name": "reject_bool", "passed": False})
    sources = (
        "server.py",
        "src/creo_mechdog/capabilities.py",
        "version.py",
        "tests/unit/test_product_rules_mcp.py",
        "tests/unit/test_product_rules_driver.py",
        "src/creo_mechdog/product_rules.py",
        "src/creo_mechdog/schema.py",
        "src/creo_mechdog/paths.py",
        "examples/product_rules/box_frame.json",
        "tools/test_adoption_product_rules.py",
        "tests/unit/test_product_rules.py",
    )
    return {
        "work_item": "FEAT-063",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "platform": platform.platform(),
        "mode": "offline",
        "passed": all(c["passed"] for c in cases),
        "cases": cases,
        "native": "not_run",
        "saved_reload": "not_run",
        "interpreter": sys.executable,
        "resource_root": str(SOURCE_PATHS.resource_root),
        "source_sha256": {
            name: hashlib.sha256((SOURCE_PATHS.resource_root / name).read_bytes()).hexdigest()
            for name in sources
        },
    }


def git_identity() -> dict:
    """Record read-only CLI provenance; an unavailable Git identity stays explicit."""
    from creo_mechdog.source_provenance import local_provenance

    evidence = local_provenance(SOURCE_PATHS.resource_root)
    identity = {
        "commit": evidence["commit"],
        "dirty": evidence["dirty"],
        "git_status": evidence["git_status"],
    }
    if evidence["git_status"] != "available":
        identity["error"] = "Git identity unavailable; directory source hashes remain available"
    return identity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Directory for report.json")
    args = parser.parse_args(argv)
    report = run_checks()
    output = args.output or SOURCE_PATHS.build / (
        "product_rules_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "_"
        + uuid4().hex[:8]
    )
    report["git"] = git_identity()
    output.mkdir(parents=True, exist_ok=True)
    path = output / "report.json"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "report": str(path.resolve())}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
