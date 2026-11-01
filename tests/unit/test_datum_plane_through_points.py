"""FEAT-053: datum_plane three-point form ({kind:'through_points'}) admission tests.

Offline only. Covers the schema contract (three labels created earlier in the
same plan by single-point datum_points operations), the explicit conversion of
the external 0.10.0 package forms, and - through isolated stubs - the judgment
and readback assertion logic of tools/test_datum_plane_through_points.py.
The native geometry boundary itself runs in the executor and is covered by the
live driver, not here.
"""

import copy
import json
import unittest

from creo_mechdog.references import (
    DATUM_PLANE_REFERENCE_KIND_DESCRIPTION,
    validate_datum_plane_reference_kind,
    validate_datum_plane_through_points,
)
from creo_mechdog.schema import PlaneOp, validate_operations
from tools import test_datum_plane_through_points as driver

SMOKE = {
    "dpa0": [-95.191114, 40.0, -88.395141],
    "dpb0": [95.191114, 40.0, 88.395141],
    "dpd0": [94.701973, 50.416667, 89.27114],
}


def points_op(label: str, positions: list) -> dict:
    return {
        "op": "datum_points",
        "label": label,
        "points": [
            {"name": f"p{index}", "position": list(position)}
            for index, position in enumerate(positions)
        ],
    }


def three_points_ops() -> list[dict]:
    return [points_op(label, [position]) for label, position in SMOKE.items()]


def plane_op(**overrides) -> dict:
    op = {
        "op": "datum_plane",
        "label": "pl00a",
        "reference": {"kind": "through_points", "points": ["dpa0", "dpb0", "dpd0"]},
    }
    op.update(overrides)
    return op


def through(points) -> dict:
    return {"kind": "through_points", "points": points}


class ThroughPointsPositiveTests(unittest.TestCase):
    def test_three_distinct_single_point_datum_points_validate(self):
        dumped = validate_operations([*three_points_ops(), plane_op()])
        reference = dumped[-1]["reference"]
        self.assertEqual(reference, through(["dpa0", "dpb0", "dpd0"]))
        self.assertEqual([op["label"] for op in dumped[:3]], ["dpa0", "dpb0", "dpd0"])

    def test_zero_offset_is_the_default_and_allowed(self):
        dumped = validate_operations([*three_points_ops(), plane_op(offset=0)])
        self.assertEqual(dumped[-1]["offset"], 0)

    def test_labels_may_be_reused_across_point_names_but_stay_distinct(self):
        operations = [
            points_op("shared_a", [[0, 0, 0], [1, 1, 1]]),
            points_op("shared_b", [[2, 0, 0]]),
            points_op("shared_c", [[0, 2, 0]]),
            plane_op(reference=through(["shared_a", "shared_b", "shared_c"])),
        ]
        # shared_a is a multi-point feature, so this must be refused.
        with self.assertRaises(ValueError) as caught:
            validate_operations(operations)
        self.assertIn("single-point", str(caught.exception))

    def test_point_order_is_preserved_verbatim(self):
        dumped = validate_operations(
            [
                *three_points_ops(),
                plane_op(reference=through(["dpd0", "dpb0", "dpa0"])),
            ]
        )
        self.assertEqual(dumped[-1]["reference"]["points"], ["dpd0", "dpb0", "dpa0"])

    def test_single_operation_model_still_admits_the_plane_shape(self):
        # The standalone tool builds exactly this dict; both entries share the
        # contract, so the same plan context decides admission.
        self.assertIsInstance(PlaneOp.model_validate(plane_op()), PlaneOp)


class ThroughPointsShapeTests(unittest.TestCase):
    def test_two_and_four_points_are_rejected(self):
        for points in (["dpa0", "dpb0"], ["dpa0", "dpb0", "dpd0", "dpe0"]):
            with self.subTest(points=points), self.assertRaises(ValueError) as caught:
                validate_operations([*three_points_ops(), plane_op(reference=through(points))])
            self.assertIn("exactly three", str(caught.exception))

    def test_empty_and_missing_points_are_rejected(self):
        for points in ([], None, "dpa0", {"a": 1}):
            with self.subTest(points=points), self.assertRaises(ValueError):
                validate_operations([*three_points_ops(), plane_op(reference=through(points))])

    def test_repeated_labels_are_rejected(self):
        with self.assertRaises(ValueError) as caught:
            validate_operations(
                [*three_points_ops(), plane_op(reference=through(["dpa0", "dpa0", "dpb0"]))]
            )
        self.assertIn("distinct", str(caught.exception))

    def test_empty_bool_and_non_string_entries_are_rejected(self):
        for points in (
            ["dpa0", "dpb0", ""],
            ["dpa0", "dpb0", None],
            ["dpa0", "dpb0", True],
            ["dpa0", "dpb0", 3],
            ["dpa0", "dpb0", ["dpd0"]],
        ):
            with self.subTest(points=points), self.assertRaises(ValueError) as caught:
                validate_operations([*three_points_ops(), plane_op(reference=through(points))])
            message = str(caught.exception)
            self.assertIn("label", message)

    def test_label_syntax_violations_are_rejected(self):
        for bad in ("Dpa0", "0dp", "dpa-0", "x" * 29, "dp a"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_operations(
                    [*three_points_ops(), plane_op(reference=through(["dpa0", "dpb0", bad]))]
                )

    def test_validate_datum_plane_through_points_reports_the_path(self):
        with self.assertRaises(ValueError) as caught:
            validate_datum_plane_through_points(through(["a", "a", "b"]), "operations[0].reference")
        self.assertIn("operations[0].reference.points:", str(caught.exception))


class ThroughPointsProducerTests(unittest.TestCase):
    def test_future_reference_is_rejected(self):
        operations = [
            plane_op(),
            *three_points_ops(),
        ]
        with self.assertRaises(ValueError) as caught:
            validate_operations(operations)
        message = str(caught.exception)
        self.assertIn("dpa0", message)
        self.assertIn("created later in this plan", message)

    def test_reference_to_a_feature_the_plan_never_creates_is_rejected(self):
        operations = [
            points_op("dpa0", [[0, 0, 0]]),
            points_op("dpb0", [[1, 0, 0]]),
            plane_op(reference=through(["dpa0", "dpb0", "ghost"])),
        ]
        with self.assertRaises(ValueError) as caught:
            validate_operations(operations)
        message = str(caught.exception)
        self.assertIn("ghost", message)
        self.assertIn("does not create it", message)

    def test_wrong_feature_type_is_rejected(self):
        operations = [
            {
                "op": "sketch",
                "label": "wrong_kind",
                "plane": "XY",
                "entities": [
                    {
                        "type": "rectangle",
                        "name": "r",
                        "min": [0, 0],
                        "max": [1, 1],
                    }
                ],
                "dimensioning": "coordinates",
            },
            *three_points_ops(),
            plane_op(reference=through(["wrong_kind", "dpb0", "dpd0"])),
        ]
        with self.assertRaises(ValueError) as caught:
            validate_operations(operations)
        message = str(caught.exception)
        self.assertIn("wrong_kind", message)
        self.assertIn("requires a datum_points", message)

    def test_multi_point_datum_points_feature_is_rejected(self):
        operations = [
            points_op("dpa0", [[0, 0, 0], [1, 0, 0]]),
            points_op("dpb0", [[0, 1, 0]]),
            points_op("dpd0", [[0, 0, 1]]),
            plane_op(),
        ]
        with self.assertRaises(ValueError) as caught:
            validate_operations(operations)
        message = str(caught.exception)
        self.assertIn("dpa0", message)
        self.assertIn("single-point", message)
        self.assertIn("defines 2 points", message)

    def test_producers_must_precede_the_plane_within_the_plan(self):
        operations = [
            points_op("dpa0", [[0, 0, 0]]),
            plane_op(),
            points_op("dpb0", [[1, 0, 0]]),
            points_op("dpd0", [[0, 1, 0]]),
        ]
        with self.assertRaises(ValueError) as caught:
            validate_operations(operations)
        self.assertIn("created later in this plan", str(caught.exception))


class ThroughPointsExclusionTests(unittest.TestCase):
    def test_angle_axis_and_nonzero_offset_are_mutually_exclusive(self):
        cases = (
            ({"angle": 0}, "angle"),
            ({"angle": 54}, "angle"),
            ({"angle": 54, "axis": {"kind": "axis", "id": 83}}, "angle"),
            ({"axis": {"kind": "axis", "id": 83}}, "axis"),
            ({"axis": {"kind": "datum_axis_feature", "label": "ax1"}}, "axis"),
            ({"offset": 5.0}, "nonzero offset"),
            ({"offset": -0.5}, "nonzero offset"),
        )
        for overrides, expected in cases:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError) as caught:
                validate_operations([*three_points_ops(), plane_op(**overrides)])
            message = str(caught.exception)
            self.assertIn("through_points", message)
            self.assertIn(expected, message)

    def test_mixed_input_is_rejected_before_any_job_is_dispatched(self):
        with self.assertRaises(ValueError):
            PlaneOp.model_validate(plane_op(offset=1.0))
        with self.assertRaises(ValueError):
            PlaneOp.model_validate(plane_op(angle=0, axis={"kind": "axis", "id": 83}))


class ExternalFormTests(unittest.TestCase):
    def test_kindless_thru_points_is_rejected_and_not_passed_through(self):
        for reference in (
            {"thru_points": ["dpa0", "dpb0", "dpd0"]},
            {"thru_points": ["dpa0", "dpb0", "dpd0"], "kind": None},
        ):
            with self.subTest(reference=reference), self.assertRaises(ValueError) as caught:
                validate_operations([*three_points_ops(), plane_op(reference=reference)])
            message = str(caught.exception)
            self.assertIn("before a job is dispatched", message)
            self.assertNotIn("json.exception", message)

    def test_thru_points_key_with_contract_kind_still_requires_points(self):
        with self.assertRaises(ValueError) as caught:
            validate_operations(
                [
                    *three_points_ops(),
                    plane_op(reference={"kind": "through_points", "thru_points": ["a", "b", "c"]}),
                ]
            )
        self.assertIn("points", str(caught.exception))

    def test_executor_internal_datum_point_feature_form_is_refused_with_conversion(self):
        reference = {"kind": "datum_point_feature", "label": "dpa0"}
        with self.assertRaises(ValueError) as caught:
            validate_operations([*three_points_ops(), plane_op(reference=reference)])
        message = str(caught.exception)
        self.assertIn("datum_point_feature", message)
        self.assertIn("through_points", message)

    def test_bare_thru_points_operation_key_is_refused_by_the_strict_model(self):
        op = {
            "op": "datum_plane",
            "label": "pl00a",
            "thru_points": ["dpa0", "dpb0", "dpd0"],
        }
        with self.assertRaises(ValueError):
            validate_operations([*three_points_ops(), op])

    def test_unsupported_kinds_keep_the_documented_description(self):
        for reference in (
            {"kind": "thru_points", "points": ["dpa0", "dpb0", "dpd0"]},
            {"kind": "point", "id": 3},
            {"kind": "axis", "id": 3},
        ):
            with self.subTest(reference=reference), self.assertRaises(ValueError) as caught:
                validate_operations([*three_points_ops(), plane_op(reference=reference)])
            self.assertIn("kind", str(caught.exception))

    def test_conversion_functions_produce_the_contract_form(self):
        converted = driver.convert_plane_operation(
            {
                "op": "datum_plane",
                "label": "pl00a",
                "reference": {"thru_points": ["dpa0", "dpb0", "dpd0"]},
            }
        )
        self.assertEqual(converted["reference"], through(["dpa0", "dpb0", "dpd0"]))
        direct = driver.convert_plane_operation(
            {
                "op": "datum_plane",
                "label": "pl00a",
                "thru_points": ["dpa0", "dpb0", "dpd0"],
            }
        )
        self.assertEqual(direct["reference"], through(["dpa0", "dpb0", "dpd0"]))
        self.assertNotIn("thru_points", direct)
        with self.assertRaises(ValueError):
            driver.convert_plane_operation(
                {
                    "op": "datum_plane",
                    "label": "pl00a",
                    "reference": {"kind": "datum_point_feature", "label": "dpa0"},
                }
            )

    def test_converted_smoke_plan_validates_and_original_does_not(self):
        raw = json.loads(driver.SMOKE_SOURCE.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            validate_operations(copy.deepcopy(raw))
        dumped = validate_operations(driver.converted_smoke_operations())
        plane = next(op for op in dumped if op["op"] == "datum_plane")
        self.assertEqual(plane["reference"], through(["dpa0", "dpb0", "dpd0"]))


class PreservedContractTests(unittest.TestCase):
    def test_missing_kind_is_still_rejected_before_dispatch(self):
        for reference in ({}, {"normal": [0, 0, 1]}, {"axis": "z"}):
            with self.subTest(reference=reference), self.assertRaises(ValueError) as caught:
                validate_operations([plane_op(reference=reference)])
            message = str(caught.exception)
            self.assertIn("kind", message)
            self.assertIn("before a job is dispatched", message)

    def test_angle_with_nonzero_offset_is_still_rejected(self):
        op = {
            "op": "datum_plane",
            "label": "datum",
            "reference": {"kind": "datum_plane", "axis": "z"},
            "offset": -8.65981,
            "angle": 54,
            "axis": {"kind": "axis", "id": 83},
        }
        with self.assertRaises(ValueError) as caught:
            validate_operations([op])
        self.assertIn("nonzero offset", str(caught.exception))

    def test_plain_plane_references_keep_their_semantics(self):
        for reference in (
            {"kind": "datum_plane", "axis": "z"},
            {"kind": "datum_plane", "normal": [0, 0, 1], "offset": 10},
            {"kind": "datum_plane", "id": 163},
            {"kind": "plane", "id": 9},
            {"kind": "surface", "id": 11},
            {"kind": "datum_feature", "label": "plane_label"},
        ):
            with self.subTest(reference=reference):
                validated = validate_operations([plane_op(reference=reference)])[0]
                self.assertEqual(validated["reference"], reference)

    def test_kind_description_still_states_the_dispatch_gate(self):
        self.assertIn("kind", DATUM_PLANE_REFERENCE_KIND_DESCRIPTION)
        self.assertIn("before a job is dispatched", DATUM_PLANE_REFERENCE_KIND_DESCRIPTION)
        self.assertIn("through_points", DATUM_PLANE_REFERENCE_KIND_DESCRIPTION)

    def test_kind_validator_reports_the_path(self):
        with self.assertRaises(ValueError) as caught:
            validate_datum_plane_reference_kind({}, "operations[0].reference")
        self.assertIn("operations[0].reference:", str(caught.exception))


class JudgmentOracleStubTests(unittest.TestCase):
    """Isolated-stub coverage of the judgment logic mirrored by the native side."""

    def test_smoke_triangle_is_accepted_at_every_scale(self):
        smoke = [list(p) for p in SMOKE.values()]
        for factor in (1e-3, 1.0, 1e6):
            with self.subTest(factor=factor):
                scaled = [[v * factor for v in p] for p in smoke]
                verdict = driver.classify_points(scaled)
                self.assertEqual(verdict["classification"], "ok")
                self.assertAlmostEqual(
                    verdict["geometry"]["min_altitude_ratio"],
                    driver.classify_points(smoke)["geometry"]["min_altitude_ratio"],
                    places=9,
                )

    def test_nearly_collinear_and_exact_collinear_are_refused(self):
        for points in (
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 1e-9, 0.0]],
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 1e-7, 0.0]],
        ):
            with self.subTest(points=points):
                self.assertEqual(
                    driver.classify_points(points)["classification"], "nearly_collinear"
                )

    def test_repeated_and_coincident_points_are_refused(self):
        self.assertEqual(
            driver.classify_points([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])[
                "classification"
            ],
            "repeated_points",
        )
        self.assertEqual(
            driver.classify_points([[0.0, 0.0, 0.0]] * 3)["classification"], "undecidable"
        )

    def test_non_finite_and_malformed_inputs_are_undecidable(self):
        for points in (
            [[0.0, 0.0, float("nan")], [1, 0, 0], [0, 1, 0]],
            [[0.0, 0.0, 0.0], [1.0, 0.0]],
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        ):
            with self.subTest(points=points):
                self.assertEqual(driver.classify_points(points)["classification"], "undecidable")

    def test_tolerances_are_dimensionless_ratios_not_world_coordinates(self):
        self.assertEqual(driver.DUPLICATE_RATIO_TOLERANCE, 1e-9)
        self.assertEqual(driver.COLLINEAR_ALTITUDE_RATIO_TOLERANCE, 1e-6)
        self.assertEqual(driver.ALIGNMENT_TOLERANCE, 1e-9)
        self.assertEqual(driver.distance_tolerance_mm(0.0), driver.DISTANCE_TOLERANCE_FLOOR_MM)
        self.assertEqual(driver.distance_tolerance_mm(1e9), 1.0)


class ReadbackAssertionStubTests(unittest.TestCase):
    def _detail(self) -> dict:
        smoke = [list(p) for p in SMOKE.values()]
        geometry = driver.classify_points(smoke)["geometry"]
        ab = [smoke[1][i] - smoke[0][i] for i in range(3)]
        ac = [smoke[2][i] - smoke[0][i] for i in range(3)]
        normal = driver.unit(driver.cross(ab, ac))
        return {
            "plane_frame": {"surface_id": 47, "normal": normal, "origin": list(smoke[0])},
            "precheck": {"classification": "ok", **geometry},
            "points": [
                {"label": label, "feature_id": i + 7, "point_id": 70 + i, "position": position}
                for i, (label, position) in enumerate(zip(SMOKE, smoke))
            ],
            "verification": {
                "point_distances": [0.0, 0.0, 0.0],
                "max_point_distance": 0.0,
                "distance_tolerance": driver.distance_tolerance_mm(geometry["longest_side"]),
                "normal_alignment": 1.0,
                "alignment_tolerance": driver.ALIGNMENT_TOLERANCE,
                "constraint_count": 3,
                "constraints": [
                    {
                        "constr_type": 0,
                        "constr_type_name": "thru",
                        "ref_type_name": "point",
                        "ref_id": ref_id,
                    }
                    for ref_id in (70, 71, 72)
                ],
                "references_ok": True,
                "verified": True,
            },
        }

    def _rejected(self, detail: dict, expected=(70, 71, 72)) -> None:
        with self.assertRaises((AssertionError, ValueError)):
            driver.check_readback(detail, list(expected))

    def test_matching_readback_passes(self):
        summary = driver.check_readback(self._detail(), [70, 71, 72])
        self.assertEqual(summary["point_ids"], [70, 71, 72])

    def test_flipped_normal_is_accepted_as_the_same_plane(self):
        detail = self._detail()
        detail["verification"]["normal_alignment"] = -1.0
        detail["plane_frame"]["normal"] = [-v for v in detail["plane_frame"]["normal"]]
        driver.check_readback(detail, [70, 71, 72])

    def test_point_off_the_plane_is_rejected(self):
        detail = self._detail()
        detail["verification"]["point_distances"] = [0.0, 0.5, 0.0]
        detail["verification"]["max_point_distance"] = 0.5
        self._rejected(detail)

    def test_skewed_normal_is_rejected(self):
        detail = self._detail()
        detail["verification"]["normal_alignment"] = 0.99
        self._rejected(detail)

    def test_wrong_constraint_reference_is_rejected(self):
        detail = self._detail()
        detail["verification"]["constraints"][0]["ref_id"] = 73
        self._rejected(detail)

    def test_wrong_constraint_reference_type_is_rejected(self):
        detail = self._detail()
        detail["verification"]["constraints"][1]["ref_type_name"] = "axis"
        self._rejected(detail)

    def test_unverified_flag_is_rejected(self):
        detail = self._detail()
        detail["verification"]["verified"] = False
        self._rejected(detail)

    def test_failure_invariant_rejects_revision_and_feature_drift(self):
        before = {
            "revision": 2,
            "aliases": {"dpa0": {"feature_id": 7, "op": "datum_points"}},
            "inspection": {"features": [{"id": 5}, {"id": 7}]},
        }
        driver.check_failure_invariant(before, copy.deepcopy(before))
        bumped = copy.deepcopy(before)
        bumped["revision"] = 3
        with self.assertRaises(AssertionError):
            driver.check_failure_invariant(before, bumped)
        grown = copy.deepcopy(before)
        grown["inspection"]["features"] = [{"id": 5}, {"id": 7}, {"id": 9}]
        with self.assertRaises(AssertionError):
            driver.check_failure_invariant(before, grown)


class NativeBoundarySourceTests(unittest.TestCase):
    """The native side must carry the same judgment constants and refusals."""

    @classmethod
    def setUpClass(cls):
        cls.source = (driver.ROOT / "native" / "generic.cpp").read_text(encoding="utf-8")

    def test_native_declares_the_documented_tolerance_constants(self):
        for token in (
            "kThruPointsDuplicateRatio",
            "kThruPointsCollinearRatio",
            "kThruPointsAlignTolerance",
        ):
            self.assertIn(token, self.source)

    def test_native_refuses_the_judgment_failures(self):
        for message in (
            "nearly collinear",
            "repeated point",
            "cannot determine",
            "single PRO_POINT",
            "datum point feature",
        ):
            self.assertIn(message, self.source)

    def test_native_builds_three_thru_constraints(self):
        self.assertIn("PRO_DTMPLN_THRU", self.source)
        self.assertIn("kind", self.source)
        self.assertIn('"through_points"', self.source)


if __name__ == "__main__":
    unittest.main()
