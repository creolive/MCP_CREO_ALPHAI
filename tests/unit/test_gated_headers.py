"""BUG-107 contract: the SDK header list is gated, never assumed.

BUG-090 fixed the same class of problem for functions (``MECHDOG_HAS_*``
macros keep missing APIs out of the compile unit) but left the header list in
``tools/generate_constants.py`` unconditional. Creo 10 has no ``Probbl.h``, so
the first ``bridge.py build`` there aborted in the generator. The contract is:
every listed header is either present in the SDK in use, or is skipped — the
enumeration set and the emitted ``#include`` set stay identical.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools.generate_constants import HEADERS, available_headers, generate

ROOT = Path(__file__).resolve().parents[2]


class HeaderListShapeTests(unittest.TestCase):
    def test_header_list_is_unique_and_plausible(self):
        self.assertEqual(len(HEADERS), len(set(HEADERS)))
        for header in HEADERS:
            self.assertTrue(header.endswith(".h"), header)
            self.assertNotIn("/", header)
            self.assertNotIn("\\", header)


class SingleHeaderSkipContractTests(unittest.TestCase):
    """Every listed header must survive its own absence.

    This is the executable form of "either it exists in the reference SDK or it
    has a skip case": if any single header is removed from an otherwise complete
    SDK fixture, generation still succeeds and never emits that include.
    """

    def test_each_header_can_be_absent_without_breaking_generation(self):
        for absent in HEADERS:
            with self.subTest(absent=absent):
                temp = tempfile.TemporaryDirectory()
                self.addCleanup(temp.cleanup)
                root = Path(temp.name)
                (root / "native").mkdir()
                inc = root / "includes"
                inc.mkdir()
                for header in HEADERS:
                    if header == absent:
                        continue
                    (inc / header).write_text("// empty SDK fixture\n", encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    generate(root, inc_dir=inc)
                content = (root / "native/constants.inc").read_text(encoding="utf-8")
                includes = [line for line in content.splitlines() if line.startswith("#include")]
                self.assertNotIn(f"#include <{absent}>", includes)
                self.assertEqual(len(includes), len(HEADERS) - 1)


class LocalSdkContractTests(unittest.TestCase):
    """When a real SDK is installed, the emitted includes match the present set."""

    def _include_dir(self):
        config = ROOT / "config.json"
        if not config.is_file():
            self.skipTest("no local config.json")
        data = json.loads(config.read_text(encoding="utf-8-sig"))
        inc = Path(data.get("creo_root", "")) / "Common Files/protoolkit/includes"
        if not inc.is_dir():
            self.skipTest(f"SDK include directory not present: {inc}")
        return inc

    def test_local_sdk_present_and_missing_sets_are_disjoint(self):
        inc = self._include_dir()
        present, missing = available_headers(inc)
        self.assertEqual(sorted(present + missing), sorted(HEADERS))
        self.assertEqual(set(present) & set(missing), set())

    def test_generated_constants_only_include_present_headers(self):
        inc = self._include_dir()
        constants = ROOT / "native/constants.inc"
        if not constants.is_file():
            self.skipTest("native/constants.inc has not been generated yet")
        present, missing = available_headers(inc)
        includes = {
            line[len("#include <") : -1]
            for line in constants.read_text(encoding="utf-8").splitlines()
            if line.startswith("#include <")
        }
        self.assertEqual(includes, set(present))
        self.assertTrue(set(missing).isdisjoint(includes))
