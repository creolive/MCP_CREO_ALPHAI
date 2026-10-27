"""BUG-084 T03: geometry IDs and plane selectors have distinct identities."""

import unittest
from unittest.mock import patch

import bridge
import generic_bridge
import server
from creo_mechdog.schema import validate_operations


def sketch(reference: dict) -> dict:
    return {
        "op": "sketch",
        "label": "profile",
        "plane": {"reference": reference, "u_axis": [0, 0, 1]},
        "entities": [{"type": "circle", "name": "ring", "center": [0, 0], "radius": 2}],
    }


class PlaneReferenceValidation(unittest.TestCase):
    def test_both_pure_z_directions_remain_available_for_native_plane_check(self):
        for direction in (-1, 1):
            operation = sketch({"kind": "datum_plane", "id": 163})
            operation["plane"]["u_axis"] = [0, 0, direction]
            with self.subTest(direction=direction):
                self.assertEqual(
                    validate_operations([operation])[0]["plane"]["u_axis"],
                    [0, 0, direction],
                )

    def test_compact_job_preserves_the_native_resolved_frame(self):
        frame = {
            "op": "sketch",
            "label": "profile",
            "surface_id": 163,
            "origin": [0, 0, 0],
            "normal": [1, 0, 0],
            "u_axis": [0, 0, -1],
            "v_axis": [0, 1, 0],
            "succeeded": True,
        }
        compact = bridge.compact_job(
            {
                "job_id": "j",
                "operations": [sketch({"kind": "datum_plane", "id": 163})],
                "result": {"operations": [frame]},
            }
        )
        self.assertEqual(compact["result"]["operations"], [frame])

    def test_explicit_geometry_id_and_feature_label_survive_without_reinterpretation(self):
        for reference in (
            {"kind": "datum_plane", "id": 163},
            {"kind": "plane", "id": 163},
            {"kind": "surface", "id": 163},
            {"kind": "datum_feature", "label": "right_plane"},
        ):
            with self.subTest(reference=reference):
                self.assertEqual(
                    validate_operations([sketch(reference)])[0]["plane"]["reference"],
                    reference,
                )

    def test_id_and_each_filter_are_mutually_exclusive_even_at_default_values(self):
        for kind in ("plane", "datum_plane"):
            for filter_name, value in (("axis", "z"), ("normal", [0, 0, 1]), ("offset", 0)):
                reference = {"kind": kind, "id": 163, filter_name: value}
                with (
                    self.subTest(reference=reference),
                    self.assertRaisesRegex(ValueError, "plane.reference.*id.*axis.*normal.*offset"),
                ):
                    validate_operations([sketch(reference)])

    def test_invalid_id_types_and_range_fail_before_toolkit_lock(self):
        for value in (True, "163", 163.0, -1, 2147483648):
            for kind in ("plane", "datum_plane"):
                with self.subTest(kind=kind, value=value):
                    with patch.object(generic_bridge.bridge, "toolkit_lock") as lock:
                        with self.assertRaisesRegex(ValueError, "plane.reference.id.*integer"):
                            generic_bridge.submit(
                                [sketch({"kind": kind, "id": value})],
                                "a" * 32,
                                expected_revision=1,
                            )
                    lock.assert_not_called()

    def test_selector_mode_remains_valid_without_an_id(self):
        for reference in (
            {"kind": "datum_plane", "axis": "x"},
            {"kind": "datum_plane", "normal": [0, 1, 0], "offset": 3},
            {"kind": "plane", "axis": "z", "offset": 0},
        ):
            with self.subTest(reference=reference):
                self.assertEqual(
                    validate_operations([sketch(reference)])[0]["plane"]["reference"],
                    reference,
                )

    def test_dictionary_frame_requires_reference_and_nonzero_u_axis(self):
        for plane, error in (
            ({"u_axis": [0, 0, 1]}, "plane.reference"),
            (
                {"reference": {"kind": "datum_plane", "id": 163}, "u_axis": [0, 0, 0]},
                "plane.u_axis.*nonzero",
            ),
            (
                {"reference": {"kind": "datum_plane", "id": 163}, "origin": [0, 0]},
                "plane.origin.*3D",
            ),
        ):
            with self.subTest(plane=plane), self.assertRaisesRegex(ValueError, error):
                validate_operations(
                    [{**sketch({"kind": "datum_plane", "id": 163}), "plane": plane}]
                )


class PlanePublicToolValidation(unittest.IsolatedAsyncioTestCase):
    async def test_both_public_sketch_paths_reject_ambiguous_reference_before_submission(self):
        reference = {"kind": "datum_plane", "id": 163, "axis": "z"}
        for name, arguments in (
            (
                "creo_execute_plan",
                {
                    "model_id": "a" * 32,
                    "expected_revision": 1,
                    "operations": [sketch(reference)],
                },
            ),
            (
                "creo_create_sketch",
                {
                    "model_id": "a" * 32,
                    "expected_revision": 1,
                    "label": "profile",
                    "plane": {"reference": reference, "u_axis": [0, 0, 1]},
                    "entities": sketch(reference)["entities"],
                },
            ),
        ):
            with self.subTest(name=name):
                with (
                    patch.object(server.startup, "require_ready"),
                    patch.object(server.general.bridge, "toolkit_lock") as lock,
                ):
                    with self.assertRaisesRegex(Exception, "plane.reference.*id.*axis"):
                        await server.mcp.call_tool(name, arguments)
                lock.assert_not_called()

    async def test_public_examples_include_geometry_id_and_label_forms(self):
        references = server.reference_capabilities()
        self.assertEqual(references["datum_plane_id"], {"kind": "datum_plane", "id": 163})
        self.assertEqual(references["plane_id"], {"kind": "plane", "id": 163})
        self.assertEqual(references["datum_label"]["kind"], "datum_feature")
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        description = tools["creo_create_sketch"].input_schema["properties"]["plane"]["description"]
        self.assertIn("datum_plane", description)
        self.assertIn("surface", description)


if __name__ == "__main__":
    unittest.main()
