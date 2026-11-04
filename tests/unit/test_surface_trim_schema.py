"""S02 surface_trim contract tests (FEAT-039).

Offline only. The Python contract is exercised directly; the native half is
locked at source level (documented ProTrim.h element tree, no blind quilt
pick, no fabricated measurements). Live geometry belongs to
``tools/test_surface_chain.py --case trim --live``; these tests never claim a
native feature was built.
"""

import unittest
from pathlib import Path

from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
GENERIC = ROOT / "native" / "generic.cpp"
SURFACE_TRIM = ROOT / "native" / "surface_trim.cpp"
DRIVER = ROOT / "tools" / "test_surface_chain.py"

QUILT_TARGET = {"kind": "quilt", "id": 12}
QUILT_TOOL = {"kind": "quilt_feature", "label": "tool_fill"}
PLANE_TOOL = {"kind": "datum_plane", "label": "FRONT"}


def trim_operation(**overrides):
    operation = {
        "op": "surface_trim",
        "label": "trim_main",
        "target": dict(QUILT_TARGET),
        "tool": dict(QUILT_TOOL),
        "keep_side": "one",
    }
    operation.update(overrides)
    return operation


class SurfaceTrimSchemaTests(unittest.TestCase):
    def test_accepts_quilt_target_and_quilt_tool(self):
        validated = validate_operations([trim_operation()])
        self.assertEqual(validated[0]["op"], "surface_trim")
        self.assertEqual(validated[0]["target"], {"kind": "quilt", "id": 12})
        self.assertEqual(validated[0]["tool"], {"kind": "quilt_feature", "label": "tool_fill"})
        self.assertEqual(validated[0]["keep_side"], "one")

    def test_accepts_explicit_quilt_feature_target(self):
        validated = validate_operations(
            [trim_operation(target={"kind": "quilt_feature", "label": "blade_face"})]
        )
        self.assertEqual(validated[0]["target"], {"kind": "quilt_feature", "label": "blade_face"})

    def test_accepts_datum_plane_tool(self):
        validated = validate_operations([trim_operation(tool=dict(PLANE_TOOL))])
        self.assertEqual(validated[0]["tool"], PLANE_TOOL)

    def test_rejects_body_target(self):
        with self.assertRaisesRegex(ValueError, "target"):
            validate_operations([trim_operation(target={"kind": "body", "id": 3})])

    def test_rejects_body_tool(self):
        with self.assertRaisesRegex(ValueError, "tool"):
            validate_operations([trim_operation(tool={"kind": "body", "id": 3})])

    def test_rejects_curve_tool_use_curve_variant(self):
        # use-curve trimming is not part of the first release; a curve tool is
        # refused instead of being forwarded as an unproven tree variant.
        with self.assertRaisesRegex(ValueError, "tool"):
            validate_operations([trim_operation(tool={"kind": "curve", "id": 41})])

    def test_rejects_tool_list(self):
        with self.assertRaisesRegex(ValueError, "tool"):
            validate_operations([trim_operation(tool=[dict(QUILT_TOOL), dict(PLANE_TOOL)])])

    def test_rejects_missing_kind(self):
        with self.assertRaisesRegex(ValueError, "target"):
            validate_operations([trim_operation(target={"id": 12})])

    def test_rejects_invalid_keep_side(self):
        with self.assertRaises(ValueError):
            validate_operations([trim_operation(keep_side="both")])

    def test_rejects_missing_keep_side(self):
        operation = trim_operation()
        del operation["keep_side"]
        with self.assertRaises(ValueError):
            validate_operations([operation])

    def test_rejects_unknown_field(self):
        # Thin trimming is out of the first release; silently ignoring the
        # request would build a different feature than the caller asked for.
        with self.assertRaises(ValueError):
            validate_operations([trim_operation(thickness=2.0)])

    def test_rejects_quilt_id_type(self):
        with self.assertRaisesRegex(ValueError, "target"):
            validate_operations([trim_operation(target={"kind": "quilt", "id": "12"})])

    def test_rejects_negative_quilt_id(self):
        with self.assertRaisesRegex(ValueError, "target"):
            validate_operations([trim_operation(target={"kind": "quilt", "id": -1})])

    def test_rejects_same_quilt_for_target_and_tool(self):
        # A quilt cannot trim itself; the SDK tree would reference one object
        # as both the trimmed and the trimming side.
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate_operations([trim_operation(tool=dict(QUILT_TARGET))])

    def test_rejects_duplicate_label_with_existing_ops(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_operations(
                [
                    trim_operation(),
                    trim_operation(label="trim_main", target={"kind": "quilt", "id": 13}),
                ]
            )

    def test_surface_trim_is_gated_until_live_evidence(self):
        # S00 F03 evidence shows the quilt reference on a trim result failing
        # with ProFeatureGeomitemVisit -4; the operation is registered so the
        # removal hook and the refusal path have one home, but it is listed as
        # unavailable: server.py removes creo_surface_trim from the MCP surface
        # and submissions are refused before a native job is queued.
        from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS

        self.assertIn("surface_trim", REGISTERED_OPERATIONS)
        self.assertIn("surface_trim", UNAVAILABLE_OPERATIONS)
        server = (ROOT / "server.py").read_text(encoding="utf-8")
        self.assertIn('"creo_" + _unavailable', server)
        self.assertIn("async def creo_surface_trim(", server)


class SurfaceTrimNativeSourceTests(unittest.TestCase):
    def test_native_entry_point_is_wired_once(self):
        source = SURFACE_TRIM.read_text(encoding="utf-8")
        self.assertIn("static void generic_surface_trim(const J &op)", source)
        # Both documented trim type elements are mandatory and must agree.
        self.assertIn("PRO_E_SRF_TRIM_TYPE", source)
        self.assertIn("PRO_E_SURF_TRIM_TYPE", source)
        self.assertIn("PRO_SURF_TRIM_USE_QLT", source)
        # The use-curve variant is out of the first release.
        self.assertNotIn("PRO_E_STD_CURVE_COLLECTION_APPL", source)
        generic = GENERIC.read_text(encoding="utf-8")
        self.assertEqual(generic.count("generic_surface_trim(op)"), 1)
        self.assertIn('#include "surface_trim.cpp"', generic)

    def test_native_reuses_shared_quilt_helpers(self):
        source = SURFACE_TRIM.read_text(encoding="utf-8")
        self.assertIn("resolve_quilt_reference", source)
        self.assertIn("quilt_area_native", source)
        # A second measurement implementation would drift from S01.
        self.assertNotIn("ProContourAreaEval(", source)

    def test_native_never_fabricates_measurements_or_side(self):
        source = SURFACE_TRIM.read_text(encoding="utf-8")
        for field in (
            "area_before_mm2",
            "area_before_status",
            "area_after_mm2",
            "area_after_status",
            "kept_side_basis",
            "kept_quilt_id",
        ):
            self.assertIn(field, source)
        # keep_side one/two is mapped to the SDK side enum, never to a GUI guess.
        self.assertIn("PRO_TRIM_PRIM_QLT_SIDE_ONE", source)
        self.assertIn("PRO_TRIM_PRIM_QLT_SIDE_TWO", source)
        self.assertIn("PRO_KEEP_TRIM_SURF_OPT_NO", source)
        self.assertIn("PRO_TRIM_MATL_SIDE_ONE", source)

    def test_driver_declares_trim_case(self):
        driver = DRIVER.read_text(encoding="utf-8")
        self.assertIn('"trim"', driver)
        self.assertRegex(driver, r"CASES = \(.*\"trim\"")


if __name__ == "__main__":
    unittest.main()
