"""Run input validation tests and save a versioned result for release evidence."""

import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creo_mechdog.source_provenance import local_provenance
from creo_mechdog.unit_report import build_unit_report


def main() -> int:
    source = local_provenance(ROOT)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = build_unit_report(
        result,
        timestamp=time.time(),
        duration_seconds=time.monotonic() - started,
        provenance=source,
    )
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "build/unit_test_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
