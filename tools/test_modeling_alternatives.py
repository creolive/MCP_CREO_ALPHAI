"""Prepare DEV-078 recipes offline. This driver has no live execution option."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creo_mechdog.modeling_recipes import grille_cut_recipe, reference_route


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/dev078_offline_recipes.json")
    args = parser.parse_args()
    report = {
        "work_item": "DEV-078",
        "mode": "offline",
        "native_validation": "not_run",
        "recipes": [
            grille_cut_recipe(),
            grille_cut_recipe(rows=3, columns=3),
            reference_route("standard_quilt_offset"),
            reference_route("punch_die_form"),
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Offline preparation written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
