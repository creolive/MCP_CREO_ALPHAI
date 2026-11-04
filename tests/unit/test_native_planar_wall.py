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
    def test_resize_keeps_identity_and_reports_shift(self):
        result = create_result(
            op=pwall.PLANAR_WALL_RESIZE_OP,
            length=120.0,
            width=80.0,
            volume_mm3=9600.0,
            feature_id_before=49,
            feature_id=49,
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


if __name__ == "__main__":
    unittest.main()
