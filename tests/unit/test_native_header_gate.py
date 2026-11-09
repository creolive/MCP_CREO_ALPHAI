"""DEV-080: handwritten native units must gate SDK headers that can be absent.

P1-1 of the 2026-11-08 0.19.0 report: ``test_gated_headers.py`` only guards
the generated ``constants.inc`` include list, so the generator can be green
while a handwritten translation unit hard-includes ``Probbl.h`` and breaks the
whole build on Creo 10. This contract shares ``available_headers()`` as its
truth source, simulates an SDK generation that omits the optional headers, and
checks every handwritten ``native/*.cpp`` / ``*.h`` against that missing set.
"""

from __future__ import annotations

import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path

from tools.generate_constants import HEADERS, available_headers, generate

ROOT = Path(__file__).resolve().parents[2]
NATIVE_DIR = ROOT / "native"

#: Headers observed missing on a supported SDK generation (Creo 10 has no
#: boundary-blend tree). H01 will replace this catalogue with the generator's
#: single truth source once handwritten units consume the emitted macros.
SDK_OPTIONAL_HEADERS = frozenset({"Probbl.h"})

_INCLUDE = re.compile(r"^\s*#\s*include\s*<([^>]+)>")
_IF = re.compile(r"^\s*#\s*(?:if|ifdef|ifndef)\b")
_ENDIF = re.compile(r"^\s*#\s*endif\b")
_GATE = re.compile(r"__has_include|MECHDOG_HAS_")


def _fixture_missing() -> set[str]:
    """Build a complete SDK fixture minus the optional headers, return missing."""
    temp = tempfile.TemporaryDirectory()
    inc = Path(temp.name) / "includes"
    inc.mkdir()
    for header in HEADERS:
        if header not in SDK_OPTIONAL_HEADERS:
            (inc / header).write_text("// empty SDK fixture\n", encoding="utf-8")
    _, missing = available_headers(inc)
    temp.cleanup()
    return set(missing)


def _sdk_includes(path: Path, headers: set[str]) -> list[tuple[int, str, bool]]:
    """Return ``(line, header, guarded)`` for direct SDK includes in one TU.

    ``guarded`` is true only when an enclosing conditional actually mentions a
    header gate (``__has_include`` or ``MECHDOG_HAS_*``); an unrelated include
    guard must not be mistaken for protection.
    """
    stack: list[bool] = []
    found: list[tuple[int, str, bool]] = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        if _IF.match(line):
            stack.append(bool(_GATE.search(line)))
            continue
        if _ENDIF.match(line):
            if stack:
                stack.pop()
            continue
        match = _INCLUDE.match(line)
        if match and match.group(1) in headers:
            found.append((number, match.group(1), any(stack)))
    return found


class OptionalHeaderCatalogueTests(unittest.TestCase):
    def test_optional_headers_are_part_of_the_generator_list(self):
        self.assertTrue(SDK_OPTIONAL_HEADERS.issubset(set(HEADERS)))

    def test_simulated_sdk_reports_exactly_the_optional_headers_missing(self):
        with tempfile.TemporaryDirectory() as name:
            inc = Path(name) / "includes"
            inc.mkdir()
            for header in HEADERS:
                if header not in SDK_OPTIONAL_HEADERS:
                    (inc / header).write_text("// fixture\n", encoding="utf-8")
            present, missing = available_headers(inc)
        self.assertEqual(set(missing), set(SDK_OPTIONAL_HEADERS))
        self.assertEqual(sorted(present + missing), sorted(HEADERS))


class HandwrittenUnitGateTests(unittest.TestCase):
    def test_no_unguarded_include_of_a_missing_sdk_header(self):
        missing = _fixture_missing()
        self.assertEqual(missing, set(SDK_OPTIONAL_HEADERS))
        offenders: list[str] = []
        sources = sorted(NATIVE_DIR.glob("*.cpp")) + sorted(NATIVE_DIR.glob("*.h"))
        self.assertTrue(sources, "native sources are missing from this checkout")
        for path in sources:
            for number, header, guarded in _sdk_includes(path, missing):
                if not guarded:
                    offenders.append(f"{path.name}:{number}: #include <{header}>")
        self.assertEqual(
            offenders,
            [],
            "unguarded optional SDK header include aborts the whole native build; "
            "gate it with __has_include or MECHDOG_HAS_*",
        )

    def test_surface_loft_probbl_include_is_gated(self):
        includes = _sdk_includes(NATIVE_DIR / "surface_loft.cpp", {"Probbl.h"})
        self.assertTrue(includes, "surface_loft.cpp must include Probbl.h when available")
        self.assertTrue(all(guarded for _, _, guarded in includes))

    def test_missing_header_branch_publishes_sdk_state(self):
        source = (NATIVE_DIR / "surface_loft.cpp").read_text(encoding="utf-8")
        self.assertIn("#ifndef MECHDOG_HAS_PROBBL_HEADER", source)
        self.assertIn("mechdog_surface_loft_sdk_state", source)
        self.assertIn("sdk_header_missing", source)


class GeneratorSourceTests(unittest.TestCase):
    def test_generator_skips_missing_optional_headers(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "native").mkdir()
            inc = root / "includes"
            inc.mkdir()
            for header in HEADERS:
                if header not in SDK_OPTIONAL_HEADERS:
                    (inc / header).write_text("// fixture\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                generate(root, inc_dir=inc)
            content = (root / "native/constants.inc").read_text(encoding="utf-8")
        for header in SDK_OPTIONAL_HEADERS:
            self.assertNotIn(f"#include <{header}>", content)


if __name__ == "__main__":
    unittest.main()
