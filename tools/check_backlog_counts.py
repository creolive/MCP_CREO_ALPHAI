"""CLI for the BACKLOG ID count check (DEV-077).

Exit 0 when the declared counts, table rows and category table agree; exit 1
with a JSON report otherwise. Run from any working directory::

    python tools/check_backlog_counts.py
    python tools/check_backlog_counts.py --file <path/to/BACKLOG.md>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from creo_mechdog.backlog_counts import summarize
except ModuleNotFoundError:  # unpacked source distribution without an editable install
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from creo_mechdog.backlog_counts import summarize

DEFAULT_BACKLOG = Path(__file__).resolve().parents[1] / "docs" / "BACKLOG.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_BACKLOG)
    args = parser.parse_args(argv)
    report = summarize(args.file.read_text(encoding="utf-8"))
    print(json.dumps({"file": str(args.file), **report}, ensure_ascii=False, indent=2))
    return 0 if report["consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
