import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from tools.generate_constants import HEADERS, PROBES, available_headers, generate


class GenerateConstantsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "native").mkdir()
        self.inc = self.root / "includes"
        self.inc.mkdir()
        for header in HEADERS:
            (self.inc / header).write_text("// empty SDK fixture\n", encoding="utf-8")
        self.output = self.root / "native/constants.inc"

    def test_probe_presence_absence_and_stable_bytes(self):
        for present in (False, True, False):
            with self.subTest(present=present):
                (self.inc / "ProElemId.h").write_text(
                    "#define PRO_E_HLE_ADD_PARAMETERS 6900\n" if present else "// old SDK\n"
                )
                (self.inc / "ProHole.h").write_text(
                    "enum flag { PRO_HOLE_NO_PARAMETERS_FLAG = -1 };\n"
                    if present
                    else "// PRO_HOLE_NO_PARAMETERS_FLAG does not exist\n"
                )
                self.assertEqual(generate(self.root, inc_dir=self.inc), 2 if present else 0)
                content = self.output.read_text()
                for name in PROBES:
                    self.assertEqual(f"#define MECHDOG_HAS_{name} 1" in content, present)
                self.assertNotIn("Creo 10 SDK", content)
                self.assertNotIn(b"\r", self.output.read_bytes())
                self.output.touch()
                timestamp = self.output.stat().st_mtime_ns
                generate(self.root, inc_dir=self.inc)
                self.assertEqual(self.output.stat().st_mtime_ns, timestamp)
                macros = [line for line in content.splitlines() if line.startswith("#define")]
                self.assertEqual(macros, sorted(macros))

    def test_partial_sdk_and_commented_names_do_not_create_missing_probe(self):
        (self.inc / "ProElemId.h").write_text(
            "#define PRO_E_HLE_ADD_PARAMETERS 6900\n"
            "/* enum fake { PRO_HOLE_NO_PARAMETERS_FLAG = -1 }; */\n"
        )
        generate(self.root, inc_dir=self.inc)
        content = self.output.read_text()
        self.assertIn("#define MECHDOG_HAS_PRO_E_HLE_ADD_PARAMETERS 1", content)
        self.assertNotIn("MECHDOG_HAS_PRO_HOLE_NO_PARAMETERS_FLAG", content)


class FunctionDeclarationProbeTests(unittest.TestCase):
    """BUG-090: SDK function declarations gate native calls via MECHDOG_HAS_ macros.

    Creo 10 SDK reports (2026-10-29 / 2026-10-30) show ProSmtPartThicknessValueGet
    is not declared at all there, so the native call must stay behind a generated
    capability macro. Only a callable declaration counts: comments and same-name
    text without a call parenthesis do not declare the function.
    """

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "native").mkdir()
        self.inc = self.root / "includes"
        self.inc.mkdir()
        for header in HEADERS:
            (self.inc / header).write_text("// empty SDK fixture\n", encoding="utf-8")
        self.output = self.root / "native/constants.inc"

    def test_function_probe_presence_and_absence(self):
        header = self.inc / "ProSheetmetal.h"
        for present in (False, True, False):
            with self.subTest(present=present):
                header.write_text(
                    "extern ProError ProSmtPartThicknessValueGet(ProPart smt_part, double* t);\n"
                    if present
                    else "// old SDK without the API\n",
                    encoding="utf-8",
                )
                generate(self.root, inc_dir=self.inc)
                content = self.output.read_text()
                self.assertEqual(
                    "#define MECHDOG_HAS_ProSmtPartThicknessValueGet 1" in content, present
                )
                self.assertNotIn("Creo 10 SDK", content)
                self.assertNotIn(b"\r", self.output.read_bytes())

    def test_comment_and_same_name_text_are_not_callable_declarations(self):
        (self.inc / "ProSheetmetal.h").write_text(
            "/* extern ProError ProSmtPartThicknessValueGet(ProPart smt_part, double* t); */\n"
            "/* ProSmtPartThicknessValueGet(part, &value) inside a comment */\n"
            "// ProSmtPartThicknessValueGet was removed from this SDK generation\n"
            "#define SOME_ALIAS ProSmtPartThicknessValueGet\n",
            encoding="utf-8",
        )
        generate(self.root, inc_dir=self.inc)
        self.assertNotIn("MECHDOG_HAS_ProSmtPartThicknessValueGet", self.output.read_text())

    def test_function_probes_keep_constant_probes_and_sorted_macros(self):
        (self.inc / "ProElemId.h").write_text("#define PRO_E_HLE_ADD_PARAMETERS 6900\n")
        (self.inc / "ProHole.h").write_text("enum flag { PRO_HOLE_NO_PARAMETERS_FLAG = -1 };\n")
        (self.inc / "ProSheetmetal.h").write_text(
            "extern ProError ProSmtPartThicknessGet(ProPart smt_part, ProDimension *t);\n"
            "extern ProError ProSmtPartThicknessValueGet(ProPart smt_part, double* t);\n",
            encoding="utf-8",
        )
        # The constant-name count stays the constant probe's own contract even
        # when function probes add macros.
        self.assertEqual(generate(self.root, inc_dir=self.inc), 2)
        content = self.output.read_text()
        for name in (
            "PRO_E_HLE_ADD_PARAMETERS",
            "PRO_HOLE_NO_PARAMETERS_FLAG",
            "ProSmtPartThicknessGet",
            "ProSmtPartThicknessValueGet",
        ):
            self.assertIn(f"#define MECHDOG_HAS_{name} 1", content)
        macros = [line for line in content.splitlines() if line.startswith("#define")]
        self.assertEqual(macros, sorted(macros))


class MissingHeaderGateTests(unittest.TestCase):
    """BUG-107: a header absent from the installed SDK must never abort generation.

    Creo 10 does not ship Probbl.h; the Q07 G5 probe list added it
    unconditionally, so the first build on that SDK died with FileNotFoundError
    before a single constant was emitted.
    """

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "native").mkdir()
        self.inc = self.root / "includes"
        self.inc.mkdir()
        (self.inc / "ProElemId.h").write_text("#define PRO_E_HLE_ADD_PARAMETERS 6900\n")
        (self.inc / "ProTrim.h").write_text("enum trim { PRO_TRIM_KEEP = 1 };\n")
        self.output = self.root / "native/constants.inc"

    def test_missing_header_is_skipped_and_never_included(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            count = generate(self.root, inc_dir=self.inc)
        content = self.output.read_text()
        self.assertEqual(count, 2)
        self.assertIn("#include <ProElemId.h>", content)
        self.assertIn("#include <ProTrim.h>", content)
        self.assertNotIn("Probbl.h", content)
        self.assertIn('{"PRO_TRIM_KEEP"', content)
        report = [
            line
            for line in stdout.getvalue().splitlines()
            if line.startswith("MISSING_SDK_HEADER=")
        ]
        self.assertIn("MISSING_SDK_HEADER=Probbl.h", report)
        self.assertEqual(len(report), len(HEADERS) - 2)

    def test_available_headers_partitions_the_list(self):
        present, missing = available_headers(self.inc)
        self.assertEqual(present, ["ProElemId.h", "ProTrim.h"])
        self.assertEqual(sorted(present + missing), sorted(HEADERS))
        self.assertEqual(set(present) & set(missing), set())

    def test_all_headers_present_keeps_the_previous_include_block(self):
        for header in HEADERS:
            (self.inc / header).write_text("// empty SDK fixture\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            generate(self.root, inc_dir=self.inc)
        content = self.output.read_text()
        includes = [line for line in content.splitlines() if line.startswith("#include")]
        self.assertEqual(includes, [f"#include <{header}>" for header in HEADERS])
        self.assertNotIn("MISSING_SDK_HEADER=", stdout.getvalue())
