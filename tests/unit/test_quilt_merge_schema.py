"""S03 quilt_merge contract tests (FEAT-039).

Offline only. The schema, the gate and the native wiring are locked here; the
documented ProMerge.h tree is compiled but its geometry, closure and saved
reload belong to ``tools/test_surface_chain.py --case merge --live``. No test
in this file claims a native merge ran.
"""

import unittest
from pathlib import Path

from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
GENERIC = ROOT / "native" / "generic.cpp"
QUILT_MERGE = ROOT / "native" / "quilt_merge.cpp"
DRIVER = ROOT / "tools" / "test_surface_chain.py"

TARGET = {"kind": "quilt", "id": 12}
TOOL = {"kind": "quilt_feature", "label": "tool_fill"}


def merge_operation(**overrides):
    operation = {
        "op": "quilt_merge",
        "label": "merge_main",
        "target": dict(TARGET),
        "tool": dict(TOOL),
    }
    operation.update(overrides)
    return operation


class QuiltMergeSchemaTests(unittest.TestCase):
    def test_accepts_two_distinct_quilts(self):
        validated = validate_operations([merge_operation()])
        self.assertEqual(validated[0]["op"], "quilt_merge")
        self.assertEqual(validated[0]["target"], TARGET)
        self.assertEqual(validated[0]["tool"], TOOL)

    def test_accepts_explicit_quilt_features_on_both_sides(self):
        validated = validate_operations(
            [
                merge_operation(
                    target={"kind": "quilt_feature", "label": "face_a"},
                    tool={"kind": "quilt_feature", "label": "face_b"},
                )
            ]
        )
        self.assertEqual(validated[0]["target"]["label"], "face_a")
        self.assertEqual(validated[0]["tool"]["label"], "face_b")

    def test_merge_requires_two_distinct_quilts(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate_operations([merge_operation(tool=dict(TARGET))])

    def test_merge_rejects_body(self):
        with self.assertRaisesRegex(ValueError, "target"):
            validate_operations([merge_operation(target={"kind": "body", "id": 3})])
        with self.assertRaisesRegex(ValueError, "tool"):
            validate_operations([merge_operation(tool={"kind": "body", "id": 3})])

    def test_merge_rejects_datum_plane_tool(self):
        # The first release joins two quilts only; a datum plane is a trim
        # tool, not a merge participant.
        with self.assertRaisesRegex(ValueError, "tool"):
            validate_operations([merge_operation(tool={"kind": "datum_plane", "label": "FRONT"})])

    def test_merge_rejects_missing_kind(self):
        with self.assertRaisesRegex(ValueError, "target"):
            validate_operations([merge_operation(target={"id": 12})])

    def test_merge_rejects_unknown_field(self):
        # A tolerance would have to be proved to take effect; until then the
        # request is refused instead of being silently ignored.
        with self.assertRaises(ValueError):
            validate_operations([merge_operation(tolerance_mm=0.01)])

    def test_merge_rejects_same_label_as_surface_trim(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_operations(
                [
                    merge_operation(),
                    merge_operation(label="merge_main", target={"kind": "quilt", "id": 13}),
                ]
            )

    def test_quilt_merge_is_gated_until_live_evidence(self):
        from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS

        self.assertIn("quilt_merge", REGISTERED_OPERATIONS)
        self.assertIn("quilt_merge", UNAVAILABLE_OPERATIONS)
        server = (ROOT / "server.py").read_text(encoding="utf-8")
        self.assertIn("async def creo_quilt_merge(", server)


class QuiltMergeNativeSourceTests(unittest.TestCase):
    def test_native_entry_point_is_wired_once(self):
        source = QUILT_MERGE.read_text(encoding="utf-8")
        self.assertIn("static void generic_quilt_merge(const J &op)", source)
        generic = GENERIC.read_text(encoding="utf-8")
        self.assertEqual(generic.count("generic_quilt_merge(op)"), 1)
        self.assertIn('#include "quilt_merge.cpp"', generic)

    def test_native_uses_the_documented_merge_tree(self):
        source = QUILT_MERGE.read_text(encoding="utf-8")
        for element in (
            "PRO_E_SRF_MRG_QUILT_ARR",
            "PRO_E_SRF_MRG_QUILT_CMPD",
            "PRO_E_SRF_MRG_QUILT_REF",
            "PRO_E_SRF_MRG_TYPE",
            "PRO_FEAT_DATUM_QUILT",
            "ProElementArraySet",
        ):
            self.assertIn(element, source)
        # ProMerge.h documents INTERSECT as the default, so JOIN must be set.
        self.assertIn("PRO_SRF_MRG_JOIN", source)
        self.assertNotIn("PRO_SRF_MRG_INTSCT", source)

    def test_native_reuses_shared_helpers(self):
        source = QUILT_MERGE.read_text(encoding="utf-8")
        self.assertIn("resolve_quilt_reference", source)
        self.assertIn("quilt_area_native", source)
        self.assertIn("quilt_closed_native", source)
        self.assertNotIn("ProContourAreaEval(", source)

    def test_native_never_fabricates_closure_or_gap(self):
        source = QUILT_MERGE.read_text(encoding="utf-8")
        for field in ("result_quilt_id", "area_mm2", "area_status", "closed", "closed_status"):
            self.assertIn(field, source)
        # No tolerance parameter and no gap field in the first release; the
        # source comment may talk about them, the tree must not build them.
        self.assertNotIn("tolerance_mm", source)
        self.assertNotIn("PRO_E_STD_MERGE_TOLERANCE", source)
        self.assertNotIn("gap_mm", source)

    def test_merge_closed_uses_the_shared_helper(self):
        # Same live lesson as S01: never compare the reason char* to a literal.
        source = QUILT_MERGE.read_text(encoding="utf-8")
        self.assertIn("quilt_closed_is_open", source)
        self.assertNotIn("closed.reason ==", source)

    def test_merge_does_not_claim_unknown_closed(self):
        # closed is true only for a measured closed quilt, false only when the
        # probe says open, and null when the probe failed. The bool/nullptr
        # ternary is forbidden: MSVC folds it into the null pointer constant.
        source = QUILT_MERGE.read_text(encoding="utf-8")
        self.assertNotIn("is_open ? false : nullptr", source)
        self.assertIn('details["closed"] = closed_json;', source)
        self.assertIn("closed_json = false;", source)

    def test_driver_declares_merge_case(self):
        driver = DRIVER.read_text(encoding="utf-8")
        self.assertIn('"merge"', driver)
        self.assertRegex(driver, r"CASES = \(.*\"merge\"")


if __name__ == "__main__":
    unittest.main()
