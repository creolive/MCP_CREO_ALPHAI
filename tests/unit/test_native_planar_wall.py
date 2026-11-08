"""FEAT-058: native rectangular planar wall contract (offline half).

The live acceptance creates a 100x60x1 first wall and resizes it to 120x80
(2026-11-04 probe: Fill tree in a sheetmetal-template part gives exactly
6000 mm3; the same tree in a solid part is created but fails regeneration).
Everything decided offline lives here: admission of the two operations, the
feature-identity and downstream-dependency rules, the square case, and the
signed frame envelope that rules out a sorted world bounding box.

The native side is not re-implemented in Python. These tests read the native
source only to prove the two ops are dispatched and that the create/redize
paths exist; the geometry judgements are made on the values the native result
must carry.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from creo_mechdog import native_planar_wall as pwall
from creo_mechdog.schema import validate_operations

REPO_ROOT = Path(__file__).resolve().parents[2]
NATIVE_WALL = REPO_ROOT / "native" / "planar_wall.cpp"
NATIVE_GENERIC = REPO_ROOT / "native" / "generic.cpp"
SERVER = REPO_ROOT / "server.py"

FRAME_XY = {
    "origin": [0.0, 0.0, 0.0],
    "u_axis": [1.0, 0.0, 0.0],
    "v_axis": [0.0, 1.0, 0.0],
    "normal": [0.0, 0.0, 1.0],
}
# Frame of a wall sketched on a datum plane whose u axis runs along model +Y.
FRAME_ROTATED = {
    "origin": [0.0, 0.0, 0.0],
    "u_axis": [0.0, 1.0, 0.0],
    "v_axis": [-1.0, 0.0, 0.0],
    "normal": [0.0, 0.0, 1.0],
}


def empty_sheetmetal_model() -> dict:
    return {
        "model_type": "sheetmetal",
        "inspection_summary": {"has_solid": False},
        "aliases": {},
    }


def create_op(**overrides) -> dict:
    operation = {
        "op": "sheetmetal_planar_wall",
        "label": "wall",
        "plane": "XY",
        "length": 100.0,
        "width": 60.0,
        "thickness": 1.0,
    }
    operation.update(overrides)
    return operation


def create_result(**overrides) -> dict:
    result = {
        "op": pwall.PLANAR_WALL_OP,
        "feature": "wall",
        "feature_id": 49,
        "sketch": "wall_sk",
        "length": 100.0,
        "width": 60.0,
        "thickness": 1.0,
        "direction": "positive",
        "dimension_count": 8,
        "volume_mm3": 6000.0,
        "frame": FRAME_XY,
        "envelope": {
            "u": {"min": 0.0, "max": 100.0},
            "v": {"min": 0.0, "max": 60.0},
            "n": {"min": 0.0, "max": 1.0},
        },
        "sheetmetal_body": True,
        "thickness_source": "parameter",
        "thickness_measured_mm": 1.0,
        "thickness_verified": True,
        "thickness_body_code": 0,
        "body_linked": True,
    }
    result.update(overrides)
    return result


class AdmissionTest(unittest.TestCase):
    def test_requires_empty_sheetmetal(self):
        part_model = {"model_type": "part", "inspection_summary": {"has_solid": False}}
        self.assertIn("sheetmetal", pwall.create_problem(part_model) or "")

        used_model = {
            "model_type": "sheetmetal",
            "inspection_summary": {"has_solid": True},
        }
        self.assertIn("already has geometry", pwall.create_problem(used_model) or "")

        self.assertIsNone(pwall.create_problem(empty_sheetmetal_model()))
        # A brand new model is judged natively; admission must not block it.
        self.assertIsNone(pwall.create_problem(None))

        with self.assertRaises(ValueError):
            pwall.validate_plan(part_model, [create_op()])
        pwall.validate_plan(empty_sheetmetal_model(), [create_op()])

    def test_resize_preserves_feature_identity(self):
        aliases = {"wall": {"op": pwall.PLANAR_WALL_OP, "feature_id": 49}}
        model = empty_sheetmetal_model()
        model["aliases"] = aliases
        resize = {
            "op": pwall.PLANAR_WALL_RESIZE_OP,
            "feature": "wall",
            "length": 120.0,
            "width": 80.0,
        }
        self.assertIsNone(pwall.resize_problem(model, resize, aliases=aliases))

        parent_aliases = {"wall": {"op": "sheetmetal_wall", "feature_id": 47}}
        problem = pwall.resize_problem(model, resize, aliases=parent_aliases)
        self.assertIn("only walls created by", problem or "")
        self.assertIn("unknown", (pwall.resize_problem(model, resize, aliases={}) or "").lower())

    def test_downstream_dependency_refused(self):
        aliases = {"wall": {"op": pwall.PLANAR_WALL_OP, "feature_id": 49}}
        model = empty_sheetmetal_model()
        resize = {
            "op": pwall.PLANAR_WALL_RESIZE_OP,
            "feature": "wall",
            "length": 120.0,
            "width": 80.0,
        }
        features = [
            {"id": 49, "child_ids": []},
            {"id": 52, "child_ids": []},
        ]
        self.assertIsNone(pwall.resize_problem(model, resize, aliases, features))

        features[0]["child_ids"] = [52]
        problem = pwall.resize_problem(model, resize, aliases, features)
        self.assertIn("downstream dependencies", problem or "")
        self.assertIn("52", problem or "")
        with self.assertRaises(ValueError):
            pwall.validate_plan(model, [resize], aliases, features)


class SquareTest(unittest.TestCase):
    def test_square_not_silently_unconstrained(self):
        square = create_result(
            length=60.0,
            width=60.0,
            volume_mm3=3600.0,
            envelope={
                "u": {"min": 0.0, "max": 60.0},
                "v": {"min": 0.0, "max": 60.0},
                "n": {"min": 0.0, "max": 1.0},
            },
        )
        projection = pwall.result_projection(square)
        self.assertTrue(projection["square"])
        self.assertEqual(projection["length"], 60.0)
        self.assertEqual(projection["width"], 60.0)
        self.assertEqual(projection["dimension_count"], 8)
        self.assertTrue(projection["verified"])

        # A square solved with a single dimension leaves the rectangle free to
        # move; that must never be reported as a verified wall.
        thin = pwall.result_projection(create_result(dimension_count=1))
        self.assertFalse(thin["verified"])
        self.assertTrue(any("not fully dimensioned" in item for item in thin["problems"]))


class SignedEnvelopeTest(unittest.TestCase):
    def test_signed_envelope(self):
        bounds = [[-80.0, 0.0, 0.0], [0.0, 120.0, 1.0]]
        extents = pwall.signed_extents(FRAME_ROTATED, bounds)
        self.assertAlmostEqual(extents["u"]["max"] - extents["u"]["min"], 120.0)
        self.assertAlmostEqual(extents["v"]["max"] - extents["v"]["min"], 80.0)
        self.assertAlmostEqual(extents["n"]["max"] - extents["n"]["min"], 1.0)

        result = create_result(
            length=120.0,
            width=80.0,
            frame=FRAME_ROTATED,
            envelope=extents,
            volume_mm3=9600.0,
        )
        projection = pwall.result_projection(result)
        self.assertTrue(projection["verified"], projection["problems"])

        # A sorted world bounding box would report 80 along u and 120 along v
        # for this wall; the frame judgement has to reject it.
        sorted_box = {
            "u": {"min": 0.0, "max": 80.0},
            "v": {"min": 0.0, "max": 120.0},
            "n": {"min": 0.0, "max": 1.0},
        }
        self.assertIsNotNone(pwall.envelope_problem(FRAME_ROTATED, sorted_box, 120.0, 80.0, 1.0))
        swapped = pwall.result_projection(create_result(envelope=sorted_box))
        self.assertFalse(swapped["verified"])

        inverted = {
            "u": {"min": 120.0, "max": 0.0},
            "v": {"min": 0.0, "max": 80.0},
            "n": {"min": 0.0, "max": 1.0},
        }
        self.assertIn(
            "signed interval",
            pwall.envelope_problem(FRAME_ROTATED, inverted, 120.0, 80.0, 1.0) or "",
        )

        # Wrong thickness direction is a real finding, not a rounding detail.
        self.assertIsNotNone(
            pwall.envelope_problem(
                FRAME_ROTATED,
                {
                    "u": {"min": 0.0, "max": 120.0},
                    "v": {"min": 0.0, "max": 80.0},
                    "n": {"min": -1.0, "max": 0.0},
                },
                120.0,
                80.0,
                3.0,
            )
        )


class ResizeProjectionTest(unittest.TestCase):
    def test_effective_gauge_checks_requested_value_in_both_contexts(self):
        receipt = {
            "status": "verified",
            "source": "geometry_normal_span",
            "value_mm": 2.0,
            "reason": None,
            "context": "current_plan",
        }
        projection = pwall.result_projection(
            create_result(
                op=pwall.PLANAR_WALL_RESIZE_OP,
                feature_id_before=49,
                thickness_loaded_mm=1.0,
                thickness_validation=receipt,
                thickness_loaded_validation={**receipt, "context": "saved_loaded"},
            )
        )
        self.assertFalse(projection["thickness_verified_effective"])
        self.assertFalse(projection["thickness_loaded_verified_effective"])
        self.assertFalse(projection["verified"])
        receipt["value_mm"] = 1.0
        projection = pwall.result_projection(
            create_result(
                op=pwall.PLANAR_WALL_RESIZE_OP,
                feature_id_before=49,
                thickness_loaded_mm=1.0,
                thickness_validation=receipt,
                thickness_loaded_validation={**receipt, "context": "saved_loaded"},
            )
        )
        self.assertTrue(projection["thickness_verified_effective"])
        self.assertTrue(projection["thickness_loaded_verified_effective"])
        self.assertTrue(projection["verified"], projection["problems"])

    def test_resize_keeps_identity_and_reports_shift(self):
        result = create_result(
            op=pwall.PLANAR_WALL_RESIZE_OP,
            length=120.0,
            width=80.0,
            volume_mm3=9600.0,
            feature_id_before=49,
            feature_id=49,
            thickness_loaded_mm=1.0,
            envelope={
                "u": {"min": 0.0, "max": 120.0},
                "v": {"min": 0.0, "max": 80.0},
                "n": {"min": 0.0, "max": 1.0},
            },
        )
        projection = pwall.result_projection(result)
        self.assertTrue(projection["feature_id_unchanged"])
        self.assertTrue(projection["verified"], projection["problems"])

        rebuilt = dict(result, feature_id=57)
        projection = pwall.result_projection(rebuilt)
        self.assertFalse(projection["feature_id_unchanged"])
        self.assertFalse(projection["verified"])

    def test_missing_native_ids_and_loaded_receipt_remain_unknown(self):
        result = create_result(op=pwall.PLANAR_WALL_RESIZE_OP)
        result.pop("feature_id", None)
        result.pop("feature_id_before", None)
        result.pop("thickness_loaded_validation", None)
        projection = pwall.result_projection(result)
        self.assertIsNone(projection["feature_id_unchanged"])
        self.assertIsNone(projection["thickness_loaded_validation"])
        self.assertIsNone(projection["thickness_loaded_api_scope"])
        self.assertIsNone(projection["thickness_loaded_api_reason"])
        self.assertIsNone(projection["thickness_loaded_fallback_source"])
        self.assertIsNone(projection["thickness_loaded_verified_effective"])
        self.assertFalse(projection["verified"])


class SchemaTest(unittest.TestCase):
    def test_operations_are_registered_and_validated(self):
        operations = validate_operations(
            [
                create_op(),
                {
                    "op": "resize_sheetmetal_planar_wall",
                    "feature": "wall",
                    "length": 120.0,
                    "width": 80.0,
                },
            ]
        )
        self.assertEqual(operations[0]["op"], "sheetmetal_planar_wall")
        self.assertEqual(operations[0]["plane"], "XY")
        self.assertEqual(operations[1]["op"], "resize_sheetmetal_planar_wall")

        with self.assertRaises(Exception):
            validate_operations([create_op(length=0)])
        with self.assertRaises(Exception):
            validate_operations([create_op(label="w" * 26)])
        with self.assertRaises(Exception):
            validate_operations([create_op(thickness=-1)])


class NativeWiringTest(unittest.TestCase):
    def test_job_result_publishes_the_verdict(self):
        result = {"operations": [create_result()]}
        pwall.annotate_result(result)
        self.assertTrue(result["planar_wall"]["verified"])
        self.assertEqual(result["planar_wall"]["feature_id"], 49)

        failed = {"operations": [create_result(dimension_count=2)]}
        pwall.annotate_result(failed)
        self.assertFalse(failed["planar_wall"]["verified"])

        other = {"operations": [{"op": "extrude"}]}
        pwall.annotate_result(other)
        self.assertNotIn("planar_wall", other)

        bridge_source = (REPO_ROOT / "generic_bridge.py").read_text(
            encoding="utf-8", errors="replace"
        )
        self.assertIn("native_planar_wall.annotate_result", bridge_source)

    def test_native_create_and_resize_are_dispatched(self):
        self.assertTrue(NATIVE_WALL.is_file(), "native/planar_wall.cpp is missing")
        wall = NATIVE_WALL.read_text(encoding="utf-8", errors="replace")
        for token in (
            "PRO_E_IS_UNATTACHED_WALL",
            "PRO_E_BODY_USE",
            "PRO_E_SMT_NEW_BODY_LINKED",
            "PRO_E_STD_SMT_THICKNESS",
            "ProSecdimValueSet",
            "ProFeatureChildrenGet",
        ):
            self.assertIn(token, wall, f"native planar wall is missing {token}")

        dispatch = NATIVE_GENERIC.read_text(encoding="utf-8", errors="replace")
        self.assertIn('"sheetmetal_planar_wall"', dispatch)
        self.assertIn('"resize_sheetmetal_planar_wall"', dispatch)
        self.assertIn('#include "planar_wall.cpp"', dispatch)

        server = SERVER.read_text(encoding="utf-8", errors="replace")
        self.assertIn("creo_sheetmetal_planar_wall", server)
        self.assertIn("creo_resize_sheetmetal_planar_wall", server)


class NameProtectionTest(unittest.TestCase):
    """Review finding: the driving sketch is a feature name too."""

    def test_internal_sketch_name_is_reserved(self):
        self.assertEqual(pwall.internal_labels(create_op()), (pwall.sketch_label("wall"),))
        self.assertIn("wall_sk", pwall.declared_names([create_op()]))
        self.assertEqual(pwall.internal_labels({"op": "extrude", "label": "b"}), ())

        taken = {"wall_sk": {"op": "sketch", "feature_id": 40}}
        problem = pwall.create_problem(empty_sheetmetal_model(), taken, create_op())
        self.assertIn("wall_sk", problem or "")
        self.assertIsNone(pwall.create_problem(empty_sheetmetal_model(), {}, create_op()))
        self.assertIsNone(pwall.create_problem(empty_sheetmetal_model()))

        self.assertEqual(pwall.name_conflict(["wall", "wall_sk"], set()), [])
        self.assertEqual(pwall.name_conflict(["wall", "wall"], set()), ["wall"])
        self.assertEqual(pwall.name_conflict(["wall_sk", "wall_sk"], set()), ["wall_sk"])
        self.assertEqual(pwall.name_conflict(["wall_sk"], {"wall_sk"}), ["wall_sk"])

        bridge_source = (REPO_ROOT / "generic_bridge.py").read_text(
            encoding="utf-8", errors="replace"
        )
        for token in ("declared_names", "internal_labels", "name_conflict"):
            self.assertIn(token, bridge_source)

    def test_native_refuses_a_taken_internal_name(self):
        wall = NATIVE_WALL.read_text(encoding="utf-8", errors="replace")
        self.assertIn("alias_entry(sketch_name)", wall)
        self.assertIn("managed labels are never overwritten", wall)


class PlanOrderTest(unittest.TestCase):
    """A plan may create and resize its own wall; a stranger label may not."""

    def test_create_then_resize_in_one_plan(self):
        resize = {
            "op": pwall.PLANAR_WALL_RESIZE_OP,
            "feature": "wall",
            "length": 120.0,
            "width": 80.0,
        }
        model = empty_sheetmetal_model()
        pwall.validate_plan(model, [create_op(), resize])
        with self.assertRaises(ValueError):
            pwall.validate_plan(model, [resize])
        with self.assertRaises(ValueError):
            pwall.validate_plan(model, [create_op(), dict(resize, feature="other")])


class EvidenceTest(unittest.TestCase):
    """Review finding: missing or misdirected evidence must not look verified."""

    def test_missing_or_misdirected_evidence_is_not_verified(self):
        opposite = {
            "u": {"min": 0.0, "max": 100.0},
            "v": {"min": 0.0, "max": 60.0},
            "n": {"min": -1.0, "max": 0.0},
        }
        offset = {
            "u": {"min": 5.0, "max": 105.0},
            "v": {"min": 0.0, "max": 60.0},
            "n": {"min": 0.0, "max": 1.0},
        }
        cases = {
            "growth on the opposite side": create_result(envelope=opposite),
            "origin offset": create_result(envelope=offset),
            "no direction": create_result(direction=None),
            "unknown direction": create_result(direction="up"),
            "no volume": create_result(volume_mm3=None),
            "wrong volume": create_result(volume_mm3=0.0),
            "gauge not read back": create_result(
                thickness_verified=False, thickness_measured_mm=None, thickness_body_code=-1
            ),
            "gauge disagrees": create_result(thickness_measured_mm=3.71),
            "no sheetmetal body": create_result(sheetmetal_body=False),
            "no feature id": create_result(feature_id=None),
        }
        for name, result in cases.items():
            with self.subTest(case=name):
                self.assertFalse(pwall.result_projection(result)["verified"])

        negative = create_result(
            direction="negative",
            envelope={
                "u": {"min": 0.0, "max": 100.0},
                "v": {"min": 0.0, "max": 60.0},
                "n": {"min": -1.0, "max": 0.0},
            },
        )
        projection = pwall.result_projection(negative)
        self.assertTrue(projection["verified"], projection["problems"])

        missing_volume = pwall.result_projection(create_result(volume_mm3=None))
        self.assertTrue(any("measured volume" in item for item in missing_volume["problems"]))

    def test_saved_gauge_is_rechecked_on_resize(self):
        result = create_result(
            op=pwall.PLANAR_WALL_RESIZE_OP,
            length=120.0,
            width=80.0,
            volume_mm3=9600.0,
            feature_id_before=49,
            thickness_loaded_mm=1.0,
            envelope={
                "u": {"min": 0.0, "max": 120.0},
                "v": {"min": 0.0, "max": 80.0},
                "n": {"min": 0.0, "max": 1.0},
            },
        )
        self.assertTrue(pwall.result_projection(result)["verified"])
        stale = pwall.result_projection(dict(result, thickness_loaded_mm=3.71))
        self.assertFalse(stale["verified"])
        self.assertTrue(any("saved wall carried" in item for item in stale["problems"]))


class CounterexampleTest(unittest.TestCase):
    """Review finding (2026-11-04): absent or non-finite evidence read as verified."""

    def test_missing_size_is_its_own_problem(self):
        cases = {
            "no length": create_result(length=None),
            "no width": create_result(width=None),
            "no thickness": create_result(thickness=None),
            # The review case that carried neither a size nor a shape.
            "no size and no shape": create_result(
                length=None,
                width=None,
                thickness=None,
                volume_mm3=None,
                frame=None,
                envelope=None,
            ),
        }
        for name, result in cases.items():
            with self.subTest(case=name):
                projection = pwall.result_projection(result)
                self.assertFalse(projection["verified"])
                self.assertTrue(
                    any("no usable" in item for item in projection["problems"]),
                    projection["problems"],
                )
        # An unknown length cannot make the wall look square either.
        self.assertFalse(pwall.result_projection(create_result(length=None))["square"])
        self.assertTrue(pwall.result_projection(create_result())["verified"])

    def test_missing_saved_gauge_is_its_own_problem(self):
        result = create_result(
            op=pwall.PLANAR_WALL_RESIZE_OP,
            length=120.0,
            width=80.0,
            volume_mm3=9600.0,
            feature_id_before=49,
            envelope={
                "u": {"min": 0.0, "max": 120.0},
                "v": {"min": 0.0, "max": 80.0},
                "n": {"min": 0.0, "max": 1.0},
            },
        )
        projection = pwall.result_projection(result)
        self.assertFalse(projection["verified"])
        self.assertIsNone(projection["thickness_loaded_mm"])
        self.assertTrue(any("saved wall" in item for item in projection["problems"]))

        # The same result with the saved gauge read back stays verified.
        read_back = pwall.result_projection(dict(result, thickness_loaded_mm=1.0))
        self.assertTrue(read_back["verified"], read_back["problems"])

    def test_non_finite_evidence_is_rejected(self):
        not_a_number = float("nan")
        infinite = float("inf")
        cases = {
            "nan volume": (
                create_result(volume_mm3=not_a_number),
                "measured volume",
            ),
            "nan gauge": (
                create_result(thickness_measured_mm=not_a_number),
                "verified gauge",
            ),
            "infinite length": (
                create_result(length=infinite),
                "no usable length",
            ),
            "nan envelope": (
                create_result(
                    envelope={
                        "u": {"min": 0.0, "max": not_a_number},
                        "v": {"min": 0.0, "max": 60.0},
                        "n": {"min": 0.0, "max": 1.0},
                    }
                ),
                "not finite",
            ),
            "nan frame": (
                create_result(frame=dict(FRAME_XY, normal=[0.0, 0.0, not_a_number])),
                "not a finite vector",
            ),
        }
        for name, (result, expected) in cases.items():
            with self.subTest(case=name):
                projection = pwall.result_projection(result)
                self.assertFalse(projection["verified"])
                self.assertTrue(
                    any(expected in item for item in projection["problems"]),
                    projection["problems"],
                )
        # A non-finite measurement is published as absent, never as a number.
        nan_volume = pwall.result_projection(create_result(volume_mm3=not_a_number))
        self.assertIsNone(nan_volume["volume_mm3"])
        nan_gauge = pwall.result_projection(create_result(thickness_measured_mm=not_a_number))
        self.assertIsNone(nan_gauge["thickness_measured_mm"])


class OriginTest(unittest.TestCase):
    """R10: origin=[u0,v0] moves the rectangle and never the plane frame."""

    offset_envelope = {
        "u": {"min": -92.5, "max": 92.5},
        "v": {"min": -116.0, "max": 116.0},
        "n": {"min": 0.0, "max": 1.0},
    }

    def test_offset_wall_is_verified_on_its_moved_envelope(self):
        result = create_result(
            length=185.0,
            width=232.0,
            origin=[-92.5, -116.0],
            volume_mm3=42920.0,
            envelope=self.offset_envelope,
        )
        projection = pwall.result_projection(result)
        self.assertEqual(projection["origin"], [-92.5, -116.0])
        self.assertTrue(projection["verified"], projection["problems"])

    def test_the_same_envelope_at_origin_zero_is_refused(self):
        # An executor that ignores the origin still reports the frame envelope
        # starting at 0, so the verdict has to fail instead of accepting the
        # wall at the wrong place (or the request as echoing itself).
        result = create_result(
            length=185.0,
            width=232.0,
            volume_mm3=42920.0,
            envelope=self.offset_envelope,
        )
        projection = pwall.result_projection(result)
        self.assertFalse(projection["verified"])
        self.assertTrue(any("envelope u" in problem for problem in projection["problems"]))

    def test_expected_intervals_move_with_the_origin(self):
        intervals = pwall.expected_intervals(185.0, 232.0, 1.0, "positive", (-92.5, -116.0))
        self.assertEqual(intervals["u"], (-92.5, 92.5))
        self.assertEqual(intervals["v"], (-116.0, 116.0))
        self.assertEqual(intervals["n"], (0.0, 1.0))
        self.assertIsNone(
            pwall.envelope_problem(
                FRAME_XY,
                self.offset_envelope,
                185.0,
                232.0,
                1.0,
                "positive",
                origin=(-92.5, -116.0),
            )
        )
        self.assertIn(
            "envelope u",
            pwall.envelope_problem(FRAME_XY, self.offset_envelope, 185.0, 232.0, 1.0) or "",
        )

    def test_malformed_origin_is_a_problem(self):
        for origin in ([1.0, 2.0, 3.0], ["a", 0.0], [float("nan"), 0.0], [True, 0.0]):
            with self.subTest(origin=origin):
                projection = pwall.result_projection(create_result(origin=origin))
                self.assertFalse(projection["verified"])
                self.assertTrue(any("origin" in item for item in projection["problems"]))

    def test_old_result_without_origin_starts_at_zero(self):
        projection = pwall.result_projection(create_result())
        self.assertEqual(projection["origin"], [0.0, 0.0])
        self.assertTrue(projection["verified"], projection["problems"])

    def test_schema_accepts_and_bounds_the_origin(self):
        valid = create_op(origin=[-92.5, -116.0])
        self.assertEqual(validate_operations([valid])[0]["origin"], [-92.5, -116.0])
        self.assertEqual(validate_operations([create_op()])[0]["origin"], [0.0, 0.0])
        for origin in (
            [1.0],
            [1.0, 2.0, 3.0],
            ["a", 0.0],
            [True, 0.0],
            [float("inf"), 0.0],
            [1_000_001.0, 0.0],
        ):
            with self.subTest(origin=origin):
                with self.assertRaises(ValueError):
                    validate_operations([create_op(origin=origin)])
        # A dictionary plane already carries a world-coordinate origin.
        plane = {"reference": {"kind": "datum_plane", "axis": "z", "offset": 0}}
        validate_operations([create_op(plane=plane)])
        with self.assertRaises(ValueError):
            validate_operations([create_op(plane=plane, origin=[1.0, 0.0])])

    def test_server_exposes_the_origin(self):
        source = SERVER.read_text(encoding="utf-8")
        self.assertIn("origin: list[float] | None = None", source)
        self.assertIn('"origin": list(origin) if origin is not None else [0.0, 0.0]', source)

    def test_native_records_and_checks_the_origin(self):
        source = NATIVE_WALL.read_text(encoding="utf-8")
        self.assertIn('op.value("origin", J::array({0.0, 0.0}))', source)
        self.assertIn('{"origin", J::array({u0, v0})}', source)
        self.assertIn('negative, "created", u0, v0)', source)
        self.assertIn('negative, "resized", u0, v0)', source)

    def test_native_resize_maps_the_recorded_frame(self):
        # A coordinate dimension is a distance from a section axis, so the resize
        # must resolve the corner side through the section location matrix
        # instead of scaling the absolute values.
        source = NATIVE_WALL.read_text(encoding="utf-8")
        self.assertIn("ProSectionLocationGet(section, loc)", source)
        self.assertIn("corner_u[4][2]", source)
        self.assertIn("fabs(resized_coordinate)", source)
        self.assertIn("is not part of the recorded rectangle", source)


def validation_block(**overrides) -> dict:
    block = {
        "status": "verified",
        "source": "api",
        "value_mm": 1.0,
        "reason": None,
        "context": "current_plan",
    }
    block.update(overrides)
    return block


RESIZE_ENVELOPE = {
    "u": {"min": 0.0, "max": 120.0},
    "v": {"min": 0.0, "max": 80.0},
    "n": {"min": 0.0, "max": 1.0},
}


def resized_result(**overrides) -> dict:
    result = {
        "op": pwall.PLANAR_WALL_RESIZE_OP,
        "length": 120.0,
        "width": 80.0,
        "volume_mm3": 9600.0,
        "feature_id_before": 49,
        "thickness_loaded_mm": 1.0,
        "envelope": RESIZE_ENVELOPE,
    }
    result.update(overrides)
    return create_result(**result)


class GaugeReceiptTest(unittest.TestCase):
    """FEAT-058/R03: the gauge receipt stays readable and never invents evidence."""

    def test_verified_receipt_is_published_with_both_contexts(self):
        create = pwall.result_projection(create_result(thickness_validation=validation_block()))
        self.assertTrue(create["verified"], create["problems"])
        self.assertEqual(
            create["thickness_validation"],
            {
                "status": "verified",
                "source": "api",
                "value_mm": 1.0,
                "reason": None,
                "context": "current_plan",
            },
        )

        resize = pwall.result_projection(
            resized_result(
                thickness_validation=validation_block(),
                thickness_loaded_validation=validation_block(context="saved_loaded"),
            )
        )
        self.assertTrue(resize["verified"], resize["problems"])
        self.assertEqual(resize["thickness_validation"]["context"], "current_plan")
        self.assertEqual(
            resize["thickness_loaded_validation"],
            {
                "status": "verified",
                "source": "api",
                "value_mm": 1.0,
                "reason": None,
                "context": "saved_loaded",
            },
        )

    def test_missing_api_is_unverified_and_carries_no_value(self):
        projection = pwall.result_projection(
            create_result(
                thickness_measured_mm=None,
                thickness_verified=False,
                thickness_body_code=-1,
                thickness_validation=validation_block(
                    status="unverified",
                    source="missing_api",
                    value_mm=None,
                    reason="thickness_api_unavailable",
                ),
            )
        )
        self.assertFalse(projection["verified"])
        self.assertIsNone(projection["thickness_measured_mm"])
        self.assertEqual(
            projection["thickness_validation"],
            {
                "status": "unverified",
                "source": "missing_api",
                "value_mm": None,
                "reason": "thickness_api_unavailable",
                "context": "current_plan",
            },
        )
        self.assertTrue(
            any("thickness_api_unavailable" in item for item in projection["problems"]),
            projection["problems"],
        )

    def test_api_failure_is_unavailable_not_missing_api(self):
        projection = pwall.result_projection(
            create_result(
                thickness_measured_mm=None,
                thickness_verified=False,
                thickness_body_code=-2,
                thickness_validation=validation_block(
                    status="unavailable",
                    source="api",
                    value_mm=None,
                    reason="thickness_api_query_failed",
                ),
            )
        )
        self.assertFalse(projection["verified"])
        self.assertEqual(projection["thickness_validation"]["source"], "api")
        self.assertEqual(projection["thickness_validation"]["status"], "unavailable")
        self.assertIsNone(projection["thickness_validation"]["value_mm"])

    def test_ambiguous_material_body_is_unavailable(self):
        projection = pwall.result_projection(
            create_result(
                thickness_measured_mm=None,
                thickness_verified=False,
                material_bodies=2,
                thickness_validation=validation_block(
                    status="unavailable",
                    source="not_measured",
                    value_mm=None,
                    reason="thickness_material_body_not_unique",
                ),
            )
        )
        self.assertFalse(projection["verified"])
        self.assertEqual(projection["thickness_validation"]["source"], "not_measured")
        self.assertIsNone(projection["thickness_validation"]["value_mm"])

    def test_disagreeing_reading_is_a_mismatch(self):
        projection = pwall.result_projection(
            create_result(
                thickness_measured_mm=2.0,
                thickness_validation=validation_block(
                    status="mismatch", value_mm=2.0, reason="thickness_measured_mismatch"
                ),
            )
        )
        self.assertFalse(projection["verified"])
        self.assertEqual(projection["thickness_validation"]["status"], "mismatch")
        self.assertEqual(projection["thickness_validation"]["value_mm"], 2.0)

    def test_non_finite_or_unitless_values_are_degraded(self):
        cases = {
            "nan": (float("nan"), "thickness_validation_non_finite_value"),
            "inf": (float("inf"), "thickness_validation_non_finite_value"),
            "unit unknown": ("1.0", "thickness_validation_invalid_value"),
        }
        for name, (value, expected) in cases.items():
            with self.subTest(case=name):
                projection = pwall.result_projection(
                    create_result(thickness_validation=validation_block(value_mm=value))
                )
                self.assertFalse(projection["verified"])
                block = projection["thickness_validation"]
                self.assertEqual(block["status"], "unavailable")
                self.assertEqual(block["source"], "not_measured")
                self.assertIsNone(block["value_mm"])
                self.assertEqual(block["reason"], expected)

        unknown_source = pwall.result_projection(
            create_result(thickness_validation=validation_block(source="unitless", value_mm=None))
        )
        self.assertFalse(unknown_source["verified"])
        self.assertEqual(
            unknown_source["thickness_validation"]["reason"],
            "thickness_validation_unknown_source",
        )

    def test_malformed_receipts_are_degraded_without_a_value(self):
        cases = {
            "not an object": "verified",
            "unknown status": validation_block(status="ok"),
            "unknown source": validation_block(source="caliper"),
            "wrong context": validation_block(context="saved_loaded"),
            "verified without a value": validation_block(value_mm=None),
            "verified without the api": validation_block(source="not_measured"),
            "not verified without a reason": validation_block(
                status="unavailable", value_mm=None, reason=None
            ),
        }
        for name, raw in cases.items():
            with self.subTest(case=name):
                projection = pwall.result_projection(create_result(thickness_validation=raw))
                self.assertFalse(projection["verified"])
                block = projection["thickness_validation"]
                self.assertEqual(block["status"], "unavailable")
                self.assertEqual(block["source"], "not_measured")
                self.assertIsNone(block["value_mm"])
                self.assertEqual(block["context"], "current_plan")
                self.assertTrue(
                    str(block["reason"]).startswith("thickness_validation_"),
                    block["reason"],
                )

    def test_missing_saved_receipt_read_back_is_not_verified(self):
        projection = pwall.result_projection(
            resized_result(
                thickness_loaded_mm=None,
                thickness_loaded_validation=validation_block(
                    status="unavailable",
                    source="api",
                    value_mm=None,
                    reason="thickness_api_query_failed",
                    context="saved_loaded",
                ),
            )
        )
        self.assertFalse(projection["verified"])
        self.assertEqual(projection["thickness_loaded_validation"]["status"], "unavailable")
        self.assertTrue(
            any("saved wall" in item for item in projection["problems"]),
            projection["problems"],
        )

    def test_resize_does_not_inherit_the_create_receipt(self):
        create = create_result(thickness_validation=validation_block())
        self.assertTrue(pwall.result_projection(create)["verified"])

        resize = resized_result(
            thickness_validation=validation_block(),
            thickness_loaded_validation=validation_block(
                status="unverified",
                source="missing_api",
                value_mm=None,
                reason="thickness_api_unavailable",
                context="saved_loaded",
            ),
        )
        projection = pwall.result_projection(resize)
        self.assertEqual(projection["thickness_validation"]["status"], "verified")
        self.assertEqual(projection["thickness_loaded_validation"]["status"], "unverified")
        self.assertFalse(projection["verified"])

        # Copying the create receipt into the loaded slot is refused by its
        # context, so a create-stage result cannot stand in for the saved read.
        borrowed = dict(resize, thickness_loaded_validation=validation_block())
        projection = pwall.result_projection(borrowed)
        self.assertFalse(projection["verified"])
        self.assertEqual(
            projection["thickness_loaded_validation"]["reason"],
            "thickness_validation_current_plan_without_create",
        )

    def test_old_executor_without_receipts_is_unchanged(self):
        projection = pwall.result_projection(create_result())
        self.assertTrue(projection["verified"], projection["problems"])
        self.assertNotIn("thickness_validation", projection)

        resized = pwall.result_projection(resized_result())
        self.assertTrue(resized["verified"], resized["problems"])
        self.assertNotIn("thickness_loaded_validation", resized)

    def test_compact_poll_keeps_the_receipts(self):
        import bridge

        result = {
            "operations": [
                resized_result(
                    thickness_validation=validation_block(),
                    thickness_loaded_validation=validation_block(context="saved_loaded"),
                )
            ]
        }
        pwall.annotate_result(result)
        summary = bridge.compact_job({"job_id": "j", "status": "succeeded", "result": result})
        planar = summary["result"]["planar_wall"]
        self.assertEqual(planar["thickness_validation"]["status"], "verified")
        self.assertEqual(planar["thickness_loaded_validation"]["context"], "saved_loaded")

    def test_geometry_span_verifies_without_the_api_boolean(self):
        projection = pwall.result_projection(
            create_result(
                thickness_measured_mm=None,
                thickness_verified=False,
                thickness_body_code=-1,
                thickness_geometry_span_mm=1.0,
                thickness_validation=validation_block(source="geometry_normal_span"),
            )
        )
        self.assertTrue(projection["verified"], projection["problems"])
        self.assertEqual(projection["thickness_validation"]["source"], "geometry_normal_span")
        # The API-specific fields stay absent instead of being rewritten as if
        # the body API had answered.
        self.assertIsNone(projection["thickness_measured_mm"])
        self.assertFalse(projection["thickness_verified"])
        self.assertEqual(projection["thickness_api_scope"], "body_api_readback_only")
        self.assertEqual(projection["thickness_api_reason"], "thickness_api_unavailable")
        self.assertEqual(projection["thickness_fallback_source"], "geometry_normal_span")

    def test_api_failure_has_no_geometry_fallback(self):
        projection = pwall.result_projection(
            create_result(
                thickness_measured_mm=None,
                thickness_verified=False,
                thickness_body_code=-2,
                thickness_validation=validation_block(
                    status="unavailable",
                    source="api",
                    value_mm=None,
                    reason="thickness_api_query_failed",
                ),
            )
        )
        self.assertFalse(projection["verified"])
        self.assertEqual(projection["thickness_api_reason"], "thickness_api_query_failed")
        self.assertIsNone(projection["thickness_fallback_source"])

    def test_malformed_receipt_does_not_claim_missing_api_or_fallback(self):
        projection = pwall.result_projection(create_result(thickness_validation="bad"))
        self.assertFalse(projection["verified"])
        self.assertEqual(projection["thickness_api_reason"], "unknown")
        self.assertIsNone(projection["thickness_fallback_source"])

    def test_legacy_receipt_has_no_new_api_explanation(self):
        projection = pwall.result_projection(create_result())
        for field in ("thickness_api_scope", "thickness_api_reason", "thickness_fallback_source"):
            self.assertNotIn(field, projection)

    def test_resize_explains_loaded_geometry_fallback_separately(self):
        projection = pwall.result_projection(
            resized_result(
                thickness_measured_mm=None,
                thickness_verified=False,
                thickness_loaded_mm=None,
                thickness_body_code=-1,
                thickness_geometry_span_mm=1.0,
                thickness_validation=validation_block(source="geometry_normal_span"),
                thickness_loaded_validation=validation_block(
                    source="geometry_normal_span", context="saved_loaded"
                ),
            )
        )
        self.assertTrue(projection["verified"], projection["problems"])
        self.assertIsNone(projection["thickness_loaded_mm"])
        self.assertEqual(projection["thickness_loaded_api_scope"], "body_api_readback_only")
        self.assertEqual(projection["thickness_loaded_api_reason"], "thickness_api_unavailable")
        self.assertEqual(projection["thickness_loaded_fallback_source"], "geometry_normal_span")

    def test_public_tool_descriptions_name_the_gauge_verdict(self):
        source = SERVER.read_text(encoding="utf-8")
        self.assertIn("thickness_validation is the", source)
        self.assertIn("thickness_loaded_validation must verify", source)

    def test_geometry_span_mismatch_is_not_verified(self):
        projection = pwall.result_projection(
            create_result(
                thickness_measured_mm=None,
                thickness_verified=False,
                thickness_geometry_span_mm=2.0,
                thickness_validation=validation_block(
                    status="mismatch",
                    source="geometry_normal_span",
                    value_mm=2.0,
                    reason="thickness_measured_mismatch",
                ),
            )
        )
        self.assertFalse(projection["verified"])
        self.assertEqual(projection["thickness_validation"]["status"], "mismatch")
        self.assertEqual(projection["thickness_validation"]["value_mm"], 2.0)

    def test_same_plan_resize_accepts_the_current_plan_context(self):
        projection = pwall.result_projection(
            resized_result(
                wall_created_this_job=True,
                thickness_measured_mm=None,
                thickness_verified=False,
                thickness_loaded_mm=None,
                thickness_geometry_span_mm=1.0,
                thickness_validation=validation_block(source="geometry_normal_span"),
                thickness_loaded_validation=validation_block(
                    source="geometry_normal_span", context="current_plan"
                ),
            )
        )
        self.assertTrue(projection["verified"], projection["problems"])
        self.assertEqual(projection["thickness_loaded_validation"]["context"], "current_plan")
        self.assertIsNone(projection["thickness_loaded_mm"])

    def test_native_geometry_fallback_is_gated(self):
        wall = NATIVE_WALL.read_text(encoding="utf-8", errors="replace")
        self.assertIn('bodies.gauge_source != "missing_api"', wall)
        self.assertIn("planar_walls_created_this_job", wall)
        self.assertIn('const char *loaded_context = created_this_job ? "current_plan"', wall)
        for gate in (
            "thickness_geometry_has_downstream_features",
            "thickness_geometry_frame_not_axis_aligned",
            "thickness_geometry_span_unavailable",
            "thickness_material_body_not_unique",
        ):
            with self.subTest(gate=gate):
                self.assertIn(gate, wall)

    def test_native_publishes_one_receipt_per_operation(self):
        wall = NATIVE_WALL.read_text(encoding="utf-8", errors="replace")
        create_call = 'planar_wall_thickness_validation(bodies, thickness, "current_plan")'
        loaded_call = "planar_wall_thickness_validation(loaded, thickness, loaded_context)"
        self.assertEqual(wall.count(create_call), 2, "create and resize each publish a receipt")
        self.assertEqual(wall.count(loaded_call), 1)
        self.assertIn('"thickness_loaded_validation"', wall)
        for reason in (
            "thickness_api_unavailable",
            "thickness_api_query_failed",
            "thickness_material_body_not_unique",
            "thickness_value_not_finite",
            "thickness_measured_mismatch",
        ):
            with self.subTest(reason=reason):
                self.assertIn(reason, wall)


class OriginCrossingResizeTest(unittest.TestCase):
    """H01: a resize that moves a corner across the sketch origin.

    A coordinate dimension is a distance to a section axis, so the 2026-11-07
    Creo 10 report at origin [-92.5,-116] solved 185x232 -> 100x60 as
    v [-116,56] (17200 mm3) and was refused. The native resize now writes each
    target coordinate with the dimension's own direction, measured from the
    current value and point, instead of writing its absolute value.
    """

    def test_native_resize_writes_the_measured_dimension_side(self):
        wall = NATIVE_WALL.read_text(encoding="utf-8", errors="replace")
        for token in (
            "planar_wall_dimension_side",
            "value * coordinate",
            "side * resized_coordinate",
            "fabs(fabs(current) - expected)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, wall)

    def test_volume_guard_reports_the_measured_envelope(self):
        wall = NATIVE_WALL.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            'planar_wall_require_volume(measured, length, width, thickness, "resized", &envelope)',
            wall,
        )
        self.assertIn("measured u=[", wall)

    def test_matrix_expects_the_short_side_after_crossing(self):
        from tools.test_planar_wall_origin_resize import (
            CASES,
            expected_bbox,
            expected_envelope,
            offline_checks,
        )

        self.assertTrue(offline_checks()["crossing_case_is_100x60_not_100x172"])
        case = next(item for item in CASES if item[0] == "xy_neg_cross")
        self.assertEqual(
            expected_bbox(case[1], case[2], case[3], 100.0, 60.0),
            [[-92.5, -116.0, 0.0], [7.5, -56.0, 1.0]],
        )
        self.assertEqual(
            expected_envelope(case[1], case[2], case[3], 100.0, 60.0),
            {"u": [-92.5, 7.5], "v": [-116.0, -56.0], "n": [0.0, 1.0]},
        )
        # 100 x (116 + 56) is the wrong-branch reading the report measured.
        self.assertNotEqual(17200.0, 100.0 * 60.0)


class RuntimeIdentityTest(unittest.TestCase):
    """Review finding (2026-11-04): the planar wall sources missed the identity."""

    def test_planar_wall_sources_participate_in_runtime_identity(self):
        import server

        fingerprints = server._source_fingerprints()
        for name in (
            "src/creo_mechdog/native_planar_wall.py",
            "native/planar_wall.cpp",
            "native/planar_wall.h",
        ):
            with self.subTest(name=name):
                self.assertIn(name, server._SOURCE_NAMES)
                self.assertEqual(len(fingerprints[name]), 64)


if __name__ == "__main__":
    unittest.main()
