"""DEV-077: check the declared BACKLOG ID counts against the ledger itself.

The declaration in ``docs/BACKLOG.md`` used to be maintained by hand and went
stale when an ID moved to the completion archive. This module only parses text;
it never edits the ledger, so it can run in a source distribution without Git.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

PREFIXES = ("BUG", "FEAT", "DEV")

_ID_ROW = re.compile(r"^\|\s*\[?(BUG|FEAT|DEV)-(\d+)\]?", re.MULTILINE)
_DECLARED = re.compile(
    r"当前唯一 ID \*\*(\d+)\*\*（BUG \*\*(\d+)\*\*、FEAT \*\*(\d+)\*\*、DEV \*\*(\d+)\*\*）"
)
_COUNTS_SECTION = re.compile(r"^##\s*使用与计数\s*$(.*?)^##\s", re.MULTILINE | re.DOTALL)
_CATEGORY_ROW = re.compile(r"^\|[^|]+\|\s*(\d+)\s*\|\s*$", re.MULTILINE)


def summarize(text: str) -> dict[str, Any]:
    """Compare the declared counts, ID rows and category table of one ledger."""
    rows = _ID_ROW.findall(text)
    per_prefix = Counter(prefix for prefix, _ in rows)
    actual = {prefix: per_prefix[prefix] for prefix in PREFIXES}
    identifiers = [f"{prefix}-{number}" for prefix, number in rows]
    duplicates = sorted(name for name, count in Counter(identifiers).items() if count > 1)
    section = _COUNTS_SECTION.search(text)
    category_total = (
        sum(int(value) for value in _CATEGORY_ROW.findall(section.group(1)))
        if section is not None
        else None
    )
    declared_match = _DECLARED.search(text)
    declared = (
        {
            "total": int(declared_match.group(1)),
            "BUG": int(declared_match.group(2)),
            "FEAT": int(declared_match.group(3)),
            "DEV": int(declared_match.group(4)),
        }
        if declared_match is not None
        else None
    )

    problems: list[str] = []
    if declared is None:
        problems.append("declared_line_missing")
    else:
        if declared["total"] != len(identifiers):
            problems.append("declared_total")
        for prefix in PREFIXES:
            if declared[prefix] != actual[prefix]:
                problems.append(f"declared_{prefix}")
    if category_total is None:
        problems.append("category_table_missing")
    elif category_total != len(identifiers):
        problems.append("category_total")
    if duplicates:
        problems.append("duplicate_ids")

    return {
        "declared": declared,
        "actual": actual,
        "actual_total": len(identifiers),
        "category_total": category_total,
        "duplicates": duplicates,
        "problems": problems,
        "consistent": not problems,
    }
