import unittest

from pydantic import ValidationError

from creo_mechdog.sheetmetal_candidates import SheetmetalCornerReliefOp, SheetmetalQuiltFormOp


class SheetmetalCandidateTests(unittest.TestCase):
    def corner(self, **changes):
        data = dict(
            op="sheetmetal_corner_relief",
            label="relief",
            flat={"kind": "surface", "id": 1},
            bends=[{"kind": "surface", "id": 2}, {"kind": "surface", "id": 3}],
            width=2,
            depth=3,
        )
        data.update(changes)
        return SheetmetalCornerReliefOp.model_validate(data)

    def test_corner_valid_defaults(self):
        self.assertEqual(self.corner().state, "formed")

    def test_corner_invalid_dimensions(self):
        for key in ("width", "depth"):
            for value in (True, "2", 0, -1, float("nan"), float("inf")):
                with self.subTest(key=key, value=value), self.assertRaises(ValidationError):
                    self.corner(**{key: value})

    def test_corner_invalid_surfaces(self):
        for ref in (
            {"kind": "surface", "id": True},
            {"kind": "surface", "id": 2**31},
            {"kind": "surface", "id": -1},
            {"kind": "surface", "id": 1.0},
            {"kind": "edge", "id": 1},
            {"kind": "surface", "id": 1, "extra": 0},
            {"kind": "surface", "label": "face"},
        ):
            with self.subTest(ref=ref), self.assertRaises(ValidationError):
                self.corner(flat=ref)
        for bends in (
            [],
            [{"kind": "surface", "id": 2}],
            [{"kind": "surface", "id": 2}] * 2,
            [{"kind": "surface", "id": 1}, {"kind": "surface", "id": 3}],
        ):
            with self.subTest(bends=bends), self.assertRaises(ValidationError):
                self.corner(bends=bends)

    def test_no_rip_or_body_declarations(self):
        for key in ("has_rip", "rip_verified", "body"):
            with self.assertRaises(ValidationError):
                self.corner(**{key: True})

    def test_quilt_defaults_and_refs(self):
        for ref in ({"kind": "quilt", "id": 0}, {"kind": "quilt_feature", "label": "source"}):
            op = SheetmetalQuiltFormOp(op="sheetmetal_quilt_form", label="form", quilt=ref)
            self.assertTrue(op.keep_quilt)
            self.assertFalse(op.trim_sides)
            self.assertEqual(op.side, "face")
            self.assertEqual(op.material_side, "outside")

    def test_quilt_invalid_refs_and_bool(self):
        base = dict(op="sheetmetal_quilt_form", label="form", quilt={"kind": "quilt", "id": 1})
        for ref in (
            {"kind": "quilt", "id": True},
            {"kind": "quilt", "id": 2**31},
            {"kind": "quilt", "id": 1.5},
            {"kind": "surface", "id": 1},
            {"kind": "quilt", "id": 1, "label": "source"},
            {"kind": "quilt_feature", "label": "UPPER"},
        ):
            with self.subTest(ref=ref), self.assertRaises(ValidationError):
                SheetmetalQuiltFormOp.model_validate(dict(base, quilt=ref))
        for key in ("keep_quilt", "trim_sides"):
            for value in (0, 1, "true"):
                with self.assertRaises(ValidationError):
                    SheetmetalQuiltFormOp.model_validate(dict(base, **{key: value}))


class SheetmetalTargetBodyBehaviorTests(unittest.TestCase):
    def test_native_target_decisions(self):
        import subprocess
        import tempfile
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        vcvars = Path(
            "C:/Program Files/Microsoft Visual Studio/2022/Enterprise/VC/Auxiliary/Build/vcvars64.bat"
        )
        if not vcvars.exists():
            self.skipTest("MSVC x64 environment unavailable for standalone helper")
        source = r"""#include "sheetmetal_target_guard.h"
#include <cassert>
#include <limits>
using namespace sheetmetal_target;
template<class F> bool rejects(F f) {
    try { f(); } catch(const std::runtime_error &) { return true; }
    return false;
}
int main() {
    // Empty stock default is not the material target. Part-level zero gauge
    // has no input to this production decision; only actual body gauge matters.
    std::vector<BodyCandidate> bodies = {{1,false}, {7,true}};
    assert(unique_material_body(bodies,true)==7);
    double part_level_thickness=0; (void)part_level_thickness;
    require_body_gauge(true,true,1.25);
    require_membership(7,7,true,true);
    assert(rejects([&]{unique_material_body(bodies,false);}));
    assert(rejects([]{unique_material_body({},true);}));
    assert(rejects([]{unique_material_body({{1,false}},true);}));
    assert(rejects([]{unique_material_body({{7,true},{8,true}},true);}));
    for(double value : {0.0,-1.0,std::numeric_limits<double>::quiet_NaN(),std::numeric_limits<double>::infinity()})
        assert(rejects([&]{require_body_gauge(true,true,value);}));
    assert(rejects([]{require_body_gauge(true,false,1.25);}));
    assert(rejects([]{require_body_gauge(false,true,1.25);}));
    assert(rejects([]{require_membership(7,8,true,true);}));
    assert(rejects([]{require_membership(7,7,false,true);}));
    assert(rejects([]{require_membership(7,7,true,false);}));
}
"""
        with tempfile.TemporaryDirectory(prefix="sheetmetal-target-") as tmp:
            cpp = Path(tmp) / "test.cpp"
            exe = Path(tmp) / "test.exe"
            cpp.write_text(source, encoding="utf-8")
            command = (
                f'call "{vcvars}" >nul && cl /nologo /EHsc /std:c++17 '
                f'/I"{root / "native"}" "{cpp}" /Fe:"{exe}"'
            )
            compiled = subprocess.run(
                'cmd /d /s /c "' + command + '"',
                cwd=tmp,
                capture_output=True,
                text=True,
                errors="replace",
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
