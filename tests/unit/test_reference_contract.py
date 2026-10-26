"""BUG-006 exact report reproduction, wire schemas and queue compatibility."""

import asyncio
import contextlib
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import bridge
import generic_bridge as general
import server
from creo_mechdog.references import reference_capabilities
from creo_mechdog.schema import AxisPatternOp, validate_operations

ROOT = Path(__file__).resolve().parents[2]


def pattern(axis):
    return {"op": "axis_pattern", "label": "copies", "leader": "leader", "axis": axis}


class ReferenceContractTests(unittest.TestCase):
    def test_exact_report_label_is_normalized_without_mutating_input(self):
        reported = pattern({"kind": "datum_feature", "label": "t82_da1"})
        original = copy.deepcopy(reported)
        validated = validate_operations([reported])[0]
        self.assertEqual(validated["axis"], {"kind": "datum_axis_feature", "label": "t82_da1"})
        self.assertEqual(reported, original)
        self.assertEqual(AxisPatternOp.model_validate(reported).axis, validated["axis"])

    def test_existing_geometry_and_specific_label_are_unchanged(self):
        for axis in (
            {"kind": "axis", "id": 83},
            {"kind": "datum_axis_feature", "label": "t82_da1"},
        ):
            self.assertEqual(validate_operations([pattern(axis)])[0]["axis"], axis)

    def test_wrong_kind_wrapper_and_invalid_identifier_have_actionable_errors(self):
        values = [
            {"kind": "datum_plane", "axis": "z"},
            {"kind": "surface", "id": 83},
            {"reference": {"kind": "axis", "id": 83}},
            {"edge": {"kind": "axis", "id": 83}},
            {"kind": "axis"},
            {"kind": "axis", "id": -1},
            {"kind": "axis", "id": True},
            {"kind": "axis", "id": "83"},
            {"kind": "datum_feature"},
            {"kind": "datum_feature", "label": ""},
            {"kind": "datum_axis_feature", "label": 83},
        ]
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValueError) as caught:
                validate_operations([pattern(value)])
            self.assertIn("datum_axis_feature", str(caught.exception))
            self.assertIn("Do not wrap", str(caught.exception))
            self.assertIn("id:N", str(caught.exception))

    def test_compatibility_alias_does_not_bypass_pattern_constraints(self):
        for change in (
            {"count": 1},
            {"increment_deg": 0},
            {"increment_deg": 361},
            {"label": "invalid-label"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_operations(
                    [{**pattern({"kind": "datum_feature", "label": "t82_da1"}), **change}]
                )

    def test_axis_compatibility_does_not_reinterpret_plane_or_flange_fields(self):
        plane = {
            "op": "datum_plane",
            "label": "offset_plane",
            "reference": {"kind": "datum_feature", "label": "plane_label"},
        }
        flange = {
            "op": "sheetmetal_flange",
            "label": "flange",
            "edge": {"kind": "edge", "id": 12},
            "height": 10,
        }
        values = validate_operations([plane, flange])
        self.assertEqual(values[0]["reference"], plane["reference"])
        self.assertEqual(values[1]["edge"], flange["edge"])

    def test_capability_examples_validate_with_operation_parameter_shapes(self):
        refs = reference_capabilities()
        tools = refs["by_tool"]
        legacy = {"datum_plane", "planar_solid_face", "raw_face", "raw_edge", "datum_label"}
        self.assertTrue(legacy <= set(refs))
        for key in ("axis", "axis_label", "compatibility_axis_label"):
            validate_operations([pattern(tools["creo_axis_pattern"][key])])
        operations = [
            {
                "op": "datum_plane",
                "label": "plane",
                "reference": tools["creo_datum_plane"]["reference"],
            },
            {
                "op": "datum_axis",
                "label": "axis",
                "references": tools["creo_datum_axis"]["references"],
            },
            {
                "op": "datum_csys",
                "label": "csys",
                "reference": tools["creo_datum_csys"]["reference"],
            },
            {
                "op": "datum_points",
                "label": "points",
                "reference": tools["creo_datum_points"]["reference"],
                "points": [{"name": "p", "position": [0, 0, 0]}],
            },
            {"op": "hole", "label": "hole", **tools["creo_hole"], "diameter": 2},
            {"op": "draft", "label": "draft", **tools["creo_draft"], "angle": 5},
            {
                "op": "boolean_bodies",
                "label": "combine",
                "method": "union",
                "targets": tools["creo_boolean_bodies"]["targets"],
                "tools": tools["creo_boolean_bodies"]["tools"],
            },
            {
                "op": "solidify",
                "label": "trim",
                "mode": "cut",
                "reference": tools["creo_solidify"]["reference"],
            },
            {"op": "surface_fill", "label": "fill", "sketch": tools["creo_surface_fill"]["sketch"]},
            {
                "op": "thicken",
                "label": "thick",
                "reference": tools["creo_thicken"]["reference"],
                "thickness": 2,
            },
            {
                "op": "sheetmetal_flange",
                "label": "flange",
                "edge": tools["creo_sheetmetal_flange"]["edge"],
                "height": 10,
            },
            {
                "op": "sketch",
                "label": "profile",
                "plane": tools["creo_create_sketch"]["plane"],
                "entities": [{"type": "circle", "name": "c", "center": [0, 0], "radius": 2}],
            },
        ]
        for name in ("round", "chamfer"):
            for key in ("references", "surface_pair_alternative"):
                operations.append(
                    {
                        "op": name,
                        "label": f"{name}_example",
                        "size": 1,
                        "references": tools[f"creo_{name}"][key],
                    }
                )
        for operation in operations:
            with self.subTest(operation=operation):
                validate_operations([operation])

    def test_schema_examples_list_all_three_axis_forms(self):
        tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
        self.assertEqual(len(tools), 93)
        axis = tools["creo_axis_pattern"].input_schema["properties"]["axis"]
        self.assertEqual(
            {form["properties"]["kind"]["const"] for form in axis["oneOf"]},
            {"axis", "datum_axis_feature", "datum_feature"},
        )
        for name in ("creo_round", "creo_chamfer"):
            self.assertIn(
                "Set list", tools[name].input_schema["properties"]["references"]["description"]
            )
        self.assertIn(
            "Bare edge",
            tools["creo_sheetmetal_flange"].input_schema["properties"]["edge"]["description"],
        )
        self.assertIn(
            "reference container",
            tools["creo_create_sketch"].input_schema["properties"]["plane"]["description"],
        )


class ReferenceQueueTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        fixture = tempfile.TemporaryDirectory(prefix="bug006_", dir=ROOT / ".tmp")
        self.addCleanup(fixture.cleanup)
        self.root = Path(fixture.name).resolve()
        self.model_id = "a" * 32
        model_dir = self.root / "models" / self.model_id
        model_dir.mkdir(parents=True)
        self.model_file = model_dir / "model.json"
        self.model = {
            "model_id": self.model_id,
            "model_name": "fixture",
            "model_type": "part",
            "status": "ready",
            "revision": 7,
            "pending_job": None,
            "aliases": {"t82_da1": {"feature_id": 43}, "leader": {"feature_id": 50}},
        }
        import hashlib

        output = model_dir / "output"
        output.mkdir()
        part = output / "fixture.prt.1"
        part.write_bytes(b"controlled saved baseline fixture")
        self.model.update(
            output_directory=str(output),
            part_file=str(part),
            part_sha256=hashlib.sha256(part.read_bytes()).hexdigest(),
        )
        self.model_file.write_text(json.dumps(self.model), encoding="utf-8")
        template = self.root / "creo/Common Files/templates/mmns_part_solid_abs.prt"
        template.parent.mkdir(parents=True)
        template.write_bytes(b"controlled fixture, never opened by Creo")
        self.enterContext(patch.object(bridge, "ROOT", self.root))
        self.enterContext(patch.object(bridge, "JOBS", self.root / "jobs"))
        self.enterContext(patch.object(general, "MODELS", self.root / "models"))
        self.enterContext(
            patch.object(bridge, "toolkit_lock", side_effect=lambda **kw: contextlib.nullcontext())
        )
        self.enterContext(
            patch.object(bridge, "config", return_value={"creo_root": str(self.root / "creo")})
        )
        self.spawn = self.enterContext(
            patch.object(general.subprocess, "Popen", return_value=Mock())
        )
        self.enterContext(patch.object(server.startup, "require_ready"))

    async def test_high_level_tool_and_execute_plan_queue_same_canonical_axis(self):
        inputs = {"model_id": self.model_id, "expected_revision": 7}
        for name, specific in (
            (
                "creo_axis_pattern",
                {
                    "label": "copies",
                    "leader": "leader",
                    "axis": {"kind": "datum_feature", "label": "t82_da1"},
                },
            ),
            (
                "creo_execute_plan",
                {"operations": [pattern({"kind": "datum_feature", "label": "t82_da1"})]},
            ),
        ):
            self.model_file.write_text(json.dumps(self.model), encoding="utf-8")
            result = await server.mcp.call_tool(name, {**inputs, **specific})
            self.assertFalse(result.is_error, result)
            job_id = result.structured_content["job_id"]
            request = bridge.read_json(self.root / "jobs" / job_id / "request.json")
            self.assertEqual(
                request["operations"][0]["axis"], {"kind": "datum_axis_feature", "label": "t82_da1"}
            )
            self.assertEqual(request["model"]["revision"], 7)
        self.assertEqual(self.spawn.call_count, 2)

    async def test_invalid_axis_and_stale_revision_do_not_create_or_launch_jobs(self):
        before = self.model_file.read_bytes()
        with self.assertRaises(ValueError):
            general.submit(
                [pattern({"kind": "datum_plane", "axis": "z"})], self.model_id, expected_revision=7
            )
        with self.assertRaisesRegex(ValueError, "Stale revision"):
            general.submit(
                [pattern({"kind": "datum_feature", "label": "t82_da1"})],
                self.model_id,
                expected_revision=6,
            )
        self.assertFalse((self.root / "jobs").exists())
        self.assertEqual(self.model_file.read_bytes(), before)
        self.spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
