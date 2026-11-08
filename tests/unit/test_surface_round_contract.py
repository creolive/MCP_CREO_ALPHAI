"""DEV-074/H08 surface_round contract tests.

Offline only: the Python admission surface, capability/reference registration,
compact projection keys and the native source route are locked here. No Creo
session is opened and no native feature is claimed to have been built; the
2026-11-08 H08 hardware probe is referenced as evidence, not replayed.
"""

import asyncio
import unittest
from pathlib import Path

import server
from creo_mechdog.capabilities import (
    REGISTERED_OPERATIONS,
    UNAVAILABLE_OPERATIONS,
    families,
    require_available,
)
from creo_mechdog.job_projection import SURFACE_ROUND_KEYS, compact_operation
from creo_mechdog.references import reference_capabilities
from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native" / "surface_round.cpp"
GENERIC = ROOT / "native" / "generic.cpp"


def surface_round(**overrides):
    operation = {
        "op": "surface_round",
        "label": "quilt_edge",
        "target": {"kind": "quilt", "id": 70},
        "references": [
            {"surfaces": [{"kind": "surface", "id": 68}, {"kind": "surface", "id": 66}]}
        ],
        "radius": 3.0,
    }
    operation.update(overrides)
    return operation


class SurfaceRoundSchemaTests(unittest.TestCase):
    def test_accepts_two_member_faces_of_one_quilt(self):
        validated = validate_operations([surface_round()])
        self.assertEqual(validated[0]["op"], "surface_round")
        self.assertEqual(validated[0]["radius"], 3.0)
        self.assertEqual(
            validated[0]["references"],
            [{"surfaces": [{"kind": "surface", "id": 68}, {"kind": "surface", "id": 66}]}],
        )

    def test_accepts_a_quilt_feature_label_target(self):
        validated = validate_operations(
            [surface_round(target={"kind": "quilt_feature", "label": "quilt_fill"})]
        )
        self.assertEqual(validated[0]["target"]["kind"], "quilt_feature")

    def test_accepts_a_non_adjacent_pair_because_the_kernel_decides(self):
        # H08 measured a non-adjacent pair failing regeneration with a rollback.
        # The schema deliberately cannot prove adjacency from ids alone, so the
        # request is admitted and the kernel owns the verdict.
        validated = validate_operations(
            [
                surface_round(
                    references=[
                        {
                            "surfaces": [
                                {"kind": "surface", "id": 68},
                                {"kind": "surface", "id": 64},
                            ]
                        }
                    ]
                )
            ]
        )
        self.assertEqual(validated[0]["references"][0]["surfaces"][1]["id"], 64)

    def test_rejects_a_target_that_is_not_a_quilt(self):
        for target in (
            {"kind": "surface", "id": 68},
            {"kind": "body", "id": 1},
            {"kind": "datum_plane", "label": "FRONT"},
            {"kind": "quilt", "id": -1},
            {"kind": "quilt", "label": "wrong_spelling"},
            {"id": 70},
        ):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    validate_operations([surface_round(target=target)])

    def test_rejects_an_invalid_radius(self):
        for radius in (0, -0.5, float("inf"), float("nan"), True, "3", None):
            with self.subTest(radius=radius):
                operation = surface_round()
                if radius is None:
                    operation.pop("radius")
                else:
                    operation["radius"] = radius
                with self.assertRaises(ValueError):
                    validate_operations([operation])

    def test_rejects_more_or_fewer_than_two_faces(self):
        for faces in (
            [{"kind": "surface", "id": 68}],
            [],
            [
                {"kind": "surface", "id": 68},
                {"kind": "surface", "id": 66},
                {"kind": "surface", "id": 64},
            ],
            [
                {"kind": "surface", "id": 68},
                {"kind": "surface", "id": 68},
            ],
        ):
            with self.subTest(faces=faces):
                with self.assertRaises(ValueError):
                    validate_operations([surface_round(references=[{"surfaces": faces}])])

    def test_rejects_a_face_that_is_not_a_surface_reference(self):
        for face in (
            {"kind": "edge", "id": 54},
            {"kind": "plane", "id": 53},
            {"kind": "body", "id": 52},
            {"kind": "surface", "label": "fill"},
            {"kind": "surface", "id": -2},
            {"kind": "surface", "id": True},
        ):
            with self.subTest(face=face):
                with self.assertRaises(ValueError):
                    validate_operations(
                        [
                            surface_round(
                                references=[{"surfaces": [{"kind": "surface", "id": 68}, face]}]
                            )
                        ]
                    )

    def test_rejects_multiple_sets_edge_chains_and_transitions(self):
        pair = [{"kind": "surface", "id": 68}, {"kind": "surface", "id": 66}]
        for references in (
            [{"surfaces": pair}, {"surfaces": pair}],
            [{"edge": {"kind": "edge", "id": 54}}],
            [{"surfaces": pair, "transitions": {}}],
        ):
            with self.subTest(references=references):
                with self.assertRaises(ValueError):
                    validate_operations([surface_round(references=references)])

    def test_rejects_fields_that_would_mean_a_variable_or_full_round(self):
        for patch in (
            {"full_round": True},
            {"radius2": 4.0},
            {"transitions": {}},
            {"chordal": True},
        ):
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):
                    validate_operations([surface_round(**patch)])


class SurfaceRoundRegistrationTests(unittest.TestCase):
    def test_the_operation_and_tool_are_published(self):
        self.assertIn("surface_round", REGISTERED_OPERATIONS)
        self.assertNotIn("surface_round", UNAVAILABLE_OPERATIONS)
        tools = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
        self.assertIn("creo_surface_round", tools)
        self.assertEqual(len(tools), 105)

    def test_require_available_admits_the_operation(self):
        require_available(validate_operations([surface_round()]))

    def test_capabilities_publish_the_constant_radius_boundary(self):
        surface_chain = families()["surface_chain"]
        self.assertIn("creo_surface_round", surface_chain["tools"])
        self.assertIn("round the edge shared by two member faces", surface_chain["scope"])
        round_family = families()["surface_round"]
        self.assertEqual(round_family["tool"], "creo_surface_round")
        self.assertIn("constant", round_family["scope"])
        self.assertIn("kernel decides adjacency", round_family["limits"])

    def test_reference_capabilities_validate_with_the_operation(self):
        example = reference_capabilities()["by_tool"]["creo_surface_round"]
        validated = validate_operations(
            [
                surface_round(
                    target=example["target"],
                    references=example["references"],
                    radius=example["radius"],
                )
            ]
        )
        self.assertEqual(validated[0]["radius"], 3.0)
        self.assertIn("kernel decides it", example["adjacency"])


class SurfaceRoundProjectionTests(unittest.TestCase):
    def test_compact_projection_keeps_every_measurement_and_its_status(self):
        record = {
            "op": "surface_round",
            "succeeded": True,
            "execution_status": "succeeded",
            "effect_status": "committed",
            "quilt_id": 70,
            "face_ids": [68, 66],
            "radius": 3.0,
            "face_count_before": 4,
            "face_count": 5,
            "area_before_mm2": 1200.0,
            "area_mm2": 1187.1238898038469,
            "closed": False,
            "has_solid": False,
            "solid_surface_count": 0,
            "unrelated": "dropped",
        }
        projected = compact_operation(record)
        for key in SURFACE_ROUND_KEYS:
            if key in record:
                self.assertIn(key, projected)
        self.assertNotIn("unrelated", projected)
        self.assertEqual(projected["face_count"], 5)
        self.assertEqual(projected["area_mm2"], 1187.1238898038469)


class SurfaceRoundNativeRouteTests(unittest.TestCase):
    def test_the_native_route_is_the_documented_face_pair_round(self):
        native = NATIVE.read_text(encoding="utf-8")
        for lock in (
            "PRO_FEAT_ROUND",
            "PRO_ROUND_TYPE_CONSTANT",
            "PRO_ROUND_REF_SURF_SURF",
            "PRO_E_RNDCH_REFERENCE_SURFACE1",
            "PRO_E_RNDCH_REFERENCE_SURFACE2",
            "PRO_E_RNDCH_ATTACH_TYPE, PRO_ROUND_ATTACHED",
            "PRO_E_RNDCH_LEG_VALUE",
        ):
            self.assertIn(lock, native)

    def test_the_native_route_measures_the_quilt_instead_of_echoing_the_request(self):
        native = NATIVE.read_text(encoding="utf-8")
        for lock in (
            "ProQuiltSurfaceVisit",
            "quilt_area_native",
            "quilt_closed_native",
            "area_fields_json",
            "ProFeatureStatusGet",
            "not a member of quilt",
            "stage_operation_result",
        ):
            self.assertIn(lock, native)

    def test_the_native_route_is_wired_once_and_rolls_back_with_the_job(self):
        generic = GENERIC.read_text(encoding="utf-8")
        self.assertIn('#include "surface_round.cpp"', generic)
        self.assertIn('kind == "surface_round"', generic)
        self.assertIn("generic_surface_round(op)", generic)
        # The job-level checkpoint/rollback path is shared by every mutating
        # operation; this route adds no second rollback mechanism.
        self.assertIn("surface_round_regeneration", NATIVE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
