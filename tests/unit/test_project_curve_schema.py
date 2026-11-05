"""S04 project_curve contract tests (FEAT-039/FEAT-055).

Offline only. The schema, the gate and the native wiring are locked here; the
projection geometry, its measured length/endpoints and the saved reload belong
to ``tools/test_surface_chain.py --case project --live``. No test in this file
claims a native projection ran.

The direction rules follow the S02 lesson: ``{kind:"datum_plane",label:...}``
resolves by geometry and silently drops the label, so a projection may not name
a plane that way. A label is only honoured through ``datum_feature`` /
``datum_axis_feature``, and a raw vector is never accepted — the direction must
be readable from real model geometry.
"""

import unittest
from pathlib import Path

from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
GENERIC = ROOT / "native" / "generic.cpp"
PROJECT_CURVE = ROOT / "native" / "project_curve.cpp"
DRIVER = ROOT / "tools" / "test_surface_chain.py"

TARGET = {"kind": "quilt", "id": 12}
SOURCE = {"kind": "curve", "id": 7}
DIRECTION = {"kind": "datum_feature", "label": "top"}


def project_operation(**overrides):
    operation = {
        "op": "project_curve",
        "label": "project_main",
        "target": dict(TARGET),
        "source": dict(SOURCE),
        "direction_ref": dict(DIRECTION),
    }
    operation.update(overrides)
    return operation


class ProjectCurveSchemaTests(unittest.TestCase):
    def test_accepts_one_quilt_one_curve_and_explicit_direction(self):
        validated = validate_operations([project_operation()])
        self.assertEqual(validated[0]["op"], "project_curve")
        self.assertEqual(validated[0]["target"], TARGET)
        self.assertEqual(validated[0]["source"], SOURCE)
        self.assertEqual(validated[0]["direction_ref"], DIRECTION)

    def test_side_defaults_to_positive(self):
        validated = validate_operations([project_operation()])
        self.assertEqual(validated[0]["side"], "positive")
        explicit = validate_operations([project_operation(side="negative")])
        self.assertEqual(explicit[0]["side"], "negative")

    def test_rejects_side_outside_the_two_native_values(self):
        for side in ("along", "against", "both", 1, None):
            with self.assertRaises(ValueError):
                validate_operations([project_operation(side=side)])

    def test_rejects_body_target(self):
        with self.assertRaisesRegex(ValueError, "target"):
            validate_operations([project_operation(target={"kind": "body", "id": 3})])

    def test_rejects_datum_plane_target(self):
        # The projection lands on a quilt; a datum plane is a trim tool, not a
        # projection target.
        with self.assertRaisesRegex(ValueError, "target"):
            validate_operations(
                [project_operation(target={"kind": "datum_plane", "label": "FRONT"})]
            )

    def test_rejects_missing_target_kind(self):
        with self.assertRaisesRegex(ValueError, "target"):
            validate_operations([project_operation(target={"id": 12})])

    def test_rejects_source_that_is_not_a_curve(self):
        for source in (
            {"kind": "quilt", "id": 12},
            {"kind": "surface", "id": 3},
            {"kind": "body", "id": 1},
            {"kind": "curve", "label": "sketch_1"},
        ):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "source"):
                validate_operations([project_operation(source=source)])

    def test_rejects_source_id_that_is_not_a_nonnegative_integer(self):
        for value in (-1, "7", 7.0, True, None, 2147483648):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "source"):
                validate_operations([project_operation(source={"kind": "curve", "id": value})])

    def test_rejects_missing_direction(self):
        operation = project_operation()
        operation.pop("direction_ref")
        with self.assertRaises(ValueError):
            validate_operations([operation])

    def test_rejects_datum_plane_label_as_direction(self):
        # Live 2026-11-04 (S02): a label on kind datum_plane is dropped by the
        # resolver and the default axis filter picks TOP. The refusal names the
        # form that does honour the label.
        with self.assertRaisesRegex(ValueError, "datum_feature"):
            validate_operations(
                [project_operation(direction_ref={"kind": "datum_plane", "label": "TOP"})]
            )

    def test_accepts_the_documented_direction_forms(self):
        for direction in (
            {"kind": "datum_feature", "label": "top"},
            {"kind": "datum_axis_feature", "label": "axis_main"},
            {"kind": "curve", "id": 9},
        ):
            with self.subTest(direction=direction):
                validated = validate_operations([project_operation(direction_ref=direction)])
                self.assertEqual(validated[0]["direction_ref"], direction)

    def test_rejects_direction_forms_that_cannot_be_read(self):
        for direction in (
            {"kind": "body", "id": 1},
            {"kind": "datum_feature"},
            {"kind": "datum_axis_feature"},
            {"kind": "curve", "id": -2},
            {"kind": "quilt", "id": 12},
        ):
            with self.subTest(direction=direction), self.assertRaises(ValueError):
                validate_operations([project_operation(direction_ref=direction)])
        with self.assertRaises(ValueError):
            validate_operations([project_operation(direction_ref={})])

    def test_rejects_a_raw_direction_vector(self):
        # No implicit or vector-supplied direction: the vector has to come from
        # real geometry so the reported side has a measurable basis.
        with self.assertRaises(ValueError):
            validate_operations([project_operation(direction=[0.0, 0.0, -1.0])])
        with self.assertRaises(ValueError):
            validate_operations(
                [project_operation(direction_ref={"kind": "vector", "xyz": [0, 0, 1]})]
            )

    def test_rejects_unknown_field(self):
        with self.assertRaises(ValueError):
            validate_operations([project_operation(closed=True)])

    def test_labels_stay_unique_across_surface_operations(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_operations(
                [
                    project_operation(),
                    project_operation(label="project_main", target={"kind": "quilt", "id": 13}),
                ]
            )

    def test_project_curve_is_published_after_live_evidence(self):
        from creo_mechdog.capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS

        self.assertIn("project_curve", REGISTERED_OPERATIONS)
        # Live 2026-11-04: the swept-surface route measured a 30 mm line and a
        # pi*8 arc projection at z=0, saved and reloaded, so the gate is off.
        self.assertNotIn("project_curve", UNAVAILABLE_OPERATIONS)
        server = (ROOT / "server.py").read_text(encoding="utf-8")
        self.assertIn("async def creo_project_curve(", server)
        self.assertIn("helper_feature_id", server)


class ProjectCurveNativeSourceTests(unittest.TestCase):
    def test_native_entry_point_is_wired_once(self):
        source = PROJECT_CURVE.read_text(encoding="utf-8")
        self.assertIn("static void generic_project_curve(const J &op)", source)
        generic = GENERIC.read_text(encoding="utf-8")
        self.assertEqual(generic.count("generic_project_curve(op)"), 1)
        self.assertIn('#include "project_curve.cpp"', generic)

    def test_native_reuses_the_frozen_measurement_helpers(self):
        source = PROJECT_CURVE.read_text(encoding="utf-8")
        for helper in (
            "resolve_quilt_reference",
            "curve_length_native",
            "curve_endpoints_json",
            "length_mm_json",
            "measurement_status_json",
        ):
            self.assertIn(helper, source)
        # The curve measurement lives in surface_measure.h; the projection must
        # not grow a second copy of ProCurveLengthEval.
        self.assertNotIn("ProCurveLengthEval(", source)

    def test_native_refuses_a_degenerate_direction(self):
        source = PROJECT_CURVE.read_text(encoding="utf-8")
        for token in ("std::isfinite", "direction_length", "must not be zero"):
            self.assertIn(token, source)

    def test_native_uses_the_routes_that_exist(self):
        # Neither the COPYTRIM nor the PROJECT element family has a documented
        # tree; the delivery must stay on the documented intersect tree plus a
        # real swept surface, never on a guessed element layout.
        source = PROJECT_CURVE.read_text(encoding="utf-8")
        self.assertIn("PRO_CURVE_TYPE_INTSRF", source)
        self.assertIn("PRO_E_CRV_IP_COMP_REF1", source)
        self.assertIn("PRO_CURVE_TYPE_MULTIPLE_SEL", source)
        self.assertIn("PRO_E_STD_SECTION", source)
        self.assertNotIn('"PRO_E_COPYTRIM', source)
        self.assertNotIn('"PRO_E_PROJ_CRV', source)

    def test_native_reports_the_construction_and_refuses_multi_branch(self):
        source = PROJECT_CURVE.read_text(encoding="utf-8")
        for token in (
            '"swept_surface_intersect"',
            "helper_feature_id",
            "curve_candidates",
            "separate curves",
            "target quilt lies behind",
        ):
            self.assertIn(token, source)

    def test_driver_declares_project_case(self):
        driver = DRIVER.read_text(encoding="utf-8")
        self.assertIn('"project"', driver)
        self.assertRegex(driver, r"(?s)CASES = \([^)]*\"project\"")


if __name__ == "__main__":
    unittest.main()
