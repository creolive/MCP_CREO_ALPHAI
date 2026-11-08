"""FEAT-009/H02 surface_loft contract tests.

Offline only: the Python admission surface, capability registration, result
projection keys and the native source-level route are locked here. Live
geometry belongs to ``tools/test_surface_loft.py --live --confirm-session-usable``;
these tests never claim a native feature was built.
"""

import unittest
from pathlib import Path

from creo_mechdog.capabilities import (
    REGISTERED_OPERATIONS,
    UNAVAILABLE_OPERATIONS,
    require_available,
)
from creo_mechdog.job_projection import _OPERATION_CRITERIA, SURFACE_LOFT_KEYS
from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native" / "surface_loft.cpp"
GENERIC = ROOT / "native" / "generic.cpp"
SERVER = ROOT / "server.py"
DRIVER = ROOT / "tools" / "test_surface_loft.py"


def loft_operation(**overrides):
    operation = {
        "op": "surface_loft",
        "label": "loft_surface",
        "sections": ["loft_a", "loft_b"],
    }
    operation.update(overrides)
    return operation


class SurfaceLoftSchemaTests(unittest.TestCase):
    def test_accepts_two_labelled_sections(self):
        validated = validate_operations([loft_operation()])
        self.assertEqual(validated[0]["op"], "surface_loft")
        self.assertEqual(validated[0]["sections"], ["loft_a", "loft_b"])
        self.assertEqual(validated[0]["interpolation"], "straight")

    def test_accepts_integer_section_ids(self):
        validated = validate_operations([loft_operation(sections=[12, 19])])
        self.assertEqual(validated[0]["sections"], [12, 19])

    def test_normalizes_digit_only_strings_to_ids(self):
        validated = validate_operations([loft_operation(sections=["12", 19])])
        self.assertEqual(validated[0]["sections"], [12, 19])

    def test_rejects_one_section(self):
        with self.assertRaises(ValueError):
            validate_operations([loft_operation(sections=["loft_a"])])

    def test_rejects_three_sections(self):
        with self.assertRaises(ValueError):
            validate_operations([loft_operation(sections=["loft_a", "loft_b", "loft_c"])])

    def test_rejects_duplicate_sections(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate_operations([loft_operation(sections=["loft_a", "loft_a"])])

    def test_rejects_smooth_interpolation(self):
        with self.assertRaises(ValueError):
            validate_operations([loft_operation(interpolation="smooth")])

    def test_rejects_closed_continuity_and_solid_switches(self):
        # Extra keys are refused by the strict model instead of silently
        # degrading an unsupported request into a straight two-section loft.
        for extra in (
            {"closed": True},
            {"continuity": "G1"},
            {"tangency": "free"},
            {"mode": "add"},
            {"new_body": True},
        ):
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):
                    validate_operations([loft_operation(**extra)])

    def test_rejects_negative_and_boolean_ids(self):
        for sections in ([-1, 5], [True, 5]):
            with self.subTest(sections=sections):
                with self.assertRaises(ValueError):
                    validate_operations([loft_operation(sections=sections)])


class SurfaceLoftCapabilityTests(unittest.TestCase):
    def test_operation_is_registered_and_published(self):
        self.assertIn("surface_loft", REGISTERED_OPERATIONS)
        self.assertNotIn("surface_loft", UNAVAILABLE_OPERATIONS)

    def test_surface_chain_publishes_the_loft_tool(self):
        from creo_mechdog.capabilities import families

        block = families()["surface_chain"]
        self.assertIn("creo_surface_loft", block["tools"])
        self.assertIn("surface_loft", families())

    def test_server_registers_the_tool(self):
        text = SERVER.read_text(encoding="utf-8")
        self.assertIn("async def creo_surface_loft(", text)
        self.assertIn('"surface_loft"', text)

    def test_solid_loft_stays_solid_only(self):
        # The new surface op must not loosen creo_loft's existing gate.
        for operation in (
            {"op": "loft", "label": "solid", "sections": ["a", "b"], "mode": "surface"},
            {"op": "loft", "label": "solid", "sections": ["a", "b"], "new_body": True},
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(ValueError):
                    require_available([operation])


class SurfaceLoftProjectionTests(unittest.TestCase):
    def test_compact_projection_keeps_the_measurements(self):
        self.assertIs(_OPERATION_CRITERIA["surface_loft"], SURFACE_LOFT_KEYS)
        for key in (
            "quilt_id",
            "surface_area_mm2",
            "surface_area_status",
            "quilt_closed_native",
            "has_solid",
            "section_curve_ids",
        ):
            self.assertIn(key, SURFACE_LOFT_KEYS)

    def test_native_route_is_the_documented_blend_tree(self):
        text = NATIVE.read_text(encoding="utf-8")
        self.assertIn("static void generic_surface_loft(const J &op)", text)
        self.assertIn("PRO_E_DTM_SRF_TYPE_BND_BLEND", text)
        self.assertIn("PRO_E_BNBLN_CURVES", text)
        self.assertIn("PRO_E_BNBLN_1DIR", text)
        self.assertIn("PRO_E_BNBLN_DIR_CURVES", text)
        self.assertIn("PRO_E_STD_CHAIN_HOLDER", text)
        self.assertIn("PRO_E_STD_CURVE_COLLECTION_APPL", text)
        self.assertIn("curve_collection", text)
        # INCOMPLETE create + extracted tree + redefine is the documented route.
        self.assertIn("PRO_FEAT_CR_INCOMPLETE_FEAT", text)
        self.assertIn("ProFeatureElemtreeExtract", text)
        self.assertIn("redefine(&feature, extracted)", text)
        # §2.1 forbids guessing the free-tangency elements in the first release.
        # Only code counts: the header comment names the forbidden elements.
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))
        self.assertNotIn("PRO_E_BNBLN_TAN_COND", code)
        self.assertNotIn("PRO_E_BBL_ADD_CLOSED", code)
        # The solid Blend macro route is never a fallback for a surface loft.
        self.assertNotIn("ProMacroLoad", code)

    def test_native_is_dispatched_and_included(self):
        generic = GENERIC.read_text(encoding="utf-8")
        self.assertIn('#include "surface_loft.cpp"', generic)
        self.assertIn('else if (kind == "surface_loft")', generic)

    def test_driver_exposes_the_offline_and_live_modes(self):
        text = DRIVER.read_text(encoding="utf-8")
        self.assertIn("--confirm-session-usable", text)
        self.assertIn('"surface_area_mm2"', text)
        self.assertIn("800.0", text)


if __name__ == "__main__":
    unittest.main()
